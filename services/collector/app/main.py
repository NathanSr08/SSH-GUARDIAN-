from services.collector.app.journal_reader import read_ssh_logs
from services.collector.app.parser import parse_ssh_line

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings


def main() -> None:
    bus = RedisBus()

    print("SSH Guardian - Collector")
    print(f"Redis : {bus.ping()}")
    print(f"Stream : {Settings.SSH_EVENTS_STREAM}")
    print("En attente des logs SSH...")

    try:
        for line in read_ssh_logs():
            event = parse_ssh_line(line)

            if event is None:
                continue

            event_id = bus.publish(
                Settings.SSH_EVENTS_STREAM,
                event.to_dict(),
            )

            print(
                f"[PUBLISH] "
                f"id={event_id} "
                f"type={event.event_type} "
                f"ip={event.ip}"
            )

    except KeyboardInterrupt:
        print("\nCollector arrêté.")


if __name__ == "__main__":
    main()
