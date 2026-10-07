"""Worker process entrypoint.

One worker runs exactly one simulation session:

    1. Loads a plugin from the registry
    2. Builds the OPC UA address space
    3. Starts the HTTP dashboard in a background thread
    4. Publishes a heartbeat to Redis every HEARTBEAT_INTERVAL seconds
    5. Runs the OPC UA tick loop until SIGTERM
    6. Cleans up (heartbeat key, idle key, PID file) before exit

Run by the daemon as a subprocess (see worker_pool/manager.py). Can also
be run by hand for development; see --help.

Bind vs advertise: workers are internal — the gateway is their only
client, and it connects over loopback. So the default bind_host is
127.0.0.1, and advertise_host defaults to the same. Set advertise_host
to a different value only if a client needs to reach the worker
directly (rare; the gateway is the intended entry point).

Ready signalling: SessionReadyEvent is published by the adapter's
on_ready callback, which fires once the OPC UA port is actually bound.
Publishing before bind caused a race where the gateway tried to connect
to a socket that wasn't listening yet and gave up.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from shared.constants import (
    HEARTBEAT_INTERVAL,
    HEARTBEAT_TTL,
    HTTP_PORT_OFFSET,
    PID_DIR,
    REDIS_EVT_STREAM,
    REDIS_HEARTBEAT_PREFIX,
    REDIS_IDLE_PREFIX,
    STREAM_MAXLEN,
)
from shared.logging import configure_logging, get_logger
from shared.schemas import SessionReadyEvent
from sim_runtime.base import SimulationConfig
from sim_runtime.http_adapter import HTTPDashboard
from sim_runtime.opcua_adapter import OPCUAAdapter
from sim_runtime.registry import SimulationRegistry


log = get_logger(__name__)


# Fallback PID directory when the configured one is not writable (e.g. dev
# runs outside systemd). Real deploys use PID_DIR.
_FALLBACK_PID_DIR = Path("/tmp/cip-sim-pids")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run one simulation worker.")
    p.add_argument("--session-id", required=True)
    p.add_argument("--simulation-id", required=True)
    p.add_argument("--opcua-port", type=int, required=True)

    # Two separate concepts. bind_host is the interface the socket is
    # attached to; advertise_host is what goes into the OPC UA
    # discovery response. They default to the same value (loopback) so
    # the gateway can reach the worker and any client that happens to
    # see the URL can too.
    p.add_argument(
        "--bind-host", default="127.0.0.1",
        help="Interface to bind the OPC UA socket to. Default: 127.0.0.1 "
             "(workers are internal, reachable by the gateway over "
             "loopback).",
    )
    p.add_argument(
        "--advertise-host", default=None,
        help="Host that appears in the OPC UA endpoint URL. Defaults to "
             "--bind-host. Set this only if a client must reach the worker "
             "at a different address than it binds to.",
    )

    p.add_argument("--http-host", default="0.0.0.0")
    p.add_argument("--http-port", type=int, default=None,
                   help=f"Defaults to opcua_port + {HTTP_PORT_OFFSET}.")
    p.add_argument("--config", default="{}",
                   help="JSON config passed to the plugin as SimulationConfig.params.")
    return p.parse_args(argv)


def _parse_config(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--config is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit("--config must be a JSON object")
    # Accept either {"params": {...}} or a flat dict; flat is treated as params.
    return parsed.get("params", parsed)


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

async def _heartbeat_loop(
    r: aioredis.Redis,
    *,
    session_id: str,
    simulation_id: str,
    port: int,
    adapter: OPCUAAdapter,
    stop: asyncio.Event,
) -> None:
    """Publish worker liveness and idle timestamp to Redis every interval.

    Two keys, both with TTL so a crash cleans up automatically:

        cip:hb:<sid>    JSON heartbeat, refreshed every HEARTBEAT_INTERVAL
        cip:idle:<sid>  Unix timestamp of the last external OPC UA activity

    The heartbeat payload includes simulation_id so the gateway can
    discover what plugin a session is running when it reconciles on
    startup, without needing a separate metadata key.

    The first heartbeat is written immediately so the worker is visible
    to the gateway and to reconciliation without an interval-long delay.
    """
    hb_key = f"{REDIS_HEARTBEAT_PREFIX}{session_id}"
    idle_key = f"{REDIS_IDLE_PREFIX}{session_id}"

    start_mono = time.monotonic()
    last_seen_count = 0
    last_activity_wall = time.time()

    async def write_heartbeat() -> None:
        nonlocal last_seen_count, last_activity_wall
        count = adapter.external_request_count()
        if count != last_seen_count:
            last_seen_count = count
            last_activity_wall = time.time()

        payload = json.dumps({
            "pid": os.getpid(),
            "port": port,
            "simulation_id": simulation_id,
            "uptime": round(time.monotonic() - start_mono, 1),
            "requests": count,
        })
        try:
            await r.set(hb_key, payload, ex=HEARTBEAT_TTL)
            await r.set(idle_key, str(int(last_activity_wall)),
                        ex=HEARTBEAT_TTL * 2)
        except RedisError:
            log.exception("heartbeat write failed; will retry next interval")

    # Immediate first heartbeat.
    await write_heartbeat()

    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_INTERVAL)
            return  # stop was set during the wait
        except asyncio.TimeoutError:
            pass
        await write_heartbeat()


# ---------------------------------------------------------------------------
# Ready event
# ---------------------------------------------------------------------------

async def _publish_ready(
    r: aioredis.Redis,
    *,
    session_id: str,
    simulation_id: str,
    port: int,
) -> None:
    """Publish SessionReadyEvent.

    Called by the adapter's on_ready callback once the OPC UA port is
    actually bound and the server is accepting connections. Publishing
    earlier (before bind) is what caused the gateway to race on
    ConnectionRefusedError.
    """
    try:
        ready = SessionReadyEvent(
            session_id=session_id,
            simulation_id=simulation_id,
            port=port,
            pid=os.getpid(),
        )
        await r.xadd(
            REDIS_EVT_STREAM,
            {"payload": ready.model_dump_json()},
            maxlen=STREAM_MAXLEN,
        )
    except RedisError:
        log.exception("failed to publish ready event; continuing anyway")


# ---------------------------------------------------------------------------
# PID file
# ---------------------------------------------------------------------------

def _write_pid_file(session_id: str) -> Path | None:
    """Write our PID to a well-known path. Returns the path, or None on failure.

    The daemon uses PID files only as an advisory signal; Redis heartbeats
    are the authoritative liveness check. If we cannot create the file
    (permissions, unwritable directory), we log and continue.
    """
    for candidate in (Path(PID_DIR), _FALLBACK_PID_DIR):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            path = candidate / f"{session_id}.pid"
            path.write_text(str(os.getpid()))
            return path
        except OSError:
            continue
    log.warning("could not write PID file; proceeding without one")
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _run(args: argparse.Namespace) -> int:
    registry = SimulationRegistry()
    registry.load_from()

    try:
        sim_class = registry.get(args.simulation_id)
    except Exception as exc:
        log.error("cannot load simulation", extra={
            "simulation_id": args.simulation_id, "error": str(exc)
        })
        return 2

    sim = sim_class(SimulationConfig(
        session_id=args.session_id,
        params=_parse_config(args.config),
    ))

    http_port = args.http_port if args.http_port is not None else (
        args.opcua_port + HTTP_PORT_OFFSET
    )

    # advertise_host defaults to bind_host when not given.
    bind_host = args.bind_host
    advertise_host = args.advertise_host or bind_host

    adapter = OPCUAAdapter(
        sim,
        advertise_host=advertise_host,
        bind_host=bind_host,
        port=args.opcua_port,
    )
    dashboard = HTTPDashboard(
        sim,
        host=args.http_host,
        port=http_port,
        session_id=args.session_id,
        endpoint=adapter.endpoint,
    )

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = aioredis.from_url(redis_url, decode_responses=True)

    hb_key = f"{REDIS_HEARTBEAT_PREFIX}{args.session_id}"
    idle_key = f"{REDIS_IDLE_PREFIX}{args.session_id}"

    log.info("worker starting", extra={
        "session_id": args.session_id,
        "simulation_id": args.simulation_id,
        "endpoint": adapter.endpoint,
        "bind_host": bind_host,
        "http_port": http_port,
        "pid": os.getpid(),
    })

    # Build the address space before entering the run loop. Any schema
    # error fails fast here, rather than three seconds into the tick
    # loop when the port is already bound and half a session exists.
    await adapter.initialize()

    pid_path = _write_pid_file(args.session_id)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    dashboard.start()

    # Ready fires from inside adapter.run() once the port is bound.
    async def on_ready() -> None:
        await _publish_ready(
            r,
            session_id=args.session_id,
            simulation_id=args.simulation_id,
            port=args.opcua_port,
        )

    failed = False

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                adapter.run(stop, on_ready=on_ready),
                name=f"opcua-{args.session_id}",
            )
            tg.create_task(
                _heartbeat_loop(
                    r,
                    session_id=args.session_id,
                    simulation_id=args.simulation_id,
                    port=args.opcua_port,
                    adapter=adapter,
                    stop=stop,
                ),
                name=f"heartbeat-{args.session_id}",
            )
    except* Exception as eg:
        # TaskGroup wraps errors. Log each and remember that something
        # went wrong; we return non-zero below so the daemon marks the
        # session as failed rather than cleanly stopped.
        #
        # Note: `return` is not allowed inside an `except*` block. Setting
        # a flag and returning after the try/except*/finally is the
        # standard workaround.
        for exc in eg.exceptions:
            log.error("worker task failed", extra={"error": repr(exc)})
        failed = True
    finally:
        dashboard.stop()
        try:
            await r.delete(hb_key, idle_key)
        except RedisError:
            log.exception("failed to remove heartbeat keys")
        if pid_path is not None:
            try:
                pid_path.unlink(missing_ok=True)
            except OSError:
                log.exception("failed to remove PID file")
        try:
            await r.aclose()
        except Exception:
            pass

    if failed:
        return 1

    log.info("worker exited cleanly")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    args = _parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())