"""Core gateway server.

Maintains a single OPC UA server endpoint and a pool of internal clients
(WorkerMirror instances) connected to each running worker.
"""

from __future__ import annotations

import asyncio
from typing import Dict

import redis.asyncio as aioredis
from asyncua import Server, ua

from shared.constants import (
    REDIS_EVT_STREAM,
    REDIS_STREAM_EVT_GROUP,
    HEARTBEAT_INTERVAL,
)
from shared.logging import get_logger
from shared.schemas import (
    SessionReadyEvent,
    SessionStoppedEvent,
    SessionFailedEvent,
    parse_event,
)

from gateway.mirror import WorkerMirror

log = get_logger(__name__)


class Gateway:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        redis: aioredis.Redis,
        advertise_host: str,
    ) -> None:
        self._host = host
        self._port = port
        self._advertise_host = advertise_host
        self._redis = redis

        self._server = Server()
        self._namespace_idx: int = 0
        self._sessions_folder: ua.Node | None = None

        self._mirrors: Dict[str, WorkerMirror] = {}
        self._mirrors_lock = asyncio.Lock()

    async def start(self) -> None:
        await self._server.init()
        self._server.set_endpoint(
            f"opc.tcp://{self._advertise_host}:{self._port}/gateway/"
        )
        self._server.set_server_name("CIP Simulation Gateway")
        self._server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        self._server.set_identity_tokens([ua.AnonymousIdentityToken])

        self._namespace_idx = await self._server.register_namespace(
            "urn:cip-sim:gateway:1.0.0"
        )

        root = await self._server.nodes.objects.add_object(
            ua.NodeId("Gateway", self._namespace_idx),
            ua.QualifiedName("Gateway", self._namespace_idx),
        )
        self._sessions_folder = await root.add_folder(
            ua.NodeId("Gateway.Sessions", self._namespace_idx),
            ua.QualifiedName("Sessions", self._namespace_idx),
        )

        await self._server.start()
        log.info("gateway started", extra={"endpoint": self._server.endpoint})

    async def run_event_loop(self) -> None:
        """Consume session events and add/remove mirrors."""
        try:
            await self._redis.xgroup_create(
                REDIS_EVT_STREAM, REDIS_STREAM_EVT_GROUP,
                id="$", mkstream=True,
            )
        except Exception:
            # Group already exists
            pass

        consumer_name = "gateway-1"
        while True:
            entries = await self._redis.xreadgroup(
                REDIS_STREAM_EVT_GROUP,
                consumer_name,
                {REDIS_EVT_STREAM: ">"},
                count=10,
                block=5000,
            )
            for _stream, messages in entries:
                for msg_id, fields in messages:
                    payload = fields.get("payload")
                    if not payload:
                        await self._redis.xack(REDIS_EVT_STREAM,
                                               REDIS_STREAM_EVT_GROUP, msg_id)
                        continue
                    try:
                        event = parse_event(payload)
                    except Exception:
                        log.exception("bad event payload")
                        await self._redis.xack(REDIS_EVT_STREAM,
                                               REDIS_STREAM_EVT_GROUP, msg_id)
                        continue

                    if isinstance(event, SessionReadyEvent):
                        await self._on_session_ready(event)
                    elif isinstance(event, SessionStoppedEvent):
                        await self._on_session_stopped(event)
                    elif isinstance(event, SessionFailedEvent):
                        await self._on_session_failed(event)

                    await self._redis.xack(REDIS_EVT_STREAM,
                                           REDIS_STREAM_EVT_GROUP, msg_id)

    async def _on_session_ready(self, ev: SessionReadyEvent) -> None:
        async with self._mirrors_lock:
            if ev.session_id in self._mirrors:
                return
            mirror = WorkerMirror(
                session_id=ev.session_id,
                worker_endpoint=f"opc.tcp://127.0.0.1:{ev.port}/{ev.simulation_id}/",
                parent_folder=self._sessions_folder,
                namespace_idx=self._namespace_idx,
            )
            try:
                await mirror.connect_and_mirror()
            except Exception:
                log.exception("failed to mirror worker",
                              extra={"session_id": ev.session_id})
                return
            self._mirrors[ev.session_id] = mirror
            log.info("mirror added", extra={"session_id": ev.session_id})

    async def _on_session_stopped(self, ev: SessionStoppedEvent) -> None:
        await self._remove_mirror(ev.session_id)

    async def _on_session_failed(self, ev: SessionFailedEvent) -> None:
        await self._remove_mirror(ev.session_id)

    async def _remove_mirror(self, session_id: str) -> None:
        async with self._mirrors_lock:
            mirror = self._mirrors.pop(session_id, None)
        if mirror is not None:
            try:
                await mirror.disconnect()
            except Exception:
                log.exception("error disconnecting mirror",
                              extra={"session_id": session_id})
            log.info("mirror removed", extra={"session_id": session_id})