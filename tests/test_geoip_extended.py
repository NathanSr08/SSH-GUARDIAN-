import json

import pytest
import requests

import services.geoip.app.provider as geo_module
from services.geoip.app.provider import GeoIPProvider


PUBLIC_IP = "8.8.8.8"


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.deleted = []
        self.setex_calls = []

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        self.deleted.append(key)
        self.values.pop(key, None)
        return 1

    def setex(
        self,
        key,
        ttl,
        value,
    ):
        self.setex_calls.append(
            (key, ttl, value)
        )
        self.values[key] = value
        return True


class FakeBus:
    def __init__(self):
        self.client = FakeRedis()


class Response:
    def __init__(
        self,
        data=None,
        error=None,
    ):
        self.data = data or {}
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.data


def make_provider():
    bus = FakeBus()
    return GeoIPProvider(bus), bus


def test_cache_key():
    provider, _ = make_provider()

    assert (
        provider._cache_key(PUBLIC_IP)
        == f"geoip:{PUBLIC_IP}"
    )


def test_unknown_structure():
    provider, _ = make_provider()

    data = provider._unknown(
        "bad",
        "reason",
    )

    assert data["ip"] == "bad"
    assert data["country"] == "Inconnu"
    assert data["city"] == "Inconnu"
    assert data["isp"] == "Inconnu"
    assert data["geo_status"] == "reason"
    assert data["geo_cache"] is False


@pytest.mark.parametrize(
    "ip",
    [
        "invalid",
        "",
        "999.999.999.999",
    ],
)
def test_invalid_ip(ip):
    provider, _ = make_provider()

    result = provider.lookup(ip)

    assert (
        result["geo_status"]
        == "invalid_ip"
    )


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "192.168.1.1",
        "169.254.1.1",
        "::1",
        "2001:db8::1",
    ],
)
def test_private_or_reserved_ip(ip):
    provider, _ = make_provider()

    result = provider.lookup(ip)

    assert (
        result["geo_status"]
        == "private_or_reserved"
    )


def test_valid_cache_hit(
    monkeypatch,
):
    provider, bus = make_provider()

    key = (
        f"geoip:{PUBLIC_IP}"
    )

    bus.client.values[key] = json.dumps(
        {
            "ip": PUBLIC_IP,
            "country": "United States",
            "country_code": "US",
            "city": "Test",
            "geo_status": "success",
            "geo_cache": False,
        }
    )

    called = []

    monkeypatch.setattr(
        geo_module.requests,
        "get",
        lambda *a, **k:
            called.append(True),
    )

    result = provider.lookup(
        PUBLIC_IP
    )

    assert (
        result["country"]
        == "United States"
    )
    assert result["geo_cache"] is True
    assert called == []


def test_valid_cache_bytes():
    provider, bus = make_provider()

    key = (
        f"geoip:{PUBLIC_IP}"
    )

    bus.client.values[key] = (
        json.dumps(
            {
                "ip": PUBLIC_IP,
                "country": "USA",
                "geo_status": "success",
            }
        ).encode()
    )

    result = provider.lookup(
        PUBLIC_IP
    )

    assert result["country"] == "USA"
    assert result["geo_cache"] is True


def test_corrupt_cache_is_deleted_then_provider_used(
    monkeypatch,
):
    provider, bus = make_provider()

    key = (
        f"geoip:{PUBLIC_IP}"
    )

    bus.client.values[key] = (
        "{broken-json"
    )

    monkeypatch.setattr(
        geo_module.requests,
        "get",
        lambda *a, **k:
            Response(
                {
                    "status": "success",
                    "country": "United States",
                    "countryCode": "US",
                    "city": "Mountain View",
                }
            ),
    )

    result = provider.lookup(
        PUBLIC_IP
    )

    assert key in bus.client.deleted

    assert (
        result["geo_status"]
        == "success"
    )


def test_provider_timeout(
    monkeypatch,
):
    provider, _ = make_provider()

    def fail(*args, **kwargs):
        raise requests.Timeout(
            "timeout"
        )

    monkeypatch.setattr(
        geo_module.requests,
        "get",
        fail,
    )

    result = provider.lookup(
        PUBLIC_IP
    )

    assert (
        result["geo_status"]
        == "provider_error:Timeout"
    )


