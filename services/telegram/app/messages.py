import re
import time

from services.geoip.app.provider import GeoIPProvider
from services.telegram.app.client import TelegramClient


#
# ============================================================
# Tentatives SSH
# ============================================================
#

def get_attempt_state(
    client: TelegramClient,
    ip: str,
) -> dict:
    """
    Récupère le compteur calculé par Security.

    Telegram et Security consomment Redis en parallèle.
    On laisse donc quelques centaines de millisecondes
    à Security pour écrire le compteur.
    """

    key = f"security:attempts:{ip}"

    for _ in range(8):
        try:
            raw = client.bus.client.hgetall(
                key
            )

            if raw:
                return {
                    "attempts": int(
                        raw.get(
                            "attempts",
                            0,
                        )
                    ),

                    "max_attempts": int(
                        raw.get(
                            "max_attempts",
                            0,
                        )
                    ),

                    "remaining_attempts": int(
                        raw.get(
                            "remaining_attempts",
                            0,
                        )
                    ),
                }

        except Exception:
            return {}

        time.sleep(0.10)

    return {}


def attempt_text(
    client: TelegramClient,
    ip: str,
) -> str:

    state = get_attempt_state(
        client,
        ip,
    )

    attempts = state.get(
        "attempts",
        0,
    )

    max_attempts = state.get(
        "max_attempts",
        0,
    )

    remaining = state.get(
        "remaining_attempts",
        0,
    )

    if not max_attempts:
        return ""

    text = (
        "\n🔢 Tentatives : "
        f"<b>{attempts}/{max_attempts}</b>"
    )

    if remaining > 0:
        text += (
            "\n⚠️ Avant bannissement : "
            f"<b>{remaining}</b>"
        )

    else:
        text += (
            "\n🚫 <b>Seuil de bannissement atteint</b>"
        )

    return text


#
# ============================================================
# Déduplication
# ============================================================
#

def is_blocked_country_ip(
    client: TelegramClient,
    ip: str,
) -> bool:
    """
    Retourne True si Security a marqué cette IP comme provenant
    d'un pays bloqué.
    """

    if not ip:
        return False

    key = f"security:blocked-country:{ip}"

    for _ in range(10):
        try:
            if client.bus.client.exists(key):
                return True
        except Exception:
            return False

        time.sleep(0.05)

    return False


def extract_ssh_port(
    event: dict,
) -> str | None:

    message = str(
        event.get("message")
        or ""
    )

    match = re.search(
        r"\bport\s+(\d+)\b",
        message,
    )

    if not match:
        return None

    return match.group(1)


def failure_dedupe_key(
    event: dict,
) -> str:

    ip = str(
        event.get("ip")
        or "unknown"
    )

    port = extract_ssh_port(
        event
    )

    #
    # Le port source identifie une connexion SSH.
    #
    # Exemple :
    # Failed publickey ... port 49489
    # Connection reset ... port 49489
    #
    # => une seule tentative logique.
    #
    if port:
        return (
            "telegram:ssh-failure:"
            f"{ip}:{port}"
        )

    #
    # Fallback si OpenSSH fournit une ligne
    # sans port.
    #
    return (
        "telegram:ssh-failure:"
        f"{ip}:fallback"
    )


def should_notify_failure(
    client: TelegramClient,
    event: dict,
) -> bool:
    """
    Retourne True uniquement pour le PREMIER événement
    d'échec associé à une connexion SSH.

    TTL de 30 secondes :
    largement suffisant pour englober failed/reset/closed.
    """

    try:
        result = client.bus.client.set(
            failure_dedupe_key(
                event
            ),
            "1",
            nx=True,
            ex=30,
        )

        return bool(result)

    except Exception:
        #
        # En cas de panne Redis, mieux vaut envoyer
        # une notification que perdre une alerte.
        #
        return True


#
# ============================================================
# GeoIP helper
# ============================================================
#

def fallback_geoip(
    client: TelegramClient,
    ip: str,
) -> dict:
    try:
        provider = GeoIPProvider(
            client.bus
        )

        result = provider.lookup(
            ip
        )

        if isinstance(
            result,
            dict,
        ):
            return result

    except Exception as exc:
        print(
            "[TELEGRAM GEOIP ERROR] "
            f"ip={ip} "
            f"{exc}"
        )

    return {}


