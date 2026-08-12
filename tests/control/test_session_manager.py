from pathlib import Path
from types import SimpleNamespace

import services.control.app.session_manager as session_module
from services.control.app.session_manager import SessionManager


def result(
    stdout="",
    returncode=0,
):
    return SimpleNamespace(
        stdout=stdout,
        stderr="",
        returncode=returncode,
    )


def test_active_sessions_parses_processes(
    monkeypatch,
):
    monkeypatch.setattr(
        session_module.subprocess,
        "run",
        lambda *a, **k:
            result(
                "123 1 root sshd-session: admin@pts/0\n"
                "999 1 root python app.py\n"
            ),
    )

    sessions = (
        SessionManager()
        ._active_sessions()
    )

    assert sessions == [
        {
            "pid": "123",
            "ppid": "1",
            "user": "admin",
            "tty": "pts/0",
        }
    ]


def test_network_sessions_parses_mapping(
    monkeypatch,
):
    text = (
        'ESTAB 0 0 10.0.0.1:22 '
        '203.0.113.70:55555 '
        'users:(("sshd-session",pid=123,fd=4))'
    )

    monkeypatch.setattr(
        session_module.subprocess,
        "run",
        lambda *a, **k:
            result(text),
    )

    data = (
        SessionManager()
        ._network_sessions()
    )

    assert data["123"]["remote_ip"] == (
        "203.0.113.70"
    )


def test_log_for_pid_none(
    monkeypatch,
):
    monkeypatch.setattr(
        session_module.glob,
        "glob",
        lambda pattern: [],
    )

    assert (
        SessionManager()
        ._log_for_pid("123")
        is None
    )


def test_log_for_pid_newest(
    monkeypatch,
):
    monkeypatch.setattr(
        session_module.glob,
        "glob",
        lambda pattern:
            ["/a", "/b"],
    )

    monkeypatch.setattr(
        session_module.os.path,
        "getmtime",
        lambda path:
            2 if path == "/b" else 1,
    )

    assert (
        SessionManager()
        ._log_for_pid("123")
        == "/b"
    )


def test_active_empty(monkeypatch):
    manager = SessionManager()

    monkeypatch.setattr(
        manager,
        "_active_sessions",
        lambda: [],
    )

    monkeypatch.setattr(
        manager,
        "_network_sessions",
        lambda: {},
    )

    assert (
        manager.active()
        == "📭 Aucune session SSH active."
    )


def test_active_streamable_session(
    monkeypatch,
):
    manager = SessionManager()

    monkeypatch.setattr(
        manager,
        "_active_sessions",
        lambda: [
            {
                "pid": "123",
                "ppid": "1",
                "user": "<admin>",
                "tty": "pts/0",
            }
        ],
    )

    monkeypatch.setattr(
        manager,
        "_network_sessions",
        lambda: {
            "123": {
                "remote_ip":
                    "203.0.113.70",
            }
        },
    )

    monkeypatch.setattr(
        manager,
        "_log_for_pid",
        lambda pid:
            "/tmp/session.log",
    )

    text = manager.active()

    assert "LIVE / streamable" in text
    assert "203.0.113.70" in text
    assert "&lt;admin&gt;" in text
    assert "/stream 123" in text


def test_active_non_streamable(
    monkeypatch,
):
    manager = SessionManager()

    monkeypatch.setattr(
        manager,
        "_active_sessions",
        lambda: [
            {
                "pid": "123",
                "ppid": "1",
                "user": "admin",
                "tty": "pts/0",
            }
        ],
    )

    monkeypatch.setattr(
        manager,
        "_network_sessions",
        lambda: {},
    )

    monkeypatch.setattr(
        manager,
        "_log_for_pid",
        lambda pid: None,
    )

    text = manager.active()

    assert "non enregistrée" in text
    assert "Inconnue" in text


def test_sessions_aliases_active(
    monkeypatch,
):
    manager = SessionManager()

    monkeypatch.setattr(
        manager,
        "active",
        lambda: "OK",
    )

    assert manager.sessions() == "OK"


