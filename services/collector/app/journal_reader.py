import subprocess
from collections.abc import Iterator


def read_ssh_logs() -> Iterator[str]:
    """
    Lit les logs SSH en temps réel via systemd journal.
    """

    process = subprocess.Popen(
        [
            "journalctl",
            "-u",
            "ssh",
            "-f",
            "-n",
            "0",
            "--no-pager",
            "-o",
            "cat",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    if process.stdout is None:
        raise RuntimeError("Impossible de lire la sortie de journalctl")

    try:
        for line in process.stdout:
            line = line.rstrip("\n")

            if line:
                yield line

    finally:
        process.terminate()
        process.wait()