#
# ============================================================
# SSH EVENTS
# ============================================================
#

def format_ssh_event(
    client: TelegramClient,
    event: dict,
) -> str | None:

    event_type = event.get(
        "event_type"
    )

    geo = (
        event.get("geo")
        or {}
    )

    raw_ip = str(
        event.get("ip")
        or ""
    )

    ip = client.escape(
        raw_ip
    )

    username = client.escape(
        event.get("username")
        or "Inconnu"
    )

    country = client.escape(
        geo.get("country")
        or "Inconnu"
    )

    city = client.escape(
        geo.get("city")
        or "Inconnu"
    )

    isp = client.escape(
        geo.get("isp")
        or "Inconnu"
    )

    #
    # --------------------------------------------------------
    # Ouverture TCP
    # --------------------------------------------------------
    #
    # Utilisée par Security pour compter.
    # Jamais affichée directement.
    #
    if event_type == "ssh.connection.opened":
        return None

    #
    # Une IP provenant d'un pays bloqué est bannie dès
    # ssh.connection.opened. Les événements closed/reset/failed
    # qui suivent appartiennent à cette même connexion et ne
    # doivent pas produire une seconde notification Telegram.
    #
    if event_type in {
        "ssh.connection.closed",
        "ssh.connection.reset",
        "ssh.login.failed",
        "ssh.login.invalid_user",
    }:
        if is_blocked_country_ip(
            client,
            raw_ip,
        ):
            return None

    #
    # --------------------------------------------------------
    # Tous les événements d'échec
    # --------------------------------------------------------
    #

    failure_types = {
        "ssh.login.failed",
        "ssh.login.invalid_user",
        "ssh.connection.closed",
        "ssh.connection.reset",
    }

    if event_type in failure_types:

        #
        # Même IP + même port SSH =
        # même connexion =
        # UNE notification.
        #
        if not should_notify_failure(
            client,
            event,
        ):
            return None

        counter = attempt_text(
            client,
            raw_ip,
        )

        if event_type == "ssh.login.invalid_user":
            reason = (
                "utilisateur SSH invalide"
            )

        elif event_type == "ssh.login.failed":
            reason = (
                "authentification refusée"
            )

        elif event_type == "ssh.connection.reset":
            reason = (
                "connexion interrompue "
                "avant authentification"
            )

        else:
            reason = (
                "connexion fermée "
                "avant authentification"
            )

        return (
            "🚨 <b>Tentative SSH échouée</b>\n\n"
            f"👤 Utilisateur : "
            f"<code>{username}</code>\n"
            f"🌐 IP : "
            f"<code>{ip}</code>\n"
            f"📍 Localisation : "
            f"{city}, {country}\n"
            f"🏢 FAI : "
            f"{isp}\n"
            f"⚠️ Raison : "
            f"{reason}"
            f"{counter}"
        )

    #
    # --------------------------------------------------------
    # Succès SSH
    # --------------------------------------------------------
    #

    if event_type == "ssh.login.success":
        return (
            "✅ <b>Connexion SSH réussie</b>\n\n"
            f"👤 Utilisateur : "
            f"<code>{username}</code>\n"
            f"🌐 IP : "
            f"<code>{ip}</code>\n"
            f"📍 Localisation : "
            f"{city}, {country}\n"
            f"🏢 FAI : "
            f"{isp}"
        )

    return None


#
# ============================================================
# FIREWALL EVENTS
# ============================================================
#

