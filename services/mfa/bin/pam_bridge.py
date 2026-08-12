#!/usr/bin/env python3

import json
import os
import sys
import time
import uuid

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings
from services.mfa.app.runtime import MFARuntime


# ============================================================
# LOGGING
# ============================================================

def log(message):
    print(
        f"[MFA PAM] {message}",
        file=sys.stderr,
        flush=True,
    )


def allow():
    log(
        "AUTHORISED"
    )

    raise SystemExit(0)


def deny(reason):
    log(
        f"DENIED reason={reason}"
    )

    raise SystemExit(1)


# ============================================================
# RPC MFA
# ============================================================

def rpc_create(
    bus,
    username,
    ip,
):
    """
    Demande au service MFA de créer une nouvelle
    autorisation SSH.
    """

    rpc_id = str(
        uuid.uuid4()
    )

    reply_key = (
        f"mfa.reply:{rpc_id}"
    )

    bus.publish(
        Settings.MFA_COMMANDS_STREAM,
        {
            "request_id":
                rpc_id,

            "command":
                "create",

            "username":
                username,

            "ip":
                ip,

            "source":
                "pam",
        },
    )

    response = (
        bus.client.blpop(
            reply_key,
            timeout=5,
        )
    )

    if not response:
        raise RuntimeError(
            "MFA Service timeout"
        )

    payload = json.loads(
        response[1]
    )

    if not payload.get(
        "ok"
    ):
        raise RuntimeError(
            payload.get(
                "error",
                "MFA Service error",
            )
        )

    return (
        payload.get("result")
        or {}
    )


# ============================================================
# ATTENTE DE LA DECISION
# ============================================================

def wait_for_decision(
    bus,
    request_id,
    timeout_seconds,
):
    """
    Attend la réponse Telegram / Panel.

    Le timeout est dynamique et provient maintenant
    de MFARuntime Redis.
    """

    key = (
        f"mfa:request:"
        f"{request_id}"
    )

    timeout_seconds = int(
        timeout_seconds
    )

    deadline = (
        time.monotonic()
        + timeout_seconds
        + 2
    )

    while (
        time.monotonic()
        < deadline
    ):
        raw = bus.client.get(
            key
        )

        if not raw:
            time.sleep(
                0.25
            )

            continue

        if isinstance(
            raw,
            bytes,
        ):
            raw = raw.decode(
                "utf-8"
            )

        payload = json.loads(
            raw
        )

        status = payload.get(
            "status"
        )

        if status in {
            "approved",
            "denied",
            "expired",
            "cancelled",
        }:
            return status

        time.sleep(
            0.25
        )

    return "expired"


# ============================================================
# MAIN PAM
# ============================================================

