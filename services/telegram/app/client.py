import html

import requests

from shared.config.settings import Settings
from shared.bus.redis_bus import RedisBus


class TelegramClient:
    def __init__(self):
        self.bus = RedisBus()
        self.enabled = (
            Settings.TELEGRAM_ENABLED
        )

        self.token = (
            Settings.TELEGRAM_TOKEN
        )

        self.chat_id = str(
            Settings.TELEGRAM_CHAT_ID
        )

        self.base_url = (
            "https://api.telegram.org/"
            f"bot{self.token}"
        )

    def configured(self):
        return bool(
            self.enabled
            and self.token
            and self.chat_id
        )

    def escape(self, value) -> str:
        if value is None:
            return "Inconnu"

        return html.escape(
            str(value)
        )

    def send(
        self,
        text,
        reply_markup=None,
    ):
        if not self.configured():
            print(
                "[TELEGRAM DRY-RUN] "
                + text.replace(
                    "\n",
                    " | ",
                )
            )

            return None

        payload = {
            "chat_id":
                self.chat_id,
            "text":
                text,
            "parse_mode":
                "HTML",
        }

        if reply_markup:
            payload[
                "reply_markup"
            ] = reply_markup

        response = requests.post(
            f"{self.base_url}/sendMessage",
            json=payload,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("ok"):
            return data[
                "result"
            ][
                "message_id"
            ]

        raise RuntimeError(
            data.get(
                "description",
                "Telegram error",
            )
        )

    def edit(
        self,
        message_id,
        text,
        reply_markup=None,
    ):
        payload = {
            "chat_id":
                self.chat_id,
            "message_id":
                message_id,
            "text":
                text,
            "parse_mode":
                "HTML",
        }

        if reply_markup:
            payload[
                "reply_markup"
            ] = reply_markup

        try:
            response = requests.post(
                f"{self.base_url}/"
                "editMessageText",
                json=payload,
                timeout=10,
            )

            response.raise_for_status()

        except Exception as exc:
            print(
                f"[TELEGRAM EDIT ERROR] "
                f"{exc}"
            )

    def get_updates(
        self,
        offset=None,
    ):
        if not self.configured():
            return []

        try:
            response = requests.get(
                f"{self.base_url}/getUpdates",
                params={
                    "timeout": 25,
                    "offset": offset,
                },
                timeout=30,
            )

            response.raise_for_status()

            return (
                response.json()
                .get(
                    "result",
                    [],
                )
            )

        except Exception as exc:
            print(
                f"[TELEGRAM UPDATE ERROR] "
                f"{exc}"
            )

            return []

    def answer_callback(
        self,
        callback_id,
    ):
        try:
            requests.post(
                f"{self.base_url}/"
                "answerCallbackQuery",
                json={
                    "callback_query_id":
                        callback_id
                },
                timeout=5,
            )

        except Exception:
            pass
