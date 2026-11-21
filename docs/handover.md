# P4 Handover: Load Test and Plugin Guide

## Deliverables and current evidence

P4 adds a deterministic `loadtest` plugin, an async fake PLC client, an
opt-in load-test orchestrator, a raw-report formatter, and the
[Simulation Plugin Authoring Guide](plugin-guide.md).

## Session creation limits

The session API allows at most 50 sessions in `pending`, `starting`, `running`,
or `stopping` state. Stopped and failed sessions do not count. A Redis lock
serializes the capacity check and database insert across API processes, and
replacing a session with the same slug frees its slot before the check.

Each client IP may make five valid session-create requests per rolling minute.
The API uses the socket peer address (`REMOTE_ADDR`), not
`X-Forwarded-For`; behind a proxy, configure the trusted proxy/application
address handling before expecting separate limits per end user. Rate-limit
state and the capacity lock use Redis, so session creation fails with HTTP 503
if Redis is unavailable. Requests over the per-IP limit receive HTTP 429;
requests at total capacity receive HTTP 503.

**Scaling verdict: not measured in this checkout.** No live Gateway, daemon,
Redis, or control-plane stack was available for an end-to-end run. Do not treat
the test harness or plugin unit test as performance results. Run the load
series on the target Linux host and commit the resulting summary only after
reviewing the raw measurements.

The current checkout also has no committed `sessions_mgr` migration. Before a
live run, ensure the database schema has been installed by its migration
owner; P4 does not add or modify migration files.

The benchmark test targets 10, 25, 50, and 100 sessions by default. It records
Gateway, daemon, and total worker CPU and RSS using Linux `/proc`, plus OPC UA
connection latency, write-then-read round-trip latency, subscription
notifications/drops, and client errors. CPU is expressed as percent of one
logical CPU, so a multi-process role may exceed 100%.

## Run a benchmark series

1. Start the intended platform stack and verify that the control-plane API and
   Gateway are reachable. Run `python manage.py sync_catalog` so `loadtest`
   appears in the simulation catalog.
2. On the Linux stack host, identify the Gateway and worker-pool daemon PIDs.
   Export their PIDs and enable the opt-in test:

   ```sh
   export LOAD_TESTS_ENABLED=1
   export LOAD_GATEWAY_PID=<gateway-pid>
   export LOAD_DAEMON_PID=<worker-pool-daemon-pid>
   export LOAD_REPORT_PATH=load-results/load-{n}.json
   ```

3. Run the 10/25/50/100 series:

   ```sh
   pytest -q tests/load/test_n_sessions.py
   ```

   For a smaller smoke run, set `LOAD_SESSION_COUNTS=2`; adjust duration with
   `LOAD_DURATION=30` (seconds). Optionally set `LOAD_MAX_P95_MS` to impose a
   project-approved latency SLO. No latency limit is assumed by default.
4. Generate the summary:

   ```sh
   python -m tools.load_report load-results/load-*.json
   ```

   Add `--format ascii` for a terminal table. Use `--bottleneck "..."` only
   after correlating the measurements with host metrics and service logs. The
   default highest-CPU role is a candidate, not proof of the bottleneck.

The test creates uniquely named sessions and deletes those sessions in a
`finally` cleanup, including on Ctrl+C. It never signals or restarts the
shared stack. If the test process is forcibly killed, stop leftover `lt...`
sessions from the dashboard or with their capability URLs before rerunning.
Never run the 100-session case on a shared production host without an approved
maintenance window and a verified cleanup path.

Each JSON report contains the tested session count and stability result.
“Stable at tested load” means zero fake-PLC errors, zero detected subscription
drops, and no missing monitored process samples; if `LOAD_MAX_P95_MS` is set,
the p95 write/read latency must also meet it. This is a test criterion, not a
guarantee of production capacity. The highest stable tested count is only an
empirical lower bound for this host/configuration; it is not an extrapolation.

## Interpreting the measurements

- Compare p50 and p95 write/read latency as concurrency increases. A sharp
  p95 increase can indicate queueing even before requests fail.
- Subscription drops, client errors, worker startup failures, and missing
  process samples are failures to investigate, not values to average away.
- Compare Gateway CPU/RSS with the daemon and summed worker footprint. The
  formatter reports the highest-average-CPU role only as a bottleneck
  candidate; inspect logs, host-level CPU/memory, and the point where errors
  or latency rise before assigning root cause.
- Keep the machine, Python/dependency versions, `PHYSICS_HZ`, test duration,
  client interval, and stack configuration alongside any published results.
- Results do not transfer to a different host, plugin, runtime configuration,
  authentication mode, or network path without another run.

## Plugin documentation

The authoring walkthrough and working `blinker` example are in
[plugin-guide.md](plugin-guide.md). The `loadtest` plugin is intentionally
simple and should remain a benchmark fixture rather than a physical model.
