import json
from datetime import datetime, timezone

from shared.events.ssh import SSHEvent


def test_ssh_event_to_dict():
    timestamp = datetime(
        2026,
        8,
        12,
        12,
        30,
        tzinfo=timezone.utc,
    )

    event = SSHEvent(
        event_type="ssh.login.success",
        timestamp=timestamp,
        ip="1.2.3.4",
        username="root",
        message="accepted",
    )

    result = event.to_dict()

    assert result == {
        "event_type":
            "ssh.login.success",
        "timestamp":
            timestamp.isoformat(),
        "ip":
            "1.2.3.4",
        "username":
            "root",
        "message":
            "accepted",
    }


def test_ssh_event_to_json_unicode():
    event = SSHEvent(
        event_type="ssh.test",
        timestamp=datetime.now(
            timezone.utc
        ),
        ip="::1",
        username="nathan",
        message="éàç",
    )

    raw = event.to_json()
    data = json.loads(raw)

    assert data["event_type"] == "ssh.test"
    assert data["ip"] == "::1"
    assert data["username"] == "nathan"
    assert data["message"] == "éàç"

    assert "\\u00e9" not in raw


def test_ssh_event_optional_fields():
    event = SSHEvent(
        event_type="ssh.connection.opened",
        timestamp=datetime.now(
            timezone.utc
        ),
        ip="127.0.0.1",
    )

    data = event.to_dict()

    assert data["username"] is None
    assert data["message"] is None
