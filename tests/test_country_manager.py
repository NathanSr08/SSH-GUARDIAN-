from types import SimpleNamespace

import services.control.app.country_manager as country_module
from services.control.app.country_manager import CountryManager


IP = "82.80.219.126"


class FakeRedis:
    def __init__(self):
        self.values = {
            f"security:blocked-country:{IP}": "il",
            f"security:country-policy:{IP}": "blocked",
        }

        self.hashes = {
            f"security:attempts:{IP}": {
                "attempts": "2",
                "max_attempts": "3",
                "remaining_attempts": "1",
            }
        }

        self.deleted = []

    def scan_iter(
        self,
        match=None,
        count=None,
    ):
        yield f"security:blocked-country:{IP}"

    def get(
        self,
        key,
    ):
        return self.values.get(key)

    def delete(
        self,
        *keys,
    ):
        self.deleted.extend(keys)

        deleted = 0

        for key in keys:
            if key in self.values:
                del self.values[key]
                deleted += 1

            if key in self.hashes:
                del self.hashes[key]
                deleted += 1

        return deleted


class FakeBus:
    def __init__(self):
        self.client = FakeRedis()
        self.published = []

    def publish(
        self,
        stream,
        payload,
    ):
        self.published.append(
            (
                stream,
                payload,
            )
        )

        return "1-0"


class FakeControlManager:
    def country_code(
        self,
        value,
    ):
        if value.lower() in {
            "il",
            "israel",
        }:
            return "il"

        return None


class FakeFirewall:
    def __init__(self):
        self.unbanned = []

    def unban(
        self,
        ip,
    ):
        self.unbanned.append(ip)

        return {
            "status": "unbanned",
            "ip": ip,
        }


def test_unblock_country_resets_ip_security_state(
    monkeypatch,
):
    bus = FakeBus()

    monkeypatch.setattr(
        country_module,
        "Firewall",
        FakeFirewall,
    )

    monkeypatch.setattr(
        country_module.subprocess,
        "run",
        lambda *args, **kwargs:
            SimpleNamespace(
                returncode=0,
                stdout="",
                stderr="",
            ),
    )

    manager = CountryManager(
        bus,
        FakeControlManager(),
    )

    result = manager.unblock(
        "IL",
        source="test",
    )

    assert (
        IP
        in manager.firewall.unbanned
    )

    expected = {
        f"security:blocked-country:{IP}",
        f"security:country-policy:{IP}",
        f"security:attempts:{IP}",
    }

    assert expected.issubset(
        set(bus.client.deleted)
    )

    assert (
        f"security:blocked-country:{IP}"
        not in bus.client.values
    )

    assert (
        f"security:country-policy:{IP}"
        not in bus.client.values
    )

    assert (
        f"security:attempts:{IP}"
        not in bus.client.hashes
    )

    assert "1 IP(s) débannie(s)" in result

    firewall_events = [
        payload
        for _, payload
        in bus.published
        if payload.get("event_type")
        == "firewall.ip.unbanned"
    ]

    assert len(
        firewall_events
    ) == 1

    assert (
        firewall_events[0]["ip"]
        == IP
    )

    assert (
        firewall_events[0]["reason"]
        == "country_unblocked"
    )


def test_unblock_unknown_country_does_nothing(
    monkeypatch,
):
    bus = FakeBus()

    monkeypatch.setattr(
        country_module,
        "Firewall",
        FakeFirewall,
    )

    manager = CountryManager(
        bus,
        FakeControlManager(),
    )

    result = manager.unblock(
        "ZZZZ",
        source="test",
    )

    assert result == "❌ Pays inconnu."

    assert (
        manager.firewall.unbanned
        == []
    )
