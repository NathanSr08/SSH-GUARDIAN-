#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

mkdir -p logs run

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

export SG_PROJECT_ROOT="$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT"
export PYTHONUNBUFFERED=1


start_service() {
    NAME="$1"
    MODULE="$2"

    PIDFILE="$PROJECT_ROOT/run/${NAME}.pid"
    LOGFILE="$PROJECT_ROOT/logs/${NAME}.log"

    if [ -f "$PIDFILE" ]; then
        PID="$(cat "$PIDFILE")"

        if kill -0 "$PID" 2>/dev/null; then
            echo "$NAME déjà lancé (PID $PID)"
            return
        fi

        rm -f "$PIDFILE"
    fi

    echo "Démarrage de $NAME..."

    PYTHON="$PROJECT_ROOT/.venv/bin/python"

    if [ ! -x "$PYTHON" ]; then
        PYTHON="/usr/bin/python3"
    fi

    nohup "$PYTHON" \
        -u \
        -m "$MODULE" \
        > "$LOGFILE" 2>&1 &

    PID=$!

    echo "$PID" > "$PIDFILE"

    sleep 0.2

    if kill -0 "$PID" 2>/dev/null; then
        echo "$NAME démarré (PID $PID)"
    else
        echo "❌ $NAME a quitté immédiatement"
        tail -n 20 "$LOGFILE" 2>/dev/null || true
        rm -f "$PIDFILE"
    fi
}


start_service collector services.collector.app.main
start_service geoip services.geoip.app.main
start_service security services.security.app.main
start_service firewall services.firewall.app.main
start_service storage services.storage.app.main
start_service control services.control.app.main
start_service telegram services.telegram.app.main
start_service api services.api.app.main
start_service panel services.panel.app.main

echo
echo "=============================="
echo "SSH Guardian V2 démarré"
echo "=============================="
echo

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
    printf "%-12s : " "$SERVICE"

    PIDFILE="$PROJECT_ROOT/run/${SERVICE}.pid"

    if [ -f "$PIDFILE" ]; then
        PID="$(cat "$PIDFILE")"

        if kill -0 "$PID" 2>/dev/null; then
            echo "✅ RUNNING PID=$PID"
        else
            echo "❌ DOWN"
        fi
    else
        echo "❌ DOWN"
    fi
done
