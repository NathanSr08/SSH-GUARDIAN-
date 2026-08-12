import json

import pytest
import redis

from shared.bus.redis_bus import RedisBus


class FakeRedisClient:
    def __init__(self):
        self.calls = []
        self.read_response = []
        self.group_error = None

    def ping(self):
        return True

    def xadd(
        self,
        stream,
        fields,
        **kwargs,
    ):
        self.calls.append(
            (
                "xadd",
                stream,
                fields,
                kwargs,
            )
        )

        return "1-0"

    def xgroup_create(
        self,
        stream,
        group,
        **kwargs,
    ):
        self.calls.append(
            (
                "xgroup_create",
                stream,
                group,
                kwargs,
            )
        )

        if self.group_error:
            raise self.group_error

        return True

    def xreadgroup(
        self,
        group,
        consumer,
        streams,
        **kwargs,
    ):
        self.calls.append(
            (
                "xreadgroup",
                group,
                consumer,
                streams,
                kwargs,
            )
        )

        return self.read_response

    def xack(
        self,
        stream,
        group,
        message_id,
    ):
        self.calls.append(
            (
                "xack",
                stream,
                group,
                message_id,
            )
        )

        return 1


def make_bus(client=None):
    bus = object.__new__(
        RedisBus
    )

    bus.client = (
        client
        or FakeRedisClient()
    )

    return bus


def test_ping():
    assert make_bus().ping() is True


def test_publish_serializes_json():
    client = FakeRedisClient()
    bus = make_bus(client)

    event_id = bus.publish(
        "test.events",
        {
            "name": "é",
            "value": 1,
        },
    )

    assert event_id == "1-0"

    call = client.calls[0]

    assert call[0] == "xadd"
    assert call[1] == "test.events"

    payload = json.loads(
        call[2]["data"]
    )

    assert payload == {
        "name": "é",
        "value": 1,
    }


def test_ensure_group_success():
    client = FakeRedisClient()
    bus = make_bus(client)

    bus.ensure_group(
        "stream",
        "group",
        start_id="$",
    )

    assert (
        client.calls[0][0]
        == "xgroup_create"
    )


def test_busygroup_is_ignored():
    client = FakeRedisClient()

    client.group_error = (
        redis.ResponseError(
            "BUSYGROUP Consumer Group name already exists"
        )
    )

    bus = make_bus(client)

    bus.ensure_group(
        "stream",
        "group",
    )


def test_non_busygroup_error_is_raised():
    client = FakeRedisClient()

    client.group_error = (
        redis.ResponseError(
            "OTHER ERROR"
        )
    )

    bus = make_bus(client)

    with pytest.raises(
        redis.ResponseError
    ):
        bus.ensure_group(
            "stream",
            "group",
        )


def test_consume_valid_message():
    client = FakeRedisClient()

    client.read_response = [
        (
            "stream",
            [
                (
                    "1-0",
                    {
                        "data":
                            json.dumps(
                                {
                                    "ok": True,
                                }
                            )
                    },
                )
            ],
        )
    ]

    bus = make_bus(client)

    messages = bus.consume(
        "stream",
        "group",
        "consumer",
    )

    assert messages == [
        (
            "1-0",
            {
                "ok": True,
            },
        )
    ]


def test_consume_missing_data_is_acked():
    client = FakeRedisClient()

    client.read_response = [
        (
            "stream",
            [
                (
                    "1-0",
                    {},
                )
            ],
        )
    ]

    bus = make_bus(client)

    assert (
        bus.consume(
            "stream",
            "group",
            "consumer",
        )
        == []
    )

    assert any(
        call[0] == "xack"
        for call
        in client.calls
    )


def test_consume_invalid_json_is_acked():
    client = FakeRedisClient()

    client.read_response = [
        (
            "stream",
            [
                (
                    "1-0",
                    {
                        "data":
                            "{broken-json"
                    },
                )
            ],
        )
    ]

    bus = make_bus(client)

    assert (
        bus.consume(
            "stream",
            "group",
            "consumer",
        )
        == []
    )

    assert any(
        call[0] == "xack"
        for call
        in client.calls
    )


def test_ack_calls_xack():
    client = FakeRedisClient()

    bus = make_bus(client)

    bus.ack(
        "stream",
        "group",
        "1-0",
    )

    assert (
        "xack",
        "stream",
        "group",
        "1-0",
    ) in client.calls
