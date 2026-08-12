import glob
import html
import os
import re
import subprocess
from shared.config.settings import Settings


SESSION_LOG_DIR = str(Settings.SESSION_LOG_DIR)


class SessionManager:
    def _active_sessions(self):
        result = subprocess.run(
            [
                "ps",
                "-eo",
                "pid=,ppid=,user=,args=",
            ],
            capture_output=True,
            text=True,
        )

        sessions = []

        for line in result.stdout.splitlines():
            line = line.strip()

            match = re.match(
                r"(\d+)\s+(\d+)\s+(\S+)\s+"
                r"sshd-session:\s+([^@\s]+)@(\S+)",
                line,
            )

            if not match:
                continue

            pid, ppid, system_user, ssh_user, tty = match.groups()

            sessions.append(
                {
                    "pid": pid,
                    "ppid": ppid,
                    "user": ssh_user,
                    "tty": tty,
                }
            )

        return sessions

    def _network_sessions(self):
        result = subprocess.run(
            ["ss", "-tnp"],
            capture_output=True,
            text=True,
        )

        mapping = {}

        for line in result.stdout.splitlines():
            if "sshd-session" not in line:
                continue

            pid_match = re.findall(
                r'pid=(\d+)',
                line,
            )

            address_match = re.search(
                r"\s([\da-fA-F:.]+):\d+\s+"
                r"([\da-fA-F:.]+):\d+",
                line,
            )

            if not address_match:
                continue

            local_ip, remote_ip = address_match.groups()

            for pid in pid_match:
                mapping[pid] = {
                    "local_ip": local_ip,
                    "remote_ip": remote_ip,
                }

        return mapping

    def _log_for_pid(self, pid):
        files = glob.glob(
            f"{SESSION_LOG_DIR}/session_{pid}_*.log"
        )

        if not files:
            return None

        files.sort(
            key=os.path.getmtime,
            reverse=True,
        )

        return files[0]

    def active(self):
        sessions = self._active_sessions()
        network = self._network_sessions()

        if not sessions:
            return "📭 Aucune session SSH active."

        lines = [
            "📡 <b>Sessions SSH actives</b>",
            "",
        ]

        for session in sessions:
            pid = session["pid"]

            log_file = self._log_for_pid(pid)

            streamable = log_file is not None

            net = network.get(pid, {})

            remote_ip = net.get(
                "remote_ip",
                "Inconnue",
            )

            if streamable:
                status = "🟢 LIVE / streamable"
            else:
                status = "🟡 LIVE / non enregistrée"

            lines.append(
                f"• PID : <code>{pid}</code>\n"
                f"  👤 {html.escape(session['user'])}\n"
                f"  🌐 {html.escape(remote_ip)}\n"
                f"  🖥 {html.escape(session['tty'])}\n"
                f"  {status}"
            )

            if streamable:
                lines.append(
                    f"  📡 <code>/stream {pid}</code>"
                )

            lines.append("")

        return "\n".join(lines)

    def sessions(self):
        return self.active()

    def stream_snapshot(
        self,
        session_id,
        max_lines=10,
    ):
        session_id = str(session_id)

        if not session_id.isdigit():
            return {
                "ok": False,
                "text": "PID invalide.",
            }

        active_pids = {
            session["pid"]
            for session in self._active_sessions()
        }

        log_file = self._log_for_pid(
            session_id
        )

        if not log_file:
            return {
                "ok": False,
                "text": (
                    "Cette session n'a pas de flux enregistré. "
                    "Reconnectez-vous après activation du recorder."
                ),
            }

        try:
            with open(
                log_file,
                "r",
                encoding="utf-8",
                errors="ignore",
                newline="",
            ) as handle:
                raw = handle.read()

        except Exception as exc:
            return {
                "ok": False,
                "text": str(exc),
            }

        ansi = re.compile(
            r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
        )

        text = ansi.sub("", raw)
        text = text.replace("\x00", "")

        cleaned = []

        for line in text.split("\n"):
            if "\r" in line:
                parts = [
                    part
                    for part in line.split("\r")
                    if part.strip()
                ]

                line = (
                    parts[-1]
                    if parts
                    else ""
                )

            if line.strip():
                cleaned.append(
                    line.rstrip()
                )

        max_lines = max(
            1,
            min(
                int(max_lines),
                100,
            ),
        )

        content = "\n".join(
            cleaned[-max_lines:]
        )

        return {
            "ok": True,
            "alive": session_id in active_pids,
            "session_id": session_id,
            "content": (
                content
                or "(Attente de commandes...)"
            ),
        }

    def kill(self, pid):
        pid = str(pid)

        if not pid.isdigit():
            return "❌ PID invalide."

        active_pids = {
            session["pid"]
            for session in self._active_sessions()
        }

        if pid not in active_pids:
            return (
                f"❌ Session <code>{pid}</code> "
                "introuvable ou déjà terminée."
            )

        result = subprocess.run(
            ["kill", "-9", pid],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            return (
                f"💥 Session <code>{pid}</code> "
                "terminée."
            )

        return (
            f"❌ Impossible de tuer "
            f"<code>{pid}</code>."
        )

    def kill_all(self):
        sessions = self._active_sessions()

        killed = 0

        for session in sessions:
            result = subprocess.run(
                [
                    "kill",
                    "-9",
                    session["pid"],
                ],
                capture_output=True,
            )

            if result.returncode == 0:
                killed += 1

        return (
            f"⚡ {killed} session(s) SSH "
            "terminée(s)."
        )
