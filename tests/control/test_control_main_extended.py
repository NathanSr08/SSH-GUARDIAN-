import json

import pytest

import services.control.app.main as control_main


class FakeRedisClient:
    def __init__(self):
        self.pushes = []
        self.expirations = []

    def rpush(self, key, value):
        self.pushes.append((key, value))
        return 1

    def expire(self, key, ttl):
        self.expirations.append((key, ttl))
        return True


class FakeBus:
    last = None
    messages = []

    def __init__(self):
        FakeBus.last = self
        self.client = FakeRedisClient()
        self.consume_count = 0
        self.acks = []

    def ping(self):
        return True

    def consume(self, **kwargs):
        self.consume_count += 1

        if self.consume_count == 1:
            return list(FakeBus.messages)

        raise KeyboardInterrupt

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


class FakeManager:
    last = None

    def __init__(self):
        FakeManager.last = self
        self.calls = []

    def stats(self):
        self.calls.append(("stats",))
        return "stats"

    def top(self):
        self.calls.append(("top",))
        return "top"

    def topcountries(self):
        self.calls.append(("topcountries",))
        return "topcountries"

    def search(self, ip):
        self.calls.append(("search", ip))
        return f"search:{ip}"

    def bans(self):
        self.calls.append(("bans",))
        return "bans"

    def unban(self, ip):
        self.calls.append(("unban", ip))
        return f"unban:{ip}"

    def country_code(self, value):
        return value.lower()


class FakeSessions:
    last = None

    def __init__(self):
        FakeSessions.last = self
        self.calls = []

    def sessions(self):
        self.calls.append(("sessions",))
        return "sessions"

    def active(self):
        self.calls.append(("active",))
        return "active"

    def kill(self, pid):
        self.calls.append(("kill", pid))
        return f"kill:{pid}"

    def kill_all(self):
        self.calls.append(("kill_all",))
        return "kill_all"


class FakeCountries:
    last = None

    def __init__(self, bus, manager):
        FakeCountries.last = self
        self.calls = []

    def block(self, country, source="unknown"):
        self.calls.append(
            ("block", country, source)
        )
        return f"block:{country}:{source}"

    def unblock(self, country, source="unknown"):
        self.calls.append(
            ("unblock", country, source)
        )
        return f"unblock:{country}:{source}"

    def countries(self):
        self.calls.append(("countries",))
        return "countries"


class FakeStreams:
    last = None

    def __init__(self, redis_client):
        FakeStreams.last = self
        self.calls = []

    def start(self, session_id, lines):
        self.calls.append(
            (
                "start",
                session_id,
                lines,
            )
        )

        return {
            "ok": True,
            "session_id": session_id,
            "lines": lines,
        }

    def get(self, stream_id):
        self.calls.append(
            ("get", stream_id)
        )

        return {
            "ok": True,
            "stream_id": stream_id,
        }

    def stop(self, stream_id):
        self.calls.append(
            ("stop", stream_id)
        )

        return {
            "ok": True,
            "stream_id": stream_id,
        }


def setup(
    monkeypatch,
    payload,
):
    FakeBus.messages = [
        (
            "1-0",
            payload,
        )
    ]

    monkeypatch.setattr(
        control_main,
        "RedisBus",
        FakeBus,
    )

    monkeypatch.setattr(
        control_main,
        "ControlManager",
        FakeManager,
    )

    monkeypatch.setattr(
        control_main,
        "SessionManager",
        FakeSessions,
    )

    monkeypatch.setattr(
        control_main,
        "CountryManager",
        FakeCountries,
    )

    monkeypatch.setattr(
        control_main,
        "SessionStreamManager",
        FakeStreams,
    )


def run_command(
    monkeypatch,
    command,
    args=None,
    source="api",
):
    setup(
        monkeypatch,
        {
            "request_id": "rpc1",
            "command": command,
            "args": args or [],
            "source": source,
        },
    )

    with pytest.raises(
        KeyboardInterrupt
    ):
        control_main.main()

    return FakeBus.last


