import pytest

from services.firewall.app.firewall import Firewall, FirewallError


def test_valid_ip():
    firewall = Firewall()

    assert firewall.validate_ip("1.2.3.4") == "1.2.3.4"


def test_invalid_ip():
    firewall = Firewall()

    with pytest.raises(FirewallError):
        firewall.validate_ip("pas-une-ip")


def test_localhost_whitelisted():
    firewall = Firewall()

    assert firewall.is_whitelisted("127.0.0.1")


def test_dry_run_ban():
    firewall = Firewall()
    firewall.enabled = False

    result = firewall.ban("1.2.3.4")

    assert result["status"] == "dry_run"
    assert result["action"] == "ban"
