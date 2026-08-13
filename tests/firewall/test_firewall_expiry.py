from datetime import (
    datetime,
    timedelta,
    timezone,
)

import services.firewall.app.main as firewall_main


IP = "203.0.113.77"


class Redis:
    def __init__(self):
        self.zsets = {}
        self.values = {}
        self.deleted = []

    def zadd(self, key, mapping):
        zset = self.zsets.setdefault(
            key,
            {}
        )
        zset.update(mapping)
        return 1

    def zrem(self, key, member):
        zset = self.zsets.setdefault(
            key,
            {}
        )

        existed = member in zset
        zset.pop(member, None)

        return int(existed)

    def zrangebyscore(
        self,
        key,
        minimum,
        maximum,
    ):
        zset = self.zsets.get(
            key,
            {}
        )

        maximum = float(maximum)

        return [
            member
            for member, score
            in zset.items()
            if float(score) <= maximum
        ]

    def delete(self, *keys):
        self.deleted.extend(keys)

        for key in keys:
            self.values.pop(
                key,
                None,
            )

        return len(keys)


class Bus:
    def __init__(self):
        self.client = Redis()
        self.events = []

    def publish(self, stream, payload):
        self.events.append(
            (
                stream,
                payload,
            )
        )
        return "1-0"


class Firewall:
    def __init__(self):
        self.unbans = []

    def unban(self, ip):
        self.unbans.append(ip)

        return {
            "status": "unbanned",
            "ip": ip,
        }


def test_schedule_ban_expiry_from_expires_at():
    bus = Bus()

    expires = datetime(
        2026,
        8,
        14,
        12,
        0,
        tzinfo=timezone.utc,
    )

    score = (
        firewall_main
        .schedule_ban_expiry(
            bus,
            IP,
            {
                "ban_duration_seconds":
                    86400,

                "expires_at":
                    expires.isoformat(),
            },
        )
    )

    assert score == (
        expires.timestamp()
    )

    assert (
        bus.client.zsets[
            firewall_main.BAN_EXPIRY_ZSET
        ][IP]
        == expires.timestamp()
    )


def test_schedule_without_explicit_expires_at(
    monkeypatch,
):
    bus = Bus()

    before = datetime.now(
        timezone.utc
    ).timestamp()

    score = (
        firewall_main
        .schedule_ban_expiry(
            bus,
            IP,
            {
                "ban_duration_seconds":
                    60,
            },
        )
    )

    after = datetime.now(
        timezone.utc
    ).timestamp()

    assert (
        before + 60
        <= score
        <= after + 60
    )


def test_no_schedule_without_duration():
    bus = Bus()

    result = (
        firewall_main
        .schedule_ban_expiry(
            bus,
            IP,
            {},
        )
    )

    assert result is None
    assert bus.client.zsets == {}


def test_no_schedule_invalid_duration():
    bus = Bus()

    result = (
        firewall_main
        .schedule_ban_expiry(
            bus,
            IP,
            {
                "ban_duration_seconds":
                    "invalid",
            },
        )
    )

    assert result is None


def test_future_ban_not_unbanned():
    bus = Bus()
    firewall = Firewall()

    now = datetime(
        2026,
        8,
        13,
        12,
        0,
        tzinfo=timezone.utc,
    )

    future = (
        now
        + timedelta(hours=1)
    )

    bus.client.zadd(
        firewall_main.BAN_EXPIRY_ZSET,
        {
            IP:
                future.timestamp(),
        },
    )

    result = (
        firewall_main
        .process_expired_bans(
            bus,
            firewall,
            now=now,
        )
    )

    assert result == []
    assert firewall.unbans == []

    assert (
        IP
        in bus.client.zsets[
            firewall_main.BAN_EXPIRY_ZSET
        ]
    )


def test_expired_ban_is_unbanned_and_cleaned():
    bus = Bus()
    firewall = Firewall()

    now = datetime(
        2026,
        8,
        13,
        12,
        0,
        tzinfo=timezone.utc,
    )

    expired = (
        now
        - timedelta(seconds=1)
    )

    bus.client.zadd(
        firewall_main.BAN_EXPIRY_ZSET,
        {
            IP:
                expired.timestamp(),
        },
    )

    bus.client.values[
        f"security:blocked-country:{IP}"
    ] = "il"

    bus.client.values[
        f"security:country-policy:{IP}"
    ] = "blocked"

    bus.client.values[
        f"security:attempts:{IP}"
    ] = "test"

    result = (
        firewall_main
        .process_expired_bans(
            bus,
            firewall,
            now=now,
        )
    )

    assert result == [IP]

    assert firewall.unbans == [
        IP
    ]

    assert (
        IP
        not in bus.client.zsets[
            firewall_main.BAN_EXPIRY_ZSET
        ]
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

    assert len(bus.events) == 1

    stream, event = bus.events[0]

    assert stream == (
        firewall_main.Settings
        .FIREWALL_EVENTS_STREAM
    )

    assert (
        event["event_type"]
        == "firewall.ip.unbanned"
    )

    assert (
        event["reason"]
        == "ban_expired"
    )

    assert event["ip"] == IP


def test_expiry_survives_service_restart():
    #
    # Le ZSET appartient à Redis, pas à l'instance
    # Python du firewall.
    #
    bus = Bus()

    expires = datetime(
        2026,
        8,
        13,
        12,
        0,
        tzinfo=timezone.utc,
    )

    firewall_main.schedule_ban_expiry(
        bus,
        IP,
        {
            "ban_duration_seconds":
                60,

            "expires_at":
                expires.isoformat(),
        },
    )

    #
    # "Redémarrage" :
    # nouvelle instance Firewall,
    # même Redis.
    #
    firewall_after_restart = (
        Firewall()
    )

    result = (
        firewall_main
        .process_expired_bans(
            bus,
            firewall_after_restart,
            now=(
                expires
                + timedelta(seconds=1)
            ),
        )
    )

    assert result == [IP]

    assert (
        firewall_after_restart.unbans
        == [IP]
    )
