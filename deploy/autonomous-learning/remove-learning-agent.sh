#!/bin/sh
set -eu

mode="${1:---dry-run}"
unit="autonomous-learning-agent.service"
# Shared Python modules are intentionally retained: the runner imports them
# safely and disables the bridge when no learning socket is configured.
paths="/etc/systemd/system/$unit /opt/autonomous-players/tools/autonomous_learning_agent.py /etc/autonomous-learning/learning-agent.json /var/lib/autonomous-learning/status.json /run/autonomous-learning-agent"
preserved="/var/lib/autonomous-learning/learning.db /var/lib/autonomous-learning/learning.db-wal /var/lib/autonomous-learning/learning.db-shm /var/lib/autonomous-learning/learning.neural.json"

case "$mode" in
  --dry-run)
    printf 'remove: %s\npreserve learned state: %s\n' "$paths" "$preserved"
    ;;
  --apply)
    unit_state=$(systemctl is-active "$unit" 2>/dev/null || true)
    case "$unit_state" in
      active|activating|reloading|deactivating)
        systemctl stop "$unit"
        ;;
      inactive|failed)
        ;;
      *)
        printf 'cannot verify that %s is stopped (state: %s); refusing removal\n' "$unit" "$unit_state" >&2
        exit 1
        ;;
    esac
    systemctl disable "$unit" 2>/dev/null || true
    rm -f /etc/systemd/system/$unit /opt/autonomous-players/tools/autonomous_learning_agent.py /etc/autonomous-learning/learning-agent.json
    rm -f /var/lib/autonomous-learning/status.json
    rm -rf /run/autonomous-learning-agent
    systemctl daemon-reload
    ;;
  *)
    printf 'usage: %s [--dry-run|--apply]\n' "$0" >&2
    exit 2
    ;;
esac
