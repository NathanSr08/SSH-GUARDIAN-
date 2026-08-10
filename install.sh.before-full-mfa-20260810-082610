#!/usr/bin/env bash

set -Eeuo pipefail

# ============================================================
# SSH GUARDIAN V2 - INSTALLER
# ============================================================
#
# Usage:
#
#   sudo bash install.sh
#
# Options via variables:
#
#   SG_INSTALL_DIR=/opt/ssh-guardian sudo -E bash install.sh
#   SG_PANEL_PORT=3000 sudo -E bash install.sh
#   SG_API_PORT=8080 sudo -E bash install.sh
#
# ============================================================


# ------------------------------------------------------------
# COULEURS
# ------------------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'


info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}


ok() {
    echo -e "${GREEN}[OK]${NC} $*"
}


warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}


fail() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
    exit 1
}


# ------------------------------------------------------------
# ROOT
# ------------------------------------------------------------

if [ "${EUID}" -ne 0 ]; then
    fail "L'installation doit être lancée en root."
fi


# ------------------------------------------------------------
# DISTRIBUTION
# ------------------------------------------------------------

if [ ! -f /etc/os-release ]; then
    fail "Distribution Linux non reconnue."
fi

. /etc/os-release

case "${ID:-}" in
    debian|ubuntu)
        ;;
    *)
        warn "Distribution ${ID:-inconnue}. Le script est prévu pour Debian/Ubuntu."
        ;;
esac


# ------------------------------------------------------------
# CHEMINS
# ------------------------------------------------------------

SOURCE_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")"
    pwd
)"

INSTALL_DIR="${SG_INSTALL_DIR:-$SOURCE_DIR}"

STATE_DIR="${SG_STATE_DIR:-/etc/ssh-guardian}"
SESSION_LOG_DIR="${SG_SESSION_LOG_DIR:-/var/log/ssh_recorder}"

PROJECT_POINTER="$STATE_DIR/project-root"

VENV_DIR="$INSTALL_DIR/.venv"
ENV_FILE="$INSTALL_DIR/.env"

SYSTEMD_TEMPLATE="/etc/systemd/system/ssh-guardian@.service"
SERVICE_LAUNCHER="/usr/local/bin/ssh-guardian-service"

BACKUP_DIR="$STATE_DIR/backups"


# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------

PANEL_HOST="${SG_PANEL_HOST:-127.0.0.1}"
PANEL_PORT="${SG_PANEL_PORT:-3000}"

API_HOST="${SG_API_HOST:-127.0.0.1}"
API_PORT="${SG_API_PORT:-8080}"

MAX_ATTEMPTS="${SG_MAX_ATTEMPTS:-3}"
BAN_DURATION_SECONDS="${SG_BAN_DURATION_SECONDS:-86400}"

REDIS_URL="${SG_REDIS_URL:-redis://127.0.0.1:6379/0}"


# ------------------------------------------------------------
# BANNIÈRE
# ------------------------------------------------------------

echo
echo "============================================================"
echo "                  SSH GUARDIAN V2"
echo "                    INSTALLATION"
echo "============================================================"
echo
echo "Source       : $SOURCE_DIR"
echo "Installation : $INSTALL_DIR"
echo "Panel        : $PANEL_HOST:$PANEL_PORT"
echo "API          : $API_HOST:$API_PORT"
echo


# ------------------------------------------------------------
# DOSSIER D'INSTALLATION
# ------------------------------------------------------------

if [ "$SOURCE_DIR" != "$INSTALL_DIR" ]; then
    info "Copie du projet vers $INSTALL_DIR"

    mkdir -p "$INSTALL_DIR"

    cp -a \
        "$SOURCE_DIR/." \
        "$INSTALL_DIR/"
fi

cd "$INSTALL_DIR"

ok "Projet : $INSTALL_DIR"


# ------------------------------------------------------------
# DOSSIERS
# ------------------------------------------------------------

mkdir -p \
    "$STATE_DIR" \
    "$BACKUP_DIR" \
    "$SESSION_LOG_DIR" \
    "$INSTALL_DIR/data" \
    "$INSTALL_DIR/logs" \
    "$INSTALL_DIR/run"

touch "$STATE_DIR/blocked_countries.txt"

chmod 755 "$STATE_DIR"

