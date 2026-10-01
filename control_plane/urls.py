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