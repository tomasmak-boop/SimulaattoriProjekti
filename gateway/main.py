"""OPC UA Aggregation Gateway entrypoint.

Exposes one OPC UA endpoint on a whitelisted port. Internally connects to
each running worker as a client, mirrors its schema under a session folder,
and proxies reads/writes through subscriptions and value setters.

The gateway reads session lifecycle events from the Redis events stream.
When a session becomes ready, a WorkerMirror connects and mirrors it. When
a session stops, the mirror is torn down.

On startup, the gateway reconciles against Redis heartbeats so it picks up
workers that were already running before the gateway started.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import os
import signal
import sys

import redis.asyncio as aioredis

from gateway.server import Gateway
from shared.constants import (
    GATEWAY_OPCUA_PORT,
    GATEWAY_RECONNECT_ATTEMPTS,
    GATEWAY_RECONNECT_BASE_DELAY,
    GATEWAY_RECONNECT_MAX_DELAY,
    GATEWAY_SAMPLING_INTERVAL_MS,
)
from shared.logging import configure_logging, get_logger


log = get_logger(__name__)


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than 0")
    return parsed


async def _run(args: argparse.Namespace) -> int:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = aioredis.from_url(redis_url, decode_responses=True)

    gateway = Gateway(
        advertise_host=args.advertise_host,
        port=args.port,
        redis=r,
        reconnect_attempts=args.reconnect_attempts,
        reconnect_base_delay=args.reconnect_base_delay,
        reconnect_max_delay=args.reconnect_max_delay,
        sampling_interval_ms=args.sampling_interval_ms,
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    # 1. Start the OPC UA server.
    await gateway.start()

    # 2. Pick up any workers that were already running before we started.
    #    This makes the gateway restart-safe: it does not depend on having
    #    seen the SessionReadyEvent, only on the worker's heartbeat.
    await gateway.reconcile_existing()

    # 3. Consume new events until signalled to stop.
    failed = False
    try:
        await gateway.run_event_loop(stop)
    except Exception:
        log.exception("gateway event loop failed")
        failed = True
    finally:
        await gateway.stop()
        try:
            await r.aclose()
        except Exception:
            pass

    return 1 if failed else 0


def main() -> int:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    p = argparse.ArgumentParser(description="OPC UA Aggregation Gateway")
    p.add_argument("--advertise-host", required=True,
                   help="Host/IP the gateway advertises (e.g. 10.120.32.67)")
    p.add_argument("--port", type=int, default=GATEWAY_OPCUA_PORT)
    p.add_argument(
        "--reconnect-attempts", type=_positive_int,
        default=GATEWAY_RECONNECT_ATTEMPTS,
    )
    p.add_argument(
        "--reconnect-base-delay", type=_positive_float,
        default=GATEWAY_RECONNECT_BASE_DELAY,
    )
    p.add_argument(
        "--reconnect-max-delay", type=_positive_float,
        default=GATEWAY_RECONNECT_MAX_DELAY,
    )
    p.add_argument(
        "--sampling-interval-ms", type=_positive_int,
        default=GATEWAY_SAMPLING_INTERVAL_MS,
    )
    args = p.parse_args()
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())