def test_provider_connection_error(
    monkeypatch,
):
    provider, _ = make_provider()

    def fail(*args, **kwargs):
        raise requests.ConnectionError(
            "offline"
        )

    monkeypatch.setattr(
        geo_module.requests,
        "get",
        fail,
    )

    result = provider.lookup(
        PUBLIC_IP
    )

    assert (
        result["geo_status"]
        == "provider_error:ConnectionError"
    )


def test_http_error(
    monkeypatch,
):
    provider, _ = make_provider()

    monkeypatch.setattr(
        geo_module.requests,
        "get",
        lambda *a, **k:
            Response(
                error=requests.HTTPError(
                    "500"
                )
            ),
    )

    result = provider.lookup(
        PUBLIC_IP
    )

    assert (
        result["geo_status"]
        == "provider_error:HTTPError"
    )


def test_provider_failed_status(
    monkeypatch,
):
    provider, _ = make_provider()

    monkeypatch.setattr(
        geo_module.requests,
        "get",
        lambda *a, **k:
            Response(
                {
                    "status": "fail",
                    "message":
                        "reserved range",
                }
            ),
    )

    result = provider.lookup(
        PUBLIC_IP
    )

    assert (
        result["geo_status"]
        == "reserved range"
    )


def test_provider_failed_without_message(
    monkeypatch,
):
    provider, _ = make_provider()

    monkeypatch.setattr(
        geo_module.requests,
        "get",
        lambda *a, **k:
            Response(
                {
                    "status": "fail",
                }
            ),
    )

    result = provider.lookup(
        PUBLIC_IP
    )

    assert (
        result["geo_status"]
        == "provider_failed"
    )


def test_successful_lookup_and_cache(
    monkeypatch,
):
    provider, bus = make_provider()

    raw = {
        "status": "success",
        "country": "United States",
        "countryCode": "US",
        "regionName": "California",
        "city": "Mountain View",
        "lat": 37.4,
        "lon": -122.1,
        "timezone":
            "America/Los_Angeles",
        "isp": "Google LLC",
        "org": "Google",
        "as": "AS15169 Google LLC",
    }

    calls = []

    def fake_get(
        url,
        params=None,
        timeout=None,
    ):
        calls.append(
            {
                "url": url,
                "params": params,
                "timeout": timeout,
            }
        )

        return Response(raw)

    monkeypatch.setattr(
        geo_module.requests,
        "get",
        fake_get,
    )

    result = provider.lookup(
        PUBLIC_IP
    )

    assert result == {
        "ip": PUBLIC_IP,
        "country": "United States",
        "country_code": "US",
        "city": "Mountain View",
        "region": "California",
        "isp": "Google LLC",
        "org": "Google",
        "asn": "AS15169 Google LLC",
        "lat": 37.4,
        "lon": -122.1,
        "timezone":
            "America/Los_Angeles",
        "geo_status": "success",
        "geo_cache": False,
    }

    assert len(calls) == 1

    assert calls[0]["url"] == (
        f"http://ip-api.com/json/{PUBLIC_IP}"
    )

    assert calls[0]["timeout"] == (
        geo_module.Settings.GEOIP_TIMEOUT
    )

    assert len(
        bus.client.setex_calls
    ) == 1

    key, ttl, encoded = (
        bus.client.setex_calls[0]
    )

    assert key == (
        f"geoip:{PUBLIC_IP}"
    )

    assert ttl == (
        geo_module.Settings.GEOIP_CACHE_TTL
    )

    assert (
        json.loads(encoded)["country"]
        == "United States"
    )


def test_success_missing_optional_values(
    monkeypatch,
):
    provider, _ = make_provider()

    monkeypatch.setattr(
        geo_module.requests,
        "get",
        lambda *a, **k:
            Response(
                {
                    "status": "success",
                    "country": "",
                    "city": None,
                    "isp": "",
                }
            ),
    )

    result = provider.lookup(
        PUBLIC_IP
    )

    assert result["country"] == "Inconnu"
    assert result["city"] == "Inconnu"
    assert result["isp"] == "Inconnu"
