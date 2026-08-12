from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import services.api.app.main as api


IP = "203.0.113.90"


class FakeRepo:
    def __init__(self):
        self.calls = []

    def stats(self):
        self.calls.append(("stats",))
        return {"events": 10}

    def events(
        self,
        limit=100,
        ip=None,
    ):
        self.calls.append(
            ("events", limit, ip)
        )

        return [
            {
                "ip": ip,
                "limit": limit,
            }
        ]

    def firewall_history(self):
        self.calls.append(
            ("firewall_history",)
        )

        return [
            {
                "ip": IP,
            }
        ]

    def active_bans(self):
        self.calls.append(
            ("active_bans",)
        )

        return [
            {
                "ip": IP,
                "active": True,
            }
        ]

    def top_ips(self, limit):
        self.calls.append(
            ("top_ips", limit)
        )

        return [
            {
                "ip": IP,
                "attempts": 3,
            }
        ]

    def top_countries(self, limit):
        self.calls.append(
            ("top_countries", limit)
        )

        return [
            {
                "country": "France",
                "attempts": 3,
            }
        ]


class FakeControl:
    def __init__(self):
        self.calls = []
        self.error = None

    def execute(
        self,
        command,
        args=None,
        source="api",
    ):
        self.calls.append(
            (
                command,
                args,
                source,
            )
        )

        if self.error:
            raise self.error

        return {
            "command": command,
            "args": args,
            "source": source,
        }


class FakeMFA:
    def __init__(self):
        self.calls = []
        self.error = None

    def execute(
        self,
        command,
        payload=None,
    ):
        self.calls.append(
            (
                command,
                payload,
            )
        )

        if self.error:
            raise self.error

        return {
            "command": command,
            "payload": payload,
        }


class FakeBus:
    def __init__(self):
        self.ping_value = True

    def ping(self):
        return self.ping_value


@pytest.fixture
def env(
    monkeypatch,
    tmp_path,
):
    repo = FakeRepo()
    control = FakeControl()
    mfa = FakeMFA()
    bus = FakeBus()

    monkeypatch.setattr(
        api,
        "repo",
        repo,
    )

    monkeypatch.setattr(
        api,
        "control",
        control,
    )

    monkeypatch.setattr(
        api,
        "mfa",
        mfa,
    )

    monkeypatch.setattr(
        api,
        "bus",
        bus,
    )

    blocked = (
        tmp_path
        / "blocked-countries.txt"
    )

    monkeypatch.setattr(
        api.Settings,
        "BLOCKED_COUNTRIES_FILE",
        blocked,
    )

    return {
        "client":
            TestClient(api.app),

        "repo":
            repo,

        "control":
            control,

        "mfa":
            mfa,

        "bus":
            bus,

        "blocked":
            blocked,
    }


# ============================================================
# Helpers système
# ============================================================

def test_service_status_systemd_active(
    monkeypatch,
):
    monkeypatch.setattr(
        api.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                stdout="active\n",
            ),
    )

    assert (
        api.service_status("security")
        == "active"
    )


def test_service_status_dev_pid_active(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        api.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                stdout="inactive\n",
            ),
    )

    monkeypatch.setattr(
        api.Settings,
        "RUN_DIR",
        tmp_path,
    )

    (
        tmp_path
        / "security.pid"
    ).write_text("123")

    monkeypatch.setattr(
        api.os,
        "kill",
        lambda pid, sig: None,
    )

    assert (
        api.service_status("security")
        == "active"
    )


@pytest.mark.parametrize(
    "content",
    [
        "bad-pid",
        "999",
    ],
)
def test_service_status_invalid_or_dead_pid(
    monkeypatch,
    tmp_path,
    content,
):
    monkeypatch.setattr(
        api.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                stdout="inactive\n",
            ),
    )

    monkeypatch.setattr(
        api.Settings,
        "RUN_DIR",
        tmp_path,
    )

    (
        tmp_path
        / "security.pid"
    ).write_text(content)

    def fake_kill(pid, sig):
        raise ProcessLookupError

    monkeypatch.setattr(
        api.os,
        "kill",
        fake_kill,
    )

    assert (
        api.service_status("security")
        == "inactive"
    )


def test_service_status_no_pidfile(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(
        api.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                stdout="inactive\n",
            ),
    )

    monkeypatch.setattr(
        api.Settings,
        "RUN_DIR",
        tmp_path,
    )

    assert (
        api.service_status("security")
        == "inactive"
    )


