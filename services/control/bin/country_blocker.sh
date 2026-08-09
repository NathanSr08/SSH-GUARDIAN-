#!/bin/bash

set -euo pipefail

STATE_DIR="${SG_STATE_DIR:-/etc/ssh-guardian}"

TRACKER_FILE="${SG_BLOCKED_COUNTRIES_FILE:-${STATE_DIR}/blocked_countries.txt}"


init_system() {
    mkdir -p "$(dirname "$TRACKER_FILE")"
    touch "$TRACKER_FILE"
}


normalize_country() {
    echo "${1:-}" \
        | tr '[:upper:]' '[:lower:]' \
        | tr -cd 'a-z'
}


block_country() {
    init_system

    local country

    country="$(normalize_country "${1:-}")"

    if [ "${#country}" -ne 2 ]; then
        echo "Erreur : code pays ISO invalide."
        exit 1
    fi

    if grep -Fxq "$country" "$TRACKER_FILE"; then
        echo "Le pays ${country^^} est deja bloque."
        exit 0
    fi

    echo "$country" >> "$TRACKER_FILE"

    sort -u \
        "$TRACKER_FILE" \
        -o "$TRACKER_FILE"

    echo "Succes ${country^^}"
}


unblock_country() {
    init_system

    local country

    country="$(normalize_country "${1:-}")"

    if [ "${#country}" -ne 2 ]; then
        echo "Erreur : code pays ISO invalide."
        exit 1
    fi

    sed -i \
        "/^${country}$/d" \
        "$TRACKER_FILE"

    echo "Debloque ${country^^}"
}


list_countries() {
    init_system
    cat "$TRACKER_FILE"
}


is_blocked() {
    init_system

    local country

    country="$(normalize_country "${1:-}")"

    grep -Fxq \
        "$country" \
        "$TRACKER_FILE"
}


case "${1:-}" in

    block)
        block_country "${2:-}"
        ;;

    unblock)
        unblock_country "${2:-}"
        ;;

    list)
        list_countries
        ;;

    is-blocked)
        is_blocked "${2:-}"
        ;;

    *)
        echo "Usage:"
        echo "  $0 block <cc>"
        echo "  $0 unblock <cc>"
        echo "  $0 list"
        echo "  $0 is-blocked <cc>"
        exit 1
        ;;

esac
