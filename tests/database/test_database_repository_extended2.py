from datetime import datetime, timedelta, timezone

from services.database.app.repository import (
    DatabaseRepository,
)
from shared.events.ssh import SSHEvent


def test_database_repository_full_flow(tmp_path):
    db = DatabaseRepository(
        tmp_path / "guardian.db"
    )

    event = SSHEvent(
        event_type="ssh.login.failed",
        timestamp=datetime.now(timezone.utc),
        ip="1.2.3.4",
        username="root",
        message="failed",
    )

    db.log_event(event)

    with db._connect() as conn:
        row = conn.execute(
            """
            SELECT
                event_type,
                ip,
                username,
                message
            FROM ssh_events
            """
        ).fetchone()

    assert row == (
        "ssh.login.failed",
        "1.2.3.4",
        "root",
        "failed",
    )

    db.add_ban(
        "1.2.3.4",
        "too_many_attempts",
        3600,
    )

    bans = db.get_active_bans()

    assert len(bans) == 1
    assert bans[0][0] == "1.2.3.4"
    assert bans[0][1] == "too_many_attempts"

    with db._connect() as conn:
        old = (
            datetime.now(timezone.utc)
            - timedelta(hours=1)
        ).isoformat()

        conn.execute(
            """
            UPDATE bans
            SET expires_at = ?
            WHERE ip = ?
            """,
            (
                old,
                "1.2.3.4",
            ),
        )

        conn.commit()

    expired = db.get_expired_bans()

    assert len(expired) == 1
    ban_id, ip = expired[0]

    assert ip == "1.2.3.4"

    db.mark_unbanned(ban_id)

    assert db.get_active_bans() == []
    assert db.get_expired_bans() == []


def test_database_multiple_bans(tmp_path):
    db = DatabaseRepository(
        tmp_path / "guardian.db"
    )

    db.add_ban(
        "1.1.1.1",
        "reason1",
        100,
    )

    db.add_ban(
        "2.2.2.2",
        "reason2",
        200,
    )

    result = db.get_active_bans()

    assert len(result) == 2

    ips = {
        row[0]
        for row in result
    }

    assert ips == {
        "1.1.1.1",
        "2.2.2.2",
    }
