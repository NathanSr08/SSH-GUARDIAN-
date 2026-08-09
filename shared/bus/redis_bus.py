import json

import redis

from shared.config.settings import Settings


class RedisBus:
    def __init__(self):
        self.client = redis.Redis.from_url(
            Settings.REDIS_URL,
            decode_responses=True,
        )

    def ping(self) -> bool:
        return bool(self.client.ping())

    def publish(self, stream: str, payload: dict) -> str:
        return self.client.xadd(
            stream,
            {
                "data": json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            },
            maxlen=100000,
            approximate=True,
        )

    def ensure_group(
        self,
        stream: str,
        group: str,
        start_id: str = "0",
    ) -> None:
        try:
            self.client.xgroup_create(
                stream,
                group,
                id=start_id,
                mkstream=True,
            )

        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block_ms: int = 5000,
        group_start_id: str = "0",
    ):
        self.ensure_group(
            stream,
            group,
            start_id=group_start_id,
        )

        response = self.client.xreadgroup(
            group,
            consumer,
            {stream: ">"},
            count=count,
            block=block_ms,
        )

        messages = []

        for _, entries in response:
            for message_id, fields in entries:
                raw = fields.get("data")

                if raw is None:
                    self.ack(
                        stream,
                        group,
                        message_id,
                    )
                    continue

                try:
                    payload = json.loads(raw)

                except json.JSONDecodeError:
                    self.ack(
                        stream,
                        group,
                        message_id,
                    )
                    continue

                messages.append(
                    (
                        message_id,
                        payload,
                    )
                )

        return messages

    def ack(
        self,
        stream: str,
        group: str,
        message_id: str,
    ) -> None:
        self.client.xack(
            stream,
            group,
            message_id,
        )
