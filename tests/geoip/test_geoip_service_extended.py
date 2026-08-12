import pytest

import services.geoip.app.main as geo_main


class FakeClient:
    pass


class FakeBus:
    last = None

    def __init__(self):
        FakeBus.last = self

        self.client = FakeClient()
        self.consume_count = 0
        self.acks = []
        self.published = []

    def ping(self):
        return True

    def consume(self, **kwargs):
        self.consume_count += 1

        if self.consume_count == 1:
            return list(
                getattr(
                    self,
                    "messages",
                    [],
                )
            )

        raise KeyboardInterrupt

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

        return "999-0"

    def ack(
        self,
        stream,
        group,
        message_id,
    ):
        self.acks.append(
            (
                stream,
                group,
                message_id,
            )
        )


class FakeProvider:
    result = {
        "country": "France",
        "city": "Paris",
        "geo_cache": False,
    }

    def __init__(self, bus):
        self.bus = bus
        self.calls = []

    def lookup(self, ip):
        self.calls.append(ip)
        return dict(self.result)


def setup(
    monkeypatch,
    messages,
):
    monkeypatch.setattr(
        geo_main,
        "RedisBus",
        FakeBus,
    )

    monkeypatch.setattr(
        geo_main,
        "GeoIPProvider",
        FakeProvider,
    )

    original_init = FakeBus.__init__

    def init(self):
        original_init(self)
        self.messages = messages

    monkeypatch.setattr(
        FakeBus,
        "__init__",
        init,
    )


def test_geoip_worker_enriches_and_acks(
    monkeypatch,
):
    setup(
        monkeypatch,
        [
            (
                "1-0",
                {
                    "event_type":
                        "ssh.connection.opened",
                    "ip":
                        "8.8.8.8",
                },
            )
        ],
    )

    # main() intercepte lui-même KeyboardInterrupt.
    geo_main.main()

    bus = FakeBus.last

    assert len(bus.published) == 1

    stream, payload = (
        bus.published[0]
    )

    assert stream == (
        geo_main.Settings
        .SSH_ENRICHED_STREAM
    )

    assert payload["ip"] == "8.8.8.8"

    assert payload["geo"][
        "country"
    ] == "France"

    assert (
        payload["source_event_id"]
        == "1-0"
    )

    assert bus.acks == [
        (
            geo_main.Settings
            .SSH_EVENTS_STREAM,
            "geoip",
            "1-0",
        )
    ]


def test_geoip_worker_missing_ip_is_acked_without_publish(
    monkeypatch,
):
    setup(
        monkeypatch,
        [
            (
                "2-0",
                {
                    "event_type":
                        "ssh.connection.opened",
                },
            )
        ],
    )

    geo_main.main()

    bus = FakeBus.last

    assert bus.published == []

    assert bus.acks == [
        (
            geo_main.Settings
            .SSH_EVENTS_STREAM,
            "geoip",
            "2-0",
        )
    ]


def test_geoip_worker_multiple_messages(
    monkeypatch,
):
    setup(
        monkeypatch,
        [
            (
                "1-0",
                {
                    "ip": "8.8.8.8",
                },
            ),
            (
                "2-0",
                {
                    "ip": "1.1.1.1",
                },
            ),
        ],
    )

    geo_main.main()

    bus = FakeBus.last

    assert len(
        bus.published
    ) == 2

    assert len(
        bus.acks
    ) == 2
