import json

import pytest

import services.mfa.bin.pam_bridge as pam

from services.mfa.app.manager import MFAManager
from services.mfa.app.runtime import MFARuntime
from services.telegram.app.mfa_dedupe import (
    mark_mfa_approval,
    mark_mfa_denial,
    should_suppress_ssh_event,
)


IP = "203.0.113.200"
USER = "admin"


class Redis:
    def __init__(self):
        self.values = {}
        self.ttls = {}
        self.lists = {}
        self.published = []

    def get(self, key):
        return self.values.get(key)

    def set(
        self,
        key,
        value,
        ex=None,
        **kwargs,
    ):
        self.values[key] = value

        if ex is not None:
            self.ttls[key] = int(ex)

        return True

    def setex(
        self,
        key,
        ttl,
        value,
    ):
        self.values[key] = value
        self.ttls[key] = int(ttl)
        return True

    def getdel(self, key):
        return self.values.pop(
            key,
            None,
        )

    def exists(self, key):
        return int(
            key in self.values
        )

    def delete(self, *keys):
        count = 0

        for key in keys:
            if key in self.values:
                count += 1

            self.values.pop(
                key,
                None,
            )

            self.ttls.pop(
                key,
                None,
            )

        return count

    def ttl(self, key):
        return self.ttls.get(
            key,
            -1,
        )

    def scan_iter(
        self,
        match=None,
        count=None,
    ):
        if (
            match
            and match.endswith("*")
        ):
            prefix = match[:-1]

            for key in list(
                self.values
            ):
                if str(key).startswith(
                    prefix
                ):
                    yield key

            return

        yield from list(
            self.values
        )

    def rpush(self, key, value):
        self.lists.setdefault(
            key,
            [],
        ).append(value)

        return len(
            self.lists[key]
        )

    def blpop(
        self,
        key,
        timeout=0,
    ):
        values = self.lists.get(
            key,
            [],
        )

        if not values:
            return None

        return (
            key,
            values.pop(0),
        )

    def expire(self, key, seconds):
        self.ttls[key] = int(
            seconds
        )

        return True


class Bus:
    def __init__(self, redis):
        self.client = redis
        self.events = []

    def ping(self):
        return True

    def publish(
        self,
        stream,
        payload,
    ):
        self.events.append(
            (
                stream,
                payload,
            )
        )

        self.client.published.append(
            (
                stream,
                payload,
            )
        )

        return "1-0"


def configure_pam(
    monkeypatch,
    redis,
    *,
    fail_mode="deny",
):
    bus = Bus(redis)

    monkeypatch.setenv(
        "PAM_USER",
        USER,
    )

    monkeypatch.setenv(
        "PAM_RHOST",
        IP,
    )

    monkeypatch.setenv(
        "PAM_TYPE",
        "auth",
    )

    monkeypatch.setattr(
        pam.Settings,
        "MFA_FAIL_MODE",
        fail_mode,
    )

    monkeypatch.setattr(
        pam.Settings,
        "MFA_BYPASS_USERS",
        set(),
    )

    monkeypatch.setattr(
        pam.Settings,
        "MFA_BYPASS_IPS",
        set(),
    )

    monkeypatch.setattr(
        pam,
        "RedisBus",
        lambda: bus,
    )

    return bus


