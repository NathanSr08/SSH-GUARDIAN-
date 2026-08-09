import os
import socket
from datetime import datetime, timezone

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings

from services.firewall.app.firewall import (
    Firewall,
    FirewallError,
)


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

                    if action != "ban_ip":

                        bus.ack(
                            stream,
                            group,
                            message_id,
                        )

                        continue

                    ip = command["ip"]

                    result = firewall.ban(ip)

                    firewall_event = {
                        "event_type":
                            "firewall.ip.banned",

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
