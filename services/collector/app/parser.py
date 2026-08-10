import ipaddress
import re
from datetime import datetime, timezone

from shared.events.ssh import SSHEvent


#
# Une adresse est d'abord extraite par les regex,
# puis systématiquement validée avec ipaddress.
#
IP_PATTERN = r"(\S+)"


FAILED_PASSWORD_RE = re.compile(
    r"Failed password for "
    r"(?:invalid user )?"
    r"(\S+) from "
    + IP_PATTERN
)

FAILED_PUBLICKEY_RE = re.compile(
    r"Failed publickey for "
    r"(?:invalid user )?"
    r"(\S+) from "
    + IP_PATTERN
)

FAILED_KEYBOARD_INTERACTIVE_RE = re.compile(
    r"Failed keyboard-interactive(?:/pam)? for "
    r"(\S+) from "
    + IP_PATTERN
)

ACCEPTED_PASSWORD_RE = re.compile(
    r"Accepted password for "
    r"(\S+) from "
    + IP_PATTERN
)

ACCEPTED_PUBLICKEY_RE = re.compile(
    r"Accepted publickey for "
    r"(\S+) from "
    + IP_PATTERN
)

ACCEPTED_KEYBOARD_INTERACTIVE_RE = re.compile(
    r"Accepted keyboard-interactive(?:/pam)? for "
    r"(\S+) from "
    + IP_PATTERN
)

INVALID_USER_RE = re.compile(
    r"Invalid user "
    r"(\S+) from "
    + IP_PATTERN
)

CONNECTION_OPENED_RE = re.compile(
    r"Connection from "
    + IP_PATTERN
    + r" port (\d+)"
)

CONNECTION_RESET_INVALID_USER_RE = re.compile(
    r"Connection reset by invalid user "
    r"(\S+) "
    + IP_PATTERN
)

CONNECTION_RESET_AUTH_USER_RE = re.compile(
    r"Connection reset by authenticating user "
    r"(\S+) "
    + IP_PATTERN
)

#
# Exemple :
#
# Connection closed by authenticating user root
# 92.118.39.77 port 54728 [preauth]
#
CONNECTION_CLOSED_AUTH_USER_RE = re.compile(
    r"Connection closed by authenticating user "
    r"(\S+) "
    + IP_PATTERN
    + r" port "
)

#
# Exemple :
#
# Connection closed by 190.61.110.243 port 52940
#
CONNECTION_CLOSED_RE = re.compile(
    r"Connection closed by "
    + IP_PATTERN
    + r" port "
)


def valid_ip(value: str) -> bool:
    """
    Vérifie qu'une valeur est réellement
    une adresse IPv4 ou IPv6 valide.
    """

    try:
        ipaddress.ip_address(value)
        return True

    except ValueError:
        return False


def build_event(
    event_type: str,
    ip: str,
    username: str | None,
    line: str,
) -> SSHEvent | None:

    #
    # Protection centrale :
    #
    # aucune fausse IP ne doit pouvoir
    # sortir du parser.
    #
    if not valid_ip(ip):
        return None

    return SSHEvent(
        event_type=event_type,
        timestamp=datetime.now(
            timezone.utc
        ),
        ip=ip,
        username=username,
        message=line.strip(),
    )


def parse_ssh_line(
    line: str,
) -> SSHEvent | None:

    #
    # Nouvelle connexion TCP SSH.
    #
    match = CONNECTION_OPENED_RE.search(
        line
    )

    if match:
        ip, _port = match.groups()

        return build_event(
            "ssh.connection.opened",
            ip,
            None,
            line,
        )

    #
    # Mot de passe incorrect.
    #
    match = FAILED_PASSWORD_RE.search(
        line
    )

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.login.failed",
            ip,
            username,
            line,
        )

    #
    # Clé publique incorrecte.
    #
    match = FAILED_PUBLICKEY_RE.search(
        line
    )

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.login.failed",
            ip,
            username,
            line,
        )

    #
    # Authentification par mot de passe réussie.
    #
    match = (
        FAILED_KEYBOARD_INTERACTIVE_RE
        .search(line)
    )

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.login.failed",
            ip,
            username,
            line,
        )

    match = ACCEPTED_PASSWORD_RE.search(
        line
    )

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.login.success",
            ip,
            username,
            line,
        )

    #
    # Authentification par clé publique réussie.
    #
    match = ACCEPTED_PUBLICKEY_RE.search(
        line
    )

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.login.success",
            ip,
            username,
            line,
        )

    #
    # Utilisateur SSH inexistant.
    #
    #
    # Authentification keyboard-interactive/PAM réussie.
    #
    # Avec SSH Guardian MFA, c'est cette ligne qui marque
    # la réussite finale après publickey + Telegram.
    #
    match = (
        ACCEPTED_KEYBOARD_INTERACTIVE_RE
        .search(line)
    )

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.login.success",
            ip,
            username,
            line,
        )

    match = INVALID_USER_RE.search(
        line
    )

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.login.invalid_user",
            ip,
            username,
            line,
        )

    #
    # Reset pour utilisateur invalide.
    #
    match = (
        CONNECTION_RESET_INVALID_USER_RE
        .search(line)
    )

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.connection.reset",
            ip,
            username,
            line,
        )

    #
    # Reset pendant authentification.
    #
    match = (
        CONNECTION_RESET_AUTH_USER_RE
        .search(line)
    )

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.connection.reset",
            ip,
            username,
            line,
        )

    #
    # Connexion fermée pendant
    # l'authentification.
    #
    # IMPORTANT :
    # cette règle doit être testée AVANT
    # CONNECTION_CLOSED_RE.
    #
    match = (
        CONNECTION_CLOSED_AUTH_USER_RE
        .search(line)
    )

    if match:
        username, ip = match.groups()

        return build_event(
            "ssh.connection.closed",
            ip,
            username,
            line,
        )

    #
    # Connexion fermée sans username.
    #
    match = CONNECTION_CLOSED_RE.search(
        line
    )

    if match:
        ip = match.group(1)

        return build_event(
            "ssh.connection.closed",
            ip,
            None,
            line,
        )

    return None