def test_blocked_country_has_priority_over_mfa(
    monkeypatch,
):
    redis = Redis()

    redis.set(
        f"security:country-policy:{IP}",
        "blocked",
        ex=60,
    )

    redis.set(
        f"security:blocked-country:{IP}",
        "il",
        ex=86400,
    )

    bus = configure_pam(
        monkeypatch,
        redis,
    )

    rpc_calls = []

    monkeypatch.setattr(
        pam,
        "rpc_create",
        lambda *args, **kwargs:
            rpc_calls.append(True),
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 1

    # Aucun MFA ne doit être créé.
    assert rpc_calls == []

    # La politique reste présente.
    assert (
        redis.get(
            f"security:country-policy:{IP}"
        )
        == "blocked"
    )

    assert (
        redis.get(
            f"security:blocked-country:{IP}"
        )
        == "il"
    )


def test_blocked_country_beats_temporary_mfa_bypass(
    monkeypatch,
):
    redis = Redis()

    runtime = MFARuntime(redis)

    runtime.allow_ip(
        IP,
        3600,
        source="test",
    )

    redis.set(
        f"security:country-policy:{IP}",
        "blocked",
        ex=60,
    )

    redis.set(
        f"security:blocked-country:{IP}",
        "il",
        ex=86400,
    )

    configure_pam(
        monkeypatch,
        redis,
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 1


def test_allowed_country_reaches_mfa(
    monkeypatch,
):
    redis = Redis()

    redis.set(
        f"security:country-policy:{IP}",
        "allowed",
        ex=60,
    )

    configure_pam(
        monkeypatch,
        redis,
    )

    monkeypatch.setattr(
        pam.MFARuntime,
        "enabled",
        lambda self: True,
    )

    monkeypatch.setattr(
        pam.MFARuntime,
        "is_ip_allowed",
        lambda self, ip: False,
    )

    monkeypatch.setattr(
        pam.MFARuntime,
        "timeout_seconds",
        lambda self: 45,
    )

    calls = []

    monkeypatch.setattr(
        pam,
        "rpc_create",
        lambda bus, username, ip: (
            calls.append(
                (
                    username,
                    ip,
                )
            )
            or {
                "request_id":
                    "req-integration",
            }
        ),
    )

    monkeypatch.setattr(
        pam,
        "wait_for_decision",
        lambda *args, **kwargs:
            "approved",
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 0

    assert calls == [
        (
            USER,
            IP,
        )
    ]


def test_real_mfa_manager_approve_then_pam_decision():
    redis = Redis()

    manager = MFAManager(
        redis,
        timeout_seconds=45,
    )

    request = (
        manager.create_request(
            USER,
            IP,
        )
    )

    assert (
        request.status
        == "pending"
    )

    approved = manager.approve(
        request.request_id,
        source="telegram",
    )

    assert (
        approved.status
        == "approved"
    )

    raw = redis.get(
        f"mfa:request:{request.request_id}"
    )

    data = json.loads(raw)

    assert (
        data["status"]
        == "approved"
    )

    bus = Bus(redis)

    assert (
        pam.wait_for_decision(
            bus,
            request.request_id,
            1,
        )
        == "approved"
    )


def test_real_mfa_manager_deny_then_pam_decision():
    redis = Redis()

    manager = MFAManager(
        redis,
        timeout_seconds=45,
    )

    request = (
        manager.create_request(
            USER,
            IP,
        )
    )

    denied = manager.deny(
        request.request_id,
        source="telegram",
    )

    assert denied.status == "denied"

    bus = Bus(redis)

    assert (
        pam.wait_for_decision(
            bus,
            request.request_id,
            1,
        )
        == "denied"
    )


def test_mfa_approval_then_telegram_success_dedupe():
    redis = Redis()

    mark_mfa_approval(
        redis,
        USER,
        IP,
    )

    event = {
        "event_type":
            "ssh.login.success",
        "username":
            USER,
        "ip":
            IP,
    }

    # Le succès généré immédiatement
    # après le MFA est masqué.
    assert (
        should_suppress_ssh_event(
            redis,
            event,
        )
        is True
    )

    # Mais pas un deuxième succès futur.
    assert (
        should_suppress_ssh_event(
            redis,
            event,
        )
        is False
    )


def test_mfa_denial_suppresses_entire_ssh_failure_sequence():
    redis = Redis()

    mark_mfa_denial(
        redis,
        IP,
    )

    for event_type in (
        "ssh.login.failed",
        "ssh.connection.reset",
        "ssh.connection.closed",
    ):
        assert (
            should_suppress_ssh_event(
                redis,
                {
                    "event_type":
                        event_type,
                    "ip":
                        IP,
                },
            )
            is True
        )