def test_network_sessions_parser(
    monkeypatch,
):
    output = (
        "ESTAB 0 0 "
        "10.0.0.1:22 "
        "203.0.113.1:50000 "
        'users:(("sshd-session",'
        "pid=123,fd=4))\n"
        "garbage\n"
    )

    monkeypatch.setattr(
        api.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                stdout=output
            ),
    )

    result = api.network_sessions()

    assert result["123"] == {
        "local_ip": "10.0.0.1",
        "remote_ip":
            "203.0.113.1",
    }


def test_find_session_log_pid(
    monkeypatch,
):
    monkeypatch.setattr(
        api.glob,
        "glob",
        lambda pattern:
            (
                ["/old", "/new"]
                if "session_123_" in pattern
                else []
            ),
    )

    monkeypatch.setattr(
        api.os.path,
        "getmtime",
        lambda p:
            2 if p == "/new" else 1,
    )

    result = api.find_session_log(
        "123",
        "12",
    )

    assert result == {
        "session_id": "123",
        "log_file": "/new",
    }


def test_find_session_log_ppid_fallback(
    monkeypatch,
):
    def fake_glob(pattern):
        if "session_12_" in pattern:
            return ["/parent"]

        return []

    monkeypatch.setattr(
        api.glob,
        "glob",
        fake_glob,
    )

    monkeypatch.setattr(
        api.os.path,
        "getmtime",
        lambda p: 1,
    )

    assert (
        api.find_session_log(
            "123",
            "12",
        )["session_id"]
        == "12"
    )


def test_find_session_log_none(
    monkeypatch,
):
    monkeypatch.setattr(
        api.glob,
        "glob",
        lambda pattern: [],
    )

    assert (
        api.find_session_log(
            "123",
            "12",
        )
        is None
    )


def test_active_sessions_parser(
    monkeypatch,
):
    output = (
        "123 12 root "
        "sshd-session: admin@pts/0\n"
        "999 1 root python app.py\n"
    )

    monkeypatch.setattr(
        api.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                stdout=output
            ),
    )

    monkeypatch.setattr(
        api,
        "network_sessions",
        lambda: {
            "123": {
                "remote_ip": IP,
                "local_ip":
                    "10.0.0.1",
            }
        },
    )

    monkeypatch.setattr(
        api,
        "find_session_log",
        lambda pid, ppid:
            {
                "session_id":
                    pid,
                "log_file":
                    "/tmp/log",
            },
    )

    result = api.active_sessions()

    assert len(result) == 1

    assert result[0]["pid"] == 123
    assert result[0]["ppid"] == 12
    assert result[0]["user"] == "admin"
    assert result[0]["remote_ip"] == IP
    assert result[0]["streamable"] is True
    assert (
        result[0]["session_id"]
        == "123"
    )


# ============================================================
# Routes lecture
# ============================================================

def test_root(env):
    response = (
        env["client"].get("/")
    )

    assert response.status_code == 200

    assert response.json() == {
        "name": "SSH Guardian",
        "version": "2.0.0",
        "status": "online",
    }


def test_health(
    env,
    monkeypatch,
):
    monkeypatch.setattr(
        api,
        "service_status",
        lambda name:
            "active",
    )

    response = env[
        "client"
    ].get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["redis"] is True

    assert all(
        value == "active"
        for value
        in data["services"].values()
    )


def test_stats(env):
    response = env[
        "client"
    ].get("/stats")

    assert response.json() == {
        "events": 10
    }


def test_events_default(env):
    response = env[
        "client"
    ].get("/events")

    assert response.status_code == 200

    assert (
        env["repo"].calls[-1]
        == ("events", 100, None)
    )


def test_events_custom_limit(env):
    response = env[
        "client"
    ].get(
        "/events?limit=5"
    )

    assert response.status_code == 200

    assert (
        env["repo"].calls[-1]
        == ("events", 5, None)
    )


@pytest.mark.parametrize(
    "limit",
    [
        0,
        1001,
    ],
)
def test_events_invalid_limit(
    env,
    limit,
):
    response = env[
        "client"
    ].get(
        f"/events?limit={limit}"
    )

    assert response.status_code == 422


