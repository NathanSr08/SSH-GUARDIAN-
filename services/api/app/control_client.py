import json
import uuid

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings


class ControlClient:
    def __init__(self):
        self.bus = RedisBus()

    def execute(
        self,
        command: str,
        args=None,
        timeout: int = 10,
    ):
        request_id = str(uuid.uuid4())

        reply_key = (
            f"control.reply:{request_id}"
        )

        self.bus.publish(
            Settings.CONTROL_COMMANDS_STREAM,
            {
                "request_id": request_id,
                "command": command,
                "args": args or [],
            },
        )

        response = self.bus.client.blpop(
            reply_key,
            timeout=timeout,
        )

        if not response:
            raise TimeoutError(
                f"Control timeout: {command}"
            )

        payload = json.loads(
            response[1]
        )

        if not payload.get("ok"):
            raise RuntimeError(
                payload.get(
                    "error",
                    "Control error",
                )
            )

        return payload.get("result")
