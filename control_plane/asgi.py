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