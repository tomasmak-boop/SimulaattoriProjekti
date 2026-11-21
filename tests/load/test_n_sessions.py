"""Opt-in end-to-end load test for N concurrent Gateway sessions.

Run on the Linux host running the stack. The test owns and stops only the
sessions it creates; it does not restart or signal the shared platform.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.error
from urllib.parse import urlsplit, urlunsplit
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from sim_plugins.loadtest.simulation import LoadTestSimulation
from sim_runtime.base import SimulationConfig
from tools.fake_plc import _percentile
from tools.load_report import main as render_load_report


def test_loadtest_plugin_contract() -> None:
    simulation = LoadTestSimulation(SimulationConfig(session_id="test"))
    assert set(LoadTestSimulation.commands()) == {"ResetCount"}
    assert set(LoadTestSimulation.measurements()) == {"TickCount"}
    assert set(LoadTestSimulation.status()) == {"IsActive"}
    assert simulation.snapshot() == {
        "measurements": {"TickCount": 0},
        "status": {"IsActive": True},
    }

    simulation.step(0.1)
    assert simulation.snapshot()["measurements"]["TickCount"] == 1
    simulation.write_command("ResetCount", True)
    assert simulation.snapshot()["measurements"]["TickCount"] == 0
    with pytest.raises(ValueError):
        simulation.write_command("Unknown", True)


def test_percentile_interpolates_samples() -> None:
    assert _percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 3.85


def _safe_api_url(url: str) -> str:
    parts = urlsplit(url)
    segments = parts.path.rstrip("/").split("/")
    if len(segments) >= 3 and segments[-2] == "sessions":
        segments[-1] = "<token>"
    return urlunsplit((parts.scheme, parts.netloc, "/".join(segments), "", ""))


def _redact_tokens(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "<redacted>" if key == "token" else _redact_tokens(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_tokens(item) for item in value]
    return value


def test_load_report_renders_latency_and_resource_metrics(
    tmp_path: Path, capsys
) -> None:
    report = {
        "session_count": 10,
        "aggregate": {
            "connection_latency_ms": {"p50": 3.0, "p95": 5.0},
            "write_read_round_trip_latency_ms": {"p50": 8.0, "p95": 12.0},
            "attempts": 10,
            "errors": 0,
            "error_rate_percent": 0.0,
            "dropped_subscriptions": 0,
        },
        "resources": {
            "roles": {
                "gateway": {
                    "avg_cpu_percent": 12.0,
                    "peak_rss_mb": 80.0,
                },
                "workers": {"peak_rss_mb": 240.0},
            },
        },
    }
    report_path = tmp_path / "load.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    assert render_load_report([str(report_path)]) == 0
    rendered = capsys.readouterr().out
    assert "Sessions" in rendered
    assert "Workers peak RSS" in rendered
    assert "Connect p95" in rendered
    assert "Write/read p95" in rendered
    assert "12.0%" in rendered
    assert "240.0 MB" in rendered


def _session_counts() -> list[int]:
    raw = os.environ.get("LOAD_SESSION_COUNTS", "10,25,50,100")
    try:
        counts = [int(item.strip()) for item in raw.split(",") if item.strip()]
    except ValueError as exc:
        raise ValueError("LOAD_SESSION_COUNTS must be comma-separated integers") from exc
    if not counts or any(count <= 0 or count > 100 for count in counts):
        raise ValueError("LOAD_SESSION_COUNTS values must be between 1 and 100")
    return counts


def _api_json(method: str, url: str, payload: dict[str, Any] | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url, data=data, headers=headers, method=method
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw_detail = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.dumps(_redact_tokens(json.loads(raw_detail)))
        except json.JSONDecodeError:
            detail = raw_detail
        raise RuntimeError(
            f"{method} {_safe_api_url(url)} returned HTTP {exc.code}: {detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"{method} {_safe_api_url(url)} failed: {exc.reason}"
        ) from exc


async def _request(
    method: str, url: str, payload: dict[str, Any] | None = None
):
    return await asyncio.to_thread(_api_json, method, url, payload)


def _proc_stats(pid: int) -> tuple[float, int]:
    """Return one-core CPU ticks and resident bytes for a Linux process."""
    stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    fields = stat[stat.rfind(")") + 2 :].split()
    cpu_ticks = float(int(fields[11]) + int(fields[12]))
    resident_pages = int(
        Path(f"/proc/{pid}/statm").read_text(encoding="ascii").split()[1]
    )
    return cpu_ticks, resident_pages * os.sysconf("SC_PAGE_SIZE")


class ProcessSampler:
    def __init__(self, roles: dict[str, list[int]], interval: float = 1.0):
        if not Path("/proc").is_dir():
            raise RuntimeError(
                "process sampling requires Linux /proc; run the load test "
                "on the stack host"
            )
        self._roles = roles
        self._interval = interval
        self._previous: dict[int, tuple[float, float]] = {}
        self.samples: list[dict[str, Any]] = []
        self._stop = asyncio.Event()

    def _sample(self) -> None:
        now = time.monotonic()
        cpu_totals: dict[str, float] = {}
        cpu_observations: dict[str, int] = {}
        rss_totals: dict[str, int] = {}
        process_counts: dict[str, int] = {}
        missing: dict[str, int] = {}

        for role, pids in self._roles.items():
            cpu_totals[role] = 0.0
            cpu_observations[role] = 0
            rss_totals[role] = 0
            process_counts[role] = 0
            missing[role] = 0
            for pid in pids:
                try:
                    cpu_ticks, rss_bytes = _proc_stats(pid)
                except FileNotFoundError:
                    missing[role] += 1
                    continue
                prior = self._previous.get(pid)
                if prior is not None:
                    prior_ticks, prior_time = prior
                    elapsed = now - prior_time
                    if elapsed > 0:
                        cpu_totals[role] += max(
                            0.0,
                            (cpu_ticks - prior_ticks)
                            / os.sysconf("SC_CLK_TCK")
                            / elapsed
                            * 100,
                        )
                        cpu_observations[role] += 1
                self._previous[pid] = (cpu_ticks, now)
                rss_totals[role] += rss_bytes
                process_counts[role] += 1

        self.samples.append({
            "elapsed_s": round(now - self.samples_start, 3),
            "roles": {
                role: {
                    "cpu_percent": (
                        round(cpu_totals[role], 3)
                        if cpu_observations[role]
                        else None
                    ),
                    "rss_mb": round(rss_totals[role] / 1024 / 1024, 3),
                    "process_count": process_counts[role],
                    "missing_processes": missing[role],
                }
                for role in self._roles
            },
        })

    async def run(self) -> None:
        self.samples_start = time.monotonic()
        while not self._stop.is_set():
            self._sample()
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self._interval
                )
            except asyncio.TimeoutError:
                pass
        self._sample()

    def stop(self) -> None:
        self._stop.set()

    def summary(self) -> dict[str, Any]:
        roles: dict[str, Any] = {}
        for role in self._roles:
            samples = [
                sample["roles"][role]
                for sample in self.samples
                if sample["roles"][role]["process_count"] > 0
            ]
            cpu = [
                sample["cpu_percent"]
                for sample in samples
                if sample["cpu_percent"] is not None
            ]
            rss = [sample["rss_mb"] for sample in samples]
            roles[role] = {
                "processes": len(self._roles[role]),
                "samples": len(samples),
                "avg_cpu_percent": round(sum(cpu) / len(cpu), 3) if cpu else None,
                "peak_cpu_percent": round(max(cpu), 3) if cpu else None,
                "avg_rss_mb": round(sum(rss) / len(rss), 3) if rss else None,
                "peak_rss_mb": round(max(rss), 3) if rss else None,
                "missing_process_observations": sum(
                    sample["roles"][role]["missing_processes"]
                    for sample in self.samples
                ),
            }
        return {"interval_s": self._interval, "roles": roles, "samples": self.samples}


def _write_report(report: dict[str, Any], session_count: int) -> None:
    report["session_count"] = session_count
    max_p95 = os.environ.get("LOAD_MAX_P95_MS")
    p95 = report["aggregate"]["write_read_round_trip_latency_ms"]["p95"]
    missing_process_observations = sum(
        role["missing_process_observations"]
        for role in report["resources"]["roles"].values()
    )
    if max_p95:
        report["max_p95_ms"] = float(max_p95)
    stable = (
        report["aggregate"]["errors"] == 0
        and report["aggregate"]["dropped_subscriptions"] == 0
        and missing_process_observations == 0
        and (not max_p95 or (p95 is not None and p95 <= float(max_p95)))
    )
    report["scaling_verdict"] = {
        "stable_at_tested_load": stable,
        "criteria": (
            "zero client errors, dropped subscriptions, and missing process "
            "observations"
            + (f", p95 <= {max_p95} ms" if max_p95 else "")
        ),
    }

    output = os.environ.get("LOAD_REPORT_PATH")
    if output:
        path = Path(output.format(n=session_count))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


async def _wait_until_running(
    api_base: str, sessions: list[dict[str, Any]], timeout: float
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    latest = sessions
    while time.monotonic() < deadline:
        latest = await asyncio.gather(*[
            _request("GET", f"{api_base}/sessions/{session['token']}/")
            for session in sessions
        ])
        failed = [
            session for session in latest if session["status"] == "failed"
        ]
        if failed:
            raise RuntimeError(
                f"{len(failed)} load-test session(s) failed during startup"
            )
        if all(session["status"] == "running" for session in latest):
            return latest
        await asyncio.sleep(1.0)
    statuses = [session["status"] for session in latest]
    raise TimeoutError(
        f"sessions did not become ready in {timeout}s; statuses={statuses}"
    )


async def _stop_sessions(api_base: str, sessions: list[dict[str, Any]]) -> None:
    if not sessions:
        return
    results = await asyncio.gather(*[
        _request("DELETE", f"{api_base}/sessions/{session['token']}/")
        for session in sessions
    ], return_exceptions=True)
    errors = [result for result in results if isinstance(result, Exception)]
    if errors:
        raise RuntimeError(
            f"failed to request stop for {len(errors)} benchmark session(s): "
            + "; ".join(str(error) for error in errors[:3])
        )

    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        latest = await asyncio.gather(*[
            _request("GET", f"{api_base}/sessions/{session['token']}/")
            for session in sessions
        ])
        if all(
            session["status"] in ("stopped", "failed") for session in latest
        ):
            return
        await asyncio.sleep(1.0)
    statuses = [session["status"] for session in latest]
    raise TimeoutError(f"sessions did not stop within 90s: {statuses}")


async def _run_load_test(session_count: int) -> dict[str, Any]:
    if not Path("/proc").is_dir():
        pytest.skip("load test requires Linux /proc process metrics")

    api_base = os.environ.get(
        "LOAD_API_URL", "http://127.0.0.1:8000/api"
    ).rstrip("/")
    endpoint = os.environ.get(
        "LOAD_GATEWAY_ENDPOINT", "opc.tcp://127.0.0.1:8080/gateway/"
    )
    gateway_pid = int(os.environ["LOAD_GATEWAY_PID"])
    daemon_pid = int(os.environ["LOAD_DAEMON_PID"])
    if gateway_pid <= 0 or daemon_pid <= 0:
        raise ValueError("LOAD_GATEWAY_PID and LOAD_DAEMON_PID must be positive")

    unique = uuid.uuid4().hex[:8]
    created: list[dict[str, Any]] = []
    fake_plc = None
    sampler_task = None
    sampler = None
    primary_error = None
    try:
        for index in range(session_count):
            slug = f"lt{unique}_{index:03d}"
            create_task = asyncio.create_task(
                _request(
                    "POST",
                    f"{api_base}/sessions/",
                    {
                        "simulation_id": "loadtest",
                        "slug": slug,
                        "label": f"Load test {slug}",
                    },
                )
            )
            try:
                session = await asyncio.shield(create_task)
            except asyncio.CancelledError:
                session = await create_task
                created.append(session)
                raise
            created.append(session)

        ready = await _wait_until_running(
            api_base,
            created,
            float(os.environ.get("LOAD_STARTUP_TIMEOUT", "240")),
        )
        worker_pids = [int(session["pid"]) for session in ready if session["pid"]]
        if len(worker_pids) != session_count:
            raise RuntimeError(
                f"expected {session_count} worker PIDs, got {len(worker_pids)}"
            )

        sampler = ProcessSampler({
            "gateway": [gateway_pid],
            "daemon": [daemon_pid],
            "workers": worker_pids,
        })
        sampler_task = asyncio.create_task(sampler.run(), name="process-sampler")
        fake_plc_script = (
            Path(__file__).resolve().parents[2] / "tools" / "fake_plc.py"
        )
        command = [
            sys.executable,
            str(fake_plc_script),
            "--endpoint",
            endpoint,
            "--duration",
            os.environ.get("LOAD_DURATION", "30"),
            "--command-interval",
            os.environ.get("LOAD_COMMAND_INTERVAL", "1"),
            "--connect-timeout",
            os.environ.get("LOAD_CONNECT_TIMEOUT", "90"),
        ]
        for session in ready:
            command.extend(["--session", session["slug"]])
        fake_plc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await fake_plc.communicate()
        if fake_plc.returncode != 0:
            raise RuntimeError(
                f"fake PLC exited {fake_plc.returncode}: "
                f"{stderr.decode('utf-8', errors='replace')}"
            )
        report = json.loads(stdout.decode("utf-8"))
        sampler.stop()
        await sampler_task
        sampler_task = None
        report["resources"] = sampler.summary()
        report["sessions_created"] = session_count
        _write_report(report, session_count)

        aggregate = report["aggregate"]
        assert aggregate["errors"] == 0, (
            f"{aggregate['errors']} fake PLC errors; benchmark report saved"
        )
        assert aggregate["dropped_subscriptions"] == 0, (
            f"{aggregate['dropped_subscriptions']} dropped subscriptions; "
            "benchmark report saved"
        )
        assert all(
            role["missing_process_observations"] == 0
            for role in report["resources"]["roles"].values()
        ), "one or more monitored processes disappeared; benchmark report saved"
        assert report["resources"]["roles"]["gateway"]["samples"] >= 2
        return report
    except BaseException as exc:
        primary_error = exc
        raise
    finally:
        if sampler is not None:
            sampler.stop()
        if sampler_task is not None:
            await sampler_task
        if fake_plc is not None and fake_plc.returncode is None:
            fake_plc.terminate()
            try:
                await asyncio.wait_for(fake_plc.wait(), timeout=5)
            except asyncio.TimeoutError:
                fake_plc.kill()
                await fake_plc.wait()
        try:
            await _stop_sessions(api_base, created)
        except Exception as cleanup_error:
            if primary_error is None:
                raise
            print(
                f"load-test cleanup failed: {cleanup_error}",
                file=sys.stderr,
            )


_INTEGRATION_ENABLED = (
    os.environ.get("LOAD_TESTS_ENABLED") == "1"
    and bool(os.environ.get("LOAD_GATEWAY_PID"))
    and bool(os.environ.get("LOAD_DAEMON_PID"))
)


@pytest.mark.parametrize("session_count", _session_counts())
@pytest.mark.asyncio
@pytest.mark.skipif(
    not _INTEGRATION_ENABLED,
    reason=(
        "set LOAD_TESTS_ENABLED=1, LOAD_GATEWAY_PID, and LOAD_DAEMON_PID "
        "to run against a live Linux stack"
    ),
)
async def test_n_sessions(session_count: int) -> None:
    await _run_load_test(session_count)