# Les sessions SSH doivent pouvoir écrire leurs logs.
chmod 1733 "$SESSION_LOG_DIR"

echo "$INSTALL_DIR" > "$PROJECT_POINTER"

ok "Arborescence système créée"


# ------------------------------------------------------------
# PAQUETS SYSTÈME
# ------------------------------------------------------------

info "Installation des dépendances système..."

export DEBIAN_FRONTEND=noninteractive

apt-get update

apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    redis-server \
    openssh-server \
    iptables \
    iproute2 \
    procps \
    util-linux \
    curl \
    ca-certificates \
    jq \
    sqlite3

ok "Dépendances système installées"


# ------------------------------------------------------------
# REDIS
# ------------------------------------------------------------

systemctl enable redis-server >/dev/null 2>&1 || true
systemctl restart redis-server

if redis-cli ping 2>/dev/null | grep -q PONG; then
    ok "Redis opérationnel"
else
    fail "Redis ne répond pas."
fi


# ------------------------------------------------------------
# PYTHON VENV
# ------------------------------------------------------------

info "Création du virtualenv Python..."

if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/pip" install \
    --upgrade \
    pip \
    setuptools \
    wheel

if [ -f "$INSTALL_DIR/requirements.txt" ]; then

    info "Installation de requirements.txt"

    "$VENV_DIR/bin/pip" install \
        -r "$INSTALL_DIR/requirements.txt"

else

    info "requirements.txt absent : installation du runtime standard"

    "$VENV_DIR/bin/pip" install \
        redis \
        requests \
        fastapi \
        "uvicorn[standard]" \
        pytest \
        typeguard

fi

ok "Environnement Python prêt"


# ------------------------------------------------------------
# TEST IMPORTS
# ------------------------------------------------------------

"$VENV_DIR/bin/python" - <<'PY'
import redis
import requests
import fastapi
import uvicorn

print("Imports Python OK")
PY

ok "Dépendances Python vérifiées"


# ------------------------------------------------------------
# WHITELIST
# ------------------------------------------------------------

CURRENT_IP=""

if [ -n "${SSH_CLIENT:-}" ]; then
    CURRENT_IP="$(
        echo "$SSH_CLIENT" |
        awk '{print $1}'
    )"
fi

if [ -z "$CURRENT_IP" ] && [ -n "${SSH_CONNECTION:-}" ]; then
    CURRENT_IP="$(
        echo "$SSH_CONNECTION" |
        awk '{print $1}'
    )"
fi


if [ -n "${SG_WHITELIST:-}" ]; then

    WHITELIST="$SG_WHITELIST"

elif [ -n "$CURRENT_IP" ]; then

    WHITELIST="127.0.0.1,::1,$CURRENT_IP"

    ok "IP SSH actuelle ajoutée à la whitelist : $CURRENT_IP"

else

    WHITELIST="127.0.0.1,::1"

    warn "Impossible de détecter ton IP SSH."
    warn "Firewall laissé en DRY-RUN par sécurité."

fi


# ------------------------------------------------------------
# FIREWALL
# ------------------------------------------------------------

if [ -n "${SG_FIREWALL_ENABLED:-}" ]; then

    FIREWALL_ENABLED="$SG_FIREWALL_ENABLED"

elif [ -n "$CURRENT_IP" ]; then

    FIREWALL_ENABLED="true"

else

    FIREWALL_ENABLED="false"

fi


# ------------------------------------------------------------
# PANEL TOKEN
# ------------------------------------------------------------

EXISTING_TOKEN=""

if [ -f "$ENV_FILE" ]; then
    EXISTING_TOKEN="$(
        grep '^SG_PANEL_TOKEN=' "$ENV_FILE" 2>/dev/null |
        tail -n 1 |
        cut -d= -f2- || true
    )"
fi

if [ -n "${SG_PANEL_TOKEN:-}" ]; then

    PANEL_TOKEN="$SG_PANEL_TOKEN"

elif [ -n "$EXISTING_TOKEN" ]; then

    PANEL_TOKEN="$EXISTING_TOKEN"

else

    PANEL_TOKEN="$(
        "$VENV_DIR/bin/python" - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
    )"

fi


# ------------------------------------------------------------
# TELEGRAM
# ------------------------------------------------------------

EXISTING_TELEGRAM_TOKEN=""
EXISTING_TELEGRAM_CHAT_ID=""

