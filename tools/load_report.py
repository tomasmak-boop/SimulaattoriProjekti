"""Render benchmark JSON files as a Markdown or plain-text summary table."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _read_report(path: Path) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read benchmark report {path}: {exc}") from exc
    if not isinstance(report, dict) or "session_count" not in report:
        raise ValueError(f"{path} is not an orchestrator benchmark report")
    return report


def _format(value: Any, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value}{suffix}"


def _bottleneck_candidate(report: dict[str, Any]) -> str:
    aggregate = report.get("aggregate", {})
    if aggregate.get("errors", 0) or aggregate.get("dropped_subscriptions", 0):
        return "degradation observed; cause not isolated"
    roles = report.get("resources", {}).get("roles", {})
    observed = [
        (role, data.get("avg_cpu_percent"))
        for role, data in roles.items()
        if data.get("avg_cpu_percent") is not None
    ]
    if not observed:
        return "not measured"
    role, cpu = max(observed, key=lambda item: item[1])
    return f"{role} (highest average CPU: {cpu}%)"


def _rows(reports: list[dict[str, Any]], bottleneck: str | None):
    rows = []
    for report in sorted(reports, key=lambda item: item["session_count"]):
        aggregate = report.get("aggregate", {})
        resources = report.get("resources", {}).get("roles", {})
        gateway = resources.get("gateway", {})
        workers = resources.get("workers", {})
        connection = aggregate.get("connection_latency_ms", {})
        latency = aggregate.get("write_read_round_trip_latency_ms", {})
        errors = aggregate.get("errors", 0)
        attempts = aggregate.get("attempts", 0)
        error_rate = aggregate.get(
            "error_rate_percent",
            round(100 * errors / attempts, 3) if attempts else 0.0,
        )
        row_bottleneck = (
            bottleneck
            or report.get("scaling_verdict", {}).get("bottleneck")
            or _bottleneck_candidate(report)
        )
        rows.append([
            str(report["session_count"]),
            _format(workers.get("peak_rss_mb"), " MB"),
            _format(gateway.get("avg_cpu_percent"), "%"),
            _format(gateway.get("peak_rss_mb"), " MB"),
            _format(connection.get("p50"), " ms"),
            _format(connection.get("p95"), " ms"),
            _format(latency.get("p50"), " ms"),
            _format(latency.get("p95"), " ms"),
            f"{error_rate}%",
            str(aggregate.get("dropped_subscriptions", "n/a")),
            row_bottleneck,
        ])
    return rows


def _markdown(rows: list[list[str]]) -> str:
    headers = [
        "Sessions",
        "Workers peak RSS",
        "Gateway avg CPU",
        "Gateway peak RSS",
        "Connect p50",
        "Connect p95",
        "Write/read p50",
        "Write/read p95",
        "Error rate",
        "Dropped subscriptions",
        "Primary bottleneck / candidate",
    ]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _ascii(rows: list[list[str]]) -> str:
    headers = [
        "Sessions", "Workers peak RSS", "Gateway avg CPU", "Gateway peak RSS",
        "Connect p50", "Connect p95", "Write/read p50", "Write/read p95", "Error rate",
        "Dropped subscriptions", "Primary bottleneck / candidate",
    ]
    widths = [
        max(len(header), *(len(row[index]) for row in rows))
        for index, header in enumerate(headers)
    ]
    border = "+-" + "-+-".join("-" * width for width in widths) + "-+"
    lines = [border]
    lines.append(
        "| " + " | ".join(
            header.ljust(widths[index]) for index, header in enumerate(headers)
        ) + " |"
    )
    lines.append(border)
    for row in rows:
        lines.append(
            "| " + " | ".join(
                cell.ljust(widths[index]) for index, cell in enumerate(row)
            ) + " |"
        )
    lines.append(border)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--format", choices=("markdown", "ascii"), default="markdown")
    parser.add_argument(
        "--bottleneck",
        help="Optional measured bottleneck conclusion to use for every row.",
    )
    args = parser.parse_args(argv)
    try:
        reports = [_read_report(path) for path in args.reports]
    except ValueError as exc:
        parser.error(str(exc))
    rows = _rows(reports, args.bottleneck)
    print(_markdown(rows) if args.format == "markdown" else _ascii(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
