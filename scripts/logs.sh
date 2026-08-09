#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LOG_DIR="${SG_LOG_DIR:-$PROJECT_ROOT/logs}"

tail -f \
    "$LOG_DIR/collector.log" \
    "$LOG_DIR/geoip.log" \
    "$LOG_DIR/security.log" \
    "$LOG_DIR/firewall.log" \
    "$LOG_DIR/storage.log" \
    "$LOG_DIR/control.log" \
    "$LOG_DIR/telegram.log"
