import json
import os
import socket

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings

from services.control.app.manager import ControlManager
from services.control.app.session_manager import SessionManager
from services.control.app.session_stream import SessionStreamManager
from services.control.app.country_manager import CountryManager


def main():
    bus = RedisBus()

    manager = ControlManager()
    sessions = SessionManager()
    countries = CountryManager(
        bus,
        manager,
    )

    streams = SessionStreamManager(
        bus.client
    )

    stream_name = (
        Settings.CONTROL_COMMANDS_STREAM
    )

    group = "control"

    consumer = (
        f"{socket.gethostname()}-"
        f"{os.getpid()}"
    )

    print("SSH Guardian - Control Service")
    print(f"Redis : {bus.ping()}")

    def reply(
        request_id,
        payload,
    ):
        key = (
            f"control.reply:{request_id}"
        )

        bus.client.rpush(
            key,
            json.dumps(
                payload,
                ensure_ascii=False,
            ),
        )

        bus.client.expire(
            key,
            60,
        )

    def execute(
        command,
        args,
        source="unknown",
    ):
        if command == "stats":
            return manager.stats()

        if command == "top":
            return manager.top()

        if command == "topcountries":
            return manager.topcountries()

        if command == "search":
            return manager.search(
                args[0]
            )

        if command == "bans":
            return manager.bans()

        if command == "unban":
            return manager.unban(
                args[0]
            )

        if command == "sessions":
            return sessions.sessions()

        if command == "active":
            return sessions.active()

        if command == "killsession":
            return sessions.kill(
                args[0]
            )

        if command == "killallsessions":
            return sessions.kill_all()

        if command == "stream_start":
            lines = (
                int(args[1])
                if len(args) > 1
                else 15
            )

            return streams.start(
                args[0],
                lines,
            )

        if command == "stream_get":
            return streams.get(
                args[0]
            )

        if command == "stream_stop":
            return streams.stop(
                args[0]
            )

        if command == "block":
            return countries.block(
                args[0],
                source=source,
            )

        if command == "unblock":
            return countries.unblock(
                args[0],
                source=source,
            )

        if command == "countries":
            return countries.countries()

        return "❌ Commande inconnue."

    while True:
        messages = bus.consume(
            stream=stream_name,
            group=group,
            consumer=consumer,
            count=20,
            block_ms=5000,
        )

        for message_id, payload in messages:
            request_id = payload.get(
                "request_id"
            )

            command = payload.get(
                "command"
            )

            args = (
                payload.get("args")
                or []
            )

            source = (
                payload.get("source")
                or "unknown"
            )

            try:
                result = execute(
                    command,
                    args,
                    source=source,
                )

                reply(
                    request_id,
                    {
                        "ok": True,
                        "result": result,
                    },
                )

                print(
                    f"[CONTROL] "
                    f"{command} {args}"
                )

            except Exception as exc:
                reply(
                    request_id,
                    {
                        "ok": False,
                        "error": str(exc),
                    },
                )

                print(
                    f"[CONTROL ERROR] "
                    f"{command}: {exc}"
                )

            bus.ack(
                stream_name,
                group,
                message_id,
            )


if __name__ == "__main__":
    main()
