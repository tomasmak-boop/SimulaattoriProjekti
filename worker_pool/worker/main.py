"""Worker process entrypoint.

One worker runs exactly one simulation session:

    1. Loads a plugin from the registry
    2. Builds the OPC UA address space
    3. Starts the HTTP dashboard in a background thread
    4. Publishes a heartbeat to Redis every HEARTBEAT_INTERVAL seconds
    5. Runs the OPC UA tick loop until SIGTERM
    6. Cleans up (heartbeat key, idle key, PID file) before exit

Invoked by the daemon as a transient systemd unit, roughly:

    systemd-run --unit=cip-worker-<sid> --scope \\
        /opt/cip-sim/.venv/bin/python -m worker_pool.worker.main \\
            --session-id <sid> \\
            --simulation-id cip \\
            --opcua-port 5003 \\
            --http-port 6003 \\
            --advertise-host 10.0.0.5 \\
            --config '{"params": {}}'

Can also be run by hand for development; see --help.
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


# Default offset from OPC UA port to HTTP dashboard port. Worker on OPC UA
# 5003 serves its dashboard on 6003, so a firewall rule for one range covers
# both. Configurable via --http-port for unusual setups.
HTTP_PORT_OFFSET = 1000

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
    p.add_argument("--advertise-host", required=True,
                   help="Host or IP that OPC UA clients will use to connect.")
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
    port: int,
    adapter: OPCUAAdapter,
    stop: asyncio.Event,
) -> None:
    """Publish worker liveness and idle timestamp to Redis every interval.

    Two keys, both with TTL so a crash cleans up automatically:

        cip:hb:<sid>    JSON heartbeat, refreshed every HEARTBEAT_INTERVAL
        cip:idle:<sid>  Unix timestamp of the last external OPC UA activity

    The daemon reads these to decide if a session is alive and whether it
    should be stopped for idleness.
    """
    hb_key = f"{REDIS_HEARTBEAT_PREFIX}{session_id}"
    idle_key = f"{REDIS_IDLE_PREFIX}{session_id}"

    start_mono = time.monotonic()
    start_wall = time.time()
    last_seen_count = 0
    last_activity_wall = start_wall

    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_INTERVAL)
            return  # stop was set during the wait
        except asyncio.TimeoutError:
            pass

        # Detect new external activity by watching the adapter's counter.
        count = adapter.external_request_count()
        if count != last_seen_count:
            last_seen_count = count
            last_activity_wall = time.time()

        payload = json.dumps({
            "pid": os.getpid(),
            "port": port,
            "uptime": round(time.monotonic() - start_mono, 1),
            "requests": count,
        })

        try:
            await r.set(hb_key, payload, ex=HEARTBEAT_TTL)
            await r.set(idle_key, str(int(last_activity_wall)),
                        ex=HEARTBEAT_TTL * 2)
        except RedisError:
            log.exception("heartbeat write failed; will retry next interval")


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

    adapter = OPCUAAdapter(
        sim,
        advertise_host=args.advertise_host,
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
        "http_port": http_port,
        "pid": os.getpid(),
    })

    # Build the address space before publishing "ready". Any schema error
    # fails fast here rather than three seconds into the tick loop.
    await adapter.initialize()

    # Publish ready BEFORE the port is bound. The tiny race between this
    # event and the actual bind is acceptable: if bind fails a moment later,
    # the process exits non-zero and the daemon marks the session failed.
    # Avoiding this race properly would require splitting adapter.run() into
    # separate start/loop/stop phases; not worth the API churn right now.
    try:
        ready = SessionReadyEvent(
            session_id=args.session_id,
            port=args.opcua_port,
            pid=os.getpid(),
        )
        await r.xadd(
            REDIS_EVT_STREAM,
            {"payload": ready.model_dump_json()},
            maxlen=STREAM_MAXLEN,
        )
    except RedisError:
        log.exception("failed to publish ready event; continuing anyway")

    pid_path = _write_pid_file(args.session_id)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    dashboard.start()

    failed = False

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                adapter.run(stop),
                name=f"opcua-{args.session_id}",
            )
            tg.create_task(
                _heartbeat_loop(
                    r,
                    session_id=args.session_id,
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