import glob
import ipaddress
import os
import re
import subprocess

from fastapi import FastAPI, HTTPException, Query

from shared.bus.redis_bus import RedisBus
from shared.config.settings import Settings

from services.api.app.control_client import ControlClient
from services.api.app.repository import APIRepository


app = FastAPI(
    title="SSH Guardian API",
    version="2.0.0",
)


repo = APIRepository()
control = ControlClient()
bus = RedisBus()


SERVICES = (
    "collector",
    "geoip",
    "security",
    "firewall",
    "storage",
    "control",
    "telegram",
    "api",
    "panel",
)


def service_status(name):
    """
    Détecte un service lancé soit par systemd,
    soit par scripts/start-dev.sh.
    """

    #
    # 1. Mode systemd
    #
    result = subprocess.run(
        [
            "systemctl",
            "is-active",
            f"ssh-guardian@{name}",
        ],
        capture_output=True,
        text=True,
    )

    if result.stdout.strip() == "active":
        return "active"

    #
    # 2. Mode dev : run/<service>.pid
    #
    pidfile = (
        Settings.RUN_DIR
        / f"{name}.pid"
    )

    if pidfile.exists():
        try:
            pid = int(
                pidfile.read_text().strip()
            )

            os.kill(
                pid,
                0,
            )

            return "active"

        except (
            ValueError,
            ProcessLookupError,
            PermissionError,
            OSError,
        ):
            pass

    #
    # 3. Rien trouvé
    #
    return "inactive"


def network_sessions():
    result = subprocess.run(
        ["ss", "-tnp"],
        capture_output=True,
        text=True,
    )

    mapping = {}

    for line in result.stdout.splitlines():
        if "sshd-session" not in line:
            continue

        pids = re.findall(
            r"pid=(\d+)",
            line,
        )

        address = re.search(
            r"\s([\da-fA-F:.]+):\d+\s+"
            r"([\da-fA-F:.]+):\d+",
            line,
        )

        if not address:
            continue

        local_ip, remote_ip = (
            address.groups()
        )

        for pid in pids:
            mapping[pid] = {
                "local_ip": local_ip,
                "remote_ip": remote_ip,
            }

    return mapping


def find_session_log(
    pid,
    ppid,
):
    log_dir = str(
        Settings.SESSION_LOG_DIR
    )

    for session_id in (
        str(pid),
        str(ppid),
    ):
        files = glob.glob(
            os.path.join(
                log_dir,
                f"session_{session_id}_*.log",
            )
        )

        if not files:
            continue

        files.sort(
            key=os.path.getmtime,
            reverse=True,
        )

        return {
            "session_id": session_id,
            "log_file": files[0],
        }

    return None


def active_sessions():
    process = subprocess.run(
        [
            "ps",
            "-eo",
            "pid=,ppid=,user=,args=",
        ],
        capture_output=True,
        text=True,
    )

    network = network_sessions()

    sessions = []

    regex = re.compile(
        r"(\d+)\s+"
        r"(\d+)\s+"
        r"(\S+)\s+"
        r"sshd-session:\s+"
        r"([^@\s]+)@(\S+)"
    )

    for line in process.stdout.splitlines():
        match = regex.match(
            line.strip()
        )

        if not match:
            continue

        pid, ppid, system_user, ssh_user, tty = (
            match.groups()
        )

        net = (
            network.get(pid)
            or network.get(ppid)
            or {}
        )

        recorder = find_session_log(
            pid,
            ppid,
        )

        sessions.append(
            {
                "pid": int(pid),
                "ppid": int(ppid),
                "user": ssh_user,
                "system_user": system_user,
                "tty": tty,
                "remote_ip": net.get(
                    "remote_ip"
                ),
                "local_ip": net.get(
                    "local_ip"
                ),
                "streamable":
                    recorder is not None,
                "session_id":
                    recorder.get(
                        "session_id"
                    )
                    if recorder
                    else None,
            }
        )

    return sessions


@app.get("/")
def root():
    return {
        "name": "SSH Guardian",
        "version": "2.0.0",
        "status": "online",
    }


@app.get("/health")
def health():
    services = {
        name: service_status(name)
        for name in SERVICES
    }

    return {
        "redis": bus.ping(),
        "services": services,
    }


@app.get("/stats")
def stats():
    return repo.stats()


@app.get("/events")
def events(
    limit: int = Query(
        100,
        ge=1,
        le=1000,
    ),
):
    return repo.events(
        limit=limit
    )


@app.get("/search/{ip}")
def search_ip(
    ip: str,
):
    try:
        ipaddress.ip_address(ip)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Adresse IP invalide",
        )

    return {
        "ip": ip,
        "events": repo.events(
            limit=100,
            ip=ip,
        ),
    }


@app.get("/bans")
def bans():
    return repo.firewall_history()


@app.get("/bans/active")
def active_bans():
    return repo.active_bans()


@app.get("/top")
def top(
    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),
):
    return repo.top_ips(limit)


@app.get("/topcountries")
def topcountries(
    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),
):
    return repo.top_countries(limit)


@app.get("/countries")
def countries():
    try:
        values = {
            line.strip().upper()
            for line
            in Settings.BLOCKED_COUNTRIES_FILE
            .read_text()
            .splitlines()
            if line.strip()
        }

    except FileNotFoundError:
        values = set()

    return {
        "blocked_countries":
            sorted(values)
    }


@app.get("/sessions")
def sessions():
    return active_sessions()


@app.post("/unban/{ip}")
def unban(
    ip: str,
):
    try:
        ipaddress.ip_address(ip)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="IP invalide",
        )

    try:
        result = control.execute(
            "unban",
            [ip],
        )

        return {
            "ok": True,
            "result": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )


@app.post(
    "/block-country/{country}"
)
def block_country(
    country: str,
):
    try:
        result = control.execute(
            "block",
            [country],
        )

        return {
            "ok": True,
            "result": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )


@app.post(
    "/unblock-country/{country}"
)
def unblock_country(
    country: str,
):
    try:
        result = control.execute(
            "unblock",
            [country],
        )

        return {
            "ok": True,
            "result": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )


@app.post(
    "/kill-session/{pid}"
)
def kill_session(
    pid: int,
):
    if pid <= 1:
        raise HTTPException(
            status_code=400,
            detail="PID invalide",
        )

    try:
        result = control.execute(
            "killsession",
            [str(pid)],
        )

        return {
            "ok": True,
            "result": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )


@app.post("/kill-all-sessions")
def kill_all_sessions():
    try:
        result = control.execute(
            "killallsessions"
        )

        return {
            "ok": True,
            "result": result,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )


@app.post(
    "/stream/start/{session_id}"
)
def stream_start(
    session_id: str,
    lines: int = Query(
        20,
        ge=5,
        le=60,
    ),
):
    try:
        result = control.execute(
            "stream_start",
            [
                session_id,
                str(lines),
            ],
        )

        return result

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )


@app.get(
    "/stream/{stream_id}"
)
def stream_get(
    stream_id: str,
):
    try:
        return control.execute(
            "stream_get",
            [stream_id],
        )

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )


@app.post(
    "/stream/stop/{stream_id}"
)
def stream_stop(
    stream_id: str,
):
    try:
        return control.execute(
            "stream_stop",
            [stream_id],
        )

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=Settings.API_HOST,
        port=Settings.API_PORT,
    )
