#!/usr/bin/env bash

set -Eeuo pipefail


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


ask_yes_no() {
    local prompt="$1"
    local default="${2:-n}"
    local answer

    if [ "$default" = "y" ]; then
        read -r -p "$prompt [Y/n] " answer
        answer="${answer:-y}"
    else
        read -r -p "$prompt [y/N] " answer
        answer="${answer:-n}"
    fi

    case "${answer,,}" in
        y|yes|o|oui)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}


if [ "${EUID}" -ne 0 ]; then
    fail "Lance ce script en root."
fi


SCRIPT_DIR="$(
    cd "$(dirname "${BASH_SOURCE[0]}")"
    pwd
)"


STATE_DIR="${SG_STATE_DIR:-/etc/ssh-guardian}"

PROJECT_POINTER="$STATE_DIR/project-root"


if [ -f "$PROJECT_POINTER" ]; then
    PROJECT_ROOT="$(cat "$PROJECT_POINTER")"
else
    PROJECT_ROOT="$SCRIPT_DIR"
fi


if [ ! -d "$PROJECT_ROOT" ]; then
    warn "Projet indiqué par project-root introuvable."
    PROJECT_ROOT="$SCRIPT_DIR"
fi


ENV_FILE="$PROJECT_ROOT/.env"


if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi


SESSION_LOG_DIR="${SG_SESSION_LOG_DIR:-/var/log/ssh_recorder}"

DB_PATH="${SG_DB_PATH:-$PROJECT_ROOT/data/guardian.db}"

LOG_DIR="${SG_LOG_DIR:-$PROJECT_ROOT/logs}"

RUN_DIR="${SG_RUN_DIR:-$PROJECT_ROOT/run}"


echo
echo "============================================================"
echo "              SSH GUARDIAN V2 - UNINSTALL"
echo "============================================================"
echo
echo "Projet           : $PROJECT_ROOT"
echo "État             : $STATE_DIR"
echo "Base             : $DB_PATH"
echo "Logs             : $LOG_DIR"
echo "Sessions SSH     : $SESSION_LOG_DIR"
echo


if ! ask_yes_no \
    "Continuer la désinstallation de SSH Guardian ?" \
    "n"
then
    echo "Annulé."
    exit 0
fi


# ============================================================
# SERVICES
# ============================================================

info "Arrêt des services SSH Guardian..."


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
    systemctl stop \
        "ssh-guardian@$service" \
        >/dev/null 2>&1 || true

    systemctl disable \
        "ssh-guardian@$service" \
        >/dev/null 2>&1 || true
done


ok "Services arrêtés"


# ============================================================
# ANCIENS PROCESS DEV
# ============================================================

if [ -x "$PROJECT_ROOT/scripts/stop-dev.sh" ]; then
    "$PROJECT_ROOT/scripts/stop-dev.sh" \
        >/dev/null 2>&1 || true
fi


for service in "${KNOWN_SERVICES[@]}"
do
    pkill -f \
        "services.${service}.app.main" \
        >/dev/null 2>&1 || true
done


# ============================================================
# FIREWALL
# ============================================================

info "Nettoyage des règles firewall SSH Guardian..."


declare -A IPS_TO_UNBAN=()


if [ -f "$DB_PATH" ] && command -v sqlite3 >/dev/null 2>&1; then

    while IFS= read -r ip
    do
        if [ -n "$ip" ]; then
            IPS_TO_UNBAN["$ip"]=1
        fi
    done < <(
        sqlite3 "$DB_PATH" \
            "SELECT DISTINCT ip
             FROM firewall_events
             WHERE event_type='firewall.ip.banned'
               AND ip IS NOT NULL
               AND ip != '';"
    )

fi


if command -v redis-cli >/dev/null 2>&1; then

    while IFS= read -r key
    do
        ip="${key#security:blocked-country:}"

        if [ -n "$ip" ] && [ "$ip" != "$key" ]; then
            IPS_TO_UNBAN["$ip"]=1
        fi
    done < <(
        redis-cli \
            --scan \
            --pattern 'security:blocked-country:*' \
            2>/dev/null || true
    )

fi


if command -v iptables >/dev/null 2>&1; then

    for ip in "${!IPS_TO_UNBAN[@]}"
    do
        while iptables -C INPUT \
            -s "$ip" \
            -j DROP \
            >/dev/null 2>&1
        do
            iptables -D INPUT \
                -s "$ip" \
                -j DROP \
                >/dev/null 2>&1 || break
        done
    done


    while iptables -C INPUT \
        -m set \
        --match-set blocked_countries src \
        -j DROP \
        >/dev/null 2>&1
    do
        iptables -D INPUT \
            -m set \
            --match-set blocked_countries src \
            -j DROP \
            >/dev/null 2>&1 || break
    done

fi


if command -v ipset >/dev/null 2>&1; then
    ipset destroy blocked_countries \
        >/dev/null 2>&1 || true
fi


if command -v redis-cli >/dev/null 2>&1; then

    redis-cli \
        --scan \
        --pattern 'security:blocked-country:*' \
        2>/dev/null |
    while IFS= read -r key
    do
        redis-cli DEL "$key" \
            >/dev/null 2>&1 || true
    done


    redis-cli \
        --scan \
        --pattern 'security:attempts:*' \
        2>/dev/null |
    while IFS= read -r key
    do
        redis-cli DEL "$key" \
            >/dev/null 2>&1 || true
    done

fi


ok "Firewall nettoyé"


# ============================================================
# SSH RECORDER
# ============================================================

