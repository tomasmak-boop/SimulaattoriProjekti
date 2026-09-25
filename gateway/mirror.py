"""One worker connection inside the gateway.

Connects to a worker's OPC UA server as a client, reads its declared
commands/measurements/status, and mirrors the tree under a session folder
in the gateway's address space.
"""

from __future__ import annotations

from typing import Dict

from asyncua import Client, ua, Node

from shared.logging import get_logger

log = get_logger(__name__)


class WorkerMirror:
    def __init__(
        self,
        *,
        session_id: str,
        worker_endpoint: str,
        parent_folder: Node,
        namespace_idx: int,
    ) -> None:
        self.session_id = session_id
        self.worker_endpoint = worker_endpoint
        self.parent_folder = parent_folder
        self.namespace_idx = namespace_idx

        self._client: Client | None = None
        self._session_folder: Node | None = None
        self._subscription = None
        self._value_cache: Dict[str, object] = {}

    async def connect_and_mirror(self) -> None:
        self._client = Client(url=self.worker_endpoint)
        await self._client.connect()

        # Create session folder in gateway
        self._session_folder = await self.parent_folder.add_folder(
            ua.NodeId(f"Gateway.Sessions.{self.session_id}", self.namespace_idx),
            ua.QualifiedName(self.session_id, self.namespace_idx),
        )

        # Find the CIP (or other plugin) root in the worker
        worker_idx = await self._client.get_namespace_index(
            "urn:cip-sim:cip:2.0.0"  # TODO: derive dynamically
        )
        worker_root = await self._client.nodes.root.get_child(
            ["0:Objects", f"{worker_idx}:Clean-In-Place"]
        )

        # Mirror Commands, Measurements, Status
        for folder_name in ("Commands", "Measurements", "Status"):
            await self._mirror_folder(worker_root, folder_name, worker_idx)

        # Subscribe to Measurements and Status for value updates
        await self._start_subscription()

    async def _mirror_folder(self, worker_root: Node, folder_name: str,
                             worker_idx: int) -> None:
        """Mirror a single folder and its variables into the gateway."""
        worker_folder = await worker_root.get_child(
            [f"{worker_idx}:{folder_name}"]
        )
        gateway_folder = await self._session_folder.add_folder(
            ua.NodeId(
                f"Gateway.Sessions.{self.session_id}.{folder_name}",
                self.namespace_idx,
            ),
            ua.QualifiedName(folder_name, self.namespace_idx),
        )

        for child in await worker_folder.get_children():
            browse_name = await child.read_browse_name()
            name = browse_name.Name

            # Read the DataType and ValueRank to recreate the variable
            data_type_node = await child.read_data_type()
            variant_type = await self._map_data_type(data_type_node)

            # Read current value
            value = await child.read_value()

            # Create mirrored variable
            new_var = await gateway_folder.add_variable(
                ua.NodeId(
                    f"Gateway.Sessions.{self.session_id}.{folder_name}.{name}",
                    self.namespace_idx,
                ),
                ua.QualifiedName(name, self.namespace_idx),
                value,
                variant_type,
            )
            await new_var.set_writable()
            self._value_cache[name] = value

            # If this is a command, wire up a setter that writes to the worker.
            if folder_name == "Commands":
                self._server.set_attribute_value_setter(
                    new_var.nodeid,
                    self._make_proxy_setter(child, name),
                )

    async def _start_subscription(self) -> None:
        """Subscribe to worker measurements/status for live updates."""
        self._subscription = await self._client.create_subscription(
            500,  # ms publishing interval
            self,
        )
        # TODO: subscribe to measurement and status nodes,
        # update gateway variables in the datachange handler.

    async def disconnect(self) -> None:
        if self._subscription:
            await self._subscription.delete()
        if self._client:
            await self._client.disconnect()