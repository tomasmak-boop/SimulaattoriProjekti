"""Cross-cutting constants shared by the control plane and worker pool.

Anything that must match on both sides of the Redis boundary belongs here,
not scattered across modules. Values are read from the environment at import
time so systemd's EnvironmentFile is the single source of configuration.
"""

from __future__ import annotations

import math
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


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name}={raw!r} is not a number") from exc
    if not math.isfinite(value) or value <= 0:
        raise RuntimeError(f"{name} must be greater than zero")
    return value


# --- Redis Streams ---------------------------------------------------------
REDIS_CMD_STREAM: Final[str] = "cip:cmd"
REDIS_EVT_STREAM: Final[str] = "cip:evt"

STREAM_MAXLEN: Final[int] = 10_000

CMD_CONSUMER_GROUP: Final[str] = "worker-pool"
EVT_CONSUMER_GROUP: Final[str] = "control-plane"


# --- Redis keys ------------------------------------------------------------
REDIS_PORT_LEASES: Final[str] = "cip:ports"
REDIS_HEARTBEAT_PREFIX: Final[str] = "cip:hb:"
REDIS_IDLE_PREFIX: Final[str] = "cip:idle:"


# --- Port pool -------------------------------------------------------------
OPCUA_PORT_START: Final[int] = _int_env("OPCUA_PORT_START", 5000)
OPCUA_PORT_END: Final[int] = _int_env("OPCUA_PORT_END", 5100)
HTTP_PORT_OFFSET: Final[int] = _int_env("HTTP_PORT_OFFSET", 1000)

# --- Timeouts (seconds) ----------------------------------------------------
WORKER_STARTUP_TIMEOUT: Final[int] = _int_env("WORKER_STARTUP_TIMEOUT", 15)
WORKER_IDLE_TIMEOUT: Final[int] = _int_env("WORKER_IDLE_TIMEOUT", 1800)
WORKER_STOP_GRACE: Final[int] = _int_env("WORKER_STOP_GRACE", 10)
HEARTBEAT_INTERVAL: Final[int] = _int_env("HEARTBEAT_INTERVAL", 10)
HEARTBEAT_TTL: Final[int] = _int_env("HEARTBEAT_TTL", 30)
RECONCILE_INTERVAL: Final[int] = _int_env("RECONCILE_INTERVAL", 15)

# --- Session admission and OPC UA authentication ---------------------------
MAX_CONCURRENT_SESSIONS: Final[int] = 100
CREATE_REQUESTS_PER_MINUTE: Final[int] = 10
CREATE_RATE_WINDOW_SECONDS: Final[int] = 60
CREATE_RATE_LIMIT_PREFIX: Final[str] = "cip:ratelimit:create:"

OPCUA_AUTH_MODE: Final[str] = os.environ.get(
    "OPCUA_AUTH_MODE", "none"
).strip().lower()
if OPCUA_AUTH_MODE not in {"none", "per_session"}:
    raise RuntimeError(
        "OPCUA_AUTH_MODE must be 'none' or 'per_session'"
    )


# --- Loop rates (Hz) -------------------------------------------------------
PHYSICS_HZ: Final[int] = _int_env("PHYSICS_HZ", 10)
UI_BROADCAST_HZ: Final[int] = _int_env("UI_BROADCAST_HZ", 4)


# --- systemd integration ---------------------------------------------------
SYSTEMD_UNIT_PREFIX: Final[str] = "cip-worker-"
PID_DIR: Final[str] = "/var/lib/cip-sim/pids"


# --- Gateway ---------------------------------------------------------------
GATEWAY_OPCUA_PORT: Final[int] = _int_env("GATEWAY_OPCUA_PORT", 8080)
GATEWAY_EVT_CONSUMER_GROUP: Final[str] = "gateway"
GATEWAY_RECONNECT_ATTEMPTS: Final[int] = _int_env(
    "GATEWAY_RECONNECT_ATTEMPTS", 5
)
GATEWAY_RECONNECT_BASE_DELAY: Final[float] = _float_env(
    "GATEWAY_RECONNECT_BASE_DELAY", 0.3
)
GATEWAY_RECONNECT_MAX_DELAY: Final[float] = _float_env(
    "GATEWAY_RECONNECT_MAX_DELAY", 1.5
)
GATEWAY_SAMPLING_INTERVAL_MS: Final[int] = _int_env(
    "GATEWAY_SAMPLING_INTERVAL_MS", 500
)

if GATEWAY_RECONNECT_ATTEMPTS < 1:
    raise RuntimeError("GATEWAY_RECONNECT_ATTEMPTS must be at least 1")
if GATEWAY_SAMPLING_INTERVAL_MS < 1:
    raise RuntimeError("GATEWAY_SAMPLING_INTERVAL_MS must be at least 1")