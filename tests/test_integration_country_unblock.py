from types import SimpleNamespace

import services.control.app.country_manager as country_module
from services.control.app.country_manager import (
    CountryManager,
)


IP = "203.0.113.210"


class Redis:
    def __init__(self):
        self.values = {
            f"security:blocked-country:{IP}":
                "il",

            f"security:country-policy:{IP}":
                "blocked",

            f"security:attempts:{IP}":
                "attempt-state",
        }

        self.deleted = []

    def scan_iter(
        self,
        match=None,
        count=None,
    ):
        for key in list(
            self.values
        ):
            if key.startswith(
                "security:blocked-country:"
            ):
                yield key

    def get(self, key):
        return self.values.get(
            key
        )

    def delete(self, *keys):
        self.deleted.extend(keys)

        count = 0

        for key in keys:
            if key in self.values:
                count += 1

            self.values.pop(
                key,
                None,
            )

        return count


class Bus:
    def __init__(self):
        self.client = Redis()
        self.events = []

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

        return "1-0"


class Control:
    def country_code(
        self,
        value,
    ):
        if str(value).lower() in {
            "il",
            "israel",
        }:
            return "il"

        return None


class Firewall:
    def __init__(self):
        self.calls = []

    def unban(self, ip):
        self.calls.append(ip)

        return {
            "status": "unbanned",
            "ip": ip,
        }


def test_country_unblock_resets_firewall_and_all_security_state(
    monkeypatch,
):
    firewall = Firewall()

    monkeypatch.setattr(
        country_module,
        "Firewall",
        lambda:
            firewall,
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

    bus = Bus()

    manager = CountryManager(
        bus,
        Control(),
    )

    result = manager.unblock(
        "IL",
        source="integration-test",
    )

    assert firewall.calls == [
        IP
    ]

    assert (
        bus.client.get(
            f"security:blocked-country:{IP}"
        )
        is None
    )

    assert (
        bus.client.get(
            f"security:country-policy:{IP}"
        )
        is None
    )

    assert (
        bus.client.get(
            f"security:attempts:{IP}"
        )
        is None
    )

    assert "1 IP(s)" in result

    event_types = [
        payload["event_type"]
        for _stream, payload
        in bus.events
    ]

    assert (
        "firewall.ip.unbanned"
        in event_types
    )

    assert (
        "security.country.unblocked"
        in event_types
    )


def test_unblock_still_resets_redis_if_firewall_rule_already_absent(
    monkeypatch,
):
    class MissingFirewall:
        def unban(self, ip):
            return {
                "status":
                    "not_present",
                "ip":
                    ip,
            }

    monkeypatch.setattr(
        country_module,
        "Firewall",
        MissingFirewall,
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

    bus = Bus()

    manager = CountryManager(
        bus,
        Control(),
    )

    manager.unblock(
        "IL",
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
        not in bus.client.values
    )
