from types import SimpleNamespace

import pytest

import services.firewall.app.firewall as firewall_module
from services.firewall.app.firewall import (
    Firewall,
    FirewallError,
)


IP = "203.0.113.10"


def make_fw(monkeypatch, enabled=True, whitelist=None):
    monkeypatch.setattr(
        firewall_module.Settings,
        "FIREWALL_ENABLED",
        enabled,
    )

    monkeypatch.setattr(
        firewall_module.Settings,
        "WHITELIST",
        set(whitelist or []),
    )

    return Firewall()


def test_ipv6_is_valid(monkeypatch):
    fw = make_fw(monkeypatch)

    assert fw.validate_ip(
        "2001:db8::1"
    ) == "2001:db8::1"


def test_whitelisted_ip_is_ignored(monkeypatch):
    fw = make_fw(
        monkeypatch,
        whitelist={IP},
    )

    result = fw.ban(IP)

    assert result == {
        "status": "ignored",
        "reason": "whitelisted",
        "ip": IP,
    }


def test_dry_run_unban(monkeypatch):
    fw = make_fw(
        monkeypatch,
        enabled=False,
    )

    result = fw.unban(IP)

    assert result == {
        "status": "dry_run",
        "action": "unban",
        "ip": IP,
    }


def test_existing_firewall_rule_is_not_inserted_again(
    monkeypatch,
):
    fw = make_fw(monkeypatch)

    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)

        return SimpleNamespace(
            returncode=0,
            stderr="",
        )

    monkeypatch.setattr(
        firewall_module.subprocess,
        "run",
        fake_run,
    )

    result = fw.ban(IP)

    assert result["status"] == "banned"
    assert len(calls) == 1
    assert "-C" in calls[0]


def test_missing_rule_is_inserted(monkeypatch):
    fw = make_fw(monkeypatch)

    calls = []

    responses = iter([
        SimpleNamespace(
            returncode=1,
            stderr="",
        ),
        SimpleNamespace(
            returncode=0,
            stderr="",
        ),
    ])

    def fake_run(args, **kwargs):
        calls.append(args)
        return next(responses)

    monkeypatch.setattr(
        firewall_module.subprocess,
        "run",
        fake_run,
    )

    result = fw.ban(IP)

    assert result["status"] == "banned"
    assert len(calls) == 2

    assert "-C" in calls[0]
    assert "-I" in calls[1]


def test_iptables_insert_error_raises(monkeypatch):
    fw = make_fw(monkeypatch)

    responses = iter([
        SimpleNamespace(
            returncode=1,
            stderr="",
        ),
        SimpleNamespace(
            returncode=2,
            stderr="permission denied",
        ),
    ])

    monkeypatch.setattr(
        firewall_module.subprocess,
        "run",
        lambda *args, **kwargs:
            next(responses),
    )

    with pytest.raises(
        FirewallError,
        match="permission denied",
    ):
        fw.ban(IP)


def test_unban_removes_all_duplicate_rules(
    monkeypatch,
):
    fw = make_fw(monkeypatch)

    calls = []

    responses = iter([
        SimpleNamespace(
            returncode=0,
            stderr="",
        ),
        SimpleNamespace(
            returncode=0,
            stderr="",
        ),
        SimpleNamespace(
            returncode=1,
            stderr="",
        ),
    ])

    def fake_run(args, **kwargs):
        calls.append(args)
        return next(responses)

    monkeypatch.setattr(
        firewall_module.subprocess,
        "run",
        fake_run,
    )

    result = fw.unban(IP)

    assert result == {
        "status": "unbanned",
        "ip": IP,
    }

    assert len(calls) == 3

    for call in calls:
        assert "-D" in call


def test_unban_invalid_ip_raises(monkeypatch):
    fw = make_fw(monkeypatch)

    with pytest.raises(FirewallError):
        fw.unban("not-an-ip")
