import json
import sqlite3

import pytest

import services.api.app.repository as repo_module


SCHEMA = """
CREATE TABLE enriched_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT,
    ip TEXT,
    username TEXT,
    country TEXT,
    country_code TEXT,
    city TEXT,
    isp TEXT,
    timestamp TEXT
);

CREATE TABLE firewall_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    redis_id TEXT,
    event_type TEXT,
    ip TEXT,
    reason TEXT,
    payload TEXT,
    created_at TEXT
);
"""


@pytest.fixture
def repository(tmp_path, monkeypatch):
    db = tmp_path / "api-test.db"

    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        repo_module.Settings,
        "DB_PATH",
        db,
    )

    return repo_module.APIRepository(), db


def insert_event(
    db,
    event_type,
    ip,
    country=None,
    country_code=None,
    username=None,
    city=None,
    isp=None,
):
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO enriched_events (
                event_type,
                ip,
                username,
                country,
                country_code,
                city,
                isp,
                timestamp
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_type,
                ip,
                username,
                country,
                country_code,
                city,
                isp,
                "2026-08-12T12:00:00+00:00",
            ),
        )


def insert_firewall(
    db,
    redis_id,
    event_type,
    ip,
    reason="test",
    payload=None,
):
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO firewall_events (
                redis_id,
                event_type,
                ip,
                reason,
                payload,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                redis_id,
                event_type,
                ip,
                reason,
                (
                    json.dumps(payload)
                    if isinstance(payload, dict)
                    else payload
                ),
                "2026-08-12T12:00:00+00:00",
            ),
        )


def test_connect_uses_row_factory(
    repository,
):
    repo, _ = repository

    conn = repo.connect()

    try:
        assert conn.row_factory is sqlite3.Row
    finally:
        conn.close()


def test_stats_empty(repository):
    repo, _ = repository

    assert repo.stats() == {
        "events": 0,
        "connections": 0,
        "failed": 0,
        "success": 0,
        "unique_ips": 0,
        "bans": 0,
    }


def test_stats_counts_all_categories(repository):
    repo, db = repository

    insert_event(
        db,
        "ssh.connection.opened",
        "1.1.1.1",
    )

    insert_event(
        db,
        "ssh.login.failed",
        "1.1.1.1",
    )

    insert_event(
        db,
        "ssh.login.invalid_user",
        "2.2.2.2",
    )

    insert_event(
        db,
        "ssh.login.success",
        "3.3.3.3",
    )

    insert_event(
        db,
        "other",
        None,
    )

    insert_firewall(
        db,
        "1-0",
        "firewall.ip.banned",
        "1.1.1.1",
        payload={},
    )

    insert_firewall(
        db,
        "2-0",
        "firewall.ip.unbanned",
        "1.1.1.1",
        payload={},
    )

    result = repo.stats()

    assert result["events"] == 5
    assert result["connections"] == 1
    assert result["failed"] == 2
    assert result["success"] == 1

    # COUNT(DISTINCT ip) ignore NULL.
    assert result["unique_ips"] == 3
    assert result["bans"] == 1


def test_events_empty(repository):
    repo, _ = repository

    assert repo.events() == []


def test_events_order_and_limit(repository):
    repo, db = repository

    for i in range(5):
        insert_event(
            db,
            "ssh.login.failed",
            f"1.1.1.{i}",
        )

    result = repo.events(limit=2)

    assert len(result) == 2
    assert result[0]["id"] > result[1]["id"]


def test_events_filter_ip(repository):
    repo, db = repository

    insert_event(
        db,
        "ssh.login.failed",
        "1.1.1.1",
    )

    insert_event(
        db,
        "ssh.login.failed",
        "2.2.2.2",
    )

    result = repo.events(
        limit=100,
        ip="2.2.2.2",
    )

    assert len(result) == 1
    assert result[0]["ip"] == "2.2.2.2"


def test_firewall_history_valid_json(
    repository,
):
    repo, db = repository

    insert_firewall(
        db,
        "1-0",
        "firewall.ip.banned",
        "1.2.3.4",
        payload={
            "duration": 3600,
        },
    )

    result = repo.firewall_history()

    assert len(result) == 1
    assert result[0]["details"] == {
        "duration": 3600,
    }

    assert "payload" not in result[0]


