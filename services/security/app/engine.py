from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from shared.config.settings import Settings
from shared.events.ssh import SSHEvent
from services.security.app.rules import SecurityRules


class SecurityEngine:
    def __init__(
        self,
        rules: SecurityRules | None = None,
    ):
        self.rules = rules or SecurityRules(
            max_attempts=Settings.MAX_ATTEMPTS,
            ban_duration_seconds=Settings.BAN_DURATION_SECONDS,
        )

        self.attempts: dict[str, deque[datetime]] = defaultdict(deque)
        self.banned_until: dict[str, datetime] = {}

    def process(
        self,
        event: SSHEvent,
    ) -> dict | None:

        #
        # On ne compte qu'une ouverture de connexion.
        #
        if event.event_type != "ssh.connection.opened":
            return None

        now = datetime.now(timezone.utc)

        attempts = self.attempts[event.ip]

        #
        # Nettoyage de la fenêtre temporelle.
        #
        while attempts:
            age = (
                now - attempts[0]
            ).total_seconds()

            if age <= self.rules.window_seconds:
                break

            attempts.popleft()

        #
        # Chaque nouvelle connexion = +1 tentative.
        #
        attempts.append(now)

        count = len(attempts)

        #
        # WHITELIST :
        # on compte, mais on ne bannit jamais.
        #
        if event.ip in Settings.WHITELIST:
            return {
                "action": "ignore",
                "reason": "whitelisted",
                "ip": event.ip,
                "attempts": count,
                "max_attempts":
                    self.rules.max_attempts,
                "remaining_attempts":
                    max(
                        self.rules.max_attempts - count,
                        0,
                    ),
                "whitelisted": True,
            }

        #
        # Déjà bannie.
        #
        banned_until = self.banned_until.get(
            event.ip
        )

        if banned_until is not None:
            if now < banned_until:
                return None

            self.banned_until.pop(
                event.ip,
                None,
            )

        #
        # Ban au seuil.
        #
        if count >= self.rules.max_attempts:
            expires_at = now + timedelta(
                seconds=self.rules.ban_duration_seconds
            )

            self.banned_until[
                event.ip
            ] = expires_at

            attempts.clear()

            return {
                "action": "ban_ip",
                "ip": event.ip,
                "reason":
                    "too_many_connection_attempts",
                "attempts": count,
                "max_attempts":
                    self.rules.max_attempts,
                "remaining_attempts": 0,
                "ban_duration_seconds":
                    self.rules.ban_duration_seconds,
                "expires_at":
                    expires_at.isoformat(),
            }

        return {
            "action": "monitor",
            "ip": event.ip,
            "reason": "connection_attempt",
            "attempts": count,
            "max_attempts":
                self.rules.max_attempts,
            "remaining_attempts":
                self.rules.max_attempts - count,
        }
