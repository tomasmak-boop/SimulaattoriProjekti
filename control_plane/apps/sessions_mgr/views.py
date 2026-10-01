"""REST API for session management.

Every endpoint is public. Access to a specific session is gated by the
capability token in the URL, not by authentication. This is the design
choice recorded in the project plan: no accounts, no personal data.

Endpoints:

    GET    /api/simulations/          list available simulations
    GET    /api/sessions/             list active sessions (no tokens)
    POST   /api/sessions/             create a session
    GET    /api/sessions/<token>/     session detail (token required)
    DELETE /api/sessions/<token>/     stop a session (token required)
    GET    /api/sessions/<token>/events/   session event log
"""

from __future__ import annotations

from django.conf import settings
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
# Sessions
# ---------------------------------------------------------------------------

@api_view(["GET"])
def list_sessions(request):  # noqa: ARG001
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


@api_view(["POST"])
def create_session(request):
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