if [ -f "$ENV_FILE" ]; then

    EXISTING_TELEGRAM_TOKEN="$(
        grep '^SG_TELEGRAM_TOKEN=' "$ENV_FILE" 2>/dev/null |
        tail -n 1 |
        cut -d= -f2- || true
    )"

    EXISTING_TELEGRAM_CHAT_ID="$(
        grep '^SG_TELEGRAM_CHAT_ID=' "$ENV_FILE" 2>/dev/null |
        tail -n 1 |
        cut -d= -f2- || true
    )"

fi

TELEGRAM_TOKEN="${SG_TELEGRAM_TOKEN:-$EXISTING_TELEGRAM_TOKEN}"
TELEGRAM_CHAT_ID="${SG_TELEGRAM_CHAT_ID:-$EXISTING_TELEGRAM_CHAT_ID}"

if [ -n "$TELEGRAM_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
    TELEGRAM_ENABLED=true
else
    TELEGRAM_ENABLED=false
fi


# ------------------------------------------------------------
# .ENV
# ------------------------------------------------------------

info "Création de .env"

if [ -f "$ENV_FILE" ]; then
    cp -a \
        "$ENV_FILE" \
        "$BACKUP_DIR/env.$(date +%Y%m%d-%H%M%S)"
fi

cat > "$ENV_FILE" <<EOF
# ============================================================
# SSH Guardian V2
# Generated by install.sh
# ============================================================


# ------------------------------------------------------------
# Runtime
# ------------------------------------------------------------

SG_STATE_DIR=$STATE_DIR
SG_BLOCKED_COUNTRIES_FILE=$STATE_DIR/blocked_countries.txt
SG_SESSION_LOG_DIR=$SESSION_LOG_DIR


# ------------------------------------------------------------
# Redis
# ------------------------------------------------------------

SG_REDIS_URL=$REDIS_URL

SG_SSH_EVENTS_STREAM=ssh.events
SG_SSH_ENRICHED_STREAM=ssh.events.enriched
SG_SECURITY_ACTIONS_STREAM=security.actions
SG_FIREWALL_EVENTS_STREAM=firewall.events
SG_CONTROL_COMMANDS_STREAM=control.commands


# ------------------------------------------------------------
# Security
# ------------------------------------------------------------

SG_MAX_ATTEMPTS=$MAX_ATTEMPTS
SG_BAN_DURATION_SECONDS=$BAN_DURATION_SECONDS

SG_WHITELIST=$WHITELIST

SG_FIREWALL_ENABLED=$FIREWALL_ENABLED


# ------------------------------------------------------------
# GeoIP
# ------------------------------------------------------------

SG_GEOIP_CACHE_TTL=604800
SG_GEOIP_TIMEOUT=5


# ------------------------------------------------------------
# Telegram
# ------------------------------------------------------------

SG_TELEGRAM_ENABLED=$TELEGRAM_ENABLED
SG_TELEGRAM_TOKEN=$TELEGRAM_TOKEN
SG_TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID


# ------------------------------------------------------------
# API
# ------------------------------------------------------------

SG_API_HOST=$API_HOST
SG_API_PORT=$API_PORT


# ------------------------------------------------------------
# Panel
# ------------------------------------------------------------

SG_PANEL_HOST=$PANEL_HOST
SG_PANEL_PORT=$PANEL_PORT

SG_PANEL_API_URL=http://127.0.0.1:$API_PORT

SG_PANEL_TOKEN=$PANEL_TOKEN
EOF

chmod 600 "$ENV_FILE"

ok ".env généré"


# ------------------------------------------------------------
# SSH RECORDER
# ------------------------------------------------------------

info "Configuration de l'enregistrement SSH..."

cat > /usr/local/bin/ssh-wrapper.sh <<EOF
#!/usr/bin/env bash

set -u

SESSION_LOG_DIR="${SESSION_LOG_DIR}"

if [ -n "\${SSH_TTY:-}" ]; then

    SESSION_ID="\$PPID"
    USERNAME="\${USER:-unknown}"

    mkdir -p "\$SESSION_LOG_DIR"

    LOG_FILE="\${SESSION_LOG_DIR}/session_\${SESSION_ID}_\${USERNAME}.log"

    umask 077

    exec /usr/bin/script \
        -f \
        -q \
        -c "\${SHELL:-/bin/bash} -l" \
        "\$LOG_FILE"
fi


if [ -n "\${SSH_ORIGINAL_COMMAND:-}" ]; then

    exec "\${SHELL:-/bin/bash}" \
        -c "\$SSH_ORIGINAL_COMMAND"

fi


exec "\${SHELL:-/bin/bash}" -l
EOF

chmod 755 /usr/local/bin/ssh-wrapper.sh

ok "SSH recorder installé"


# ------------------------------------------------------------
# SSHD CONFIG BACKUP
# ------------------------------------------------------------

mkdir -p /etc/ssh/sshd_config.d

if [ -f /etc/ssh/sshd_config ]; then

    cp -a \
        /etc/ssh/sshd_config \
        "$BACKUP_DIR/sshd_config.$(date +%Y%m%d-%H%M%S)"

fi


# ------------------------------------------------------------
# LOGLEVEL
# ------------------------------------------------------------

cat > /etc/ssh/sshd_config.d/98-ssh-guardian-logging.conf <<'EOF'
LogLevel VERBOSE
EOF


# ------------------------------------------------------------
# FORCECOMMAND
# ------------------------------------------------------------

cat > /etc/ssh/sshd_config.d/99-ssh-guardian-recorder.conf <<'EOF'
ForceCommand /usr/local/bin/ssh-wrapper.sh
EOF


# ------------------------------------------------------------
# TEST SSHD
# ------------------------------------------------------------

if sshd -t; then
    ok "Configuration SSH valide"
else
    fail "Configuration sshd invalide. Installation interrompue."
fi


# ------------------------------------------------------------
# RELOAD SSH
# ------------------------------------------------------------

if systemctl list-unit-files |
    grep -q '^ssh.service'
then

    systemctl reload ssh

elif systemctl list-unit-files |
    grep -q '^sshd.service'
then

    systemctl reload sshd

else

    fail "Service SSH introuvable."

fi

ok "SSH rechargé"


# ------------------------------------------------------------
# VÉRIFICATION FORCECOMMAND
# ------------------------------------------------------------

FORCE_COMMAND="$(
    sshd -T 2>/dev/null |
    awk '$1 == "forcecommand" {
        $1="";
        sub(/^ /, "");
        print
    }'
)"

