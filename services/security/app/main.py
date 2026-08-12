import os
import socket
from datetime import datetime

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings
from shared.events.ssh import SSHEvent

from services.security.app.engine import SecurityEngine


BLOCKED_COUNTRIES_FILE = Settings.BLOCKED_COUNTRIES_FILE


def payload_to_event(payload: dict) -> SSHEvent:
    return SSHEvent(
        event_type=payload["event_type"],
        timestamp=datetime.fromisoformat(
            payload["timestamp"]
        ),
        ip=payload["ip"],
        username=payload.get("username"),
        message=payload.get("message"),
    )


def get_blocked_countries() -> set[str]:
    try:
        with open(
            BLOCKED_COUNTRIES_FILE,
            "r",
            encoding="utf-8",
        ) as handle:

            return {
                line.strip().lower()
                for line in handle
                if line.strip()
            }

    except FileNotFoundError:
        return set()


def main() -> None:
    bus = RedisBus()
    security = SecurityEngine()

    stream = Settings.SSH_ENRICHED_STREAM
    group = "security-enriched"

    consumer = (
        f"{socket.gethostname()}-"
        f"{os.getpid()}"
    )

    print("SSH Guardian - Security Service")
    print(f"Redis : {bus.ping()}")
    print(f"Consumer : {consumer}")
    print(f"Lecture : {stream}")
    print("Blocage pays : PRE-AUTH sur ssh.connection.opened")

    try:
        while True:

            messages = bus.consume(
                stream=stream,
                group=group,
                consumer=consumer,
            )

            for message_id, payload in messages:

                try:
                    event = payload_to_event(
                        payload
                    )

                    geo = (
                        payload.get("geo")
                        or {}
                    )

                    country_code = str(
                        geo.get("country_code")
                        or ""
                    ).lower()

                    blocked_countries = (
                        get_blocked_countries()
                    )

                    #
                    # Expose immédiatement la décision pays à PAM.
                    # PAM attend brièvement cette clé avant de créer
                    # une demande MFA afin d'éviter la race :
                    #
                    #   MFA autorisé
                    #   puis ban blocked_country quelques ms après.
                    #
                    country_policy_key = (
                        f"security:country-policy:{event.ip}"
                    )

                    country_blocked = bool(
                        country_code
                        and country_code
                        in blocked_countries
                    )

                    bus.client.set(
                        country_policy_key,
                        (
                            "blocked"
                            if country_blocked
                            else "allowed"
                        ),
                        ex=30,
                    )

                    decision = None

                    #
                    # WHITELIST TOUJOURS PRIORITAIRE
                    #
                    if event.ip in Settings.WHITELIST:

                        decision = {
                            "action": "ignore",
                            "reason": "whitelisted",
                            "ip": event.ip,
                        }

                    #
                    # PAYS BLOQUÉ
                    #
                    elif (
                        country_code
                        and country_code
                        in blocked_countries
                    ):

                        redis_key = (
                            "security:"
                            "blocked-country:"
                            f"{event.ip}"
                        )

                        #
                        # NX = seulement le premier événement.
                        #
                        first_ban = bus.client.set(
                            redis_key,
                            country_code,
                            nx=True,
                            ex=Settings.BAN_DURATION_SECONDS,
                        )

                        if first_ban:

                            decision = {
                                "action": "ban_ip",
                                "ip": event.ip,
                                "reason": "blocked_country",
                                "country_code":
                                    country_code.upper(),
                                "country":
                                    geo.get("country"),
                                "city":
                                    geo.get("city"),
                                "isp":
                                    geo.get("isp"),
                                "trigger_event_type":
                                    event.event_type,
                                "ban_duration_seconds":
                                    Settings.BAN_DURATION_SECONDS,
                            }

                    #
                    # POLITIQUE NORMALE
                    #
                    else:

                        decision = (
                            security.process(event)
                        )

                    if decision is not None:

                        #
                        # Ajouter les informations GeoIP à toute
                        # décision Security.
                        #
                        # Ainsi les bans normaux disposent aussi de
                        # country / city / isp dans firewall.events.
                        #
                        decision.setdefault(
                            "country",
                            geo.get("country"),
                        )

                        decision.setdefault(
                            "country_code",
                            geo.get("country_code"),
                        )

                        decision.setdefault(
                            "city",
                            geo.get("city"),
                        )

                        decision.setdefault(
                            "isp",
                            geo.get("isp"),
                        )

                        #
                        # Exposer l'état courant des tentatives
                        # aux autres microservices.
                        #
                        if decision.get("action") in {
                            "monitor",
                            "ban_ip",
                            "ignore",
                        } and decision.get("attempts") is not None:

                            attempt_key = (
                                f"security:attempts:{event.ip}"
                            )

                            bus.client.hset(
                                attempt_key,
                                mapping={
                                    "attempts":
                                        decision.get(
                                            "attempts",
                                            0,
                                        ),
                                    "max_attempts":
                                        Settings.MAX_ATTEMPTS,
                                    "remaining_attempts":
                                        max(
                                            Settings.MAX_ATTEMPTS
                                            - int(
                                                decision.get(
                                                    "attempts",
                                                    0,
                                                )
                                            ),
                                            0,
                                        ),
                                },
                            )

                            bus.client.expire(
                                attempt_key,
                                Settings.BAN_DURATION_SECONDS,
                            )

                        decision[
                            "source_event_id"
                        ] = message_id

                        action_id = bus.publish(
                            Settings.SECURITY_ACTIONS_STREAM,
                            decision,
                        )

                        print(
                            f"[SECURITY] "
                            f"{decision} "
                            f"redis_id={action_id}"
                        )

                    bus.ack(
                        stream,
                        group,
                        message_id,
                    )

                except Exception as exc:

                    print(
                        f"[ERROR] "
                        f"id={message_id} "
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )

    except KeyboardInterrupt:

        print(
            "\nSecurity Service arrêté."
        )


if __name__ == "__main__":
    main()
