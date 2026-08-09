from pathlib import Path

import requests

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
)

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from shared.config.settings import Settings


STATIC_DIR = (
    Path(__file__).resolve().parent
    / "static"
)


app = FastAPI(
    title="SSH Guardian Panel",
)


def auth(
    authorization: str | None = Header(
        default=None
    ),
):
    expected = Settings.PANEL_TOKEN

    if not expected:
        raise HTTPException(
            503,
            "Token panel non configuré",
        )

    if authorization != (
        f"Bearer {expected}"
    ):
        raise HTTPException(
            401,
            "Token invalide",
        )


def api_url(path):
    return (
        Settings.PANEL_API_URL.rstrip("/")
        + path
    )


def request_api(
    method,
    path,
):
    response = requests.request(
        method,
        api_url(path),
        timeout=20,
    )

    try:
        data = response.json()
    except Exception:
        data = {
            "detail": response.text
        }

    if response.status_code >= 400:
        raise HTTPException(
            response.status_code,
            detail=data,
        )

    return data


app.mount(
    "/static",
    StaticFiles(
        directory=str(STATIC_DIR)
    ),
    name="static",
)


@app.get("/")
def index():
    return FileResponse(
        STATIC_DIR / "index.html"
    )


@app.get(
    "/api/health",
    dependencies=[Depends(auth)],
)
def health():
    return request_api(
        "GET",
        "/health",
    )


@app.get(
    "/api/stats",
    dependencies=[Depends(auth)],
)
def stats():
    return request_api(
        "GET",
        "/stats",
    )


@app.get(
    "/api/events",
    dependencies=[Depends(auth)],
)
def events():
    return request_api(
        "GET",
        "/events?limit=100",
    )


@app.get(
    "/api/search/{ip}",
    dependencies=[Depends(auth)],
)
def search(ip: str):
    return request_api(
        "GET",
        f"/search/{ip}",
    )


@app.get(
    "/api/bans",
    dependencies=[Depends(auth)],
)
def bans():
    return request_api(
        "GET",
        "/bans/active",
    )


@app.get(
    "/api/countries",
    dependencies=[Depends(auth)],
)
def countries():
    return request_api(
        "GET",
        "/countries",
    )


@app.get(
    "/api/top",
    dependencies=[Depends(auth)],
)
def top():
    return request_api(
        "GET",
        "/top",
    )


@app.get(
    "/api/topcountries",
    dependencies=[Depends(auth)],
)
def topcountries():
    return request_api(
        "GET",
        "/topcountries",
    )


@app.get(
    "/api/sessions",
    dependencies=[Depends(auth)],
)
def sessions():
    return request_api(
        "GET",
        "/sessions",
    )


@app.post(
    "/api/unban/{ip}",
    dependencies=[Depends(auth)],
)
def unban(ip: str):
    return request_api(
        "POST",
        f"/unban/{ip}",
    )


@app.post(
    "/api/block-country/{country}",
    dependencies=[Depends(auth)],
)
def block_country(country: str):
    return request_api(
        "POST",
        f"/block-country/{country}",
    )


@app.post(
    "/api/unblock-country/{country}",
    dependencies=[Depends(auth)],
)
def unblock_country(country: str):
    return request_api(
        "POST",
        f"/unblock-country/{country}",
    )


@app.post(
    "/api/kill-session/{pid}",
    dependencies=[Depends(auth)],
)
def kill_session(pid: int):
    return request_api(
        "POST",
        f"/kill-session/{pid}",
    )


@app.post(
    "/api/kill-all-sessions",
    dependencies=[Depends(auth)],
)
def kill_all_sessions():
    return request_api(
        "POST",
        "/kill-all-sessions",
    )


@app.post(
    "/api/stream/start/{session_id}",
    dependencies=[Depends(auth)],
)
def stream_start(
    session_id: str,
    lines: int = Query(
        20,
        ge=5,
        le=60,
    ),
):
    return request_api(
        "POST",
        f"/stream/start/{session_id}?lines={lines}",
    )


@app.get(
    "/api/stream/{stream_id}",
    dependencies=[Depends(auth)],
)
def stream_get(
    stream_id: str,
):
    return request_api(
        "GET",
        f"/stream/{stream_id}",
    )


@app.post(
    "/api/stream/stop/{stream_id}",
    dependencies=[Depends(auth)],
)
def stream_stop(
    stream_id: str,
):
    return request_api(
        "POST",
        f"/stream/stop/{stream_id}",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=Settings.PANEL_HOST,
        port=Settings.PANEL_PORT,
    )
