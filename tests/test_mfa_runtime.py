import json

import pytest

import services.mfa.app.runtime as runtime_module
from services.mfa.app.runtime import MFARuntime


IP = "203.0.113.20"


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expirations = {}

    def get(self, key):
        return self.values.get(key)

    def set(
        self,
        key,
        value,
        ex=None,
        **kwargs,
    ):
        self.values[key] = value

        if ex is not None:
            self.expirations[key] = int(ex)

        return True

    def delete(self, key):
        existed = key in self.values

        self.values.pop(
            key,
            None,
        )

        self.expirations.pop(
            key,
            None,
        )

        return int(existed)

    def exists(self, key):
        return int(
            key in self.values
        )

    def ttl(self, key):
        return self.expirations.get(
            key,
            -1,
        )

    def scan_iter(self, match=None):
        prefix = (
            match[:-1]
            if match and match.endswith("*")
            else match
        )

        for key in list(self.values):
            if (
                prefix is None
                or key.startswith(prefix)
            ):
                yield key


def test_enabled_falls_back_to_settings(
    monkeypatch,
):
    redis = FakeRedis()

    monkeypatch.setattr(
        runtime_module.Settings,
        "MFA_ENABLED",
        True,
    )

    assert MFARuntime(redis).enabled() is True


@pytest.mark.parametrize(
    "value",
    [
        "1",
        "true",
        "yes",
        "on",
        b"true",
    ],
)
def test_enabled_truthy_values(value):
    redis = FakeRedis()

    redis.values[
        MFARuntime.ENABLED_KEY
    ] = value

    assert MFARuntime(redis).enabled() is True


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "false",
        "off",
        "no",
        "anything",
    ],
)
def test_enabled_false_values(value):
    redis = FakeRedis()

    redis.values[
        MFARuntime.ENABLED_KEY
    ] = value

    assert MFARuntime(redis).enabled() is False


def test_set_enabled():
    redis = FakeRedis()
    runtime = MFARuntime(redis)

    assert runtime.set_enabled(True) is True
    assert runtime.enabled() is True

    assert runtime.set_enabled(False) is False
    assert runtime.enabled() is False


def test_timeout_falls_back_to_settings(
    monkeypatch,
):
    redis = FakeRedis()

    monkeypatch.setattr(
        runtime_module.Settings,
        "MFA_TIMEOUT_SECONDS",
        45,
    )

    assert (
        MFARuntime(redis).timeout_seconds()
        == 45
    )


def test_invalid_timeout_value_falls_back(
    monkeypatch,
):
    redis = FakeRedis()

    redis.values[
        MFARuntime.TIMEOUT_KEY
    ] = "invalid"

    monkeypatch.setattr(
        runtime_module.Settings,
        "MFA_TIMEOUT_SECONDS",
        45,
    )

    assert (
        MFARuntime(redis).timeout_seconds()
        == 45
    )


def test_set_timeout_minimum():
    runtime = MFARuntime(
        FakeRedis()
    )

    assert runtime.set_timeout(10) == 10


def test_set_timeout_maximum():
    runtime = MFARuntime(
        FakeRedis()
    )

    assert runtime.set_timeout(300) == 300


@pytest.mark.parametrize(
    "seconds",
    [
        0,
        9,
        -1,
    ],
)
def test_timeout_too_small_is_rejected(
    seconds,
):
    runtime = MFARuntime(
        FakeRedis()
    )

    with pytest.raises(ValueError):
        runtime.set_timeout(seconds)


@pytest.mark.parametrize(
    "seconds",
    [
        301,
        1000,
    ],
)
def test_timeout_too_large_is_rejected(
    seconds,
):
    runtime = MFARuntime(
        FakeRedis()
    )

    with pytest.raises(ValueError):
        runtime.set_timeout(seconds)


def test_allow_ip_stores_bypass():
    redis = FakeRedis()

    runtime = MFARuntime(redis)

    result = runtime.allow_ip(
        IP,
        3600,
        source="test",
    )

    key = runtime.bypass_key(IP)

    assert key in redis.values
    assert redis.expirations[key] == 3600

    payload = json.loads(
        redis.values[key]
    )

    assert payload["ip"] == IP
    assert payload["source"] == "test"
    assert payload["duration"] == 3600

    assert result["ip"] == IP
    assert result["ttl"] == 3600


@pytest.mark.parametrize(
    "duration",
    [
        0,
        -1,
        604801,
    ],
)
def test_invalid_bypass_duration_is_rejected(
    duration,
):
    runtime = MFARuntime(
        FakeRedis()
    )

    with pytest.raises(ValueError):
        runtime.allow_ip(
            IP,
            duration,
        )


def test_revoke_existing_ip():
    redis = FakeRedis()
    runtime = MFARuntime(redis)

    runtime.allow_ip(
        IP,
        60,
    )

    assert runtime.revoke_ip(IP) is True
    assert runtime.is_ip_allowed(IP) is False


def test_revoke_unknown_ip():
    runtime = MFARuntime(
        FakeRedis()
    )

    assert runtime.revoke_ip(IP) is False


def test_empty_ip_is_not_allowed():
    runtime = MFARuntime(
        FakeRedis()
    )

    assert runtime.is_ip_allowed("") is False
    assert runtime.is_ip_allowed(None) is False


def test_corrupted_bypass_json_is_tolerated():
    redis = FakeRedis()

    runtime = MFARuntime(redis)

    key = runtime.bypass_key(IP)

    redis.values[key] = "{bad-json"
    redis.expirations[key] = 42

    info = runtime.bypass_info(IP)

    assert info["ip"] == IP
    assert info["ttl"] == 42


def test_bytes_bypass_payload_is_supported():
    redis = FakeRedis()
    runtime = MFARuntime(redis)

    key = runtime.bypass_key(IP)

    redis.values[key] = (
        json.dumps(
            {
                "ip": IP,
                "source": "test",
            }
        ).encode()
    )

    redis.expirations[key] = 30

    info = runtime.bypass_info(IP)

    assert info["ip"] == IP
    assert info["ttl"] == 30


def test_list_bypasses_sorted_by_ttl():
    redis = FakeRedis()
    runtime = MFARuntime(redis)

    runtime.allow_ip(
        "203.0.113.1",
        10,
    )

    runtime.allow_ip(
        "203.0.113.2",
        100,
    )

    result = runtime.list_bypasses()

    assert result[0]["ip"] == "203.0.113.2"
    assert result[1]["ip"] == "203.0.113.1"


def test_runtime_status(
    monkeypatch,
):
    redis = FakeRedis()

    monkeypatch.setattr(
        runtime_module.Settings,
        "MFA_FAIL_MODE",
        "deny",
    )

    runtime = MFARuntime(redis)

    runtime.set_enabled(True)
    runtime.set_timeout(45)

    status = runtime.status()

    assert status["enabled"] is True
    assert status["timeout_seconds"] == 45
    assert status["fail_mode"] == "deny"
    assert status["temporary_bypasses"] == []
