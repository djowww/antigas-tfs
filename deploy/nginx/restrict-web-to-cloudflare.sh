#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

IP_FILE=/etc/nginx/conf.d/antigas-cloudflare-realip.conf
test -f "$IP_FILE"
mapfile -t IPV4_RANGES < <(awk '$1 == "set_real_ip_from" && $2 !~ /:/ { gsub(";", "", $2); print $2 }' "$IP_FILE")
mapfile -t IPV6_RANGES < <(awk '$1 == "set_real_ip_from" && $2 ~ /:/ { gsub(";", "", $2); print $2 }' "$IP_FILE")
if [[ ${#IPV4_RANGES[@]} -lt 15 || ${#IPV6_RANGES[@]} -lt 7 ]]; then
  echo "Cloudflare range list is incomplete; firewall unchanged." >&2
  exit 1
fi

BACKUP_DIR="/root/backups/antigas-site-firewall-$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -a /etc/ufw/user.rules "$BACKUP_DIR/"
cp -a /etc/ufw/user6.rules "$BACKUP_DIR/"
restricted=0
restore_public_web_access() {
  status=$?
  if [[ $restricted -eq 1 ]]; then
    ufw allow 80/tcp || true
    ufw allow 443/tcp || true
    echo "Public web rules restored after validation failure." >&2
  fi
  echo "Firewall backup: $BACKUP_DIR" >&2
  exit "$status"
}
trap restore_public_web_access ERR

# Add every Cloudflare range first; leave the existing public rules intact
# until the full IPv4/IPv6 allowlist has been verified on disk.
for cidr in "${IPV4_RANGES[@]}" "${IPV6_RANGES[@]}"; do
  for port in 80 443; do
    ufw allow proto tcp from "$cidr" to any port "$port" comment 'Cloudflare web'
  done
done

for cidr in "${IPV4_RANGES[@]}"; do
  for port in 80 443; do
    grep -q -- "--dport $port -s $cidr " /etc/ufw/user.rules
  done
done
for cidr in "${IPV6_RANGES[@]}"; do
  for port in 80 443; do
    grep -q -- "--dport $port -s $cidr " /etc/ufw/user6.rules
  done
done

restricted=1
ufw --force delete allow 80/tcp
ufw --force delete allow 443/tcp
if grep -qE -- '--dport (80|443) -j ACCEPT' /etc/ufw/user.rules /etc/ufw/user6.rules; then
  echo "Unrestricted HTTP/HTTPS firewall rule remains." >&2
  false
fi

status=$(curl --connect-timeout 10 --max-time 20 -sS -o /dev/null -w '%{http_code}' https://tibia74.tech/)
if [[ "$status" != 200 ]]; then
  echo "Public site check returned HTTP $status; reopening web ports." >&2
  false
fi

restricted=0
trap - ERR
echo "HTTP/HTTPS origin is now restricted to Cloudflare. Site returned HTTP $status."
echo "Backup: $BACKUP_DIR"
