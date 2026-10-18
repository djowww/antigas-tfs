#!/bin/sh
set -eu

mode="${1:---dry-run}"
unit="autonomous-learning-agent.service"
paths="/etc/systemd/system/$unit /opt/autonomous-players/tools/autonomous_learning_agent.py /opt/autonomous-players/tools/autonomous_players/learning_bridge.py /opt/autonomous-players/tools/autonomous_players/learning_protocol.py /opt/autonomous-players/tools/autonomous_players/learning_store.py /etc/autonomous-learning/learning-agent.json /var/lib/autonomous-learning /run/autonomous-learning-agent"

case "$mode" in
  --dry-run)
    printf '%s\n' "$paths"
    ;;
  --apply)
    systemctl disable --now "$unit" 2>/dev/null || true
    rm -f /etc/systemd/system/$unit /opt/autonomous-players/tools/autonomous_learning_agent.py /opt/autonomous-players/tools/autonomous_players/learning_bridge.py /opt/autonomous-players/tools/autonomous_players/learning_protocol.py /opt/autonomous-players/tools/autonomous_players/learning_store.py /etc/autonomous-learning/learning-agent.json
    rm -rf /var/lib/autonomous-learning /run/autonomous-learning-agent
    systemctl daemon-reload
    ;;
  *)
    printf 'usage: %s [--dry-run|--apply]\n' "$0" >&2
    exit 2
    ;;
esac
