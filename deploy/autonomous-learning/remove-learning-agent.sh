#!/bin/sh
set -eu

mode="${1:---dry-run}"
unit="autonomous-learning-agent.service"
# Shared Python modules are intentionally retained: the runner imports them
# safely and disables the bridge when no learning socket is configured.
paths="/etc/systemd/system/$unit /opt/autonomous-players/tools/autonomous_learning_agent.py /etc/autonomous-learning/learning-agent.json /var/lib/autonomous-learning /run/autonomous-learning-agent"

case "$mode" in
  --dry-run)
    printf '%s\n' "$paths"
    ;;
  --apply)
    systemctl disable --now "$unit" 2>/dev/null || true
    rm -f /etc/systemd/system/$unit /opt/autonomous-players/tools/autonomous_learning_agent.py /etc/autonomous-learning/learning-agent.json
    rm -rf /var/lib/autonomous-learning /run/autonomous-learning-agent
    systemctl daemon-reload
    ;;
  *)
    printf 'usage: %s [--dry-run|--apply]\n' "$0" >&2
    exit 2
    ;;
esac
