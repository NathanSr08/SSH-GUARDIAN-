import pytest

from services.telegram.app.mfa_dedupe import (
    DENIAL_TTL,
    SUCCESS_TTL,
    denial_key,
    mark_mfa_approval,
    mark_mfa_denial,
    should_suppress_ssh_event,
    success_key,
)


class Redis:
    def __init__(self):
        self.values = {}
        self.setex_calls = []
        self.getdel_calls = []
        self.get_calls = []

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.setex_calls.append(
            (key, ttl, value)
        )

    def getdel(self, key):
        self.getdel_calls.append(key)
        return self.values.pop(
            key,
            None,
        )

    def get(self, key):
        self.get_calls.append(key)
        return self.values.get(key)


def test_success_key():
    assert success_key(
        "admin",
        "1.2.3.4",
    ) == (
        "telegram:mfa:suppress_success:"
        "admin:1.2.3.4"
    )


def test_denial_key():
    assert denial_key(
        "1.2.3.4"
    ) == (
        "telegram:mfa:suppress_failure:"
        "1.2.3.4"
    )


@pytest.mark.parametrize(
    "username,ip",
    [
        ("", "1.2.3.4"),
        ("admin", ""),
        (None, "1.2.3.4"),
        ("admin", None),
        ("   ", "1.2.3.4"),
        ("admin", "   "),
    ],
)
def test_mark_approval_missing_data_is_ignored(
    username,
    ip,
):
    redis = Redis()

    mark_mfa_approval(
        redis,
        username,
        ip,
    )

    assert redis.setex_calls == []


def test_mark_approval_success():
    redis = Redis()

    mark_mfa_approval(
        redis,
        " admin ",
        " 1.2.3.4 ",
    )

    assert redis.setex_calls == [
        (
            success_key(
                "admin",
                "1.2.3.4",
            ),
            SUCCESS_TTL,
            "1",
        )
    ]


@pytest.mark.parametrize(
    "ip",
    [
        "",
        None,
        "   ",
    ],
)
def test_mark_denial_missing_ip_is_ignored(
    ip,
):
    redis = Redis()

    mark_mfa_denial(
        redis,
        ip,
    )

    assert redis.setex_calls == []


def test_mark_denial_success():
    redis = Redis()

    mark_mfa_denial(
        redis,
        " 1.2.3.4 ",
    )

    assert redis.setex_calls == [
        (
            denial_key(
                "1.2.3.4"
            ),
            DENIAL_TTL,
            "1",
        )
    ]


def test_success_marker_suppresses_once():
    redis = Redis()

    mark_mfa_approval(
        redis,
        "admin",
        "1.2.3.4",
    )

    payload = {
        "event_type":
            "ssh.login.success",
        "username":
            "admin",
        "ip":
            "1.2.3.4",
    }

    assert (
        should_suppress_ssh_event(
            redis,
            payload,
        )
        is True
    )

    assert (
        should_suppress_ssh_event(
            redis,
            payload,
        )
        is False
    )


@pytest.mark.parametrize(
    "event_type",
    [
        "ssh.login.failed",
        "ssh.connection.reset",
        "ssh.connection.closed",
    ],
)
def test_denial_marker_suppresses_all_failure_events(
    event_type,
):
    redis = Redis()

    mark_mfa_denial(
        redis,
        "1.2.3.4",
    )

    payload = {
        "event_type":
            event_type,
        "ip":
            "1.2.3.4",
    }

    assert (
        should_suppress_ssh_event(
            redis,
            payload,
        )
        is True
    )

    # Contrairement au succès,
    # le marqueur de refus n'est pas consommé.
    assert (
        should_suppress_ssh_event(
            redis,
            payload,
        )
        is True
    )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "event_type":
                "ssh.login.success",
            "ip":
                "1.2.3.4",
        },
        {
            "event_type":
                "ssh.login.success",
            "username":
                "admin",
        },
        {
            "event_type":
                "ssh.login.failed",
        },
        {
            "event_type":
                "ssh.connection.opened",
            "ip":
                "1.2.3.4",
        },
    ],
)
def test_unrelated_or_incomplete_event_not_suppressed(
    payload,
):
    redis = Redis()

    assert (
        should_suppress_ssh_event(
            redis,
            payload,
        )
        is False
    )
