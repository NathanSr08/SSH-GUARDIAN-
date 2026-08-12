import json

import pytest

import services.api.app.control_client as control_module
import services.api.app.mfa_client as mfa_module


class FakeRedis:
    def __init__(self):
        self.responses = []
        self.deleted = []
        self.blpop_calls = []

    def blpop(self, key, timeout=0):
        self.blpop_calls.append((key, timeout))
        if not self.responses:
            return None
        return self.responses.pop(0)

    def delete(self, key):
        self.deleted.append(key)
        return 1


class FakeBus:
    def __init__(self):
        self.client = FakeRedis()
        self.published = []

    def publish(self, stream, payload):
        self.published.append((stream, payload))
        return "1-0"


# ============================================================
# ControlClient
# ============================================================

def make_control(monkeypatch):
    bus = FakeBus()

    monkeypatch.setattr(
        control_module,
        "RedisBus",
        lambda: bus,
    )

    monkeypatch.setattr(
        control_module.uuid,
        "uuid4",
        lambda: "fixed-control-id",
    )

    return control_module.ControlClient(), bus


def test_control_execute_success(monkeypatch):
    client, bus = make_control(monkeypatch)

    bus.client.responses.append(
        (
            b"control.reply:fixed-control-id",
            json.dumps({
                "ok": True,
                "result": {"done": True},
            }).encode(),
        )
    )

    result = client.execute(
        "unban",
        ["1.2.3.4"],
        timeout=7,
        source="panel",
    )

    assert result == {"done": True}

    assert len(bus.published) == 1

    stream, payload = bus.published[0]

    assert stream == control_module.Settings.CONTROL_COMMANDS_STREAM
    assert payload["request_id"] == "fixed-control-id"
    assert payload["command"] == "unban"
    assert payload["args"] == ["1.2.3.4"]
    assert payload["source"] == "panel"

    assert bus.client.blpop_calls == [
        ("control.reply:fixed-control-id", 7)
    ]


def test_control_execute_args_none_becomes_empty_list(
    monkeypatch,
):
    client, bus = make_control(monkeypatch)

    bus.client.responses.append(
        (
            b"x",
            b'{"ok": true, "result": "ok"}',
        )
    )

    assert client.execute("status") == "ok"

    payload = bus.published[0][1]

    assert payload["args"] == []
    assert payload["source"] == "api"


def test_control_execute_timeout(monkeypatch):
    client, bus = make_control(monkeypatch)

    with pytest.raises(
        TimeoutError,
        match="Control timeout: killallsessions",
    ):
        client.execute(
            "killallsessions",
            timeout=3,
        )

    assert bus.client.blpop_calls == [
        ("control.reply:fixed-control-id", 3)
    ]


def test_control_execute_remote_error(monkeypatch):
    client, bus = make_control(monkeypatch)

    bus.client.responses.append(
        (
            b"x",
            b'{"ok": false, "error": "boom"}',
        )
    )

    with pytest.raises(
        RuntimeError,
        match="boom",
    ):
        client.execute("unban")


def test_control_execute_remote_error_default(
    monkeypatch,
):
    client, bus = make_control(monkeypatch)

    bus.client.responses.append(
        (
            b"x",
            b'{"ok": false}',
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Control error",
    ):
        client.execute("test")


def test_control_execute_invalid_json(monkeypatch):
    client, bus = make_control(monkeypatch)

    bus.client.responses.append(
        (
            b"x",
            b"not-json",
        )
    )

    with pytest.raises(json.JSONDecodeError):
        client.execute("test")


def test_control_execute_success_none_result(
    monkeypatch,
):
    client, bus = make_control(monkeypatch)

    bus.client.responses.append(
        (
            b"x",
            b'{"ok": true}',
        )
    )

    assert client.execute("test") is None


# ============================================================
# MFAClient
# ============================================================

def make_mfa(monkeypatch):
    bus = FakeBus()

    monkeypatch.setattr(
        mfa_module,
        "RedisBus",
        lambda: bus,
    )

    monkeypatch.setattr(
        mfa_module.secrets,
        "token_urlsafe",
        lambda n: "fixed-mfa-id",
    )

    return mfa_module.MFAClient(), bus


def test_mfa_execute_success_bytes(monkeypatch):
    client, bus = make_mfa(monkeypatch)

    bus.client.responses.append(
        (
            b"mfa.reply:fixed-mfa-id",
            b'{"ok": true, "result": {"enabled": true}}',
        )
    )

    original = {
        "source": "panel",
    }

    result = client.execute(
        "status",
        original,
        timeout=8,
    )

    assert result == {
        "enabled": True,
    }

    # Le payload d'origine ne doit pas être muté.
    assert original == {
        "source": "panel",
    }

    assert bus.client.deleted == [
        "mfa.reply:fixed-mfa-id"
    ]

    assert bus.client.blpop_calls == [
        ("mfa.reply:fixed-mfa-id", 8)
    ]

    stream, payload = bus.published[0]

    assert stream == mfa_module.Settings.MFA_COMMANDS_STREAM
    assert payload["request_id"] == "fixed-mfa-id"
    assert payload["command"] == "status"
    assert payload["source"] == "panel"


def test_mfa_execute_success_string(monkeypatch):
    client, bus = make_mfa(monkeypatch)

    bus.client.responses.append(
        (
            "reply",
            '{"ok": true, "result": "yes"}',
        )
    )

    assert client.execute("enable") == "yes"


def test_mfa_execute_none_payload(monkeypatch):
    client, bus = make_mfa(monkeypatch)

    bus.client.responses.append(
        (
            "reply",
            '{"ok": true, "result": {}}',
        )
    )

    client.execute("status", None)

    payload = bus.published[0][1]

    assert payload == {
        "request_id": "fixed-mfa-id",
        "command": "status",
    }


def test_mfa_execute_timeout(monkeypatch):
    client, bus = make_mfa(monkeypatch)

    with pytest.raises(
        RuntimeError,
        match="Le service MFA ne répond pas",
    ):
        client.execute(
            "status",
            timeout=4,
        )

    assert bus.client.blpop_calls == [
        ("mfa.reply:fixed-mfa-id", 4)
    ]


def test_mfa_execute_remote_error(monkeypatch):
    client, bus = make_mfa(monkeypatch)

    bus.client.responses.append(
        (
            "reply",
            '{"ok": false, "error": "refusé"}',
        )
    )

    with pytest.raises(
        RuntimeError,
        match="refusé",
    ):
        client.execute("approve")


def test_mfa_execute_remote_error_default(
    monkeypatch,
):
    client, bus = make_mfa(monkeypatch)

    bus.client.responses.append(
        (
            "reply",
            '{"ok": false}',
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Erreur MFA inconnue",
    ):
        client.execute("approve")


def test_mfa_execute_invalid_json(monkeypatch):
    client, bus = make_mfa(monkeypatch)

    bus.client.responses.append(
        (
            "reply",
            "invalid-json",
        )
    )

    with pytest.raises(json.JSONDecodeError):
        client.execute("status")


def test_mfa_execute_success_none_result(
    monkeypatch,
):
    client, bus = make_mfa(monkeypatch)

    bus.client.responses.append(
        (
            "reply",
            '{"ok": true}',
        )
    )

    assert client.execute("status") is None
