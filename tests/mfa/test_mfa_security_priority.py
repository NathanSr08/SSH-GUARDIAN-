import pytest

from services.mfa.bin import pam_bridge


IP = "46.210.209.194"
USER = "admin"


class FakeRedisClient:
    def __init__(
        self,
        blocked=True,
    ):
        self.blocked = blocked
        self.exists_calls = []

    def exists(
        self,
        key,
    ):
        self.exists_calls.append(
            key
        )

        if (
            key
            == f"security:blocked-country:{IP}"
        ):
            return 1 if self.blocked else 0

        return 0


class FakeRedisBus:
    def __init__(
        self,
        blocked=True,
    ):
        self.client = FakeRedisClient(
            blocked=blocked
        )

    def ping(self):
        return True


class FakeRuntime:
    def __init__(
        self,
        redis_client,
        enabled=True,
        temporary_bypass=False,
    ):
        self.redis = redis_client
        self._enabled = enabled
        self._temporary_bypass = (
            temporary_bypass
        )

        self.enabled_called = False
        self.temp_bypass_called = False

    def enabled(self):
        self.enabled_called = True
        return self._enabled

    def is_ip_allowed(
        self,
        ip,
    ):
        self.temp_bypass_called = True
        return self._temporary_bypass

    def bypass_info(
        self,
        ip,
    ):
        return {
            "ttl": 3600,
        }

    def timeout_seconds(self):
        return 45


def configure_pam_env(
    monkeypatch,
):
    monkeypatch.setenv(
        "PAM_USER",
        USER,
    )

    monkeypatch.setenv(
        "PAM_RHOST",
        IP,
    )

    monkeypatch.setenv(
        "PAM_SERVICE",
        "sshd",
    )

    monkeypatch.setenv(
        "PAM_TYPE",
        "auth",
    )


def configure_settings(
    monkeypatch,
    bypass_users=None,
    bypass_ips=None,
):
    monkeypatch.setattr(
        pam_bridge.Settings,
        "MFA_BYPASS_USERS",
        set(
            bypass_users
            or []
        ),
    )

    monkeypatch.setattr(
        pam_bridge.Settings,
        "MFA_BYPASS_IPS",
        set(
            bypass_ips
            or []
        ),
    )

    monkeypatch.setattr(
        pam_bridge.Settings,
        "MFA_FAIL_MODE",
        "deny",
    )


def install_fake_backend(
    monkeypatch,
    *,
    blocked=True,
    enabled=True,
    temporary_bypass=False,
):
    bus = FakeRedisBus(
        blocked=blocked
    )

    runtime_holder = {}

    def fake_bus():
        return bus

    def fake_runtime(
        redis_client,
    ):
        runtime = FakeRuntime(
            redis_client,
            enabled=enabled,
            temporary_bypass=(
                temporary_bypass
            ),
        )

        runtime_holder[
            "runtime"
        ] = runtime

        return runtime

    monkeypatch.setattr(
        pam_bridge,
        "RedisBus",
        fake_bus,
    )

    monkeypatch.setattr(
        pam_bridge,
        "MFARuntime",
        fake_runtime,
    )

    return (
        bus,
        runtime_holder,
    )


def forbid_mfa_request(
    monkeypatch,
):
    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Une demande MFA ne devait "
            "pas être créée."
        )

    monkeypatch.setattr(
        pam_bridge,
        "rpc_create",
        forbidden,
    )


# ============================================================
# TEST 1
#
# Pays bloqué + MFA actif
# => refus immédiat
# => aucune demande MFA
# ============================================================

def test_blocked_country_denied_before_mfa(
    monkeypatch,
):
    configure_pam_env(
        monkeypatch
    )

    configure_settings(
        monkeypatch
    )

    bus, runtime_holder = (
        install_fake_backend(
            monkeypatch,
            blocked=True,
            enabled=True,
        )
    )

    forbid_mfa_request(
        monkeypatch
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam_bridge.main()

    assert exc.value.code == 1

    assert (
        f"security:blocked-country:{IP}"
        in bus.client.exists_calls
    )

    #
    # Le contrôle Security intervient avant
    # runtime.enabled().
    #
    runtime = runtime_holder[
        "runtime"
    ]

    assert (
        runtime.enabled_called
        is False
    )


# ============================================================
# TEST 2
#
# Pays bloqué + bypass utilisateur permanent
# => Security gagne
# ============================================================

def test_blocked_country_beats_user_bypass(
    monkeypatch,
):
    configure_pam_env(
        monkeypatch
    )

    configure_settings(
        monkeypatch,
        bypass_users={
            USER,
        },
    )

    install_fake_backend(
        monkeypatch,
        blocked=True,
        enabled=True,
    )

    forbid_mfa_request(
        monkeypatch
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam_bridge.main()

    assert exc.value.code == 1


# ============================================================
# TEST 3
#
# Pays bloqué + bypass IP permanent
# => Security gagne
# ============================================================

def test_blocked_country_beats_ip_bypass(
    monkeypatch,
):
    configure_pam_env(
        monkeypatch
    )

    configure_settings(
        monkeypatch,
        bypass_ips={
            IP,
        },
    )

    install_fake_backend(
        monkeypatch,
        blocked=True,
        enabled=True,
    )

    forbid_mfa_request(
        monkeypatch
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam_bridge.main()

    assert exc.value.code == 1


# ============================================================
# TEST 4
#
# Pays bloqué + bypass temporaire Redis
# => Security gagne avant le bypass temporaire
# ============================================================

def test_blocked_country_beats_temporary_bypass(
    monkeypatch,
):
    configure_pam_env(
        monkeypatch
    )

    configure_settings(
        monkeypatch
    )

    _, runtime_holder = (
        install_fake_backend(
            monkeypatch,
            blocked=True,
            enabled=True,
            temporary_bypass=True,
        )
    )

    forbid_mfa_request(
        monkeypatch
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam_bridge.main()

    assert exc.value.code == 1

    runtime = runtime_holder[
        "runtime"
    ]

    #
    # Le bypass temporaire ne doit même
    # pas être consulté.
    #
    assert (
        runtime.temp_bypass_called
        is False
    )


# ============================================================
# TEST 5
#
# Pays bloqué + MFA runtime OFF
# => toujours refusé.
#
# Désactiver le MFA ne désactive jamais
# les politiques Security.
# ============================================================

def test_blocked_country_denied_even_when_mfa_disabled(
    monkeypatch,
):
    configure_pam_env(
        monkeypatch
    )

    configure_settings(
        monkeypatch
    )

    _, runtime_holder = (
        install_fake_backend(
            monkeypatch,
            blocked=True,
            enabled=False,
        )
    )

    forbid_mfa_request(
        monkeypatch
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam_bridge.main()

    assert exc.value.code == 1

    runtime = runtime_holder[
        "runtime"
    ]

    assert (
        runtime.enabled_called
        is False
    )


# ============================================================
# TEST 6
#
# Pays NON bloqué + MFA OFF
# => connexion autorisée normalement.
# ============================================================

def test_allowed_country_with_mfa_disabled_is_allowed(
    monkeypatch,
):
    configure_pam_env(
        monkeypatch
    )

    configure_settings(
        monkeypatch
    )

    install_fake_backend(
        monkeypatch,
        blocked=False,
        enabled=False,
    )

    forbid_mfa_request(
        monkeypatch
    )

    with pytest.raises(
        SystemExit
    ) as exc:
        pam_bridge.main()

    assert exc.value.code == 0
