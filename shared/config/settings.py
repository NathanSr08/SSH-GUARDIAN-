import os
from pathlib import Path


DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def env_path(name: str, default) -> Path:
    return Path(
        os.getenv(name, str(default))
    ).expanduser().resolve()


class Settings:
    # ==========================================================
    # Projet
    # ==========================================================

    PROJECT_ROOT = env_path(
        "SG_PROJECT_ROOT",
        DEFAULT_PROJECT_ROOT,
    )

    DATA_DIR = env_path(
        "SG_DATA_DIR",
        PROJECT_ROOT / "data",
    )

    LOG_DIR = env_path(
        "SG_LOG_DIR",
        PROJECT_ROOT / "logs",
    )

    RUN_DIR = env_path(
        "SG_RUN_DIR",
        PROJECT_ROOT / "run",
    )

    DB_PATH = env_path(
        "SG_DB_PATH",
        DATA_DIR / "guardian.db",
    )

    COUNTRY_SCRIPT = env_path(
        "SG_COUNTRY_SCRIPT",
        PROJECT_ROOT
        / "services"
        / "control"
        / "bin"
        / "country_blocker.sh",
    )

    # ==========================================================
    # État système
    # ==========================================================

    STATE_DIR = env_path(
        "SG_STATE_DIR",
        "/etc/ssh-guardian",
    )

    BLOCKED_COUNTRIES_FILE = env_path(
        "SG_BLOCKED_COUNTRIES_FILE",
        STATE_DIR / "blocked_countries.txt",
    )

    SESSION_LOG_DIR = env_path(
        "SG_SESSION_LOG_DIR",
        "/var/log/ssh_recorder",
    )

    # ==========================================================
    # Security
    # ==========================================================

    MAX_ATTEMPTS = int(
        os.getenv(
            "SG_MAX_ATTEMPTS",
            "3",
        )
    )

    BAN_DURATION_SECONDS = int(
        os.getenv(
            "SG_BAN_DURATION_SECONDS",
            "86400",
        )
    )

    WHITELIST = {
        ip.strip()
        for ip in os.getenv(
            "SG_WHITELIST",
            "127.0.0.1,::1",
        ).split(",")
        if ip.strip()
    }

    FIREWALL_ENABLED = (
        os.getenv(
            "SG_FIREWALL_ENABLED",
            "false",
        ).lower()
        == "true"
    )

    # ==========================================================
    # Redis
    # ==========================================================

    REDIS_URL = os.getenv(
        "SG_REDIS_URL",
        "redis://127.0.0.1:6379/0",
    )

    SSH_EVENTS_STREAM = os.getenv(
        "SG_SSH_EVENTS_STREAM",
        "ssh.events",
    )

    SSH_ENRICHED_STREAM = os.getenv(
        "SG_SSH_ENRICHED_STREAM",
        "ssh.events.enriched",
    )

    SECURITY_ACTIONS_STREAM = os.getenv(
        "SG_SECURITY_ACTIONS_STREAM",
        "security.actions",
    )

    FIREWALL_EVENTS_STREAM = os.getenv(
        "SG_FIREWALL_EVENTS_STREAM",
        "firewall.events",
    )

    CONTROL_COMMANDS_STREAM = os.getenv(
        "SG_CONTROL_COMMANDS_STREAM",
        "control.commands",
    )

    # ==========================================================
    # MFA
    # ==========================================================

    MFA_EVENTS_STREAM = os.getenv(
        "SG_MFA_EVENTS_STREAM",
        "mfa.events",
    )

    MFA_COMMANDS_STREAM = os.getenv(
        "SG_MFA_COMMANDS_STREAM",
        "mfa.commands",
    )

    MFA_TIMEOUT_SECONDS = int(
        os.getenv(
            "SG_MFA_TIMEOUT_SECONDS",
            "45",
        )
    )

    MFA_ENABLED = (
        os.getenv(
            "SG_MFA_ENABLED",
            "false",
        ).lower()
        == "true"
    )

    MFA_FAIL_MODE = os.getenv(
        "SG_MFA_FAIL_MODE",
        "deny",
    ).lower()

    MFA_BYPASS_USERS = {
        value.strip()
        for value in os.getenv(
            "SG_MFA_BYPASS_USERS",
            "",
        ).split(",")
        if value.strip()
    }

    MFA_BYPASS_IPS = {
        value.strip()
        for value in os.getenv(
            "SG_MFA_BYPASS_IPS",
            "",
        ).split(",")
        if value.strip()
    }

    # ==========================================================
    # GeoIP
    # ==========================================================

    GEOIP_CACHE_TTL = int(
        os.getenv(
            "SG_GEOIP_CACHE_TTL",
            "604800",
        )
    )

    GEOIP_TIMEOUT = int(
        os.getenv(
            "SG_GEOIP_TIMEOUT",
            "5",
        )
    )

    # ==========================================================
    # Telegram
    # ==========================================================

    TELEGRAM_TOKEN = os.getenv(
        "SG_TELEGRAM_TOKEN",
        "",
    )

    TELEGRAM_CHAT_ID = os.getenv(
        "SG_TELEGRAM_CHAT_ID",
        "",
    )

    TELEGRAM_ENABLED = (
        os.getenv(
            "SG_TELEGRAM_ENABLED",
            "false",
        ).lower()
        == "true"
    )

    # ==========================================================
    # API
    # ==========================================================

    API_HOST = os.getenv(
        "SG_API_HOST",
        "127.0.0.1",
    )

    API_PORT = int(
        os.getenv(
            "SG_API_PORT",
            "8080",
        )
    )


    # ==========================================================
    # Panel
    # ==========================================================

    PANEL_HOST = os.getenv(
        "SG_PANEL_HOST",
        "0.0.0.0",
    )

    PANEL_PORT = int(
        os.getenv(
            "SG_PANEL_PORT",
            "3000",
        )
    )

    PANEL_API_URL = os.getenv(
        "SG_PANEL_API_URL",
        f"http://{API_HOST}:{API_PORT}",
    )

    PANEL_TOKEN = os.getenv(
        "SG_PANEL_TOKEN",
        "",
    )


for directory in (
    Settings.DATA_DIR,
    Settings.LOG_DIR,
    Settings.RUN_DIR,
    Settings.STATE_DIR,
):
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )
