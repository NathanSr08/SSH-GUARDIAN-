import os
import socket

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings

from services.storage.app.repository import (
    StorageRepository,
)


def process_stream(
    bus,
    stream,
    group,
    consumer,
    saver,
):
    messages = bus.consume(
        stream=stream,
        group=group,
        consumer=consumer,
        count=100,
        block_ms=250,
    )

    for message_id, payload in messages:
        try:
            saver(
                message_id,
                payload,
            )

            bus.ack(
                stream,
                group,
                message_id,
            )

            print(
                f"[STORE] "
                f"stream={stream} "
                f"id={message_id}"
            )

        except Exception as exc:
            print(
                f"[STORAGE ERROR] "
                f"{stream} "
                f"{message_id} "
                f"{exc}"
            )


def main():
    bus = RedisBus()
    repository = StorageRepository()

    consumer = (
        f"{socket.gethostname()}-"
        f"{os.getpid()}"
    )

    print(
        "SSH Guardian - Storage Service"
    )
    print(f"Redis : {bus.ping()}")

    try:
        while True:

            process_stream(
                bus,
                Settings.SSH_EVENTS_STREAM,
                "storage-ssh",
                consumer,
                repository.save_ssh_event,
            )

            process_stream(
                bus,
                Settings.SSH_ENRICHED_STREAM,
                "storage-enriched",
                consumer,
                repository.save_enriched_event,
            )

            process_stream(
                bus,
                Settings.SECURITY_ACTIONS_STREAM,
                "storage-security",
                consumer,
                repository.save_security_action,
            )

            process_stream(
                bus,
                Settings.FIREWALL_EVENTS_STREAM,
                "storage-firewall",
                consumer,
                repository.save_firewall_event,
            )

    except KeyboardInterrupt:
        print(
            "\nStorage Service arrêté."
        )


if __name__ == "__main__":
    main()
