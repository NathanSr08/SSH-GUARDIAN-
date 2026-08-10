import json
import secrets

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings


class MFAClient:
    def __init__(self):
        self.bus = RedisBus()

    def execute(
        self,
        command,
        payload=None,
        timeout=10,
    ):
        payload = dict(payload or {})

        request_id = secrets.token_urlsafe(18)

        payload["request_id"] = request_id
        payload["command"] = command

        reply_key = f"mfa.reply:{request_id}"

        # Nettoyage préventif
        self.bus.client.delete(reply_key)

        self.bus.publish(
            Settings.MFA_COMMANDS_STREAM,
            payload,
        )

        result = self.bus.client.blpop(
            reply_key,
            timeout=timeout,
        )

        if not result:
            raise RuntimeError(
                "Le service MFA ne répond pas."
            )

        _, raw = result

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        response = json.loads(raw)

        if not response.get("ok"):
            raise RuntimeError(
                response.get("error")
                or "Erreur MFA inconnue"
            )

        return response.get("result")
