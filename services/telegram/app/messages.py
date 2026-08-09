from services.telegram.app.client import TelegramClient


def get_attempt_state(
    client: TelegramClient,
    ip: str,
) -> dict:
    try:
        key = f"security:attempts:{ip}"

        raw = client.bus.client.hgetall(key)

        if not raw:
            return {}

        return {
            "attempts": int(
                raw.get("attempts", 0)
            ),
            "max_attempts": int(
                raw.get("max_attempts", 0)
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
        f"\n🔢 Tentatives : "
        f"<b>{attempts}/{max_attempts}</b>"
    )

    if remaining > 0:
        text += (
            f"\n⚠️ Avant bannissement : "
            f"<b>{remaining}</b>"
        )
    else:
        text += (
            "\n🚫 <b>Seuil de bannissement atteint</b>"
        )

    return text


def format_ssh_event(
    client: TelegramClient,
    event: dict,
) -> str | None:
    event_type = event.get(
        "event_type"
    )

    geo = event.get("geo") or {}

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

    country_code = client.escape(
        geo.get("country_code")
        or "??"
    )

    city = client.escape(
        geo.get("city")
        or "Inconnu"
    )

    isp = client.escape(
        geo.get("isp")
        or "Inconnu"
    )

    counter = attempt_text(
        client,
        raw_ip,
    )

    #
    # Connection opened :
    # interne uniquement.
    #
    if event_type == "ssh.connection.opened":
        return None

    #
    # Échec auth classique
    #
    if event_type == "ssh.login.failed":
        return (
            "🚨 <b>Tentative SSH échouée</b>\n\n"
            f"👤 Utilisateur : <code>{username}</code>\n"
            f"🌐 IP : <code>{ip}</code>\n"
            f"📍 Localisation : {city}, {country}\n"
            f"🏢 FAI : {isp}\n"
            f"⚠️ Raison : authentification refusée"
            f"{counter}"
        )

    #
    # Utilisateur invalide
    #
    if event_type == "ssh.login.invalid_user":
        return (
            "🚨 <b>Tentative SSH échouée</b>\n\n"
            f"👤 Utilisateur : <code>{username}</code>\n"
            f"🌐 IP : <code>{ip}</code>\n"
            f"📍 Localisation : {city}, {country}\n"
            f"🏢 FAI : {isp}\n"
            f"⚠️ Raison : utilisateur SSH invalide"
            f"{counter}"
        )

    #
    # Connexion fermée avant authentification
    #
    if event_type == "ssh.connection.closed":
        return (
            "🚨 <b>Tentative SSH échouée</b>\n\n"
            f"🌐 IP : <code>{ip}</code>\n"
            f"📍 Localisation : {city}, {country}\n"
            f"🏢 FAI : {isp}\n"
            f"⚠️ Raison : connexion fermée avant authentification"
            f"{counter}"
        )

    #
    # Connexion reset avant authentification
    #
    if event_type == "ssh.connection.reset":
        return (
            "🚨 <b>Tentative SSH échouée</b>\n\n"
            f"👤 Utilisateur : <code>{username}</code>\n"
            f"🌐 IP : <code>{ip}</code>\n"
            f"📍 Localisation : {city}, {country}\n"
            f"🏢 FAI : {isp}\n"
            f"⚠️ Raison : connexion interrompue avant authentification"
            f"{counter}"
        )

    #
    # Succès
    #
    if event_type == "ssh.login.success":
        return (
            "✅ <b>Connexion SSH réussie</b>\n\n"
            f"👤 Utilisateur : <code>{username}</code>\n"
            f"🌐 IP : <code>{ip}</code>\n"
            f"📍 Localisation : {city}, {country}\n"
            f"🏢 FAI : {isp}"
        )

    return None


def format_firewall_event(
    client: TelegramClient,
    event: dict,
) -> str | None:
    event_type = event.get(
        "event_type"
    )

    if event_type == "security.country.blocked":
        country_code = client.escape(
            event.get("country_code")
            or "??"
        )

        return (
            "🌍 <b>Pays bloqué</b>\n\n"
            f"🛡 Pays : <b>{country_code}</b>\n"
            "📡 Source : Control / Panel\n\n"
            "Toute nouvelle connexion détectée "
            "depuis ce pays sera automatiquement bloquée."
        )

    if event_type == "security.country.unblocked":
        country_code = client.escape(
            event.get("country_code")
            or "??"
        )

        count = event.get(
            "unbanned_count",
            0,
        )

        return (
            "🔓 <b>Pays débloqué</b>\n\n"
            f"🌍 Pays : <b>{country_code}</b>\n"
            f"✅ IP débannies : <b>{count}</b>"
        )

    if event_type == "firewall.ip.unbanned":
        ip = client.escape(
            event.get("ip")
        )

        country_code = client.escape(
            event.get("country_code")
            or ""
        )

        if country_code:
            return (
                "🔓 <b>IP débannie</b>\n\n"
                f"🌐 IP : <code>{ip}</code>\n"
                f"🌍 Pays débloqué : "
                f"<b>{country_code}</b>"
            )

        return (
            "🔓 <b>IP débannie</b>\n\n"
            f"🌐 IP : <code>{ip}</code>"
        )

    if event_type != "firewall.ip.banned":
        return None

    ip = client.escape(
        event.get("ip")
    )

    reason = event.get(
        "reason"
    ) or "security_policy"

    firewall_result = (
        event.get("firewall_result")
        or {}
    )

    status = client.escape(
        firewall_result.get("status")
        or "unknown"
    )

    duration = event.get(
        "ban_duration_seconds"
    )

    hours = (
        round(
            int(duration) / 3600,
            2,
        )
        if duration
        else "?"
    )

    attempts = client.escape(
        event.get("attempts")
        or "?"
    )

    return (
        "🚫 <b>IP bannie</b>\n\n"
        f"🌐 IP : <code>{ip}</code>\n"
        f"⚠️ Raison : {client.escape(reason)}\n"
        f"🔢 Tentatives : {attempts}\n"
        f"⏱ Durée : {hours} h\n"
        f"🔥 Firewall : {status}"
    )
