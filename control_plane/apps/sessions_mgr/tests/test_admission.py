"""Session creation capacity and per-client rate limits."""

from __future__ import annotations

from unittest.mock import patch

import fakeredis
import redis
from django.test import TestCase

from control_plane.apps.sessions_mgr.models import Session, SimulationCatalog
from control_plane.apps.sessions_mgr.serializers import (
    SessionDetailSerializer,
    SessionSummarySerializer,
)
from control_plane.apps.sessions_mgr import views
from control_plane.apps.sessions_mgr import orchestrator
from shared.constants import (
    CREATE_RATE_WINDOW_SECONDS,
    CREATE_REQUESTS_PER_MINUTE,
    MAX_CONCURRENT_SESSIONS,
)


class SessionAdmissionTests(TestCase):
    def setUp(self) -> None:
        self._request_start_impl = orchestrator.request_start
        self.redis = fakeredis.FakeRedis(decode_responses=True)
        self.addCleanup(self.redis.close)
        self.redis_patcher = patch(
            "control_plane.apps.sessions_mgr.views._get_admission_client",
            return_value=self.redis,
        )
        self.redis_patcher.start()
        self.addCleanup(self.redis_patcher.stop)

        self.start_patcher = patch(
            "control_plane.apps.sessions_mgr.views.orchestrator.request_start"
        )
        self.start_patcher.start()
        self.addCleanup(self.start_patcher.stop)

        self.stop_patcher = patch(
            "control_plane.apps.sessions_mgr.views.orchestrator.request_stop"
        )
        self.stop_patcher.start()
        self.addCleanup(self.stop_patcher.stop)

        SimulationCatalog.objects.create(
            simulation_id="test-sim",
            display_name="Test Simulation",
            version="1.0.0",
        )

    def _create(self, *, slug: str | None = None, remote_addr: str = "192.0.2.1"):
        payload = {"simulation_id": "test-sim"}
        if slug is not None:
            payload["slug"] = slug
        return self.client.post(
            "/api/sessions/",
            payload,
            content_type="application/json",
            REMOTE_ADDR=remote_addr,
        )

    def test_creation_succeeds_below_capacity(self):
        response = self._create()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Session.objects.count(), 1)

    def test_creation_is_rejected_at_active_session_cap(self):
        Session.objects.bulk_create([
            Session(simulation_id="test-sim", status=Session.STATUS_RUNNING)
            for _ in range(MAX_CONCURRENT_SESSIONS)
        ])

        response = self._create()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(Session.objects.count(), MAX_CONCURRENT_SESSIONS)
        self.assertEqual(response["Retry-After"], "30")

    def test_stopped_and_failed_sessions_do_not_count_toward_cap(self):
        Session.objects.bulk_create([
            Session(simulation_id="test-sim", status=Session.STATUS_STOPPED)
            for _ in range(MAX_CONCURRENT_SESSIONS)
        ] + [
            Session(simulation_id="test-sim", status=Session.STATUS_FAILED)
            for _ in range(MAX_CONCURRENT_SESSIONS)
        ])

        response = self._create()

        self.assertEqual(response.status_code, 201)

    def test_replacing_slug_is_allowed_at_capacity(self):
        Session.objects.bulk_create([
            Session(
                simulation_id="test-sim",
                slug="replace_me",
                status=Session.STATUS_RUNNING,
            ),
            *[
                Session(simulation_id="test-sim", status=Session.STATUS_RUNNING)
                for _ in range(MAX_CONCURRENT_SESSIONS - 1)
            ],
        ])

        response = self._create(slug="replace_me")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Session.objects.filter(status=Session.STATUS_RUNNING).count(),
            MAX_CONCURRENT_SESSIONS - 1,
        )
        self.assertEqual(
            Session.objects.filter(status=Session.STATUS_PENDING).count(),
            1,
        )

    def test_eleventh_create_from_same_ip_is_rate_limited(self):
        responses = [self._create() for _ in range(
            CREATE_REQUESTS_PER_MINUTE + 1
        )]

        self.assertEqual(
            [response.status_code for response in responses],
            [201] * CREATE_REQUESTS_PER_MINUTE + [429],
        )
        self.assertEqual(
            responses[-1]["Retry-After"],
            str(CREATE_RATE_WINDOW_SECONDS),
        )

    def test_rate_limit_uses_remote_addr_not_forwarded_header(self):
        responses = [
            self.client.post(
                "/api/sessions/",
                {"simulation_id": "test-sim"},
                content_type="application/json",
                REMOTE_ADDR="192.0.2.1",
                HTTP_X_FORWARDED_FOR=f"198.51.100.{index}",
            )
            for index in range(CREATE_REQUESTS_PER_MINUTE + 1)
        ]

        self.assertEqual(responses[-1].status_code, 429)

    def test_different_client_ips_have_independent_rate_limits(self):
        first_ip = [
            self._create(remote_addr="192.0.2.1")
            for _ in range(CREATE_REQUESTS_PER_MINUTE)
        ]
        second_ip = self._create(remote_addr="192.0.2.2")

        self.assertTrue(all(response.status_code == 201 for response in first_ip))
        self.assertEqual(second_ip.status_code, 201)

    def test_rate_limit_uses_required_redis_key_prefix_and_ip(self):
        response = self._create(remote_addr="192.0.2.77")

        self.assertEqual(response.status_code, 201)
        keys = self.redis.keys("cip:ratelimit:create:192.0.2.77:*")
        self.assertEqual(len(keys), 1)

    def test_capacity_lock_is_exclusive_and_owner_checked_on_release(self):
        first_token = views._acquire_session_creation_lock(self.redis)
        with patch.object(views, "CREATE_LOCK_WAIT_SECONDS", 0.01):
            with self.assertRaises(views.SessionCreationLockBusy):
                views._acquire_session_creation_lock(self.redis)

        views._release_session_creation_lock(self.redis, first_token)
        second_token = views._acquire_session_creation_lock(self.redis)
        views._release_session_creation_lock(self.redis, first_token)

        self.assertEqual(
            self.redis.get(views.CREATE_LOCK_KEY),
            second_token,
        )
        views._release_session_creation_lock(self.redis, second_token)

    def test_rate_limiter_fails_open_when_redis_eval_fails(self):
        original_eval = self.redis.eval

        def eval_with_rate_limit_failure(script, *args, **kwargs):
            if "local time = redis.call" in script:
                raise redis.ConnectionError("offline")
            return original_eval(script, *args, **kwargs)

        with patch.object(
            self.redis, "eval", side_effect=eval_with_rate_limit_failure
        ):
            response = self._create()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Session.objects.count(), 1)

    def test_session_credentials_are_created_only_for_start_command(self):
        session = Session.objects.create(
            simulation_id="test-sim",
            status=Session.STATUS_PENDING,
        )

        with (
            patch.object(orchestrator, "OPCUA_AUTH_MODE", "per_session"),
            patch.object(orchestrator, "_publish") as publish,
        ):
            self._request_start_impl(session)

        command = publish.call_args.args[0]
        session.refresh_from_db()
        self.assertEqual(command.opcua_username, session.opcua_username)
        self.assertEqual(command.opcua_password, session.opcua_password)
        self.assertTrue(session.opcua_username)
        self.assertTrue(session.opcua_password)

    def test_credentials_are_only_in_detail_serializer(self):
        session = Session.objects.create(
            simulation_id="test-sim",
            opcua_username="worker-user",
            opcua_password="worker-password",
        )

        summary = SessionSummarySerializer(session).data
        detail = SessionDetailSerializer(session).data

        self.assertNotIn("opcua_username", summary)
        self.assertNotIn("opcua_password", summary)
        self.assertEqual(detail["opcua_username"], "worker-user")
        self.assertEqual(detail["opcua_password"], "worker-password")
