import json
import sqlite3

from shared.config.settings import Settings


class APIRepository:
    def connect(self):
        conn = sqlite3.connect(
            Settings.DB_PATH
        )

        conn.row_factory = sqlite3.Row
        return conn

    def stats(self):
        with self.connect() as conn:

            def count(query, params=()):
                return conn.execute(
                    query,
                    params,
                ).fetchone()[0]

            return {
                "events": count(
                    """
                    SELECT COUNT(*)
                    FROM enriched_events
                    """
                ),

                "connections": count(
                    """
                    SELECT COUNT(*)
                    FROM enriched_events
                    WHERE event_type = 'ssh.connection.opened'
                    """
                ),

                "failed": count(
                    """
                    SELECT COUNT(*)
                    FROM enriched_events
                    WHERE event_type IN (
                        'ssh.login.failed',
                        'ssh.login.invalid_user'
                    )
                    """
                ),

                "success": count(
                    """
                    SELECT COUNT(*)
                    FROM enriched_events
                    WHERE event_type = 'ssh.login.success'
                    """
                ),

                "unique_ips": count(
                    """
                    SELECT COUNT(DISTINCT ip)
                    FROM enriched_events
                    """
                ),

                "bans": count(
                    """
                    SELECT COUNT(*)
                    FROM firewall_events
                    WHERE event_type = 'firewall.ip.banned'
                    """
                ),
            }

    def events(
        self,
        limit=100,
        ip=None,
    ):
        query = """
            SELECT
                id,
                event_type,
                ip,
                username,
                country,
                country_code,
                city,
                isp,
                timestamp
            FROM enriched_events
        """

        params = []

        if ip:
            query += " WHERE ip = ?"
            params.append(ip)

        query += """
            ORDER BY id DESC
            LIMIT ?
        """

        params.append(limit)

        with self.connect() as conn:
            rows = conn.execute(
                query,
                params,
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def firewall_history(
        self,
        limit=100,
    ):
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    redis_id,
                    event_type,
                    ip,
                    reason,
                    payload,
                    created_at
                FROM firewall_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        results = []

        for row in rows:
            item = dict(row)

            try:
                item["details"] = json.loads(
                    item.pop("payload")
                )
            except Exception:
                item["details"] = {}

            results.append(item)

        return results

    def active_bans(self):
        history = self.firewall_history(
            5000
        )

        latest = {}

        for event in history:
            ip = event.get("ip")

            if not ip:
                continue

            if ip not in latest:
                latest[ip] = event

        return [
            event
            for event in latest.values()
            if event.get("event_type")
            == "firewall.ip.banned"
        ]

    def top_ips(
        self,
        limit=20,
    ):
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    ip,
                    MAX(country) AS country,
                    MAX(country_code) AS country_code,
                    MAX(city) AS city,
                    MAX(isp) AS isp,
                    COUNT(*) AS attempts
                FROM enriched_events
                WHERE event_type IN (
                    'ssh.login.failed',
                    'ssh.login.invalid_user',
                    'ssh.connection.closed',
                    'ssh.connection.reset'
                )
                GROUP BY ip
                ORDER BY attempts DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    def top_countries(
        self,
        limit=20,
    ):
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(
                        country,
                        'Unknown'
                    ) AS country,

                    country_code,

                    COUNT(*) AS attempts

                FROM enriched_events

                WHERE event_type IN (
                    'ssh.login.failed',
                    'ssh.login.invalid_user',
                    'ssh.connection.closed',
                    'ssh.connection.reset'
                )

                GROUP BY
                    country,
                    country_code

                ORDER BY attempts DESC

                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]
