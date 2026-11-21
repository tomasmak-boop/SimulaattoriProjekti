from __future__ import annotations

import asyncio
import json
import os
import socket
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest
from asyncua import Client, Server, ua

from gateway.mirror import WorkerMirror
from gateway.server import Gateway
from shared.logging import get_logger
from shared.schemas import SessionReadyEvent, StartSessionCommand
from sim_runtime.http_adapter import _make_handler
from sim_runtime.opcua_adapter import OPCUAAdapter, _SessionUserManager
from sim_runtime.base import SimulationConfig
from sim_plugins.blinker.simulation import Blinker
from worker_pool import daemon
from worker_pool.port_allocator import PortPoolExhausted
from worker_pool.manager import WorkerPoolManager
from worker_pool.redis_bridge import RedisBridge


def test_logger_adapter_merges_context_and_call_extras(caplog):
    logger = get_logger("test.p3.logger", session_id="session-1")

    with caplog.at_level("INFO", logger="test.p3.logger"):
        logger.info("request", extra={"request_id": "request-1"})

    record = caplog.records[-1]
    assert record.session_id == "session-1"
    assert record.request_id == "request-1"


def test_logger_call_extra_overrides_context():
    logger = get_logger("test.p3.logger.override", value="context")
    logger.logger.setLevel("INFO")

    with patch.object(logger.logger, "handle") as handle:
        logger.info("request", extra={"value": "call"})

    assert handle.call_args.args[0].value == "call"


def test_ready_event_accepts_legacy_payload_without_http_port():
    event = SessionReadyEvent.model_validate({
        "kind": "session_ready",
        "session_id": "session-1",
        "session_name": "sim1",
        "simulation_id": "blinker",
        "port": 5000,
        "pid": 42,
    })

    assert event.http_port is None


def test_session_credentials_must_be_paired():
    with pytest.raises(ValueError):
        StartSessionCommand(
            request_id="request-1",
            session_id="session-1",
            session_name="sim1",
            simulation_id="blinker",
            opcua_username="user",
        )


def test_session_user_manager_accepts_only_matching_credentials():
    manager = _SessionUserManager("session-user", "secret-password")

    assert manager.get_user(
        None, username="session-user", password="secret-password"
    ).role.name == "User"
    assert manager.get_user(
        None, username="session-user", password="wrong-password"
    ) is None


@pytest.mark.asyncio
async def test_opcua_per_session_mode_requires_matching_username_token(monkeypatch):
    import sim_runtime.opcua_adapter as opcua_adapter

    monkeypatch.setattr(opcua_adapter, "OPCUA_AUTH_MODE", "per_session")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    adapter = OPCUAAdapter(
        Blinker(SimulationConfig(session_id="session-1")),
        advertise_host="127.0.0.1",
        bind_host="127.0.0.1",
        port=port,
        opcua_username="worker-user",
        opcua_password="worker-password",
    )
    await adapter.initialize()
    stop = asyncio.Event()
    ready = asyncio.Event()
    task = asyncio.create_task(
        adapter.run(stop, on_ready=ready.set)
    )
    try:
        await asyncio.wait_for(ready.wait(), timeout=5)

        anonymous = Client(url=adapter.endpoint)
        with pytest.raises(Exception):
            await anonymous.connect()

        invalid = Client(url=adapter.endpoint)
        invalid.set_user("worker-user")
        invalid.set_password("wrong-password")
        with pytest.raises(Exception):
            await invalid.connect()

        valid = Client(url=adapter.endpoint)
        valid.set_user("worker-user")
        valid.set_password("worker-password")
        await valid.connect()
        await valid.disconnect()
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=5)


@pytest.mark.asyncio
async def test_worker_mirror_disconnect_recursively_deletes_session_folder():
    server = SimpleNamespace(delete_nodes=AsyncMock(return_value=([], [])))
    client = SimpleNamespace(disconnect=AsyncMock())
    subscription = SimpleNamespace(delete=AsyncMock())
    mirror = WorkerMirror(
        session_id="session-1",
        session_name="sim1",
        simulation_id="blinker",
        worker_endpoint="opc.tcp://127.0.0.1:5000/blinker/",
        parent_folder=None,
        namespace_idx=1,
        server=server,
        enqueue_write=lambda *_: None,
    )
    folder = object()
    mirror._session_folder = folder
    mirror._client = client
    mirror._subscription = subscription

    await mirror.disconnect()

    subscription.delete.assert_awaited_once()
    client.disconnect.assert_awaited_once()
    server.delete_nodes.assert_awaited_once_with([folder], recursive=True)
    assert mirror._session_folder is None


@pytest.mark.asyncio
async def test_worker_mirror_allows_reusing_session_slug():
    server = Server()
    await server.init()
    namespace_idx = await server.register_namespace(
        "urn:cip-sim:gateway:test"
    )
    parent = await server.nodes.objects.add_folder(
        ua.NodeId("Gateway.Sessions", namespace_idx),
        ua.QualifiedName("Sessions", namespace_idx),
    )
    folder_id = ua.NodeId("Gateway.Sessions.sim1", namespace_idx)
    folder = await parent.add_folder(
        folder_id, ua.QualifiedName("sim1", namespace_idx)
    )
    mirror = WorkerMirror(
        session_id="session-1",
        session_name="sim1",
        simulation_id="blinker",
        worker_endpoint="opc.tcp://127.0.0.1:5000/blinker/",
        parent_folder=parent,
        namespace_idx=namespace_idx,
        server=server,
        enqueue_write=lambda *_: None,
    )
    mirror._session_folder = folder

    await mirror.disconnect()

    replacement = await parent.add_folder(
        folder_id, ua.QualifiedName("sim1", namespace_idx)
    )
    assert replacement.nodeid == folder_id


