"""URL configuration.

Routes added incrementally as WP4 progresses. This file holds the
health endpoint and the placeholder root; API routes and dashboard
routes are wired in later steps.
"""

from __future__ import annotations

from django.http import HttpRequest, JsonResponse
from django.urls import path


def health(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


def index(_request: HttpRequest) -> JsonResponse:
    return JsonResponse({
        "service": "cip-sim control plane",
        "version": "0.1.0",
        "note": "session API and dashboard are still being built",
    })


urlpatterns = [
    path("health/", health, name="health"),
    path("", index, name="index"),
]