def reply_payload(bus):
    key, raw = (
        bus.client.pushes[0]
    )

    return (
        key,
        json.loads(raw),
    )


@pytest.mark.parametrize(
    "command,args,expected",
    [
        ("stats", [], "stats"),
        ("top", [], "top"),
        ("topcountries", [], "topcountries"),
        ("search", ["1.2.3.4"], "search:1.2.3.4"),
        ("bans", [], "bans"),
        ("unban", ["1.2.3.4"], "unban:1.2.3.4"),
        ("sessions", [], "sessions"),
        ("active", [], "active"),
        ("killsession", ["123"], "kill:123"),
        ("killallsessions", [], "kill_all"),
        ("countries", [], "countries"),
    ],
)
def test_commands(
    monkeypatch,
    command,
    args,
    expected,
):
    bus = run_command(
        monkeypatch,
        command,
        args,
    )

    key, response = (
        reply_payload(bus)
    )

    assert key == "control.reply:rpc1"
    assert response["ok"] is True
    assert response["result"] == expected

    assert bus.acks == [
        (
            control_main.Settings
            .CONTROL_COMMANDS_STREAM,
            "control",
            "1-0",
        )
    ]


def test_stream_start_default_lines(
    monkeypatch,
):
    bus = run_command(
        monkeypatch,
        "stream_start",
        ["123"],
    )

    _, response = (
        reply_payload(bus)
    )

    assert response["ok"] is True

    assert (
        FakeStreams.last.calls
        == [
            (
                "start",
                "123",
                15,
            )
        ]
    )


def test_stream_start_custom_lines(
    monkeypatch,
):
    run_command(
        monkeypatch,
        "stream_start",
        ["123", "42"],
    )

    assert (
        FakeStreams.last.calls
        == [
            (
                "start",
                "123",
                42,
            )
        ]
    )


def test_stream_get(
    monkeypatch,
):
    run_command(
        monkeypatch,
        "stream_get",
        ["abc"],
    )

    assert (
        FakeStreams.last.calls
        == [
            (
                "get",
                "abc",
            )
        ]
    )


def test_stream_stop(
    monkeypatch,
):
    run_command(
        monkeypatch,
        "stream_stop",
        ["abc"],
    )

    assert (
        FakeStreams.last.calls
        == [
            (
                "stop",
                "abc",
            )
        ]
    )


def test_block_source(
    monkeypatch,
):
    run_command(
        monkeypatch,
        "block",
        ["il"],
        source="telegram",
    )

    assert (
        FakeCountries.last.calls
        == [
            (
                "block",
                "il",
                "telegram",
            )
        ]
    )


def test_unblock_source(
    monkeypatch,
):
    run_command(
        monkeypatch,
        "unblock",
        ["il"],
        source="panel",
    )

    assert (
        FakeCountries.last.calls
        == [
            (
                "unblock",
                "il",
                "panel",
            )
        ]
    )


def test_unknown_command(
    monkeypatch,
):
    bus = run_command(
        monkeypatch,
        "wat",
    )

    _, response = (
        reply_payload(bus)
    )

    assert response == {
        "ok": True,
        "result":
            "❌ Commande inconnue.",
    }


def test_command_exception_returns_error_and_acks(
    monkeypatch,
):
    # search sans args => IndexError
    bus = run_command(
        monkeypatch,
        "search",
        [],
    )

    _, response = (
        reply_payload(bus)
    )

    assert response["ok"] is False
    assert "error" in response

    assert len(bus.acks) == 1


def test_reply_ttl(
    monkeypatch,
):
    bus = run_command(
        monkeypatch,
        "stats",
    )

    assert (
        bus.client.expirations
        == [
            (
                "control.reply:rpc1",
                60,
            )
        ]
    )
