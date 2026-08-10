from services.telegram.app.mfa_dedupe import (
    DENIAL_TTL,
    SUCCESS_TTL,
    denial_key,
    mark_mfa_approval,
    mark_mfa_denial,
    should_suppress_ssh_event,
    success_key,
)


class FakeRedis:
    def __init__(self):
        self.data = {}
        self.ttls = {}

    def setex(
        self,
        key,
        ttl,
        value,
    ):
        self.data[key] = value
        self.ttls[key] = ttl
        return True

    def get(
        self,
        key,
    ):
        return self.data.get(
            key
        )

    def getdel(
        self,
        key,
    ):
        return self.data.pop(
            key,
            None,
        )


def test_mfa_approval_marks_success():
    redis = FakeRedis()

    mark_mfa_approval(
        redis,
        "admin",
        "82.80.219.126",
    )

    key = success_key(
        "admin",
        "82.80.219.126",
    )

    assert redis.data[key] == "1"
    assert redis.ttls[key] == SUCCESS_TTL


def test_approved_mfa_suppresses_next_success():
    redis = FakeRedis()

    mark_mfa_approval(
        redis,
        "admin",
        "82.80.219.126",
    )

    event = {
        "event_type":
            "ssh.login.success",
        "username":
            "admin",
        "ip":
            "82.80.219.126",
    }

    assert (
        should_suppress_ssh_event(
            redis,
            event,
        )
        is True
    )


def test_approved_mfa_suppresses_only_one_success():
    redis = FakeRedis()

    mark_mfa_approval(
        redis,
        "admin",
        "82.80.219.126",
    )

    event = {
        "event_type":
            "ssh.login.success",
        "username":
            "admin",
        "ip":
            "82.80.219.126",
    }

    assert should_suppress_ssh_event(
        redis,
        event,
    )

    #
    # Le marqueur a été consommé.
    #
    # Une reconnexion normale/bypassée doit donc
    # produire sa notification.
    #
    assert (
        should_suppress_ssh_event(
            redis,
            event,
        )
        is False
    )


def test_mfa_disabled_keeps_normal_success_notification():
    redis = FakeRedis()

    #
    # Aucun mark_mfa_approval().
    #
    # C'est exactement le comportement MFA OFF.
    #
    event = {
        "event_type":
            "ssh.login.success",
        "username":
            "admin",
        "ip":
            "82.80.219.126",
    }

    assert (
        should_suppress_ssh_event(
            redis,
            event,
        )
        is False
    )


def test_mfa_bypass_keeps_normal_success_notification():
    redis = FakeRedis()

    #
    # Un bypass ne crée aucune décision MFA
    # explicite et donc aucun marqueur.
    #
    event = {
        "event_type":
            "ssh.login.success",
        "username":
            "admin",
        "ip":
            "82.80.219.126",
    }

    assert (
        should_suppress_ssh_event(
            redis,
            event,
        )
        is False
    )


def test_mfa_denial_marks_ip():
    redis = FakeRedis()

    mark_mfa_denial(
        redis,
        "82.80.219.126",
    )

    key = denial_key(
        "82.80.219.126"
    )

    assert redis.data[key] == "1"
    assert redis.ttls[key] == DENIAL_TTL


def test_denied_mfa_suppresses_login_failed():
    redis = FakeRedis()

    mark_mfa_denial(
        redis,
        "82.80.219.126",
    )

    event = {
        "event_type":
            "ssh.login.failed",
        "username":
            "admin",
        "ip":
            "82.80.219.126",
    }

    assert (
        should_suppress_ssh_event(
            redis,
            event,
        )
        is True
    )


def test_denied_mfa_suppresses_connection_reset():
    redis = FakeRedis()

    mark_mfa_denial(
        redis,
        "82.80.219.126",
    )

    event = {
        "event_type":
            "ssh.connection.reset",
        "username":
            "admin",
        "ip":
            "82.80.219.126",
    }

    assert (
        should_suppress_ssh_event(
            redis,
            event,
        )
        is True
    )


def test_denied_mfa_suppresses_connection_closed():
    redis = FakeRedis()

    mark_mfa_denial(
        redis,
        "82.80.219.126",
    )

    event = {
        "event_type":
            "ssh.connection.closed",
        "username":
            None,
        "ip":
            "82.80.219.126",
    }

    assert (
        should_suppress_ssh_event(
            redis,
            event,
        )
        is True
    )


def test_denial_marker_can_suppress_multiple_derived_events():
    redis = FakeRedis()

    mark_mfa_denial(
        redis,
        "82.80.219.126",
    )

    events = [
        {
            "event_type":
                "ssh.login.failed",
            "username":
                "admin",
            "ip":
                "82.80.219.126",
        },
        {
            "event_type":
                "ssh.connection.reset",
            "username":
                "admin",
            "ip":
                "82.80.219.126",
        },
        {
            "event_type":
                "ssh.connection.closed",
            "username":
                None,
            "ip":
                "82.80.219.126",
        },
    ]

    for event in events:
        assert (
            should_suppress_ssh_event(
                redis,
                event,
            )
            is True
        )


def test_normal_failure_without_mfa_denial_is_not_suppressed():
    redis = FakeRedis()

    event = {
        "event_type":
            "ssh.login.failed",
        "username":
            "admin",
        "ip":
            "82.80.219.126",
    }

    assert (
        should_suppress_ssh_event(
            redis,
            event,
        )
        is False
    )


def test_mfa_denial_does_not_hide_success():
    redis = FakeRedis()

    mark_mfa_denial(
        redis,
        "82.80.219.126",
    )

    event = {
        "event_type":
            "ssh.login.success",
        "username":
            "admin",
        "ip":
            "82.80.219.126",
    }

    assert (
        should_suppress_ssh_event(
            redis,
            event,
        )
        is False
    )


def test_mfa_approval_does_not_hide_failures():
    redis = FakeRedis()

    mark_mfa_approval(
        redis,
        "admin",
        "82.80.219.126",
    )

    event = {
        "event_type":
            "ssh.login.failed",
        "username":
            "admin",
        "ip":
            "82.80.219.126",
    }

    assert (
        should_suppress_ssh_event(
            redis,
            event,
        )
        is False
    )


def test_different_ip_is_not_suppressed():
    redis = FakeRedis()

    mark_mfa_denial(
        redis,
        "82.80.219.126",
    )

    event = {
        "event_type":
            "ssh.login.failed",
        "username":
            "admin",
        "ip":
            "203.0.113.50",
    }

    assert (
        should_suppress_ssh_event(
            redis,
            event,
        )
        is False
    )
