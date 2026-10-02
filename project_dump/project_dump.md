# Project Dump: draft_innovaatioprojekti

- **Root:** `C:\Users\User\Documents\GitHub\draft_innovaatioprojekti`
- **Generated:** 2026-10-01T19:42:01
- **Text files:** 65
- **Binary skipped:** 0
- **Too large skipped:** 0

## Directory Structure

```
draft_innovaatioprojekti/
├── control_plane/
│   ├── apps/
│   │   ├── sessions_mgr/
│   │   │   ├── management/
│   │   │   │   ├── commands/
│   │   │   │   │   ├── __init__.py
│   │   │   │   │   ├── purge_events.py
│   │   │   │   │   ├── run_event_consumer.py
│   │   │   │   │   └── sync_catalog.py
│   │   │   │   └── __init__.py
│   │   │   ├── __init__.py
│   │   │   ├── admin.py
│   │   │   ├── apps.py
│   │   │   ├── models.py
│   │   │   ├── orchestrator.py
│   │   │   ├── serializers.py
│   │   │   ├── urls.py
│   │   │   └── views.py
│   │   └── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── __init__.py
│   ├── asgi.py
│   ├── urls.py
│   └── wsgi.py
├── gateway/
│   ├── __init__.py
│   ├── main.py
│   ├── mirror.py
│   └── server.py
├── shared/
│   ├── constants.py
│   ├── logging.py
│   └── schemas.py
├── sim_plugins/
│   ├── blinker/
│   │   ├── __init__.py
│   │   ├── body.html
│   │   ├── simulation.py
│   │   └── ui.js
│   ├── cip/
│   │   ├── __init__.py
│   │   ├── body.html
│   │   ├── simulation.py
│   │   └── ui.js
│   └── __init__.py
├── sim_runtime/
│   ├── base.py
│   ├── http_adapter.py
│   ├── opcua_adapter.py
│   ├── registry.py
│   └── shell.html
├── tests/
│   ├── manual/
│   │   ├── __init__.py
│   │   ├── test_daemon.py
│   │   ├── test_manager.py
│   │   └── test_redis_bridge.py
│   ├── unit/
│   │   ├── test_blinker.py
│   │   └── test_port_allocator.py
│   └── __init__.py
├── tools/
│   └── opcua_cli.py
├── worker_pool/
│   ├── worker/
│   │   └── main.py
│   ├── __init__.py
│   ├── daemon.py
│   ├── manager.py
│   ├── port_allocator.py
│   └── redis_bridge.py
├── .env.example
├── .gitattributes
├── .gitignore
├── manage.py
├── pyproject.toml
├── requirements.txt
├── run-cip.sh
└── venv-activate.txt
```

## File Contents

### `.env.example`

```
# Django
DJANGO_SECRET_KEY=change-me-in-production
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=10.120.32.67,localhost,127.0.0.1
DJANGO_HSTS=0

# Data stores
DATABASE_URL=sqlite:///db.sqlite3
REDIS_URL=redis://localhost:6379/0

# Logging
LOG_LEVEL=INFO

GATEWAY_PUBLIC_HOST=10.120.32.67:8080
```

### `.gitattributes`

```
# Auto detect text files and perform LF normalization
* text=auto
```

### `.gitignore`

```
.venv/
```

### `manage.py`

```python
#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main() -> None:
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "control_plane.settings.dev"
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
```

### `pyproject.toml`

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### `requirements.txt`

```
# Core runtime
asyncua==2.0.1
pydantic==2.13.5
redis==8.1.0

# Web control plane
Django==5.0.6
djangorestframework==3.15.1
channels==4.1.0
channels-redis==4.2.0
uvicorn[standard]==0.30.1
dj-database-url==2.2.0
psycopg[binary]==3.1.19

# Testing
pytest==9.1.1
pytest-asyncio==1.4.0
fakeredis[lua]==2.38.0
```

### `run-cip.sh`

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
pkill -f 'worker_pool.worker.main' 2>/dev/null || true
sleep 1
exec env REDIS_URL=redis://localhost:6379/0 \
    python -m worker_pool.worker.main \
        --session-id cip-smoke \
        --simulation-id cip \
        --opcua-port 5020 \
        --advertise-host 127.0.0.1 \
        --http-host 127.0.0.1
```

### `venv-activate.txt`

```
#activate venv
cd ~/cip-sim
source .venv/bin/activate
which python


#leave venv
deactivate
```

### `control_plane/__init__.py`

```python

```

### `control_plane/asgi.py`

```python
"""ASGI entry point.

Runs Django's HTTP handler and the Channels WebSocket handler behind
the same application. Uvicorn serves this in dev and prod.
"""

from __future__ import annotations

import os

from channels.routing import ProtocolTypeRouter
from django.core.asgi import get_asgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "control_plane.settings.dev")

# Importing Django's ASGI application must happen before any module
# that touches the app registry (e.g. routing modules that import
# consumers). Order matters.
django_asgi = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi,
    # "websocket": ... added when the Channels consumer lands
})
```

### `control_plane/urls.py`

```python
"""URL configuration."""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.urls import include, path


def health(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


def index(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({
        "service": "cip-sim control plane",
        "version": "0.1.0",
        "api": "/api/",
    })


urlpatterns = [
    path("health/", health, name="health"),
    path("api/", include("control_plane.apps.sessions_mgr.urls")),
    path("", index, name="index"),
]
```

### `control_plane/wsgi.py`

```python
"""WSGI entry point.

Provided so `manage.py runserver` works out of the box during
development. Production runs the ASGI application via uvicorn, which
supports both HTTP and WebSocket. Nothing in the project depends on
this file beyond the dev server.
"""

from __future__ import annotations

import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "control_plane.settings.dev")

application = get_wsgi_application()
```

### `control_plane/apps/__init__.py`

```python

```

### `control_plane/apps/sessions_mgr/__init__.py`

```python

```

### `control_plane/apps/sessions_mgr/admin.py`

```python
from django.contrib import admin

from control_plane.apps.sessions_mgr.models import (
    Session,
    SessionEvent,
    SimulationCatalog,
)


@admin.register(SimulationCatalog)
class SimulationCatalogAdmin(admin.ModelAdmin):
    list_display = ("simulation_id", "display_name", "version", "is_active")
    list_filter = ("is_active",)
    search_fields = ("simulation_id", "display_name")


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("id", "label", "simulation_id", "status", "created_at")
    list_filter = ("status", "simulation_id")
    search_fields = ("id", "label", "token")
    readonly_fields = ("id", "token", "created_at")


@admin.register(SessionEvent)
class SessionEventAdmin(admin.ModelAdmin):
    list_display = ("session_id", "event", "occurred_at")
    list_filter = ("event",)
    readonly_fields = ("session", "event", "detail", "occurred_at")

    def has_add_permission(self, request):  # noqa: ARG002
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ARG002
        return False
```

### `control_plane/apps/sessions_mgr/apps.py`

```python
from django.apps import AppConfig


class SessionsMgrConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "control_plane.apps.sessions_mgr"
    verbose_name = "Session Manager"
```

### `control_plane/apps/sessions_mgr/models.py`

```python
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
```

### `control_plane/apps/sessions_mgr/orchestrator.py`

```python
"""Session orchestrator.

The Django side of the Redis bridge. Publishes StartSessionCommand and
StopSessionCommand to the command stream, and (via a separate consumer
process) receives lifecycle events on the event stream.

Uses the synchronous redis client. Django views are synchronous by
default and the operations here are single XADD calls, so an async
client would add complexity without benefit. The event consumer, which
is a long-running process, uses the async client instead.

The Redis connection is created lazily on first use and cached at
module scope. ``reset_for_tests`` clears it.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import redis
from django.conf import settings

from shared.constants import REDIS_CMD_STREAM, STREAM_MAXLEN
from shared.logging import get_logger
from shared.schemas import (
    PingCommand,
    StartSessionCommand,
    StopSessionCommand,
)


log = get_logger(__name__)


_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _client
    if _client is None:
        url = getattr(settings, "REDIS_URL", None) or "redis://localhost:6379/0"
        _client = redis.from_url(url, decode_responses=True)
    return _client


def reset_for_tests() -> None:
    """Clear the cached client. Used by test fixtures."""
    global _client
    _client = None


def _publish(command) -> str:
    """XADD a command and return its request_id."""
    client = _get_client()
    client.xadd(
        REDIS_CMD_STREAM,
        {"payload": command.model_dump_json()},
        maxlen=STREAM_MAXLEN,
        approximate=True,
    )
    return command.request_id


def request_start(session) -> str:
    """Publish a start command for the given Session row."""
    command = StartSessionCommand(
        session_id=str(session.id),
        simulation_id=session.simulation_id,
        config_params=session.config_params or {},
        request_id=str(uuid.uuid4()),
        issued_at=datetime.now(timezone.utc),
    )
    request_id = _publish(command)
    log.info("start command published", extra={
        "session_id": str(session.id),
        "simulation_id": session.simulation_id,
        "request_id": request_id,
    })
    return request_id


def request_stop(session, reason: str = "user_request") -> str:
    """Publish a stop command for the given Session row."""
    command = StopSessionCommand(
        session_id=str(session.id),
        reason=reason,
        request_id=str(uuid.uuid4()),
        issued_at=datetime.now(timezone.utc),
    )
    request_id = _publish(command)
    log.info("stop command published", extra={
        "session_id": str(session.id),
        "reason": reason,
        "request_id": request_id,
    })
    return request_id


def ping() -> str:
    """Send a liveness ping. Useful for health checks."""
    command = PingCommand(
        request_id=str(uuid.uuid4()),
        issued_at=datetime.now(timezone.utc),
    )
    return _publish(command)
```

### `control_plane/apps/sessions_mgr/serializers.py`

```python
"""DRF serializers for the session API.

Two views of the same model:

- SessionSummarySerializer — safe for the public list, no token.
- SessionDetailSerializer — returned on create and on token access.

The token is never included in the list endpoint. It is returned
exactly once, at creation time, as part of the create response.
"""

from __future__ import annotations

from rest_framework import serializers

from control_plane.apps.sessions_mgr.models import (
    Session,
    SessionEvent,
    SimulationCatalog,
)


class SimulationCatalogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SimulationCatalog
        fields = [
            "simulation_id",
            "display_name",
            "version",
            "description",
        ]


class SessionSummarySerializer(serializers.ModelSerializer):
    """Public list view. No token."""

    class Meta:
        model = Session
        fields = [
            "id",
            "simulation_id",
            "simulation_version",
            "label",
            "status",
            "created_at",
            "started_at",
            "stopped_at",
        ]
        read_only_fields = fields


class SessionDetailSerializer(serializers.ModelSerializer):
    """Full view. Includes token and runtime endpoint info."""

    endpoint_url = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = [
            "id",
            "token",
            "simulation_id",
            "simulation_version",
            "label",
            "status",
            "port",
            "pid",
            "advertised_endpoint",
            "endpoint_url",
            "config_params",
            "created_at",
            "started_at",
            "stopped_at",
        ]
        read_only_fields = fields

    def get_endpoint_url(self, obj: Session) -> str:
        """The gateway URL a PLC client should connect to.

        Every session is reached through the same gateway endpoint.
        The session is identified by its folder inside the gateway's
        address space, so the endpoint URL itself does not depend on
        the session. We return the gateway URL with the session ID
        as a hint for the operator.
        """
        host = self.context.get("gateway_host", "")
        if not host:
            return ""
        return f"opc.tcp://{host}/gateway/"


class SessionCreateSerializer(serializers.Serializer):
    """Input for POST /api/sessions/.

    The client supplies the simulation_id (must exist in the catalog),
    an optional label, and optional config params. Everything else is
    generated by the server.
    """

    simulation_id = serializers.CharField(max_length=64)
    label = serializers.CharField(
        max_length=128, required=False, allow_blank=True, default="",
    )
    config_params = serializers.JSONField(required=False, default=dict)

    def validate_simulation_id(self, value: str) -> str:
        if not SimulationCatalog.objects.filter(
            simulation_id=value, is_active=True,
        ).exists():
            raise serializers.ValidationError(
                f"unknown or inactive simulation: {value}"
            )
        return value

    def validate_config_params(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("must be a JSON object")
        return value


class SessionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionEvent
        fields = ["event", "detail", "occurred_at"]
        read_only_fields = fields
```

### `control_plane/apps/sessions_mgr/urls.py`

```python
from django.urls import path

from control_plane.apps.sessions_mgr import views


urlpatterns = [
    path("simulations/", views.list_simulations, name="list-simulations"),
    path("sessions/", views.sessions_collection, name="sessions-collection"),
    path(
        "sessions/<str:token>/",
        views.session_detail,
        name="session-detail",
    ),
    path(
        "sessions/<str:token>/events/",
        views.session_events,
        name="session-events",
    ),
]
```

### `control_plane/apps/sessions_mgr/views.py`

```python
"""REST API for session management.

Every endpoint is public. Access to a specific session is gated by the
capability token in the URL.

Endpoints:

    GET    /api/simulations/                list available simulations
    GET    /api/sessions/                   list active sessions (no tokens)
    POST   /api/sessions/                   create a session
    GET    /api/sessions/<token>/           session detail (token required)
    DELETE /api/sessions/<token>/           stop a session (token required)
    GET    /api/sessions/<token>/events/    session event log
"""

from __future__ import annotations

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from control_plane.apps.sessions_mgr import orchestrator
from control_plane.apps.sessions_mgr.models import (
    Session,
    SessionEvent,
    SimulationCatalog,
)
from control_plane.apps.sessions_mgr.serializers import (
    SessionCreateSerializer,
    SessionDetailSerializer,
    SessionEventSerializer,
    SessionSummarySerializer,
    SimulationCatalogSerializer,
)
from shared.logging import get_logger


log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Simulations
# ---------------------------------------------------------------------------

@api_view(["GET"])
def list_simulations(request):  # noqa: ARG001
    """Available simulations, from the catalog."""
    qs = SimulationCatalog.objects.filter(is_active=True)
    return Response(SimulationCatalogSerializer(qs, many=True).data)


# ---------------------------------------------------------------------------
# Sessions collection (GET list, POST create)
# ---------------------------------------------------------------------------

@api_view(["GET", "POST"])
def sessions_collection(request):
    if request.method == "GET":
        return _list_sessions(request)
    return _create_session(request)


def _list_sessions(request):
    """Active sessions, safe to show to anyone.

    Only sessions that are not in a terminal state by default. Pass
    ?include_stopped=1 to see everything.
    """
    qs = Session.objects.all()
    include_stopped = request.query_params.get("include_stopped") in (
        "1", "true", "yes",
    )
    if not include_stopped:
        qs = qs.exclude(
            status__in=[Session.STATUS_STOPPED, Session.STATUS_FAILED]
        )
    return Response(SessionSummarySerializer(qs, many=True).data)


def _create_session(request):
    """Create a session and ask the daemon to start it.

    Returns the full session record including the capability token.
    This is the only time the token is returned in a list-shaped
    response; every other endpoint requires the token in the URL.
    """
    ser = SessionCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    sim_id = ser.validated_data["simulation_id"]
    catalog = SimulationCatalog.objects.get(simulation_id=sim_id)

    session = Session.objects.create(
        simulation_id=sim_id,
        simulation_version=catalog.version,
        label=ser.validated_data.get("label", ""),
        config_params=ser.validated_data.get("config_params", {}),
        status=Session.STATUS_PENDING,
    )
    _record_event(session, SessionEvent.EVENT_CREATED)

    try:
        orchestrator.request_start(session)
    except Exception:
        log.exception("failed to publish start command",
                      extra={"session_id": str(session.id)})
        session.status = Session.STATUS_FAILED
        session.save(update_fields=["status"])
        _record_event(
            session, SessionEvent.EVENT_FAILED,
            detail={"error": "could not reach command bus"},
        )
        return Response(
            SessionDetailSerializer(session, context=_ctx(request)).data,
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        SessionDetailSerializer(session, context=_ctx(request)).data,
        status=status.HTTP_201_CREATED,
    )


# ---------------------------------------------------------------------------
# Session detail (GET, DELETE)
# ---------------------------------------------------------------------------

@api_view(["GET", "DELETE"])
def session_detail(request, token: str):
    """Get or stop one session. Requires the capability token."""
    session = get_object_or_404(Session, token=token)

    if request.method == "GET":
        return Response(
            SessionDetailSerializer(session, context=_ctx(request)).data
        )

    # DELETE — stop the session
    if session.is_terminal:
        return Response(
            SessionDetailSerializer(session, context=_ctx(request)).data,
            status=status.HTTP_200_OK,
        )

    session.status = Session.STATUS_STOPPING
    session.save(update_fields=["status"])
    _record_event(session, SessionEvent.EVENT_STOPPING)

    try:
        orchestrator.request_stop(session, reason="user_request")
    except Exception:
        log.exception("failed to publish stop command",
                      extra={"session_id": str(session.id)})
        return Response(
            {"detail": "could not reach command bus"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        SessionDetailSerializer(session, context=_ctx(request)).data
    )


# ---------------------------------------------------------------------------
# Session events
# ---------------------------------------------------------------------------

@api_view(["GET"])
def session_events(request, token: str):
    """The event log for one session. Requires the capability token."""
    session = get_object_or_404(Session, token=token)
    events = session.events.all()[:100]
    return Response(SessionEventSerializer(events, many=True).data)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(request) -> dict:
    host = getattr(settings, "GATEWAY_PUBLIC_HOST", "") or request.get_host()
    return {"gateway_host": host}


def _record_event(session: Session, event: str, detail: dict | None = None) -> None:
    SessionEvent.objects.create(
        session=session,
        event=event,
        detail=detail or {},
    )
```

### `control_plane/apps/sessions_mgr/management/__init__.py`

```python

```

### `control_plane/apps/sessions_mgr/management/commands/__init__.py`

```python

```

### `control_plane/apps/sessions_mgr/management/commands/purge_events.py`

```python
"""Delete SessionEvent rows older than the retention window.

Default retention is 30 days, configurable with --days. Run from cron
or a systemd timer.

Usage:
    python manage.py purge_events
    python manage.py purge_events --days 7
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from control_plane.apps.sessions_mgr.models import SessionEvent


class Command(BaseCommand):
    help = "Delete session events older than the retention window."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--days", type=int, default=30,
            help="Retention window in days (default: 30).",
        )

    def handle(self, *args, **options) -> None:
        days = options["days"]
        if days < 1:
            self.stderr.write("--days must be >= 1")
            return

        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = SessionEvent.objects.filter(
            occurred_at__lt=cutoff
        ).delete()

        self.stdout.write(self.style.SUCCESS(
            f"purged {deleted} event(s) older than {days} day(s)"
        ))
```

### `control_plane/apps/sessions_mgr/management/commands/run_event_consumer.py`

```python
"""Consume lifecycle events from the daemon and update the database.

Runs as a long-lived process alongside the control plane. Reads from
the events stream using a consumer group, updates the Session row
described by each event, writes a SessionEvent row, and XACKs.

Run as a systemd service in production. For development:

    python manage.py run_event_consumer
"""

from __future__ import annotations

import asyncio
import json

import redis.asyncio as aioredis
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from control_plane.apps.sessions_mgr.models import Session, SessionEvent
from shared.constants import (
    EVT_CONSUMER_GROUP,
    REDIS_EVT_STREAM,
)
from shared.logging import get_logger
from shared.schemas import (
    SessionFailedEvent,
    SessionReadyEvent,
    SessionStartedEvent,
    SessionStoppedEvent,
    parse_event,
)


log = get_logger(__name__)


_READ_BLOCK_MS = 2000


class Command(BaseCommand):
    help = "Consume session lifecycle events and update the database."

    def handle(self, *args, **options) -> None:  # noqa: ARG002
        try:
            asyncio.run(self._run())
        except KeyboardInterrupt:
            self.stdout.write("interrupted")

    async def _run(self) -> None:
        redis_url = getattr(settings, "REDIS_URL", None) \
            or "redis://localhost:6379/0"
        client = aioredis.from_url(redis_url, decode_responses=True)

        await self._ensure_group(client)
        consumer = f"control-plane-{timezone.now().timestamp():.0f}"

        self.stdout.write(f"event consumer started as {consumer}")
        log.info("event consumer started", extra={"consumer": consumer})

        try:
            while True:
                await self._consume_once(client, consumer)
        finally:
            await client.aclose()

    async def _ensure_group(self, client: aioredis.Redis) -> None:
        try:
            await client.xgroup_create(
                REDIS_EVT_STREAM, EVT_CONSUMER_GROUP,
                id="0", mkstream=True,
            )
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def _consume_once(
        self, client: aioredis.Redis, consumer: str
    ) -> None:
        try:
            entries = await asyncio.wait_for(
                client.xreadgroup(
                    EVT_CONSUMER_GROUP, consumer,
                    {REDIS_EVT_STREAM: ">"},
                    count=20, block=_READ_BLOCK_MS,
                ),
                timeout=(_READ_BLOCK_MS / 1000.0) + 2.0,
            )
        except asyncio.TimeoutError:
            return
        except Exception:
            log.exception("xreadgroup failed")
            await asyncio.sleep(1.0)
            return

        for _stream, messages in entries or []:
            for msg_id, fields in messages:
                await self._handle(fields)
                try:
                    await client.xack(
                        REDIS_EVT_STREAM, EVT_CONSUMER_GROUP, msg_id,
                    )
                except Exception:
                    log.exception("xack failed", extra={"msg_id": msg_id})

    async def _handle(self, fields: dict) -> None:
        payload = fields.get("payload")
        if not payload:
            return
        try:
            event = parse_event(payload)
        except Exception:
            log.exception("unparsable event")
            return

        # DB work is synchronous; run it in a thread so the event loop
        # stays responsive.
        await asyncio.to_thread(self._apply, event)

    def _apply(self, event) -> None:
        close_old_connections()

        session = Session.objects.filter(id=event.session_id).first()
        if session is None:
            log.warning("event for unknown session",
                        extra={"session_id": event.session_id,
                               "kind": event.kind})
            return

        if isinstance(event, SessionStartedEvent):
            session.status = Session.STATUS_RUNNING
            session.port = event.port
            session.pid = event.pid
            session.advertised_endpoint = event.advertised_endpoint
            if session.started_at is None:
                session.started_at = timezone.now()
            session.save(update_fields=[
                "status", "port", "pid",
                "advertised_endpoint", "started_at",
            ])
            _record(session, SessionEvent.EVENT_STARTED, {
                "port": event.port,
                "pid": event.pid,
            })

        elif isinstance(event, SessionReadyEvent):
            # The worker is actually accepting connections now.
            _record(session, SessionEvent.EVENT_READY, {
                "port": event.port,
                "pid": event.pid,
            })

        elif isinstance(event, SessionStoppedEvent):
            session.status = Session.STATUS_STOPPED
            session.stopped_at = timezone.now()
            session.port = None
            session.pid = None
            session.advertised_endpoint = ""
            session.save(update_fields=[
                "status", "stopped_at", "port", "pid",
                "advertised_endpoint",
            ])
            _record(session, SessionEvent.EVENT_STOPPED, {
                "reason": event.reason,
                "exit_code": event.exit_code,
            })

        elif isinstance(event, SessionFailedEvent):
            session.status = Session.STATUS_FAILED
            session.stopped_at = timezone.now()
            session.save(update_fields=["status", "stopped_at"])
            _record(session, SessionEvent.EVENT_FAILED, {
                "error": event.error,
            })


def _record(session: Session, event: str, detail: dict) -> None:
    SessionEvent.objects.create(
        session=session, event=event, detail=detail or {},
    )
