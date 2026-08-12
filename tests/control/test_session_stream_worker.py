import json
from types import SimpleNamespace

import services.control.app.session_stream as stream_module
from services.control.app.session_stream import (
    SessionStreamManager,
)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.setex_calls = []

    def setex(
        self,
        key,
        ttl,
        value,
    ):
        self.values[key] = value
        self.setex_calls.append(
            (
                key,
                ttl,
                value,
            )
        )

    def get(self, key):
        return self.values.get(key)


class FakeStdout:
    def __init__(self, lines):
        self.lines = list(lines)

    def readline(self):
        if not self.lines:
            return ""

        return self.lines.pop(0)


class FakeProcess:
    def __init__(
        self,
        lines=None,
        poll_result=0,
        terminate_error=False,
    ):
        self.stdout = FakeStdout(
            lines or []
        )

        self.poll_result = poll_result
        self.terminate_error = (
            terminate_error
        )

        self.terminated = False
        self.killed = False
        self.waited = False

    def poll(self):
        return self.poll_result

    def terminate(self):
        self.terminated = True

        if self.terminate_error:
            raise RuntimeError(
                "terminate failed"
            )

    def wait(self, timeout=None):
        self.waited = True

    def kill(self):
        self.killed = True


class FakeEvent:
    def __init__(self):
        self.stopped = False

    def is_set(self):
        return self.stopped


def test_worker_publishes_initial_state(
    monkeypatch,
):
    redis = FakeRedis()

    manager = (
        SessionStreamManager(
            redis
        )
    )

    process = FakeProcess(
        lines=[],
        poll_result=0,
    )

    monkeypatch.setattr(
        stream_module.subprocess,
        "Popen",
        lambda *a, **k:
            process,
    )

    monkeypatch.setattr(
        stream_module.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                returncode=0
            ),
    )

    manager.streams["abc"] = {
        "stop": FakeEvent(),
        "session_id": "123",
    }

    manager._worker(
        "abc",
        "123",
        "/tmp/fake.log",
        "sshguardian:stream:abc",
        10,
        FakeEvent(),
    )

    assert (
        "sshguardian:stream:abc"
        in redis.values
    )

    payload = json.loads(
        redis.values[
            "sshguardian:stream:abc"
        ]
    )

    assert payload["session_id"] == "123"
    assert payload["alive"] is True
    assert "content" in payload
    assert (
        payload["stream_stopped"]
        is True
    )

    assert "abc" not in (
        manager.streams
    )


def test_worker_reads_and_cleans_lines(
    monkeypatch,
):
    redis = FakeRedis()

    manager = (
        SessionStreamManager(
            redis
        )
    )

    process = FakeProcess(
        lines=[
            "\x1b[31mhello\x1b[0m\n",
        ],
        poll_result=0,
    )

    calls = {
        "kill": 0
    }

    def fake_run(*a, **k):
        calls["kill"] += 1

        return SimpleNamespace(
            returncode=(
                0
                if calls["kill"] == 1
                else 1
            )
        )

    monkeypatch.setattr(
        stream_module.subprocess,
        "Popen",
        lambda *a, **k:
            process,
    )

    monkeypatch.setattr(
        stream_module.subprocess,
        "run",
        fake_run,
    )

    manager._worker(
        "abc",
        "123",
        "/tmp/log",
        "sshguardian:stream:abc",
        10,
        FakeEvent(),
    )

    payload = json.loads(
        redis.values[
            "sshguardian:stream:abc"
        ]
    )

    assert "\x1b" not in (
        payload["content"]
    )

    assert "hello" in (
        payload["content"]
    )


def test_worker_falls_back_to_kill_when_terminate_fails(
    monkeypatch,
):
    redis = FakeRedis()

    manager = (
        SessionStreamManager(
            redis
        )
    )

    process = FakeProcess(
        terminate_error=True,
    )

    monkeypatch.setattr(
        stream_module.subprocess,
        "Popen",
        lambda *a, **k:
            process,
    )

    monkeypatch.setattr(
        stream_module.subprocess,
        "run",
        lambda *a, **k:
            SimpleNamespace(
                returncode=1
            ),
    )

    manager._worker(
        "abc",
        "123",
        "/tmp/log",
        "sshguardian:stream:abc",
        10,
        FakeEvent(),
    )

    assert process.killed is True


def test_stop_process_terminate_exception_is_ignored():
    redis = FakeRedis()

    manager = (
        SessionStreamManager(
            redis
        )
    )

    class Event:
        def __init__(self):
            self.called = False

        def set(self):
            self.called = True

    class Process:
        def terminate(self):
            raise RuntimeError(
                "boom"
            )

    event = Event()

    manager.streams["abc"] = {
        "stop": event,
        "process": Process(),
    }

    result = manager.stop("abc")

    assert result["ok"] is True
    assert result["stopped"] is True
    assert event.called is True
