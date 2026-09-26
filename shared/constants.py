"""Cross-cutting constants shared by the control plane and worker pool.

Anything that must match on both sides of the Redis boundary belongs here,
not scattered across modules. Values are read from the environment at import
time so systemd's EnvironmentFile is the single source of configuration.
"""

from __future__ import annotations

import os
from typing import Final


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name}={raw!r} is not an integer") from exc


# --- Redis Streams ---------------------------------------------------------
# Commands flow Django -> worker pool. Events flow worker pool -> Django.
# Both use consumer groups; see shared/schemas.py for message format.
REDIS_CMD_STREAM: Final[str] = "cip:cmd"
REDIS_EVT_STREAM: Final[str] = "cip:evt"

# Cap stream length so Redis memory is bounded even if a consumer falls far
# behind. 10k is days of commands at any realistic load for this project.
STREAM_MAXLEN: Final[int] = 10_000

# One consumer group per logical consumer class. Scaling a class means adding
# consumers to the same group, not creating new groups.
CMD_CONSUMER_GROUP: Final[str] = "worker-pool"
EVT_CONSUMER_GROUP: Final[str] = "control-plane"


# --- Redis keys ------------------------------------------------------------
REDIS_PORT_LEASES: Final[str] = "cip:ports"          # hash: port -> session_id
REDIS_HEARTBEAT_PREFIX: Final[str] = "cip:hb:"        # key per session, TTL
REDIS_IDLE_PREFIX: Final[str] = "cip:idle:"           # key per session, unix ts


# --- Port pool -------------------------------------------------------------
OPCUA_PORT_START: Final[int] = _int_env("OPCUA_PORT_START", 5000)
OPCUA_PORT_END: Final[int] = _int_env("OPCUA_PORT_END", 5100)


# --- Timeouts (seconds) ----------------------------------------------------
WORKER_STARTUP_TIMEOUT: Final[int] = _int_env("WORKER_STARTUP_TIMEOUT", 15)
WORKER_IDLE_TIMEOUT: Final[int] = _int_env("WORKER_IDLE_TIMEOUT", 1800)
WORKER_STOP_GRACE: Final[int] = _int_env("WORKER_STOP_GRACE", 10)
HEARTBEAT_INTERVAL: Final[int] = _int_env("HEARTBEAT_INTERVAL", 10)
HEARTBEAT_TTL: Final[int] = _int_env("HEARTBEAT_TTL", 30)
RECONCILE_INTERVAL: Final[int] = _int_env("RECONCILE_INTERVAL", 15)


# --- Loop rates (Hz) -------------------------------------------------------
# Physics and OPC UA run fast for stability and PLC fidelity. UI broadcast is
# deliberately lower: browsers do not need 10 Hz and DOM churn is expensive.
PHYSICS_HZ: Final[int] = _int_env("PHYSICS_HZ", 10)
UI_BROADCAST_HZ: Final[int] = _int_env("UI_BROADCAST_HZ", 4)

# --- Gateway ---------------------------------------------------------------
#The gateway reads the session event stream (cip:evt). When 
#a SessionReadyEvent arrives, it connects to the worker. When 
#SessionStoppedEvent or SessionFailedEvent arrives, it disconnects.
GATEWAY_OPCUA_PORT: Final[int] = _int_env("GATEWAY_OPCUA_PORT", 8080)
GATEWAY_EVT_CONSUMER_GROUP: Final[str] = "gateway"


# --- systemd integration ---------------------------------------------------
# Workers are transient systemd units so the daemon can rediscover them after
# a restart. This prefix is used in `systemctl list-units 'cip-worker-*'`.
SYSTEMD_UNIT_PREFIX: Final[str] = "cip-worker-"
PID_DIR: Final[str] = "/var/lib/cip-sim/pids"