@pytest.mark.asyncio
async def test_gateway_reconciliation_reads_new_and_legacy_heartbeats():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    gateway = Gateway(
        advertise_host="127.0.0.1", port=8080, redis=redis
    )
    await redis.set("cip:hb:legacy", json.dumps({
        "pid": 10,
        "port": 5000,
        "simulation_id": "blinker",
    }))
    await redis.set("cip:hb:current", json.dumps({
        "pid": 11,
        "port": 5001,
        "http_port": 6001,
        "simulation_id": "blinker",
        "session_name": "current",
        "opcua_username": "worker",
        "opcua_password": "secret",
    }))
    with patch.object(gateway, "_add_mirror", new_callable=AsyncMock) as add:
        await gateway.reconcile_existing()

    events = {call.args[0].session_id: call.args[0] for call in add.await_args_list}
    assert events["legacy"].http_port is None
    assert events["current"].http_port == 6001
    assert events["current"].opcua_username == "worker"
    await redis.aclose()


@pytest.mark.asyncio
async def test_bridge_publishes_failure_when_port_pool_is_exhausted():
    manager = SimpleNamespace(
        start_worker=AsyncMock(side_effect=PortPoolExhausted("no ports"))
    )
    bridge = RedisBridge(redis=SimpleNamespace(), manager=manager)
    command = StartSessionCommand(
        request_id="request-1",
        session_id="session-1",
        session_name="sim1",
        simulation_id="blinker",
    )

    with patch.object(bridge, "publish_event", new_callable=AsyncMock) as publish:
        await bridge._handle_start(command)

    event = publish.await_args.args[0]
    assert event.kind == "session_failed"
    assert "port pool exhausted" in event.error


@pytest.mark.asyncio
async def test_worker_manager_scopes_credentials_to_one_child_process():
    manager = WorkerPoolManager(
        redis=SimpleNamespace(),
        port_allocator=SimpleNamespace(),
        advertise_host="127.0.0.1",
    )
    with (
        patch.dict(os.environ, {
            "OPCUA_SESSION_USERNAME": "stale-user",
            "OPCUA_SESSION_PASSWORD": "stale-password",
        }),
        patch(
            "worker_pool.manager.asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
        ) as spawn,
    ):
        await manager._spawn_process(
            session_id="session-1",
            session_name="sim1",
            simulation_id="blinker",
            port=5000,
            config_params={},
            opcua_username=None,
            opcua_password=None,
        )
        child_env = spawn.call_args.kwargs["env"]

    assert "OPCUA_SESSION_USERNAME" not in child_env
    assert "OPCUA_SESSION_PASSWORD" not in child_env

    with patch(
        "worker_pool.manager.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
    ) as spawn:
        await manager._spawn_process(
            session_id="session-2",
            session_name="sim2",
            simulation_id="blinker",
            port=5001,
            config_params={},
            opcua_username="worker-user",
            opcua_password="worker-password",
        )
        child_env = spawn.call_args.kwargs["env"]

    assert child_env["OPCUA_SESSION_USERNAME"] == "worker-user"
    assert child_env["OPCUA_SESSION_PASSWORD"] == "worker-password"


@pytest.mark.asyncio
async def test_idle_timeout_stops_worker_and_publishes_reason():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("cip:idle:session-1", str(int(time.time()) - 10))
    manager = SimpleNamespace(
        active_sessions=lambda: [{
            "session_id": "session-1",
            "session_name": "sim1",
        }],
        stop_worker=AsyncMock(return_value=True),
    )
    bridge = SimpleNamespace(publish_event=AsyncMock())
    stop = asyncio.Event()

    with patch.object(daemon, "WORKER_IDLE_TIMEOUT", 1):
        task = asyncio.create_task(daemon._idle_loop(
            redis=redis, manager=manager, bridge=bridge, stop=stop
        ))
        try:
            await asyncio.sleep(0.35)
        finally:
            stop.set()
            await asyncio.wait_for(task, timeout=2)

    manager.stop_worker.assert_awaited_once_with(
        "session-1", reason="idle_timeout"
    )
    event = bridge.publish_event.await_args.args[0]
    assert event.kind == "session_stopped"
    assert event.reason == "idle_timeout"
    await redis.aclose()


def test_http_dashboard_activity_callback_tracks_requests():
    activity: list[bool] = []
    handler = _make_handler(
        SimpleNamespace(SIMULATION_ID="blinker", snapshot=lambda: {}),
        session_id="session-1",
        endpoint="opc.tcp://127.0.0.1:5000/",
        page_bytes=b"ok",
        on_activity=lambda: activity.append(True),
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_address[1]}/health"
        ) as response:
            assert response.read() == b"ok"
        assert activity == [True]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
