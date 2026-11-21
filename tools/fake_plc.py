"""Run concurrent OPC UA clients against the aggregated gateway."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from asyncua import Client, ua


GATEWAY_NAMESPACE = "urn:cip-sim:gateway:1.0.0"


def _percentile(samples: list[float], percentile: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    value = ordered[lower] + (ordered[upper] - ordered[lower]) * (
        position - lower
    )
    return round(value, 3)


@dataclass
class ClientMetrics:
    session: str
    connection_latency_ms: float | None = None
    ready_wait_s: float = 0.0
    startup_retries: int = 0
    active: bool | None = None
    notifications: int = 0
    dropped_subscriptions: int = 0
    attempts: int = 0
    successes: int = 0
    errors: int = 0
    error_messages: list[str] = field(default_factory=list)
    round_trip_latencies_ms: list[float] = field(default_factory=list)
    last_notification_at: float | None = None
    subscription_stalled: bool = False

    def add_error(self, message: str) -> None:
        self.errors += 1
        if len(self.error_messages) < 10:
            self.error_messages.append(message)

    def as_dict(self) -> dict[str, Any]:
        return {
            "session": self.session,
            "connection_latency_ms": self.connection_latency_ms,
            "ready_wait_s": round(self.ready_wait_s, 3),
            "startup_retries": self.startup_retries,
            "active": self.active,
            "notifications": self.notifications,
            "dropped_subscriptions": self.dropped_subscriptions,
            "attempts": self.attempts,
            "successes": self.successes,
            "errors": self.errors,
            "error_messages": self.error_messages,
            "round_trip_latency_ms": {
                "p50": _percentile(self.round_trip_latencies_ms, 0.50),
                "p95": _percentile(self.round_trip_latencies_ms, 0.95),
                "samples": len(self.round_trip_latencies_ms),
            },
        }


class _SubscriptionHandler:
    def __init__(self, metrics: ClientMetrics) -> None:
        self._metrics = metrics

    def datachange_notification(self, node, value, data) -> None:
        self._metrics.notifications += 1
        self._metrics.last_notification_at = time.monotonic()
        self._metrics.subscription_stalled = False

    def status_change_notification(self, status) -> None:
        if not self._metrics.subscription_stalled:
            self._metrics.dropped_subscriptions += 1
            self._metrics.subscription_stalled = True


async def _connect_ready_client(
    endpoint: str,
    session: str,
    metrics: ClientMetrics,
    connect_timeout: float,
    stop: asyncio.Event,
) -> tuple[Client, Any, Any, Any]:
    deadline = asyncio.get_running_loop().time() + connect_timeout
    started = time.monotonic()
    last_error = "gateway session did not appear"

    while (
        asyncio.get_running_loop().time() < deadline
        and not stop.is_set()
    ):
        client = Client(url=endpoint)
        connected = False
        try:
            connect_started = time.monotonic()
            await client.connect()
            connected = True
            metrics.connection_latency_ms = (
                time.monotonic() - connect_started
            ) * 1000

            namespace = await client.get_namespace_index(GATEWAY_NAMESPACE)
            session_folder = await client.nodes.objects.get_child([
                f"{namespace}:Gateway",
                f"{namespace}:Sessions",
                f"{namespace}:{session}",
            ])
            measurements = await session_folder.get_child(
                [f"{namespace}:Measurements"]
            )
            status = await session_folder.get_child([f"{namespace}:Status"])
            commands = await session_folder.get_child([f"{namespace}:Commands"])
            tick_count = await measurements.get_child(
                [f"{namespace}:TickCount"]
            )
            is_active = await status.get_child([f"{namespace}:IsActive"])
            reset_count = await commands.get_child(
                [f"{namespace}:ResetCount"]
            )
            metrics.active = bool(await is_active.read_value())

            subscription = await client.create_subscription(
                500, _SubscriptionHandler(metrics)
            )
            await subscription.subscribe_data_change(tick_count)
            metrics.ready_wait_s = time.monotonic() - started
            metrics.last_notification_at = time.monotonic()
            return client, subscription, tick_count, reset_count
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            metrics.startup_retries += 1
            if connected:
                try:
                    await client.disconnect()
                except Exception as disconnect_error:
                    metrics.add_error(
                        "startup disconnect: "
                        f"{type(disconnect_error).__name__}: {disconnect_error}"
                    )
            if asyncio.get_running_loop().time() >= deadline:
                break
            await asyncio.sleep(0.5)

    metrics.ready_wait_s = time.monotonic() - started
    if stop.is_set():
        last_error = "benchmark stopped before the session became browseable"
    metrics.add_error(f"could not subscribe to {session}: {last_error}")
    raise TimeoutError(
        f"session {session!r} was not browseable before the connect timeout"
    )


async def _run_client(
    endpoint: str,
    session: str,
    *,
    duration: float,
    command_interval: float,
    connect_timeout: float,
    subscription_stall_timeout: float,
    stop: asyncio.Event,
    ready_queue: asyncio.Queue[str],
    start_gate: asyncio.Event,
) -> ClientMetrics:
    metrics = ClientMetrics(session=session)
    client = None
    subscription = None

    try:
        client, subscription, tick_count, reset_count = (
            await _connect_ready_client(
                endpoint, session, metrics, connect_timeout, stop
            )
        )

        await ready_queue.put(session)
        await start_gate.wait()
        if stop.is_set():
            return metrics

        deadline = asyncio.get_running_loop().time() + duration
        while not stop.is_set():
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=min(command_interval, remaining)
                )
                break
            except asyncio.TimeoutError:
                pass

            now = time.monotonic()
            if (
                metrics.last_notification_at is not None
                and now - metrics.last_notification_at
                > subscription_stall_timeout
                and not metrics.subscription_stalled
            ):
                metrics.dropped_subscriptions += 1
                metrics.subscription_stalled = True

            metrics.attempts += 1
            started = time.perf_counter()
            try:
                await reset_count.write_value(
                    ua.Variant(True, ua.VariantType.Boolean)
                )
                await tick_count.read_value()
                metrics.round_trip_latencies_ms.append(
                    (time.perf_counter() - started) * 1000
                )
                metrics.successes += 1
            except Exception as exc:
                metrics.add_error(f"{type(exc).__name__}: {exc}")

        return metrics
    except Exception as exc:
        if not metrics.errors:
            metrics.add_error(f"{type(exc).__name__}: {exc}")
        return metrics
    finally:
        if subscription is not None:
            try:
                await subscription.delete()
            except Exception as exc:
                metrics.add_error(
                    f"subscription cleanup: {type(exc).__name__}: {exc}"
                )
        if client is not None:
            try:
                await client.disconnect()
            except Exception as exc:
                metrics.add_error(
                    f"client cleanup: {type(exc).__name__}: {exc}"
                )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulate PLC clients against a Gateway OPC UA endpoint."
    )
    parser.add_argument(
        "--endpoint",
        default="opc.tcp://127.0.0.1:8080/gateway/",
        help="Gateway endpoint URL.",
    )
    parser.add_argument(
        "--session",
        action="append",
        required=True,
        help="Gateway session slug; repeat once for each simulated PLC.",
    )
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--command-interval", type=float, default=1.0)
    parser.add_argument("--connect-timeout", type=float, default=90.0)
    parser.add_argument("--subscription-stall-timeout", type=float, default=5.0)
    parser.add_argument(
        "--output",
        type=Path,
        help="Write raw JSON to this file instead of stdout.",
    )
    return parser


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    if args.duration <= 0 or args.command_interval <= 0:
        raise ValueError("duration and command interval must be positive")
    if args.connect_timeout <= 0 or args.subscription_stall_timeout <= 0:
        raise ValueError("timeouts must be positive")
    if len(set(args.session)) != len(args.session):
        raise ValueError("session slugs must be unique")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    started_at = datetime.now(timezone.utc)
    startup_started = time.monotonic()
    ready_queue: asyncio.Queue[str] = asyncio.Queue()
    start_gate = asyncio.Event()
    tasks = [
        asyncio.create_task(
            _run_client(
                args.endpoint,
                session,
                duration=args.duration,
                command_interval=args.command_interval,
                connect_timeout=args.connect_timeout,
                subscription_stall_timeout=args.subscription_stall_timeout,
                stop=stop,
                ready_queue=ready_queue,
                start_gate=start_gate,
            ),
            name=f"fake-plc-{session}",
        )
        for session in args.session
    ]
    try:
        ready_sessions: set[str] = set()
        while len(ready_sessions) < len(tasks) and not stop.is_set():
            if any(task.done() for task in tasks):
                break
            try:
                session = await asyncio.wait_for(
                    ready_queue.get(), timeout=0.1
                )
                ready_sessions.add(session)
            except asyncio.TimeoutError:
                pass

        startup_duration_s = time.monotonic() - startup_started
        load_started = time.monotonic()
        if len(ready_sessions) == len(tasks):
            start_gate.set()
            try:
                await asyncio.wait_for(stop.wait(), timeout=args.duration)
            except asyncio.TimeoutError:
                pass
        else:
            stop.set()
        start_gate.set()
        stop.set()
        client_metrics = await asyncio.gather(*tasks)
    finally:
        stop.set()
        start_gate.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    duration_s = time.monotonic() - load_started
    round_trips = [
        latency
        for metrics in client_metrics
        for latency in metrics.round_trip_latencies_ms
    ]
    connections = [
        metrics.connection_latency_ms
        for metrics in client_metrics
        if metrics.connection_latency_ms is not None
    ]
    attempts = sum(metrics.attempts for metrics in client_metrics)
    errors = sum(metrics.errors for metrics in client_metrics)
    report = {
        "tool": "fake_plc",
        "started_at": started_at.isoformat(),
        "startup_duration_s": round(startup_duration_s, 3),
        "duration_s": round(duration_s, 3),
        "client_count": len(args.session),
        "clients": [metrics.as_dict() for metrics in client_metrics],
        "aggregate": {
            "connection_latency_ms": {
                "p50": _percentile(connections, 0.50),
                "p95": _percentile(connections, 0.95),
                "samples": len(connections),
            },
            "write_read_round_trip_latency_ms": {
                "p50": _percentile(round_trips, 0.50),
                "p95": _percentile(round_trips, 0.95),
                "samples": len(round_trips),
            },
            "attempts": attempts,
            "successes": sum(
                metrics.successes for metrics in client_metrics
            ),
            "errors": errors,
            "error_rate_percent": round(
                100 * errors / attempts, 3
            ) if attempts else (100.0 if errors else 0.0),
            "dropped_subscriptions": sum(
                metrics.dropped_subscriptions for metrics in client_metrics
            ),
            "subscription_notifications": sum(
                metrics.notifications for metrics in client_metrics
            ),
        },
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        report = asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130
    except ValueError as exc:
        parser.error(str(exc))

    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
