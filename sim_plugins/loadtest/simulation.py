"""Minimal deterministic plugin for platform load tests."""

from __future__ import annotations

from typing import Any

from sim_runtime.base import (
    BaseSimulation,
    CommandSpec,
    MeasurementSpec,
    SimulationConfig,
    StatusSpec,
)


class LoadTestSimulation(BaseSimulation):
    SIMULATION_ID = "loadtest"
    SIMULATION_NAME = "Load Test"
    SIMULATION_VERSION = "1.0.0"

    def __init__(self, config: SimulationConfig) -> None:
        self._tick_count = 0
        self._is_active = True

    @classmethod
    def commands(cls) -> dict[str, CommandSpec]:
        return {
            "ResetCount": CommandSpec(
                name="ResetCount",
                type="bool",
                description="Pulse to reset TickCount to zero.",
                pulse=True,
                default=False,
            ),
        }

    @classmethod
    def measurements(cls) -> dict[str, MeasurementSpec]:
        return {
            "TickCount": MeasurementSpec(
                name="TickCount",
                type="int",
                unit="ticks",
                description="Number of runtime steps since the last reset.",
            ),
        }

    @classmethod
    def status(cls) -> dict[str, StatusSpec]:
        return {
            "IsActive": StatusSpec(
                name="IsActive",
                type="bool",
                description="True while this load-test simulation is active.",
            ),
        }

    def step(self, dt: float) -> None:
        self._tick_count += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "measurements": {"TickCount": self._tick_count},
            "status": {"IsActive": self._is_active},
        }

    def write_command(self, name: str, value: Any) -> None:
        if name != "ResetCount":
            raise ValueError(f"Unknown command: {name}")
        if not isinstance(value, bool):
            raise ValueError("ResetCount must be a bool")
        if value:
            self._tick_count = 0
