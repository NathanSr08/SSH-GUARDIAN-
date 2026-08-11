#!/usr/bin/env bash

set -Eeuo pipefail

DB="data/guardian.db"
OUT_DIR="data/nmap-scans"

TOP_COUNT=10
TOP_PORTS=100

#
# Ports utilisés uniquement pour savoir rapidement
# si la cible expose quelque chose d'intéressant.
#
QUICK_PORTS="21,22,23,25,53,80,110,143,443,445,993,995,1723,3306,3389,5432,5900,6379,8080,8443"

mkdir -p "$OUT_DIR"

if ! command -v nmap >/dev/null 2>&1; then
    echo "[INFO] Installation de nmap..."
    apt-get update
    apt-get install -y nmap
fi


echo
echo "╔══════════════════════════════════════════════╗"
echo "║     SSH GUARDIAN — TOP IP ATTAQUANTES      ║"
echo "╚══════════════════════════════════════════════╝"
echo


mapfile -t IPS < <(
    sqlite3 "$DB" "
        SELECT ip
        FROM enriched_events
        WHERE ip IS NOT NULL
          AND ip != ''
          AND event_type IN (
              'ssh.login.failed',
              'ssh.login.invalid_user',
              'ssh.connection.reset',
              'ssh.connection.closed'
          )
        GROUP BY ip
        ORDER BY COUNT(*) DESC
        LIMIT $TOP_COUNT;
    "
)


if [ "${#IPS[@]}" -eq 0 ]; then
    echo "❌ Aucune IP trouvée."
    exit 0
fi


echo "🎯 ${#IPS[@]} IP à analyser"
echo


for ip in "${IPS[@]}"
do
    safe_ip="${ip//:/_}"
    outfile="$OUT_DIR/${safe_ip}.txt"

    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🌐 IP : $ip"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    #
    # ========================================================
    # ÉTAPE 1 — PRE-SCAN ULTRA RAPIDE
    # ========================================================
    #

    echo "⚡ Vérification rapide..."

    QUICK_RESULT="$(
        nmap \
            -Pn \
            -n \
            -sT \
            -p "$QUICK_PORTS" \
            --open \
            --max-retries 0 \
            --initial-rtt-timeout 250ms \
            --max-rtt-timeout 500ms \
            --host-timeout 3s \
            "$ip" \
            -oG - \
            2>/dev/null \
            || true
    )"


    if ! echo "$QUICK_RESULT" | grep -q '/open/'; then

        echo "⏭ Aucun port principal détecté rapidement."
        echo "   IP ignorée."

        continue
    fi


    echo "✅ Service exposé détecté"
    echo


    #
    # ========================================================
    # ÉTAPE 2 — SCAN 100 PORTS
    # ========================================================
    #

    echo "🔎 Scan des $TOP_PORTS ports principaux..."

    nmap \
        -Pn \
        -n \
        -sT \
        --top-ports "$TOP_PORTS" \
        --open \
        -T4 \
        --max-retries 1 \
        --initial-rtt-timeout 250ms \
        --max-rtt-timeout 750ms \
        --host-timeout 8s \
        "$ip" \
        -oN "$outfile" \
        || true

done


echo
echo "╔══════════════════════════════════════════════╗"
echo "║                SCAN TERMINÉ                 ║"
echo "╚══════════════════════════════════════════════╝"
echo
echo "📂 Résultats : $OUT_DIR"
