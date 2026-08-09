import os
import socket
import threading
import time

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings

from services.telegram.app.client import (
    TelegramClient,
)

from services.telegram.app.commands import (
    TelegramCommands,
)

from services.telegram.app.messages import (
    format_firewall_event,
    format_ssh_event,
)


def notifications(
    bus,
    telegram,
    consumer,
):
    while True:

        messages = bus.consume(
            stream=
                Settings.SSH_ENRICHED_STREAM,
            group="telegram-ssh",
            consumer=consumer,
            count=20,
            block_ms=1000,
            group_start_id="$",
        )

        for message_id, payload in messages:
            try:
                message = format_ssh_event(
                    telegram,
                    payload,
                )

                if message:
                    telegram.send(
                        message
                    )

                bus.ack(
                    Settings.SSH_ENRICHED_STREAM,
                    "telegram-ssh",
                    message_id,
                )

            except Exception as exc:
                print(
                    f"[TELEGRAM ERROR] "
                    f"{exc}"
                )

        messages = bus.consume(
            stream=
                Settings.FIREWALL_EVENTS_STREAM,
            group="telegram-firewall",
            consumer=consumer,
            count=20,
            block_ms=500,
            group_start_id="$",
        )

        for message_id, payload in messages:
            try:
                message = (
                    format_firewall_event(
                        telegram,
                        payload,
                    )
                )

                if message:
                    telegram.send(
                        message
                    )

                bus.ack(
                    Settings.FIREWALL_EVENTS_STREAM,
                    "telegram-firewall",
                    message_id,
                )

            except Exception as exc:
                print(
                    f"[TELEGRAM ERROR] "
                    f"{exc}"
                )


def commands_loop(
    telegram,
    commands,
):
    offset = None

    while True:
        updates = telegram.get_updates(
            offset
        )

        for update in updates:
            offset = (
                update[
                    "update_id"
                ]
                + 1
            )

            try:
                if "callback_query" in update:
                    commands.callback(
                        update
                    )

                elif "message" in update:
                    commands.message(
                        update
                    )

            except Exception as exc:
                print(
                    f"[COMMAND ERROR] "
                    f"{exc}"
                )


def main():
    bus = RedisBus()
    telegram = TelegramClient()

    consumer = (
        f"{socket.gethostname()}-"
        f"{os.getpid()}"
    )

    print(
        "SSH Guardian - Telegram Service"
    )

    print(
        f"Redis : {bus.ping()}"
    )

    print(
        f"Telegram actif : "
        f"{telegram.configured()}"
    )

    commands = TelegramCommands(
        bus,
        telegram,
    )

    threading.Thread(
        target=commands_loop,
        args=(
            telegram,
            commands,
        ),
        daemon=True,
    ).start()

    try:
        notifications(
            bus,
            telegram,
            consumer,
        )

    except KeyboardInterrupt:
        print(
            "\nTelegram Service arrêté."
        )


if __name__ == "__main__":
    main()
