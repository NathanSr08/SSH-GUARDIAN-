#!/usr/bin/env bash

set -u

SERVICES=(
    collector
    geoip
    mfa
    security
    firewall
    storage
    control
    telegram
    api
    panel
)

LINES="${SG_LOG_LINES:-15}"
REFRESH="${SG_LOG_REFRESH:-2}"

cleanup() {
    printf '\033[?25h'
}

handle_exit() {
    exit 130
}

trap cleanup EXIT
trap handle_exit INT TERM

printf '\033[?25l'

while true
do
    clear

    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║              SSH GUARDIAN — JOURNAL SYSTEMD              ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo
    echo "Rafraîchissement : ${REFRESH}s | ${LINES} dernières lignes/service"
    echo "Ctrl+C pour quitter"
    echo

    for service in "${SERVICES[@]}"
    do
        unit="ssh-guardian@${service}.service"

        printf "━━━━━━━━━━━━━━━━━━━ %-10s ━━━━━━━━━━━━━━━━━━━\n" \
            "$(echo "$service" | tr '[:lower:]' '[:upper:]')"

        if systemctl is-active \
            --quiet \
            "$unit" \
            2>/dev/null
        then
            echo "● ACTIVE"
        else
            echo "○ INACTIVE"
        fi

        echo

        journalctl \
            -u "$unit" \
            -n "$LINES" \
            --no-pager \
            -o cat \
            2>/dev/null

        echo
        echo
    done

    sleep "$REFRESH"
done