def test_search_valid_ip(env):
    response = env[
        "client"
    ].get(
        f"/search/{IP}"
    )

    assert response.status_code == 200

    assert response.json()["ip"] == IP

    assert (
        env["repo"].calls[-1]
        == ("events", 100, IP)
    )


def test_search_ipv6(env):
    response = env[
        "client"
    ].get(
        "/search/2001:db8::1"
    )

    assert response.status_code == 200


def test_search_invalid_ip(env):
    response = env[
        "client"
    ].get(
        "/search/not-an-ip"
    )

    assert response.status_code == 400

    assert (
        response.json()["detail"]
        == "Adresse IP invalide"
    )


def test_bans(env):
    response = env[
        "client"
    ].get("/bans")

    assert response.status_code == 200
    assert response.json()[0]["ip"] == IP


def test_active_bans(env):
    response = env[
        "client"
    ].get("/bans/active")

    assert response.status_code == 200

    assert (
        response.json()[0][
            "active"
        ]
        is True
    )


def test_top(env):
    response = env[
        "client"
    ].get("/top?limit=7")

    assert response.status_code == 200

    assert (
        env["repo"].calls[-1]
        == ("top_ips", 7)
    )


def test_topcountries(env):
    response = env[
        "client"
    ].get(
        "/topcountries?limit=9"
    )

    assert response.status_code == 200

    assert (
        env["repo"].calls[-1]
        == (
            "top_countries",
            9,
        )
    )


@pytest.mark.parametrize(
    "path",
    [
        "/top?limit=0",
        "/top?limit=101",
        "/topcountries?limit=0",
        "/topcountries?limit=101",
    ],
)
def test_top_invalid_limits(
    env,
    path,
):
    assert (
        env["client"]
        .get(path)
        .status_code
        == 422
    )


def test_countries_missing_file(env):
    response = env[
        "client"
    ].get("/countries")

    assert response.json() == {
        "blocked_countries": []
    }


def test_countries_normalized_sorted(
    env,
):
    env["blocked"].write_text(
        "il\nRU\n\nfr\nil\n"
    )

    response = env[
        "client"
    ].get("/countries")

    assert response.json() == {
        "blocked_countries":
            ["FR", "IL", "RU"]
    }


def test_sessions_route(
    env,
    monkeypatch,
):
    monkeypatch.setattr(
        api,
        "active_sessions",
        lambda: [
            {
                "pid": 123
            }
        ],
    )

    response = env[
        "client"
    ].get("/sessions")

    assert response.json() == [
        {
            "pid": 123
        }
    ]


# ============================================================
# Actions Control
# ============================================================

def test_unban_valid(env):
    response = env[
        "client"
    ].post(
        f"/unban/{IP}"
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True

    assert (
        env["control"].calls[-1]
        == (
            "unban",
            [IP],
            "api",
        )
    )


def test_unban_invalid_ip(env):
    response = env[
        "client"
    ].post(
        "/unban/bad"
    )

    assert response.status_code == 400


def test_unban_backend_error(env):
    env["control"].error = (
        RuntimeError("control down")
    )

    response = env[
        "client"
    ].post(
        f"/unban/{IP}"
    )

    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "control down"
    )


def test_block_country_panel_source(
    env,
):
    response = env[
        "client"
    ].post(
        "/block-country/il"
        "?source=panel"
    )

    assert response.status_code == 200

    assert (
        env["control"].calls[-1]
        == (
            "block",
            ["il"],
            "panel",
        )
    )


def test_block_country_invalid_source_falls_back(
    env,
):
    env["client"].post(
        "/block-country/il"
        "?source=hacker"
    )

    assert (
        env["control"].calls[-1]
        == (
            "block",
            ["il"],
            "api",
        )
    )


def test_unblock_country(env):
    response = env[
        "client"
    ].post(
        "/unblock-country/il"
        "?source=panel"
    )

    assert response.status_code == 200

    assert (
        env["control"].calls[-1]
        == (
            "unblock",
            ["il"],
            "panel",
        )
    )


def test_country_backend_errors(env):
    env["control"].error = (
        RuntimeError("rpc failed")
    )

    assert (
        env["client"]
        .post(
            "/block-country/il"
        )
        .status_code
        == 503
    )

    assert (
        env["client"]
        .post(
            "/unblock-country/il"
        )
        .status_code
        == 503
    )


