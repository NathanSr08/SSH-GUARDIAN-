import collections
import glob
import json
import os
import re
import subprocess
import threading
import time
import uuid
from shared.config.settings import Settings


SESSION_LOG_DIR = str(Settings.SESSION_LOG_DIR)


# CSI : couleurs, curseur, bracketed paste, clear screen, etc.
ANSI_CSI_RE = re.compile(
    r"\x1B(?:"
    r"\[[0-?]*[ -/]*[@-~]"
    r"|[@-_]"
    r")"
)

# OSC : titre de terminal, par ex ESC ] 0 ; admin@host BEL
ANSI_OSC_RE = re.compile(
    r"\x1B\].*?(?:\x07|\x1B\\)",
    re.DOTALL,
)

# Séquences qui peuvent rester après certains enregistrements
BRACKETED_PASTE_RE = re.compile(
    r"\[\?2004[hl]"
)

COLOR_LEFTOVER_RE = re.compile(
    r"\[(?:0|1|01|30|31|32|33|34|35|36|37)(?:;\d+)*m"
)


def clean_terminal_text(raw: str) -> str:
    if not raw:
        return ""

    # Supprimer NUL
    text = raw.replace("\x00", "")

    # Supprimer OSC avant CSI
    text = ANSI_OSC_RE.sub("", text)
    text = ANSI_CSI_RE.sub("", text)

    # Nettoyage de sécurité pour séquences mal enregistrées
    text = BRACKETED_PASTE_RE.sub("", text)
    text = COLOR_LEFTOVER_RE.sub("", text)

    # Supprimer le header/footer généré par `script`
    cleaned_lines = []

    for raw_line in text.splitlines():
        line = raw_line

        if line.startswith("Script started on "):
            continue

        if line.startswith("Script done on "):
            continue

        # Un terminal réécrit souvent la même ligne avec \r.
        # On conserve uniquement la dernière version.
        if "\r" in line:
            parts = [
                part
                for part in line.split("\r")
                if part.strip()
            ]

            line = parts[-1] if parts else ""

        # Traiter les backspaces
        while "\b" in line:
            line = re.sub(
                r".\x08",
                "",
                line,
            )

        line = line.strip("\r")

        # Supprimer quelques artefacts courants restants
        line = line.replace(
            "]0;",
            "",
        )

        line = re.sub(
            r"^\s+",
            "",
            line,
        )

        if not line.strip():
            continue

        # Éviter plusieurs prompts identiques vides
        if (
            cleaned_lines
            and line == cleaned_lines[-1]
        ):
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


class SessionStreamManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.streams = {}
        self.lock = threading.Lock()

    def find_log(self, session_id: str):
        files = glob.glob(
            f"{SESSION_LOG_DIR}/session_{session_id}_*.log"
        )

        if not files:
            return None

        files.sort(
            key=os.path.getmtime,
            reverse=True,
        )

        return files[0]

    def start(
        self,
        session_id: str,
        max_lines: int = 20,
    ):
        session_id = str(session_id)

        if not session_id.isdigit():
            return {
                "ok": False,
                "error": "PID invalide",
            }

        log_file = self.find_log(
            session_id
        )

        if not log_file:
            return {
                "ok": False,
                "error": (
                    "Aucun fichier d'enregistrement "
                    "pour cette session."
                ),
            }

        max_lines = max(
            5,
            min(
                int(max_lines),
                60,
            ),
        )

        stream_id = uuid.uuid4().hex

        redis_key = (
            f"sshguardian:stream:{stream_id}"
        )

        stop_event = threading.Event()

        with self.lock:
            self.streams[stream_id] = {
                "stop": stop_event,
                "session_id": session_id,
                "log_file": log_file,
            }

        thread = threading.Thread(
            target=self._worker,
            args=(
                stream_id,
                session_id,
                log_file,
                redis_key,
                max_lines,
                stop_event,
            ),
            daemon=True,
        )

        thread.start()

        return {
            "ok": True,
            "stream_id": stream_id,
            "session_id": session_id,
        }

    def _worker(
        self,
        stream_id,
        session_id,
        log_file,
        redis_key,
        max_lines,
        stop_event,
    ):
        # On garde davantage de lignes brutes puis on nettoie.
        raw_buffer = collections.deque(
            maxlen=max_lines * 4
        )

        process = subprocess.Popen(
            [
                "tail",
                "-n",
                str(max_lines * 2),
                "-F",
                log_file,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
            bufsize=1,
        )

        with self.lock:
            if stream_id in self.streams:
                self.streams[stream_id][
                    "process"
                ] = process

        def publish():
            raw_text = "\n".join(
                raw_buffer
            )

            cleaned = clean_terminal_text(
                raw_text
            )

            lines = cleaned.splitlines()

            cleaned = "\n".join(
                lines[-max_lines:]
            )

            alive = (
                subprocess.run(
                    [
                        "kill",
                        "-0",
                        session_id,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                ).returncode
                == 0
            )

            payload = {
                "session_id":
                    session_id,
                "alive":
                    alive,
                "content":
                    cleaned
                    or "(Attente de commandes...)",
                "updated_at":
                    time.time(),
            }

            self.redis.setex(
                redis_key,
                120,
                json.dumps(
                    payload,
                    ensure_ascii=False,
                ),
            )

            return alive

        try:
            # Publier même avant une nouvelle commande.
            publish()

            while not stop_event.is_set():
                if process.stdout is None:
                    break

                line = process.stdout.readline()

                if line:
                    raw_buffer.append(
                        line.rstrip("\n")
                    )

                    alive = publish()

                    if not alive:
                        break

                    continue

                if process.poll() is not None:
                    break

                time.sleep(0.05)

        finally:
            try:
                process.terminate()
                process.wait(timeout=1)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

            # Garder un dernier état dans Redis
            try:
                raw = self.redis.get(
                    redis_key
                )

                if raw:
                    payload = json.loads(
                        raw
                    )

                    payload["stream_stopped"] = True

                    self.redis.setex(
                        redis_key,
                        60,
                        json.dumps(
                            payload,
                            ensure_ascii=False,
                        ),
                    )
            except Exception:
                pass

            with self.lock:
                self.streams.pop(
                    stream_id,
                    None,
                )

    def get(self, stream_id):
        key = (
            f"sshguardian:stream:{stream_id}"
        )

        raw = self.redis.get(key)

        if not raw:
            return {
                "ok": False,
                "error":
                    "Flux introuvable ou expiré",
            }

        return {
            "ok": True,
            **json.loads(raw),
        }

    def stop(self, stream_id):
        with self.lock:
            stream = self.streams.get(
                stream_id
            )

        if not stream:
            return {
                "ok": True,
                "already_stopped": True,
            }

        stream["stop"].set()

        process = stream.get(
            "process"
        )

        if process:
            try:
                process.terminate()
            except Exception:
                pass

        return {
            "ok": True,
            "stopped": True,
        }