def test_stream_invalid_pid():
    result = (
        SessionManager()
        .stream_snapshot("abc")
    )

    assert result["ok"] is False
    assert "PID invalide" in result["text"]


def test_stream_without_log(
    monkeypatch,
):
    manager = SessionManager()

    monkeypatch.setattr(
        manager,
        "_active_sessions",
        lambda: [],
    )

    monkeypatch.setattr(
        manager,
        "_log_for_pid",
        lambda pid: None,
    )

    result = manager.stream_snapshot(
        "123"
    )

    assert result["ok"] is False
    assert "pas de flux" in result["text"]


def test_stream_cleans_terminal(
    tmp_path,
    monkeypatch,
):
    log = tmp_path / "session.log"

    log.write_text(
        "\x1b[31mred\x1b[0m\n"
        "old\rnew\n"
        "\x00hello\n"
    )

    manager = SessionManager()

    monkeypatch.setattr(
        manager,
        "_active_sessions",
        lambda: [
            {
                "pid": "123",
            }
        ],
    )

    monkeypatch.setattr(
        manager,
        "_log_for_pid",
        lambda pid: str(log),
    )

    result = manager.stream_snapshot(
        "123",
        max_lines=10,
    )

    assert result["ok"] is True
    assert result["alive"] is True
    assert "\x1b" not in result["content"]
    assert "\x00" not in result["content"]
    assert "new" in result["content"]
    assert "old" not in result["content"]


def test_stream_max_lines_is_capped(
    tmp_path,
    monkeypatch,
):
    log = tmp_path / "session.log"

    log.write_text(
        "\n".join(
            f"line-{i}"
            for i in range(150)
        )
    )

    manager = SessionManager()

    monkeypatch.setattr(
        manager,
        "_active_sessions",
        lambda: [],
    )

    monkeypatch.setattr(
        manager,
        "_log_for_pid",
        lambda pid: str(log),
    )

    data = manager.stream_snapshot(
        "123",
        1000,
    )

    assert (
        len(
            data["content"].splitlines()
        )
        == 100
    )


def test_kill_invalid_pid():
    assert (
        SessionManager().kill("bad")
        == "❌ PID invalide."
    )


def test_kill_unknown_pid(
    monkeypatch,
):
    manager = SessionManager()

    monkeypatch.setattr(
        manager,
        "_active_sessions",
        lambda: [],
    )

    assert "introuvable" in (
        manager.kill("123")
    )


def test_kill_success(
    monkeypatch,
):
    manager = SessionManager()

    monkeypatch.setattr(
        manager,
        "_active_sessions",
        lambda: [
            {
                "pid": "123",
            }
        ],
    )

    monkeypatch.setattr(
        session_module.subprocess,
        "run",
        lambda *a, **k:
            result(returncode=0),
    )

    assert "terminée" in (
        manager.kill("123")
    )


def test_kill_failure(
    monkeypatch,
):
    manager = SessionManager()

    monkeypatch.setattr(
        manager,
        "_active_sessions",
        lambda: [
            {
                "pid": "123",
            }
        ],
    )

    monkeypatch.setattr(
        session_module.subprocess,
        "run",
        lambda *a, **k:
            result(returncode=1),
    )

    assert "Impossible" in (
        manager.kill("123")
    )


def test_kill_all_counts_successes(
    monkeypatch,
):
    manager = SessionManager()

    monkeypatch.setattr(
        manager,
        "_active_sessions",
        lambda: [
            {"pid": "1"},
            {"pid": "2"},
            {"pid": "3"},
        ],
    )

    responses = iter([
        result(returncode=0),
        result(returncode=1),
        result(returncode=0),
    ])

    monkeypatch.setattr(
        session_module.subprocess,
        "run",
        lambda *a, **k:
            next(responses),
    )

    assert (
        manager.kill_all()
        == "⚡ 2 session(s) SSH terminée(s)."
    )
