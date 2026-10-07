"""HTML views for the operator dashboard.

Reads the same Session rows the REST API does. The list view links each
named session to its dashboard URL; the proxy view that serves those
URLs arrives in Phase 3.
"""

from __future__ import annotations

from django.shortcuts import render

from control_plane.apps.sessions_mgr.models import Session


def session_list(request):
    include_stopped = request.GET.get("include_stopped") in ("1", "true", "yes")
    qs = Session.objects.all()
    if not include_stopped:
        qs = qs.exclude(
            status__in=[Session.STATUS_STOPPED, Session.STATUS_FAILED],
        )
    return render(request, "sessions/list.html", {
        "sessions": qs,
        "include_stopped": include_stopped,
    })