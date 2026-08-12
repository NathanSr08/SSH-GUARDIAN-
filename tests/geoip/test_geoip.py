from unittest.mock import Mock

from services.geoip.app.provider import GeoIPProvider


def test_invalid_ip():
    bus = Mock()

    provider = GeoIPProvider(bus)

    result = provider.lookup(
        "pas-une-ip"
    )

    assert result["geo_status"] == "invalid_ip"


def test_private_ip():
    bus = Mock()

    provider = GeoIPProvider(bus)

    result = provider.lookup(
        "127.0.0.1"
    )

    assert (
        result["geo_status"]
        == "private_or_reserved"
    )


def test_private_ipv4():
    bus = Mock()

    provider = GeoIPProvider(bus)

    result = provider.lookup(
        "192.168.1.10"
    )

    assert (
        result["geo_status"]
        == "private_or_reserved"
    )