if echo "$FORCE_COMMAND" |
    grep -q 'ssh-wrapper.sh'
then

    ok "SSH recorder actif"

else

    warn "ForceCommand ne semble pas actif."

fi


# ------------------------------------------------------------
# NETTOYAGE ANCIEN IPSET COUNTRY BLOCKER
# ------------------------------------------------------------

if command -v ipset >/dev/null 2>&1; then

    while iptables -C INPUT \
        -m set \
        --match-set blocked_countries src \
        -j DROP >/dev/null 2>&1
    do

        iptables -D INPUT \
            -m set \
            --match-set blocked_countries src \
            -j DROP \
            || true

    done

    ipset destroy blocked_countries \
        >/dev/null 2>&1 || true

fi


# ------------------------------------------------------------
# LAUNCHER SYSTEMD
# ------------------------------------------------------------

cat > "$SERVICE_LAUNCHER" <<'EOF'
#!/usr/bin/env bash

set -Eeuo pipefail


SERVICE="${1:?Nom du service manquant}"

PROJECT_FILE="${SG_PROJECT_FILE:-/etc/ssh-guardian/project-root}"


if [ ! -f "$PROJECT_FILE" ]; then

    echo "SSH Guardian project-root introuvable : $PROJECT_FILE" >&2
    exit 1

fi


PROJECT_ROOT="$(
    cat "$PROJECT_FILE"
)"


if [ ! -d "$PROJECT_ROOT" ]; then

    echo "Projet SSH Guardian introuvable : $PROJECT_ROOT" >&2
    exit 1

fi


cd "$PROJECT_ROOT"


ENV_FILE="${SG_ENV_FILE:-$PROJECT_ROOT/.env}"


if [ -f "$ENV_FILE" ]; then

    set -a
    source "$ENV_FILE"
    set +a

fi


export SG_PROJECT_ROOT="$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"
export PYTHONUNBUFFERED=1


PYTHON="$PROJECT_ROOT/.venv/bin/python"


if [ ! -x "$PYTHON" ]; then
    PYTHON="/usr/bin/python3"
fi


