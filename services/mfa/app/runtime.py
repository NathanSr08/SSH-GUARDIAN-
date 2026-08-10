import json
import time

from shared.config.settings import Settings


class MFARuntime:
    ENABLED_KEY = "mfa:runtime:enabled"
    TIMEOUT_KEY = "mfa:runtime:timeout"
    BYPASS_PREFIX = "mfa:bypass:ip:"

    MIN_TIMEOUT = 10
    MAX_TIMEOUT = 300

    def __init__(
        self,
        redis_client,
    ):
        self.redis = redis_client

    # ==========================================================
    # MFA ON / OFF
    # ==========================================================

    def enabled(self):
        value = self.redis.get(
            self.ENABLED_KEY
        )

        if value is None:
            return bool(
                Settings.MFA_ENABLED
            )

        if isinstance(
            value,
            bytes,
        ):
            value = value.decode(
                "utf-8"
            )

        return str(value).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def set_enabled(
        self,
        enabled,
    ):
        self.redis.set(
            self.ENABLED_KEY,
            "1" if enabled else "0",
        )

        return self.enabled()

    # ==========================================================
    # TIMEOUT
    # ==========================================================

    def timeout_seconds(self):
        value = self.redis.get(
            self.TIMEOUT_KEY
        )

        if value is None:
            return int(
                Settings.MFA_TIMEOUT_SECONDS
            )

        try:
            return int(value)
        except Exception:
            return int(
                Settings.MFA_TIMEOUT_SECONDS
            )

    def set_timeout(
        self,
        seconds,
    ):
        seconds = int(seconds)

        if seconds < self.MIN_TIMEOUT:
            raise ValueError(
                f"Timeout minimum : "
                f"{self.MIN_TIMEOUT} secondes"
            )

        if seconds > self.MAX_TIMEOUT:
            raise ValueError(
                f"Timeout maximum : "
                f"{self.MAX_TIMEOUT} secondes"
            )

        self.redis.set(
            self.TIMEOUT_KEY,
            seconds,
        )

        return seconds

    # ==========================================================
    # BYPASS TEMPORAIRE
    # ==========================================================

    def bypass_key(
        self,
        ip,
    ):
        return (
            f"{self.BYPASS_PREFIX}"
            f"{ip}"
        )

    def allow_ip(
        self,
        ip,
        seconds=3600,
        source="unknown",
    ):
        seconds = int(seconds)

        if seconds < 1:
            raise ValueError(
                "Durée invalide"
            )

        #
        # Limite de sécurité :
        # maximum 7 jours.
        #
        if seconds > 604800:
            raise ValueError(
                "Durée maximum : 7 jours"
            )

        payload = {
            "ip": ip,
            "source": source,
            "created_at": int(
                time.time()
            ),
            "duration": seconds,
        }

        self.redis.set(
            self.bypass_key(ip),
            json.dumps(payload),
            ex=seconds,
        )

        return self.bypass_info(
            ip
        )

    def revoke_ip(
        self,
        ip,
    ):
        return bool(
            self.redis.delete(
                self.bypass_key(ip)
            )
        )

    def is_ip_allowed(
        self,
        ip,
    ):
        if not ip:
            return False

        return bool(
            self.redis.exists(
                self.bypass_key(ip)
            )
        )

    def bypass_info(
        self,
        ip,
    ):
        key = self.bypass_key(
            ip
        )

        raw = self.redis.get(
            key
        )

        if not raw:
            return None

        if isinstance(
            raw,
            bytes,
        ):
            raw = raw.decode(
                "utf-8"
            )

        try:
            data = json.loads(
                raw
            )
        except Exception:
            data = {
                "ip": ip,
            }

        ttl = self.redis.ttl(
            key
        )

        data["ttl"] = max(
            int(ttl),
            0,
        )

        return data

    def list_bypasses(self):
        result = []

        for key in self.redis.scan_iter(
            match=(
                f"{self.BYPASS_PREFIX}*"
            )
        ):
            if isinstance(
                key,
                bytes,
            ):
                key = key.decode(
                    "utf-8"
                )

            ip = key[
                len(
                    self.BYPASS_PREFIX
                ):
            ]

            info = self.bypass_info(
                ip
            )

            if info:
                result.append(
                    info
                )

        result.sort(
            key=lambda item:
                item.get(
                    "ttl",
                    0,
                ),
            reverse=True,
        )

        return result

    # ==========================================================
    # STATUS GLOBAL
    # ==========================================================

    def status(self):
        return {
            "enabled":
                self.enabled(),

            "timeout_seconds":
                self.timeout_seconds(),

            "fail_mode":
                Settings.MFA_FAIL_MODE,

            "temporary_bypasses":
                self.list_bypasses(),
        }
