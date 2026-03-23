"""Tests for worker execution — task_delivery, ttl_checker, status_decay, strength_deriver.

Tests worker logic using mocks and actual service method signatures.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import TaskStatus


class TestTaskDeliveryWorker:
    """Test task_delivery worker processes pending tasks."""

    @pytest.mark.asyncio
    async def test_delivery_worker_loop_respects_shutdown(self):
        """Worker loop should exit when shutdown_event is set."""
        from app.workers.task_delivery import run_delivery_worker

        shutdown_event = asyncio.Event()
        shutdown_event.set()  # Set immediately

        with patch(
            "app.workers.task_delivery._process_pending_tasks",
            new_callable=AsyncMock,
        ):
            # Should exit quickly since shutdown is already set
            await asyncio.wait_for(
                run_delivery_worker(shutdown_event),
                timeout=5.0,
            )

    @pytest.mark.asyncio
    async def test_process_pending_tasks_calls_deliver(self):
        """_process_pending_tasks should call deliver_task_to_agent for each task."""
        from app.workers.task_delivery import _process_pending_tasks

        mock_task = MagicMock()
        mock_task.id = "task_001"
        mock_task.status = TaskStatus.PENDING_DELIVERY.value

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_task]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.workers.task_delivery.async_session_factory",
            return_value=mock_session,
        ), patch(
            "app.workers.task_delivery.deliver_task_to_agent",
            new_callable=AsyncMock,
        ) as mock_deliver:
            await _process_pending_tasks()
            mock_deliver.assert_awaited_once_with(mock_session, mock_task)

    def test_poll_interval(self):
        """Poll interval should be 5 seconds."""
        from app.workers.task_delivery import POLL_INTERVAL
        assert POLL_INTERVAL == 5


class TestTTLCheckerWorker:
    """Test ttl_checker worker expires old tasks, intents, introductions."""

    @pytest.mark.asyncio
    async def test_ttl_checker_loop_respects_shutdown(self):
        """TTL checker should exit when shutdown_event is set."""
        from app.workers.ttl_checker import run_ttl_checker

        shutdown_event = asyncio.Event()
        shutdown_event.set()

        with patch(
            "app.workers.ttl_checker._check_expired_tasks",
            new_callable=AsyncMock,
        ), patch(
            "app.workers.ttl_checker._check_expired_intents",
            new_callable=AsyncMock,
        ), patch(
            "app.workers.ttl_checker._check_expired_introductions",
            new_callable=AsyncMock,
        ):
            await asyncio.wait_for(
                run_ttl_checker(shutdown_event),
                timeout=5.0,
            )

    @pytest.mark.asyncio
    async def test_check_expired_tasks_marks_expired(self):
        """Tasks past their expires_at should be marked as expired."""
        from app.workers.ttl_checker import _check_expired_tasks

        mock_task = MagicMock()
        mock_task.id = "task_expired"
        mock_task.status = TaskStatus.PENDING_DELIVERY.value

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_task]

        mock_confirm_result = MagicMock()
        mock_confirm_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_confirm_result])
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.workers.ttl_checker.async_session_factory",
            return_value=mock_session,
        ):
            await _check_expired_tasks()
            assert mock_task.status == TaskStatus.EXPIRED.value

    @pytest.mark.asyncio
    async def test_check_expired_intents(self):
        """Intents past their expires_at should be marked as expired."""
        from app.workers.ttl_checker import _check_expired_intents

        mock_intent = MagicMock()
        mock_intent.id = "intent_expired"
        mock_intent.status = "active"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_intent]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.workers.ttl_checker.async_session_factory",
            return_value=mock_session,
        ):
            await _check_expired_intents()
            assert mock_intent.status == "expired"

    @pytest.mark.asyncio
    async def test_check_expired_introductions(self):
        """Introductions past their expires_at should be marked as expired."""
        from app.workers.ttl_checker import _check_expired_introductions

        mock_intro = MagicMock()
        mock_intro.id = "intro_expired"
        mock_intro.status = "pending"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_intro]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.workers.ttl_checker.async_session_factory",
            return_value=mock_session,
        ):
            await _check_expired_introductions()
            assert mock_intro.status == "expired"

    def test_check_interval(self):
        """TTL checker interval should be 3600 seconds (1 hour)."""
        from app.workers.ttl_checker import CHECK_INTERVAL
        assert CHECK_INTERVAL == 3600


class TestStatusDecayWorker:
    """Test status_decay worker downgrades inactive agents."""

    @pytest.mark.asyncio
    async def test_status_decay_loop_respects_shutdown(self):
        """Status decay should exit when shutdown_event is set."""
        from app.workers.status_decay import run_status_decay

        shutdown_event = asyncio.Event()
        shutdown_event.set()

        with patch(
            "app.workers.status_decay._decay_agent_statuses",
            new_callable=AsyncMock,
        ):
            await asyncio.wait_for(
                run_status_decay(shutdown_event),
                timeout=5.0,
            )

    @pytest.mark.asyncio
    async def test_decay_online_to_away(self):
        """Agent online with last_seen > 5min ago should become away."""
        from app.workers.status_decay import _decay_agent_statuses

        now = datetime.now(timezone.utc)
        agent = MagicMock()
        agent.status = "online"
        agent.last_seen_at = now - timedelta(minutes=10)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [agent]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.workers.status_decay.async_session_factory",
            return_value=mock_session,
        ):
            await _decay_agent_statuses()
            assert agent.status == "away"

    @pytest.mark.asyncio
    async def test_decay_away_to_offline(self):
        """Agent away with last_seen > 30min ago should become offline."""
        from app.workers.status_decay import _decay_agent_statuses

        now = datetime.now(timezone.utc)
        agent = MagicMock()
        agent.status = "away"
        agent.last_seen_at = now - timedelta(minutes=45)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [agent]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.workers.status_decay.async_session_factory",
            return_value=mock_session,
        ):
            await _decay_agent_statuses()
            assert agent.status == "offline"

    @pytest.mark.asyncio
    async def test_recent_online_stays_online(self):
        """Agent online with last_seen < 5min ago should stay online."""
        from app.workers.status_decay import _decay_agent_statuses

        now = datetime.now(timezone.utc)
        agent = MagicMock()
        agent.status = "online"
        agent.last_seen_at = now - timedelta(minutes=2)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [agent]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.workers.status_decay.async_session_factory",
            return_value=mock_session,
        ):
            await _decay_agent_statuses()
            assert agent.status == "online"

    def test_decay_check_interval(self):
        """Status decay check interval should be 300 seconds (5 min)."""
        from app.workers.status_decay import CHECK_INTERVAL
        assert CHECK_INTERVAL == 300


class TestStrengthDeriverWorker:
    """Test strength_deriver worker re-derives strength."""

    @pytest.mark.asyncio
    async def test_strength_deriver_loop_respects_shutdown(self):
        """Strength deriver should exit when shutdown_event is set."""
        from app.workers.strength_deriver import run_strength_deriver

        shutdown_event = asyncio.Event()
        shutdown_event.set()

        with patch(
            "app.workers.strength_deriver._rederive_all_strengths",
            new_callable=AsyncMock,
        ):
            await asyncio.wait_for(
                run_strength_deriver(shutdown_event),
                timeout=5.0,
            )

    @pytest.mark.asyncio
    async def test_rederive_updates_changed_strength(self):
        """When derived strength differs from current, it should update."""
        from app.workers.strength_deriver import _rederive_all_strengths

        edge = MagicMock()
        edge.from_agent_id = "agt_a"
        edge.to_agent_id = "agt_b"
        edge.strength = "new"
        edge.is_blocked = False
        edge.interaction_count = 5

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [edge]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.workers.strength_deriver.async_session_factory",
            return_value=mock_session,
        ), patch(
            "app.workers.strength_deriver.relationship_service.derive_strength",
            new_callable=AsyncMock,
            return_value="acquaintance",
        ):
            await _rederive_all_strengths()
            assert edge.strength == "acquaintance"

    @pytest.mark.asyncio
    async def test_rederive_no_update_when_same(self):
        """When derived strength is the same, should not count as updated."""
        from app.workers.strength_deriver import _rederive_all_strengths

        edge = MagicMock()
        edge.from_agent_id = "agt_a"
        edge.to_agent_id = "agt_b"
        edge.strength = "acquaintance"
        edge.is_blocked = False
        edge.interaction_count = 3

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [edge]

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.workers.strength_deriver.async_session_factory",
            return_value=mock_session,
        ), patch(
            "app.workers.strength_deriver.relationship_service.derive_strength",
            new_callable=AsyncMock,
            return_value="acquaintance",
        ):
            await _rederive_all_strengths()
            # strength should remain the same
            assert edge.strength == "acquaintance"

    def test_derivation_interval(self):
        """Strength re-derivation interval should be 1800 seconds (30 min)."""
        from app.workers.strength_deriver import CHECK_INTERVAL
        assert CHECK_INTERVAL == 1800
