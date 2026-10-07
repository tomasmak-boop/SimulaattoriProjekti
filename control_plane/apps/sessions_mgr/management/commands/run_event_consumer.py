"""Consume lifecycle events from the daemon and update the database.

Long-lived process. Reads the events stream via a consumer group,
updates the corresponding Session row, appends a SessionEvent, and
XACKs. Run as a systemd service in production, or by hand during
development:

    python manage.py run_event_consumer
"""

from __future__ import annotations

import asyncio
import uuid

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

        session = _lookup_session(event.session_id)
        if session is None:
            log.warning("event for unknown session",
                        extra={"session_id": event.session_id,
                               "session_name": event.session_name,
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
            # The worker is accepting connections now. Record the
            # dashboard port so the control plane can proxy to it.
            session.http_port = event.http_port
            session.save(update_fields=["http_port"])
            _record(session, SessionEvent.EVENT_READY, {
                "port": event.port,
                "http_port": event.http_port,
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


def _lookup_session(session_id: str) -> Session | None:
    """Find a session by its UUID.

    Events carry the UUID in session_id and the display name in
    session_name. Lookup is unambiguous even when a slug has been
    reused across sessions.
    """
    try:
        uuid.UUID(session_id)
    except (ValueError, TypeError):
        return None
    return Session.objects.filter(id=session_id).first()


def _record(session: Session, event: str, detail: dict) -> None:
    SessionEvent.objects.create(
        session=session, event=event, detail=detail or {},
    )