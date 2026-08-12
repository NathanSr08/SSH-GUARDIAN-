import pytest

import services.mfa.bin.pam_bridge as pam


IP = "203.0.113.50"


class FakeClient:
    def __init__(
        self,
        policy="allowed",
        blocked=False,
    ):
        self.policy = policy
        self.blocked = blocked

    def get(self, key):
        if key.startswith(
            "security:country-policy:"
        ):
            return self.policy

        return None

    def exists(self, key):
        if key.startswith(
            "security:blocked-country:"
        ):
            return int(
                self.blocked
            )

        return 0


class FakeBus:
    def __init__(
        self,
        policy="allowed",
        blocked=False,
        ping=True,
    ):
        self.client = FakeClient(
            policy=policy,
            blocked=blocked,
        )

        self._ping = ping

    def ping(self):
        return self._ping


class FakeRuntime:
    enabled_value = True
    temporary = False

    def __init__(self, redis_client):
        pass

    def enabled(self):
        return self.enabled_value

    def is_ip_allowed(self, ip):
        return self.temporary

    def bypass_info(self, ip):
        return {
            "ttl": 60,
        }

    def timeout_seconds(self):
        return 45


def configure(
    monkeypatch,
    *,
    username="admin",
    ip=IP,
    pam_type="auth",
    fail_mode="deny",
    policy="allowed",
    blocked=False,
    redis_ping=True,
    runtime_enabled=True,
    temporary=False,
    bypass_users=None,
    bypass_ips=None,
):
    monkeypatch.setenv(
        "PAM_USER",
        username,
    )

    monkeypatch.setenv(
        "PAM_RHOST",
        ip,
    )

    monkeypatch.setenv(
        "PAM_TYPE",
        pam_type,
    )

    monkeypatch.setattr(
        pam.Settings,
        "MFA_FAIL_MODE",
        fail_mode,
    )

    monkeypatch.setattr(
        pam.Settings,
        "MFA_BYPASS_USERS",
        set(
            bypass_users
            or []
        ),
    )

    monkeypatch.setattr(
        pam.Settings,
        "MFA_BYPASS_IPS",
        set(
            bypass_ips
            or []
        ),
    )

    bus = FakeBus(
        policy=policy,
        blocked=blocked,
        ping=redis_ping,
    )

    monkeypatch.setattr(
        pam,
        "RedisBus",
        lambda: bus,
    )

    FakeRuntime.enabled_value = (
        runtime_enabled
    )

    FakeRuntime.temporary = (
        temporary
    )

    monkeypatch.setattr(
        pam,
        "MFARuntime",
        FakeRuntime,
    )

    return bus


def test_non_auth_pam_phase_is_allowed(
    monkeypatch,
):
    configure(
        monkeypatch,
        username="",
        ip="",
        pam_type="account",
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 0


def test_missing_username_denied(
    monkeypatch,
):
    configure(
        monkeypatch,
        username="",
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 1


def test_missing_ip_fail_closed(
    monkeypatch,
):
    configure(
        monkeypatch,
        ip="",
        fail_mode="deny",
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 1


def test_missing_ip_fail_open(
    monkeypatch,
):
    configure(
        monkeypatch,
        ip="",
        fail_mode="allow",
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 0


def test_redis_unavailable_fail_closed(
    monkeypatch,
):
    configure(
        monkeypatch,
        redis_ping=False,
        fail_mode="deny",
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 1


def test_redis_unavailable_fail_open(
    monkeypatch,
):
    configure(
        monkeypatch,
        redis_ping=False,
        fail_mode="allow",
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 0


def test_blocked_country_denied(
    monkeypatch,
):
    configure(
        monkeypatch,
        policy="blocked",
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 1


def test_legacy_blocked_country_key_denied(
    monkeypatch,
):
    configure(
        monkeypatch,
        policy=None,
        blocked=True,
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 1


def test_permanent_user_bypass(
    monkeypatch,
):
    configure(
        monkeypatch,
        bypass_users={
            "admin",
        },
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 0


def test_permanent_ip_bypass(
    monkeypatch,
):
    configure(
        monkeypatch,
        bypass_ips={
            IP,
        },
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 0


def test_runtime_disabled_allows(
    monkeypatch,
):
    configure(
        monkeypatch,
        runtime_enabled=False,
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 0


def test_temporary_bypass_allows(
    monkeypatch,
):
    configure(
        monkeypatch,
        temporary=True,
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 0


def test_approved_mfa_allows(
    monkeypatch,
):
    configure(
        monkeypatch,
    )

    monkeypatch.setattr(
        pam,
        "rpc_create",
        lambda *args, **kwargs:
            {
                "request_id":
                    "req-ok",
            },
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


@pytest.mark.parametrize(
    "status",
    [
        "denied",
        "expired",
        "cancelled",
    ],
)
def test_non_approved_mfa_is_denied(
    monkeypatch,
    status,
):
    configure(
        monkeypatch,
    )

    monkeypatch.setattr(
        pam,
        "rpc_create",
        lambda *args, **kwargs:
            {
                "request_id":
                    "req-no",
            },
    )

    monkeypatch.setattr(
        pam,
        "wait_for_decision",
        lambda *args, **kwargs:
            status,
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 1


def test_missing_request_id_fails_closed(
    monkeypatch,
):
    configure(
        monkeypatch,
        fail_mode="deny",
    )

    monkeypatch.setattr(
        pam,
        "rpc_create",
        lambda *args, **kwargs:
            {},
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 1


def test_missing_request_id_fail_open(
    monkeypatch,
):
    configure(
        monkeypatch,
        fail_mode="allow",
    )

    monkeypatch.setattr(
        pam,
        "rpc_create",
        lambda *args, **kwargs:
            {},
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam.main()

    assert exc.value.code == 0