def test_kill_session_valid(env):
    response = env[
        "client"
    ].post(
        "/kill-session/123"
    )

    assert response.status_code == 200

    assert (
        env["control"].calls[-1]
        == (
            "killsession",
            ["123"],
            "api",
        )
    )


@pytest.mark.parametrize(
    "pid",
    [
        0,
        1,
        -1,
    ],
)
def test_kill_session_invalid_pid(
    env,
    pid,
):
    response = env[
        "client"
    ].post(
        f"/kill-session/{pid}"
    )

    assert response.status_code == 400


def test_kill_session_backend_error(
    env,
):
    env["control"].error = (
        RuntimeError("kill error")
    )

    response = env[
        "client"
    ].post(
        "/kill-session/123"
    )

    assert response.status_code == 503


def test_kill_all(env):
    response = env[
        "client"
    ].post(
        "/kill-all-sessions"
    )

    assert response.status_code == 200

    assert (
        env["control"].calls[-1][0]
        == "killallsessions"
    )


def test_kill_all_error(env):
    env["control"].error = (
        RuntimeError("boom")
    )

    assert (
        env["client"]
        .post(
            "/kill-all-sessions"
        )
        .status_code
        == 503
    )


def test_stream_start(env):
    response = env[
        "client"
    ].post(
        "/stream/start/123"
        "?lines=25"
    )

    assert response.status_code == 200

    assert (
        env["control"].calls[-1]
        == (
            "stream_start",
            ["123", "25"],
            "api",
        )
    )


@pytest.mark.parametrize(
    "lines",
    [
        4,
        61,
    ],
)
def test_stream_start_invalid_lines(
    env,
    lines,
):
    response = env[
        "client"
    ].post(
        f"/stream/start/123"
        f"?lines={lines}"
    )

    assert response.status_code == 422


def test_stream_get(env):
    response = env[
        "client"
    ].get(
        "/stream/abc"
    )

    assert response.status_code == 200

    assert (
        env["control"].calls[-1]
        == (
            "stream_get",
            ["abc"],
            "api",
        )
    )


def test_stream_stop(env):
    response = env[
        "client"
    ].post(
        "/stream/stop/abc"
    )

    assert response.status_code == 200

    assert (
        env["control"].calls[-1]
        == (
            "stream_stop",
            ["abc"],
            "api",
        )
    )


@pytest.mark.parametrize(
    "method,path",
    [
        (
            "post",
            "/stream/start/123",
        ),
        (
            "get",
            "/stream/abc",
        ),
        (
            "post",
            "/stream/stop/abc",
        ),
    ],
)
def test_stream_backend_errors(
    env,
    method,
    path,
):
    env["control"].error = (
        RuntimeError(
            "stream unavailable"
        )
    )

    response = getattr(
        env["client"],
        method,
    )(path)

    assert response.status_code == 503


# ============================================================
# MFA routes
# ============================================================

@pytest.mark.parametrize(
    "method,path,command",
    [
        (
            "get",
            "/mfa/status",
            "status",
        ),
        (
            "post",
            "/mfa/enable",
            "enable",
        ),
        (
            "post",
            "/mfa/disable",
            "disable",
        ),
    ],
)
def test_mfa_simple_routes(
    env,
    method,
    path,
    command,
):
    response = getattr(
        env["client"],
        method,
    )(path)

    assert response.status_code == 200

    assert (
        env["mfa"].calls[-1][0]
        == command
    )


def test_mfa_backend_error(env):
    env["mfa"].error = (
        RuntimeError("mfa down")
    )

    response = env[
        "client"
    ].get("/mfa/status")

    assert response.status_code == 503
    assert (
        response.json()["detail"]
        == "mfa down"
    )


@pytest.mark.parametrize(
    "seconds",
    [
        10,
        45,
        300,
    ],
)
def test_mfa_timeout_valid(
    env,
    seconds,
):
    response = env[
        "client"
    ].post(
        f"/mfa/timeout/{seconds}"
    )

    assert response.status_code == 200

    assert (
        env["mfa"].calls[-1]
        == (
            "set_timeout",
            {
                "timeout_seconds":
                    seconds,
            },
        )
    )


@pytest.mark.parametrize(
    "seconds",
    [
        9,
        301,
    ],
)
def test_mfa_timeout_invalid(
    env,
    seconds,
):
    response = env[
        "client"
    ].post(
        f"/mfa/timeout/{seconds}"
    )

    assert response.status_code == 400


