import json
from types import SimpleNamespace

import services.control.app.session_stream as stream_module
from services.control.app.session_stream import (
    SessionStreamManager,
    clean_terminal_text,
)


class FakeRedis:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def setex(
        self,
        key,
        ttl,
        value,
    ):
        self.values[key] = value
        return True


class FakeEvent:
    def __init__(self):
        self.value = False

    def set(self):
        self.value = True

    def is_set(self):
        return self.value


class FakeThread:
    def __init__(
        self,
        target=None,
        args=None,
        daemon=None,
    ):
        self.target = target
        self.args = args
        self.daemon = daemon
        self.started = False

    def start(self):
        self.started = True


def test_clean_empty():
    assert clean_terminal_text("") == ""


def test_clean_terminal_ansi():
    raw = (
        "Script started on x\n"
        "\x1b[31mhello\x1b[0m\n"
        "Script done on x\n"
    )

    assert (
        clean_terminal_text(raw)
        == "hello"
    )


def test_clean_terminal_carriage_return():
    assert (
        clean_terminal_text(
            "old\rnew"
        )
        == "new"
    )


def test_clean_terminal_backspaces():
    assert (
        clean_terminal_text(
            "abc\b\bX"
        )
        == "aX"
    )


def test_clean_terminal_deduplicates_lines():
    assert (
        clean_terminal_text(
            "hello\nhello\nworld"
        )
        == "hello\nworld"
    )


def test_find_log_none(
    monkeypatch,
):
    manager = SessionStreamManager(
        FakeRedis()
    )

    monkeypatch.setattr(
        stream_module.glob,
        "glob",
        lambda pattern: [],
    )

    assert manager.find_log("1") is None


def test_find_log_newest(
    monkeypatch,
):
    manager = SessionStreamManager(
        FakeRedis()
    )

    monkeypatch.setattr(
        stream_module.glob,
        "glob",
        lambda pattern:
            ["/old", "/new"],
    )

    monkeypatch.setattr(
        stream_module.os.path,
        "getmtime",
        lambda path:
            2 if path == "/new" else 1,
    )

    assert (
        manager.find_log("1")
        == "/new"
    )


def test_start_invalid_pid():
    manager = SessionStreamManager(
        FakeRedis()
    )

    result = manager.start("bad")

    assert result == {
        "ok": False,
        "error": "PID invalide",
    }


def test_start_missing_log(
    monkeypatch,
):
    manager = SessionStreamManager(
        FakeRedis()
    )

    monkeypatch.setattr(
        manager,
        "find_log",
        lambda sid: None,
    )

    result = manager.start("123")

    assert result["ok"] is False
    assert "Aucun fichier" in (
        result["error"]
    )


def test_start_creates_stream_without_running_worker(
    monkeypatch,
):
    redis = FakeRedis()

    manager = SessionStreamManager(
        redis
    )

    monkeypatch.setattr(
        manager,
        "find_log",
        lambda sid:
            "/tmp/session.log",
    )

    monkeypatch.setattr(
        stream_module.threading,
        "Event",
        FakeEvent,
    )

    monkeypatch.setattr(
        stream_module.threading,
        "Thread",
        FakeThread,
    )

    monkeypatch.setattr(
        stream_module.uuid,
        "uuid4",
        lambda:
            SimpleNamespace(
                hex="stream123"
            ),
    )

    result = manager.start(
        "123",
        max_lines=999,
    )

    assert result == {
        "ok": True,
        "stream_id": "stream123",
        "session_id": "123",
    }

    assert "stream123" in (
        manager.streams
    )


def test_get_missing_stream():
    manager = SessionStreamManager(
        FakeRedis()
    )

    result = manager.get("xxx")

    assert result["ok"] is False


def test_get_existing_stream():
    redis = FakeRedis()

    redis.values[
        "sshguardian:stream:abc"
    ] = json.dumps(
        {
            "session_id": "123",
            "alive": True,
            "content": "hello",
        }
    )

    result = (
        SessionStreamManager(redis)
        .get("abc")
    )

    assert result["ok"] is True
    assert result["content"] == "hello"


def test_stop_unknown_stream():
    manager = SessionStreamManager(
        FakeRedis()
    )

    assert (
        manager.stop("missing")
        == {
            "ok": True,
            "already_stopped": True,
        }
    )


def test_stop_sets_event():
    manager = SessionStreamManager(
        FakeRedis()
    )

    event = FakeEvent()

    manager.streams["abc"] = {
        "stop": event,
        "session_id": "123",
    }

    result = manager.stop("abc")

    assert result == {
        "ok": True,
        "stopped": True,
    }

    assert event.value is True


def test_stop_terminates_process():
    manager = SessionStreamManager(
        FakeRedis()
    )

    event = FakeEvent()

    process = SimpleNamespace(
        terminated=False
    )

    def terminate():
        process.terminated = True

    process.terminate = terminate

    manager.streams["abc"] = {
        "stop": event,
        "session_id": "123",
        "process": process,
    }

    manager.stop("abc")

    assert process.terminated is True