def format_firewall_event(
    client: TelegramClient,
    event: dict,
) -> str | None:

    event_type = event.get(
        "event_type"
    )

    #
    # --------------------------------------------------------
    # Pays bloqué
    # --------------------------------------------------------
    #

    if event_type == "security.country.blocked":

        country_code = client.escape(
            event.get("country_code")
            or "??"
        )

        source = client.escape(
            str(
                event.get("source")
                or "unknown"
            ).title()
        )

        return (
            "🌍 <b>Pays bloqué</b>\n\n"
            f"🛡 Pays : "
            f"<b>{country_code}</b>\n"
            f"📡 Source : "
            f"<b>{source}</b>\n\n"
            "Toute nouvelle connexion détectée "
            "depuis ce pays sera automatiquement "
            "bloquée."
        )

    #
    # --------------------------------------------------------
    # Pays débloqué
    # --------------------------------------------------------
    #

    if event_type == "security.country.unblocked":

        country_code = client.escape(
            event.get("country_code")
            or "??"
        )

        source = client.escape(
            str(
                event.get("source")
                or "unknown"
            ).title()
        )

        count = event.get(
            "unbanned_count",
            0,
        )

        return (
            "🔓 <b>Pays débloqué</b>\n\n"
            f"🌍 Pays : "
            f"<b>{country_code}</b>\n"
            f"📡 Source : "
            f"<b>{source}</b>\n"
            f"✅ IP débannies : "
            f"<b>{count}</b>"
        )

    #
    # --------------------------------------------------------
    # IP débannie
    # --------------------------------------------------------
    #

    if event_type == "firewall.ip.unbanned":

        ip = client.escape(
            event.get("ip")
            or "?"
        )

        country_code = client.escape(
            event.get("country_code")
            or ""
        )

        if country_code:
            return (
                "🔓 <b>IP débannie</b>\n\n"
                f"🌐 IP : "
                f"<code>{ip}</code>\n"
                f"🌍 Pays débloqué : "
                f"<b>{country_code}</b>"
            )

        return (
            "🔓 <b>IP débannie</b>\n\n"
            f"🌐 IP : "
            f"<code>{ip}</code>"
        )

    #
    # --------------------------------------------------------
    # Tout ce qui n'est pas un ban
    # --------------------------------------------------------
    #

    if event_type != "firewall.ip.banned":
        return None

    #
    # --------------------------------------------------------
    # IP bannie
    # --------------------------------------------------------
    #

    raw_ip = str(
        event.get("ip")
        or ""
    )

    ip = client.escape(
        raw_ip
        or "?"
    )

    reason = client.escape(
        event.get("reason")
        or "security_policy"
    )

    #
    # Les données doivent normalement venir
    # du Security Engine.
    #
    country_raw = (
        event.get("country")
    )

    city_raw = (
        event.get("city")
    )

    isp_raw = (
        event.get("isp")
    )

    #
    # Fallback :
    # si Firewall n'a pas propagé le GeoIP,
    # Telegram le récupère directement.
    #
    if not (
        country_raw
        and city_raw
        and isp_raw
    ):
        geo = fallback_geoip(
            client,
            raw_ip,
        )

        country_raw = (
            country_raw
            or geo.get("country")
        )

        city_raw = (
            city_raw
            or geo.get("city")
        )

        isp_raw = (
            isp_raw
            or geo.get("isp")
        )

    country = client.escape(
        country_raw
        or "Inconnu"
    )

    city = client.escape(
        city_raw
        or "Inconnu"
    )

    isp = client.escape(
        isp_raw
        or "Inconnu"
    )

    firewall_result = (
        event.get("firewall_result")
        or {}
    )

    status = client.escape(
        firewall_result.get("status")
        or "unknown"
    )

    duration = (
        event.get(
            "ban_duration_seconds"
        )
        or 0
    )

    hours = (
        round(
            int(duration) / 3600,
            2,
        )
        if duration
        else "?"
    )

    attempts_raw = event.get("attempts")

    attempts = (
        client.escape(str(attempts_raw))
        if attempts_raw is not None
        else None
    )

    attempts_line = ""

    if reason != "blocked_country" and attempts is not None:
        attempts_line = (
            f"🔢 Tentatives : "
            f"<b>{attempts}</b>\n"
        )

    return (
        "🚫 <b>IP bannie</b>\n\n"
        f"🌐 IP : "
        f"<code>{ip}</code>\n"
        f"📍 Localisation : "
        f"<b>{city}, {country}</b>\n"
        f"🏢 FAI : "
        f"{isp}\n\n"
        f"⚠️ Raison : "
        f"{reason}\n"
        f"{attempts_line}"
        f"⏱ Durée : "
        f"<b>{hours} h</b>\n"
        f"🔥 Firewall : "
        f"<b>{status}</b>"
    )
