import os
import socket
from datetime import datetime, timedelta, timezone

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings

from services.firewall.app.firewall import (
    Firewall,
    FirewallError,
)


BAN_EXPIRY_ZSET = "firewall:bans:expires"


def schedule_ban_expiry(
    bus,
    ip: str,
    command: dict,
) -> float | None:
    """
    Persiste l'échéance d'un ban dans Redis.

    Le score du ZSET est un timestamp Unix UTC.
    """
    duration = command.get(
        "ban_duration_seconds"
    )

    if duration is None:
        return None

    try:
        duration = int(duration)
    except (TypeError, ValueError):
        return None

    if duration <= 0:
        return None

    expires_at_raw = command.get(
        "expires_at"
    )

    expires_at = None

    if expires_at_raw:
        try:
            expires_at = datetime.fromisoformat(
                str(expires_at_raw)
            )

            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(
                    tzinfo=timezone.utc
                )

        except (TypeError, ValueError):
            expires_at = None

    if expires_at is None:
        expires_at = (
            datetime.now(timezone.utc)
            + timedelta(seconds=duration)
        )

    score = expires_at.timestamp()

    bus.client.zadd(
        BAN_EXPIRY_ZSET,
        {
            ip: score,
        },
    )

    return score


def clear_ban_expiry(
    bus,
    ip: str,
) -> None:
    bus.client.zrem(
        BAN_EXPIRY_ZSET,
        ip,
    )


def process_expired_bans(
    bus,
    firewall,
    now: datetime | None = None,
) -> list[str]:
    """
    Débannit les IP dont l'échéance persistée est dépassée.

    Une entrée n'est supprimée du ZSET qu'après un unban
    firewall réussi.
    """
    now = (
        now
        or datetime.now(timezone.utc)
    )

    expired = bus.client.zrangebyscore(
        BAN_EXPIRY_ZSET,
        "-inf",
        now.timestamp(),
    )

    unbanned = []

    for ip in expired:

        try:
            result = firewall.unban(ip)

            clear_ban_expiry(
                bus,
                ip,
            )

            #
            # Nettoyer également les états temporaires
            # utilisés par Security/PAM.
            #
            bus.client.delete(
                f"security:blocked-country:{ip}",
                f"security:country-policy:{ip}",
                f"security:attempts:{ip}",
            )

            event = {
                "event_type":
                    "firewall.ip.unbanned",

                "timestamp":
                    datetime.now(
                        timezone.utc
                    ).isoformat(),

                "ip":
                    ip,

                "reason":
                    "ban_expired",

                "firewall_result":
                    result,
            }

            event_id = bus.publish(
                Settings.FIREWALL_EVENTS_STREAM,
                event,
            )

            print(
                f"[FIREWALL] "
                f"auto-unban ip={ip} "
                f"event={event_id}"
            )

            unbanned.append(ip)

        except FirewallError as exc:

            print(
                f"[FIREWALL ERROR] "
                f"auto-unban ip={ip} "
                f"{exc}"
            )

        except Exception as exc:

            print(
                f"[ERROR] "
                f"auto-unban ip={ip} "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

    return unbanned


def main() -> None:
    bus = RedisBus()
    firewall = Firewall()

    stream = Settings.SECURITY_ACTIONS_STREAM
    group = "firewall"

    consumer = (
        f"{socket.gethostname()}-"
        f"{os.getpid()}"
    )

    print("SSH Guardian - Firewall Service")
    print(f"Redis : {bus.ping()}")
    print(f"Firewall actif : {firewall.enabled}")
    print(f"Consumer : {consumer}")

    try:
        while True:

            #
            # Vérifier avant chaque lecture du stream
            # les bans temporaires arrivés à expiration.
            #
            process_expired_bans(
                bus,
                firewall,
            )

            messages = bus.consume(
                stream=stream,
                group=group,
                consumer=consumer,
            )

            for message_id, command in messages:

                try:
                    action = command.get(
                        "action"
                    )

                    if action not in {
                        "ban_ip",
                        "unban_ip",
                    }:

                        bus.ack(
                            stream,
                            group,
                            message_id,
                        )

                        continue

                    ip = command["ip"]

                    if action == "ban_ip":
                        result = firewall.ban(ip)

                        schedule_ban_expiry(
                            bus,
                            ip,
                            command,
                        )

                        event_type = "firewall.ip.banned"

                    else:
                        result = firewall.unban(ip)

                        clear_ban_expiry(
                            bus,
                            ip,
                        )

                        bus.client.delete(
                            f"security:blocked-country:{ip}",
                            f"security:country-policy:{ip}",
                            f"security:attempts:{ip}",
                        )

                        event_type = "firewall.ip.unbanned"

                    firewall_event = {
                        "event_type":
                            event_type,

                        "timestamp":
                            datetime.now(
                                timezone.utc
                            ).isoformat(),

                        "ip":
                            ip,

                        "reason":
                            command.get("reason"),

                        "attempts":
                            command.get("attempts"),

                        "ban_duration_seconds":
                            command.get(
                                "ban_duration_seconds"
                            ),

                        "country_code":
                            command.get(
                                "country_code"
                            ),

                        "country":
                            command.get(
                                "country"
                            ),

                        "city":
                            command.get(
                                "city"
                            ),

                        "isp":
                            command.get(
                                "isp"
                            ),

                        "trigger_event_type":
                            command.get(
                                "trigger_event_type"
                            ),

                        "firewall_result":
                            result,

                        "source_action_id":
                            message_id,
                    }

                    event_id = bus.publish(
                        Settings.FIREWALL_EVENTS_STREAM,
                        firewall_event,
                    )

                    print(
                        f"[FIREWALL] "
                        f"{result} "
                        f"reason="
                        f"{command.get('reason')} "
                        f"event={event_id}"
                    )

                    bus.ack(
                        stream,
                        group,
                        message_id,
                    )

                except FirewallError as exc:

                    print(
                        f"[FIREWALL ERROR] "
                        f"{exc}"
                    )

                except Exception as exc:

                    print(
                        f"[ERROR] "
                        f"id={message_id} "
                        f"{exc}"
                    )

    except KeyboardInterrupt:

        print(
            "\nFirewall Service arrêté."
        )


if __name__ == "__main__":
    main()
