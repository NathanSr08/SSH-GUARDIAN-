from datetime import datetime, timezone

from shared.events.ssh import SSHEvent
from services.security.app.engine import SecurityEngine
from services.security.app.rules import SecurityRules


def connection_event(
    ip="1.2.3.4",
):
    return SSHEvent(
        event_type="ssh.connection.opened",
        timestamp=datetime.now(timezone.utc),
        ip=ip,
        username=None,
    )


def failed_event(
    ip="1.2.3.4",
):
    return SSHEvent(
        event_type="ssh.login.failed",
        timestamp=datetime.now(timezone.utc),
        ip=ip,
        username="root",
    )


def success_event(
    ip="1.2.3.4",
):
    return SSHEvent(
        event_type="ssh.login.success",
        timestamp=datetime.now(timezone.utc),
        ip=ip,
        username="root",
    )


def test_first_connection_is_monitored():
    engine = SecurityEngine(
        SecurityRules(
            max_attempts=3,
        )
    )

    result = engine.process(
        connection_event()
    )

    assert result is not None
    assert result["action"] == "monitor"
    assert result["attempts"] == 1
    assert result["remaining_attempts"] == 2


def test_ban_after_three_connections():
    engine = SecurityEngine(
        SecurityRules(
            max_attempts=3,
        )
    )

    engine.process(
        connection_event()
    )

    engine.process(
        connection_event()
    )

    result = engine.process(
        connection_event()
    )

    assert result is not None
    assert result["action"] == "ban_ip"
    assert result["ip"] == "1.2.3.4"
    assert result["attempts"] == 3
    assert (
        result["reason"]
        == "too_many_connection_attempts"
    )


def test_failed_login_does_not_increment_counter():
    engine = SecurityEngine(
        SecurityRules(
            max_attempts=3,
        )
    )

    first = engine.process(
        connection_event()
    )

    failed = engine.process(
        failed_event()
    )

    second = engine.process(
        connection_event()
    )

    assert first["attempts"] == 1
    assert failed is None
    assert second["attempts"] == 2


def test_successful_login_does_not_increment_counter():
    engine = SecurityEngine(
        SecurityRules(
            max_attempts=3,
        )
    )

    first = engine.process(
        connection_event()
    )

    success = engine.process(
        success_event()
    )

    second = engine.process(
        connection_event()
    )

    assert first["attempts"] == 1
    assert success is None
    assert second["attempts"] == 2


def test_ips_are_counted_separately():
    engine = SecurityEngine(
        SecurityRules(
            max_attempts=2,
        )
    )

    first = engine.process(
        connection_event(
            "1.1.1.1"
        )
    )

    second = engine.process(
        connection_event(
            "2.2.2.2"
        )
    )

    assert first["attempts"] == 1
    assert second["attempts"] == 1


def test_only_one_ban_is_emitted():
    engine = SecurityEngine(
        SecurityRules(
            max_attempts=3,
            ban_duration_seconds=3600,
        )
    )

    engine.process(
        connection_event()
    )

    engine.process(
        connection_event()
    )

    third = engine.process(
        connection_event()
    )

    fourth = engine.process(
        connection_event()
    )

    fifth = engine.process(
        connection_event()
    )

    assert third is not None
    assert third["action"] == "ban_ip"

    assert fourth is None
    assert fifth is None
