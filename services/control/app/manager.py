import glob
import ipaddress
import os
import re
import sqlite3
import subprocess

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings
from services.firewall.app.firewall import Firewall


DB_PATH = Settings.DB_PATH

COUNTRY_SCRIPT = str(Settings.COUNTRY_SCRIPT)

SESSION_LOG_DIR = str(Settings.SESSION_LOG_DIR)


COUNTRIES = {
    "russie": "ru",
    "russia": "ru",
    "chine": "cn",
    "china": "cn",
    "iran": "ir",
    "israel": "il",
    "france": "fr",
    "allemagne": "de",
    "germany": "de",
    "ukraine": "ua",
    "inde": "in",
    "india": "in",
    "usa": "us",
    "us": "us",
    "united-states": "us",
    "uk": "gb",
    "royaume-uni": "gb",
}


class ControlManager:
    def __init__(self):
        self.firewall = Firewall()
        self.bus = RedisBus()

    def db(self):
        return sqlite3.connect(
            DB_PATH
        )

    def stats(self):
        with self.db() as conn:

            failed = conn.execute(
                """
                SELECT COUNT(*)
                FROM enriched_events
                WHERE event_type IN (
                    'ssh.login.failed',
                    'ssh.login.invalid_user',
                    'ssh.connection.closed',
                    'ssh.connection.reset'
                )
                """
            ).fetchone()[0]

            success = conn.execute(
                """
                SELECT COUNT(*)
                FROM enriched_events
                WHERE event_type =
                    'ssh.login.success'
                """
            ).fetchone()[0]

            unique_ips = conn.execute(
                """
                SELECT COUNT(
                    DISTINCT ip
                )
                FROM enriched_events
                """
            ).fetchone()[0]

        return (
            "📊 <b>Statistiques SSH-Guardian</b>\n\n"
            f"❌ Échecs : <code>{failed}</code>\n"
            f"✅ Succès : <code>{success}</code>\n"
            f"🌐 IP uniques : "
            f"<code>{unique_ips}</code>"
        )

    def top(self):
        with self.db() as conn:
            rows = conn.execute(
                """
                SELECT
                    ip,
                    MAX(country),
                    MAX(city),
                    COUNT(*) AS total
                FROM enriched_events
                WHERE event_type IN (
                    'ssh.login.failed',
                    'ssh.login.invalid_user',
                    'ssh.connection.closed',
                    'ssh.connection.reset'
                )
                GROUP BY ip
                ORDER BY total DESC
                LIMIT 20
                """
            ).fetchall()

        if not rows:
            return (
                "📭 Aucune tentative "
                "enregistrée."
            )

        lines = [
            "🏆 <b>Top 20 IP attaquantes</b>",
            "",
        ]

        for i, row in enumerate(
            rows,
            1,
        ):
            ip, country, city, count = row

            location = (
                f"{city}, {country}"
                if city
                else country
            )

            lines.append(
                f"{i}. <code>{ip}</code> "
                f"({location or 'Inconnu'}) "
                f"— <b>{count}</b>"
            )

        return "\n".join(lines)

    def topcountries(self):
        with self.db() as conn:
            rows = conn.execute(
                """
                SELECT
                    COALESCE(
                        country,
                        'Inconnu'
                    ),
                    COUNT(*) AS total
                FROM enriched_events
                WHERE event_type IN (
                    'ssh.login.failed',
                    'ssh.login.invalid_user',
                    'ssh.connection.closed',
                    'ssh.connection.reset'
                )
                GROUP BY country
                ORDER BY total DESC
                LIMIT 20
                """
            ).fetchall()

        if not rows:
            return (
                "📭 Aucun pays "
                "enregistré."
            )

        lines = [
            "🌍 <b>Top pays attaquants</b>",
            "",
        ]

        for i, (
            country,
            count,
        ) in enumerate(
            rows,
            1,
        ):
            lines.append(
                f"{i}. {country} — "
                f"<b>{count}</b>"
            )

        return "\n".join(lines)

    def search(self, ip):
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return "❌ Adresse IP invalide."

        with self.db() as conn:
            rows = conn.execute(
                """
                SELECT
                    timestamp,
                    event_type,
                    username,
                    city,
                    country,
                    isp
                FROM enriched_events
                WHERE ip = ?
                ORDER BY id DESC
                LIMIT 20
                """,
                (ip,),
            ).fetchall()

        if not rows:
            return (
                f"🔍 Aucun historique pour "
                f"<code>{ip}</code>."
            )

        lines = [
            f"🔍 <b>Historique {ip}</b>",
            "",
        ]

        for row in rows:
            (
                timestamp,
                event_type,
                username,
                city,
                country,
                isp,
            ) = row

            icon = (
                "✅"
                if event_type
                == "ssh.login.success"
                else "❌"
            )

            lines.append(
                f"{icon} "
                f"{timestamp}\n"
                f"👤 {username or 'Inconnu'}\n"
                f"📍 {city or 'Inconnu'}, "
                f"{country or 'Inconnu'}\n"
                f"🏢 {isp or 'Inconnu'}\n"
            )

        return "\n".join(lines)

    def bans(self):
        with self.db() as conn:
            rows = conn.execute(
                """
                SELECT
                    ip,
                    reason,
                    created_at
                FROM firewall_events
                WHERE event_type =
                    'firewall.ip.banned'
                ORDER BY id DESC
                LIMIT 50
                """
            ).fetchall()

        if not rows:
            return (
                "✅ Aucun ban enregistré."
            )

        seen = set()

        lines = [
            "🚫 <b>Derniers bans</b>",
            "",
        ]

        for ip, reason, date in rows:

            if ip in seen:
                continue

            seen.add(ip)

            lines.append(
                f"• <code>{ip}</code>\n"
                f"  {reason or 'security'}\n"
                f"  {date}"
            )

        return "\n".join(lines)

    def unban(self, ip):
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return "❌ Adresse IP invalide."

        result = self.firewall.unban(ip)

        self.bus.publish(
            Settings.FIREWALL_EVENTS_STREAM,
            {
                "event_type":
                    "firewall.ip.unbanned",
                "ip": ip,
                "reason": "manual",
                "firewall_result": result,
            },
        )

        return (
            f"🔓 IP <code>{ip}</code> "
            f"débannie.\n"
            f"Firewall : "
            f"<code>{result['status']}</code>"
        )

    def sessions(self):
        result = subprocess.run(
            [
                "ss",
                "-tnp",
            ],
            capture_output=True,
            text=True,
        )

        lines = [
            line
            for line
            in result.stdout.splitlines()
            if "sshd" in line
        ]

        if not lines:
            return (
                "📭 Aucune session SSH "
                "active."
            )

        output = "\n".join(
            lines[:20]
        )

        return (
            "💻 <b>Sessions SSH</b>\n\n"
            f"<pre>{output}</pre>"
        )

    def active(self):
        files = glob.glob(
            f"{SESSION_LOG_DIR}/"
            "session_*.log"
        )

        files.sort(
            key=os.path.getmtime,
            reverse=True,
        )

        if not files:
            return (
                "📭 Aucune session "
                "enregistrée."
            )

        lines = [
            "📡 <b>Sessions enregistrées</b>",
            "",
        ]

        for path in files[:20]:
            name = os.path.basename(path)

            match = re.match(
                r"session_(\d+)_",
                name,
            )

            if not match:
                continue

            pid = match.group(1)

            alive = (
                subprocess.run(
                    [
                        "kill",
                        "-0",
                        pid,
                    ],
                    capture_output=True,
                ).returncode
                == 0
            )

            status = (
                "🟢 LIVE"
                if alive
                else "⚪ Terminée"
            )

            lines.append(
                f"• <code>{pid}</code> "
                f"— {status}"
            )

        return "\n".join(lines)

    def stream_snapshot(
        self,
        session_id,
        max_lines=10,
    ):
        if not str(
            session_id
        ).isdigit():
            return {
                "ok": False,
                "text":
                    "Session invalide.",
            }

        files = glob.glob(
            f"{SESSION_LOG_DIR}/"
            f"session_{session_id}_*.log"
        )

        if not files:
            return {
                "ok": False,
                "text":
                    "Session introuvable.",
            }

        path = files[0]

        try:
            text = open(
                path,
                "r",
                encoding="utf-8",
                errors="ignore",
            ).read()

        except Exception as exc:
            return {
                "ok": False,
                "text": str(exc),
            }

        ansi = re.compile(
            r"\x1B(?:"
            r"[@-Z\\-_]|"
            r"\[[0-?]*"
            r"[ -/]*[@-~])"
        )

        text = ansi.sub(
            "",
            text,
        ).replace(
            "\x00",
            "",
        )

        lines = [
            x.rstrip()
            for x
            in text.splitlines()
            if x.strip()
        ]

        display = "\n".join(
            lines[-int(max_lines):]
        )

        alive = (
            subprocess.run(
                [
                    "kill",
                    "-0",
                    str(session_id),
                ],
                capture_output=True,
            ).returncode
            == 0
        )

        return {
            "ok": True,
            "alive": alive,
            "session_id":
                str(session_id),
            "content":
                display
                or "(Attente...)",
        }

    def killsession(self, pid):
        if not str(pid).isdigit():
            return (
                "❌ PID invalide."
            )

        result = subprocess.run(
            [
                "kill",
                "-9",
                str(pid),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return (
                f"🛑 Session "
                f"<code>{pid}</code> "
                f"terminée."
            )

        return (
            f"❌ Impossible de tuer "
            f"<code>{pid}</code>."
        )

    def killallsessions(self):
        subprocess.run(
            [
                "pkill",
                "-9",
                "-f",
                "sshd-session",
            ],
            capture_output=True,
        )

        return (
            "⚡ Toutes les sessions SSH "
            "distantes ont été terminées."
        )

    def country_code(self, value):
        value = (
            value.strip()
            .lower()
        )

        if len(value) == 2:
            return value

        return COUNTRIES.get(
            value,
        )

    def country_action(
        self,
        action,
        country,
    ):
        code = self.country_code(
            country
        )

        if not code:
            return (
                "❌ Pays inconnu. "
                "Utilisez un code ISO "
                "comme fr, ru, cn..."
            )

        if not Settings.FIREWALL_ENABLED:
            return (
                "🧪 Firewall en DRY-RUN.\n"
                f"Action simulée : "
                f"<code>{action} "
                f"{code}</code>"
            )

        result = subprocess.run(
            [
                COUNTRY_SCRIPT,
                action,
                code,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return (
                "❌ Erreur firewall :\n"
                f"<pre>{result.stderr}</pre>"
            )

        if action == "block":
            return (
                f"🛡 Pays "
                f"<b>{code.upper()}</b> "
                f"bloqué."
            )

        return (
            f"🔓 Pays "
            f"<b>{code.upper()}</b> "
            f"débloqué."
        )

    def countries(self):
        result = subprocess.run(
            [
                COUNTRY_SCRIPT,
                "list",
            ],
            capture_output=True,
            text=True,
        )

        output = (
            result.stdout.strip()
        )

        if not output:
            return (
                "📜 Aucun pays bloqué."
            )

        return (
            "📜 <b>Pays bloqués</b>\n\n"
            + "\n".join(
                f"• {x.upper()}"
                for x
                in output.splitlines()
            )
        )


    def sessions_data(self):
        result = subprocess.run(
            ["ss", "-Htnp"],
            capture_output=True,
            text=True,
        )

        sessions = []

        for line in result.stdout.splitlines():
            if "sshd-session" not in line:
                continue

            if "ESTAB" not in line:
                continue

            parts = line.split()

            if len(parts) < 5:
                continue

            local_address = parts[3]
            remote_address = parts[4]

            pids = re.findall(
                r"pid=(\d+)",
                line,
            )

            session_pid = None
            username = None

            for pid in pids:
                ps = subprocess.run(
                    [
                        "ps",
                        "-p",
                        pid,
                        "-o",
                        "user=,args=",
                    ],
                    capture_output=True,
                    text=True,
                )

                info = ps.stdout.strip()

                if not info:
                    continue

                if "@" in info and "sshd-session:" in info:
                    session_pid = pid

                    username = (
                        info.split()[0]
                        if info.split()
                        else "unknown"
                    )

                    break

            if not session_pid:
                continue

            files = glob.glob(
                f"{SESSION_LOG_DIR}/"
                f"session_{session_pid}_*.log"
            )

            streamable = bool(files)

            sessions.append(
                {
                    "pid": session_pid,
                    "username": username,
                    "remote": remote_address,
                    "local": local_address,
                    "streamable": streamable,
                    "log_file": (
                        files[0]
                        if files
                        else None
                    ),
                }
            )

        unique = {}

        for session in sessions:
            unique[
                session["pid"]
            ] = session

        return list(
            unique.values()
        )


    def active_data(self):
        return [
            session
            for session
            in self.sessions_data()
            if session["streamable"]
        ]