exec "$PYTHON" \
    -m "services.${SERVICE}.app.main"
EOF

chmod 755 "$SERVICE_LAUNCHER"

ok "Launcher systemd installé"


# ------------------------------------------------------------
# SYSTEMD TEMPLATE
# ------------------------------------------------------------

cat > "$SYSTEMD_TEMPLATE" <<'EOF'
[Unit]
Description=SSH Guardian V2 - %i

After=network-online.target redis-server.service
Wants=network-online.target
Requires=redis-server.service


[Service]

Type=simple

ExecStart=/usr/local/bin/ssh-guardian-service %i

Restart=always
RestartSec=2

TimeoutStopSec=10
KillSignal=SIGINT


[Install]

WantedBy=multi-user.target
EOF

systemctl daemon-reload

ok "Template systemd installé"


# ------------------------------------------------------------
# DÉTECTION SERVICES
# ------------------------------------------------------------

SERVICES=()

KNOWN_SERVICES=(
    collector
    geoip
    security
    firewall
    storage
    control
    telegram
    api
    panel
)


for service in "${KNOWN_SERVICES[@]}"
do

    if [ -f "$INSTALL_DIR/services/$service/app/main.py" ]; then

        SERVICES+=("$service")

        ok "Microservice détecté : $service"

    else

        warn "Microservice absent : $service"

    fi

done


if [ "${#SERVICES[@]}" -eq 0 ]; then
    fail "Aucun microservice trouvé."
fi


# ------------------------------------------------------------
# PY COMPILE
# ------------------------------------------------------------

info "Vérification syntaxique Python..."

cd "$INSTALL_DIR"

while IFS= read -r -d '' file
do

    "$VENV_DIR/bin/python" \
        -m py_compile \
        "$file"

done < <(
    find services shared \
        -type f \
        -name '*.py' \
        -print0
)

ok "Syntaxe Python valide"


# ------------------------------------------------------------
# TESTS
# ------------------------------------------------------------

if [ -d "$INSTALL_DIR/tests" ]; then

    info "Tests SSH Guardian..."

    set +e

    PYTHONPATH="$INSTALL_DIR" \
        "$VENV_DIR/bin/python" \
        -m pytest \
        -q

    TEST_STATUS=$?

    set -e

    if [ "$TEST_STATUS" -eq 0 ]; then
        ok "Tests réussis"
    else
        warn "Certains tests ont échoué."
        warn "Installation poursuivie pour permettre le diagnostic."
    fi

fi


# ------------------------------------------------------------
# STOP DEV PROCESSES
# ------------------------------------------------------------

if [ -x "$INSTALL_DIR/scripts/stop-dev.sh" ]; then

    "$INSTALL_DIR/scripts/stop-dev.sh" \
        >/dev/null 2>&1 || true

fi


# ------------------------------------------------------------
# ENABLE SERVICES
# ------------------------------------------------------------

info "Activation des microservices..."

for service in "${SERVICES[@]}"
do

    systemctl enable \
        "ssh-guardian@$service" \
        >/dev/null

    systemctl restart \
        "ssh-guardian@$service"

done


sleep 4


# ------------------------------------------------------------
# STATUT
# ------------------------------------------------------------

echo
echo "============================================================"
echo "                  ÉTAT DES SERVICES"
echo "============================================================"

FAILED_SERVICES=0

for service in "${SERVICES[@]}"
do

    printf "%-12s : " "$service"

    if systemctl is-active \
        --quiet \
        "ssh-guardian@$service"
    then

        echo -e "${GREEN}RUNNING${NC}"

    else

        echo -e "${RED}DOWN${NC}"

        FAILED_SERVICES=$(
            (FAILED_SERVICES + 1)
        )

    fi

done


# ------------------------------------------------------------
# FIREWALL STATUS
# ------------------------------------------------------------

echo
info "Firewall : SG_FIREWALL_ENABLED=$FIREWALL_ENABLED"
info "Whitelist : $WHITELIST"


# ------------------------------------------------------------
# API TEST
# ------------------------------------------------------------

if printf '%s\n' "${SERVICES[@]}" |
    grep -qx api
then

    echo

    if curl \
        -fsS \
        "http://127.0.0.1:$API_PORT/health" \
        >/dev/null 2>&1
    then

        ok "API répond sur 127.0.0.1:$API_PORT"

    else

        warn "API ne répond pas encore."

    fi

