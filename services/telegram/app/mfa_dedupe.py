"""
Déduplication des notifications SSH après une décision MFA.

But :

- une approbation MFA Telegram produit déjà
  "CONNEXION SSH AUTORISÉE" ;
- un refus MFA Telegram produit déjà
  "CONNEXION SSH REFUSÉE".

Les événements OpenSSH produits immédiatement après ne doivent
donc pas créer une deuxième notification Telegram.

IMPORTANT :

Les connexions sans décision MFA explicite restent inchangées :

- MFA désactivé ;
- bypass utilisateur ;
- bypass IP statique ;
- bypass IP temporaire.

Dans ces cas aucun marqueur Redis n'existe et les notifications
SSH classiques continuent d'être envoyées.
"""


SUCCESS_PREFIX = (
    "telegram:mfa:suppress_success"
)

DENIAL_PREFIX = (
    "telegram:mfa:suppress_failure"
)


SUCCESS_TTL = 60

#
# Un refus PAM peut générer plusieurs lignes OpenSSH
# immédiatement après la décision.
#
# On garde donc le marqueur quelques secondes afin de
# supprimer tous les événements dérivés de CE refus.
#
DENIAL_TTL = 15


MFA_DENIAL_FAILURE_EVENTS = {
    "ssh.login.failed",
    "ssh.connection.reset",
    "ssh.connection.closed",
}


def success_key(
    username: str,
    ip: str,
) -> str:
    return (
        f"{SUCCESS_PREFIX}:"
        f"{username}:"
        f"{ip}"
    )


def denial_key(
    ip: str,
) -> str:
    return (
        f"{DENIAL_PREFIX}:"
        f"{ip}"
    )


def mark_mfa_approval(
    redis,
    username: str,
    ip: str,
) -> None:

    username = str(
        username or ""
    ).strip()

    ip = str(
        ip or ""
    ).strip()

    if not username or not ip:
        return

    redis.setex(
        success_key(
            username,
            ip,
        ),
        SUCCESS_TTL,
        "1",
    )


def mark_mfa_denial(
    redis,
    ip: str,
) -> None:

    ip = str(
        ip or ""
    ).strip()

    if not ip:
        return

    redis.setex(
        denial_key(ip),
        DENIAL_TTL,
        "1",
    )


def should_suppress_ssh_event(
    redis,
    payload: dict,
) -> bool:

    event_type = str(
        payload.get(
            "event_type"
        )
        or ""
    )

    username = str(
        payload.get(
            "username"
        )
        or ""
    ).strip()

    ip = str(
        payload.get(
            "ip"
        )
        or ""
    ).strip()

    #
    # ========================================================
    # APPROBATION MFA
    # ========================================================
    #
    # Une approbation doit supprimer UNE SEULE notification
    # ssh.login.success.
    #
    # getdel() consomme donc le marqueur.
    #
    if (
        event_type
        == "ssh.login.success"
        and username
        and ip
    ):
        key = success_key(
            username,
            ip,
        )

        value = redis.getdel(
            key
        )

        return bool(value)

    #
    # ========================================================
    # REFUS MFA
    # ========================================================
    #
    # Un refus PAM peut produire plusieurs événements :
    #
    #   ssh.login.failed
    #   ssh.connection.reset
    #   ssh.connection.closed
    #
    # Le marqueur n'est PAS consommé au premier événement.
    # Il expire tout seul après DENIAL_TTL secondes afin que
    # tous les événements dérivés du même refus soient
    # silencieux.
    #
    if (
        event_type
        in MFA_DENIAL_FAILURE_EVENTS
        and ip
    ):
        value = redis.get(
            denial_key(ip)
        )

        return bool(value)

    return False