```

### `control_plane/apps/sessions_mgr/management/commands/sync_catalog.py`

```python
"""Sync the simulation catalog with the plugins on disk.

Reads every plugin's SIMULATION_ID, name, and version via the same
registry the worker uses, and upserts one row per plugin. Deactivating
a plugin that no longer exists rather than deleting its row preserves
any session history that references it.

Usage:
    python manage.py sync_catalog
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from control_plane.apps.sessions_mgr.models import SimulationCatalog
from sim_runtime.registry import SimulationRegistry


class Command(BaseCommand):
    help = "Sync SimulationCatalog with the plugin registry."

    def handle(self, *args, **options) -> None:
        registry = SimulationRegistry()
        registry.load_from()

        seen_ids: set[str] = set()
        created = updated = 0

        for sim_id in registry.ids():
            cls = registry.get(sim_id)
            seen_ids.add(sim_id)

            _, was_created = SimulationCatalog.objects.update_or_create(
                simulation_id=sim_id,
                defaults={
                    "display_name": cls.SIMULATION_NAME,
                    "version": cls.SIMULATION_VERSION,
                    "description": (cls.__doc__ or "").strip().split("\n")[0],
                    "is_active": True,
                    "discovered_at": timezone.now(),
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        # Deactivate rows for plugins that no longer exist on disk.
        deactivated = SimulationCatalog.objects.exclude(
            simulation_id__in=seen_ids
        ).update(is_active=False)

        self.stdout.write(self.style.SUCCESS(
            f"catalog: {created} created, {updated} updated, "
            f"{deactivated} deactivated"
        ))
```

### `control_plane/settings/__init__.py`

```python

```

### `control_plane/settings/base.py`

```python
"""Shared Django settings.

Reads every value from the environment so the same code runs in dev,
test, and production without changes. The only files that differ
between environments are dev.py and prod.py, and each overrides just a
handful of variables.
"""

from __future__ import annotations

import os
from pathlib import Path

import dj_database_url

from shared.logging import JSONFormatter


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

REDIS_URL = _env("REDIS_URL", "redis://localhost:6379/0")
GATEWAY_PUBLIC_HOST = _env("GATEWAY_PUBLIC_HOST", "")
SECRET_KEY = _env("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = _env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

ROOT_URLCONF = "control_plane.urls"
WSGI_APPLICATION = "control_plane.wsgi.application"
ASGI_APPLICATION = "control_plane.asgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "control_plane.apps.sessions_mgr",
]


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "control_plane" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    "default": dj_database_url.parse(
        _env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
    ),
}


# ---------------------------------------------------------------------------
# Channels
# ---------------------------------------------------------------------------

_redis_url = _env("REDIS_URL", "redis://localhost:6379/0")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [_redis_url]},
    },
}


# ---------------------------------------------------------------------------
# REST framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [],      # no accounts
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny", # capability URLs are the gate
    ],
    "UNAUTHENTICATED_USER": None,
}


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# ---------------------------------------------------------------------------
# Logging — JSON, structured, correlated by session_id
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": JSONFormatter},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.access": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
```

### `control_plane/settings/dev.py`

```python
"""Development settings.

DEBUG on, verbose errors, SQLite by default, permissive hosts. Not
suitable for anything reachable from another machine.
"""

from control_plane.settings.base import *  # noqa: F401,F403
from control_plane.settings.base import _env_bool


DEBUG = True

ALLOWED_HOSTS = ["*"]

# CSRF protection stays on, but in dev we accept connections over
# plain HTTP from any host.
CSRF_TRUSTED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]

# SQLite by default; can be overridden by DATABASE_URL in the shell.
# Nothing in the project depends on Postgres-specific features.
```

### `control_plane/settings/prod.py`

```python
"""Production settings.

Assumes a reverse proxy or direct exposure on the intranet. Cookies
are marked secure, HSTS is on, and the app refuses to start without a
real secret key.
"""

import os

from control_plane.settings.base import *  # noqa: F401,F403
from control_plane.settings.base import _env_list


DEBUG = False

if os.environ.get("DJANGO_SECRET_KEY", "").startswith("dev-"):
    raise RuntimeError(
        "DJANGO_SECRET_KEY is still the development default. "
        "Set a real secret in /etc/cip-sim/env."
    )

ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS")

# Cookies. Even though there is no login, the CSRF and session cookies
# are still used and should carry the Secure flag when served over TLS.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS is only meaningful over TLS. If TLS is terminated upstream and
# forwarded as HTTPS, enable this; otherwise leave it off. It is
# enabled by setting DJANGO_HSTS=1 in the environment.
if os.environ.get("DJANGO_HSTS", "").lower() in ("1", "true", "yes"):
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Trust the X-Forwarded-Proto header when behind a reverse proxy that
# terminates TLS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
```

### `gateway/__init__.py`

```python

```

### `gateway/main.py`

```python
"""OPC UA Aggregation Gateway entrypoint.

Exposes one OPC UA endpoint on a whitelisted port. Internally connects to
each running worker as a client, mirrors its schema under a session folder,
and proxies reads/writes through subscriptions and value setters.

The gateway reads session lifecycle events from the Redis events stream.
When a session becomes ready, a WorkerMirror connects and mirrors it. When
a session stops, the mirror is torn down.

On startup, the gateway reconciles against Redis heartbeats so it picks up
workers that were already running before the gateway started.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys

import redis.asyncio as aioredis

from gateway.server import Gateway
from shared.constants import GATEWAY_OPCUA_PORT
from shared.logging import configure_logging, get_logger


log = get_logger(__name__)


