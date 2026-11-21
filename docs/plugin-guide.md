# Simulation Plugin Authoring Guide

This guide describes the plugin contract used by the worker runtime. A plugin
is a Python package under `sim_plugins/`; its `simulation.py` defines a
`BaseSimulation` subclass. The runtime discovers plugins by scanning that
directory, so a separate registry edit is not needed.

## 1. Create a plugin

Create a package such as:

```text
sim_plugins/
  temperature_demo/
    __init__.py
    simulation.py
    body.html       # optional browser UI
    ui.js           # optional browser UI
```

`SIMULATION_ID` must be unique, lowercase, and contain no spaces. Keep
`SIMULATION_VERSION` in semantic-version form and increment it when the
plugin's public schema or behavior changes.

## 2. Declare the OPC UA schema and implement the simulation

The worker calls `commands()`, `measurements()`, and `status()` to build the
OPC UA tree before constructing a runtime session. Names in the returned
dictionaries become OPC UA browse names. Each `CommandSpec`, measurement
specification, and status specification should use the same name as its
dictionary key.

```python
from __future__ import annotations

from typing import Any

from sim_runtime.base import (
    BaseSimulation,
    CommandSpec,
    MeasurementSpec,
    SimulationConfig,
    StatusSpec,
)


class TemperatureDemo(BaseSimulation):
    SIMULATION_ID = "temperature_demo"
    SIMULATION_NAME = "Temperature Demo"
    SIMULATION_VERSION = "1.0.0"

    def __init__(self, config: SimulationConfig) -> None:
        self._temperature = float(config.params.get("initial_temperature", 20.0))
        self._running = False

    @classmethod
    def commands(cls) -> dict[str, CommandSpec]:
        return {
            "Running": CommandSpec(
                name="Running",
                type="bool",
                description="Enable or pause temperature changes.",
                default=False,
            ),
        }

    @classmethod
    def measurements(cls) -> dict[str, MeasurementSpec]:
        return {
            "Temperature": MeasurementSpec(
                name="Temperature",
                type="float",
                unit="degC",
                description="Current simulated temperature.",
            ),
        }

    @classmethod
    def status(cls) -> dict[str, StatusSpec]:
        return {
            "State": StatusSpec(
                name="State",
                type="string",
                description="Current simulation state.",
            ),
        }

    def step(self, dt: float) -> None:
        if self._running:
            self._temperature += 0.1 * dt

    def snapshot(self) -> dict[str, Any]:
        return {
            "measurements": {"Temperature": round(self._temperature, 2)},
            "status": {"State": "Running" if self._running else "Paused"},
        }

    def write_command(self, name: str, value: Any) -> None:
        if name == "Running":
            if not isinstance(value, bool):
                raise ValueError("Running must be a bool")
            self._running = value
            return
        raise ValueError(f"Unknown command: {name}")
```

### Contract and runtime expectations

- Implement `__init__(config)`, `step(dt)`, `snapshot()`, and
  `write_command(name, value)`. `SimulationConfig` has a per-session
  `session_id` and a plugin-specific `params` dictionary.
- `step(dt)` is synchronous and runs on the worker's physics loop (10 Hz by
  default). Keep it short and non-blocking; do not make network or disk calls
  there. `dt` is elapsed simulation time in seconds.
- `snapshot()` must return exactly the two top-level dictionaries
  `measurements` and `status`, with keys matching the declared schema. Values
  must be JSON serializable and fit their OPC UA types.
- `write_command()` should validate input and raise `ValueError` for an
  unsupported command or invalid value. The adapter reports invalid writes as
  OPC UA errors.
- Supported schema type strings are `bool`, `int`, `float`, and `string`.
  Numeric command specs may set `min` and `max`; commands with `pulse=True`
  are cleared by the runtime on the next physics tick. Use a pulse for
  momentary actions such as reset.
- Status values are read-only to OPC UA clients. Use `StatusSpec` for state
  codes, text, and other non-command status.
- `step()` and OPC UA operations run on the worker event loop, while the
  optional HTTP dashboard may call `snapshot()` on another thread. Protect
  state shared across these threads with a lock if the plugin needs more than
  simple atomic value reads/writes.
- `on_client_activity()` is an optional hook for simulations that need to
  react to external OPC UA reads or writes. The default does nothing.

## 3. Use the blinker as a reference

[`sim_plugins/blinker/simulation.py`](../sim_plugins/blinker/simulation.py)
shows the full contract in a small working plugin: a Boolean enable command,
a bounded period command, a pulse reset command, measurements, and status.
Review its matching `body.html` and `ui.js` for the optional web panel pattern.

## 4. Add an optional browser UI

`body.html` is inserted into the shared simulation page. `ui.js` is loaded
after it and may define `window.renderState(state)`. The runtime fetches
`api/state` and calls that function with the response's `state` object.
Both files are optional; without them the worker still serves the shell and
OPC UA interface.

Keep the UI self-contained, do not hard-code a worker port, and render state
from the supplied snapshot. The same page may be reached directly or through
the control-plane dashboard proxy.

## 5. Discover and run the plugin

From the repository root with the project's environment active:

```sh
python manage.py migrate
python manage.py sync_catalog
```

Apply the project's database migrations first; `sync_catalog` discovers the
plugin and updates the catalog used by session creation. Start Redis, the
worker-pool daemon, Gateway, event consumer, and control plane using the
project's normal stack launcher. Then create a session in the browser by
selecting the plugin, or call the session API:

```sh
curl -X POST http://127.0.0.1:8000/api/sessions/ \
  -H 'Content-Type: application/json' \
  -d '{"simulation_id":"temperature_demo","config_params":{"initial_temperature":22}}'
```

The response contains the session token and advertised OPC UA endpoint. Browse
the Gateway's `Objects/Gateway/Sessions/<slug>` folder to read measurements
and write commands. Use the same token with
`DELETE /api/sessions/<token>/` to stop the session. For a runtime-only smoke
test, run the worker with a valid session ID, session name, and OPC UA port.

Before handing off a plugin, check that:

1. The registry finds it and `sync_catalog` lists its ID.
2. Its schema has unique names and valid type strings.
3. A simulation instance returns every declared key in `snapshot()`.
4. Valid commands change state and invalid commands raise `ValueError`.
5. OPC UA clients can read measurements/status and write commands.
6. If provided, the dashboard panel renders from `renderState(state)`.
