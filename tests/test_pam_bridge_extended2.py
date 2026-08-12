import json
from types import SimpleNamespace

import pytest

import services.mfa.bin.pam_bridge as pam


class FakeClient:
    def __init__(self):
        self.blpop_result = None
        self.values = {}
        self.get_calls = 0

    def blpop(
        self,
        key,
        timeout=0,
    ):
        return self.blpop_result

    def get(self, key):
        self.get_calls += 1

        value = self.values.get(
            self.get_calls
        )

        return value


class FakeBus:
    def __init__(self):
        self.client = FakeClient()
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


def test_rpc_create_success(
    monkeypatch,
):
    bus = FakeBus()

    monkeypatch.setattr(
        pam.uuid,
        "uuid4",
        lambda:
            "rpc-fixed",
    )

    bus.client.blpop_result = (
        "mfa.reply:rpc-fixed",
        json.dumps(
            {
                "ok": True,
                "result": {
                    "request_id":
                        "req1",
                },
            }
        ),
    )

    result = pam.rpc_create(
        bus,
        "admin",
        "1.2.3.4",
    )

    assert result == {
        "request_id": "req1"
    }

    stream, payload = (
        bus.published[0]
    )

    assert stream == (
        pam.Settings
        .MFA_COMMANDS_STREAM
    )

    assert payload == {
        "request_id":
            "rpc-fixed",
        "command":
            "create",
        "username":
            "admin",
        "ip":
            "1.2.3.4",
        "source":
            "pam",
    }


def test_rpc_create_timeout(
    monkeypatch,
):
    bus = FakeBus()

    monkeypatch.setattr(
        pam.uuid,
        "uuid4",
        lambda:
            "rpc-fixed",
    )

    with pytest.raises(
        RuntimeError,
        match="MFA Service timeout",
    ):
        pam.rpc_create(
            bus,
            "admin",
            "1.2.3.4",
        )


def test_rpc_create_remote_error(
    monkeypatch,
):
    bus = FakeBus()

    bus.client.blpop_result = (
        "reply",
        json.dumps(
            {
                "ok": False,
                "error": "refused",
            }
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="refused",
    ):
        pam.rpc_create(
            bus,
            "admin",
            "1.2.3.4",
        )


def test_rpc_create_remote_error_default(
    monkeypatch,
):
    bus = FakeBus()

    bus.client.blpop_result = (
        "reply",
        json.dumps(
            {
                "ok": False,
            }
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="MFA Service error",
    ):
        pam.rpc_create(
            bus,
            "admin",
            "1.2.3.4",
        )


def test_rpc_create_invalid_json():
    bus = FakeBus()

    bus.client.blpop_result = (
        "reply",
        "{broken",
    )

    with pytest.raises(
        json.JSONDecodeError
    ):
        pam.rpc_create(
            bus,
            "admin",
            "1.2.3.4",
        )


def test_rpc_create_empty_result():
    bus = FakeBus()

    bus.client.blpop_result = (
        "reply",
        '{"ok": true}',
    )

    assert (
        pam.rpc_create(
            bus,
            "admin",
            "1.2.3.4",
        )
        == {}
    )


@pytest.mark.parametrize(
    "status",
    [
        "approved",
        "denied",
        "expired",
        "cancelled",
    ],
)
def test_wait_for_decision_terminal_status(
    monkeypatch,
    status,
):
    bus = FakeBus()

    bus.client.values[1] = (
        json.dumps(
            {
                "status":
                    status,
            }
        )
    )

    times = iter([
        0,
        0,
    ])

    monkeypatch.setattr(
        pam.time,
        "monotonic",
        lambda:
            next(
                times,
                999,
            ),
    )

    monkeypatch.setattr(
        pam.time,
        "sleep",
        lambda x: None,
    )

    assert (
        pam.wait_for_decision(
            bus,
            "req1",
            5,
        )
        == status
    )


def test_wait_for_decision_bytes():
    bus = FakeBus()

    bus.client.values[1] = (
        b'{"status":"approved"}'
    )

    assert (
        pam.wait_for_decision(
            bus,
            "req1",
            1,
        )
        == "approved"
    )


def test_wait_for_decision_pending_then_approved(
    monkeypatch,
):
    bus = FakeBus()

    bus.client.values = {
        1:
            '{"status":"pending"}',
        2:
            '{"status":"approved"}',
    }

    monkeypatch.setattr(
        pam.time,
        "sleep",
        lambda x: None,
    )

    values = iter(
        [
            0,
            0,
            0,
            0,
        ]
    )

    monkeypatch.setattr(
        pam.time,
        "monotonic",
        lambda:
            next(
                values,
                999,
            ),
    )

    assert (
        pam.wait_for_decision(
            bus,
            "req1",
            5,
        )
        == "approved"
    )


def test_wait_for_decision_missing_then_approved(
    monkeypatch,
):
    bus = FakeBus()

    bus.client.values = {
        1: None,
        2:
            '{"status":"approved"}',
    }

    monkeypatch.setattr(
        pam.time,
        "sleep",
        lambda x: None,
    )

    values = iter(
        [
            0,
            0,
            0,
            0,
        ]
    )

    monkeypatch.setattr(
        pam.time,
        "monotonic",
        lambda:
            next(
                values,
                999,
            ),
    )

    assert (
        pam.wait_for_decision(
            bus,
            "req1",
            5,
        )
        == "approved"
    )


def test_wait_for_decision_timeout(
    monkeypatch,
):
    bus = FakeBus()

    bus.client.values = {
        1: None,
    }

    values = iter(
        [
            0,
            10,
        ]
    )

    monkeypatch.setattr(
        pam.time,
        "monotonic",
        lambda:
            next(
                values,
                10,
            ),
    )

    monkeypatch.setattr(
        pam.time,
        "sleep",
        lambda x: None,
    )

    assert (
        pam.wait_for_decision(
            bus,
            "req1",
            1,
        )
        == "expired"
    )


def test_wait_for_decision_invalid_json():
    bus = FakeBus()

    bus.client.values[1] = (
        "{broken"
    )

    with pytest.raises(
        json.JSONDecodeError
    ):
        pam.wait_for_decision(
            bus,
            "req1",
            1,
        )