async def _run(args: argparse.Namespace) -> int:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = aioredis.from_url(redis_url, decode_responses=True)

    gateway = Gateway(
        advertise_host=args.advertise_host,
        port=args.port,
        redis=r,
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    # 1. Start the OPC UA server.
    await gateway.start()

    # 2. Pick up any workers that were already running before we started.
    #    This makes the gateway restart-safe: it does not depend on having
    #    seen the SessionReadyEvent, only on the worker's heartbeat.
    await gateway.reconcile_existing()

    # 3. Consume new events until signalled to stop.
    failed = False
    try:
        await gateway.run_event_loop(stop)
    except Exception:
        log.exception("gateway event loop failed")
        failed = True
    finally:
        await gateway.stop()
        try:
            await r.aclose()
        except Exception:
            pass

    return 1 if failed else 0


def main() -> int:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    p = argparse.ArgumentParser(description="OPC UA Aggregation Gateway")
    p.add_argument("--advertise-host", required=True,
                   help="Host/IP the gateway advertises (e.g. 10.120.32.67)")
    p.add_argument("--port", type=int, default=GATEWAY_OPCUA_PORT)
    args = p.parse_args()
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `gateway/mirror.py`

```python
"""Mirror one worker's OPC UA address space inside the gateway.

Reads the worker's schema once at connect time to build a mirrored subtree
under the session folder. Subscribes to the worker's measurement and status
nodes so gateway values stay current. Command nodes get a setter that
forwards writes back to the worker through the gateway's write queue.

The worker's root object exposes three self-describing properties that
this mirror reads on connect:

    SimulationId       e.g. "cip"
    SimulationName     e.g. "Clean-In-Place"
    NamespaceUri       e.g. "urn:cip-sim:cip:2.0.0"

Reading these instead of keeping a hardcoded map means adding a new
plugin to the project requires no changes to the gateway.
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable

from asyncua import Client, Node, Server, ua

from shared.logging import get_logger


log = get_logger(__name__)


def _coerce_value(value: Any, variant_type: ua.VariantType) -> Any:
    """Coerce a Python value to match a target OPC UA variant type."""
    if variant_type == ua.VariantType.Boolean:
        return bool(value)
    if variant_type in (ua.VariantType.Int16,
                        ua.VariantType.Int32,
                        ua.VariantType.Int64):
        return int(value)
    if variant_type in (ua.VariantType.UInt16,
                        ua.VariantType.UInt32,
                        ua.VariantType.UInt64):
        v = int(value)
        return v if v >= 0 else 0
    if variant_type in (ua.VariantType.Float, ua.VariantType.Double):
        return float(value)
    if variant_type == ua.VariantType.String:
        return str(value)
    return value


def _default_for(variant_type: ua.VariantType) -> Any:
    if variant_type == ua.VariantType.Boolean:
        return False
    if variant_type in (ua.VariantType.Int16, ua.VariantType.Int32,
                        ua.VariantType.Int64):
        return 0
    if variant_type in (ua.VariantType.UInt16, ua.VariantType.UInt32,
                        ua.VariantType.UInt64):
        return 0
    if variant_type in (ua.VariantType.Float, ua.VariantType.Double):
        return 0.0
    if variant_type == ua.VariantType.String:
        return ""
    return None


class SimulationRootNotFound(RuntimeError):
    """Raised when a worker has no node carrying the SimulationId property."""


class WorkerMirror:
    def __init__(
        self,
        *,
        session_id: str,
        simulation_id: str,
        worker_endpoint: str,
        parent_folder: Node,
        namespace_idx: int,
        server: Server,
        enqueue_write: Callable[[str, str, Any], None],
    ) -> None:
        self.session_id = session_id
        self.simulation_id = simulation_id
        self.worker_endpoint = worker_endpoint
        self._parent_folder = parent_folder
        self._namespace_idx = namespace_idx
        self._server = server
        self._enqueue_write = enqueue_write

        self._client: Client | None = None
        self._session_folder: Node | None = None
        self._subscription = None

        # Discovered on connect.
        self._worker_ns: int = 0
        self._worker_ns_uri: str = ""
        self._worker_root: Node | None = None

        # worker NodeId (as string) -> (gateway Node, target VariantType)
        self._map: dict[str, tuple[Node, ua.VariantType]] = {}

    # --- lifecycle ---

    async def connect_and_mirror(self) -> None:
        self._client = Client(url=self.worker_endpoint)
        await self._client.connect()
        log.info("connected to worker", extra={
            "session_id": self.session_id, "endpoint": self.worker_endpoint,
        })

        # Discover the simulation root by looking for a node with a
        # SimulationId property. No hardcoded namespace or folder name.
        self._worker_root, self._worker_ns_uri = (
            await self._discover_simulation_root()
        )
        try:
            self._worker_ns = await self._client.get_namespace_index(
                self._worker_ns_uri
            )
        except Exception as exc:
            raise SimulationRootNotFound(
                f"worker namespace {self._worker_ns_uri!r} not registered "
                f"on client side"
            ) from exc

        log.info("discovered simulation root", extra={
            "session_id": self.session_id,
            "namespace": self._worker_ns_uri,
        })

        ns = self._namespace_idx
        self._session_folder = await self._parent_folder.add_folder(
            ua.NodeId(f"Gateway.Sessions.{self.session_id}", ns),
            ua.QualifiedName(self.session_id, ns),
        )

        for folder_name in ("Commands", "Measurements", "Status"):
            try:
                await self._mirror_folder(folder_name)
            except Exception:
                log.exception("failed to mirror folder",
                              extra={"folder": folder_name,
                                     "session_id": self.session_id})

        await self._start_subscription()

    async def _discover_simulation_root(self) -> tuple[Node, str]:
        """Return (root_node, namespace_uri) by reading a SimulationId property.

        Walks the worker's Objects folder. Any child that has a property
        named SimulationId is treated as a simulation root. Reads the
        NamespaceUri property from the same node.
        """
        if self._client is None:
            raise SimulationRootNotFound("client not connected")

        objects = self._client.nodes.objects
        children = await objects.get_children()
        for child in children:
            try:
                props = await child.get_properties()
            except Exception:
                continue
            prop_map: dict[str, Any] = {}
            for prop in props:
                try:
                    name = (await prop.read_browse_name()).Name
                    value = await prop.read_value()
                    prop_map[name] = value
                except Exception:
                    continue
            if "SimulationId" not in prop_map:
                continue
            ns_uri = prop_map.get("NamespaceUri")
            if not isinstance(ns_uri, str) or not ns_uri:
                raise SimulationRootNotFound(
                    f"root {prop_map['SimulationId']!r} has no NamespaceUri"
                )
            return child, ns_uri

        raise SimulationRootNotFound(
            "no node with SimulationId property found under Objects"
        )

    async def disconnect(self) -> None:
        if self._subscription is not None:
            try:
                await self._subscription.delete()
            except Exception:
                pass
            self._subscription = None
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None

    # --- mirroring ---

    async def _mirror_folder(self, folder_name: str) -> None:
        worker_ns = self._worker_ns
        worker_folder = await self._worker_root.get_child(
            [f"{worker_ns}:{folder_name}"]
        )

        ns = self._namespace_idx
        gateway_folder = await self._session_folder.add_folder(
            ua.NodeId(
                f"Gateway.Sessions.{self.session_id}.{folder_name}", ns
            ),
            ua.QualifiedName(folder_name, ns),
        )

        for worker_child in await worker_folder.get_children():
            await self._mirror_variable(
                worker_child, gateway_folder, folder_name
            )

    async def _mirror_variable(
        self, worker_node: Node, gateway_folder: Node, folder_name: str
    ) -> None:
        name = (await worker_node.read_browse_name()).Name

        try:
            variant_type = await worker_node.read_data_type_as_variant_type()
        except Exception:
            log.warning("could not read data type; assuming Double",
                        extra={"session_id": self.session_id, "name": name})
            variant_type = ua.VariantType.Double

        try:
            raw_value = await worker_node.read_value()
            value = _coerce_value(raw_value, variant_type)
        except Exception:
            value = _default_for(variant_type)

        ns = self._namespace_idx
        gateway_node = await gateway_folder.add_variable(
            ua.NodeId(
                f"Gateway.Sessions.{self.session_id}"
                f".{folder_name}.{name}", ns
            ),
            ua.QualifiedName(name, ns),
            value,
            variant_type,
        )
        await gateway_node.set_writable()

        self._map[worker_node.nodeid.to_string()] = (gateway_node, variant_type)

        if folder_name == "Commands":
            self._server.set_attribute_value_setter(
                gateway_node.nodeid,
                self._make_command_setter(name),
            )

    def _make_command_setter(self, name: str):
        session_id = self.session_id
        enqueue = self._enqueue_write

        def set_value(node_data, attribute, value: ua.DataValue) -> None:
            if value is None or value.Value is None:
                return
            raw = value.Value.Value
            node_data.attributes[attribute].value = value
            enqueue(session_id, name, raw)

        return set_value

    # --- subscription ---

    async def _start_subscription(self) -> None:
        if self._client is None or not self._map:
            return

        handler = _MirrorSubscriptionHandler(self._map)
        self._subscription = await self._client.create_subscription(500, handler)

        worker_nodes = [
            self._client.get_node(nid_str) for nid_str in self._map.keys()
        ]
        if worker_nodes:
            await self._subscription.subscribe_data_change(worker_nodes)

    # --- command forwarding ---

    async def forward_command(self, name: str, value: Any) -> None:
        if self._client is None or self._worker_root is None:
            return

        worker_ns = self._worker_ns
        node = await self._worker_root.get_child([
            f"{worker_ns}:Commands",
            f"{worker_ns}:{name}",
        ])

        variant_type = await node.read_data_type_as_variant_type()
        coerced = _coerce_value(value, variant_type)
        await node.write_value(ua.Variant(coerced, variant_type))


class _MirrorSubscriptionHandler:
    """Push worker value changes into the corresponding gateway node."""

    def __init__(
        self, mapping: dict[str, tuple[Node, ua.VariantType]]
    ) -> None:
        self._map = mapping

    def datachange_notification(self, node: Node, val: Any, data) -> None:
        entry = self._map.get(node.nodeid.to_string())
        if entry is None:
            return
        gateway_node, variant_type = entry

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        coerced = _coerce_value(val, variant_type)
        loop.create_task(_safe_write(gateway_node, coerced, variant_type))


async def _safe_write(
    node: Node, value: Any, variant_type: ua.VariantType
) -> None:
    try:
        await node.write_value(ua.Variant(value, variant_type))
    except Exception:
        log.warning("mirror value update skipped",
                    extra={"variant_type": str(variant_type)})
```

### `gateway/server.py`

```python
"""Gateway OPC UA server.

Owns the aggregate address space. Each active session appears under
Objects/Gateway/Sessions/<session_id>/. Mirrors are kept in a dict and
updated as session events arrive.

Two ways mirrors get added:

  1. reconcile_existing() — at startup, scan Redis heartbeats. This is
     the ground truth for "what workers are alive right now" and does not
     depend on having seen the SessionReadyEvent.
  2. run_event_loop() — consume the events stream for sessions that start
     or stop while the gateway is running.

Both paths converge on _add_mirror and _remove_mirror.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable

import redis.asyncio as aioredis
from asyncua import Server, ua

from gateway.mirror import SimulationRootNotFound, WorkerMirror
from shared.constants import (
    GATEWAY_EVT_CONSUMER_GROUP,
    REDIS_EVT_STREAM,
    REDIS_HEARTBEAT_PREFIX,
)
from shared.logging import get_logger
from shared.schemas import (
    SessionFailedEvent,
    SessionReadyEvent,
    SessionStoppedEvent,
    parse_event,
)


log = get_logger(__name__)


class Gateway:
    def __init__(
        self,
        *,
        advertise_host: str,
        port: int,
        redis: aioredis.Redis,
    ) -> None:
        self._advertise_host = advertise_host
        self._port = port
        self._redis = redis

        self._server = Server()
        self._namespace_idx: int = 0
        self._sessions_folder: ua.Node | None = None

        self._mirrors: dict[str, WorkerMirror] = {}
        self._mirrors_lock = asyncio.Lock()

        # Pending outbound writes to workers. The setter callback is
        # synchronous; enqueueing here decouples it from the async write.
        self._write_queue: asyncio.Queue[tuple[str, str, Any]] = asyncio.Queue()
        self._write_task: asyncio.Task | None = None

        self._endpoint = f"opc.tcp://{advertise_host}:{port}/gateway/"

    # --- lifecycle ---

    async def start(self) -> None:
        await self._server.init()
        self._server.set_endpoint(self._endpoint)
        self._server.set_server_name("CIP Simulation Gateway")
        await self._server.set_application_uri("urn:cip-sim:gateway")
        self._server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        self._server.set_identity_tokens([ua.AnonymousIdentityToken])

        self._namespace_idx = await self._server.register_namespace(
            "urn:cip-sim:gateway:1.0.0"
        )
        ns = self._namespace_idx

        root = await self._server.nodes.objects.add_object(
            ua.NodeId("Gateway", ns),
            ua.QualifiedName("Gateway", ns),
        )
        self._sessions_folder = await root.add_folder(
            ua.NodeId("Gateway.Sessions", ns),
            ua.QualifiedName("Sessions", ns),
        )

        self._write_task = asyncio.create_task(self._drain_writes())

        await self._server.start()
        log.info("gateway listening", extra={"endpoint": self._endpoint})

    async def stop(self) -> None:
        if self._write_task:
            self._write_task.cancel()
            try:
                await self._write_task
            except (asyncio.CancelledError, Exception):
                pass

        async with self._mirrors_lock:
            mirrors = list(self._mirrors.values())
            self._mirrors.clear()
        for m in mirrors:
            try:
                await m.disconnect()
            except Exception:
                log.exception("error disconnecting mirror",
                              extra={"session_id": m.session_id})

        try:
            await self._server.stop()
        except Exception:
            log.exception("error stopping gateway server")

    # --- startup reconciliation ---

    async def reconcile_existing(self) -> None:
        """Scan Redis heartbeats and mirror every live worker.

        Called once at startup. This is the correct, restart-safe way to
        rebuild state; the event stream only covers transitions that
        happen while the gateway is running.

        Reads simulation_id from the heartbeat payload. Workers write it
        there on every heartbeat, so a session created before the
        gateway started is still discoverable.
        """
        log.info("reconcile: starting")
        keys = await self._redis.keys(f"{REDIS_HEARTBEAT_PREFIX}*")
        log.info("reconcile: scanned keys", extra={"count": len(keys)})

        if not keys:
            log.info("reconcile: no live sessions")
            return

        seen: list[str] = []
        for key in keys:
            session_id = key.split(":", 2)[-1]
            hb_raw = await self._redis.get(key)
            if not hb_raw:
                continue
            try:
                hb = json.loads(hb_raw)
            except Exception:
                log.warning("reconcile: unparsable heartbeat",
                            extra={"session_id": session_id})
                continue

            port = hb.get("port")
            pid = hb.get("pid", 0)
            sim_id = hb.get("simulation_id")
            if port is None or not sim_id:
                log.warning(
                    "reconcile: heartbeat missing port or simulation_id",
                    extra={"session_id": session_id},
                )
                continue

            ev = SessionReadyEvent(
                session_id=session_id,
                simulation_id=str(sim_id),
                port=int(port),
                pid=int(pid),
            )
            await self._add_mirror(ev)
            seen.append(session_id)

        log.info("reconcile complete",
                 extra={"sessions": seen, "count": len(seen)})

    # --- event loop ---

    async def run_event_loop(self, stop: asyncio.Event) -> None:
        # Create the consumer group starting from the beginning of the
        # stream (id="0") so we don't miss events that arrived before we
        # started. Combined with reconcile_existing this covers both the
        # cold-start and restart cases.
        try:
            await self._redis.xgroup_create(
                REDIS_EVT_STREAM, GATEWAY_EVT_CONSUMER_GROUP,
                id="0", mkstream=True,
            )
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise

        consumer = f"gateway-{self._port}"

        while not stop.is_set():
            try:
                entries = await asyncio.wait_for(
                    self._redis.xreadgroup(
                        GATEWAY_EVT_CONSUMER_GROUP, consumer,
                        {REDIS_EVT_STREAM: ">"},
                        count=10, block=2000,
                    ),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                continue
            except Exception:
                log.exception("xreadgroup failed")
                await asyncio.sleep(1.0)
                continue

            for _stream, messages in entries:
                for msg_id, fields in messages:
                    await self._handle_event(fields)
                    try:
                        await self._redis.xack(
                            REDIS_EVT_STREAM, GATEWAY_EVT_CONSUMER_GROUP,
                            msg_id,
                        )
                    except Exception:
                        log.exception("xack failed")

    async def _handle_event(self, fields: dict) -> None:
        payload = fields.get("payload")
        if not payload:
            return
        try:
            event = parse_event(payload)
        except Exception:
            log.exception("bad event payload")
            return

        if isinstance(event, SessionReadyEvent):
            await self._add_mirror(event)
        elif isinstance(event, (SessionStoppedEvent, SessionFailedEvent)):
            await self._remove_mirror(event.session_id)

    # --- mirrors ---

    async def _add_mirror(self, ev: SessionReadyEvent) -> None:
        async with self._mirrors_lock:
            if ev.session_id in self._mirrors:
                return

        # The gateway is on the same host as the workers, so it always
        # connects via loopback regardless of what the worker advertises.
        worker_endpoint = (
            f"opc.tcp://127.0.0.1:{ev.port}/{ev.simulation_id}/"
        )

        mirror = WorkerMirror(
            session_id=ev.session_id,
            simulation_id=ev.simulation_id,
            worker_endpoint=worker_endpoint,
            parent_folder=self._sessions_folder,
            namespace_idx=self._namespace_idx,
            server=self._server,
            enqueue_write=self._enqueue_write,
        )

        try:
            await mirror.connect_and_mirror()
        except SimulationRootNotFound as exc:
            log.error("worker has no discoverable simulation root",
                      extra={"session_id": ev.session_id, "error": str(exc)})
            return
        except Exception:
            log.exception("failed to mirror worker",
                          extra={"session_id": ev.session_id})
            return

        async with self._mirrors_lock:
            self._mirrors[ev.session_id] = mirror
        log.info("mirror added", extra={"session_id": ev.session_id})

    async def _remove_mirror(self, session_id: str) -> None:
        async with self._mirrors_lock:
            mirror = self._mirrors.pop(session_id, None)
        if mirror is None:
            return
        try:
            await mirror.disconnect()
        except Exception:
            log.exception("error disconnecting mirror",
                          extra={"session_id": session_id})
        log.info("mirror removed", extra={"session_id": session_id})

    # --- write forwarding ---

    def _enqueue_write(
        self, session_id: str, command_name: str, value: Any
    ) -> None:
        self._write_queue.put_nowait((session_id, command_name, value))

    async def _drain_writes(self) -> None:
        while True:
            session_id, command_name, value = await self._write_queue.get()
            mirror = self._mirrors.get(session_id)
            if mirror is None:
                continue
            try:
                await mirror.forward_command(command_name, value)
            except Exception:
                log.exception(
                    "command forward failed",
                    extra={"session_id": session_id, "command": command_name},
                )
```

### `shared/constants.py`

```python
"""Cross-cutting constants shared by the control plane and worker pool.

Anything that must match on both sides of the Redis boundary belongs here,
not scattered across modules. Values are read from the environment at import
time so systemd's EnvironmentFile is the single source of configuration.
"""

from __future__ import annotations

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


# --- Loop rates (Hz) -------------------------------------------------------
PHYSICS_HZ: Final[int] = _int_env("PHYSICS_HZ", 10)
UI_BROADCAST_HZ: Final[int] = _int_env("UI_BROADCAST_HZ", 4)


# --- systemd integration ---------------------------------------------------
SYSTEMD_UNIT_PREFIX: Final[str] = "cip-worker-"
PID_DIR: Final[str] = "/var/lib/cip-sim/pids"


# --- Gateway ---------------------------------------------------------------
GATEWAY_OPCUA_PORT: Final[int] = _int_env("GATEWAY_OPCUA_PORT", 8080)
GATEWAY_EVT_CONSUMER_GROUP: Final[str] = "gateway"
```

### `shared/logging.py`

```python
"""Structured JSON logging shared by Django and the worker pool.

One format means one parser, one filter set, and one way to correlate log
lines across processes by session_id.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per record, newline-delimited.

    JSON over logfmt or plain text: it parses unambiguously, handles nested
    fields, and every log aggregator expects it by default.
    """

    _CONTEXT_KEYS = ("session_id", "simulation_id", "pid", "port", "request_id")

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
                  + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in self._CONTEXT_KEYS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger. Call once per process."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # asyncua logs per-message at INFO on some transports. At 10 Hz per
    # session, that is unusable noise in the logs.
    logging.getLogger("asyncua").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str, **context: Any) -> logging.LoggerAdapter:
    """Return a logger that stamps the given context on every record.

        log = get_logger(__name__, session_id=sid)
        log.info("worker started")   # -> {"session_id": sid, ...}
    """
    return logging.LoggerAdapter(logging.getLogger(name), context)
```

### `shared/schemas.py`

```python
"""Message schemas for the Redis Streams boundary.

Every command and every event is one of these models. Django and the daemon
import the same definitions, so a change on one side that isn't mirrored on
the other fails at deserialization with a clear error.

Base models use extra="forbid" so undeclared fields raise at construction
time rather than being silently dropped. This catches drift between
producers and consumers immediately.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator


def _now() -> datetime:
    return datetime.now(timezone.utc)


class _StrictBase(BaseModel):
    """Base for all messages. Rejects undeclared fields loudly."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Commands: Django -> Worker Pool
# ---------------------------------------------------------------------------

class _CommandBase(_StrictBase):
    request_id: str = Field(description="Echoed back in the resulting event.")
    issued_at: datetime = Field(default_factory=_now)


class StartSessionCommand(_CommandBase):
    kind: Literal["start_session"] = "start_session"
    session_id: str
    simulation_id: str
    config_params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("session_id", "simulation_id")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or len(v) > 128:
            raise ValueError("must be 1-128 chars")
        return v


class StopSessionCommand(_CommandBase):
    kind: Literal["stop_session"] = "stop_session"
    session_id: str
    reason: Literal["user_request", "idle_timeout", "admin_action"] = "user_request"


class PingCommand(_CommandBase):
    kind: Literal["ping"] = "ping"


# ---------------------------------------------------------------------------
# Events: Worker Pool -> Django
# ---------------------------------------------------------------------------

class _EventBase(_StrictBase):
    occurred_at: datetime = Field(default_factory=_now)


class SessionStartedEvent(_EventBase):
    """Emitted by the daemon when a worker process is spawned."""

    kind: Literal["session_started"] = "session_started"
    session_id: str
    simulation_id: str
    port: int
    pid: int
    systemd_unit: str
    advertised_endpoint: str
    request_id: str | None = None


class SessionReadyEvent(_EventBase):
    """Emitted by the worker itself once its OPC UA port is bound."""

    kind: Literal["session_ready"] = "session_ready"
    session_id: str
    simulation_id: str
    port: int
    pid: int


class SessionStoppedEvent(_EventBase):
    kind: Literal["session_stopped"] = "session_stopped"
    session_id: str
    exit_code: int | None = None
    reason: str = "user_request"


class SessionFailedEvent(_EventBase):
    kind: Literal["session_failed"] = "session_failed"
    session_id: str
    error: str


# ---------------------------------------------------------------------------
# Discriminated unions + parsers
# ---------------------------------------------------------------------------

Command = Annotated[
    Union[StartSessionCommand, StopSessionCommand, PingCommand],
    Field(discriminator="kind"),
]

Event = Annotated[
    Union[
        SessionStartedEvent,
        SessionReadyEvent,
        SessionStoppedEvent,
        SessionFailedEvent,
    ],
    Field(discriminator="kind"),
]

_COMMAND_ADAPTER: TypeAdapter[Command] = TypeAdapter(Command)
_EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)


def parse_command(raw: bytes | str) -> Command:
    return _COMMAND_ADAPTER.validate_json(raw)


def parse_event(raw: bytes | str) -> Event:
    return _EVENT_ADAPTER.validate_json(raw)
```

### `sim_plugins/__init__.py`

```python

```

### `sim_plugins/blinker/__init__.py`

```python

```

### `sim_plugins/blinker/body.html`

```html
<div class="card">
  <h2>Blinker state</h2>
  <div class="kv"><span class="k">State</span><span class="v" id="s-state">--</span></div>
  <div class="kv"><span class="k">On</span><span class="v" id="s-on">--</span></div>
  <div class="kv"><span class="k">Phase</span><span class="v" id="s-phase">--</span></div>
  <div class="kv"><span class="k">Blink count</span><span class="v" id="s-count">--</span></div>
</div>

<div class="card">
  <h2>Light</h2>
  <div id="light" style="width:100px;height:100px;border-radius:50%;
       background:#cfd8dc;border:2px solid #90a4ae;margin:0 auto;
       transition:background .12s;"></div>
</div>
```

### `sim_plugins/blinker/simulation.py`

```python
"""Blinker: the minimal plugin. Proves the contract.

A light that blinks on a configurable period. No physics, no state beyond
a phase counter and a cycle count. Its entire job is to be the simplest
possible plugin, so any awkwardness in BaseSimulation surfaces here rather
than inside CIP.
"""

from __future__ import annotations

from typing import Any

from sim_runtime.base import (
    BaseSimulation,
    CommandSpec,
    MeasurementSpec,
    SimulationConfig,
    StatusSpec,
)


class Blinker(BaseSimulation):
    SIMULATION_ID = "blinker"
    SIMULATION_NAME = "Blinking Light"
    SIMULATION_VERSION = "1.0.0"

    def __init__(self, config: SimulationConfig) -> None:
        self._enabled = bool(config.params.get("enabled", False))
        self._period = float(config.params.get("period_seconds", 1.0))
        self._phase = 0.0
        self._blink_count = 0

    # -- schema -----------------------------------------------------------

    @classmethod
    def commands(cls) -> dict[str, CommandSpec]:
        return {
            "Enabled": CommandSpec(
                name="Enabled",
                type="bool",
                description="Start or stop the blink.",
                default=False,
            ),
            "PeriodSeconds": CommandSpec(
                name="PeriodSeconds",
                type="float",
                description="Blink period in seconds.",
                min=0.1,
                max=10.0,
                default=1.0,
            ),
            "ResetCountCmd": CommandSpec(
                name="ResetCountCmd",
                type="bool",
                description="Pulse to reset the blink counter to zero.",
                pulse=True,
                default=False,
            ),
        }

    @classmethod
    def measurements(cls) -> dict[str, MeasurementSpec]:
        return {
            "On": MeasurementSpec(
                name="On",
                type="bool",
                unit="",
                description="True while the light is in the on phase.",
            ),
            "Phase": MeasurementSpec(
                name="Phase",
                type="float",
                unit="s",
                description="Position within the current blink period.",
            ),
        }

    @classmethod
    def status(cls) -> dict[str, StatusSpec]:
        return {
            "State": StatusSpec(
                name="State",
                type="string",
                description="Human-readable state: Off, On, or Idle.",
            ),
            "BlinkCount": StatusSpec(
                name="BlinkCount",
                type="uint16",
                description="Completed blink cycles since the last reset.",
            ),
        }

    # -- physics ----------------------------------------------------------

    def step(self, dt: float) -> None:
        if not self._enabled:
            return

        self._phase += dt

        # A while loop rather than a single subtraction so a large dt
        # cannot silently swallow periods. At PHYSICS_HZ this never loops
        # more than once, but it costs nothing to be correct.
        while self._phase >= self._period:
            self._phase -= self._period
            self._blink_count += 1

    # -- observation ------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        on = self._enabled and self._phase < self._period / 2
        state = "On" if on else ("Off" if self._enabled else "Idle")
        return {
            "measurements": {
                "On": on,
                "Phase": round(self._phase, 3) if self._enabled else 0.0,
            },
            "status": {
                "State": state,
                # uint16 range guard so the OPC UA write never overflows.
                "BlinkCount": min(self._blink_count, 65535),
            },
        }

    # -- commands ---------------------------------------------------------

    def write_command(self, name: str, value: Any) -> None:
        if name == "Enabled":
            self._enabled = bool(value)
            if not self._enabled:
                self._phase = 0.0
            return

        if name == "PeriodSeconds":
            self._period = float(value)
            return

        if name == "ResetCountCmd":
            # The adapter treats pulse commands as True-then-cleared, so
            # we only act when the value is truthy.
            if value:
                self._blink_count = 0
                self._phase = 0.0
            return

        raise ValueError(f"Unknown command: {name}")
```

### `sim_plugins/blinker/ui.js`

```javascript
/* Blinker dashboard renderer. Called by the shell on every poll.
 *
 * Reads measurements.On, measurements.Phase, status.State, and
 * status.BlinkCount. Nothing else. No physics, no guessing.
 */
window.renderState = function (state) {
  'use strict';

  var m = state.measurements || {};
  var s = state.status || {};

  var stateEl = document.getElementById('s-state');
  if (stateEl) stateEl.textContent = s.State != null ? s.State : '--';

  var onEl = document.getElementById('s-on');
  if (onEl) onEl.textContent = m.On ? 'yes' : 'no';

  var phaseEl = document.getElementById('s-phase');
  if (phaseEl) {
    phaseEl.textContent =
      (typeof m.Phase === 'number' ? m.Phase.toFixed(2) : '0.00') + ' s';
  }

  var countEl = document.getElementById('s-count');
  if (countEl) countEl.textContent = s.BlinkCount != null ? s.BlinkCount : 0;

  var light = document.getElementById('light');
  if (light) {
    light.style.background = m.On ? '#f5c518' : '#cfd8dc';
  }
};
```

### `sim_plugins/cip/__init__.py`

```python

```

### `sim_plugins/cip/body.html`

```html
<style>
  /* Wide card for the diagram + metrics + trends row */
  .cip-wide { grid-column: 1 / -1; }

  .diagram-wrap svg { width: 100%; height: auto; display: block; }

  /* Pipes */
  .pipe { fill: none; stroke: #b7c0cc; stroke-width: 8;
          stroke-linecap: round; stroke-linejoin: round; }
  .pipe.flow { stroke-dasharray: 11 13; animation: cip-dash 0.7s linear infinite; }
  .pipe.flow.water   { stroke: #1e88e5; }
  .pipe.flow.caustic { stroke: #fb8c00; }
  .pipe.flow.acid    { stroke: #d81b8c; }
  .pipe.flow.mixture { stroke: #7e57c2; }
  @keyframes cip-dash { to { stroke-dashoffset: -24; } }

  .arrow { fill: #64748b; }
  .equip { fill: #cbd5e1; stroke: #64748b; stroke-width: 2; }
  .equip-label { fill: #1f2933; font-size: 15px; font-weight: 600; }
  .equip-sub { fill: #52606d; font-size: 12.5px; }
  .valve-label { fill: #52606d; font-size: 13px; }
  .tick-label { fill: #7b8794; font-size: 12px; }

  .valve { fill: #ffffff; stroke: #64748b; stroke-width: 2; }
  .valve.cmd { fill: #d97706; stroke: #a8620a; }
  .valve.flow { fill: #2e9e6b; stroke: #1c6a47; }

  .pump-run { fill: #2e9e6b; stroke: #1c6a47; stroke-width: 2; }
  .tank-bg { fill: #ffffff; }
  .tank-outline { fill: none; stroke: #64748b; stroke-width: 2.5; }
  .chip-bg { fill: #ffffff; opacity: .82; }
  .chip-text { fill: #1f2933; font-size: 14px; font-weight: 600; }

  .heater-off { fill: #cbd5e1; stroke: #64748b; stroke-width: 2; }
  .heater-on  { fill: #ffd8a8; stroke: #d97706; stroke-width: 2.5; }

  /* Metric tiles */
  .cip-metrics { display: grid; grid-template-columns: repeat(4, 1fr);
                 gap: 10px; margin-top: 12px; }
  @media (max-width: 720px) { .cip-metrics { grid-template-columns: repeat(2, 1fr); } }
  .cip-tile { background: #f7f9fb; border: 1px solid #d3dae2;
              border-radius: 8px; padding: 9px 11px; }
  .cip-tile .k { font-size: 11px; color: #7b8794;
                 text-transform: uppercase; letter-spacing: .4px; }
  .cip-tile .v { font-size: 22px; font-weight: 650;
                 font-variant-numeric: tabular-nums; margin-top: 2px; }
  .cip-tile .u { font-size: 12px; color: #7b8794; font-weight: 500; }

  /* Trends */
  .cip-trends { display: grid; grid-template-columns: 1fr 1fr;
                gap: 10px; margin-top: 10px; }
  @media (max-width: 620px) { .cip-trends { grid-template-columns: 1fr; } }
  .cip-trend { background: #f7f9fb; border: 1px solid #d3dae2;
               border-radius: 8px; padding: 8px 10px; }
  .cip-trend .t-head { display: flex; justify-content: space-between;
                       font-size: 11px; color: #7b8794; }
  .cip-trend .t-axis { display: flex; justify-content: space-between;
                       font-size: 10.5px; color: #7b8794; margin-top: 2px; }
  .cip-trend canvas { width: 100%; height: 46px; display: block; margin-top: 2px; }

  /* Pills + badges */
  .pill-row { display: flex; flex-wrap: wrap; gap: 6px; }
  .badge { font-size: 11px; font-weight: 600; padding: 2px 7px;
           border-radius: 999px; border: 1px solid #d3dae2;
           background: #f7f9fb; color: #52606d; }
  .badge.cmd { background: #fff3e0; border-color: #f2ce9a; color: #9a5a06; }

  /* Fault list */
  .alarm-none { color: #2e9e6b; font-weight: 600; }
  .alarm-item { display: flex; align-items: baseline; gap: 8px;
                padding: 5px 0; border-bottom: 1px dashed #d3dae2; }
  .alarm-item:last-child { border-bottom: 0; }
  .alarm-item .bit { font-size: 11px; font-weight: 700; color: #fff;
                     background: #e02424; border-radius: 5px;
                     padding: 1px 6px; flex: none;
                     font-variant-numeric: tabular-nums; }
  .alarm-item .txt { color: #7a1414; }

  /* Heat panel */
  .heat-line { display: flex; justify-content: space-between; padding: 3px 0; }
</style>

<section class="card cip-wide">
  <h2>Process</h2>
  <div class="diagram-wrap">
    <svg viewBox="0 62 960 456" role="img" aria-label="CIP process diagram">
      <path id="p-water"   class="pipe" d="M780 96 H450 V180"></path>
      <path id="p-acid"    class="pipe" d="M780 152 H505 V180"></path>
      <path id="p-caustic" class="pipe" d="M865 315 V232 H560"></path>
      <path id="p-suction" class="pipe" d="M480 430 V456 H358"></path>
      <path id="p-common"  class="pipe" d="M302 456 H230"></path>
      <path id="p-return"  class="pipe" d="M230 456 V300 H120"></path>
      <path id="p-drain"   class="pipe" d="M230 456 H120"></path>

      <polygon class="arrow" points="444,168 456,168 450,180"></polygon>
      <polygon class="arrow" points="499,168 511,168 505,180"></polygon>
      <polygon class="arrow" points="572,226 572,238 560,232"></polygon>
      <polygon class="arrow" points="372,450 372,462 360,456"></polygon>
      <polygon class="arrow" points="224,312 236,312 230,300"></polygon>
      <polygon class="arrow" points="132,450 132,462 120,456"></polygon>

      <!-- Tank -->
      <rect class="tank-bg" x="400" y="180" width="160" height="250" rx="8"></rect>
      <clipPath id="tankClip">
        <rect x="404" y="186" width="152" height="238" rx="5"></rect>
      </clipPath>
      <rect id="liquid" x="404" y="424" width="152" height="0"
            fill="#cbd5e1" clip-path="url(#tankClip)"></rect>
      <rect class="tank-outline" x="400" y="180" width="160" height="250" rx="8"></rect>
      <rect class="chip-bg" x="428" y="196" width="104" height="24" rx="6"></rect>
      <text class="chip-text" id="liquid-name" x="480" y="213"
            text-anchor="middle">Empty</text>

      <line x1="560" y1="186" x2="568" y2="186" stroke="#64748b"></line>
      <text class="tick-label" x="572" y="190">100</text>
      <line x1="560" y1="305" x2="568" y2="305" stroke="#64748b"></line>
      <text class="tick-label" x="572" y="309">50</text>
      <line x1="560" y1="424" x2="568" y2="424" stroke="#64748b"></line>
      <text class="tick-label" x="572" y="428">0 %</text>

      <!-- Supplies -->
      <rect class="equip" x="780" y="74" width="150" height="44" rx="10"></rect>
      <text class="equip-label" x="855" y="102" text-anchor="middle">Water supply</text>
      <rect class="equip" x="780" y="130" width="150" height="44" rx="10"></rect>
      <text class="equip-label" x="855" y="158" text-anchor="middle">Acid supply</text>

      <rect x="758" y="288" width="192" height="158" rx="12"
            fill="#fff8f0" stroke="#f2ddc0"></rect>
      <text class="equip-sub" x="854" y="308" text-anchor="middle"
            style="font-weight:600;fill:#9a5a06">Caustic tank + heater</text>
      <rect class="tank-bg" x="822" y="318" width="86" height="104" rx="6"></rect>
      <rect class="tank-outline" x="822" y="318" width="86" height="104" rx="6"></rect>
      <text class="equip-label" x="865" y="360" text-anchor="middle"
            style="font-size:13px">Caustic</text>
      <rect id="heater" class="heater-off" x="770" y="352" width="42" height="34" rx="6"></rect>
      <text class="valve-label" x="791" y="402" text-anchor="middle">Heater</text>
      <text class="equip-sub" id="caustic-temp" x="865" y="410"
            text-anchor="middle">20.0 °C</text>

      <!-- Valves -->
      <polygon id="v-water"   class="valve" points="620,86 632,96 620,106 608,96"></polygon>
      <text class="valve-label" x="620" y="80" text-anchor="middle">Water valve</text>
      <polygon id="v-acid"    class="valve" points="620,142 632,152 620,162 608,152"></polygon>
      <text class="valve-label" x="620" y="136" text-anchor="middle">Acid valve</text>
      <polygon id="v-caustic" class="valve" points="700,222 712,232 700,242 688,232"></polygon>
      <text class="valve-label" x="700" y="216" text-anchor="middle">Caustic valve</text>

      <!-- Pump -->
      <circle id="pump" class="equip" cx="330" cy="456" r="28"></circle>
      <path d="M318 456 L342 442 L342 470 Z" fill="#ffffff"
            stroke="#64748b" stroke-width="1.5"></path>
      <text class="valve-label" x="330" y="500" text-anchor="middle">Pump</text>

      <!-- Return / recovery -->
      <polygon id="v-return" class="valve" points="230,368 242,378 230,388 218,378"></polygon>
      <text class="valve-label" x="248" y="382" text-anchor="start">Return valve</text>
      <rect class="equip" x="40" y="282" width="80" height="40" rx="10"></rect>
      <text class="equip-sub" x="80" y="299" text-anchor="middle"
            style="font-weight:600">Chemical</text>
      <text class="equip-sub" x="80" y="314" text-anchor="middle">recovery</text>

      <!-- Drain -->
      <polygon id="v-drain" class="valve" points="185,446 197,456 185,466 173,456"></polygon>
      <text class="valve-label" x="185" y="440" text-anchor="middle">Drain valve</text>
      <rect class="equip" x="40" y="440" width="80" height="34" rx="8"></rect>
      <text class="equip-sub" x="80" y="461" text-anchor="middle">Drain / sewer</text>
    </svg>
  </div>

  <div class="cip-metrics">
    <div class="cip-tile">
      <div class="k">Level</div>
      <div class="v"><span id="m-level">0.0</span><span class="u"> %</span></div>
    </div>
    <div class="cip-tile">
      <div class="k">Flow (pump)</div>
      <div class="v"><span id="m-flow">0.0</span><span class="u"> L/min</span></div>
    </div>
    <div class="cip-tile">
      <div class="k">Process temp.</div>
      <div class="v"><span id="m-temp">20.0</span><span class="u"> °C</span></div>
    </div>
    <div class="cip-tile">
      <div class="k">Conductivity</div>
      <div class="v"><span id="m-cond">0.0</span><span class="u"> su</span></div>
    </div>
  </div>

  <div class="cip-trends">
    <div class="cip-trend">
      <div class="t-head"><span>Level</span><span id="tr-level-v">0.0 %</span></div>
      <canvas id="tr-level" width="300" height="46"></canvas>
      <div class="t-axis"><span>0–100 %</span><span>← ~90 s</span></div>
    </div>
    <div class="cip-trend">
      <div class="t-head"><span>Process temp.</span><span id="tr-temp-v">20.0 °C</span></div>
      <canvas id="tr-temp" width="300" height="46"></canvas>
      <div class="t-axis"><span>10–90 °C</span><span>← ~90 s</span></div>
    </div>
  </div>
</section>

<section class="card">
  <h2>Actual state</h2>
  <div class="kv"><span class="k">Pump</span><span class="v" id="s-pump">--</span></div>
  <div class="kv"><span class="k">Action</span><span class="v" id="s-action">Idle</span></div>
  <div class="kv"><span class="k">Liquid</span><span class="v" id="s-liquid">Empty</span></div>
  <div class="kv"><span class="k">Level</span><span class="v" id="s-level">0.0 %</span></div>
  <div class="kv"><span class="k">Flow route</span><span class="v" id="s-route">Closed</span></div>
</section>

<section class="card">
  <h2>Caustic tank &amp; heating</h2>
  <div class="heat-line"><span class="k">Heater command</span><span class="v" id="h-cmd">Off</span></div>
  <div class="heat-line"><span class="k">Caustic tank temp.</span><span class="v" id="h-temp">20.0 °C</span></div>
  <div class="heat-line"><span class="k">Temp. setpoint</span><span class="v" id="h-sp">45.0 °C</span></div>
</section>

<section class="card">
  <h2>Commands</h2>
  <div class="pill-row" id="command-pills"></div>
</section>

<section class="card">
  <h2>Alarms / faults</h2>
  <div id="faults"></div>
</section>
```

### `sim_plugins/cip/simulation.py`

```python
"""CIP process simulation.

Refactored from the original standalone simulator to conform to
BaseSimulation. The physics in _tick_locked is unchanged. What changed:

- Commands and measurements are declared as named schema entries instead
  of Modbus-shaped holding/input registers.
- Snapshot returns {"measurements": {...}, "status": {...}} as the plugin
  contract requires.
- Read-only UI hints (branch flows, pipe states) are exposed as status
  booleans. The dashboard never guesses physics.
- ResetFaultCmd is a pulse command. The adapter handles clear-on-next-tick;
  the plugin applies the reset immediately when write_command is called.

The internal lock protects all mutable state. step() and snapshot() may be
called from different threads (asyncio loop and HTTP thread respectively),
so every public method takes the lock.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from sim_runtime.base import (
    BaseSimulation,
    CommandSpec,
    MeasurementSpec,
    SimulationConfig,
    StatusSpec,
)


class CIPSimulation(BaseSimulation):
    SIMULATION_ID = "cip"
    SIMULATION_NAME = "Clean-In-Place"
    SIMULATION_VERSION = "2.0.0"

    # --- schema ---

    @classmethod
    def commands(cls) -> dict[str, CommandSpec]:
        return {
            "PumpCmd": CommandSpec(
                name="PumpCmd", type="bool",
                description="Run the circulation pump.",
            ),
            "WaterValveCmd": CommandSpec(
                name="WaterValveCmd", type="bool",
                description="Open the water supply valve.",
            ),
            "CausticValveCmd": CommandSpec(
                name="CausticValveCmd", type="bool",
                description="Open the caustic supply valve.",
            ),
            "AcidValveCmd": CommandSpec(
                name="AcidValveCmd", type="bool",
                description="Open the acid supply valve.",
            ),
            "ReturnValveCmd": CommandSpec(
                name="ReturnValveCmd", type="bool",
                description="Open the return (recovery) valve.",
            ),
            "DrainValveCmd": CommandSpec(
                name="DrainValveCmd", type="bool",
                description="Open the drain valve.",
            ),
            "HeaterCmd": CommandSpec(
                name="HeaterCmd", type="bool",
                description="Run the caustic tank heater.",
            ),
            "ResetFaultCmd": CommandSpec(
                name="ResetFaultCmd", type="bool",
                description="Pulse to clear the active fault word.",
                pulse=True,
            ),
            "CausticTempSetpointC": CommandSpec(
                name="CausticTempSetpointC", type="float",
                description="Caustic tank temperature setpoint.",
                min=20.0, max=80.0, default=45.0,
            ),
        }

    @classmethod
    def measurements(cls) -> dict[str, MeasurementSpec]:
        return {
            "LevelPercent": MeasurementSpec(
                name="LevelPercent", type="float", unit="%",
                description="Wash tank fill level.",
            ),
            "VolumeLiters": MeasurementSpec(
                name="VolumeLiters", type="float", unit="L",
                description="Total liquid volume in the tank.",
            ),
            "FlowLpm": MeasurementSpec(
                name="FlowLpm", type="float", unit="L/min",
                description="Current circulation or drain flow.",
            ),
            "TemperatureC": MeasurementSpec(
                name="TemperatureC", type="float", unit="deg C",
                description="Process loop temperature.",
            ),
            "Conductivity": MeasurementSpec(
                name="Conductivity", type="float", unit="sim units",
                description="Simulated conductivity (proxy for chemistry).",
            ),
            "CausticTankTempC": MeasurementSpec(
                name="CausticTankTempC", type="float", unit="deg C",
                description="Caustic supply tank temperature.",
            ),
        }

    @classmethod
    def status(cls) -> dict[str, StatusSpec]:
        specs = {
            "LiquidCode": StatusSpec("LiquidCode", "uint16",
                "0=Empty, 1=Water, 2=Caustic, 3=Acid, 4=Mixture."),
            "LiquidName": StatusSpec("LiquidName", "string",
                "Human-readable liquid name."),
            "RouteCode": StatusSpec("RouteCode", "uint16",
                "0=Closed, 1=Return, 2=Drain, 3=Return+Drain."),
            "RouteName": StatusSpec("RouteName", "string",
                "Human-readable route name."),
            "FaultWord": StatusSpec("FaultWord", "uint16",
                "Active faults as a bitfield."),
            "StatusWord": StatusSpec("StatusWord", "uint16",
                "Process status bits."),
            "SequenceHint": StatusSpec("SequenceHint", "string",
                "Best-guess name of the current sequence."),
        }
        # Branch flow flags consumed by the dashboard to animate pipes.
        # Exposing these keeps the physics on the server; the UI never
        # recomputes what it thinks should be flowing.
        for branch in (
            "waterInlet", "causticInlet", "acidInlet",
            "pumpRunning", "returnFlow", "drainFlow",
            "gravityDrain", "drainBlocked", "chemicalRecovery",
        ):
            specs[branch] = StatusSpec(branch, "bool",
                f"UI hint: {branch} is active.")
        return specs

    # --- lifecycle ---

    def __init__(self, config: SimulationConfig) -> None:
        self._lock = threading.Lock()

        # Commands (kept as plain attributes; the lock is the sync point)
        self._pump = False
        self._water_valve = False
        self._caustic_valve = False
        self._acid_valve = False
        self._return_valve = False
        self._drain_valve = False
        self._heater = False
        self._setpoint_c = 45.0

        # Physics state
        self._ambient_temp = 20.0
        self._water_supply_temp_c = 20.0
        self._temperature_c = 20.0
        self._caustic_tank_temp_c = 20.0
        self._water_l = 0.0
        self._caustic_l = 0.0
        self._acid_l = 0.0
        self._flow_lpm = 0.0
        self._conductivity = 0.0
        self._liquid_code = 0
        self._fault_word = 0
        self._status_word = 0
        self._route_code = 0
        self._sequence_hint = "Idle"

        # Optional initial state from config
        params = config.params or {}
        self._water_l = float(params.get("initial_water_l", 0.0))
        self._caustic_l = float(params.get("initial_caustic_l", 0.0))
        self._acid_l = float(params.get("initial_acid_l", 0.0))
        self._temperature_c = float(params.get("initial_temperature_c", 20.0))

        self._last_tick = time.monotonic()
        self._start_time = self._last_tick
        self._branches: dict[str, bool] = {}

    # --- step and snapshot ---

    def step(self, dt: float) -> None:
        with self._lock:
            self._tick_locked()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            total = self._total_volume()
            fractions = self._fractions_locked()
            return {
                "measurements": {
                    "LevelPercent": round(total, 1),
                    "VolumeLiters": round(total, 1),
                    "FlowLpm": round(self._flow_lpm, 1),
                    "TemperatureC": round(self._temperature_c, 1),
                    "Conductivity": round(self._conductivity, 1),
                    "CausticTankTempC": round(self._caustic_tank_temp_c, 1),
                },
                "status": {
                    "LiquidCode": self._liquid_code,
                    "LiquidName": self._liquid_name(self._liquid_code),
                    "RouteCode": self._route_code,
                    "RouteName": self._route_name(self._route_code),
                    "FaultWord": self._fault_word,
                    "StatusWord": self._status_word,
                    "SequenceHint": self._sequence_hint,
                    **{k: bool(v) for k, v in self._branches.items()},
                },
            }

    # --- command dispatch ---

    def write_command(self, name: str, value: Any) -> None:
        with self._lock:
            if name == "PumpCmd":
                self._pump = bool(value)
            elif name == "WaterValveCmd":
                self._water_valve = bool(value)
            elif name == "CausticValveCmd":
                self._caustic_valve = bool(value)
            elif name == "AcidValveCmd":
                self._acid_valve = bool(value)
            elif name == "ReturnValveCmd":
                self._return_valve = bool(value)
            elif name == "DrainValveCmd":
                self._drain_valve = bool(value)
            elif name == "HeaterCmd":
                self._heater = bool(value)
            elif name == "CausticTempSetpointC":
                self._setpoint_c = float(value)
            elif name == "ResetFaultCmd":
                if value:
                    self._fault_word = 0
            else:
                raise ValueError(f"Unknown command: {name}")
            # Advance so the effect is visible in the next snapshot even
            # if step() hasn't fired yet.
            self._tick_locked()

    # --- physics (unchanged from original, just renamed internals) ---

    def _tick_locked(self) -> None:
        now = time.monotonic()
        dt = min(max(now - self._last_tick, 0.0), 1.0)
        if dt <= 0.0:
            return
        self._last_tick = now

        caustic_temp_setpoint_c = max(20.0, min(self._setpoint_c, 80.0))
        pump_cmd = self._pump
        water_cmd = self._water_valve
        caustic_cmd = self._caustic_valve
        acid_cmd = self._acid_valve
        return_cmd = self._return_valve
        drain_cmd = self._drain_valve
        heater_cmd = self._heater
        source_count = sum((water_cmd, caustic_cmd, acid_cmd))
        total_before = self._total_volume()

        fractions = self._fractions_locked()
        conductivity_preview = (
            0.0
            if total_before < 0.05
            else 0.5 * fractions["water"]
                 + 220.0 * fractions["caustic"]
                 + 160.0 * fractions["acid"]
        )
        chemical_in_tank = conductivity_preview >= 25.0

        fault_word = 0
        if pump_cmd and total_before < 1.0 and source_count == 0:
            fault_word |= 1 << 0
        if pump_cmd and not return_cmd and not drain_cmd:
            fault_word |= 1 << 1
        if source_count > 1:
            fault_word |= 1 << 2
        if self._temperature_c > 85.0:
            fault_word |= 1 << 3
        if drain_cmd and chemical_in_tank:
            fault_word |= 1 << 4
        self._fault_word = fault_word

        blocked = self._fault_word != 0
        pump_running = pump_cmd and not blocked
        inlet_boost = 1.5 if pump_running else 1.0

        if not blocked and source_count == 1:
            if water_cmd:
                self._water_l += 5.0 * inlet_boost * dt
            elif caustic_cmd:
                self._caustic_l += 2.5 * inlet_boost * dt
            elif acid_cmd:
                self._acid_l += 2.5 * inlet_boost * dt

        self._cap_volume_locked(100.0)
        self._route_code = (
            3 if return_cmd and drain_cmd
            else 1 if return_cmd
            else 2 if drain_cmd
            else 0
        )

        if heater_cmd and not blocked:
            heat_target = min(80.0, max(caustic_temp_setpoint_c + 5.0, 35.0))
            self._caustic_tank_temp_c += (
                (heat_target - self._caustic_tank_temp_c) * 0.22 * dt
            )
        else:
            self._caustic_tank_temp_c += (
                (self._ambient_temp - self._caustic_tank_temp_c) * 0.05 * dt
            )
        self._caustic_tank_temp_c = min(
            max(self._caustic_tank_temp_c, 15.0), 90.0
        )

        total = self._total_volume()
        fractions = self._fractions_locked()
        dominant_name = (
            max(fractions, key=fractions.get) if total > 0.0 else "water"
        )
        is_chemical_recovery = (
            return_cmd and pump_running and total > 0.5
            and dominant_name in ("caustic", "acid")
        )
        drain_blocked_by_chemicals = drain_cmd and chemical_in_tank

        if drain_cmd and not drain_blocked_by_chemicals:
            drain_rate = (
                7.0 if pump_running and not return_cmd
                else 2.5 if pump_running
                else 1.5
            )
            self._remove_volume_locked(drain_rate * dt)
        elif is_chemical_recovery:
            self._remove_volume_locked(6.0 * dt)

        total = self._total_volume()
        route_open = return_cmd or drain_cmd
        medium_available = total > 0.5 or source_count > 0
        if pump_running and route_open and medium_available:
            if return_cmd and drain_cmd:
                self._flow_lpm = 14.0
            elif is_chemical_recovery:
                self._flow_lpm = 11.0
            elif drain_blocked_by_chemicals:
                self._flow_lpm = 0.0
            elif drain_cmd:
                self._flow_lpm = 10.0
            else:
                self._flow_lpm = 12.0
        else:
            self._flow_lpm = 0.0

        source_temp = self._ambient_temp
        mix_gain = 0.10
        if water_cmd:
            source_temp = self._water_supply_temp_c
            mix_gain = 0.30
        elif caustic_cmd:
            source_temp = self._caustic_tank_temp_c
            mix_gain = 0.24
        elif acid_cmd:
            source_temp = self._ambient_temp
            mix_gain = 0.24
        elif pump_running and return_cmd:
            source_temp = self._temperature_c
            mix_gain = 0.02
        self._temperature_c += (
            (source_temp - self._temperature_c) * mix_gain * dt
        )
        self._temperature_c += (
            (self._ambient_temp - self._temperature_c) * 0.03 * dt
        )
        self._temperature_c = min(max(self._temperature_c, 15.0), 90.0)

        fractions = self._fractions_locked()
        self._conductivity = (
            0.0
            if total < 0.05
            else 0.5 * fractions["water"]
                 + 220.0 * fractions["caustic"]
                 + 160.0 * fractions["acid"]
        )
        self._liquid_code = self._compute_liquid_code_locked(fractions, total)
        self._sequence_hint = self._infer_sequence_hint_locked()

        status_word = 0
        if pump_running:
            status_word |= 1 << 0
        if source_count > 0:
            status_word |= 1 << 1
        if return_cmd:
            status_word |= 1 << 2
        if drain_cmd:
            status_word |= 1 << 3
        if self._flow_lpm > 0.1:
            status_word |= 1 << 4
        if heater_cmd and not blocked:
            status_word |= 1 << 5
        if total > 0.5:
            status_word |= 1 << 6
        if self._fault_word != 0:
            status_word |= 1 << 7
        self._status_word = status_word

        self._branches = {
            "waterInlet": bool(water_cmd and source_count == 1 and not blocked),
            "causticInlet": bool(caustic_cmd and source_count == 1 and not blocked),
            "acidInlet": bool(acid_cmd and source_count == 1 and not blocked),
            "pumpRunning": bool(pump_running),
            "returnFlow": bool(return_cmd and pump_running and self._flow_lpm > 0.1),
            "drainFlow": bool(
                drain_cmd and pump_running and self._flow_lpm > 0.1
                and not drain_blocked_by_chemicals
            ),
            "gravityDrain": bool(
                drain_cmd and (not pump_running)
                and (not drain_blocked_by_chemicals) and total > 0.5
            ),
            "drainBlocked": bool(drain_blocked_by_chemicals),
            "chemicalRecovery": bool(is_chemical_recovery),
        }

    # --- helpers (unchanged) ---

    def _fractions_locked(self) -> dict[str, float]:
        total = self._total_volume()
        if total <= 0.0:
            return {"water": 0.0, "caustic": 0.0, "acid": 0.0}
        return {
            "water": self._water_l / total,
            "caustic": self._caustic_l / total,
            "acid": self._acid_l / total,
        }

    def _compute_liquid_code_locked(
        self, fractions: dict[str, float], total: float
    ) -> int:
        if total < 0.05:
            return 0
        dominant_name = max(fractions, key=fractions.get)
        dominant = fractions[dominant_name]
        if dominant < 0.75:
            return 4
        return {"water": 1, "caustic": 2, "acid": 3}[dominant_name]

    def _infer_sequence_hint_locked(self) -> str:
        if self._fault_word:
            return "Fault"
        if self._caustic_valve and self._return_valve and self._pump:
            return "Caustic Return"
        if self._acid_valve and self._return_valve and self._pump:
            return "Acid Return"
        if self._caustic_valve:
            return "Caustic Wash"
        if self._acid_valve:
            return "Acid Wash"
        if self._water_valve and self._drain_valve:
            return "Rinse To Drain"
        if self._water_valve and self._return_valve:
            return "Recirculating Rinse"
        if self._pump and self._return_valve:
            return "Circulation"
        if self._drain_valve:
            return "Drain"
        return "Idle"

    def _remove_volume_locked(self, remove_liters: float) -> None:
        total = self._total_volume()
        if total <= 0.0:
            return
        amount = min(remove_liters, total)
        remaining_ratio = (total - amount) / total
        self._water_l *= remaining_ratio
        self._caustic_l *= remaining_ratio
        self._acid_l *= remaining_ratio

    def _cap_volume_locked(self, max_volume: float) -> None:
        total = self._total_volume()
        if total <= max_volume:
            return
        scale = max_volume / total
        self._water_l *= scale
        self._caustic_l *= scale
        self._acid_l *= scale

    def _total_volume(self) -> float:
        return self._water_l + self._caustic_l + self._acid_l

    @staticmethod
    def _liquid_name(code: int) -> str:
        return {0: "Empty", 1: "Water", 2: "Caustic",
                3: "Acid", 4: "Mixture"}.get(code, "Unknown")

    @staticmethod
    def _route_name(code: int) -> str:
        return {0: "Closed", 1: "Return", 2: "Drain",
                3: "Return + Drain"}.get(code, "Unknown")
```

### `sim_plugins/cip/ui.js`

```javascript
/* CIP dashboard renderer. Called by the shell on every poll.
 *
 * Reads only what the server exposes. The branches dict in status tells us
 * which pipes are flowing; we never recompute physics here.
 */
(function () {
  'use strict';

  var FLUID_COLOR = { 1: 'water', 2: 'caustic', 3: 'acid', 4: 'mixture' };
  var FAULT_LABELS = {
    0: 'Pump on without liquid',
    1: 'Pump on without flow route',
    2: 'Multiple source valves open',
    3: 'Overtemperature',
    4: 'Drain blocked by chemical residue',
  };

  var HIST_MAX = 90;
  var levelHist = [];
  var tempHist = [];
  var lastHistPush = 0;

  function el(id) { return document.getElementById(id); }
  function txt(id, s) { var e = el(id); if (e) e.textContent = s; }

  function setPipe(id, active, fluid) {
    var e = el(id);
    if (!e) return;
    e.setAttribute('class', 'pipe' + (active ? ' flow ' + fluid : ''));
  }

  function setValve(id, commanded, flowing) {
    var e = el(id);
    if (!e) return;
    var cls = 'valve';
    if (flowing) cls += ' flow';
    else if (commanded) cls += ' cmd';
    e.setAttribute('class', cls);
  }

  function badge(text, kind) {
    var s = document.createElement('span');
    s.className = 'badge' + (kind ? ' ' + kind : '');
    s.textContent = text;
    return s;
  }

  function faultList(word) {
    var out = [];
    for (var b = 0; b < 16; b++) {
      if (word & (1 << b)) {
        out.push({ bit: b, label: FAULT_LABELS[b] || ('fault bit ' + b) });
      }
    }
    return out;
  }

  function deriveAction(s, branches) {
    if (s.FaultWord !== 0) return 'Fault';
    if (branches.chemicalRecovery) return 'Chemical recovery';
    var inlet =
      branches.waterInlet ? 'water' :
      branches.causticInlet ? 'caustic' :
      branches.acidInlet ? 'acid' : null;
    var heat = (s.StatusWord & (1 << 5)) ? ' + heating' : '';
    if (inlet && branches.returnFlow) return 'Wash / circulate (' + inlet + ')' + heat;
    if (inlet) return 'Filling: ' + inlet + heat;
    if (branches.returnFlow) return 'Circulating (return)' + heat;
    if (branches.drainFlow) return 'Draining (pumped)';
    if (branches.gravityDrain) return 'Draining (gravity)';
    if (heat) return 'Heating (idle flow)';
    return 'Idle';
  }

  function pushHist(arr, v) {
    arr.push(v);
    if (arr.length > HIST_MAX) arr.shift();
  }

  function drawTrend(id, arr, lo, hi, color) {
    var c = el(id);
    if (!c) return;
    var ctx = c.getContext('2d');
    var w = c.width, h = c.height;
    ctx.clearRect(0, 0, w, h);
    if (arr.length < 2) return;
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (var i = 0; i < arr.length; i++) {
      var x = (i / (HIST_MAX - 1)) * w;
      var norm = Math.max(0, Math.min((arr[i] - lo) / (hi - lo), 1));
      var y = h - norm * (h - 4) - 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  window.renderState = function (state) {
    var m = state.measurements || {};
    var s = state.status || {};

    // Metric tiles
    txt('m-level', (m.LevelPercent || 0).toFixed(1));
    txt('m-flow',  (m.FlowLpm || 0).toFixed(1));
    txt('m-temp',  (m.TemperatureC || 0).toFixed(1));
    txt('m-cond',  (m.Conductivity || 0).toFixed(1));

    // Tank fill
    var top = 186, H = 238;
    var lvl = Math.max(0, Math.min(m.LevelPercent || 0, 100));
    var fillH = H * lvl / 100;
    var liq = el('liquid');
    if (liq) {
      liq.setAttribute('y', (top + H - fillH).toFixed(1));
      liq.setAttribute('height', fillH.toFixed(1));
      var fc = FLUID_COLOR[s.LiquidCode] || null;
      liq.setAttribute('fill', fc ? ('#' + ({
        water: '1e88e5', caustic: 'fb8c00', acid: 'd81b8c', mixture: '7e57c2'
      })[fc]) : '#cbd5e1');
    }
    txt('liquid-name', s.LiquidName || 'Empty');

    // Pipes (server-driven branches)
    var fluid = FLUID_COLOR[s.LiquidCode] || 'water';
    var suction = s.pumpRunning && (m.FlowLpm || 0) > 0.1;
    setPipe('p-water',   !!s.waterInlet, 'water');
    setPipe('p-acid',    !!s.acidInlet, 'acid');
    setPipe('p-caustic', !!s.causticInlet, 'caustic');
    setPipe('p-suction', suction || !!s.gravityDrain, fluid);
    setPipe('p-common',  suction || !!s.gravityDrain, fluid);
    setPipe('p-return',  !!s.returnFlow, fluid);
    setPipe('p-drain',   !!s.drainFlow || !!s.gravityDrain, fluid);

    // Valves
    setValve('v-water',   false, !!s.waterInlet);
    setValve('v-acid',    false, !!s.acidInlet);
    setValve('v-caustic', false, !!s.causticInlet);
    setValve('v-return',  false, !!s.returnFlow);
    setValve('v-drain',   false, !!s.drainFlow || !!s.gravityDrain);

    // Pump
    var pump = el('pump');
    if (pump) pump.setAttribute('class', s.pumpRunning ? 'pump-run' : 'equip');

    // Heater
    var heaterOn = (s.StatusWord & (1 << 5)) !== 0;
    var heater = el('heater');
    if (heater) heater.setAttribute('class', heaterOn ? 'heater-on' : 'heater-off');
    txt('caustic-temp', (m.CausticTankTempC || 20).toFixed(1) + ' °C');

    // Heat panel
    txt('h-cmd', heaterOn ? 'On' : 'Off');
    txt('h-temp', (m.CausticTankTempC || 20).toFixed(1) + ' °C');
    // Setpoint is a command; shell doesn't expose it to the read-only view.
    // Derive from status if you later add it; for now show the default.
    txt('h-sp', '45.0 °C');

    // State panel
    var pumpText = (s.StatusWord & (1 << 0))
      ? 'Running'
      : ((m.FlowLpm || 0) > 0.1 ? 'Running (gravity)' : 'Stopped');
    txt('s-pump', pumpText);
    txt('s-action', deriveAction(s, s));
    txt('s-liquid', s.LiquidName || 'Empty');
    txt('s-level', (m.LevelPercent || 0).toFixed(1) + ' %');
    txt('s-route', s.RouteName || 'Closed');

    // Command pills
    var cp = el('command-pills');
    if (cp) {
      cp.innerHTML = '';
      var shown = [];
      if (s.waterInlet) shown.push(['Water', 'cmd']);
      if (s.causticInlet) shown.push(['Caustic', 'cmd']);
      if (s.acidInlet) shown.push(['Acid', 'cmd']);
      if (s.pumpRunning) shown.push(['Pump', 'cmd']);
      if (s.returnFlow) shown.push(['Return', 'cmd']);
      if (s.drainFlow || s.gravityDrain) shown.push(['Drain', 'cmd']);
      if (s.StatusWord & (1 << 5)) shown.push(['Heater', 'cmd']);
      shown.forEach(function (p) { cp.appendChild(badge(p[0], p[1])); });
      if (!shown.length) cp.appendChild(badge('all commands off'));
    }

    // Faults
    var f = el('faults');
    if (f) {
      f.innerHTML = '';
      var active = faultList(s.FaultWord || 0);
      if (!active.length) {
        var ok = document.createElement('div');
        ok.className = 'alarm-none';
        ok.textContent = 'No active faults';
        f.appendChild(ok);
      } else {
        active.forEach(function (item) {
          var row = document.createElement('div');
          row.className = 'alarm-item';
          var bb = document.createElement('span');
          bb.className = 'bit';
          bb.textContent = 'bit ' + item.bit;
          var tt = document.createElement('span');
          tt.className = 'txt';
          tt.textContent = item.label;
          row.appendChild(bb);
          row.appendChild(tt);
          f.appendChild(row);
        });
      }
    }

    // Trends: push at most once per second so the window stays ~90s
    // even though the shell polls at 4 Hz.
    var now = Date.now();
    if (now - lastHistPush >= 1000) {
      lastHistPush = now;
      pushHist(levelHist, m.LevelPercent || 0);
      pushHist(tempHist, m.TemperatureC || 20);
      txt('tr-level-v', (m.LevelPercent || 0).toFixed(1) + ' %');
      txt('tr-temp-v', (m.TemperatureC || 0).toFixed(1) + ' °C');
    }
    drawTrend('tr-level', levelHist, 0, 100, '#1e88e5');
    drawTrend('tr-temp',  tempHist, 10, 90, '#fb8c00');
  };
})();
```

### `sim_runtime/base.py`

```python
"""Plugin contract for simulations.

A simulation is a pure-Python class implementing BaseSimulation. It has no
I/O, no async, no Django imports. The runtime adapts it to OPC UA and HTTP;
the plugin never knows those exist.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

CommandType = Literal["bool", "int", "float", "string"]
MeasurementType = Literal["bool", "int", "float", "string"]


@dataclass(frozen=True)
class CommandSpec:
    """One writable command exposed on the OPC UA server."""

    name: str
    type: CommandType
    description: str
    min: float | None = None        # numeric types only
    max: float | None = None        # numeric types only
    pulse: bool = False             # self-clearing, e.g. ResetFaultCmd
    default: Any = None


@dataclass(frozen=True)
class MeasurementSpec:
    """One read-only measurement exposed on the OPC UA server."""

    name: str
    type: MeasurementType
    unit: str
    description: str


@dataclass(frozen=True)
class StatusSpec:
    """One read-only status value (codes, strings, bitfield words)."""

    name: str
    type: MeasurementType
    description: str


@dataclass
class SimulationConfig:
    """Per-session configuration. Plugin-specific fields go in `params`."""

    session_id: str
    params: dict[str, Any] = field(default_factory=dict)


class BaseSimulation(ABC):
    """Contract every simulation implements.

    Design notes:
    - Schema is class-level so the OPC UA tree can be built before any
      instance exists.
    - step() is synchronous and must be fast. The runtime calls it at
      PHYSICS_HZ; blocking here stalls the whole session.
    - snapshot() returns a dict keyed by names declared in measurements()
      and status(). The adapter handles OPC UA and JSON serialization.
    - write_command() may raise ValueError; the adapter translates that
      into BadOutOfRange for the OPC UA client.
    """

    SIMULATION_ID: ClassVar[str]        # unique, lowercase, no spaces
    SIMULATION_NAME: ClassVar[str]      # human label
    SIMULATION_VERSION: ClassVar[str]   # semantic, e.g. "1.0.0"

    @classmethod
    @abstractmethod
    def commands(cls) -> dict[str, CommandSpec]: ...

    @classmethod
    @abstractmethod
    def measurements(cls) -> dict[str, MeasurementSpec]: ...

    @classmethod
    def status(cls) -> dict[str, StatusSpec]:
        """Optional. Override to expose status values."""
        return {}

    @abstractmethod
    def __init__(self, config: SimulationConfig) -> None: ...

    @abstractmethod
    def step(self, dt: float) -> None: ...

    @abstractmethod
    def snapshot(self) -> dict[str, Any]:
        """Return {"measurements": {...}, "status": {...}}.

        Keys must match the names declared in measurements() and status().
        Called on every OPC UA update and every HTTP poll.
        """

    @abstractmethod
    def write_command(self, name: str, value: Any) -> None: ...

    def on_client_activity(self) -> None:
        """Optional hook. Called when an external OPC UA read or write occurs.

        Default implementation does nothing. Simulations that want to react
        to being observed (or that need to suppress idle timeout) override.
        """
```

### `sim_runtime/http_adapter.py`

```python
"""HTTP dashboard for a running simulation.

Serves one HTML page and one JSON endpoint. Runs in a background thread so
it does not interfere with the OPC UA asyncio loop. The simulation's
snapshot() is called from this thread, so plugins that mutate state in
step() must use internal locking (CIP does; blinker's operations are
atomic enough for teaching purposes).

Plugin contract for the UI:
  sim_plugins/<sim_id>/body.html  — markup injected into the shell
  sim_plugins/<sim_id>/ui.js      — defines window.renderState(state)

Both are optional. A plugin without them gets a shell with no content.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from shared.logging import get_logger
from sim_runtime.base import BaseSimulation

_SHELL_PATH = Path(__file__).parent / "shell.html"
_PLUGIN_ROOT = Path(__file__).parent.parent / "sim_plugins"


def _compose_page(sim: BaseSimulation) -> bytes:
    """Read the shell and the plugin's body/script, substitute, return bytes.

    Done once at startup. If a plugin's body.html or ui.js is missing,
    the corresponding placeholder is replaced with an empty string.
    """
    shell = _SHELL_PATH.read_text(encoding="utf-8")
    plugin_dir = _PLUGIN_ROOT / sim.SIMULATION_ID

    body_path = plugin_dir / "body.html"
    body = body_path.read_text(encoding="utf-8") if body_path.exists() else ""

    script_path = plugin_dir / "ui.js"
    script = script_path.read_text(encoding="utf-8") if script_path.exists() else ""

    html = (
        shell
        .replace("{SIMULATION_NAME}", sim.SIMULATION_NAME)
        .replace("{PLUGIN_BODY}", body)
        .replace("{PLUGIN_SCRIPT}", script)
    )
    return html.encode("utf-8")


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def _make_handler(
    sim: BaseSimulation,
    *,
    session_id: str,
    endpoint: str,
    page_bytes: bytes,
):
    log = get_logger(__name__, session_id=session_id)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send(200, "text/html; charset=utf-8", page_bytes)
                return

            if self.path == "/api/state":
                payload = json.dumps({
                    "sessionId": session_id,
                    "simulationId": sim.SIMULATION_ID,
                    "endpoint": endpoint,
                    "state": sim.snapshot(),
                }).encode("utf-8")
                self._send(200, "application/json; charset=utf-8",
                           payload, no_cache=True)
                return

            if self.path == "/health":
                self._send(200, "text/plain; charset=utf-8", b"ok")
                return

            self.send_error(404, "Not Found")

        def _send(self, code: int, ctype: str, body: bytes,
                  no_cache: bool = False) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            if no_cache:
                self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args) -> None:
            # Route access logs through the structured logger at DEBUG.
            # At 4 Hz per browser this would otherwise flood stderr.
            log.debug("http %s %s", self.address_string(), fmt % args)

    return Handler


class HTTPDashboard:
    """Background HTTP server exposing the simulation state.

    Usage:
        dash = HTTPDashboard(sim, host="0.0.0.0", port=port,
                             session_id=sid, endpoint=endpoint)
        dash.start()
        ...
        dash.stop()
    """

    def __init__(
        self,
        sim: BaseSimulation,
        *,
        host: str,
        port: int,
        session_id: str,
        endpoint: str,
    ) -> None:
        self._log = get_logger(__name__, session_id=session_id, port=port)
        page = _compose_page(sim)
        handler = _make_handler(
            sim, session_id=session_id, endpoint=endpoint, page_bytes=page
        )
        self._server = _ReusableThreadingHTTPServer((host, port), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name=f"http-{session_id[:8]}",
            daemon=True,
        )
        self._started = False

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    def start(self) -> None:
        if self._started:
            return
        self._thread.start()
        self._started = True
        self._log.info("HTTP dashboard started")

    def stop(self, timeout: float = 5.0) -> None:
        if not self._started:
            return
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=timeout)
        self._started = False
        self._log.info("HTTP dashboard stopped")
```

### `sim_runtime/opcua_adapter.py`

```python
"""Schema-driven OPC UA server adapter.

Builds an OPC UA address space from a plugin's declared commands,
measurements, and status values. Knows nothing about any specific
simulation — reads the schema, wires up nodes, and translates between
OPC UA and the plugin's pure-Python interface.

Design notes:
- One adapter per running session. The adapter owns the Server instance;
  the caller owns the asyncio event loop and the stop signal.
- Command writes are validated by the adapter (type + range) and then
  applied via BaseSimulation.write_command(). A ValueError from the plugin
  is translated to BadOutOfRange for the client.
- Pulse commands (spec.pulse=True) are auto-cleared on the next tick.
- External reads and writes are observed via asyncua's PostRead/PostWrite
  callbacks, which feed idle detection in the worker runtime.
- Browse names are qualified in the adapter's own namespace. Passing a
  plain string to add_object/add_variable/add_folder would place the
  BrowseName in ns=0 (the OPC UA base namespace), which makes client-side
  path lookups like `2:Commands` fail with BadNoMatch.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable

from asyncua import Server, ua
from asyncua.common.callback import CallbackType
from asyncua.common.utils import ServiceError

from shared.constants import PHYSICS_HZ
from shared.logging import get_logger
from sim_runtime.base import BaseSimulation, CommandSpec


# ---------------------------------------------------------------------------
# Type mapping: plugin type name -> OPC UA variant type
# ---------------------------------------------------------------------------

_VARIANT_TYPES: dict[str, ua.VariantType] = {
    "bool": ua.VariantType.Boolean,
    "int": ua.VariantType.Int32,
    "uint": ua.VariantType.UInt32,
    "int16": ua.VariantType.Int16,
    "uint16": ua.VariantType.UInt16,
    "float": ua.VariantType.Double,
    "string": ua.VariantType.String,
}

_ZERO_VALUES: dict[str, Any] = {
    "bool": False,
    "int": 0,
    "uint": 0,
    "int16": 0,
    "uint16": 0,
    "float": 0.0,
    "string": "",
}


def _ua_type(type_name: str) -> ua.VariantType:
    try:
        return _VARIANT_TYPES[type_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported OPC UA type: {type_name!r}") from exc


def _zero_for(type_name: str) -> Any:
    try:
        return _ZERO_VALUES[type_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported type for default: {type_name!r}") from exc


def _coerce(value: Any, type_name: str) -> Any:
    """Coerce a snapshot value to the Python type matching the OPC UA type."""
    if type_name == "bool":
        return bool(value)
    if type_name in ("int", "int16"):
        return int(value)
    if type_name in ("uint", "uint16"):
        return max(0, int(value))
    if type_name == "float":
        return float(value)
    if type_name == "string":
        return str(value)
    raise ValueError(f"Unsupported type: {type_name!r}")


def _validate_command_value(raw: Any, spec: CommandSpec) -> Any:
    """Validate and normalise an incoming command value.

    Raises ServiceError with an appropriate OPC UA status code on any
    type or range mismatch. Returns the normalised value on success.
    """
    if spec.type == "bool":
        if not isinstance(raw, bool):
            raise ServiceError(ua.StatusCodes.BadTypeMismatch)
        return raw

    if spec.type in ("int", "int16", "uint", "uint16"):
        # Reject bool (subclass of int in Python) and floats.
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ServiceError(ua.StatusCodes.BadTypeMismatch)
        value = int(raw)

    elif spec.type == "float":
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ServiceError(ua.StatusCodes.BadTypeMismatch)
        value = float(raw)

    elif spec.type == "string":
        if not isinstance(raw, str):
            raise ServiceError(ua.StatusCodes.BadTypeMismatch)
        return raw

    else:
        raise ServiceError(ua.StatusCodes.BadTypeMismatch)

    # Range checks apply to numeric types only.
    if spec.min is not None and value < spec.min:
        raise ServiceError(ua.StatusCodes.BadOutOfRange)
    if spec.max is not None and value > spec.max:
        raise ServiceError(ua.StatusCodes.BadOutOfRange)
    if spec.type in ("uint", "uint16") and value < 0:
        raise ServiceError(ua.StatusCodes.BadOutOfRange)

    return value


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class OPCUAAdapter:
    """Wraps a BaseSimulation in an OPC UA server driven by its schema."""

    def __init__(
        self,
        sim: BaseSimulation,
        *,
        advertise_host: str,
        port: int,
        server_name: str | None = None,
    ) -> None:
        self._sim = sim
        self._sim_id = sim.SIMULATION_ID
        self._advertise_host = advertise_host
        self._port = port

        # Endpoint path is /<simulation_id>/ so the URL self-describes.
        self._endpoint = f"opc.tcp://{advertise_host}:{port}/{self._sim_id}/"
        self._namespace_uri = f"urn:cip-sim:{self._sim_id}:{sim.SIMULATION_VERSION}"

        self._server = Server()
        self._server_name = server_name or f"{sim.SIMULATION_NAME} simulator"
        self._namespace_idx: int = 0

        # Node references kept for the update loop.
        self._command_nodes: dict[str, ua.Node] = {}
        self._measurement_nodes: dict[str, ua.Node] = {}
        self._status_nodes: dict[str, ua.Node] = {}

        # Pulse commands written since the last tick, to be cleared next tick.
        self._pulses_pending: set[str] = set()

        # External activity tracking (PostRead / PostWrite).
        self._last_external_activity: float | None = None
        self._external_request_count: int = 0

        self._log = get_logger(
            __name__, simulation_id=self._sim_id, port=port
        )

    # ---- public API ----

    @property
    def endpoint(self) -> str:
        return self._endpoint

    def last_external_activity(self) -> float | None:
        """Monotonic timestamp of the last external client read or write.

        None if no external client has touched this session yet.
        """
        return self._last_external_activity

    def external_request_count(self) -> int:
        return self._external_request_count

    async def initialize(self) -> None:
        """Build the address space. Called once before run()."""
        await self._server.init()
        self._server.set_endpoint(self._endpoint)
        self._server.set_server_name(self._server_name)
        await self._server.set_application_uri(f"urn:cip-sim:server:{self._sim_id}")

        # v1: trusted intranet. No transport security, anonymous clients.
        # v2 direction: Basic256Sha256_SignAndEncrypt with per-session X.509
        # certificates and a trust list. See plan section on OPC UA security.
        self._server.set_security_policy([ua.SecurityPolicyType.NoSecurity])
        self._server.set_identity_tokens([ua.AnonymousIdentityToken])

        self._namespace_idx = await self._server.register_namespace(
            self._namespace_uri
        )

        ns = self._namespace_idx

        root = await self._server.nodes.objects.add_object(
            ua.NodeId(self._sim_id, ns),
            ua.QualifiedName(self._sim.SIMULATION_NAME, ns),
        )

        # Self-describing metadata. Consumers (the gateway, discovery tools,
        # CODESYS browsing) read these instead of relying on hardcoded maps.
        # Add a new plugin and these properties describe it automatically.
        await self._add_metadata_property(root, "SimulationId", self._sim_id)
        await self._add_metadata_property(
            root, "SimulationName", self._sim.SIMULATION_NAME
        )
        await self._add_metadata_property(
            root, "SimulationVersion", self._sim.SIMULATION_VERSION
        )
        await self._add_metadata_property(
            root, "NamespaceUri", self._namespace_uri
        )

        commands_folder = await root.add_folder(
            ua.NodeId(f"{self._sim_id}.Commands", ns),
            ua.QualifiedName("Commands", ns),
        )
        measurements_folder = await root.add_folder(
            ua.NodeId(f"{self._sim_id}.Measurements", ns),
            ua.QualifiedName("Measurements", ns),
        )
        status_folder = await root.add_folder(
            ua.NodeId(f"{self._sim_id}.Status", ns),
            ua.QualifiedName("Status", ns),
        )

        await self._build_commands(commands_folder)
        await self._build_measurements(measurements_folder)
        await self._build_status(status_folder)

        self._install_activity_callbacks()

        self._log.info(
            "OPC UA address space built",
            extra={"endpoint": self._endpoint, "namespace": self._namespace_uri},
        )

    async def run(self, stop: asyncio.Event) -> None:
        """Run the server until `stop` is set.

        Enters the asyncua server context (starts accepting connections),
        then loops at PHYSICS_HZ: step the simulation, push values to OPC UA,
        await the stop event with a short timeout.
        """
        tick = 1.0 / PHYSICS_HZ
        last_tick = time.monotonic()

        async with self._server:
            self._log.info("OPC UA server running", extra={"endpoint": self._endpoint})

            while not stop.is_set():
                now = time.monotonic()
                dt = now - last_tick
                last_tick = now

                try:
                    self._sim.step(dt)
                except Exception:
                    self._log.exception("simulation step raised")

                try:
                    await self._push_values()
                except Exception:
                    self._log.exception("failed to push values to OPC UA")

                try:
                    await asyncio.wait_for(stop.wait(), timeout=tick)
                except asyncio.TimeoutError:
                    pass

            self._log.info("OPC UA server stopping")

    # ---- address space construction ----

    async def _build_commands(self, folder: ua.Node) -> None:
        ns = self._namespace_idx
        for name, spec in self._sim.commands().items():
            default = spec.default if spec.default is not None else _zero_for(spec.type)
            node = await folder.add_variable(
                ua.NodeId(f"{self._sim_id}.Commands.{name}", ns),
                ua.QualifiedName(name, ns),
                default,
                _ua_type(spec.type),
            )
            await node.write_attribute(
                ua.AttributeIds.Description,
                ua.DataValue(ua.Variant(ua.LocalizedText(spec.description))),
            )
            await node.set_writable()
            self._server.set_attribute_value_setter(
                node.nodeid, self._make_command_setter(spec)
            )
            self._command_nodes[name] = node

        self._log.info(
            "command nodes built",
            extra={"count": len(self._command_nodes), "names": list(self._command_nodes)},
        )

    async def _add_metadata_property(
        self, parent: ua.Node, name: str, value: str
    ) -> None:
        """Add a read-only string property under `parent`.

        Uses asyncua's add_property so the node is typed as a Property
        rather than a Variable. Clients that browse the tree see it as
        metadata, not as a data point.
        """
        ns = self._namespace_idx
        node = await parent.add_property(
            ua.NodeId(f"{self._sim_id}.{name}", ns),
            ua.QualifiedName(name, ns),
            value,
            ua.VariantType.String,
        )
        await node.write_attribute(
            ua.AttributeIds.Description,
            ua.DataValue(ua.Variant(ua.LocalizedText(
                f"Self-describing metadata: {name}"
            ))),
        )

    async def _build_measurements(self, folder: ua.Node) -> None:
        ns = self._namespace_idx
        for name, spec in self._sim.measurements().items():
            description = (
                f"{spec.description} [{spec.unit}]" if spec.unit else spec.description
            )
            node = await folder.add_variable(
                ua.NodeId(f"{self._sim_id}.Measurements.{name}", ns),
                ua.QualifiedName(name, ns),
                _zero_for(spec.type),
                _ua_type(spec.type),
            )
            await node.write_attribute(
                ua.AttributeIds.Description,
                ua.DataValue(ua.Variant(ua.LocalizedText(description))),
            )
            self._measurement_nodes[name] = node

        self._log.info(
            "measurement nodes built",
            extra={"count": len(self._measurement_nodes)},
        )

    async def _build_status(self, folder: ua.Node) -> None:
        ns = self._namespace_idx
        for name, spec in self._sim.status().items():
            node = await folder.add_variable(
                ua.NodeId(f"{self._sim_id}.Status.{name}", ns),
                ua.QualifiedName(name, ns),
                _zero_for(spec.type),
                _ua_type(spec.type),
            )
            await node.write_attribute(
                ua.AttributeIds.Description,
                ua.DataValue(ua.Variant(ua.LocalizedText(spec.description))),
            )
            self._status_nodes[name] = node

        if self._status_nodes:
            self._log.info(
                "status nodes built",
                extra={"count": len(self._status_nodes)},
            )

    # ---- command writes ----

    def _make_command_setter(
        self, spec: CommandSpec
    ) -> Callable[[Any, int, ua.DataValue], None]:
        """Return the value setter asyncua will call when a client writes.

        The setter is synchronous by contract. It must either store the
        accepted value on `node_data.attributes[attribute].value` or raise
        ServiceError. The adapter treats that assignment as the commit point.
        """

        def set_value(node_data, attribute, value: ua.DataValue) -> None:
            if value is None or value.Value is None or value.Value.is_array:
                raise ServiceError(ua.StatusCodes.BadTypeMismatch)
            if value.StatusCode is not None and value.StatusCode.is_bad():
                raise ServiceError(ua.StatusCodes.BadTypeMismatch)

            raw = value.Value.Value
            normalised = _validate_command_value(raw, spec)

            try:
                self._sim.write_command(spec.name, normalised)
            except ValueError as exc:
                self._log.warning(
                    "command rejected by plugin",
                    extra={"command": spec.name, "error": str(exc)},
                )
                raise ServiceError(ua.StatusCodes.BadOutOfRange) from exc

            # Accept the write. asyncua propagates this value to clients.
            node_data.attributes[attribute].value = value

            if spec.pulse:
                self._pulses_pending.add(spec.name)

        return set_value

    # ---- activity observation ----

    def _install_activity_callbacks(self) -> None:
        def on_activity(event, service) -> None:
            if not event.is_external:
                return
            self._last_external_activity = time.monotonic()
            self._external_request_count += 1
            try:
                self._sim.on_client_activity()
            except Exception:
                self._log.exception("on_client_activity hook raised")

        self._server.subscribe_server_callback(CallbackType.PostRead, on_activity)
        self._server.subscribe_server_callback(CallbackType.PostWrite, on_activity)

    # ---- update loop ----

    async def _push_values(self) -> None:
        """Clear pulses, then push every measurement and status to OPC UA."""
        # Pulse commands: reset to default one tick after acceptance so a
        # client can write True again on the next request.
        for name in list(self._pulses_pending):
            node = self._command_nodes.get(name)
            if node is not None:
                try:
                    await node.write_value(False, ua.VariantType.Boolean)
                except Exception:
                    self._log.exception(
                        "pulse clear failed", extra={"command": name}
                    )
            self._pulses_pending.discard(name)

        snap = self._sim.snapshot()
        measurements = snap.get("measurements", {})
        status = snap.get("status", {})

        for name, spec in self._sim.measurements().items():
            value = measurements.get(name)
            if value is None:
                continue
            node = self._measurement_nodes.get(name)
            if node is None:
                continue
            await node.write_value(_coerce(value, spec.type), _ua_type(spec.type))

        for name, spec in self._sim.status().items():
            value = status.get(name)
            if value is None:
                continue
            node = self._status_nodes.get(name)
            if node is None:
                continue
            await node.write_value(_coerce(value, spec.type), _ua_type(spec.type))
```

### `sim_runtime/registry.py`

```python
"""Convention-based plugin discovery.

A plugin is a package under `sim_plugins/` whose `simulation.py` defines a
BaseSimulation subclass with a SIMULATION_ID. No decorator, no registry
file to edit — adding a directory is the entire installation procedure.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Iterable

from sim_runtime.base import BaseSimulation


class SimulationNotFound(KeyError):
    """Raised when a requested simulation_id is not in the registry."""


class SimulationRegistry:
    """Maps SIMULATION_ID to plugin class. Populated once per process."""

    def __init__(self) -> None:
        self._by_id: dict[str, type[BaseSimulation]] = {}

    def load_from(self, package: str = "sim_plugins") -> None:
        """Scan a package for plugin modules. Idempotent — safe to call again."""
        try:
            pkg = importlib.import_module(package)
        except ModuleNotFoundError as exc:
            raise RuntimeError(f"Plugin package {package!r} not found") from exc

        for _, mod_name, _ in pkgutil.iter_modules(pkg.__path__):
            module_path = f"{package}.{mod_name}.simulation"
            try:
                mod = importlib.import_module(module_path)
            except ModuleNotFoundError:
                # Not a plugin directory (no simulation.py). Skip quietly.
                continue

            for attr in vars(mod).values():
                if not (isinstance(attr, type) and issubclass(attr, BaseSimulation)):
                    continue
                if attr is BaseSimulation:
                    continue
                sim_id = getattr(attr, "SIMULATION_ID", None)
                if not sim_id:
                    raise RuntimeError(
                        f"{module_path}: {attr.__name__} is missing SIMULATION_ID"
                    )
                if sim_id in self._by_id:
                    other = self._by_id[sim_id].__module__
                    raise RuntimeError(
                        f"Duplicate SIMULATION_ID {sim_id!r}: "
                        f"{module_path} and {other}"
                    )
                self._by_id[sim_id] = attr

    def get(self, sim_id: str) -> type[BaseSimulation]:
        try:
            return self._by_id[sim_id]
        except KeyError as exc:
            raise SimulationNotFound(
                f"Unknown simulation {sim_id!r}. "
                f"Available: {sorted(self._by_id)}"
            ) from exc

    def ids(self) -> Iterable[str]:
        return sorted(self._by_id)

    def is_loaded(self) -> bool:
        return bool(self._by_id)
```

### `sim_runtime/shell.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{SIMULATION_NAME}</title>
<style>
  :root {
    --bg: #eef1f5;
    --panel: #ffffff;
    --panel-2: #f7f9fb;
    --ink: #1f2933;
    --ink-soft: #52606d;
    --ink-faint: #7b8794;
    --line: #d3dae2;
    --ok: #2e9e6b;
    --warn: #d97706;
    --bad: #e02424;
    --radius: 10px;
    --shadow: 0 1px 2px rgba(15,23,42,.08), 0 2px 8px rgba(15,23,42,.04);
    font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; }
  body { background: var(--bg); color: var(--ink); font-size: 14px; line-height: 1.4; padding: 12px; }

  .topbar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 18px;
    background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius);
    box-shadow: var(--shadow); padding: 10px 14px; margin-bottom: 12px; }
  .brand { font-size: 17px; font-weight: 600; margin-right: auto; }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; }
  .chip { display: flex; align-items: center; gap: 7px; background: var(--panel-2);
    border: 1px solid var(--line); border-radius: 999px; padding: 4px 11px 4px 9px;
    font-size: 12px; white-space: nowrap; font-variant-numeric: tabular-nums; }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--ink-faint); flex: none; }
  .dot.ok { background: var(--ok); }
  .dot.warn { background: var(--warn); }
  .dot.bad { background: var(--bad); }

  .banner { display: none; align-items: center; gap: 10px; background: #fff4f4;
    border: 1px solid #f3c0c0; color: #a01919; border-radius: var(--radius);
    padding: 9px 14px; margin-bottom: 12px; font-size: 13px; }
  body.stale .banner { display: flex; }
  body.stale #app { opacity: .55; }

  #app { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius);
    box-shadow: var(--shadow); padding: 12px 14px; }
  .card h2 { font-size: 12px; text-transform: uppercase; letter-spacing: .6px;
    color: var(--ink-faint); margin: 0 0 10px; font-weight: 600; }
  .kv { display: flex; justify-content: space-between; gap: 10px;
    padding: 5px 0; border-bottom: 1px dashed var(--line); }
  .kv:last-child { border-bottom: 0; }
  .kv .k { color: var(--ink-soft); }
  .kv .v { font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; }