info "Retrait de la configuration SSH Guardian..."


SSH_CONF_FILES=(
    /etc/ssh/sshd_config.d/98-ssh-guardian-logging.conf
    /etc/ssh/sshd_config.d/99-ssh-guardian-recorder.conf
)


for file in "${SSH_CONF_FILES[@]}"
do
    rm -f "$file"
done


rm -f /usr/local/bin/ssh-wrapper.sh


if sshd -t; then
    ok "Configuration SSH toujours valide"
else
    fail "La configuration SSH est invalide après retrait. SSH n'a pas été rechargé."
fi


if systemctl list-unit-files |
    grep -q '^ssh.service'
then
    systemctl reload ssh
elif systemctl list-unit-files |
    grep -q '^sshd.service'
then
    systemctl reload sshd
else
    warn "Service SSH non trouvé pour reload."
fi


ok "Recorder SSH retiré"


# ============================================================
# SYSTEMD
# ============================================================

info "Retrait des fichiers systemd..."


rm -f \
    /etc/systemd/system/ssh-guardian@.service \
    /usr/local/bin/ssh-guardian-service \
    /usr/local/bin/ssh-guardian-status \
    /usr/local/bin/ssh-guardian-restart


systemctl daemon-reload
systemctl reset-failed >/dev/null 2>&1 || true


ok "Systemd nettoyé"


# ============================================================
# DONNÉES
# ============================================================

echo


if [ -f "$DB_PATH" ]; then

    if ask_yes_no \
        "Supprimer la base de données SSH Guardian ?" \
        "n"
    then
        rm -f \
            "$DB_PATH" \
            "$DB_PATH-shm" \
            "$DB_PATH-wal"

        ok "Base supprimée"
    else
        ok "Base conservée"
    fi

fi


if [ -d "$LOG_DIR" ]; then

    if ask_yes_no \
        "Supprimer les logs applicatifs ?" \
        "n"
    then
        rm -rf "$LOG_DIR"
        ok "Logs supprimés"
    else
        ok "Logs conservés"
    fi

fi


if [ -d "$SESSION_LOG_DIR" ]; then

    if ask_yes_no \
        "Supprimer les enregistrements des sessions SSH ?" \
        "n"
    then
        rm -rf "$SESSION_LOG_DIR"
        ok "Enregistrements SSH supprimés"
    else
        ok "Enregistrements SSH conservés"
    fi

fi


if [ -f "$ENV_FILE" ]; then

    if ask_yes_no \
        "Supprimer le fichier .env ?" \
        "n"
    then
        rm -f "$ENV_FILE"
        ok ".env supprimé"
    else
        ok ".env conservé"
    fi

fi


if [ -d "$RUN_DIR" ]; then
    rm -rf "$RUN_DIR"
fi


# ============================================================
# ETAT /ETC
# ============================================================

if [ -d "$STATE_DIR" ]; then

    if ask_yes_no \
        "Supprimer /etc/ssh-guardian et son état ?" \
        "n"
    then
        rm -rf "$STATE_DIR"
        ok "État système supprimé"
    else
        rm -f "$PROJECT_POINTER"
        ok "État système conservé"
    fi

fi


# ============================================================
# REDIS
# ============================================================

echo


if ask_yes_no \
    "Désinstaller aussi Redis du système ?" \
    "n"
then

    systemctl stop redis-server \
        >/dev/null 2>&1 || true

    systemctl disable redis-server \
        >/dev/null 2>&1 || true

    apt-get remove -y \
        redis-server \
        redis-tools \
        >/dev/null 2>&1 || true

    apt-get autoremove -y \
        >/dev/null 2>&1 || true

    ok "Redis désinstallé"

else
    ok "Redis conservé"
fi


# ============================================================
# VENV
# ============================================================

if [ -d "$PROJECT_ROOT/.venv" ]; then

    if ask_yes_no \
        "Supprimer le virtualenv Python .venv ?" \
        "y"
    then
        rm -rf "$PROJECT_ROOT/.venv"
        ok "Virtualenv supprimé"
    fi

fi


# ============================================================
# PROJET
# ============================================================

echo


if [ -d "$PROJECT_ROOT" ]; then

    if ask_yes_no \
        "Supprimer également tout le dossier du projet ?" \
        "n"
    then

        CURRENT_SCRIPT="$(
            cd "$(dirname "${BASH_SOURCE[0]}")"
            pwd
        )"


        if [ "$PROJECT_ROOT" = "/" ]; then
            fail "Refus de supprimer /"
        fi


        if [ "$PROJECT_ROOT" = "/root" ] || \
           [ "$PROJECT_ROOT" = "/home" ] || \
           [ "$PROJECT_ROOT" = "/usr" ] || \
           [ "$PROJECT_ROOT" = "/opt" ]
        then
            fail "Chemin de projet jugé dangereux : $PROJECT_ROOT"
        fi


        warn "Suppression finale de : $PROJECT_ROOT"


        if [ "$CURRENT_SCRIPT" = "$PROJECT_ROOT" ]; then

            (
                sleep 1
                rm -rf "$PROJECT_ROOT"
            ) &

        else
            rm -rf "$PROJECT_ROOT"
        fi


        ok "Projet programmé pour suppression"

    else
        ok "Code source conservé"
    fi

fi


echo
echo "============================================================"
echo -e "${GREEN}        SSH GUARDIAN V2 DÉSINSTALLÉ${NC}"
echo "============================================================"
echo
echo "SSH reste actif."
echo "Les règles firewall SSH Guardian ont été retirées."
echo

