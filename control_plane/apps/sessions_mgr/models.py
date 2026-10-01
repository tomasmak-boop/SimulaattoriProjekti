"""Session, catalog, and event models.

Design notes:

- No user model. No personal data. Sessions are identified by a random
  UUID and accessed by a capability token in the URL. There is nothing
  here that identifies a person.

- ``Session`` holds the durable record of a simulation session. Runtime
  fields (status, port, pid) are mirrors of state that actually lives
  in Redis. Postgres is the history, Redis is the truth about "what is
  running right now."

- ``SimulationCatalog`` is a snapshot of the plugin registry. It is
  refreshed by a management command that reads the plugins on disk.
  The purpose is to let the UI show a list of available simulations
  without the web process having to import every plugin.

- ``SessionEvent`` is append-only. Every state transition, every crash,
  every stop is recorded here with no personal data. Retention is
  thirty days by default; a management command purges older rows.
"""

from __future__ import annotations

import secrets
import uuid

from django.db import models


def _capability_token() -> str:
    """Return a URL-safe capability token.

    32 bytes of randomness gives 256 bits, encoded in 43 characters of
    base64 without padding. Guessing one is not feasible.
    """
    return secrets.token_urlsafe(32)


class SimulationCatalog(models.Model):
    """One row per plugin discovered in sim_plugins/.

    Populated by ``manage.py sync_catalog``. ``is_active`` lets an
    operator hide a plugin from the UI without deleting its row.
    """

    simulation_id = models.CharField(max_length=64, unique=True)
    display_name = models.CharField(max_length=128)
    version = models.CharField(max_length=32)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    discovered_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "simulation_catalog"
        ordering = ["simulation_id"]

    def __str__(self) -> str:
        return f"{self.simulation_id} ({self.version})"


class Session(models.Model):
    """A single simulation session."""

    STATUS_PENDING = "pending"
    STATUS_STARTING = "starting"
    STATUS_RUNNING = "running"
    STATUS_STOPPING = "stopping"
    STATUS_STOPPED = "stopped"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_STARTING, "Starting"),
        (STATUS_RUNNING, "Running"),
        (STATUS_STOPPING, "Stopping"),
        (STATUS_STOPPED, "Stopped"),
        (STATUS_FAILED, "Failed"),
    ]

    # Primary key is a UUID so the token in the URL and the session ID
    # are different values. Leaking one does not leak the other.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # The capability token. Whoever presents this can view and stop the
    # session. Stored in the URL as /s/<token>/. Rotatable by setting a
    # new value, which invalidates all existing links.
    token = models.CharField(
        max_length=64, unique=True, default=_capability_token, editable=False,
    )

    # What simulation this session is running. Recorded at creation
    # from SimulationCatalog, not from the plugin itself, so the record
    # is stable even if the plugin is later removed.
    simulation_id = models.CharField(max_length=64)
    simulation_version = models.CharField(max_length=32, blank=True)

    # Optional human label. This is a label of the session, not an
    # identifier of a person. Users can leave it blank.
    label = models.CharField(max_length=128, blank=True)

    # Configuration passed to the plugin as SimulationConfig.params.
    config_params = models.JSONField(default=dict, blank=True)

    # Runtime state. Mirrored from Redis; the daemon is authoritative.
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    port = models.IntegerField(null=True, blank=True)
    pid = models.IntegerField(null=True, blank=True)
    advertised_endpoint = models.CharField(max_length=256, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sessions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        label = self.label or str(self.id)
        return f"{label} [{self.status}]"

    @property
    def is_terminal(self) -> bool:
        return self.status in (self.STATUS_STOPPED, self.STATUS_FAILED)


class SessionEvent(models.Model):
    """Append-only event log. No personal data.

    One row per lifecycle event: created, started, ready, stopped,
    failed, reaped. Detail is a JSON blob with whatever context the
    event needs. IP addresses, user agents, and names are never stored.
    """

    EVENT_CREATED = "created"
    EVENT_STARTING = "starting"
    EVENT_STARTED = "started"
    EVENT_READY = "ready"
    EVENT_STOPPING = "stopping"
    EVENT_STOPPED = "stopped"
    EVENT_FAILED = "failed"
    EVENT_REAPED = "reaped"
    EVENT_CHOICES = [
        (EVENT_CREATED, "Created"),
        (EVENT_STARTING, "Starting"),
        (EVENT_STARTED, "Started"),
        (EVENT_READY, "Ready"),
        (EVENT_STOPPING, "Stopping"),
        (EVENT_STOPPED, "Stopped"),
        (EVENT_FAILED, "Failed"),
        (EVENT_REAPED, "Reaped"),
    ]

    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="events",
    )
    event = models.CharField(max_length=16, choices=EVENT_CHOICES)
    detail = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "session_events"
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["session", "occurred_at"]),
            models.Index(fields=["occurred_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.session_id} {self.event} @ {self.occurred_at}"