</style>
</head>
<body>
  <header class="topbar">
    <div class="brand">{SIMULATION_NAME}</div>
    <div class="chips">
      <span class="chip"><span class="dot" id="dot-conn"></span><span id="conn-text">connecting</span></span>
      <span class="chip" id="endpoint-chip">--</span>
    </div>
  </header>

  <div class="banner">Connection lost &mdash; showing last received data.</div>

  <main id="app">
{PLUGIN_BODY}
  </main>

<script>
(function () {
  'use strict';
  var STALE_MS = 3000;
  var POLL_MS = 250;       // 4 Hz, matches UI_BROADCAST_HZ
  var lastGood = 0;

  function updateFreshness() {
    var age = lastGood ? Date.now() - lastGood : Infinity;
    var stale = age > STALE_MS;
    var dot = document.getElementById('dot-conn');
    var text = document.getElementById('conn-text');
    if (!lastGood) {
      dot.className = 'dot bad'; text.textContent = 'no data';
    } else if (stale) {
      dot.className = 'dot bad'; text.textContent = 'stale ' + Math.floor(age / 1000) + 's';
    } else {
      dot.className = 'dot ok'; text.textContent = 'live';
    }
    document.body.classList.toggle('stale', stale);
  }

  async function poll() {
    try {
      var r = await fetch('/api/state', { cache: 'no-store' });
      if (!r.ok) throw new Error('bad status');
      var data = await r.json();
      lastGood = Date.now();
      document.getElementById('endpoint-chip').textContent = data.endpoint || '--';
      if (typeof window.renderState === 'function') {
        window.renderState(data.state || {});
      }
    } catch (e) {
      // freshness banner handles it
    }
    updateFreshness();
  }

  poll();
  setInterval(poll, POLL_MS);
})();
</script>
<script>
{PLUGIN_SCRIPT}
</script>
</body>
</html>
```

### `tests/__init__.py`

```python

