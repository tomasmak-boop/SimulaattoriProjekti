"""Unit tests for the port allocator.

Uses fakeredis so no external service is required. The two tests that matter
most are the concurrent-acquire race and the stale-release protection —
those are the bugs the design exists to prevent.
"""

from __future__ import annotations

import threading

import fakeredis
import pytest

from worker_pool.port_allocator import PortAllocator, PortPoolExhausted


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=False)


@pytest.fixture
def pool(redis_client):
    return PortAllocator(redis_client, start=5000, end=5002)


def test_acquire_returns_port_in_range(pool):
    port = pool.acquire("session-a")
    assert 5000 <= port <= 5002


def test_acquire_second_call_gives_different_port(pool):
    p1 = pool.acquire("session-a")
    p2 = pool.acquire("session-b")
    assert p1 != p2


def test_pool_exhaustion_raises(pool):
    pool.acquire("a")
    pool.acquire("b")
    pool.acquire("c")
    with pytest.raises(PortPoolExhausted):
        pool.acquire("d")


def test_release_frees_the_port(pool):
    p1 = pool.acquire("session-a")
    assert pool.release(p1, "session-a")
    p2 = pool.acquire("session-b")
    assert p2 == p1  # freed port is reused


def test_release_by_wrong_session_is_rejected(pool):
    p1 = pool.acquire("session-a")
    assert pool.release(p1, "session-b") is False
    # Original lease is untouched
    assert pool.snapshot()[p1] == "session-a"


def test_release_twice_is_idempotent(pool):
    p1 = pool.acquire("session-a")
    assert pool.release(p1, "session-a") is True
    assert pool.release(p1, "session-a") is False


def test_concurrent_acquire_never_double_leases(pool):
    """Race N threads for M ports; each port is leased at most once."""
    results: list[int] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def worker(sid: str):
        try:
            port = pool.acquire(sid)
            with lock:
                results.append(port)
        except Exception as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(f"s{i}",)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 3
    assert len(set(results)) == 3        # no duplicates
    assert not errors


def test_reconcile_drops_orphans(pool):
    p1 = pool.acquire("session-a")
    p2 = pool.acquire("session-b")
    # session-b is gone; only session-a is live
    dropped = pool.reconcile(live_session_ids={"session-a"})
    assert dropped == [p2]
    assert pool.snapshot() == {p1: "session-a"}


def test_reconcile_keeps_live_leases(pool):
    p1 = pool.acquire("session-a")
    dropped = pool.reconcile(live_session_ids={"session-a"})
    assert dropped == []
    assert pool.snapshot() == {p1: "session-a"}