def test_firewall_history_invalid_json(
    repository,
):
    repo, db = repository

    insert_firewall(
        db,
        "1-0",
        "firewall.ip.banned",
        "1.2.3.4",
        payload="{broken",
    )

    result = repo.firewall_history()

    assert result[0]["details"] == {}


def test_firewall_history_order_and_limit(
    repository,
):
    repo, db = repository

    for i in range(4):
        insert_firewall(
            db,
            f"{i}-0",
            "firewall.ip.banned",
            f"10.0.0.{i}",
            payload={},
        )

    result = repo.firewall_history(
        limit=2
    )

    assert len(result) == 2
    assert result[0]["id"] > result[1]["id"]


def test_active_bans_keeps_latest_state(
    repository,
):
    repo, db = repository

    # IP 1 : ban puis unban => inactive
    insert_firewall(
        db,
        "1-0",
        "firewall.ip.banned",
        "1.1.1.1",
        payload={},
    )

    insert_firewall(
        db,
        "2-0",
        "firewall.ip.unbanned",
        "1.1.1.1",
        payload={},
    )

    # IP 2 : unban puis ban => active
    insert_firewall(
        db,
        "3-0",
        "firewall.ip.unbanned",
        "2.2.2.2",
        payload={},
    )

    insert_firewall(
        db,
        "4-0",
        "firewall.ip.banned",
        "2.2.2.2",
        payload={},
    )

    # événement sans IP : ignoré
    insert_firewall(
        db,
        "5-0",
        "firewall.ip.banned",
        None,
        payload={},
    )

    result = repo.active_bans()

    assert len(result) == 1
    assert result[0]["ip"] == "2.2.2.2"
    assert (
        result[0]["event_type"]
        == "firewall.ip.banned"
    )


def test_top_ips_counts_only_attack_events(
    repository,
):
    repo, db = repository

    for _ in range(3):
        insert_event(
            db,
            "ssh.login.failed",
            "1.1.1.1",
            country="France",
            country_code="FR",
            city="Paris",
            isp="ISP1",
        )

    for _ in range(2):
        insert_event(
            db,
            "ssh.connection.reset",
            "2.2.2.2",
            country="Israel",
            country_code="IL",
            city="Haifa",
            isp="ISP2",
        )

    # Ne doit pas compter.
    for _ in range(10):
        insert_event(
            db,
            "ssh.login.success",
            "9.9.9.9",
        )

    result = repo.top_ips(limit=10)

    assert len(result) == 2

    assert result[0]["ip"] == "1.1.1.1"
    assert result[0]["attempts"] == 3

    assert result[1]["ip"] == "2.2.2.2"
    assert result[1]["attempts"] == 2


def test_top_ips_limit(repository):
    repo, db = repository

    for i in range(5):
        for _ in range(i + 1):
            insert_event(
                db,
                "ssh.login.failed",
                f"1.1.1.{i}",
            )

    result = repo.top_ips(limit=2)

    assert len(result) == 2
    assert result[0]["attempts"] >= result[1]["attempts"]


def test_top_countries_counts_and_unknown(
    repository,
):
    repo, db = repository

    for _ in range(3):
        insert_event(
            db,
            "ssh.login.failed",
            "1.1.1.1",
            country="France",
            country_code="FR",
        )

    for _ in range(2):
        insert_event(
            db,
            "ssh.connection.closed",
            "2.2.2.2",
            country=None,
            country_code=None,
        )

    # Ignoré.
    insert_event(
        db,
        "ssh.login.success",
        "3.3.3.3",
        country="Israel",
        country_code="IL",
    )

    result = repo.top_countries(
        limit=10
    )

    assert len(result) == 2

    france = next(
        x for x in result
        if x["country"] == "France"
    )

    unknown = next(
        x for x in result
        if x["country"] == "Unknown"
    )

    assert france["attempts"] == 3
    assert france["country_code"] == "FR"

    assert unknown["attempts"] == 2


def test_top_countries_limit(repository):
    repo, db = repository

    for i, country in enumerate(
        ["A", "B", "C"],
        start=1,
    ):
        for _ in range(i):
            insert_event(
                db,
                "ssh.login.invalid_user",
                f"10.0.0.{i}",
                country=country,
                country_code=country,
            )

    result = repo.top_countries(
        limit=1
    )

    assert len(result) == 1
    assert result[0]["attempts"] == 3
