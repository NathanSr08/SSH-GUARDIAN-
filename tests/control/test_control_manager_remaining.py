from types import SimpleNamespace

import services.control.app.manager as manager_module
from services.control.app.manager import ControlManager


def result(
    stdout="",
    returncode=0,
):
    return SimpleNamespace(
        stdout=stdout,
        stderr="",
        returncode=returncode,
    )


def manager_without_init():
    return object.__new__(
        ControlManager
    )


def test_sessions_empty(
    monkeypatch,
):
    manager = manager_without_init()

    monkeypatch.setattr(
        manager_module.subprocess,
        "run",
        lambda *a, **k:
            result(
                "ESTAB x python\n"
            ),
    )

    assert (
        manager.sessions()
        == "📭 Aucune session SSH active."
    )


def test_sessions_shows_sshd(
    monkeypatch,
):
    manager = manager_without_init()

    monkeypatch.setattr(
        manager_module.subprocess,
        "run",
        lambda *a, **k:
            result(
                "ESTAB one sshd-session\n"
                "ESTAB two sshd-session\n"
            ),
    )

    text = manager.sessions()

    assert "Sessions SSH" in text
    assert "ESTAB one" in text
    assert "ESTAB two" in text


def test_active_no_logs(
    monkeypatch,
):
    manager = manager_without_init()

    monkeypatch.setattr(
        manager_module.glob,
        "glob",
        lambda *a: [],
    )

    assert (
        manager.active()
        == "📭 Aucune session enregistrée."
    )


def test_active_live_and_finished(
    monkeypatch,
):
    manager = manager_without_init()

    files = [
        "/tmp/session_123_a.log",
        "/tmp/session_456_b.log",
        "/tmp/not-valid.log",
    ]

    monkeypatch.setattr(
        manager_module.glob,
        "glob",
        lambda *a:
            list(files),
    )

    monkeypatch.setattr(
        manager_module.os.path,
        "getmtime",
        lambda p: 1,
    )

    def fake_run(args, **kwargs):
        if args[:2] == [
            "kill",
            "-0",
        ]:
            return result(
                returncode=(
                    0
                    if args[2] == "123"
                    else 1
                )
            )

        return result()

    monkeypatch.setattr(
        manager_module.subprocess,
        "run",
        fake_run,
    )

    text = manager.active()

    assert "123" in text
    assert "LIVE" in text

    assert "456" in text
    assert "Terminée" in text


def test_stream_snapshot_invalid():
    manager = manager_without_init()

    result = manager.stream_snapshot(
        "abc"
    )

    assert result["ok"] is False
    assert result["text"] == (
        "Session invalide."
    )


def test_stream_snapshot_missing(
    monkeypatch,
):
    manager = manager_without_init()

    monkeypatch.setattr(
        manager_module.glob,
        "glob",
        lambda *a: [],
    )

    result = manager.stream_snapshot(
        "123"
    )

    assert result["ok"] is False
    assert (
        result["text"]
        == "Session introuvable."
    )


def test_stream_snapshot_file_error(
    monkeypatch,
):
    manager = manager_without_init()

    monkeypatch.setattr(
        manager_module.glob,
        "glob",
        lambda *a:
            ["/missing"],
    )

    result = manager.stream_snapshot(
        "123"
    )

    assert result["ok"] is False
    assert result["text"]


def test_stream_snapshot_success(
    tmp_path,
    monkeypatch,
):
    manager = manager_without_init()

    path = (
        tmp_path
        / "session_123_test.log"
    )

    path.write_text(
        "\x1b[31mred\x1b[0m\n"
        "\x00hello\n"
        "\n"
    )

    monkeypatch.setattr(
        manager_module.glob,
        "glob",
        lambda *a:
            [str(path)],
    )

    monkeypatch.setattr(
        manager_module.subprocess,
        "run",
        lambda *a, **k:
            result(returncode=0),
    )

    data = manager.stream_snapshot(
        "123",
        max_lines=1,
    )

    assert data["ok"] is True
    assert data["alive"] is True
    assert data["session_id"] == "123"
    assert data["content"] == "hello"


def test_killsession_invalid():
    manager = manager_without_init()

    assert (
        manager.killsession(
            "abc"
        )
        == "❌ PID invalide."
    )


def test_killsession_success(
    monkeypatch,
):
    manager = manager_without_init()

    monkeypatch.setattr(
        manager_module.subprocess,
        "run",
        lambda *a, **k:
            result(returncode=0),
    )

    assert "terminée" in (
        manager.killsession(
            "123"
        )
    )


def test_killsession_failure(
    monkeypatch,
):
    manager = manager_without_init()

    monkeypatch.setattr(
        manager_module.subprocess,
        "run",
        lambda *a, **k:
            result(returncode=1),
    )

    assert "Impossible" in (
        manager.killsession(
            "123"
        )
    )


def test_killallsessions(
    monkeypatch,
):
    manager = manager_without_init()

    calls = []

    monkeypatch.setattr(
        manager_module.subprocess,
        "run",
        lambda args, **kwargs:
            calls.append(args)
            or result(),
    )

    text = (
        manager.killallsessions()
    )

    assert "Toutes les sessions" in text

    assert calls[0] == [
        "pkill",
        "-9",
        "-f",
        "sshd-session",
    ]


def test_sessions_data_filters_and_dedupes(
    monkeypatch,
):
    manager = manager_without_init()

    ss_output = (
        "ESTAB 0 0 "
        "10.0.0.1:22 "
        "203.0.113.1:5555 "
        'users:(("sshd-session",pid=123,fd=1))\n'
        "LISTEN ignored sshd-session\n"
        "ESTAB too short\n"
    )

    def fake_run(args, **kwargs):
        if args[0] == "ss":
            return result(ss_output)

        if args[0] == "ps":
            return result(
                "admin sshd-session: "
                "admin@pts/0"
            )

        return result()

    monkeypatch.setattr(
        manager_module.subprocess,
        "run",
        fake_run,
    )

    monkeypatch.setattr(
        manager_module.glob,
        "glob",
        lambda *a:
            ["/tmp/session_123.log"],
    )

    data = manager.sessions_data()

    assert len(data) == 1

    assert data[0]["pid"] == "123"
    assert data[0]["username"] == "admin"
    assert data[0]["streamable"] is True
    assert (
        data[0]["remote"]
        == "203.0.113.1:5555"
    )


def test_sessions_data_skips_unknown_process(
    monkeypatch,
):
    manager = manager_without_init()

    ss_output = (
        "ESTAB 0 0 "
        "10.0.0.1:22 "
        "203.0.113.1:5555 "
        'users:(("sshd-session",pid=123,fd=1))'
    )

    def fake_run(args, **kwargs):
        if args[0] == "ss":
            return result(ss_output)

        return result("")

    monkeypatch.setattr(
        manager_module.subprocess,
        "run",
        fake_run,
    )

    assert (
        manager.sessions_data()
        == []
    )


def test_active_data_filters_streamable(
    monkeypatch,
):
    manager = manager_without_init()

    monkeypatch.setattr(
        manager,
        "sessions_data",
        lambda: [
            {
                "pid": "1",
                "streamable": True,
            },
            {
                "pid": "2",
                "streamable": False,
            },
        ],
    )

    assert manager.active_data() == [
        {
            "pid": "1",
            "streamable": True,
        }
    ]
