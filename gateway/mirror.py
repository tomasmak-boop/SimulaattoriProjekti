"""Mirror one worker's OPC UA address space inside the gateway.

Reads the worker's schema once at connect time to build a mirrored subtree
under the session folder. Subscribes to the worker's measurement and status
nodes so gateway values stay current. Command nodes get a setter that
forwards writes back to the worker through the gateway's write queue.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from asyncua import Client, Node, Server, ua

from shared.logging import get_logger


log = get_logger(__name__)


# Map from OPC UA DataType NodeId to VariantType. Covers the types our
# plugins use today. Extend as new plugins need new types.
_VARIANT_BY_NODEID: dict[str, ua.VariantType] = {
    "i=1": ua.VariantType.Boolean,
    "i=3": ua.VariantType.Int16,
    "i=4": ua.VariantType.UInt16,
    "i=5": ua.VariantType.Int32,
    "i=6": ua.VariantType.UInt32,
    "i=7": ua.VariantType.Int64,
    "i=8": ua.VariantType.UInt64,
    "i=10": ua.VariantType.Float,
    "i=11": ua.VariantType.Double,
    "i=12": ua.VariantType.String,
}

# Namespace prefix for the simulation plugins. When a worker is CIP, its
# root node lives under this URI. When it's blinker, a different one.
_SIM_NAMESPACES = {
    "cip": "urn:cip-sim:cip:2.0.0",
    "blinker": "urn:cip-sim:blinker:1.0.0",
}

# Human-readable folder name each plugin registers under Objects.
_SIM_FOLDER_NAMES = {
    "cip": "Clean-In-Place",
    "blinker": "Blinking Light",
}


class WorkerMirror:
    def __init__(
        self,
        *,
        session_id: str,
        simulation_id: str,
        worker_endpoint: str,
        parent_folder: Node,
        namespace_idx: int,
        server: Server,
        enqueue_write: Callable[[str, str, Any], None],
    ) -> None:
        self.session_id = session_id
        self.simulation_id = simulation_id
        self.worker_endpoint = worker_endpoint
        self._parent_folder = parent_folder
        self._namespace_idx = namespace_idx
        self._server = server
        self._enqueue_write = enqueue_write

        self._client: Client | None = None
        self._session_folder: Node | None = None
        self._subscription = None

        # Map of worker NodeId -> gateway Node, per folder, so the
        # subscription handler can find the gateway node to update.
        self._worker_to_gateway: dict[str, Node] = {}

    # --- lifecycle ---

    async def connect_and_mirror(self) -> None:
        self._client = Client(url=self.worker_endpoint)
        await self._client.connect()
        log.info("connected to worker", extra={
            "session_id": self.session_id, "endpoint": self.worker_endpoint,
        })

        ns = self._namespace_idx
        self._session_folder = await self._parent_folder.add_folder(
            ua.NodeId(f"Gateway.Sessions.{self.session_id}", ns),
            ua.QualifiedName(self.session_id, ns),
        )

        # Find the simulation's root folder in the worker
        worker_ns = await self._client.get_namespace_index(
            _SIM_NAMESPACES[self.simulation_id]
        )
        worker_folder_name = _SIM_FOLDER_NAMES[self.simulation_id]
        worker_root = await self._client.nodes.root.get_child([
            "0:Objects", f"{worker_ns}:{worker_folder_name}",
        ])

        for folder_name in ("Commands", "Measurements", "Status"):
            try:
                await self._mirror_folder(
                    worker_root, folder_name, worker_ns
                )
            except Exception:
                log.exception("failed to mirror folder",
                              extra={"folder": folder_name,
                                     "session_id": self.session_id})

        await self._start_subscription()

    async def disconnect(self) -> None:
        if self._subscription is not None:
            try:
                await self._subscription.delete()
            except Exception:
                pass
            self._subscription = None
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None

    # --- mirroring ---

    async def _mirror_folder(
        self, worker_root: Node, folder_name: str, worker_ns: int
    ) -> None:
        worker_folder = await worker_root.get_child([f"{worker_ns}:{folder_name}"])

        ns = self._namespace_idx
        gateway_folder = await self._session_folder.add_folder(
            ua.NodeId(
                f"Gateway.Sessions.{self.session_id}.{folder_name}", ns
            ),
            ua.QualifiedName(folder_name, ns),
        )

        for worker_child in await worker_folder.get_children():
            await self._mirror_variable(
                worker_child, gateway_folder, folder_name
            )

    async def _mirror_variable(
        self, worker_node: Node, gateway_folder: Node, folder_name: str
    ) -> None:
        name = (await worker_node.read_browse_name()).Name
        dtype_nodeid = await worker_node.read_data_type_as_variant_type()
        variant_type = dtype_nodeid  # asyncua returns VariantType directly here

        try:
            value = await worker_node.read_value()
        except Exception:
            value = _default_for(variant_type)

        ns = self._namespace_idx
        gateway_node = await gateway_folder.add_variable(
            ua.NodeId(
                f"Gateway.Sessions.{self.session_id}"
                f".{folder_name}.{name}", ns
            ),
            ua.QualifiedName(name, ns),
            value,
            variant_type,
        )
        await gateway_node.set_writable()

        # Track for subscription handler
        self._worker_to_gateway[worker_node.nodeid.to_string()] = gateway_node

        # Commands are writable in the gateway and forwarded to the worker.
        if folder_name == "Commands":
            self._server.set_attribute_value_setter(
                gateway_node.nodeid,
                self._make_command_setter(name),
            )

    def _make_command_setter(self, name: str):
        session_id = self.session_id
        enqueue = self._enqueue_write

        def set_value(node_data, attribute, value: ua.DataValue) -> None:
            if value is None or value.Value is None:
                return
            raw = value.Value.Value
            # Accept the write immediately (client sees success), then
            # forward asynchronously. Eventual consistency is acceptable
            # for commands; the physics will reflect the change within a
            # tick or two.
            node_data.attributes[attribute].value = value
            enqueue(session_id, name, raw)

        return set_value

    # --- subscription ---

    async def _start_subscription(self) -> None:
        if self._client is None:
            return

        handler = _MirrorSubscriptionHandler(
            worker_to_gateway=self._worker_to_gateway,
        )
        self._subscription = await self._client.create_subscription(500, handler)

        worker_nodes = [
            self._client.get_node(nid_str)
            for nid_str in self._worker_to_gateway.keys()
        ]
        if worker_nodes:
            await self._subscription.subscribe_data_change(worker_nodes)

    # --- command forwarding ---

    async def forward_command(self, name: str, value: Any) -> None:
        """Write a command to the worker's corresponding node."""
        if self._client is None:
            return

        worker_ns = await self._client.get_namespace_index(
            _SIM_NAMESPACES[self.simulation_id]
        )
        worker_folder_name = _SIM_FOLDER_NAMES[self.simulation_id]

        node = await self._client.nodes.root.get_child([
            "0:Objects",
            f"{worker_ns}:{worker_folder_name}",
            f"{worker_ns}:Commands",
            f"{worker_ns}:{name}",
        ])

        variant_type = await node.read_data_type_as_variant_type()
        await node.write_value(ua.Variant(value, variant_type))


class _MirrorSubscriptionHandler:
    """Handle datachange from worker, push new value into gateway node."""

    def __init__(self, worker_to_gateway: dict[str, Node]) -> None:
        self._map = worker_to_gateway

    def datachange_notification(self, node: Node, val: Any, data) -> None:
        gateway_node = self._map.get(node.nodeid.to_string())
        if gateway_node is None:
            return
        # The handler is called synchronously inside the client's event
        # loop. Schedule the gateway write as a task.
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(_safe_write(gateway_node, val))


async def _safe_write(node: Node, value: Any) -> None:
    try:
        await node.write_value(value)
    except Exception:
        log.exception("mirror value update failed")


def _default_for(variant_type: ua.VariantType) -> Any:
    if variant_type == ua.VariantType.Boolean:
        return False
    if variant_type in (ua.VariantType.Int16, ua.VariantType.Int32,
                        ua.VariantType.Int64):
        return 0
    if variant_type in (ua.VariantType.UInt16, ua.VariantType.UInt32,
                        ua.VariantType.UInt64):
        return 0
    if variant_type in (ua.VariantType.Float, ua.VariantType.Double):
        return 0.0
    if variant_type == ua.VariantType.String:
        return ""
    return None