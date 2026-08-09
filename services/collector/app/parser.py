import re
from datetime import datetime, timezone

from shared.events.ssh import SSHEvent


FAILED_PASSWORD_RE = re.compile(
    r"Failed password for (?:invalid user )?(\S+) from (\S+)"
)

FAILED_PUBLICKEY_RE = re.compile(
    r"Failed publickey for (?:invalid user )?(\S+) from (\S+)"
)

ACCEPTED_PASSWORD_RE = re.compile(
    r"Accepted password for (\S+) from (\S+)"
)

ACCEPTED_PUBLICKEY_RE = re.compile(
    r"Accepted publickey for (\S+) from (\S+)"
)

INVALID_USER_RE = re.compile(
    r"Invalid user (\S+) from (\S+)"
)

CONNECTION_OPENED_RE = re.compile(
    r"Connection from "
    r"((?:\d{1,3}\.){3}\d{1,3}|[0-9a-fA-F:]+) "
    r"port (\d+)"
)

CONNECTION_RESET_INVALID_USER_RE = re.compile(
    r"Connection reset by invalid user (\S+) (\S+)"
)

CONNECTION_RESET_AUTH_USER_RE = re.compile(
    r"Connection reset by authenticating user (\S+) (\S+)"
)

CONNECTION_CLOSED_RE = re.compile(
    r"Connection closed by "
    r"((?:\d{1,3}\.){3}\d{1,3}|[0-9a-fA-F:]+)"
)


def build_event(
    event_type: str,
    ip: str,
    username: str | None,
    line: str,
) -> SSHEvent:
    return SSHEvent(
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        ip=ip,
        username=username,
        message=line.strip(),
    )


def parse_ssh_line(line: str) -> SSHEvent | None:

    #
    # IMPORTANT :
    # cette ligne apparaît AVANT l'authentification.
    #
    match = CONNECTION_OPENED_RE.search(line)

    if match:
        ip, _port = match.groups()

        return build_event(
            "ssh.connection.opened",
            ip,
            None,
            line,
        )

    match = FAILED_PASSWORD_RE.search(line)

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.login.failed",
            ip,
            username,
            line,
        )

    match = FAILED_PUBLICKEY_RE.search(line)

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.login.failed",
            ip,
            username,
            line,
        )

    match = ACCEPTED_PASSWORD_RE.search(line)

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.login.success",
            ip,
            username,
            line,
        )

    match = ACCEPTED_PUBLICKEY_RE.search(line)

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.login.success",
            ip,
            username,
            line,
        )

    match = INVALID_USER_RE.search(line)

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.login.invalid_user",
            ip,
            username,
            line,
        )

    match = CONNECTION_RESET_INVALID_USER_RE.search(line)

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.connection.reset",
            ip,
            username,
            line,
        )

    match = CONNECTION_RESET_AUTH_USER_RE.search(line)

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.connection.reset",
            ip,
            username,
            line,
        )

    match = CONNECTION_CLOSED_RE.search(line)

    if match:
        ip = match.group(1)

        return build_event(
            "ssh.connection.closed",
            ip,
            None,
            line,
        )

    return None
