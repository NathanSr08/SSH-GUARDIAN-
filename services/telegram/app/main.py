import os
import socket
import threading

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


def mfa_notifications(
    bus,
    telegram,
    consumer,
):
    while True:
        messages = bus.consume(
            stream=Settings.MFA_EVENTS_STREAM,
            group="telegram-mfa",
            consumer=consumer,
            count=20,
            block_ms=1000,
            group_start_id="$",
        )

        for message_id, payload in messages:
            try:
                event_type = payload.get(
                    "event_type"
                )

                #
                # Seules les nouvelles demandes
                # doivent créer un message Telegram.
                #
                if event_type != "mfa.request.created":
                    bus.ack(
                        Settings.MFA_EVENTS_STREAM,
                        "telegram-mfa",
                        message_id,
                    )
                    continue

                request_id = str(
                    payload.get(
                        "request_id",
                        "",
                    )
                )

                username = telegram.escape(
                    payload.get(
                        "username"
                    )
                )

                ip = telegram.escape(
                    payload.get(
                        "ip"
                    )
                )

                country = telegram.escape(
                    payload.get(
                        "country"
                    )
                )

                city = telegram.escape(
                    payload.get(
                        "city"
                    )
                )

                isp = telegram.escape(
                    payload.get(
                        "isp"
                    )
                )

                text = (
                    "🔐 <b>AUTORISATION SSH</b>\n\n"
                    f"👤 Utilisateur : "
                    f"<code>{username}</code>\n"
                    f"🌐 IP : "
                    f"<code>{ip}</code>\n"
                    f"📍 Localisation : "
                    f"{city}, {country}\n"
                    f"🏢 FAI : {isp}\n\n"
                    f"⏳ Expire dans "
                    f"{Settings.MFA_TIMEOUT_SECONDS} secondes."
                )

                keyboard = {
                    "inline_keyboard": [
                        [
                            {
                                "text":
                                    "✅ Autoriser",
                                "callback_data":
                                    f"mfa_approve:{request_id}",
                            },
                            {
                                "text":
                                    "❌ Refuser",
                                "callback_data":
                                    f"mfa_deny:{request_id}",
                            },
                        ],
                        [
                            {
                                "text":
                                    "⏱ Autoriser 1 heure",
                                "callback_data":
                                    f"mfa_1h:{request_id}",
                            },
                        ]
                    ]
                }

                telegram.send(
                    text,
                    reply_markup=keyboard,
                )

                bus.ack(
                    Settings.MFA_EVENTS_STREAM,
                    "telegram-mfa",
                    message_id,
                )

            except Exception as exc:
                print(
                    "[TELEGRAM MFA ERROR] "
                    f"{exc}"
                )


def notifications(
    bus,
    telegram,
    consumer,
):
    while True:

        messages = bus.consume(
            stream=Settings.SSH_ENRICHED_STREAM,
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
            stream=Settings.FIREWALL_EVENTS_STREAM,
            group="telegram-firewall",
            consumer=consumer,
            count=20,
            block_ms=500,
            group_start_id="$",
        )

        for message_id, payload in messages:
            try:
                #
                # Une action lancée depuis Telegram
                # a déjà sa réponse RPC.
                #
                if (
                    payload.get("source")
                    == "telegram"
                ):
                    bus.ack(
                        Settings.FIREWALL_EVENTS_STREAM,
                        "telegram-firewall",
                        message_id,
                    )
                    continue

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

    #
    # MFA notifications
    #
    threading.Thread(
        target=mfa_notifications,
        args=(
            bus,
            telegram,
            consumer,
        ),
        daemon=True,
    ).start()

    #
    # Telegram commands + callbacks
    #
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
