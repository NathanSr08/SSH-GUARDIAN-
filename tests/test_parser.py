from services.collector.app.parser import parse_ssh_line


def test_failed_password():
    event = parse_ssh_line(
        "Failed password for root from 1.2.3.4 port 54321 ssh2"
    )

    assert event is not None
    assert event.event_type == "ssh.login.failed"
    assert event.ip == "1.2.3.4"
    assert event.username == "root"


def test_invalid_user():
    event = parse_ssh_line(
        "Invalid user natha from 82.80.219.126 port 54032"
    )

    assert event is not None
    assert event.event_type == "ssh.login.invalid_user"
    assert event.ip == "82.80.219.126"
    assert event.username == "natha"


def test_connection_reset():
    event = parse_ssh_line(
        "Connection reset by authenticating user admin 82.80.219.126 port 54034 [preauth]"
    )

    assert event is not None
    assert event.event_type == "ssh.connection.reset"
    assert event.ip == "82.80.219.126"
    assert event.username == "admin"


def test_connection_closed():
    event = parse_ssh_line(
        "Connection closed by 190.61.110.243 port 52940"
    )

    assert event is not None
    assert event.event_type == "ssh.connection.closed"
    assert event.ip == "190.61.110.243"
    assert event.username is None


def test_unknown_line_is_ignored():
    event = parse_ssh_line(
        "systemd[1]: Started Some Service."
    )

    assert event is None


def test_failed_publickey():
    event = parse_ssh_line(
        "Failed publickey for admin from 1.2.3.4 port 55555 ssh2"
    )

    assert event is not None
    assert event.event_type == "ssh.login.failed"
    assert event.ip == "1.2.3.4"
    assert event.username == "admin"


def test_connection_opened():
    event = parse_ssh_line(
        'Connection from 95.174.64.122 port 51822 '
        'on 172.31.5.56 port 22 rdomain ""'
    )

    assert event is not None
    assert event.event_type == "ssh.connection.opened"
    assert event.ip == "95.174.64.122"
    assert event.username is None
