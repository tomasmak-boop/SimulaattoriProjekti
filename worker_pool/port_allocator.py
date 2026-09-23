"""Redis-backed port pool for OPC UA workers.

Port state lives in Redis, not process memory, so daemon restarts do not lose
leases. Acquisition uses HSETNX, which is atomic: two daemons racing for the
same port cannot both win. Release is a conditional HDEL so a late release
from a crashed worker cannot clobber a new lease on the same port.
"""

from __future__ import annotations

from typing import Iterator

import redis

from shared.constants import OPCUA_PORT_END, OPCUA_PORT_START, REDIS_PORT_LEASES
from shared.logging import get_logger

log = get_logger(__name__)


class PortPoolExhausted(RuntimeError):
    """Raised when every port in the configured range is leased."""


# Conditional release. Only deletes the field if it still points at our
# session_id. Atomic because Lua scripts run single-threaded in Redis.
_RELEASE_SCRIPT = """
if redis.call('HGET', KEYS[1], ARGV[1]) == ARGV[2] then
    redis.call('HDEL', KEYS[1], ARGV[1])
    return 1
end
return 0
"""


class PortAllocator:
    def __init__(
        self,
        client: redis.Redis,
        start: int | None = None,
        end: int | None = None,
    ) -> None:
        self._r = client
        self._start = start if start is not None else OPCUA_PORT_START
        self._end = end if end is not None else OPCUA_PORT_END
        if self._start >= self._end:
            raise ValueError(f"Invalid port range: {self._start}..{self._end}")

    def acquire(self, session_id: str) -> int:
        """Lease a free port to session_id. Raises PortPoolExhausted if none."""
        for port in self._ports():
            # HSETNX returns 1 if created, 0 if the field already existed.
            if self._r.hsetnx(REDIS_PORT_LEASES, str(port), session_id):
                log.info("port leased", extra={"port": port, "session_id": session_id})
                return port
        raise PortPoolExhausted(
            f"All ports in {self._start}..{self._end} are leased"
        )

    def release(self, port: int, session_id: str) -> bool:
        """Release a port only if still leased to session_id.

        Returns True if released, False if the lease had already been
        reclaimed (by reconciliation) or reassigned.
        """
        released = self._r.eval(
            _RELEASE_SCRIPT, 1, REDIS_PORT_LEASES, str(port), session_id
        )
        if released:
            log.info("port released", extra={"port": port, "session_id": session_id})
        else:
            log.warning(
                "port release ignored (not owned)",
                extra={"port": port, "session_id": session_id},
            )
        return bool(released)

    def reconcile(self, live_session_ids: set[str]) -> list[int]:
        """Drop leases whose owning session no longer exists.

        Called on daemon startup so a crash mid-spawn does not leak ports
        until the process that owns them is finally gone.
        """
        leases = self._r.hgetall(REDIS_PORT_LEASES)
        dropped: list[int] = []
        for port_b, sid_b in leases.items():
            sid = sid_b.decode() if isinstance(sid_b, bytes) else sid_b
            if sid not in live_session_ids:
                self._r.hdel(REDIS_PORT_LEASES, port_b)
                dropped.append(int(port_b))
        if dropped:
            log.warning("reconciled stale port leases", extra={"ports": dropped})
        return dropped

    def snapshot(self) -> dict[int, str]:
        """Current {port: session_id} map. For diagnostics and admin UI."""
        return {
            int(p): (s.decode() if isinstance(s, bytes) else s)
            for p, s in self._r.hgetall(REDIS_PORT_LEASES).items()
        }

    def _ports(self) -> Iterator[int]:
        # Linear scan from the bottom of the range. At 101 ports the extra
        # HGET per acquire is invisible; a cursor would only matter at 10k+.
        for port in range(self._start, self._end + 1):
            yield port