import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

import services.control.app.manager as manager_module
from services.control.app.manager import ControlManager


IP = "203.0.113.60"


class FakeFirewall:
    def __init__(self):
        self.calls = []

    def unban(self, ip):
        self.calls.append(ip)
        return {
            "status": "unbanned",
            "ip": ip,
        }


class FakeBus:
    def __init__(self):
        self.published = []

    def publish(self, stream, payload):
        self.published.append(
            (stream, payload)
        )
        return "1-0"


@pytest.fixture
def manager(tmp_path, monkeypatch):
    db = tmp_path / "guardian.db"

    conn = sqlite3.connect(db)

    conn.executescript(
        """
        CREATE TABLE enriched_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            ip TEXT,
            username TEXT,
            country TEXT,
            city TEXT,
            isp TEXT,
            timestamp TEXT
        );

        CREATE TABLE firewall_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            ip TEXT,
            reason TEXT,
            created_at TEXT
        );
        """
    )

    conn.close()

    monkeypatch.setattr(
        manager_module,
        "DB_PATH",
        str(db),
    )

    monkeypatch.setattr(
        manager_module,
        "Firewall",
        FakeFirewall,
    )

    monkeypatch.setattr(
        manager_module,
        "RedisBus",
        FakeBus,
    )

    return ControlManager()


def add_event(
    manager,
    event_type,
    ip=IP,
    username="admin",
    country="France",
    city="Paris",
    isp="Test ISP",
    timestamp="2026-08-12T12:00:00+00:00",
):
    with manager.db() as conn:
        conn.execute(
            """
            INSERT INTO enriched_events
            (
                event_type,
                ip,
                username,
                country,
                city,
                isp,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_type,
                ip,
                username,
                country,
                city,
                isp,
                timestamp,
            ),
        )


def test_stats_empty(manager):
    text = manager.stats()

    assert "Échecs : <code>0</code>" in text
    assert "Succès : <code>0</code>" in text
    assert "IP uniques : <code>0</code>" in text


def test_stats_counts_events(manager):
    add_event(
        manager,
        "ssh.login.failed",
    )

    add_event(
        manager,
        "ssh.login.success",
    )

    add_event(
        manager,
        "ssh.connection.reset",
        ip="203.0.113.61",
    )

    text = manager.stats()

    assert "Échecs : <code>2</code>" in text
    assert "Succès : <code>1</code>" in text
    assert "IP uniques : <code>2</code>" in text


def test_top_empty(manager):
    assert (
        manager.top()
        == "📭 Aucune tentative enregistrée."
    )


def test_top_groups_failures(manager):
    for _ in range(3):
        add_event(
            manager,
            "ssh.connection.closed",
        )

    text = manager.top()

    assert IP in text
    assert "Paris, France" in text
    assert "<b>3</b>" in text


def test_top_ignores_success(manager):
    add_event(
        manager,
        "ssh.login.success",
    )

    assert (
        manager.top()
        == "📭 Aucune tentative enregistrée."
    )


def test_topcountries_empty(manager):
    assert (
        manager.topcountries()
        == "📭 Aucun pays enregistré."
    )


def test_topcountries_counts(manager):
    add_event(
        manager,
        "ssh.login.failed",
        country="France",
    )

    add_event(
        manager,
        "ssh.connection.closed",
        ip="203.0.113.61",
        country="France",
    )

    add_event(
        manager,
        "ssh.connection.reset",
        ip="203.0.113.62",
        country="Spain",
    )

    text = manager.topcountries()

    assert "France — <b>2</b>" in text
    assert "Spain — <b>1</b>" in text


def test_search_invalid_ip(manager):
    assert (
        manager.search("bad-ip")
        == "❌ Adresse IP invalide."
    )


def test_search_unknown_ip(manager):
    text = manager.search(IP)

    assert "Aucun historique" in text
    assert IP in text


def test_search_success_and_failure(manager):
    add_event(
        manager,
        "ssh.login.success",
    )

    add_event(
        manager,
        "ssh.login.failed",
    )

    text = manager.search(IP)

    assert "Historique" in text
    assert "✅" in text
    assert "❌" in text
    assert "admin" in text
    assert "Paris" in text


def test_bans_empty(manager):
    assert (
        manager.bans()
        == "✅ Aucun ban enregistré."
    )


def test_bans_deduplicates_same_ip(manager):
    with manager.db() as conn:
        conn.execute(
            """
            INSERT INTO firewall_events
            (event_type, ip, reason, created_at)
            VALUES
            ('firewall.ip.banned', ?, 'first', '1'),
            ('firewall.ip.banned', ?, 'second', '2')
            """,
            (
                IP,
                IP,
            ),
        )

    text = manager.bans()

    assert text.count(IP) == 1
    assert "second" in text


def test_unban_invalid_ip(manager):
    assert (
        manager.unban("invalid")
        == "❌ Adresse IP invalide."
    )


def test_unban_calls_firewall_and_publishes(manager):
    text = manager.unban(IP)

    assert manager.firewall.calls == [IP]

    assert (
        manager.bus.published[0][1][
            "event_type"
        ]
        == "firewall.ip.unbanned"
    )

    assert "unbanned" in text


def test_country_code_iso(manager):
    assert manager.country_code("FR") == "fr"


def test_country_code_named(manager):
    assert manager.country_code("Israel") == "il"
    assert manager.country_code("russie") == "ru"


def test_country_code_unknown(manager):
    assert (
        manager.country_code(
            "not-a-country"
        )
        is None
    )


def test_country_action_unknown(manager):
    assert "Pays inconnu" in (
        manager.country_action(
            "block",
            "xxxx",
        )
    )


def test_country_action_dry_run(
    manager,
    monkeypatch,
):
    monkeypatch.setattr(
        manager_module.Settings,
        "FIREWALL_ENABLED",
        False,
    )

    text = manager.country_action(
        "block",
        "fr",
    )

    assert "DRY-RUN" in text
    assert "block fr" in text


def test_country_action_success(
    manager,
    monkeypatch,
):
    monkeypatch.setattr(
        manager_module.Settings,
        "FIREWALL_ENABLED",
        True,
    )

    monkeypatch.setattr(
        manager_module.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                returncode=0,
                stdout="",
                stderr="",
            ),
    )

    assert "bloqué" in (
        manager.country_action(
            "block",
            "fr",
        )
    )

    assert "débloqué" in (
        manager.country_action(
            "unblock",
            "fr",
        )
    )


def test_country_action_script_error(
    manager,
    monkeypatch,
):
    monkeypatch.setattr(
        manager_module.Settings,
        "FIREWALL_ENABLED",
        True,
    )

    monkeypatch.setattr(
        manager_module.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="boom",
            ),
    )

    assert "boom" in (
        manager.country_action(
            "block",
            "fr",
        )
    )


def test_countries_empty(
    manager,
    monkeypatch,
):
    monkeypatch.setattr(
        manager_module.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                stdout="",
            ),
    )

    assert (
        manager.countries()
        == "📜 Aucun pays bloqué."
    )


def test_countries_list(
    manager,
    monkeypatch,
):
    monkeypatch.setattr(
        manager_module.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                stdout="il\nru\n",
            ),
    )

    text = manager.countries()

    assert "• IL" in text
    assert "• RU" in text
