from types import SimpleNamespace

import services.control.app.country_manager as country_module
from services.control.app.country_manager import (
    CountryManager,
    FirewallError,
)


IP = "203.0.113.80"


class Redis:
    def __init__(self):
        self.values = {}

    def scan_iter(
        self,
        match=None,
        count=None,
    ):
        return list(
            self.values.keys()
        )

    def get(self, key):
        return self.values.get(key)

    def delete(self, *keys):
        for key in keys:
            self.values.pop(
                key,
                None,
            )


class Bus:
    def __init__(self):
        self.client = Redis()
        self.events = []

    def publish(
        self,
        stream,
        payload,
    ):
        self.events.append(payload)
        return "1-0"


class Control:
    def country_code(self, value):
        value = value.lower()

        if value in {
            "il",
            "israel",
        }:
            return "il"

        return None


class Firewall:
    def __init__(self):
        self.mode = "success"

    def unban(self, ip):
        if self.mode == "error":
            raise FirewallError(
                "firewall error"
            )

        if self.mode == "exception":
            raise RuntimeError(
                "unexpected"
            )

        if self.mode == "missing":
            return {
                "status":
                    "not_present",
            }

        return {
            "status": "unbanned",
            "ip": ip,
        }


def manager(monkeypatch):
    monkeypatch.setattr(
        country_module,
        "Firewall",
        Firewall,
    )

    return CountryManager(
        Bus(),
        Control(),
    )


def ok_run(*a, **k):
    return SimpleNamespace(
        returncode=0,
        stdout="",
        stderr="",
    )


def test_block_unknown(
    monkeypatch,
):
    m = manager(monkeypatch)

    assert (
        m.block("xxx")
        == "❌ Pays inconnu."
    )


def test_block_script_error(
    monkeypatch,
):
    m = manager(monkeypatch)

    monkeypatch.setattr(
        country_module.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="boom",
            ),
    )

    assert "boom" in (
        m.block("IL")
    )


def test_block_success_publishes(
    monkeypatch,
):
    m = manager(monkeypatch)

    monkeypatch.setattr(
        country_module.subprocess,
        "run",
        ok_run,
    )

    text = m.block(
        "IL",
        source="test",
    )

    assert "IL" in text

    event = m.bus.events[-1]

    assert (
        event["event_type"]
        == "security.country.blocked"
    )

    assert event["source"] == "test"


def test_get_country_ips_filters_other_country(
    monkeypatch,
):
    m = manager(monkeypatch)

    m.bus.client.values = {
        f"security:blocked-country:{IP}":
            "il",
        "security:blocked-country:203.0.113.81":
            "ru",
    }

    assert (
        m.get_country_banned_ips(
            "IL"
        )
        == [IP]
    )


def test_unblock_script_failure_keeps_state(
    monkeypatch,
):
    m = manager(monkeypatch)

    m.bus.client.values[
        f"security:blocked-country:{IP}"
    ] = "il"

    monkeypatch.setattr(
        country_module.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="failed",
            ),
    )

    text = m.unblock("IL")

    assert "failed" in text

    assert (
        f"security:blocked-country:{IP}"
        in m.bus.client.values
    )


def test_unblock_firewall_not_present_still_cleans_redis(
    monkeypatch,
):
    m = manager(monkeypatch)

    m.firewall.mode = "missing"

    for prefix in (
        "security:blocked-country:",
        "security:country-policy:",
        "security:attempts:",
    ):
        m.bus.client.values[
            prefix + IP
        ] = "x"

    m.bus.client.values[
        f"security:blocked-country:{IP}"
    ] = "il"

    monkeypatch.setattr(
        country_module.subprocess,
        "run",
        ok_run,
    )

    text = m.unblock("IL")

    assert "aucune règle" in (
        text.lower()
    )

    for prefix in (
        "security:blocked-country:",
        "security:country-policy:",
        "security:attempts:",
    ):
        assert (
            prefix + IP
            not in m.bus.client.values
        )


def test_unblock_firewall_error_reported_and_cleaned(
    monkeypatch,
):
    m = manager(monkeypatch)

    m.firewall.mode = "error"

    m.bus.client.values[
        f"security:blocked-country:{IP}"
    ] = "il"

    monkeypatch.setattr(
        country_module.subprocess,
        "run",
        ok_run,
    )

    text = m.unblock("IL")

    assert "1 erreur" in text

    assert (
        f"security:blocked-country:{IP}"
        not in m.bus.client.values
    )


def test_unblock_no_ips(
    monkeypatch,
):
    m = manager(monkeypatch)

    monkeypatch.setattr(
        country_module.subprocess,
        "run",
        ok_run,
    )

    text = m.unblock("IL")

    assert "Aucune IP" in text


def test_countries_empty(
    monkeypatch,
):
    m = manager(monkeypatch)

    monkeypatch.setattr(
        country_module.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                returncode=0,
                stdout="\n",
                stderr="",
            ),
    )

    assert (
        m.countries()
        == "📜 Aucun pays bloqué."
    )


def test_countries_list(
    monkeypatch,
):
    m = manager(monkeypatch)

    monkeypatch.setattr(
        country_module.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                returncode=0,
                stdout="il\nru\n",
                stderr="",
            ),
    )

    text = m.countries()

    assert "• IL" in text
    assert "• RU" in text
