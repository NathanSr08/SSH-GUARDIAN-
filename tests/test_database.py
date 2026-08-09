from datetime import datetime, timezone
from pathlib import Path
import tempfile

from shared.events.ssh import SSHEvent
from services.database.app.repository import DatabaseRepository


def test_database_event_insert():
    with tempfile.TemporaryDirectory() as tmp:
        repo = DatabaseRepository(
            Path(tmp) / "test.db"
        )

        event = SSHEvent(
            event_type="ssh.login.failed",
            timestamp=datetime.now(timezone.utc),
            ip="1.2.3.4",
            username="root",
            message="test",
        )

        repo.log_event(event)


def test_database_ban_insert():
    with tempfile.TemporaryDirectory() as tmp:
        repo = DatabaseRepository(
            Path(tmp) / "test.db"
        )

        repo.add_ban(
            ip="1.2.3.4",
            reason="test",
            duration_seconds=60,
        )

        bans = repo.get_active_bans()

        assert len(bans) == 1
        assert bans[0][0] == "1.2.3.4"
