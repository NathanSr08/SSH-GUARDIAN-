import importlib
from pathlib import Path

import pytest
from fastapi import HTTPException


panel = importlib.import_module("services.panel.app.main")


class FakeResponse:
    def __init__(
        self,
        status_code=200,
        data=None,
        text="",
        json_error=False,
    ):
        self.status_code = status_code
        self.data = data
        self.text = text
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise ValueError("invalid json")
        return self.data


def test_auth_no_token(monkeypatch):
    monkeypatch.setattr(
        panel.Settings,
        "PANEL_TOKEN",
        "",
    )

    with pytest.raises(HTTPException) as exc:
        panel.auth(None)

    assert exc.value.status_code == 503


def test_auth_invalid_token(monkeypatch):
    monkeypatch.setattr(
        panel.Settings,
        "PANEL_TOKEN",
        "secret",
    )

    with pytest.raises(HTTPException) as exc:
        panel.auth("Bearer wrong")

    assert exc.value.status_code == 401


def test_auth_valid(monkeypatch):
    monkeypatch.setattr(
        panel.Settings,
        "PANEL_TOKEN",
        "secret",
    )

    assert panel.auth("Bearer secret") is None


def test_api_url(monkeypatch):
    monkeypatch.setattr(
        panel.Settings,
        "PANEL_API_URL",
        "http://api:8000/",
    )

    assert (
        panel.api_url("/health")
        == "http://api:8000/health"
    )


def test_request_api_success(monkeypatch):
    calls = []

    def fake_request(method, url, timeout):
        calls.append((method, url, timeout))
        return FakeResponse(
            200,
            {"ok": True},
        )

    monkeypatch.setattr(
        panel.requests,
        "request",
        fake_request,
    )

    monkeypatch.setattr(
        panel.Settings,
        "PANEL_API_URL",
        "http://api:8000",
    )

    result = panel.request_api(
        "GET",
        "/health",
    )

    assert result == {"ok": True}
    assert calls == [
        (
            "GET",
            "http://api:8000/health",
            20,
        )
    ]


def test_request_api_non_json(monkeypatch):
    monkeypatch.setattr(
        panel.requests,
        "request",
        lambda *a, **kw: FakeResponse(
            200,
            text="hello",
            json_error=True,
        ),
    )

    result = panel.request_api(
        "GET",
        "/x",
    )

    assert result == {
        "detail": "hello",
    }


def test_request_api_http_error_json(monkeypatch):
    monkeypatch.setattr(
        panel.requests,
        "request",
        lambda *a, **kw: FakeResponse(
            418,
            {"error": "teapot"},
        ),
    )

    with pytest.raises(HTTPException) as exc:
        panel.request_api(
            "POST",
            "/x",
        )

    assert exc.value.status_code == 418
    assert exc.value.detail == {
        "error": "teapot",
    }


def test_request_api_http_error_text(monkeypatch):
    monkeypatch.setattr(
        panel.requests,
        "request",
        lambda *a, **kw: FakeResponse(
            500,
            text="boom",
            json_error=True,
        ),
    )

    with pytest.raises(HTTPException) as exc:
        panel.request_api(
            "GET",
            "/x",
        )

    assert exc.value.status_code == 500
    assert exc.value.detail == {
        "detail": "boom",
    }


def test_index():
    response = panel.index()

    assert Path(response.path).name == "index.html"


@pytest.mark.parametrize(
    "func,args,expected_method,expected_path",
    [
        (
            panel.health,
            (),
            "GET",
            "/health",
        ),
        (
            panel.stats,
            (),
            "GET",
            "/stats",
        ),
        (
            panel.events,
            (),
            "GET",
            "/events?limit=100",
        ),
        (
            panel.search,
            ("1.2.3.4",),
            "GET",
            "/search/1.2.3.4",
        ),
        (
            panel.bans,
            (),
            "GET",
            "/bans/active",
        ),
        (
            panel.countries,
            (),
            "GET",
            "/countries",
        ),
        (
            panel.top,
            (),
            "GET",
            "/top",
        ),
        (
            panel.topcountries,
            (),
            "GET",
            "/topcountries",
        ),
        (
            panel.sessions,
            (),
            "GET",
            "/sessions",
        ),
        (
            panel.unban,
            ("1.2.3.4",),
            "POST",
            "/unban/1.2.3.4",
        ),
        (
            panel.block_country,
            ("FR",),
            "POST",
            "/block-country/FR?source=panel",
        ),
        (
            panel.unblock_country,
            ("FR",),
            "POST",
            "/unblock-country/FR?source=panel",
        ),
        (
            panel.kill_session,
            (123,),
            "POST",
            "/kill-session/123",
        ),
        (
            panel.kill_all_sessions,
            (),
            "POST",
            "/kill-all-sessions",
        ),
        (
            panel.stream_start,
            ("abc", 20),
            "POST",
            "/stream/start/abc?lines=20",
        ),
        (
            panel.stream_get,
            ("stream1",),
            "GET",
            "/stream/stream1",
        ),
        (
            panel.stream_stop,
            ("stream1",),
            "POST",
            "/stream/stop/stream1",
        ),
        (
            panel.mfa_status,
            (),
            "GET",
            "/mfa/status",
        ),
        (
            panel.mfa_requests,
            ("pending",),
            "GET",
            "/mfa/requests?status=pending",
        ),
        (
            panel.mfa_enable,
            (),
            "POST",
            "/mfa/enable",
        ),
        (
            panel.mfa_disable,
            (),
            "POST",
            "/mfa/disable",
        ),
        (
            panel.mfa_timeout,
            (60,),
            "POST",
            "/mfa/timeout/60",
        ),
        (
            panel.mfa_allow_ip,
            ("1.2.3.4", 3600),
            "POST",
            "/mfa/allow-ip/1.2.3.4?duration=3600",
        ),
        (
            panel.mfa_revoke_ip,
            ("1.2.3.4",),
            "POST",
            "/mfa/revoke-ip/1.2.3.4",
        ),
        (
            panel.mfa_approve,
            ("req1",),
            "POST",
            "/mfa/request/req1/approve?source=panel",
        ),
        (
            panel.mfa_approve_temporary,
            ("req1", 7200),
            "POST",
            (
                "/mfa/request/req1/"
                "approve-temporary"
                "?source=panel&duration=7200"
            ),
        ),
        (
            panel.mfa_deny,
            ("req1",),
            "POST",
            "/mfa/request/req1/deny?source=panel",
        ),
    ],
)
def test_proxy_functions(
    monkeypatch,
    func,
    args,
    expected_method,
    expected_path,
):
    calls = []

    def fake_request(method, path):
        calls.append((method, path))
        return {"ok": True}

    monkeypatch.setattr(
        panel,
        "request_api",
        fake_request,
    )

    result = func(*args)

    assert result == {"ok": True}
    assert calls == [
        (
            expected_method,
            expected_path,
        )
    ]
