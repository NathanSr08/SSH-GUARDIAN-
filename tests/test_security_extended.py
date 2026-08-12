from collections import deque
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from types import SimpleNamespace

import services.security.app.engine as engine_module
from services.security.app.engine import SecurityEngine


IP = "203.0.113.40"


def event(
    ip=IP,
    event_type="ssh.connection.opened",
):
    return SimpleNamespace(
        ip=ip,
        event_type=event_type,
    )


def rules(
    max_attempts=3,
    ban_duration_seconds=3600,
    window_seconds=60,
):
    return SimpleNamespace(
        max_attempts=max_attempts,
        ban_duration_seconds=
            ban_duration_seconds,
        window_seconds=
            window_seconds,
    )


def test_non_open_event_is_ignored():
    engine = SecurityEngine(
        rules()
    )

    assert (
        engine.process(
            event(
                event_type=
                    "ssh.login.failed"
            )
        )
        is None
    )


def test_old_attempts_are_removed():
    engine = SecurityEngine(
        rules(
            max_attempts=3,
            window_seconds=10,
        )
    )

    engine.attempts[IP] = deque([
        datetime.now(
            timezone.utc
        )
        - timedelta(
            seconds=100
        )
    ])

    result = engine.process(
        event()
    )

    assert result["attempts"] == 1
    assert (
        result["remaining_attempts"]
        == 2
    )


def test_whitelist_never_bans(
    monkeypatch,
):
    monkeypatch.setattr(
        engine_module.Settings,
        "WHITELIST",
        {IP},
    )

    engine = SecurityEngine(
        rules(
            max_attempts=1
        )
    )

    result = engine.process(
        event()
    )

    assert result["action"] == "ignore"
    assert result["whitelisted"] is True
    assert result["attempts"] == 1


def test_active_ban_ignores_new_connection():
    engine = SecurityEngine(
        rules()
    )

    engine.banned_until[IP] = (
        datetime.now(
            timezone.utc
        )
        + timedelta(
            minutes=5
        )
    )

    assert (
        engine.process(
            event()
        )
        is None
    )


def test_expired_ban_is_removed():
    engine = SecurityEngine(
        rules()
    )

    engine.banned_until[IP] = (
        datetime.now(
            timezone.utc
        )
        - timedelta(
            seconds=1
        )
    )

    result = engine.process(
        event()
    )

    assert (
        IP
        not in engine.banned_until
    )

    assert result["action"] == "monitor"


def test_threshold_bans_and_clears_attempts():
    engine = SecurityEngine(
        rules(
            max_attempts=2,
            ban_duration_seconds=60,
        )
    )

    first = engine.process(
        event()
    )

    second = engine.process(
        event()
    )

    assert first["action"] == "monitor"
    assert second["action"] == "ban_ip"

    assert second["attempts"] == 2

    assert (
        len(engine.attempts[IP])
        == 0
    )

    assert IP in engine.banned_until


def test_remaining_attempts_never_negative_for_whitelist(
    monkeypatch,
):
    monkeypatch.setattr(
        engine_module.Settings,
        "WHITELIST",
        {IP},
    )

    engine = SecurityEngine(
        rules(
            max_attempts=1
        )
    )

    engine.process(
        event()
    )

    result = engine.process(
        event()
    )

    assert (
        result["remaining_attempts"]
        == 0
    )
