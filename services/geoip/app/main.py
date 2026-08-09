import os
import socket

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings

from services.geoip.app.provider import GeoIPProvider


def main() -> None:
    bus = RedisBus()
    provider = GeoIPProvider(bus)

    stream = Settings.SSH_EVENTS_STREAM
    group = "geoip"

    consumer = (
        f"{socket.gethostname()}-"
        f"{os.getpid()}"
    )

    print("SSH Guardian - GeoIP Service")
    print(f"Redis : {bus.ping()}")
    print(f"Lecture : {stream}")
    print(
        f"Publication : "
        f"{Settings.SSH_ENRICHED_STREAM}"
    )

    try:
        while True:
            messages = bus.consume(
                stream=stream,
                group=group,
                consumer=consumer,
                count=50,
                block_ms=5000,
            )

            for message_id, payload in messages:
                try:
                    ip = payload.get("ip")

                    if not ip:
                        bus.ack(
                            stream,
                            group,
                            message_id,
                        )
                        continue

                    geo = provider.lookup(ip)

                    enriched = {
                        **payload,
                        "geo": geo,
                        "source_event_id": message_id,
                    }

                    enriched_id = bus.publish(
                        Settings.SSH_ENRICHED_STREAM,
                        enriched,
                    )

                    print(
                        f"[GEOIP] "
                        f"ip={ip} "
                        f"country={geo['country']} "
                        f"city={geo['city']} "
                        f"cache={geo.get('geo_cache')} "
                        f"id={enriched_id}"
                    )

                    bus.ack(
                        stream,
                        group,
                        message_id,
                    )

                except Exception as exc:
                    print(
                        f"[GEOIP ERROR] "
                        f"id={message_id} "
                        f"{type(exc).__name__}: {exc}"
                    )

    except KeyboardInterrupt:
        print("\nGeoIP Service arrêté.")


if __name__ == "__main__":
    main()
