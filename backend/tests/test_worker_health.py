import subprocess
import sys
from unittest.mock import MagicMock

import pytest
from kombu.exceptions import OperationalError

from app.core import worker_health


@pytest.fixture
def broker(monkeypatch):
    connection = MagicMock()
    monkeypatch.setattr(worker_health.celery, "connection_for_write", lambda **kwargs: connection)
    return connection.__enter__.return_value


@pytest.mark.parametrize(
    ("replies", "status"),
    [([{"celery@local": {"ok": "pong"}}], 0), ([], 1), ([{"celery@other": {"ok": "pong"}}], 1)],
)
def test_health_requires_a_pong_from_the_local_worker(monkeypatch, broker, capsys, replies, status):
    ping = MagicMock(return_value=replies)
    monkeypatch.setattr(worker_health, "default_nodename", lambda _: "celery@local")
    monkeypatch.setattr(worker_health.celery.control, "ping", ping)
    assert worker_health.main() == status
    broker.ensure_connection.assert_called_once_with(max_retries=0)
    ping.assert_called_once_with(destination=["celery@local"], timeout=5, connection=broker)
    assert ("did not answer" in capsys.readouterr().err) == bool(status)


def test_health_reports_broker_failure_without_leaking_details(broker, capsys):
    broker.ensure_connection.side_effect = OperationalError("private broker details")
    assert worker_health.main() == 1
    assert capsys.readouterr().err.strip() == (
        "Celery health check could not reach the broker (OperationalError)."
    )


def test_health_probe_imports_without_analytics_modules():
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import app.core.worker_health; "
                "assert not {'app.services.jobs', 'app.agents.workflow', 'matplotlib'}.intersection(sys.modules)"
            ),
        ],
        check=True,
        timeout=15,
    )