```

### `tests/manual/__init__.py`

```python

```

### `tests/manual/test_daemon.py`

```python
"""Manual end-to-end test for the worker pool daemon.

Starts the daemon as a subprocess, publishes a start command through
Redis, waits for the worker to appear, publishes a stop command, and
verifies clean shutdown.

Run from the project root with the venv active:

    python -m tests.manual.test_daemon

Requires Redis on localhost. Uses ports 5300-5310.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis

from shared.constants import REDIS_EVT_STREAM, STREAM_MAXLEN
from shared.schemas import (
    StartSessionCommand,
    StopSessionCommand,
    parse_event,
)


async def _wait_for(predicate, *, timeout: float = 15.0, interval: float = 0.3):
    """Poll predicate() (sync or async) until it returns truthy or times out."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        result = predicate()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return result
        await asyncio.sleep(interval)
    return None


async def main() -> int:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = aioredis.from_url(redis_url, decode_responses=True)

    # Clean slate
    async for key in r.scan_iter("cip:*"):
        await r.delete(key)
    await r.delete("cip:cmd", "cip:evt")

    env = {
        **os.environ,
        "REDIS_URL": redis_url,
        "OPCUA_PORT_START": "5300",
        "OPCUA_PORT_END": "5310",
    }

    print("== start daemon ==")
    proc = subprocess.Popen(
        [sys.executable, "-m", "worker_pool.daemon",
         "--advertise-host", "127.0.0.1"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    async def drain():
        """Print daemon output as it arrives."""
        assert proc.stdout is not None
        while True:
            line = await asyncio.to_thread(proc.stdout.readline)
            if not line:
                break
            print("   daemon:", line.decode("utf-8", errors="replace").rstrip())

    drain_task = asyncio.create_task(drain())

    # Wait for daemon to be ready by watching for the ready log line.
    # Simplest proxy: it will create the consumer group and be ready
    # within ~2s of start.
    await asyncio.sleep(2.5)

    print()
    print("== publish start command ==")
    sid = "daemon-test1"
    start = StartSessionCommand(
        session_id=sid,
        simulation_id="cip",
        config_params={},
        request_id=str(uuid.uuid4()),
        issued_at=datetime.now(timezone.utc),
    )
    await r.xadd(
        "cip:cmd", {"payload": start.model_dump_json()},
        maxlen=STREAM_MAXLEN, approximate=True,
    )

    async def worker_running():
        hb = await r.get(f"cip:hb:{sid}")
        return hb is not None

    found = await _wait_for(worker_running, timeout=15.0)
    print("   worker heartbeat present:", bool(found))
    if found:
        print("   hb:", found)

    print()
    print("== active sessions (via Redis heartbeat) ==")
    async for key in r.scan_iter("cip:hb:*"):
        print("  ", key)

    print()
    print("== publish stop command ==")
    stop_cmd = StopSessionCommand(
        session_id=sid,
        reason="user_request",
        request_id=str(uuid.uuid4()),
        issued_at=datetime.now(timezone.utc),
    )
    await r.xadd(
        "cip:cmd", {"payload": stop_cmd.model_dump_json()},
        maxlen=STREAM_MAXLEN, approximate=True,
    )

    async def worker_gone():
        hb = await r.get(f"cip:hb:{sid}")
        return hb is None

    gone = await _wait_for(worker_gone, timeout=15.0)
    print("   worker gone:", bool(gone))

    print()
    print("== events emitted ==")
    entries = await r.xrange(REDIS_EVT_STREAM, "-", "+")
    for _msg_id, fields in entries:
        payload = fields.get("payload")
        if payload:
            try:
                print("  ", parse_event(payload).kind)
            except Exception:
                print("   unparsable")

    print()
    print("== stop daemon (SIGTERM) ==")
    proc.send_signal(signal.SIGTERM)
    try:
        await asyncio.wait_for(asyncio.to_thread(proc.wait), timeout=15.0)
        print("   exited with code:", proc.returncode)
    except asyncio.TimeoutError:
        print("   daemon did not exit; killing")
        proc.kill()

    drain_task.cancel()
    await asyncio.gather(drain_task, return_exceptions=True)

    await r.aclose()
    print()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

### `tests/manual/test_manager.py`

```python
"""Manual smoke test for WorkerPoolManager.

Run from the project root with the venv active:

    python -m tests.manual.test_manager

Requires Redis running on localhost. Uses ports 5100-5110 so it does
not collide with anything else you have running.
"""

from __future__ import annotations

import asyncio
import os

import redis.asyncio as aioredis

from worker_pool.manager import WorkerPoolManager
from worker_pool.port_allocator import PortAllocator


async def main() -> int:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = aioredis.from_url(redis_url, decode_responses=True)

    allocator = PortAllocator(r, start=5100, end=5110)
    mgr = WorkerPoolManager(
        redis=r,
        port_allocator=allocator,
        advertise_host="127.0.0.1",
    )

    print("== reconcile on startup ==")
    await mgr.reconcile_on_startup()
    print("   tracked:", mgr.active_sessions())

    print()
    print("== spawn test1 (cip) ==")
    record = await mgr.start_worker(
        session_id="test1",
        simulation_id="cip",
        config_params={},
    )
    print(f"   pid={record.pid} port={record.port}")

    print()
    print("== wait 3s for heartbeat ==")
    await asyncio.sleep(3.0)
    hb = await r.get("cip:hb:test1")
    print("   cip:hb:test1 =", hb)

    print()
    print("== active sessions ==")
    for s in mgr.active_sessions():
        print("  ", s)

    print()
    print("== stop test1 ==")
    ok = await mgr.stop_worker("test1", reason="smoke_test")
    print("   stopped:", ok)

    print()
    print("== verify cleanup ==")
    print("   tracked:", mgr.active_sessions())
    print("   heartbeat:", await r.get("cip:hb:test1"))
    print("   ports leased:", await allocator.snapshot())

    await r.aclose()
    print()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

### `tests/manual/test_redis_bridge.py`

```python
"""Manual smoke test for RedisBridge.

Runs a manager and a bridge in-process, publishes commands to the
command stream, and verifies that workers are spawned and stopped.

Run from the project root with the venv active:

    python -m tests.manual.test_redis_bridge

Requires Redis on localhost. Uses ports 5200-5210.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis

from shared.constants import REDIS_EVT_STREAM, STREAM_MAXLEN
from shared.schemas import (
    SessionStartedEvent,
    SessionStoppedEvent,
    StartSessionCommand,
    StopSessionCommand,
    parse_event,
)
from worker_pool.manager import WorkerPoolManager
from worker_pool.port_allocator import PortAllocator
from worker_pool.redis_bridge import RedisBridge


async def _drain_events(r: aioredis.Redis) -> list[str]:
    """Read everything currently in the events stream."""
    entries = await r.xrange(REDIS_EVT_STREAM, "-", "+")
    out: list[str] = []
    for _msg_id, fields in entries:
        payload = fields.get("payload")
        if payload:
            try:
                event = parse_event(payload)
                out.append(event.kind)
            except Exception:
                out.append("unparsable")
    return out


async def main() -> int:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = aioredis.from_url(redis_url, decode_responses=True)

    # Clean slate
    await r.delete(REDIS_EVT_STREAM, "cip:cmd")
    async for key in r.scan_iter("cip:*"):
        await r.delete(key)

    allocator = PortAllocator(r, start=5200, end=5210)
    mgr = WorkerPoolManager(
        redis=r,
        port_allocator=allocator,
        advertise_host="127.0.0.1",
    )
    bridge = RedisBridge(
        redis=r, manager=mgr,
        consumer_name=f"smoke-{uuid.uuid4().hex[:6]}",
    )

    await bridge.ensure_group()

    stop = asyncio.Event()
    bridge_task = asyncio.create_task(bridge.run(stop))

    # Give the bridge a moment to enter xreadgroup.
    await asyncio.sleep(0.5)

    sid = "smoke1"
    print("== publish start command ==")
    start_cmd = StartSessionCommand(
        session_id=sid,
        simulation_id="cip",
        config_params={},
        request_id=str(uuid.uuid4()),
        issued_at=datetime.now(timezone.utc),
    )
    await r.xadd(
        "cip:cmd", {"payload": start_cmd.model_dump_json()},
        maxlen=STREAM_MAXLEN, approximate=True,
    )

    # Wait for worker to spawn
    for _ in range(20):
        await asyncio.sleep(0.5)
        if mgr.is_tracked(sid):
            break

    print("   tracked:", mgr.is_tracked(sid))
    print("   sessions:", mgr.active_sessions())

    print()
    print("== wait for heartbeat ==")
    await asyncio.sleep(2.0)
    hb = await r.get(f"cip:hb:{sid}")
    print(f"   cip:hb:{sid} = {hb}")

    print()
    print("== publish stop command ==")
    stop_cmd = StopSessionCommand(
        session_id=sid,
        reason="user_request",
        request_id=str(uuid.uuid4()),
        issued_at=datetime.now(timezone.utc),
    )
    await r.xadd(
        "cip:cmd", {"payload": stop_cmd.model_dump_json()},
        maxlen=STREAM_MAXLEN, approximate=True,
    )

    for _ in range(20):
        await asyncio.sleep(0.5)
        if not mgr.is_tracked(sid):
            break

    print("   tracked:", mgr.is_tracked(sid))
    print("   sessions:", mgr.active_sessions())
    print("   ports leased:", await allocator.snapshot())

    print()
    print("== events emitted ==")
    kinds = await _drain_events(r)
    for kind in kinds:
        print("  ", kind)

    # Shutdown
    stop.set()
    try:
        await asyncio.wait_for(bridge_task, timeout=5.0)
    except asyncio.TimeoutError:
        bridge_task.cancel()

    await mgr.shutdown_all(timeout=5.0)
    await r.aclose()
    print()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

### `tests/unit/test_blinker.py`

```python
"""End-to-end test for the blinker plugin through the OPC UA adapter.

Runs a real asyncua server on an ephemeral port, connects a real asyncua
client, writes a command, reads a measurement. This is the smallest
possible proof that the plugin contract works.
"""

from __future__ import annotations

import asyncio
import socket

import pytest
from asyncua import Client, ua

from sim_runtime.base import SimulationConfig
from sim_runtime.opcua_adapter import OPCUAAdapter
from sim_plugins.blinker.simulation import Blinker


def _free_port() -> int:
    """Ask the OS for a port that's currently free, then release it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _wait_for_server(host: str, port: int, timeout: float = 5.0) -> None:
    """Poll until the OPC UA port accepts a TCP connection."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            _, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            return
        except OSError:
            await asyncio.sleep(0.05)
    raise TimeoutError(f"server on {host}:{port} never came up")


@pytest.mark.asyncio
async def test_blinker_roundtrip():
    port = _free_port()
    sim = Blinker(SimulationConfig(session_id="test", params={}))
    adapter = OPCUAAdapter(sim, advertise_host="127.0.0.1", port=port)
    await adapter.initialize()

    stop = asyncio.Event()
    server_task = asyncio.create_task(adapter.run(stop))

    try:
        await _wait_for_server("127.0.0.1", port)

        async with Client(url=f"opc.tcp://127.0.0.1:{port}/blinker/") as client:
            idx = await client.get_namespace_index(
                "urn:cip-sim:blinker:1.0.0"
            )

            enabled = await client.nodes.root.get_child(
                ["0:Objects", f"{idx}:Blinking Light",
                 f"{idx}:Commands", f"{idx}:Enabled"]
            )
            on_node = await client.nodes.root.get_child(
                ["0:Objects", f"{idx}:Blinking Light",
                 f"{idx}:Measurements", f"{idx}:On"]
            )
            period_node = await client.nodes.root.get_child(
                ["0:Objects", f"{idx}:Blinking Light",
                 f"{idx}:Commands", f"{idx}:PeriodSeconds"]
            )

            # Initially off.
            assert await on_node.read_value() is False

            # Enable with a short period so we see a transition quickly.
            await period_node.write_value(
                ua.Variant(0.5, ua.VariantType.Double)
            )
            await enabled.write_value(
                ua.Variant(True, ua.VariantType.Boolean)
            )

            # Give it a couple of periods to blink.
            await asyncio.sleep(0.6)

            # At some point during the sleep the light was on; we only
            # know it ran because the phase advanced. Read BlinkCount.
            count_node = await client.nodes.root.get_child(
                ["0:Objects", f"{idx}:Blinking Light",
                 f"{idx}:Status", f"{idx}:BlinkCount"]
            )
            count = await count_node.read_value()
            assert count >= 1, f"expected at least 1 blink, got {count}"

            # Disable and confirm On goes False.
            await enabled.write_value(
                ua.Variant(False, ua.VariantType.Boolean)
            )
            await asyncio.sleep(0.15)
            assert await on_node.read_value() is False

    finally:
        stop.set()
        await asyncio.wait_for(server_task, timeout=3.0)


@pytest.mark.asyncio
async def test_blinker_pulse_resets_count():
    port = _free_port()
    sim = Blinker(SimulationConfig(session_id="test", params={}))
    adapter = OPCUAAdapter(sim, advertise_host="127.0.0.1", port=port)
    await adapter.initialize()

    stop = asyncio.Event()
    server_task = asyncio.create_task(adapter.run(stop))

    try:
        await _wait_for_server("127.0.0.1", port)

        async with Client(url=f"opc.tcp://127.0.0.1:{port}/blinker/") as client:
            idx = await client.get_namespace_index("urn:cip-sim:blinker:1.0.0")

            async def child(folder: str, name: str):
                return await client.nodes.root.get_child(
                    ["0:Objects", f"{idx}:Blinking Light",
                     f"{idx}:{folder}", f"{idx}:{name}"]
                )

            enabled = await child("Commands", "Enabled")
            period = await child("Commands", "PeriodSeconds")
            reset = await child("Commands", "ResetCountCmd")
            count_node = await child("Status", "BlinkCount")

            await period.write_value(ua.Variant(0.2, ua.VariantType.Double))
            await enabled.write_value(ua.Variant(True, ua.VariantType.Boolean))
            await asyncio.sleep(0.7)

            count = await count_node.read_value()
            assert count >= 2, f"expected >=2 blinks before reset, got {count}"

            # Pulse the reset. The adapter clears it back to False.
            await reset.write_value(ua.Variant(True, ua.VariantType.Boolean))
            await asyncio.sleep(0.15)

            # Value on the node should be False again (auto-cleared).
            assert await reset.read_value() is False
            # Count should have been reset.
            assert await count_node.read_value() <= 1

    finally:
        stop.set()
        await asyncio.wait_for(server_task, timeout=3.0)
```

### `tests/unit/test_port_allocator.py`

```python
"""Unit tests for the async port allocator.

Uses fakeredis.aioredis so no external service is required. The two
tests that matter most are the concurrent-acquire race and the stale-
release protection — those are the bugs the design exists to prevent.
"""

from __future__ import annotations

import asyncio

import fakeredis.aioredis
import pytest

from worker_pool.port_allocator import PortAllocator, PortPoolExhausted


@pytest.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis(decode_responses=False)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def pool(redis_client):
    return PortAllocator(redis_client, start=5000, end=5002)


async def test_acquire_returns_port_in_range(pool):
    port = await pool.acquire("session-a")
    assert 5000 <= port <= 5002


async def test_acquire_second_call_gives_different_port(pool):
    p1 = await pool.acquire("session-a")
    p2 = await pool.acquire("session-b")
    assert p1 != p2


async def test_pool_exhaustion_raises(pool):
    await pool.acquire("a")
    await pool.acquire("b")
    await pool.acquire("c")
    with pytest.raises(PortPoolExhausted):
        await pool.acquire("d")


async def test_release_frees_the_port(pool):
    p1 = await pool.acquire("session-a")
    assert await pool.release(p1, "session-a")
    p2 = await pool.acquire("session-b")
    assert p2 == p1


async def test_release_by_wrong_session_is_rejected(pool):
    p1 = await pool.acquire("session-a")
    assert await pool.release(p1, "session-b") is False
    assert (await pool.snapshot())[p1] == "session-a"


async def test_release_twice_is_idempotent(pool):
    p1 = await pool.acquire("session-a")
    assert await pool.release(p1, "session-a") is True
    assert await pool.release(p1, "session-a") is False


async def test_concurrent_acquire_never_double_leases(pool):
    """Race N tasks for M ports; each port is leased at most once."""
    async def worker(sid: str):
        return await pool.acquire(sid)

    results = await asyncio.gather(
        worker("s0"), worker("s1"), worker("s2"),
        return_exceptions=True,
    )
    # Every task should succeed with 3 ports available
    ports = [r for r in results if isinstance(r, int)]
    assert len(ports) == 3
    assert len(set(ports)) == 3


async def test_reconcile_drops_orphans(pool):
    p1 = await pool.acquire("session-a")
    p2 = await pool.acquire("session-b")
    dropped = await pool.reconcile(live_session_ids={"session-a"})
    assert dropped == [p2]
    assert (await pool.snapshot()) == {p1: "session-a"}


async def test_reconcile_keeps_live_leases(pool):
    p1 = await pool.acquire("session-a")
    dropped = await pool.reconcile(live_session_ids={"session-a"})
    assert dropped == []
    assert (await pool.snapshot()) == {p1: "session-a"}
```

### `tools/opcua_cli.py`

```python
#!/usr/bin/env python3
"""Send OPC UA commands to a running CIP worker or to the gateway.

Usage against a worker:
    python tools/opcua_cli.py --endpoint opc.tcp://10.120.32.67:8080/cip/ \\
        PumpCmd=1 WaterValveCmd=1

Usage against the gateway (one or more sessions visible):
    # List sessions exposed by the gateway
    python tools/opcua_cli.py --endpoint opc.tcp://127.0.0.1:8080/gateway/ \\
        --list-sessions

    # Dump one session's tree through the gateway
    python tools/opcua_cli.py --endpoint opc.tcp://127.0.0.1:8080/gateway/ \\
        --session test1 --dump

    # Write a command through the gateway to session test1
    python tools/opcua_cli.py --endpoint opc.tcp://127.0.0.1:8080/gateway/ \\
        --session test1 WaterValveCmd=1 PumpCmd=1

    # Read a measurement through the gateway
    python tools/opcua_cli.py --endpoint opc.tcp://127.0.0.1:8080/gateway/ \\
        --session test1 --read LevelPercent FlowLpm
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from asyncua import Client, ua


NAMESPACE_BY_SIM = {
    "cip": "urn:cip-sim:cip:2.0.0",
    "blinker": "urn:cip-sim:blinker:1.0.0",
    "gateway": "urn:cip-sim:gateway:1.0.0",
}

FOLDER_NAME = {
    "cip": "Clean-In-Place",
    "blinker": "Blinking Light",
    "gateway": "Gateway",
}


def _parse_value(raw: str):
    low = raw.lower()
    if low in ("1", "true", "on", "yes"):
        return True, ua.VariantType.Boolean
    if low in ("0", "false", "off", "no"):
        return False, ua.VariantType.Boolean
    try:
        return float(raw), ua.VariantType.Double
    except ValueError:
        pass
    return raw, ua.VariantType.String


def _sim_id_from_endpoint(endpoint: str) -> str:
    tail = endpoint.rstrip("/").rsplit("/", 1)[-1]
    return tail or "cip"


# --- address resolution -----------------------------------------------------

async def _resolve_plugin(prefix: Client, sim_id: str, folder: str, name: str):
    idx = await prefix.get_namespace_index(NAMESPACE_BY_SIM[sim_id])
    return await prefix.nodes.root.get_child([
        "0:Objects",
        f"{idx}:{FOLDER_NAME[sim_id]}",
        f"{idx}:{folder}",
        f"{idx}:{name}",
    ])


async def _resolve_gateway(
    c: Client, session_id: str, folder: str, name: str
):
    idx = await c.get_namespace_index(NAMESPACE_BY_SIM["gateway"])
    return await c.nodes.root.get_child([
        "0:Objects",
        f"{idx}:Gateway",
        f"{idx}:Sessions",
        f"{idx}:{session_id}",
        f"{idx}:{folder}",
        f"{idx}:{name}",
    ])


# --- operations -------------------------------------------------------------

async def _list_sessions(c: Client) -> None:
    idx = await c.get_namespace_index(NAMESPACE_BY_SIM["gateway"])
    sessions = await c.nodes.root.get_child([
        "0:Objects", f"{idx}:Gateway", f"{idx}:Sessions",
    ])
    children = await sessions.get_children()
    if not children:
        print("(no sessions)")
        return
    for child in children:
        bn = await child.read_browse_name()
        print(bn.Name)


async def _dump_plugin(c: Client, sim_id: str) -> None:
    idx = await c.get_namespace_index(NAMESPACE_BY_SIM[sim_id])
    root = await c.nodes.root.get_child([
        "0:Objects", f"{idx}:{FOLDER_NAME[sim_id]}"
    ])
    for folder_name in ("Commands", "Measurements", "Status"):
        try:
            folder = await root.get_child([f"{idx}:{folder_name}"])
        except Exception:
            continue
        print(f"--- {folder_name} ---")
        for child in await folder.get_children():
            try:
                value = await child.read_value()
            except Exception as exc:
                value = f"<error: {exc}>"
            print(f"  {(await child.read_browse_name()).Name}: {value!r}")


async def _dump_gateway(c: Client, session_id: str) -> None:
    idx = await c.get_namespace_index(NAMESPACE_BY_SIM["gateway"])
    root = await c.nodes.root.get_child([
        "0:Objects", f"{idx}:Gateway", f"{idx}:Sessions", f"{idx}:{session_id}",
    ])
    for folder_name in ("Commands", "Measurements", "Status"):
        try:
            folder = await root.get_child([f"{idx}:{folder_name}"])
        except Exception:
            continue
        print(f"--- {folder_name} ---")
        for child in await folder.get_children():
            try:
                value = await child.read_value()
            except Exception as exc:
                value = f"<error: {exc}>"
            print(f"  {(await child.read_browse_name()).Name}: {value!r}")


async def _write_plugin(c: Client, sim_id: str, assignments: list[str]) -> None:
    for a in assignments:
        if "=" not in a:
            print(f"skip (no '='): {a}", file=sys.stderr)
            continue
        name, raw = a.split("=", 1)
        value, vtype = _parse_value(raw)
        node = await _resolve_plugin(c, sim_id, "Commands", name)
        await node.write_value(ua.Variant(value, vtype))
        print(f"wrote {name} = {value!r}")


async def _write_gateway(
    c: Client, session_id: str, assignments: list[str]
) -> None:
    for a in assignments:
        if "=" not in a:
            print(f"skip (no '='): {a}", file=sys.stderr)
            continue
        name, raw = a.split("=", 1)
        value, vtype = _parse_value(raw)
        node = await _resolve_gateway(c, session_id, "Commands", name)
        await node.write_value(ua.Variant(value, vtype))
        print(f"wrote {session_id}/{name} = {value!r}")


async def _read_plugin(c: Client, sim_id: str, names: list[str]) -> None:
    for name in names:
        node = await _resolve_plugin(c, sim_id, "Measurements", name)
        print(f"{name} = {await node.read_value()!r}")


async def _read_gateway(c: Client, session_id: str, names: list[str]) -> None:
    for name in names:
        node = await _resolve_gateway(c, session_id, "Measurements", name)
        print(f"{session_id}/{name} = {await node.read_value()!r}")


# --- entry point ------------------------------------------------------------

async def _main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--endpoint", required=True,
                   help="e.g. opc.tcp://127.0.0.1:8080/cip/")
    p.add_argument("--session", help="Session id (required for gateway writes/reads/dump).")
    p.add_argument("--list-sessions", action="store_true",
                   help="List sessions exposed by the gateway.")
    p.add_argument("assignments", nargs="*",
                   help="CommandName=Value pairs to write")
    p.add_argument("--read", nargs="+", metavar="NAME")
    p.add_argument("--dump", action="store_true")
    args = p.parse_args()

    sim_id = _sim_id_from_endpoint(args.endpoint)
    is_gateway = (sim_id == "gateway")

    if is_gateway and (args.assignments or args.read or args.dump) and not args.session:
        if args.list_sessions:
            pass  # ok
        else:
            print("--session is required for gateway operations "
                  "(or use --list-sessions)", file=sys.stderr)
            return 2

    async with Client(url=args.endpoint) as c:
        if is_gateway:
            if args.list_sessions:
                await _list_sessions(c)
            if args.dump:
                await _dump_gateway(c, args.session)
            if args.read:
                await _read_gateway(c, args.session, args.read)
            if args.assignments:
                await _write_gateway(c, args.session, args.assignments)
        else:
            if args.dump:
                await _dump_plugin(c, sim_id)
            if args.read:
                await _read_plugin(c, sim_id, args.read)
            if args.assignments:
                await _write_plugin(c, sim_id, args.assignments)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
```

### `worker_pool/__init__.py`

```python

```

### `worker_pool/daemon.py`

```python
"""Worker pool daemon.

Long-running service that spawns and tracks simulation workers on
command. It is the process-side counterpart to the Django control
plane; the two communicate only through Redis.

Responsibilities:

    - Load the port allocator and manager.
    - Reconcile against Redis heartbeats at startup, so workers that
      survived a daemon restart are adopted and stale state is dropped.
    - Consume StartSessionCommand and StopSessionCommand from the
      command stream via the Redis bridge.
    - Periodically reap dead workers and enforce idle timeouts.
    - Handle SIGTERM: stop accepting commands, shut down tracked
      workers gracefully, exit cleanly.

Run as a systemd service, or by hand for development:

    REDIS_URL=redis://localhost:6379/0 \\
    python -m worker_pool.daemon --advertise-host 10.0.0.5

Configuration is read from the environment (shared.constants).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
import time

import redis.asyncio as aioredis

from shared.constants import (
    REDIS_HEARTBEAT_PREFIX,
    WORKER_IDLE_TIMEOUT,
)
from shared.logging import configure_logging, get_logger
from shared.schemas import SessionFailedEvent, SessionStoppedEvent
from worker_pool.manager import WorkerPoolManager
from worker_pool.port_allocator import PortAllocator
from worker_pool.redis_bridge import RedisBridge


log = get_logger(__name__)


# How often to scan for dead workers and idle sessions.
_REAP_INTERVAL_SEC = 5.0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CIP worker pool daemon")
    p.add_argument(
        "--advertise-host", required=True,
        help="Host or IP that OPC UA clients will use to reach workers. "
             "This is the address the server tells clients to connect to, "
             "not necessarily an interface on this machine.",
    )
    p.add_argument(
        "--log-level", default=os.environ.get("LOG_LEVEL", "INFO"),
        help="Log level (DEBUG, INFO, WARNING, ERROR).",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Background tasks
# ---------------------------------------------------------------------------

async def _reaper_loop(
    *,
    manager: WorkerPoolManager,
    bridge: RedisBridge,
    stop: asyncio.Event,
) -> None:
    """Periodically detect dead workers and publish events for them."""
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=_REAP_INTERVAL_SEC)
            return
        except asyncio.TimeoutError:
            pass

        try:
            reaped = await manager.reap_dead_workers()
        except Exception:
            log.exception("reaper pass failed")
            continue

        for session_id in reaped:
            log.warning("worker died unexpectedly",
                        extra={"session_id": session_id})
            await bridge.publish_event(SessionFailedEvent(
                session_id=session_id,
                error="worker process exited without a stop command",
            ))


async def _idle_loop(
    *,
    redis: aioredis.Redis,
    manager: WorkerPoolManager,
    bridge: RedisBridge,
    stop: asyncio.Event,
) -> None:
    """Stop workers whose OPC UA clients have been silent too long.

    The worker writes cip:idle:<sid> with the wall-clock timestamp of
    the last external OPC UA activity. If no client has connected for
    WORKER_IDLE_TIMEOUT seconds, the daemon stops the session.
    """
    # Check once per minute; the timeout itself is on the order of
    # half an hour, so precision is not important.
    interval = 60.0

    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
            return
        except asyncio.TimeoutError:
            pass

        now = time.time()
        for record in manager.active_sessions():
            session_id = record["session_id"]
            try:
                idle_raw = await redis.get(f"cip:idle:{session_id}")
            except Exception:
                log.exception("idle check failed",
                              extra={"session_id": session_id})
                continue
            if idle_raw is None:
                # Heartbeat or idle key expired; the reaper will handle
                # it on the next pass. Skip here.
                continue
            try:
                last_activity = float(idle_raw)
            except (TypeError, ValueError):
                continue

            idle_secs = now - last_activity
            if idle_secs > WORKER_IDLE_TIMEOUT:
                log.info(
                    "stopping idle session",
                    extra={"session_id": session_id,
                           "idle_seconds": round(idle_secs, 1)},
                )
                stopped = await manager.stop_worker(
                    session_id, reason="idle_timeout",
                )
                if stopped:
                    await bridge.publish_event(SessionStoppedEvent(
                        session_id=session_id,
                        reason="idle_timeout",
                    ))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _run(args: argparse.Namespace) -> int:
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis = aioredis.from_url(redis_url, decode_responses=True)

    # Verify Redis is reachable before doing anything else. A clear
    # error here beats a cascade of failures across the bridge.
    try:
        await redis.ping()
    except Exception as exc:
        log.error("cannot reach Redis", extra={"error": str(exc)})
        await redis.aclose()
        return 2

    allocator = PortAllocator(redis)
    manager = WorkerPoolManager(
        redis=redis,
        port_allocator=allocator,
        advertise_host=args.advertise_host,
    )
    bridge = RedisBridge(redis=redis, manager=manager)

    log.info("daemon starting", extra={
        "advertise_host": args.advertise_host,
        "pid": os.getpid(),
    })

    # Reconcile before consuming commands, so we know what is already
    # running and can drop stale port leases.
    await manager.reconcile_on_startup()
    active = manager.active_sessions()
    if active:
        log.info("adopted workers from previous run",
                 extra={"count": len(active)})

    await bridge.ensure_group()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    bridge_task = asyncio.create_task(
        bridge.run(stop), name="redis-bridge",
    )
    reaper_task = asyncio.create_task(
        _reaper_loop(manager=manager, bridge=bridge, stop=stop),
        name="reaper",
    )
    idle_task = asyncio.create_task(
        _idle_loop(redis=redis, manager=manager, bridge=bridge, stop=stop),
        name="idle-watch",
    )

    log.info("daemon ready")

    # Wait for the stop signal. The three background tasks keep running
    # until then.
    await stop.wait()

    log.info("daemon stopping")
    for task in (bridge_task, reaper_task, idle_task):
        task.cancel()
    await asyncio.gather(
        bridge_task, reaper_task, idle_task,
        return_exceptions=True,
    )

    # Stop all workers gracefully.
    await manager.shutdown_all(timeout=20.0)

    try:
        await redis.aclose()
    except Exception:
        log.exception("error closing Redis connection")

    log.info("daemon stopped")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    configure_logging(args.log_level)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `worker_pool/manager.py`

```python
"""Worker pool manager.

Spawns, tracks, stops, and reconciles worker processes. This is the
process-lifecycle layer: it does not know about Redis streams, does not
publish events, and does not enforce idle timeouts. Those are the
daemon's job. The manager gives the daemon four primitives:

    start_worker(session_id, simulation_id, config_params)
    stop_worker(session_id, reason)
    reap_dead_workers()
    reconcile_on_startup()

plus an `active_sessions()` snapshot for diagnostics.

Design notes:

- Workers are spawned with start_new_session=True so they detach from
  the daemon's process group. If the daemon dies, workers keep running,
  and a restart can adopt them via Redis heartbeats.
- Graceful stop is SIGTERM, then a wait of WORKER_STOP_GRACE seconds,
  then SIGKILL. Port leases are released only after the process is gone.
- Reconciliation on startup uses Redis heartbeats as the source of
  truth. A worker is alive if its heartbeat key exists AND its PID
  responds to signal 0.
- All mutations of the worker dict take an asyncio.Lock. Concurrent
  start_worker calls do not race on port allocation.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import redis.asyncio as aioredis

from shared.constants import (
    REDIS_HEARTBEAT_PREFIX,
    WORKER_STOP_GRACE,
)
from shared.logging import get_logger
from worker_pool.port_allocator import PortAllocator


log = get_logger(__name__)


# Time to wait after spawning before checking whether the worker is
# still alive. Catches bad-arg and port-conflict failures quickly.
_STARTUP_LIVENESS_CHECK = 1.0


class WorkerManagerError(RuntimeError):
    """Base for manager errors."""


class AlreadyRunningError(WorkerManagerError):
    """A worker already exists for this session_id."""


class WorkerStartupError(WorkerManagerError):
    """The worker process exited during startup."""


@dataclass
class SpawnedWorker:
    """Bookkeeping for one running worker."""

    session_id: str
    simulation_id: str
    port: int
    pid: int
    process: asyncio.subprocess.Process | None   # None for adopted workers
    started_at: float
    config_params: dict[str, Any] = field(default_factory=dict)

    @property
    def uptime(self) -> float:
        return time.time() - self.started_at

    @property
    def adopted(self) -> bool:
        """True if this record came from reconciliation, not this run."""
        return self.process is None


def _pid_alive(pid: int) -> bool:
    """Return True if a process with this PID exists and is signalable.

    os.kill with signal 0 performs the existence and permission checks
    without actually sending a signal. ProcessLookupError means no such
    process exists. PermissionError means it exists but is owned by
    another user, which we treat as alive from our perspective.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class WorkerPoolManager:
    """Spawns and tracks worker processes. See module docstring."""

    def __init__(
        self,
        *,
        redis: aioredis.Redis,
        port_allocator: PortAllocator,
        advertise_host: str,
        python_executable: str | None = None,
        worker_module: str = "worker_pool.worker.main",
        log_level: str = "INFO",
    ) -> None:
        self._redis = redis
        self._allocator = port_allocator
        self._advertise_host = advertise_host
        self._python = python_executable or sys.executable
        self._worker_module = worker_module
        self._log_level = log_level

        self._lock = asyncio.Lock()
        self._workers: dict[str, SpawnedWorker] = {}
        self._log_tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    async def start_worker(
        self,
        *,
        session_id: str,
        simulation_id: str,
        config_params: dict[str, Any] | None = None,
    ) -> SpawnedWorker:
        """Spawn a new worker process and track it.

        Raises AlreadyRunningError if session_id is already tracked.
        Raises WorkerStartupError if the process exits during startup.
        """
        async with self._lock:
            if session_id in self._workers:
                raise AlreadyRunningError(
                    f"worker for {session_id!r} is already tracked"
                )

        port = await self._allocator.acquire(session_id)

        try:
            proc = await self._spawn_process(
                session_id=session_id,
                simulation_id=simulation_id,
                port=port,
                config_params=config_params or {},
            )
        except Exception:
            await self._allocator.release(port, session_id)
            raise

        record = SpawnedWorker(
            session_id=session_id,
            simulation_id=simulation_id,
            port=port,
            pid=proc.pid,
            process=proc,
            started_at=time.time(),
            config_params=config_params or {},
        )

        # Fast-fail detection: give the worker a moment to crash on
        # bad args, missing plugin, or port conflict.
        await asyncio.sleep(_STARTUP_LIVENESS_CHECK)
        if proc.returncode is not None:
            await self._allocator.release(port, session_id)
            raise WorkerStartupError(
                f"worker for {session_id!r} exited during startup "
                f"with code {proc.returncode}"
            )

        async with self._lock:
            self._workers[session_id] = record
        self._log_tasks[session_id] = asyncio.create_task(
            self._pipe_logs(record),
            name=f"logs-{session_id}",
        )

        log.info("worker spawned", extra={
            "session_id": session_id,
            "simulation_id": simulation_id,
            "port": port,
            "pid": proc.pid,
        })
        return record

    async def _spawn_process(
        self,
        *,
        session_id: str,
        simulation_id: str,
        port: int,
        config_params: dict[str, Any],
    ) -> asyncio.subprocess.Process:
        env = {
            **os.environ,
            "SIM_MANAGED": "1",
            "LOG_LEVEL": self._log_level,
        }
        cmd = [
            self._python, "-m", self._worker_module,
            "--session-id", session_id,
            "--simulation-id", simulation_id,
            "--opcua-port", str(port),
            "--advertise-host", self._advertise_host,
            "--config", json.dumps({"params": config_params}),
        ]
        return await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )

    # ------------------------------------------------------------------
    # Stop
    # ------------------------------------------------------------------

    async def stop_worker(
        self, session_id: str, *, reason: str = "user_request"
    ) -> bool:
        """Stop a worker by session_id. Returns True if one was stopped.

        Sends SIGTERM, waits up to WORKER_STOP_GRACE seconds for exit,
        then SIGKILL. Releases the port only after the process is gone.
        """
        async with self._lock:
            record = self._workers.get(session_id)

        if record is None:
            return False

        await self._terminate(record)
        await self._allocator.release(record.port, session_id)

        async with self._lock:
            self._workers.pop(session_id, None)
        task = self._log_tasks.pop(session_id, None)
        if task is not None:
            task.cancel()

        log.info("worker stopped", extra={
            "session_id": session_id,
            "reason": reason,
            "pid": record.pid,
        })
        return True

    async def _terminate(self, record: SpawnedWorker) -> None:
        """Terminate a worker gracefully, escalating to SIGKILL if needed."""
        if not _pid_alive(record.pid):
            return

        try:
            os.kill(record.pid, signal.SIGTERM)
        except ProcessLookupError:
            return

        deadline = time.monotonic() + WORKER_STOP_GRACE
        while time.monotonic() < deadline and _pid_alive(record.pid):
            await asyncio.sleep(0.2)

        if _pid_alive(record.pid):
            log.warning(
                "worker did not exit on SIGTERM; sending SIGKILL",
                extra={"session_id": record.session_id, "pid": record.pid},
            )
            try:
                os.kill(record.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        # If we have a handle, reap the zombie so the kernel frees the PID.
        if record.process is not None:
            try:
                await asyncio.wait_for(record.process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                pass

    # ------------------------------------------------------------------
    # Reap and reconcile
    # ------------------------------------------------------------------

    async def reap_dead_workers(self) -> list[str]:
        """Detect and clean up workers whose processes have exited.

        Called periodically by the daemon. Returns session IDs that
        were reaped.
        """
        async with self._lock:
            candidates = list(self._workers.values())

        reaped: list[str] = []
        for record in candidates:
            if _pid_alive(record.pid):
                continue
            log.info("reaping dead worker", extra={
                "session_id": record.session_id,
                "pid": record.pid,
                "port": record.port,
            })
            await self._allocator.release(record.port, record.session_id)
            async with self._lock:
                self._workers.pop(record.session_id, None)
            task = self._log_tasks.pop(record.session_id, None)
            if task is not None:
                task.cancel()
            reaped.append(record.session_id)
        return reaped

    async def reconcile_on_startup(self) -> None:
        """Adopt workers that survived a daemon restart; drop dead ones.

        Uses Redis heartbeats as the source of truth. A worker is alive
        if its heartbeat key exists and its PID responds to signal 0.
        """
        keys = await self._redis.keys(f"{REDIS_HEARTBEAT_PREFIX}*")
        adopted: list[str] = []
        dropped: list[str] = []

        for key in keys:
            session_id = key.split(":", 2)[-1] if ":" in key else key
            raw = await self._redis.get(key)
            if not raw:
                continue

            try:
                hb = json.loads(raw)
                pid = int(hb["pid"])
                port = int(hb["port"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                await self._redis.delete(key)
                dropped.append(session_id)
                continue

            if not _pid_alive(pid):
                await self._redis.delete(key)
                dropped.append(session_id)
                continue

            record = SpawnedWorker(
                session_id=session_id,
                simulation_id=str(hb.get("simulation_id", "")),
                port=port,
                pid=pid,
                process=None,   # adopted; no Popen handle
                started_at=time.time() - float(hb.get("uptime", 0.0)),
            )
            async with self._lock:
                self._workers[session_id] = record
            adopted.append(session_id)

        # Drop stale port leases whose session no longer exists.
        await self._allocator.reconcile(set(adopted))

        log.info("startup reconciliation", extra={
            "adopted": len(adopted),
            "dropped": len(dropped),
        })

    # ------------------------------------------------------------------
    # Introspection and shutdown
    # ------------------------------------------------------------------

    def active_sessions(self) -> list[dict[str, Any]]:
        """Snapshot of currently tracked workers. Read-only."""
        return [
            {
                "session_id": r.session_id,
                "simulation_id": r.simulation_id,
                "port": r.port,
                "pid": r.pid,
                "uptime": round(r.uptime, 1),
                "adopted": r.adopted,
            }
            for r in self._workers.values()
        ]

    def is_tracked(self, session_id: str) -> bool:
        return session_id in self._workers

    async def shutdown_all(self, *, timeout: float = 15.0) -> None:
        """Stop every tracked worker. Called on daemon shutdown."""
        async with self._lock:
            session_ids = list(self._workers.keys())
        if not session_ids:
            return

        log.info("shutting down all workers",
                 extra={"count": len(session_ids)})
        tasks = [
            asyncio.create_task(
                self.stop_worker(sid, reason="daemon_shutdown"),
                name=f"stop-{sid}",
            )
            for sid in session_ids
        ]
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            log.warning("shutdown_all timed out; some workers may remain")

    # ------------------------------------------------------------------
    # Log piping
    # ------------------------------------------------------------------

    async def _pipe_logs(self, record: SpawnedWorker) -> None:
        """Forward the child's stdout into the daemon's structured logger.

        Workers emit JSON logs; we pass them through as the ``line``
        field so the daemon's own fields are stamped on every record
        without duplicating the worker's context.
        """
        proc = record.process
        if proc is None or proc.stdout is None:
            return
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    log.info("worker", extra={
                        "session_id": record.session_id,
                        "line": text,
                    })
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("log pipe failed",
                          extra={"session_id": record.session_id})
```

### `worker_pool/port_allocator.py`

```python
"""Async Redis-backed port pool for OPC UA workers.

Port state lives in Redis, not process memory, so daemon restarts do not
lose leases. Acquisition uses HSETNX, which is atomic: two callers racing
for the same port cannot both win. Release is a conditional HDEL so a
late release from a crashed worker cannot clobber a new lease on the
same port.

All methods are async because the daemon runs on asyncio. A synchronous
client would block the event loop during every acquire and release.
"""

from __future__ import annotations

from typing import Iterator

import redis.asyncio as aioredis

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
        client: aioredis.Redis,
        start: int | None = None,
        end: int | None = None,
    ) -> None:
        self._r = client
        self._start = start if start is not None else OPCUA_PORT_START
        self._end = end if end is not None else OPCUA_PORT_END
        if self._start >= self._end:
            raise ValueError(f"Invalid port range: {self._start}..{self._end}")

    async def acquire(self, session_id: str) -> int:
        """Lease a free port to session_id. Raises PortPoolExhausted if none."""
        for port in self._ports():
            # HSETNX returns 1 if created, 0 if the field already existed.
            if await self._r.hsetnx(REDIS_PORT_LEASES, str(port), session_id):
                log.info("port leased",
                         extra={"port": port, "session_id": session_id})
                return port
        raise PortPoolExhausted(
            f"All ports in {self._start}..{self._end} are leased"
        )

    async def release(self, port: int, session_id: str) -> bool:
        """Release a port only if still leased to session_id.

        Returns True if released, False if the lease had already been
        reclaimed or reassigned.
        """
        released = await self._r.eval(
            _RELEASE_SCRIPT, 1, REDIS_PORT_LEASES, str(port), session_id
        )
        if released:
            log.info("port released",
                     extra={"port": port, "session_id": session_id})
        else:
            log.warning(
                "port release ignored (not owned)",
                extra={"port": port, "session_id": session_id},
            )
        return bool(released)

    async def reconcile(self, live_session_ids: set[str]) -> list[int]:
        """Drop leases whose owning session no longer exists.

        Called on daemon startup so a crash mid-spawn does not leak
        ports until the process that owns them is finally gone.
        """
        leases = await self._r.hgetall(REDIS_PORT_LEASES)
        dropped: list[int] = []
        for port_b, sid_b in leases.items():
            sid = sid_b.decode() if isinstance(sid_b, bytes) else sid_b
            if sid not in live_session_ids:
                await self._r.hdel(REDIS_PORT_LEASES, port_b)
                dropped.append(int(port_b))
        if dropped:
            log.warning("reconciled stale port leases",
                        extra={"ports": dropped})
        return dropped

    async def snapshot(self) -> dict[int, str]:
        """Current {port: session_id} map. For diagnostics and admin UI."""
        raw = await self._r.hgetall(REDIS_PORT_LEASES)
        return {
            int(p): (s.decode() if isinstance(s, bytes) else s)
            for p, s in raw.items()
        }

    def _ports(self) -> Iterator[int]:
        # Linear scan from the bottom of the range. At 101 ports the
        # extra HGET per acquire is invisible; a cursor would only
        # matter at 10k+.
        for port in range(self._start, self._end + 1):
            yield port
```

### `worker_pool/redis_bridge.py`

```python
"""Redis Streams bridge for the worker pool daemon.

Consumes StartSessionCommand and StopSessionCommand from the command
stream, dispatches them to the manager, and publishes lifecycle events
back on the event stream. The daemon also uses this bridge to publish
events it generates itself — worker crashes, reconciliation actions,
shutdown notices.

Why streams and not pub/sub: a daemon restart must not lose commands
that were published while it was down. With streams, unacked messages
remain in the consumer group's pending list and are delivered again on
reconnect. Pub/sub would silently drop them.

At-least-once delivery means command handlers must be idempotent.
Starting an already-tracked session raises AlreadyRunningError, which
the bridge catches and translates to a SessionFailedEvent rather than
retrying forever. Stopping an untracked session returns False, which
is harmless.

The consumer name includes the daemon PID. A restarted daemon reads as
a fresh consumer, so its own previous pending messages are reclaimed
via XAUTOCLAIM on startup rather than sitting in the old consumer's
pending list forever.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from shared.constants import (
    CMD_CONSUMER_GROUP,
    REDIS_CMD_STREAM,
    REDIS_EVT_STREAM,
    STREAM_MAXLEN,
)
from shared.logging import get_logger
from shared.schemas import (
    Command,
    Event,
    PingCommand,
    SessionFailedEvent,
    SessionStartedEvent,
    SessionStoppedEvent,
    StartSessionCommand,
    StopSessionCommand,
    parse_command,
)
from worker_pool.manager import (
    AlreadyRunningError,
    WorkerManagerError,
    WorkerPoolManager,
    WorkerStartupError,
)


log = get_logger(__name__)


# How long XREADGROUP blocks waiting for a new message. Shorter values
# mean the loop reacts to stop events faster; longer values mean less
# Redis chatter. 2 s is a reasonable middle.
_READ_BLOCK_MS = 2000

# How often to attempt XAUTOCLAIM of messages left pending by a
# previous daemon incarnation that died mid-handler.
_CLAIM_INTERVAL_SEC = 60.0

# Idle threshold for XAUTOCLAIM. A message pending for longer than
# this is considered abandoned by its original consumer.
_CLAIM_MIN_IDLE_MS = 120_000


class RedisBridge:
    """Bridge between the Redis command/event streams and the manager."""

    def __init__(
        self,
        *,
        redis: aioredis.Redis,
        manager: WorkerPoolManager,
        consumer_name: str | None = None,
    ) -> None:
        self._redis = redis
        self._manager = manager
        self._consumer = consumer_name or f"worker-pool-{os.getpid()}"
        self._log = log
        # None = unknown; True/False once we've tried once.
        self._xautoclaim_supported: bool | None = None
    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    async def ensure_group(self) -> None:
        """Create the consumer group if it does not exist.

        id="0" starts delivery from the beginning of the stream, so a
        daemon that restarts after being down for a while still sees
        any unacked commands. MKSTREAM creates the stream itself if
        nothing has ever published to it.
        """
        try:
            await self._redis.xgroup_create(
                REDIS_CMD_STREAM,
                CMD_CONSUMER_GROUP,
                id="0",
                mkstream=True,
            )
            self._log.info("consumer group created",
                           extra={"group": CMD_CONSUMER_GROUP})
        except RedisError as exc:
            if "BUSYGROUP" in str(exc):
                return
            raise

    # ------------------------------------------------------------------
    # Publish (used by daemon and by this bridge)
    # ------------------------------------------------------------------

    async def publish_event(self, event: Event) -> None:
        """Write one event to the events stream. Non-fatal on failure."""
        try:
            await self._redis.xadd(
                REDIS_EVT_STREAM,
                {"payload": event.model_dump_json()},
                maxlen=STREAM_MAXLEN,
                approximate=True,
            )
        except RedisError:
            self._log.exception(
                "failed to publish event",
                extra={"kind": getattr(event, "kind", "unknown")},
            )

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self, stop: asyncio.Event) -> None:
        """Consume commands until the stop event is set.

        Handles one command at a time. Start and stop operations are
        fast enough (sub-second) that concurrency would add complexity
        without benefit. If a slow Redis write stalls the loop, the
        next command waits — which is the desired backpressure.
        """
        last_claim = 0.0

        while not stop.is_set():
            try:
                entries = await asyncio.wait_for(
                    self._redis.xreadgroup(
                        CMD_CONSUMER_GROUP,
                        self._consumer,
                        {REDIS_CMD_STREAM: ">"},
                        count=10,
                        block=_READ_BLOCK_MS,
                    ),
                    timeout=(_READ_BLOCK_MS / 1000.0) + 2.0,
                )
            except asyncio.TimeoutError:
                entries = []
            except RedisError:
                self._log.exception("xreadgroup failed; retrying in 2s")
                await asyncio.sleep(2.0)
                continue

            for _stream, messages in entries or []:
                for msg_id, fields in messages:
                    await self._handle_message(msg_id, fields)

            # Periodically try to reclaim abandoned pending messages.
            now = asyncio.get_event_loop().time()
            if now - last_claim > _CLAIM_INTERVAL_SEC:
                last_claim = now
                await self._claim_abandoned()

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    async def _handle_message(self, msg_id: str, fields: dict[str, Any]) -> None:
        payload = fields.get("payload")
        if not payload:
            self._log.warning("command has no payload",
                              extra={"msg_id": msg_id})
            await self._ack(msg_id)
            return

        try:
            command = parse_command(payload)
        except Exception:
            self._log.exception("unparsable command",
                                extra={"msg_id": msg_id})
            await self._ack(msg_id)
            return

        try:
            await self._dispatch(command)
        except Exception:
            self._log.exception("command handler raised",
                                extra={"kind": command.kind})
        finally:
            await self._ack(msg_id)

    async def _dispatch(self, command: Command) -> None:
        if isinstance(command, StartSessionCommand):
            await self._handle_start(command)
        elif isinstance(command, StopSessionCommand):
            await self._handle_stop(command)
        elif isinstance(command, PingCommand):
            self._log.debug("ping received",
                            extra={"request_id": command.request_id})
        else:
            self._log.warning("unknown command kind",
                              extra={"kind": getattr(command, "kind", "?")})

    async def _handle_start(self, cmd: StartSessionCommand) -> None:
        self._log.info("start command received", extra={
            "session_id": cmd.session_id,
            "simulation_id": cmd.simulation_id,
            "request_id": cmd.request_id,
        })

        try:
            record = await self._manager.start_worker(
                session_id=cmd.session_id,
                simulation_id=cmd.simulation_id,
                config_params=cmd.config_params,
            )
        except AlreadyRunningError:
            self._log.info("start ignored; session already running",
                           extra={"session_id": cmd.session_id})
            return
        except WorkerStartupError as exc:
            await self.publish_event(SessionFailedEvent(
                session_id=cmd.session_id,
                error=f"startup failed: {exc}",
            ))
            return
        except WorkerManagerError as exc:
            await self.publish_event(SessionFailedEvent(
                session_id=cmd.session_id,
                error=f"manager error: {exc}",
            ))
            return

        await self.publish_event(SessionStartedEvent(
            session_id=record.session_id,
            simulation_id=record.simulation_id,
            port=record.port,
            pid=record.pid,
            systemd_unit="",   # not used with subprocess spawning
            advertised_endpoint="",
            request_id=cmd.request_id,
        ))

    async def _handle_stop(self, cmd: StopSessionCommand) -> None:
        self._log.info("stop command received", extra={
            "session_id": cmd.session_id,
            "reason": cmd.reason,
            "request_id": cmd.request_id,
        })

        stopped = await self._manager.stop_worker(
            cmd.session_id, reason=cmd.reason,
        )
        if not stopped:
            self._log.info("stop ignored; session not tracked",
                           extra={"session_id": cmd.session_id})

        await self.publish_event(SessionStoppedEvent(
            session_id=cmd.session_id,
            exit_code=0 if stopped else None,
            reason=cmd.reason,
        ))

    # ------------------------------------------------------------------
    # Pending message recovery
    # ------------------------------------------------------------------

    async def _claim_abandoned(self) -> None:
        """Take over messages abandoned by a previous consumer.

        XAUTOCLAIM requires Redis 6.2+. On older servers the command
        returns an error; we detect that once and disable the feature
        for the lifetime of the bridge. Recovery is a safety net for
        daemon crashes mid-handle, not a correctness requirement.
        """
        if self._xautoclaim_supported is False:
            return

        try:
            result = await self._redis.xautoclaim(
                REDIS_CMD_STREAM,
                CMD_CONSUMER_GROUP,
                self._consumer,
                min_idle_time=_CLAIM_MIN_IDLE_MS,
                start_id="0-0",
                count=10,
            )
        except RedisError as exc:
            msg = str(exc).lower()
            if "unknown command" in msg and "xautoclaim" in msg:
                if self._xautoclaim_supported is None:
                    self._log.warning(
                        "XAUTOCLAIM not supported by this Redis; "
                        "abandoned-message recovery disabled. "
                        "Upgrade to Redis 6.2 or newer to enable."
                    )
                self._xautoclaim_supported = False
                return
            self._log.exception("xautoclaim failed")
            return

        if self._xautoclaim_supported is None:
            self._xautoclaim_supported = True

        # asyncua-client returns (next_cursor, messages, deleted_ids)
        if not result:
            return
        _, messages, *_ = result
        if not messages:
            return

        self._log.info("reclaimed abandoned commands",
                       extra={"count": len(messages)})
        for msg_id, fields in messages:
            await self._handle_message(msg_id, fields)
            
    # ------------------------------------------------------------------
    # Ack helper
    # ------------------------------------------------------------------

    async def _ack(self, msg_id: str) -> None:
        try:
            await self._redis.xack(
                REDIS_CMD_STREAM, CMD_CONSUMER_GROUP, msg_id,
            )
        except RedisError:
            # If ack fails, the message remains pending and will be
            # reclaimed later. Not fatal.
            self._log.warning("xack failed",
                              extra={"msg_id": msg_id})