def test_mfa_allow_ip(env):
    response = env[
        "client"
    ].post(
        f"/mfa/allow-ip/{IP}"
        "?duration=123"
    )

    assert response.status_code == 200

    assert (
        env["mfa"].calls[-1]
        == (
            "allow_ip",
            {
                "ip": IP,
                "duration": 123,
                "source": "api",
            },
        )
    )


def test_mfa_allow_invalid_ip(env):
    response = env[
        "client"
    ].post(
        "/mfa/allow-ip/bad"
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "duration",
    [
        0,
        604801,
    ],
)
def test_mfa_allow_invalid_duration(
    env,
    duration,
):
    response = env[
        "client"
    ].post(
        f"/mfa/allow-ip/{IP}"
        f"?duration={duration}"
    )

    assert response.status_code == 422


def test_mfa_revoke_ip(env):
    response = env[
        "client"
    ].post(
        f"/mfa/revoke-ip/{IP}"
    )

    assert response.status_code == 200

    assert (
        env["mfa"].calls[-1]
        == (
            "revoke_ip",
            {
                "ip": IP,
                "source": "api",
            },
        )
    )


def test_mfa_revoke_invalid_ip(env):
    assert (
        env["client"]
        .post(
            "/mfa/revoke-ip/nope"
        )
        .status_code
        == 400
    )


@pytest.mark.parametrize(
    "status",
    [
        "pending",
        "approved",
        "denied",
        "expired",
        "cancelled",
    ],
)
def test_mfa_requests_valid_status(
    env,
    status,
):
    response = env[
        "client"
    ].get(
        "/mfa/requests"
        f"?status={status}"
        "&limit=12"
    )

    assert response.status_code == 200

    assert (
        env["mfa"].calls[-1]
        == (
            "requests",
            {
                "status": status,
                "limit": 12,
            },
        )
    )


def test_mfa_requests_no_status(env):
    response = env[
        "client"
    ].get(
        "/mfa/requests"
    )

    assert response.status_code == 200

    assert (
        env["mfa"].calls[-1][1]
        == {
            "status": None,
            "limit": 100,
        }
    )


def test_mfa_requests_invalid_status(
    env,
):
    response = env[
        "client"
    ].get(
        "/mfa/requests"
        "?status=wat"
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    "limit",
    [
        0,
        501,
    ],
)
def test_mfa_requests_invalid_limit(
    env,
    limit,
):
    response = env[
        "client"
    ].get(
        f"/mfa/requests"
        f"?limit={limit}"
    )

    assert response.status_code == 422


def test_mfa_get_request(env):
    response = env[
        "client"
    ].get(
        "/mfa/request/req123"
    )

    assert response.status_code == 200

    assert (
        env["mfa"].calls[-1]
        == (
            "get",
            {
                "mfa_request_id":
                    "req123",
            },
        )
    )


def test_mfa_approve(env):
    response = env[
        "client"
    ].post(
        "/mfa/request/req1/"
        "approve?source=panel"
    )

    assert response.status_code == 200

    assert (
        env["mfa"].calls[-1]
        == (
            "approve",
            {
                "mfa_request_id":
                    "req1",
                "source": "panel",
            },
        )
    )


def test_mfa_approve_temporary(env):
    response = env[
        "client"
    ].post(
        "/mfa/request/req1/"
        "approve-temporary"
        "?source=panel"
        "&duration=600"
    )

    assert response.status_code == 200

    assert (
        env["mfa"].calls[-1]
        == (
            "approve_temporary",
            {
                "mfa_request_id":
                    "req1",
                "duration": 600,
                "source": "panel",
            },
        )
    )


@pytest.mark.parametrize(
    "duration",
    [
        0,
        604801,
    ],
)
def test_mfa_approve_temporary_invalid_duration(
    env,
    duration,
):
    response = env[
        "client"
    ].post(
        "/mfa/request/req1/"
        "approve-temporary"
        f"?duration={duration}"
    )

    assert response.status_code == 422


def test_mfa_deny(env):
    response = env[
        "client"
    ].post(
        "/mfa/request/req1/"
        "deny?source=telegram"
    )

    assert response.status_code == 200

    assert (
        env["mfa"].calls[-1]
        == (
            "deny",
            {
                "mfa_request_id":
                    "req1",
                "source":
                    "telegram",
            },
        )
    )
