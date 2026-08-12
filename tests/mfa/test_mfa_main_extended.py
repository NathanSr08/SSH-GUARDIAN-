import json

import pytest

import services.mfa.app.main as mfa_main


class FakeRedisClient:
    def __init__(self):
        self.pushes = []
        self.expirations = []

    def rpush(
        self,
        key,
        value,
    ):
        self.pushes.append(
            (
                key,
                value,
            )
        )

        return 1

    def expire(
        self,
        key,
        seconds,
    ):
        self.expirations.append(
            (
                key,
                seconds,
            )
        )

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
            return list(
                FakeBus.messages
            )

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


class Request:
    def __init__(
        self,
        request_id="req",
        ip="8.8.8.8",
        status="pending",
    ):
        self.request_id = request_id
        self.ip = ip
        self.status = status

    def to_dict(self):
        return {
            "request_id":
                self.request_id,
            "ip":
                self.ip,
            "status":
                self.status,
        }


class FakeManager:
    def __init__(self):
        self.timeout_seconds = 0
        self.list_calls = []

    def list_requests(
        self,
        status=None,
        limit=100,
    ):
        self.list_calls.append(
            (
                status,
                limit,
            )
        )

        return [
            Request(
                request_id="list-1"
            )
        ]


class FakeService:
    last = None

    def __init__(self, bus):
        FakeService.last = self

        self.bus = bus
        self.manager = FakeManager()
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(
            (
                "create",
                kwargs,
            )
        )

        return Request(
            request_id="created",
            ip=kwargs["ip"],
        )

    def approve(
        self,
        request_id,
        source="unknown",
    ):
        self.calls.append(
            (
                "approve",
                request_id,
                source,
            )
        )

        return Request(
            request_id=request_id,
            status="approved",
        )

    def deny(
        self,
        request_id,
        source="unknown",
    ):
        self.calls.append(
            (
                "deny",
                request_id,
                source,
            )
        )

        return Request(
            request_id=request_id,
            status="denied",
        )

    def get(
        self,
        request_id,
    ):
        self.calls.append(
            (
                "get",
                request_id,
            )
        )

        return Request(
            request_id=request_id,
        )


class FakeRuntime:
    last = None

    def __init__(self, client):
        FakeRuntime.last = self

        self.enabled_value = True
        self.timeout_value = 45
        self.allow_calls = []
        self.revoke_calls = []

    def enabled(self):
        return self.enabled_value

    def timeout_seconds(self):
        return self.timeout_value

    def status(self):
        return {
            "enabled":
                self.enabled_value,
            "timeout_seconds":
                self.timeout_value,
        }

    def set_timeout(self, value):
        self.timeout_value = int(
            value
        )

        return self.timeout_value

    def set_enabled(self, value):
        self.enabled_value = bool(
            value
        )

        return self.enabled_value

    def allow_ip(
        self,
        ip,
        duration,
        source="unknown",
    ):
        self.allow_calls.append(
            (
                ip,
                int(duration),
                source,
            )
        )

        return {
            "ip": ip,
            "duration":
                int(duration),
            "source": source,
            "ttl":
                int(duration),
        }

    def revoke_ip(self, ip):
        self.revoke_calls.append(ip)

        return True


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
        mfa_main,
        "RedisBus",
        FakeBus,
    )

    monkeypatch.setattr(
        mfa_main,
        "MFAService",
        FakeService,
    )

    monkeypatch.setattr(
        mfa_main,
        "MFARuntime",
        FakeRuntime,
    )


def run_main(
    monkeypatch,
    payload,
):
    setup(
        monkeypatch,
        payload,
    )

    with pytest.raises(
        KeyboardInterrupt
    ):
        mfa_main.main()

    bus = FakeBus.last

    assert bus is not None

    return (
        bus,
        FakeService.last,
        FakeRuntime.last,
    )


def reply_payload(bus):
    assert len(
        bus.client.pushes
    ) == 1

    key, raw = (
        bus.client.pushes[0]
    )

    return (
        key,
        json.loads(raw),
    )


def test_reply_without_request_id():
    bus = FakeBus()

    mfa_main.reply(
        bus,
        None,
        {
            "ok": True,
        },
    )

    assert (
        bus.client.pushes
        == []
    )


def test_reply_success():
    bus = FakeBus()

    mfa_main.reply(
        bus,
        "abc",
        {
            "ok": True,
        },
    )

    assert (
        bus.client.pushes[0][0]
        == "mfa.reply:abc"
    )

    assert (
        bus.client.expirations
        == [
            (
                "mfa.reply:abc",
                30,
            )
        ]
    )


def test_create(
    monkeypatch,
):
    bus, service, runtime = (
        run_main(
            monkeypatch,
            {
                "request_id": "rpc1",
                "command": "create",
                "username": "admin",
                "ip": "8.8.8.8",
                "country": "France",
                "country_code": "FR",
                "city": "Paris",
                "isp": "ISP",
            },
        )
    )

    assert (
        service.manager
        .timeout_seconds
        == 45
    )

    assert (
        service.calls[0][0]
        == "create"
    )

    key, response = (
        reply_payload(bus)
    )

    assert key == (
        "mfa.reply:rpc1"
    )

    assert response["ok"] is True

    assert (
        response["result"][
            "request_id"
        ]
        == "created"
    )


@pytest.mark.parametrize(
    "command,status",
    [
        (
            "approve",
            "approved",
        ),
        (
            "deny",
            "denied",
        ),
    ],
)
def test_approve_and_deny(
    monkeypatch,
    command,
    status,
):
    bus, service, _ = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": command,
            "mfa_request_id":
                "req1",
            "source": "panel",
        },
    )

    _, response = (
        reply_payload(bus)
    )

    assert response["ok"] is True

    assert (
        response["result"][
            "status"
        ]
        == status
    )