```

### `worker_pool/worker/main.py`

```python
"""Worker process entrypoint.

One worker runs exactly one simulation session:

    1. Loads a plugin from the registry
    2. Builds the OPC UA address space
    3. Starts the HTTP dashboard in a background thread
    4. Publishes a heartbeat to Redis every HEARTBEAT_INTERVAL seconds
    5. Runs the OPC UA tick loop until SIGTERM
    6. Cleans up (heartbeat key, idle key, PID file) before exit

Run by the daemon as a subprocess (see worker_pool/manager.py). Can also
be run by hand for development; see --help.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from shared.constants import (
    HEARTBEAT_INTERVAL,
    HEARTBEAT_TTL,
    HTTP_PORT_OFFSET,
    PID_DIR,
    REDIS_EVT_STREAM,
    REDIS_HEARTBEAT_PREFIX,
    REDIS_IDLE_PREFIX,
    STREAM_MAXLEN,
)
from shared.logging import configure_logging, get_logger
from shared.schemas import SessionReadyEvent
from sim_runtime.base import SimulationConfig
from sim_runtime.http_adapter import HTTPDashboard
from sim_runtime.opcua_adapter import OPCUAAdapter
from sim_runtime.registry import SimulationRegistry


log = get_logger(__name__)


# Fallback PID directory when the configured one is not writable (e.g. dev
# runs outside systemd). Real deploys use PID_DIR.
_FALLBACK_PID_DIR = Path("/tmp/cip-sim-pids")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run one simulation worker.")
    p.add_argument("--session-id", required=True)
    p.add_argument("--simulation-id", required=True)
    p.add_argument("--opcua-port", type=int, required=True)
    p.add_argument("--advertise-host", required=True,
                   help="Host or IP that OPC UA clients will use to connect.")
    p.add_argument("--http-host", default="0.0.0.0")
    p.add_argument("--http-port", type=int, default=None,
                   help=f"Defaults to opcua_port + {HTTP_PORT_OFFSET}.")
    p.add_argument("--config", default="{}",
                   help="JSON config passed to the plugin as SimulationConfig.params.")
    return p.parse_args(argv)


def _parse_config(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--config is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit("--config must be a JSON object")
    # Accept either {"params": {...}} or a flat dict; flat is treated as params.
    return parsed.get("params", parsed)


# ---------------------------------------------------------------------------
# Heartbeat
# ---------------------------------------------------------------------------

async def _heartbeat_loop(
    r: aioredis.Redis,
    *,
    session_id: str,
    simulation_id: str,
    port: int,
    adapter: OPCUAAdapter,
    stop: asyncio.Event,
) -> None:
    """Publish worker liveness and idle timestamp to Redis every interval.

    Two keys, both with TTL so a crash cleans up automatically:

        cip:hb:<sid>    JSON heartbeat, refreshed every HEARTBEAT_INTERVAL
        cip:idle:<sid>  Unix timestamp of the last external OPC UA activity

    The heartbeat payload includes simulation_id so the gateway can
    discover what plugin a session is running when it reconciles on
    startup, without needing a separate metadata key.

    The first heartbeat is written immediately so the worker is visible
    to the gateway and to reconciliation without an interval-long delay.
    """
    hb_key = f"{REDIS_HEARTBEAT_PREFIX}{session_id}"
    idle_key = f"{REDIS_IDLE_PREFIX}{session_id}"

    start_mono = time.monotonic()
    last_seen_count = 0
    last_activity_wall = time.time()

    async def write_heartbeat() -> None:
        nonlocal last_seen_count, last_activity_wall
        count = adapter.external_request_count()
        if count != last_seen_count:
            last_seen_count = count
            last_activity_wall = time.time()

        payload = json.dumps({
            "pid": os.getpid(),
            "port": port,
            "simulation_id": simulation_id,
            "uptime": round(time.monotonic() - start_mono, 1),
            "requests": count,
        })
        try:
            await r.set(hb_key, payload, ex=HEARTBEAT_TTL)
            await r.set(idle_key, str(int(last_activity_wall)),
                        ex=HEARTBEAT_TTL * 2)
        except RedisError:
            log.exception("heartbeat write failed; will retry next interval")

    # Immediate first heartbeat.
    await write_heartbeat()

    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_INTERVAL)
            return  # stop was set during the wait
        except asyncio.TimeoutError:
            pass
        await write_heartbeat()


# ---------------------------------------------------------------------------
# PID file
# ---------------------------------------------------------------------------

def _write_pid_file(session_id: str) -> Path | None:
    """Write our PID to a well-known path. Returns the path, or None on failure.

    The daemon uses PID files only as an advisory signal; Redis heartbeats
    are the authoritative liveness check. If we cannot create the file
    (permissions, unwritable directory), we log and continue.
    """
    for candidate in (Path(PID_DIR), _FALLBACK_PID_DIR):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            path = candidate / f"{session_id}.pid"
            path.write_text(str(os.getpid()))
            return path
        except OSError:
            continue
    log.warning("could not write PID file; proceeding without one")
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def _run(args: argparse.Namespace) -> int:
    registry = SimulationRegistry()
    registry.load_from()

    try:
        sim_class = registry.get(args.simulation_id)
    except Exception as exc:
        log.error("cannot load simulation", extra={
            "simulation_id": args.simulation_id, "error": str(exc)
        })
        return 2

    sim = sim_class(SimulationConfig(
        session_id=args.session_id,
        params=_parse_config(args.config),
    ))

    http_port = args.http_port if args.http_port is not None else (
        args.opcua_port + HTTP_PORT_OFFSET
    )

    adapter = OPCUAAdapter(
        sim,
        advertise_host=args.advertise_host,
        port=args.opcua_port,
    )
    dashboard = HTTPDashboard(
        sim,
        host=args.http_host,
        port=http_port,
        session_id=args.session_id,
        endpoint=adapter.endpoint,
    )

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = aioredis.from_url(redis_url, decode_responses=True)

    hb_key = f"{REDIS_HEARTBEAT_PREFIX}{args.session_id}"
    idle_key = f"{REDIS_IDLE_PREFIX}{args.session_id}"

    log.info("worker starting", extra={
        "session_id": args.session_id,
        "simulation_id": args.simulation_id,
        "endpoint": adapter.endpoint,
        "http_port": http_port,
        "pid": os.getpid(),
    })

    # Build the address space before publishing "ready". Any schema error
    # fails fast here rather than three seconds into the tick loop.
    await adapter.initialize()

    # Publish ready BEFORE the port is bound. The tiny race between this
    # event and the actual bind is acceptable: if bind fails a moment later,
    # the process exits non-zero and the daemon marks the session failed.
    try:
        ready = SessionReadyEvent(
            session_id=args.session_id,
            simulation_id=args.simulation_id,
            port=args.opcua_port,
            pid=os.getpid(),
        )
        await r.xadd(
            REDIS_EVT_STREAM,
            {"payload": ready.model_dump_json()},
            maxlen=STREAM_MAXLEN,
        )
    except RedisError:
        log.exception("failed to publish ready event; continuing anyway")

    pid_path = _write_pid_file(args.session_id)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    dashboard.start()

    failed = False

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                adapter.run(stop),
                name=f"opcua-{args.session_id}",
            )
            tg.create_task(
                _heartbeat_loop(
                    r,
                    session_id=args.session_id,
                    simulation_id=args.simulation_id,
                    port=args.opcua_port,
                    adapter=adapter,
                    stop=stop,
                ),
                name=f"heartbeat-{args.session_id}",
            )
    except* Exception as eg:
        # TaskGroup wraps errors. Log each and remember that something
        # went wrong; we return non-zero below so the daemon marks the
        # session as failed rather than cleanly stopped.
        #
        # Note: `return` is not allowed inside an `except*` block. Setting
        # a flag and returning after the try/except*/finally is the
        # standard workaround.
        for exc in eg.exceptions:
            log.error("worker task failed", extra={"error": repr(exc)})
        failed = True
    finally:
        dashboard.stop()
        try:
            await r.delete(hb_key, idle_key)
        except RedisError:
            log.exception("failed to remove heartbeat keys")
        if pid_path is not None:
            try:
                pid_path.unlink(missing_ok=True)
            except OSError:
                log.exception("failed to remove PID file")
        try:
            await r.aclose()
        except Exception:
            pass

    if failed:
        return 1

    log.info("worker exited cleanly")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    args = _parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

