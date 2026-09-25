"""Gateway OPC UA server.

Owns the aggregate address space. Each active session appears under
Objects/Gateway/Sessions/<session_id>/. Mirrors are kept in a dict and
updated as session events arrive.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

import redis.asyncio as aioredis
from asyncua import Server, ua
from asyncua.common.utils import ServiceError

from gateway.mirror import WorkerMirror
from shared.constants import (
    GATEWAY_EVT_CONSUMER_GROUP,
    REDIS_EVT_STREAM,
)
from shared.logging import get_logger
from shared.schemas import (
    SessionFailedEvent,
    SessionReadyEvent,
    SessionStoppedEvent,
    parse_event,
)


log = get_logger(__name__)


class Gateway:
    def __init__(
        self,
        *,
        advertise_host: str,
        port: int,
        redis: aioredis.Redis,
    ) -> None:
        self._advertise_host = advertise_host
        self._port = port
        self._redis = redis

        self._server = Server()
        self._namespace_idx: int = 0
        self._sessions_folder: ua.Node | None = None

        self._mirrors: dict[str, WorkerMirror] = {}
        self._mirrors_lock = asyncio.Lock()

        # Pending outbound writes to workers, drained by a background task.
        # The setter callback is synchronous; enqueueing here decouples it
        # from the async write to the worker.
        self._write_queue: asyncio.Queue[tuple[str, str, Any]] = asyncio.Queue()
        self._write_task: asyncio.Task | None = None

        self._endpoint = f"opc.tcp://{advertise_host}:{port}/gateway/"

    # --- lifecycle ---

    async def start(self) -> None:
        await self._server.init()
        self._server.set_endpoint(self._endpoint)
        self._server.set_server_name("CIP Simulation Gateway")
        await self._server.set_application_uri("urn:cip-sim:gateway")
        self._server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        self._server.set_identity_tokens([ua.AnonymousIdentityToken])

        self._namespace_idx = await self._server.register_namespace(
            "urn:cip-sim:gateway:1.0.0"
        )
        ns = self._namespace_idx

        root = await self._server.nodes.objects.add_object(
            ua.NodeId("Gateway", ns),
            ua.QualifiedName("Gateway", ns),
        )
        self._sessions_folder = await root.add_folder(
            ua.NodeId("Gateway.Sessions", ns),
            ua.QualifiedName("Sessions", ns),
        )

        self._write_task = asyncio.create_task(self._drain_writes())

        await self._server.start()
        log.info("gateway listening", extra={"endpoint": self._endpoint})

    async def stop(self) -> None:
        if self._write_task:
            self._write_task.cancel()
            try:
                await self._write_task
            except (asyncio.CancelledError, Exception):
                pass

        async with self._mirrors_lock:
            mirrors = list(self._mirrors.values())
            self._mirrors.clear()
        for m in mirrors:
            try:
                await m.disconnect()
            except Exception:
                log.exception("error disconnecting mirror",
                              extra={"session_id": m.session_id})

        await self._server.stop()

    # --- event loop ---

    async def run_event_loop(self, stop: asyncio.Event) -> None:
        # Ensure the consumer group exists. MKSTREAM creates the stream
        # if it doesn't exist yet.
        try:
            await self._redis.xgroup_create(
                REDIS_EVT_STREAM, GATEWAY_EVT_CONSUMER_GROUP,
                id="$", mkstream=True,
            )
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

        consumer = f"gateway-{self._port}"

        while not stop.is_set():
            try:
                entries = await asyncio.wait_for(
                    self._redis.xreadgroup(
                        GATEWAY_EVT_CONSUMER_GROUP, consumer,
                        {REDIS_EVT_STREAM: ">"},
                        count=10, block=2000,
                    ),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                continue
            except Exception:
                log.exception("xreadgroup failed")
                await asyncio.sleep(1.0)
                continue

            for _stream, messages in entries:
                for msg_id, fields in messages:
                    await self._handle_event(fields)
                    try:
                        await self._redis.xack(
                            REDIS_EVT_STREAM, GATEWAY_EVT_CONSUMER_GROUP, msg_id,
                        )
                    except Exception:
                        log.exception("xack failed")

    async def _handle_event(self, fields: dict) -> None:
        payload = fields.get("payload")
        if not payload:
            return
        try:
            event = parse_event(payload)
        except Exception:
            log.exception("bad event payload")
            return

        if isinstance(event, SessionReadyEvent):
            await self._add_mirror(event)
        elif isinstance(event, (SessionStoppedEvent, SessionFailedEvent)):
            await self._remove_mirror(event.session_id)

    # --- mirrors ---

    async def _add_mirror(self, ev: SessionReadyEvent) -> None:
        async with self._mirrors_lock:
            if ev.session_id in self._mirrors:
                return

        # The worker advertises a public endpoint, but the gateway is on the
        # same host and can reach it on loopback. Use loopback regardless of
        # what the worker advertises, because public ports may be blocked
        # between the two processes too.
        worker_endpoint = f"opc.tcp://127.0.0.1:{ev.port}/{ev.simulation_id}/"

        mirror = WorkerMirror(
            session_id=ev.session_id,
            simulation_id=ev.simulation_id,
            worker_endpoint=worker_endpoint,
            parent_folder=self._sessions_folder,
            namespace_idx=self._namespace_idx,
            server=self._server,
            enqueue_write=self._enqueue_write,
        )

        try:
            await mirror.connect_and_mirror()
        except Exception:
            log.exception("failed to mirror worker",
                          extra={"session_id": ev.session_id})
            return

        async with self._mirrors_lock:
            self._mirrors[ev.session_id] = mirror
        log.info("mirror added", extra={"session_id": ev.session_id})

    async def _remove_mirror(self, session_id: str) -> None:
        async with self._mirrors_lock:
            mirror = self._mirrors.pop(session_id, None)
        if mirror is None:
            return
        try:
            await mirror.disconnect()
        except Exception:
            log.exception("error disconnecting mirror",
                          extra={"session_id": session_id})
        log.info("mirror removed", extra={"session_id": session_id})

    # --- write forwarding ---

    def _enqueue_write(self, session_id: str, command_name: str, value: Any) -> None:
        """Called from the sync OPC UA setter to queue a write to a worker."""
        self._write_queue.put_nowait((session_id, command_name, value))

    async def _drain_writes(self) -> None:
        while True:
            session_id, command_name, value = await self._write_queue.get()
            mirror = self._mirrors.get(session_id)
            if mirror is None:
                continue
            try:
                await mirror.forward_command(command_name, value)
            except Exception:
                log.exception("command forward failed",
                              extra={"session_id": session_id,
                                     "command": command_name})