import html
import json
import threading
import time
import uuid

from shared.config.settings import Settings


HELP = """
📜 <b>Commandes SSH-Guardian</b>

📊 /stats
🏆 /top
🌍 /topcountries
🔍 /search &lt;ip&gt;

🚫 /bans
🔓 /unban &lt;ip&gt;

💻 /sessions
📡 /active
📡 /stream &lt;id&gt; [lignes]

🔪 /killsession &lt;PID&gt;
⚡ /killallsessions

🛡 /block &lt;pays&gt;
🔓 /unblock &lt;pays&gt;
📜 /countries

❓ /help
"""


class TelegramCommands:
    def __init__(
        self,
        bus,
        telegram,
    ):
        self.bus = bus
        self.telegram = telegram

        self.active_streams = {}

    def rpc(
        self,
        command,
        args=None,
        timeout=10,
    ):
        args = args or []

        request_id = str(
            uuid.uuid4()
        )

        key = (
            f"control.reply:"
            f"{request_id}"
        )

        self.bus.publish(
            Settings.CONTROL_COMMANDS_STREAM,
            {
                "request_id":
                    request_id,
                "command":
                    command,
                "args":
                    args,
            },
        )

        result = (
            self.bus.client.blpop(
                key,
                timeout=timeout,
            )
        )

        if not result:
            return {
                "ok": False,
                "error":
                    "Control Service timeout",
            }

        return json.loads(
            result[1]
        )

    def send_rpc(
        self,
        command,
        args=None,
    ):
        response = self.rpc(
            command,
            args,
        )

        if not response.get(
            "ok"
        ):
            self.telegram.send(
                "❌ "
                + html.escape(
                    response.get(
                        "error",
                        "Erreur",
                    )
                )
            )

            return

        result = response.get(
            "result"
        )

        if isinstance(
            result,
            str,
        ):
            self.telegram.send(
                result
            )

    def start_stream(
        self,
        session_id,
        max_lines,
    ):
        response = self.rpc(
            "stream_start",
            [
                session_id,
                max_lines,
            ],
        )

        if not response.get("ok"):
            self.telegram.send(
                "❌ Impossible de démarrer le flux."
            )
            return

        result = response.get("result") or {}

        if not result.get("ok"):
            self.telegram.send(
                "❌ "
                + html.escape(
                    result.get(
                        "error",
                        "Erreur inconnue",
                    )
                )
            )
            return

        stream_id = result["stream_id"]

        mid = self.telegram.send(
            "📡 <b>Terminal SSH en direct</b>\n\n"
            f"🆔 Session : <code>{session_id}</code>\n"
            "⏳ Connexion au flux..."
        )

        if not mid:
            self.rpc(
                "stream_stop",
                [stream_id],
            )
            return

        self.active_streams[
            str(mid)
        ] = {
            "stream_id": stream_id,
            "session_id": str(session_id),
        }

        def worker():
            last_render = None

            try:
                while str(mid) in self.active_streams:
                    response = self.rpc(
                        "stream_get",
                        [stream_id],
                        timeout=5,
                    )

                    if not response.get("ok"):
                        break

                    result = (
                        response.get("result")
                        or {}
                    )

                    if not result.get("ok"):
                        break

                    content = result.get(
                        "content",
                        "(Attente...)",
                    )

                    alive = bool(
                        result.get("alive")
                    )

                    escaped = html.escape(
                        content[-3400:]
                    )

                    status = (
                        "🟢 LIVE"
                        if alive
                        else "⚫ TERMINÉE"
                    )

                    rendered = (
                        "📡 <b>TERMINAL SSH — LIVE</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━\n"
                        f"🆔 <code>{session_id}</code>\n"
                        f"📶 {status}\n"
                        "━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"<pre>{escaped}</pre>"
                    )

                    keyboard = {
                        "inline_keyboard": [
                            [
                                {
                                    "text":
                                        "⏹ Arrêter le flux",
                                    "callback_data":
                                        f"stopstream:{stream_id}",
                                },
                                {
                                    "text":
                                        "💥 Tuer la session",
                                    "callback_data":
                                        f"kill:{session_id}",
                                },
                            ]
                        ]
                    }

                    if rendered != last_render:
                        self.telegram.edit(
                            mid,
                            rendered,
                            reply_markup=(
                                keyboard
                                if alive
                                else None
                            ),
                        )

                        last_render = rendered

                    if not alive:
                        break

                    time.sleep(0.4)

            finally:
                self.active_streams.pop(
                    str(mid),
                    None,
                )

        threading.Thread(
            target=worker,
            daemon=True,
        ).start()

    def callback(
        self,
        update,
    ):
        cb = update["callback_query"]

        callback_id = cb["id"]
        data = cb.get("data", "")

        self.telegram.answer_callback(
            callback_id
        )

        message = cb.get(
            "message",
            {},
        )

        telegram_message_id = (
            message.get("message_id")
        )

        print(
            f"[CALLBACK] data={data} "
            f"message_id={telegram_message_id}"
        )

        if data.startswith(
            "stopstream:"
        ):
            stream_id = data.split(
                ":",
                1,
            )[1]

            response = self.rpc(
                "stream_stop",
                [stream_id],
                timeout=5,
            )

            # Supprimer ce flux de la boucle locale
            for key, value in list(
                self.active_streams.items()
            ):
                if isinstance(value, dict):
                    if (
                        value.get("stream_id")
                        == stream_id
                    ):
                        self.active_streams.pop(
                            key,
                            None,
                        )

            if telegram_message_id:
                self.telegram.edit(
                    telegram_message_id,
                    (
                        "⏹ <b>Flux SSH arrêté</b>\n\n"
                        "Le terminal n'est plus suivi.\n"
                        "La session SSH reste ouverte."
                    ),
                )

            print(
                f"[STREAM STOP] "
                f"id={stream_id} "
                f"response={response}"
            )

            return

        if data.startswith(
            "kill:"
        ):
            pid = data.split(
                ":",
                1,
            )[1]

            response = self.rpc(
                "killsession",
                [pid],
                timeout=5,
            )

            if response.get("ok"):
                result = response.get(
                    "result",
                    "Session terminée.",
                )

                self.telegram.send(
                    result
                )
            else:
                self.telegram.send(
                    "❌ Impossible de tuer la session."
                )

            if telegram_message_id:
                self.telegram.edit(
                    telegram_message_id,
                    (
                        "💥 <b>Session SSH terminée</b>\n\n"
                        f"PID : <code>{html.escape(pid)}</code>"
                    ),
                )

            return

    def message(
        self,
        update,
    ):
        message = update.get(
            "message",
            {},
        )

        chat_id = str(
            message.get(
                "chat",
                {},
            ).get(
                "id",
                "",
            )
        )

        if chat_id != str(
            self.telegram.chat_id
        ):
            return

        text = (
            message.get(
                "text",
                "",
            )
            .strip()
        )

        parts = text.split()

        if not parts:
            return

        command = (
            parts[0]
            .split(
                "@",
                1,
            )[0]
            .lower()
        )

        args = parts[1:]

        if command in {
            "/help",
            "/start",
        }:
            self.telegram.send(
                HELP
            )

        elif command == "/stats":
            self.send_rpc(
                "stats"
            )

        elif command == "/top":
            self.send_rpc(
                "top"
            )

        elif command in {
            "/topcountries",
            "/top-pays",
        }:
            self.send_rpc(
                "topcountries"
            )

        elif command == "/search":
            if not args:
                self.telegram.send(
                    "⚠️ /search &lt;ip&gt;"
                )
            else:
                self.send_rpc(
                    "search",
                    [args[0]],
                )

        elif command == "/bans":
            self.send_rpc(
                "bans"
            )

        elif command == "/unban":
            if not args:
                self.telegram.send(
                    "⚠️ /unban &lt;ip&gt;"
                )
            else:
                self.send_rpc(
                    "unban",
                    [args[0]],
                )

        elif command == "/sessions":
            self.send_rpc(
                "sessions"
            )

        elif command == "/active":
            self.send_rpc(
                "active"
            )

        elif command == "/stream":
            if not args:
                self.telegram.send(
                    "⚠️ /stream "
                    "&lt;id&gt; [lignes]"
                )

                return

            max_lines = 10

            if (
                len(args) > 1
                and args[1].isdigit()
            ):
                max_lines = min(
                    int(args[1]),
                    100,
                )

            self.start_stream(
                args[0],
                max_lines,
            )

        elif command == "/killsession":
            if not args:
                self.telegram.send(
                    "⚠️ /killsession "
                    "&lt;PID&gt;"
                )
            else:
                self.send_rpc(
                    "killsession",
                    [args[0]],
                )

        elif command in {
            "/killallsessions",
            "/kill-all-sessions",
        }:
            self.send_rpc(
                "killallsessions"
            )

        elif command == "/block":
            if not args:
                self.telegram.send(
                    "⚠️ /block "
                    "&lt;pays&gt;"
                )
            else:
                self.send_rpc(
                    "block",
                    [args[0]],
                )

        elif command == "/unblock":
            if not args:
                self.telegram.send(
                    "⚠️ /unblock "
                    "&lt;pays&gt;"
                )
            else:
                self.send_rpc(
                    "unblock",
                    [args[0]],
                )

        elif command == "/countries":
            self.send_rpc(
                "countries"
            )

        else:
            self.telegram.send(
                "❓ Commande inconnue.\n\n"
                + HELP
            )
