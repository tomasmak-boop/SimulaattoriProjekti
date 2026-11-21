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

import time
import uuid

import redis

from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
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
from shared.constants import (
    CREATE_RATE_LIMIT_PREFIX,
    CREATE_RATE_WINDOW_SECONDS,
    CREATE_REQUESTS_PER_MINUTE,
    MAX_CONCURRENT_SESSIONS,
)
from shared.logging import get_logger


log = get_logger(__name__)

CREATE_LOCK_KEY = "cip:session-create:lock"
CREATE_LOCK_TTL_SECONDS = 30
CREATE_LOCK_WAIT_SECONDS = 5

_RATE_LIMIT_SCRIPT = """
local time = redis.call("TIME")
local now_ms = time[1] * 1000 + math.floor(time[2] / 1000)
local window = math.floor(now_ms / tonumber(ARGV[1]))
local key = KEYS[1] .. tostring(window)
local count = redis.call("INCR", key)
if count == 1 then
    redis.call("PEXPIRE", key, ARGV[1])
end
if count > tonumber(ARGV[2]) then
    return 0
end
return 1
"""

_RELEASE_LOCK_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
end
return 0
"""

_admission_client: redis.Redis | None = None


class SessionCreationLockBusy(Exception):
    """The cross-process session capacity lock was not acquired in time."""


# ---------------------------------------------------------------------------
# Simulations
# ---------------------------------------------------------------------------

@api_view(["GET"])
def list_simulations(request):  # noqa: ARG001
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

    If a slug is supplied and already in use, the prior session is
    stopped and its slug released so this request can take it over.
    """
    ser = SessionCreateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    sim_id = ser.validated_data["simulation_id"]
    catalog = SimulationCatalog.objects.get(simulation_id=sim_id)
    slug = ser.validated_data.get("slug")

    # Do not trust X-Forwarded-For unless a trusted proxy is configured.
    client_ip = request.META.get("REMOTE_ADDR")
    if not client_ip:
        return Response(
            {"detail": "could not determine client IP address"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    client = _get_admission_client()
    rate_key = CREATE_RATE_LIMIT_PREFIX + client_ip + ":"
    try:
        allowed = client.eval(
            _RATE_LIMIT_SCRIPT,
            1,
            rate_key,
            CREATE_RATE_WINDOW_SECONDS * 1000,
            CREATE_REQUESTS_PER_MINUTE,
        )
    except redis.RedisError:
        log.warning(
            "session creation rate limit unavailable; allowing request",
            exc_info=True,
        )
        allowed = 1
    if not allowed:
        return Response(
            {"detail": "session creation limit exceeded; try again in a minute"},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(CREATE_RATE_WINDOW_SECONDS)},
        )

    try:
        lock_token = _acquire_session_creation_lock(client)
    except SessionCreationLockBusy:
        return Response(
            {"detail": "session capacity check is busy; retry shortly"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers={"Retry-After": "1"},
        )
    except redis.RedisError:
        log.exception("session capacity lock unavailable")
        return Response(
            {"detail": "session creation is temporarily unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        try:
            if slug:
                _reclaim_slug(slug)
        except Exception:
            log.exception("slug reclaim failed", extra={"slug": slug})
            return Response(
                {"detail": "could not stop prior session using this slug"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            with transaction.atomic():
                active_count = Session.objects.filter(
                    status__in=_ACTIVE_SESSION_STATUSES
                ).count()
                if active_count >= MAX_CONCURRENT_SESSIONS:
                    return Response(
                        {
                            "detail": (
                                "session capacity reached "
                                f"({MAX_CONCURRENT_SESSIONS} active sessions)"
                            )
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE,
                        headers={"Retry-After": "30"},
                    )

                session = Session.objects.create(
                    simulation_id=sim_id,
                    simulation_version=catalog.version,
                    slug=slug,
                    label=ser.validated_data.get("label", ""),
                    config_params=ser.validated_data.get("config_params", {}),
                    status=Session.STATUS_PENDING,
                )
                _record_event(session, SessionEvent.EVENT_CREATED)
        except IntegrityError:
            # Backstop for a slug collision from a writer outside this lock.
            return Response(
                {"detail": f"slug {slug!r} is already in use"},
                status=status.HTTP_409_CONFLICT,
            )
    finally:
        _release_session_creation_lock(client, lock_token)

    try:
        orchestrator.request_start(session)
    except Exception:
        log.exception("failed to publish start command",
                      extra={"session_id": session.external_id()})
        session.status = Session.STATUS_FAILED
        session.save(update_fields=["status"])
        _record_event(
            session, SessionEvent.EVENT_FAILED,
            detail={"error": "could not reach command bus"},
        )
        return Response(
            SessionDetailSerializer(session, context=_ctx()).data,
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        SessionDetailSerializer(session, context=_ctx()).data,
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
            SessionDetailSerializer(session, context=_ctx()).data
        )

    if session.is_terminal:
        return Response(
            SessionDetailSerializer(session, context=_ctx()).data,
            status=status.HTTP_200_OK,
        )

    session.status = Session.STATUS_STOPPING
    session.save(update_fields=["status"])
    _record_event(session, SessionEvent.EVENT_STOPPING)

    try:
        orchestrator.request_stop(session, reason="user_request")
    except Exception:
        log.exception("failed to publish stop command",
                      extra={"session_id": session.external_id()})
        return Response(
            {"detail": "could not reach command bus"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        SessionDetailSerializer(session, context=_ctx()).data
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

_ACTIVE_SESSION_STATUSES = (
    Session.STATUS_PENDING,
    Session.STATUS_STARTING,
    Session.STATUS_RUNNING,
    Session.STATUS_STOPPING,
)


def _get_admission_client() -> redis.Redis:
    global _admission_client
    if _admission_client is None:
        url = getattr(settings, "REDIS_URL", None) or "redis://localhost:6379/0"
        _admission_client = redis.from_url(url, decode_responses=True)
    return _admission_client


def _acquire_session_creation_lock(client: redis.Redis) -> str:
    token = uuid.uuid4().hex
    deadline = time.monotonic() + CREATE_LOCK_WAIT_SECONDS
    while time.monotonic() < deadline:
        if client.set(
            CREATE_LOCK_KEY,
            token,
            nx=True,
            ex=CREATE_LOCK_TTL_SECONDS,
        ):
            return token
        time.sleep(0.05)
    raise SessionCreationLockBusy


def _release_session_creation_lock(client: redis.Redis, token: str) -> None:
    try:
        client.eval(_RELEASE_LOCK_SCRIPT, 1, CREATE_LOCK_KEY, token)
    except redis.RedisError:
        log.exception("failed to release session creation lock")


def _reclaim_slug(slug: str) -> None:
    """Release `slug` from any existing session so a new one can take it.

    Stops the prior session if still live, then clears its slug field
    and moves it to a terminal state. Raises if the stop command
    cannot be published, in which case the prior row is left untouched
    so a retry can succeed later.
    """
    prior = Session.objects.filter(slug=slug).first()
    if prior is None:
        return

    if not prior.is_terminal:
        orchestrator.request_stop(prior, reason="replaced_by_new_session")

    prior.slug = None
    prior.status = Session.STATUS_STOPPED
    prior.stopped_at = timezone.now()
    prior.save(update_fields=["slug", "status", "stopped_at"])

    _record_event(prior, SessionEvent.EVENT_STOPPED, {
        "reason": "replaced_by_new_session",
    })


def _ctx() -> dict:
    return {"gateway_host": getattr(settings, "GATEWAY_PUBLIC_HOST", "")}


def _record_event(session: Session, event: str, detail: dict | None = None) -> None:
    SessionEvent.objects.create(
        session=session,
        event=event,
        detail=detail or {},
    )