fi


# ------------------------------------------------------------
# PANEL TEST
# ------------------------------------------------------------

if printf '%s\n' "${SERVICES[@]}" |
    grep -qx panel
then

    if curl \
        -fsS \
        "http://127.0.0.1:$PANEL_PORT/" \
        >/dev/null 2>&1
    then

        ok "Panel répond sur 127.0.0.1:$PANEL_PORT"

    else

        warn "Panel ne répond pas encore."

    fi

fi


# ------------------------------------------------------------
# COMMANDES ADMIN
# ------------------------------------------------------------

cat > /usr/local/bin/ssh-guardian-status <<'EOF'
#!/usr/bin/env bash

for SERVICE in \
    collector \
    geoip \
    security \
    firewall \
    storage \
    control \
    telegram \
    api \
    panel
do

    if systemctl list-unit-files \
        "ssh-guardian@$SERVICE.service" \
        --no-legend 2>/dev/null |
        grep -q .
    then

        printf "%-12s : " "$SERVICE"

        if systemctl is-active \
            --quiet \
            "ssh-guardian@$SERVICE"
        then

            echo "RUNNING"

        else

            echo "DOWN"

        fi

    fi

done
EOF

chmod 755 /usr/local/bin/ssh-guardian-status


cat > /usr/local/bin/ssh-guardian-restart <<'EOF'
#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(
    cat /etc/ssh-guardian/project-root
)"

for SERVICE in \
    collector \
    geoip \
    security \
    firewall \
    storage \
    control \
    telegram \
    api \
    panel
do

    if [ -f "$PROJECT_ROOT/services/$SERVICE/app/main.py" ]; then

        systemctl restart \
            "ssh-guardian@$SERVICE"

    fi

done
EOF

chmod 755 /usr/local/bin/ssh-guardian-restart


# ------------------------------------------------------------
# FIN
# ------------------------------------------------------------

echo
echo "============================================================"
echo -e "${GREEN}       SSH GUARDIAN V2 INSTALLÉ AVEC SUCCÈS${NC}"
echo "============================================================"
echo
echo "Projet :"
echo "  $INSTALL_DIR"
echo
echo "État :"
echo "  ssh-guardian-status"
echo
echo "Redémarrer :"
echo "  ssh-guardian-restart"
echo
echo "Logs d'un service :"
echo "  journalctl -fu ssh-guardian@security"
echo
echo "Panel :"
echo "  http://127.0.0.1:$PANEL_PORT"
echo
echo "API :"
echo "  http://127.0.0.1:$API_PORT"
echo
echo "Token Panel :"
echo
echo "  $PANEL_TOKEN"
echo
echo "Tunnel Windows :"
echo
echo "  ssh -i C:\\Users\\natha\\Downloads\\f.pem -N -L ${PANEL_PORT}:127.0.0.1:${PANEL_PORT} admin@TON_SERVEUR"
echo
echo "Puis navigateur :"
echo
echo "  http://127.0.0.1:$PANEL_PORT"
echo

if [ "$FIREWALL_ENABLED" != "true" ]; then

    echo -e "${YELLOW}ATTENTION : firewall en DRY-RUN.${NC}"
    echo
    echo "Configure SG_WHITELIST dans :"
    echo
    echo "  $ENV_FILE"
    echo
    echo "puis mets :"
    echo
    echo "  SG_FIREWALL_ENABLED=true"
    echo
    echo "et :"
    echo
    echo "  ssh-guardian-restart"
    echo

fi


if [ "$TELEGRAM_ENABLED" != "true" ]; then

    echo -e "${YELLOW}Telegram non configuré.${NC}"
    echo
    echo "Ajoute dans $ENV_FILE :"
    echo
    echo "  SG_TELEGRAM_ENABLED=true"
    echo "  SG_TELEGRAM_TOKEN=..."
    echo "  SG_TELEGRAM_CHAT_ID=..."
    echo

fi


if [ "$FAILED_SERVICES" -gt 0 ]; then

    echo -e "${YELLOW}$FAILED_SERVICES service(s) ne sont pas démarrés.${NC}"
    echo
    echo "Diagnostic :"
    echo
    echo "  systemctl --failed"
    echo "  journalctl -u ssh-guardian@NOM -n 100 --no-pager"
    echo

fi
