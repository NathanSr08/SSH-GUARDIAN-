import json
import os
import socket

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings

from services.mfa.app.service import (
    MFAService,
)

from services.mfa.app.runtime import (
    MFARuntime,
)


def reply(
    bus,
    request_id,
    payload,
):
    if not request_id:
        return

    key = (
        f"mfa.reply:"
        f"{request_id}"
    )

    bus.client.rpush(
        key,
        json.dumps(payload),
    )

    bus.client.expire(
        key,
        30,
    )


def main():
    bus = RedisBus()

    service = MFAService(
        bus
    )

    runtime = MFARuntime(
        bus.client
    )

    stream = (
        Settings.MFA_COMMANDS_STREAM
    )

    group = "mfa"

    consumer = (
        f"{socket.gethostname()}-"
        f"{os.getpid()}"
    )

    print(
        "SSH Guardian - MFA Service"
    )

    print(
        f"Redis : {bus.ping()}"
    )

    print(
        f"Lecture : {stream}"
    )

    print(
        f"Publication : "
        f"{Settings.MFA_EVENTS_STREAM}"
    )

    print(
        f"MFA runtime : "
        f"{runtime.enabled()}"
    )

    while True:
        messages = bus.consume(
            stream=stream,
            group=group,
            consumer=consumer,
            count=20,
            block_ms=5000,
            group_start_id="$",
        )

        for message_id, payload in messages:
            request_id = payload.get(
                "request_id"
            )

            command = payload.get(
                "command"
            )

            try:

                if command == "create":
                    service.manager.timeout_seconds = (
                        runtime.timeout_seconds()
                    )

                    result = (
                        service.create(
                            username=payload[
                                "username"
                            ],
                            ip=payload[
                                "ip"
                            ],
                            country=payload.get(
                                "country"
                            ),
                            country_code=(
                                payload.get(
                                    "country_code"
                                )
                            ),
                            city=payload.get(
                                "city"
                            ),
                            isp=payload.get(
                                "isp"
                            ),
                        ).to_dict()
                    )

                elif command == "approve":
                    result = (
                        service.approve(
                            payload[
                                "mfa_request_id"
                            ],
                            source=(
                                payload.get(
                                    "source"
                                )
                                or "unknown"
                            ),
                        ).to_dict()
                    )

                elif command == "approve_temporary":
                    request = (
                        service.approve(
                            payload[
                                "mfa_request_id"
                            ],
                            source=(
                                payload.get(
                                    "source"
                                )
                                or "unknown"
                            ),
                        )
                    )

                    duration = int(
                        payload.get(
                            "duration",
                            3600,
                        )
                    )

                    bypass = (
                        runtime.allow_ip(
                            request.ip,
                            duration,
                            source=(
                                payload.get(
                                    "source"
                                )
                                or "unknown"
                            ),
                        )
                    )

                    result = (
                        request.to_dict()
                    )

                    result[
                        "temporary_bypass"
                    ] = bypass

                elif command == "deny":
                    result = (
                        service.deny(
                            payload[
                                "mfa_request_id"
                            ],
                            source=(
                                payload.get(
                                    "source"
                                )
                                or "unknown"
                            ),
                        ).to_dict()
                    )

                elif command == "get":
                    result = (
                        service.get(
                            payload[
                                "mfa_request_id"
                            ]
                        ).to_dict()
                    )

                elif command == "requests":
                    status = payload.get(
                        "status"
                    )

                    limit = int(
                        payload.get(
                            "limit",
                            100,
                        )
                    )

                    result = [
                        request.to_dict()
                        for request
                        in service.manager.list_requests(
                            status=status,
                            limit=limit,
                        )
                    ]

                elif command == "status":
                    result = (
                        runtime.status()
                    )

                elif command == "set_timeout":
                    timeout = (
                        runtime.set_timeout(
                            payload.get(
                                "timeout_seconds"
                            )
                        )
                    )

                    result = (
                        runtime.status()
                    )

                    result[
                        "timeout_seconds"
                    ] = timeout

                elif command == "enable":
                    runtime.set_enabled(
                        True
                    )

                    result = (
                        runtime.status()
                    )

                elif command == "disable":
                    runtime.set_enabled(
                        False
                    )

                    result = (
                        runtime.status()
                    )

                elif command == "allow_ip":
                    ip = str(
                        payload.get(
                            "ip",
                            "",
                        )
                    ).strip()

                    if not ip:
                        raise ValueError(
                            "IP manquante"
                        )

                    duration = int(
                        payload.get(
                            "duration",
                            3600,
                        )
                    )

                    result = (
                        runtime.allow_ip(
                            ip,
                            duration,
                            source=(
                                payload.get(
                                    "source"
                                )
                                or "unknown"
                            ),
                        )
                    )

                elif command == "revoke_ip":
                    ip = str(
                        payload.get(
                            "ip",
                            "",
                        )
                    ).strip()

                    if not ip:
                        raise ValueError(
                            "IP manquante"
                        )

                    result = {
                        "ip": ip,
                        "revoked":
                            runtime.revoke_ip(
                                ip
                            ),
                    }

                else:
                    raise ValueError(
                        "Commande MFA inconnue"
                    )

                reply(
                    bus,
                    request_id,
                    {
                        "ok": True,
                        "result": result,
                    },
                )

                print(
                    f"[MFA] "
                    f"command={command} "
                    f"ok=true"
                )

            except Exception as exc:
                reply(
                    bus,
                    request_id,
                    {
                        "ok": False,
                        "error": str(exc),
                    },
                )

                print(
                    f"[MFA ERROR] "
                    f"command={command} "
                    f"{exc}"
                )

            bus.ack(
                stream,
                group,
                message_id,
            )


if __name__ == "__main__":
    main()
