#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
VHOST=/etc/nginx/sites-available/otclient-download
REALIP=/etc/nginx/conf.d/antigas-cloudflare-realip.conf
HEADERS=/etc/nginx/snippets/antigas-security-headers.conf
BACKUP_DIR="/root/backups/antigas-site-security-$(date -u +%Y%m%d-%H%M%S)"

test -f "$VHOST"
test -f "$SCRIPT_DIR/antigas-cloudflare-realip.conf"
test -f "$SCRIPT_DIR/antigas-security-headers.conf"
mkdir -p "$BACKUP_DIR"
cp -a "$VHOST" "$BACKUP_DIR/otclient-download"
[[ ! -e "$REALIP" ]] || cp -a "$REALIP" "$BACKUP_DIR/antigas-cloudflare-realip.conf"
[[ ! -e "$HEADERS" ]] || cp -a "$HEADERS" "$BACKUP_DIR/antigas-security-headers.conf"

restore_on_error() {
  status=$?
  cp -a "$BACKUP_DIR/otclient-download" "$VHOST"
  if [[ -f "$BACKUP_DIR/antigas-cloudflare-realip.conf" ]]; then
    cp -a "$BACKUP_DIR/antigas-cloudflare-realip.conf" "$REALIP"
  else
    rm -f "$REALIP"
  fi
  if [[ -f "$BACKUP_DIR/antigas-security-headers.conf" ]]; then
    cp -a "$BACKUP_DIR/antigas-security-headers.conf" "$HEADERS"
  else
    rm -f "$HEADERS"
  fi
  nginx -t >/dev/null 2>&1 || true
  echo "Hardening failed; previous files restored from $BACKUP_DIR" >&2
  exit "$status"
}
trap restore_on_error ERR

install -D -o root -g root -m 0644 "$SCRIPT_DIR/antigas-cloudflare-realip.conf" "$REALIP"
install -D -o root -g root -m 0644 "$SCRIPT_DIR/antigas-security-headers.conf" "$HEADERS"

python3 - "$VHOST" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
server_name = "    server_name tibia74.tech www.tibia74.tech srv2003449.hstgr.cloud;\n"
hsts = '    add_header Strict-Transport-Security "max-age=31536000" always;\n'
if hsts.strip() not in text:
    if text.count(server_name) != 2:
        raise SystemExit("Expected both Antigas TLS and HTTP server blocks; left config unchanged.")
    text = text.replace(server_name, server_name + hsts, 1)

cache = '        add_header Cache-Control "no-store" always;\n'
include = "        include snippets/antigas-security-headers.conf;\n"
import re
pattern = re.compile(r'(^        add_header Cache-Control "no-store" always;\n)(?!        include snippets/antigas-security-headers\.conf;)', re.M)
text, _ = pattern.subn(lambda match: match.group(1) + include, text)
if text.count(cache + include) != 2:
    raise SystemExit("Expected two retired-client redirect rules; left config unchanged.")

static_location = '''    location ~* \\.(?:css|js|mjs|png|jpe?g|gif|svg|webp|ico|woff2?|ttf|otf|zip|json)$ {
        include snippets/antigas-security-headers.conf;
        try_files $uri =404;
    }

'''
location = '''    location / {
        try_files $uri $uri/ =404;
    }
'''
if static_location.strip() not in text:
    if text.count(location) != 1:
        raise SystemExit("Expected the public static-file fallback; left config unchanged.")
    text = text.replace(location, static_location + location, 1)

path.write_text(text)
PY

nginx -t
systemctl reload nginx
trap - ERR
echo "Nginx hardening applied; backup: $BACKUP_DIR"