def main():

    username = (
        os.getenv(
            "PAM_USER",
            "",
        )
        .strip()
    )

    ip = (
        os.getenv(
            "PAM_RHOST",
            "",
        )
        .strip()
    )

    pam_type = (
        os.getenv(
            "PAM_TYPE",
            "",
        )
        .strip()
    )

    log(
        f"user={username} "
        f"ip={ip or 'unknown'} "
        f"type={pam_type or 'unknown'}"
    )

    # --------------------------------------------------------
    # Le bridge ne sert qu'à PAM auth
    # --------------------------------------------------------

    if (
        pam_type
        and pam_type != "auth"
    ):
        allow()

    # --------------------------------------------------------
    # Vérifications de base
    # --------------------------------------------------------

    if not username:
        deny(
            "missing_username"
        )

    # --------------------------------------------------------
    # IP distante obligatoire
    # --------------------------------------------------------

    if not ip:

        if (
            Settings.MFA_FAIL_MODE
            == "allow"
        ):
            log(
                "missing_ip fail-open"
            )

            allow()

        deny(
            "missing_remote_ip"
        )

    # --------------------------------------------------------
    # Redis / Runtime MFA
    # --------------------------------------------------------

    try:
        bus = RedisBus()

        if not bus.ping():
            raise RuntimeError(
                "Redis unavailable"
            )

        runtime = MFARuntime(
            bus.client
        )

        # ----------------------------------------------------
        # PRIORITE SECURITE
        # ----------------------------------------------------
        #
        # Le service Security crée cette clé lorsqu'une IP
        # appartient à un pays actuellement bloqué :
        #
        #   security:blocked-country:<IP>
        #
        # Une interdiction de sécurité doit TOUJOURS avoir
        # priorité sur :
        #
        #   - MFA
        #   - bypass MFA temporaire
        #
        # Dans ce cas aucune demande MFA ne doit être créée.
        #
        blocked_country_key = (
            f"security:blocked-country:{ip}"
        )

        country_policy_key = (
            f"security:country-policy:{ip}"
        )

        #
        # Security / GeoIP et PAM travaillent en parallèle.
        #
        # On attend brièvement la décision pays calculée par
        # Security avant de créer une demande MFA.
        #
        # Cela évite :
        #
        #   autorisation MFA
        #   puis ban blocked_country juste après.
        #
        country_policy = None

        for _ in range(20):

            try:
                raw_policy = bus.client.get(
                    country_policy_key
                )
            except Exception:
                raw_policy = None

            if raw_policy:

                if isinstance(
                    raw_policy,
                    bytes,
                ):
                    raw_policy = raw_policy.decode(
                        "utf-8"
                    )

                country_policy = str(
                    raw_policy
                )

                break

            #
            # Compatibilité avec l'ancienne clé Security.
            #
            if bus.client.exists(
                blocked_country_key
            ):
                country_policy = "blocked"
                break

            time.sleep(
                0.05
            )

        if (
            country_policy == "blocked"
            or bus.client.exists(
                blocked_country_key
            )
        ):
            log(
                "security=blocked_country "
                f"ip={ip} "
                "mfa_request=skipped"
            )

            deny(
                "blocked_country"
            )

        if country_policy == "allowed":
            log(
                "security=country_allowed "
                f"ip={ip}"
            )

        elif country_policy is None:
            log(
                "security=country_policy_timeout "
                f"ip={ip}"
            )

        # ----------------------------------------------------
        # Bypass permanent utilisateur (.env)
        # ----------------------------------------------------
        #
        # IMPORTANT :
        # ce bypass est évalué uniquement APRÈS les règles
        # Security. Un pays/IP bloqué reste donc bloqué.
        #
        if (
            username
            in Settings.MFA_BYPASS_USERS
        ):
            log(
                "bypass=permanent_user"
            )

            allow()

        # ----------------------------------------------------
        # Bypass permanent IP (.env)
        # ----------------------------------------------------
        #
        # Même priorité :
        #
        # Security > bypass permanent > MFA
        #
        if (
            ip
            in Settings.MFA_BYPASS_IPS
        ):
            log(
                "bypass=permanent_ip"
            )

            allow()

        # ----------------------------------------------------
        # MFA runtime ON/OFF
        # ----------------------------------------------------

        if not runtime.enabled():
            log(
                "MFA runtime disabled"
            )

            allow()

        # ----------------------------------------------------
        # Bypass temporaire Redis
        # ----------------------------------------------------

        if runtime.is_ip_allowed(
            ip
        ):
            info = (
                runtime.bypass_info(
                    ip
                )
                or {}
            )

            log(
                "bypass=temporary_ip "
                f"ttl={info.get('ttl', 0)}"
            )

            allow()

        # ----------------------------------------------------
        # Timeout dynamique
        # ----------------------------------------------------

        timeout_seconds = (
            runtime.timeout_seconds()
        )

        log(
            f"timeout={timeout_seconds}s"
        )

        # ----------------------------------------------------
        # Création demande MFA
        # ----------------------------------------------------

        request = rpc_create(
            bus,
            username,
            ip,
        )

        request_id = (
            request.get(
                "request_id"
            )
        )

        if not request_id:
            raise RuntimeError(
                "Missing MFA request_id"
            )

        log(
            f"request={request_id} "
            "status=pending"
        )

        # ----------------------------------------------------
        # Attente Telegram / Panel
        # ----------------------------------------------------

        status = wait_for_decision(
            bus,
            request_id,
            timeout_seconds,
        )

        log(
            f"request={request_id} "
            f"status={status}"
        )

        # ----------------------------------------------------
        # Décision
        # ----------------------------------------------------

        if status == "approved":
            allow()

        deny(
            status
            or "unknown"
        )

    except SystemExit:
        raise

    except Exception as exc:

        log(
            f"error={exc}"
        )

        # ----------------------------------------------------
        # Fail mode
        # ----------------------------------------------------

        if (
            Settings.MFA_FAIL_MODE
            == "allow"
        ):
            log(
                "fail-open"
            )

            allow()

        #
        # Par défaut :
        # FAIL CLOSED
        #
        deny(
            "backend_error"
        )


if __name__ == "__main__":
    main()
