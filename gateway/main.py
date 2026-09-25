"""OPC UA Aggregation Gateway.

Exposes a single OPC UA endpoint on a whitelisted port. Internally connects
to every running worker as a client, mirrors its schema under a session
folder, and proxies reads/writes/subscriptions.

Configuration comes from Redis: the set of active sessions and their ports
is published by the daemon. The gateway subscribes to session lifecycle
events and connects/disconnects workers dynamically.
"""

from __future__ import annotations

import asyncio
import argparse
import os
import sys

import redis.asyncio as aioredis
from asyncua import Server, ua

from shared.constants import (
    GATEWAY_OPCUA_PORT,
    REDIS_EVT_STREAM,
    REDIS_STREAM_EVT_GROUP,
)
from shared.logging import configure_logging, get_logger
from shared.schemas import parse_event, SessionStartedEvent, SessionStoppedEvent

log = get_logger(__name__)


async def _main(args: argparse.Namespace) -> int:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = aioredis.from_url(redis_url, decode_responses=True)

    gateway = Gateway(
        host=args.host,
        port=args.port,
        redis=r,
        advertise_host=args.advertise_host,
    )
    await gateway.start()

    # Consume session lifecycle events from Redis and connect/disconnect.
    await gateway.run_event_loop()


def main() -> int:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    p = argparse.ArgumentParser(description="OPC UA Aggregation Gateway")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=GATEWAY_OPCUA_PORT)
    p.add_argument("--advertise-host", required=True,
                   help="Host/IP the gateway advertises to clients (e.g. 10.120.32.67).")
    args = p.parse_args()
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main())