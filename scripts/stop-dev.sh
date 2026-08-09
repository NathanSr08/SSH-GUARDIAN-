#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RUN_DIR="$PROJECT_ROOT/run"

SERVICES=(
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

echo "Arrêt de SSH Guardian..."
echo


#
# 1. Arrêter les services systemd
#
for SERVICE in "${SERVICES[@]}"
do
    UNIT="ssh-guardian@${SERVICE}"

    if systemctl is-active --quiet "$UNIT" 2>/dev/null; then
        echo "Arrêt systemd : $SERVICE"
        systemctl stop "$UNIT" 2>/dev/null || true
    fi
done


#
# 2. Arrêter les processus lancés par start-dev.sh
#
for SERVICE in "${SERVICES[@]}"
do
    PIDFILE="$RUN_DIR/${SERVICE}.pid"

    if [ ! -f "$PIDFILE" ]; then
        continue
    fi

    PID="$(cat "$PIDFILE")"

    if kill -0 "$PID" 2>/dev/null; then
        echo "Arrêt dev : $SERVICE (PID $PID)"
        kill "$PID" 2>/dev/null || true

        for _ in $(seq 1 20)
        do
            if ! kill -0 "$PID" 2>/dev/null; then
                break
            fi

            sleep 0.1
        done

        if kill -0 "$PID" 2>/dev/null; then
            echo "Force kill : $SERVICE (PID $PID)"
            kill -9 "$PID" 2>/dev/null || true
        fi
    fi

    rm -f "$PIDFILE"
done


#
# 3. Nettoyer d'éventuels processus orphelins
#
for SERVICE in "${SERVICES[@]}"
do
    pkill -f "services\.${SERVICE}\.app\.main" \
        2>/dev/null || true
done


#
# 4. Nettoyer les sous-processus du collector
#
pkill -f 'journalctl -u ssh -f' \
    2>/dev/null || true


echo
echo "=============================="
echo "Vérification"
echo "=============================="

FOUND=0

for SERVICE in "${SERVICES[@]}"
do
    printf "%-12s : " "$SERVICE"

    UNIT="ssh-guardian@${SERVICE}"

    SYSTEMD_ACTIVE=false
    PROCESS_ACTIVE=false

    if systemctl is-active --quiet "$UNIT" 2>/dev/null; then
        SYSTEMD_ACTIVE=true
    fi

    if pgrep -f "services\.${SERVICE}\.app\.main" \
        >/dev/null 2>&1
    then
        PROCESS_ACTIVE=true
    fi

    if [ "$SYSTEMD_ACTIVE" = true ] || \
       [ "$PROCESS_ACTIVE" = true ]
    then
        echo "❌ ENCORE ACTIF"
        FOUND=1
    else
        echo "✅ STOPPED"
    fi
done


echo

if [ "$FOUND" -eq 0 ]; then
    echo "✅ SSH Guardian V2 complètement arrêté."
else
    echo "⚠️ Certains services sont encore actifs."
fi