def test_approve_temporary(
    monkeypatch,
):
    bus, service, runtime = (
        run_main(
            monkeypatch,
            {
                "request_id": "rpc",
                "command":
                    "approve_temporary",
                "mfa_request_id":
                    "req1",
                "source": "telegram",
                "duration": 600,
            },
        )
    )

    _, response = (
        reply_payload(bus)
    )

    result = response["result"]

    assert (
        result["status"]
        == "approved"
    )

    assert (
        result[
            "temporary_bypass"
        ]["duration"]
        == 600
    )

    assert runtime.allow_calls == [
        (
            "8.8.8.8",
            600,
            "telegram",
        )
    ]


def test_approve_temporary_default_duration(
    monkeypatch,
):
    bus, _, runtime = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command":
                "approve_temporary",
            "mfa_request_id":
                "req1",
        },
    )

    assert runtime.allow_calls == [
        (
            "8.8.8.8",
            3600,
            "unknown",
        )
    ]


def test_get(
    monkeypatch,
):
    bus, service, _ = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": "get",
            "mfa_request_id":
                "req55",
        },
    )

    _, response = (
        reply_payload(bus)
    )

    assert (
        response["result"][
            "request_id"
        ]
        == "req55"
    )


def test_requests(
    monkeypatch,
):
    bus, service, _ = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": "requests",
            "status": "pending",
            "limit": "12",
        },
    )

    assert (
        service.manager.list_calls
        == [
            (
                "pending",
                12,
            )
        ]
    )

    _, response = (
        reply_payload(bus)
    )

    assert len(
        response["result"]
    ) == 1


def test_requests_defaults(
    monkeypatch,
):
    bus, service, _ = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": "requests",
        },
    )

    assert (
        service.manager.list_calls
        == [
            (
                None,
                100,
            )
        ]
    )


def test_status(
    monkeypatch,
):
    bus, _, _ = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": "status",
        },
    )

    _, response = (
        reply_payload(bus)
    )

    assert (
        response["result"][
            "enabled"
        ]
        is True
    )


def test_set_timeout(
    monkeypatch,
):
    bus, _, runtime = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": "set_timeout",
            "timeout_seconds": 90,
        },
    )

    _, response = (
        reply_payload(bus)
    )

    assert (
        runtime.timeout_value
        == 90
    )

    assert (
        response["result"][
            "timeout_seconds"
        ]
        == 90
    )


@pytest.mark.parametrize(
    "command,expected",
    [
        (
            "enable",
            True,
        ),
        (
            "disable",
            False,
        ),
    ],
)
def test_enable_disable(
    monkeypatch,
    command,
    expected,
):
    bus, _, runtime = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": command,
        },
    )

    _, response = (
        reply_payload(bus)
    )

    assert (
        runtime.enabled_value
        is expected
    )

    assert (
        response["result"][
            "enabled"
        ]
        is expected
    )


def test_allow_ip(
    monkeypatch,
):
    bus, _, runtime = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": "allow_ip",
            "ip": "8.8.8.8",
            "duration": 120,
            "source": "api",
        },
    )

    assert runtime.allow_calls == [
        (
            "8.8.8.8",
            120,
            "api",
        )
    ]

    _, response = (
        reply_payload(bus)
    )

    assert response["ok"] is True


def test_allow_ip_defaults(
    monkeypatch,
):
    _, _, runtime = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": "allow_ip",
            "ip": "8.8.8.8",
        },
    )

    assert runtime.allow_calls == [
        (
            "8.8.8.8",
            3600,
            "unknown",
        )
    ]


def test_allow_ip_missing(
    monkeypatch,
):
    bus, _, _ = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": "allow_ip",
            "ip": "   ",
        },
    )

    _, response = (
        reply_payload(bus)
    )

    assert response["ok"] is False
    assert (
        response["error"]
        == "IP manquante"
    )


def test_revoke_ip(
    monkeypatch,
):
    bus, _, runtime = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": "revoke_ip",
            "ip": "8.8.8.8",
        },
    )

    assert runtime.revoke_calls == [
        "8.8.8.8"
    ]

    _, response = (
        reply_payload(bus)
    )

    assert (
        response["result"][
            "revoked"
        ]
        is True
    )


def test_revoke_ip_missing(
    monkeypatch,
):
    bus, _, _ = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": "revoke_ip",
        },
    )

    _, response = (
        reply_payload(bus)
    )

    assert response["ok"] is False
    assert (
        response["error"]
        == "IP manquante"
    )


def test_unknown_command(
    monkeypatch,
):
    bus, _, _ = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": "wat",
        },
    )

    _, response = (
        reply_payload(bus)
    )

    assert response["ok"] is False

    assert (
        response["error"]
        == "Commande MFA inconnue"
    )


def test_command_exception_still_acked(
    monkeypatch,
):
    bus, _, _ = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": "create",
            # username volontairement absent
            "ip": "8.8.8.8",
        },
    )

    _, response = (
        reply_payload(bus)
    )

    assert response["ok"] is False

    assert len(
        bus.acks
    ) == 1


def test_success_message_is_acked(
    monkeypatch,
):
    bus, _, _ = run_main(
        monkeypatch,
        {
            "request_id": "rpc",
            "command": "status",
        },
    )

    assert bus.acks == [
        (
            mfa_main.Settings
            .MFA_COMMANDS_STREAM,
            "mfa",
            "1-0",
        )
    ]
