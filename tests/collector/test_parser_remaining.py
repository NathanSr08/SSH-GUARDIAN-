import pytest

from services.collector.app.parser import (
    build_event,
    parse_ssh_line,
    valid_ip,
)


@pytest.mark.parametrize(
    "value",
    [
        "1.2.3.4",
        "2001:db8::1234",
    ],
)
def test_valid_ip_true(value):
    assert valid_ip(value) is True


@pytest.mark.parametrize(
    "value",
    [
        "bad",
        "999.999.1.1",
        "",
    ],
)
def test_valid_ip_false(value):
    assert valid_ip(value) is False


def test_build_event_invalid_ip():
    assert (
        build_event(
            "ssh.test",
            "not-ip",
            "admin",
            "line",
        )
        is None
    )


@pytest.mark.parametrize(
    "line,event_type,user,ip",
    [
        (
            "sshd[1]: Failed password for root "
            "from 1.2.3.4 port 2222 ssh2",
            "ssh.login.failed",
            "root",
            "1.2.3.4",
        ),
        (
            "sshd[1]: Failed password for invalid user bad "
            "from 1.2.3.4 port 2222 ssh2",
            "ssh.login.failed",
            "bad",
            "1.2.3.4",
        ),
        (
            "sshd[1]: Failed publickey for root "
            "from 1.2.3.4 port 2222 ssh2",
            "ssh.login.failed",
            "root",
            "1.2.3.4",
        ),
        (
            "sshd[1]: Failed publickey for invalid user bad "
            "from 1.2.3.4 port 2222 ssh2",
            "ssh.login.failed",
            "bad",
            "1.2.3.4",
        ),
        (
            "sshd[1]: Failed keyboard-interactive/pam for root "
            "from 1.2.3.4 port 2222 ssh2",
            "ssh.login.failed",
            "root",
            "1.2.3.4",
        ),
        (
            "sshd[1]: Accepted password for root "
            "from 1.2.3.4 port 2222 ssh2",
            "ssh.login.success",
            "root",
            "1.2.3.4",
        ),
        (
            "sshd[1]: Accepted publickey for root "
            "from 1.2.3.4 port 2222 ssh2",
            "ssh.login.success",
            "root",
            "1.2.3.4",
        ),
        (
            "sshd[1]: Accepted keyboard-interactive/pam "
            "for root from 1.2.3.4 port 2222 ssh2",
            "ssh.login.success",
            "root",
            "1.2.3.4",
        ),
        (
            "sshd[1]: Invalid user test from "
            "1.2.3.4 port 2222",
            "ssh.login.invalid_user",
            "test",
            "1.2.3.4",
        ),
        (
            "sshd[1]: Connection reset by invalid user "
            "test 1.2.3.4 port 2222 [preauth]",
            "ssh.connection.reset",
            "test",
            "1.2.3.4",
        ),
        (
            "sshd[1]: Connection reset by authenticating user "
            "root 1.2.3.4 port 2222 [preauth]",
            "ssh.connection.reset",
            "root",
            "1.2.3.4",
        ),
        (
            "sshd[1]: Connection closed by authenticating user "
            "root 1.2.3.4 port 2222 [preauth]",
            "ssh.connection.closed",
            "root",
            "1.2.3.4",
        ),
    ],
)
def test_parser_all_user_patterns(
    line,
    event_type,
    user,
    ip,
):
    result = parse_ssh_line(
        line
    )

    assert result is not None
    assert (
        result.event_type
        == event_type
    )
    assert result.username == user
    assert result.ip == ip


def test_connection_opened():
    event = parse_ssh_line(
        "Connection from "
        "1.2.3.4 port 45678 "
        "on 10.0.0.1 port 22"
    )

    assert event is not None
    assert (
        event.event_type
        == "ssh.connection.opened"
    )
    assert event.ip == "1.2.3.4"
    assert event.username is None


def test_connection_closed_without_username():
    event = parse_ssh_line(
        "Connection closed by "
        "1.2.3.4 port 45678"
    )

    assert event is not None
    assert (
        event.event_type
        == "ssh.connection.closed"
    )
    assert event.ip == "1.2.3.4"
    assert event.username is None


@pytest.mark.parametrize(
    "line",
    [
        "random unrelated ssh log",
        "",
        "Failed password for root "
        "from NOT_AN_IP port 22",
        "Connection from invalid-ip port 22",
        "Connection closed by invalid-ip port 22",
    ],
)
def test_parser_ignores_invalid_or_unknown_lines(
    line,
):
    assert (
        parse_ssh_line(line)
        is None
    )
