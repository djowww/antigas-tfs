#!/usr/bin/env bash
set -euo pipefail
[[ $(node --version) == v24.* ]]
task_root=/workspace/cloud-onboarding
mkdir -p "$task_root/logs" "$task_root/ragnarok"
cat > '/workspace/cloud-onboarding/native-env.sh' <<'ONBOARDING_HELPER_0'
#!/usr/bin/env bash
# Local Debian libraries; leave the system installation unchanged.
export PATH="/workspace/cloud-onboarding/native/usr/bin:$PATH"
export LD_LIBRARY_PATH="/workspace/cloud-onboarding/native/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PKG_CONFIG_PATH="/workspace/cloud-onboarding/native/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
export CMAKE_PREFIX_PATH="/workspace/cloud-onboarding/native/usr${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
export CPATH="/workspace/cloud-onboarding/native/usr/include:/workspace/cloud-onboarding/native/usr/include/luajit-2.1:/workspace/cloud-onboarding/native/usr/include/mariadb${CPATH:+:$CPATH}"
ONBOARDING_HELPER_0
cat > '/workspace/cloud-onboarding/install-native.sh' <<'ONBOARDING_HELPER_1'
#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
task_root=/workspace/cloud-onboarding
mkdir -p "$task_root/apt/lists/partial" "$task_root/apt/archives/partial" "$task_root/apt/log" "$task_root/native/pkgconfig"
cat > "$task_root/apt/sources.list" <<'EOF'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie-updates main
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://security.debian.org/debian-security trixie-security main
EOF
apt_options=(
  -o "Dir::State::lists=$task_root/apt/lists"
  -o "Dir::Cache::archives=$task_root/apt/archives"
  -o "Dir::Log=$task_root/apt/log"
  -o "Dir::Etc::sourcelist=$task_root/apt/sources.list"
  -o Dir::Etc::sourceparts=-
  -o Dir::Etc::parts=-
  -o Dir::Etc::main=/dev/null
  -o "APT::Sandbox::User=$(id -un)"
  -o Debug::NoLocking=1
  -o APT::Update::Error-Mode=any
)
# APT verifies signed metadata and package hashes before local extraction.
/usr/bin/apt-get "${apt_options[@]}" update
/usr/bin/apt-get "${apt_options[@]}" --download-only --reinstall --no-install-recommends -y install \
  cmake cmake-data pkg-config librhash1 libuv1t64 \
  libboost-system-dev libboost-filesystem-dev libboost1.83-dev \
  libboost-system1.83-dev libboost-filesystem1.83-dev libboost-atomic1.83-dev \
  libboost-system1.83.0 libboost-filesystem1.83.0 libboost-atomic1.83.0 \
  libluajit-5.1-dev libluajit-5.1-2 libluajit-5.1-common luajit \
  libpugixml-dev libpugixml1v5 libmariadb-dev libmariadb-dev-compat libmariadb3 \
  libgmp-dev libgmp10
python3 - "${apt_options[@]}" <<'PY'
import hashlib
import re
import subprocess
import sys
from pathlib import Path
root = Path('/workspace/cloud-onboarding/native')
options = sys.argv[1:]
archives = {}
for archive in (root.parent / 'apt/archives').glob('*.deb'):
    package, architecture, version = subprocess.check_output([
        'dpkg-deb', '--show', '--showformat=${Package}\t${Architecture}\t${Version}', str(archive)
    ], text=True).split('\t')
    archives.setdefault((package, architecture), {})[version] = archive
selected = []
manifest_lines = []
for (package, architecture), versions in sorted(archives.items()):
    name = f'{package}:{architecture}'
    policy = subprocess.check_output(['/usr/bin/apt-cache', *options, 'policy', name], text=True)
    match = re.search(r'^\s*Candidate:\s*(\S+)', policy, re.MULTILINE)
    if not match or match[1] not in versions:
        raise SystemExit(f'No current verified candidate archive for {name}')
    version = match[1]
    archive = versions[version]
    metadata = subprocess.check_output(['/usr/bin/apt-cache', *options, 'show', f'{name}={version}'], text=True)
    expected = re.search(r'^SHA256:\s*([a-f0-9]{64})$', metadata, re.MULTILINE)
    actual = hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest()
    if not expected or actual != expected[1]:
        raise SystemExit(f'Package checksum mismatch for {name}')
    selected.append(archive)
    manifest_lines.append(f'{name}\t{version}\t{actual}\n')
manifest = ''.join(manifest_lines)
manifest_file = root / 'packages.tsv'
if (manifest_file.exists() and sorted(manifest_file.read_text().splitlines()) != sorted(manifest.splitlines())) or (
    not manifest_file.exists() and Path('/workspace/antigas-tfs/build/CMakeCache.txt').exists()
):
    (root.parent / '.native-rebuild-required').write_text('Native packages changed; rebuild affected outputs.\n')
for archive in selected:
    subprocess.run(['dpkg-deb', '-x', str(archive), str(root)], check=True)
for source in (root / 'usr/lib/x86_64-linux-gnu/pkgconfig').glob('*.pc'):
    content = source.read_text().replace('=/usr', '=' + str(root / 'usr'))
    (root / 'pkgconfig' / source.name).write_text(content)
manifest_file.write_text(manifest)
print(f'Verified and extracted {len(selected)} current Debian packages.')
PY
source "$task_root/native-env.sh"
cmake --version
luajit -v
pkg-config --modversion luajit pugixml mysqlclient gmp
ONBOARDING_HELPER_1
cat > '/workspace/cloud-onboarding/build-antigas.sh' <<'ONBOARDING_HELPER_2'
#!/usr/bin/env bash
set -euo pipefail
source /workspace/cloud-onboarding/native-env.sh
cd /workspace/antigas-tfs
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
  -DTFS_BUILD_RARITY_TESTS=ON \
  -DTFS_BUILD_LUA_WATCHDOG_TESTS=ON \
  -DTFS_BUILD_LUA_ENVIRONMENT_LIFECYCLE_TESTS=ON \
  -DTFS_BUILD_STATUS_QUERY_TESTS=ON \
  -DTFS_BUILD_REMOTE_LOG_RATE_LIMITER_TESTS=ON \
  -DTFS_BUILD_SCHEDULER_TESTS=ON \
  -DTFS_BUILD_CALLBACK_GENERATION_TESTS=ON \
  -DTFS_BUILD_QUEUE_METRICS_TESTS=ON \
  -DTFS_BUILD_SCHEDULER_SHUTDOWN_TESTS=ON \
  -DTFS_BUILD_SCRIPT_READER_TESTS=ON \
  -DTFS_BUILD_SCRIPT_ENVIRONMENT_INDEX_TESTS=ON \
  -DTFS_BUILD_CONNECTION_OUTPUT_QUEUE_TESTS=ON \
  -DTFS_BUILD_CONNECTION_ADMISSION_TESTS=ON \
  -DTFS_BUILD_LOGIN_GATE_TESTS=ON \
  -DTFS_BUILD_AUTHENTICATION_TESTS=ON \
  -DTFS_BUILD_TALKACTION_AUTHORIZATION_TESTS=ON \
  -DTFS_BUILD_DISPATCHER_FAILFAST_TESTS=ON \
  -DTFS_BUILD_SQL_IDENTIFIER_TESTS=ON \
  -DTFS_BUILD_DATABASE_ESCAPE_TESTS=ON \
  -DTFS_BUILD_DATABASE_RECOVERY_POLICY_TESTS=ON \
  -DTFS_BUILD_SCRIPT_FILENAME_TESTS=ON \
  -DTFS_BUILD_LOCALTIME_TESTS=ON \
  -DTFS_BUILD_NETWORKMESSAGE_TESTS=ON
if [[ -f /workspace/cloud-onboarding/.native-rebuild-required ]]; then
  cmake --build build --clean-first --parallel 2
  rm /workspace/cloud-onboarding/.native-rebuild-required
else
  cmake --build build --parallel 2
fi
ONBOARDING_HELPER_2
cat > '/workspace/cloud-onboarding/start-fifabet.sh' <<'ONBOARDING_HELPER_3'
#!/usr/bin/env bash
set -euo pipefail
cd /workspace/fifabet-arena
export FIFABET_HOST=127.0.0.1
export FIFABET_PORT=5174
export FIFABET_DATA_DIR=/workspace/cloud-onboarding/fifabet-data
export FIFABET_PAYMENT_MODE=unconfigured
exec node backend/server.mjs
ONBOARDING_HELPER_3
cat > '/workspace/cloud-onboarding/ragnarok/pnpm.sh' <<'ONBOARDING_HELPER_4'
#!/usr/bin/env bash
set -euo pipefail
export XDG_CONFIG_HOME=/workspace/cloud-onboarding/ragnarok/xdg-config
export XDG_DATA_HOME=/workspace/cloud-onboarding/ragnarok/xdg-data
export XDG_CACHE_HOME=/workspace/cloud-onboarding/ragnarok/xdg-cache
exec /workspace/cloud-onboarding/ragnarok-tools/node_modules/.bin/pnpm "$@"
ONBOARDING_HELPER_4
cat > '/workspace/cloud-onboarding/ragnarok/install.sh' <<'ONBOARDING_HELPER_5'
#!/usr/bin/env bash
set -euo pipefail
state=/workspace/cloud-onboarding/ragnarok
tools=/workspace/cloud-onboarding/ragnarok-tools
[[ $(node --version) == v24.* ]]
mkdir -p "$tools" "$state/npm-cache" "$state/pnpm-store" "$state/logs"
npm --cache "$state/npm-cache" install --prefix "$tools" \
  --no-audit --no-fund --ignore-scripts --save-exact pnpm@11.25.0
cd /workspace/ragnarok-old-times-idle/idle
bash "$state/pnpm.sh" install --frozen-lockfile --store-dir "$state/pnpm-store"
bash "$state/pnpm.sh" build
unset DOCKER_HOST DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH
docker --host=unix:///var/run/docker.sock info >/dev/null
image_id=sha256:ab3dff582d246358b6f6a1f6212f29ac64609fad883eb3dcfb0a89f6f7d0700e
if ! docker --host=unix:///var/run/docker.sock image inspect "$image_id" >/dev/null 2>&1; then
  if [[ -s "$state/mariadb-image.tar" ]]; then
    docker --host=unix:///var/run/docker.sock image load --input "$state/mariadb-image.tar"
  else
    docker --host=unix:///var/run/docker.sock pull mariadb@sha256:1292844148b311e4ed4300022a996d39083f415a963e970cf47cad1b3b18e3a6
  fi
fi
docker --host=unix:///var/run/docker.sock image inspect "$image_id" >/dev/null
if [[ ! -s "$state/mariadb-image.tar" ]]; then
  docker --host=unix:///var/run/docker.sock image save --output "$state/mariadb-image.tar" "$image_id"
fi
ONBOARDING_HELPER_5
cat > '/workspace/cloud-onboarding/ragnarok/db.sh' <<'ONBOARDING_HELPER_6'
#!/usr/bin/env bash
set -euo pipefail
unset DOCKER_HOST DOCKER_CONTEXT DOCKER_TLS DOCKER_TLS_VERIFY DOCKER_CERT_PATH
docker_cmd=(docker --host=unix:///var/run/docker.sock)
# Official mariadb:11.4 repository digest captured during pull:
# sha256:1292844148b311e4ed4300022a996d39083f415a963e970cf47cad1b3b18e3a6
# Docker archives can omit repository digests, so use the immutable local image ID.
image_id=sha256:ab3dff582d246358b6f6a1f6212f29ac64609fad883eb3dcfb0a89f6f7d0700e
"${docker_cmd[@]}" info >/dev/null
if ! "${docker_cmd[@]}" image inspect "$image_id" >/dev/null 2>&1; then
  "${docker_cmd[@]}" image load --input /workspace/cloud-onboarding/ragnarok/mariadb-image.tar
fi
"${docker_cmd[@]}" image inspect "$image_id" >/dev/null
if "${docker_cmd[@]}" container inspect codex-ragnarok-db >/dev/null 2>&1; then
  "${docker_cmd[@]}" start codex-ragnarok-db >/dev/null
else
  "${docker_cmd[@]}" run -d --name codex-ragnarok-db --restart unless-stopped \
    -p 127.0.0.1:3307:3306 \
    -e MARIADB_DATABASE=hercules -e MARIADB_ALLOW_EMPTY_ROOT_PASSWORD=1 \
    --mount type=volume,src=codex-ragnarok-db-data,dst=/var/lib/mysql \
    --health-cmd 'healthcheck.sh --connect --innodb_initialized' \
    --health-interval=3s --health-timeout=3s --health-retries=20 \
    "$image_id" >/dev/null
fi
for attempt in {1..60}; do
  if [[ $("${docker_cmd[@]}" inspect --format '{{.State.Health.Status}}' codex-ragnarok-db) == healthy ]]; then
    echo 'Ragnarok development MariaDB is healthy on 127.0.0.1:3307.'
    exit 0
  fi
  sleep 1
done
"${docker_cmd[@]}" logs --tail 30 codex-ragnarok-db >&2
exit 1
ONBOARDING_HELPER_6
cat > '/workspace/cloud-onboarding/ragnarok/start.sh' <<'ONBOARDING_HELPER_7'
#!/usr/bin/env bash
set -euo pipefail
repo=/workspace/ragnarok-old-times-idle
state=/workspace/cloud-onboarding/ragnarok
bash "$state/db.sh"
mkdir -p "$state/logs"
cd "$repo/idle"
export DB_HOST=127.0.0.1 DB_PORT=3307 DB_NAME=hercules DB_USER=root DB_PASSWORD=
export ASSET_ORIGIN=http://127.0.0.1:8081
launch() {
  local name=$1
  local marker=$2
  shift 2
  if [[ -s "$state/$name.pid" ]] && kill -0 "$(cat "$state/$name.pid")" 2>/dev/null && \
    [[ $(ps -p "$(cat "$state/$name.pid")" -o stat=) != Z* ]]; then
    if [[ $(ps -p "$(cat "$state/$name.pid")" -o args=) == *"$marker"* ]]; then
      return
    fi
    echo "Ignoring stale PID file for $name; the referenced process is unrelated." >&2
  fi
  nohup "$@" >"$state/logs/$name.log" 2>&1 </dev/null &
  echo "$!" >"$state/$name.pid"
}
launch assets "$repo/docker/asset-service/no-assets-server.js" env PORT=8081 node "$repo/docker/asset-service/no-assets-server.js"
launch api "$repo/idle/dist/server/index.js" env PORT=3339 node "$repo/idle/dist/server/index.js"
launch vite "$repo/idle/node_modules/vite/bin/vite.js" node "$repo/idle/node_modules/vite/bin/vite.js" --host 127.0.0.1 --port 5173 --strictPort
for attempt in {1..30}; do
  if curl --noproxy '*' -fsS http://127.0.0.1:3339/api/health >/dev/null 2>&1 && \
    curl --noproxy '*' -fsS http://127.0.0.1:5173/ >/dev/null 2>&1; then
    echo 'Ragnarok API, Vite, and development database are running.'
    node "$state/smoke.mjs"
    exit 0
  fi
  sleep 1
done
tail -n 30 "$state/logs/api.log" "$state/logs/vite.log" >&2
exit 1
ONBOARDING_HELPER_7
cat > '/workspace/cloud-onboarding/ragnarok/stop.sh' <<'ONBOARDING_HELPER_8'
#!/usr/bin/env bash
set -euo pipefail
state=/workspace/cloud-onboarding/ragnarok
repo=/workspace/ragnarok-old-times-idle
for name in api vite assets; do
  case "$name" in
    api) marker="$repo/idle/dist/server/index.js" ;;
    vite) marker="$repo/idle/node_modules/vite/bin/vite.js" ;;
    assets) marker="$repo/docker/asset-service/no-assets-server.js" ;;
  esac
  if [[ -s "$state/$name.pid" ]]; then
    pid=$(cat "$state/$name.pid")
    if kill -0 "$pid" 2>/dev/null && [[ $(ps -p "$pid" -o args=) == *"$marker"* ]]; then
      kill -TERM "$pid"
      for attempt in {1..30}; do
        if ! kill -0 "$pid" 2>/dev/null || [[ $(ps -p "$pid" -o stat=) == Z* ]]; then
          break
        fi
        sleep 1
      done
      if kill -0 "$pid" 2>/dev/null && [[ $(ps -p "$pid" -o stat=) != Z* ]]; then
        echo "$name did not stop; inspect before restarting." >&2
        exit 1
      fi
    fi
  fi
done
echo 'Stopped the Ragnarok application processes started by start.sh; database volume and container retained.'
ONBOARDING_HELPER_8
cat > '/workspace/cloud-onboarding/ragnarok/smoke.mjs' <<'ONBOARDING_HELPER_9'
import assert from 'node:assert/strict';

const api = 'http://127.0.0.1:3339';
const vite = 'http://127.0.0.1:5173';
const health = await fetch(`${api}/api/health`);
assert.equal(health.status, 200);
assert.equal((await health.json()).status, 'ok');
for (const origin of [api, vite]) {
  const page = await fetch(origin);
  assert.equal(page.status, 200);
  assert.match(await page.text(), /<div id="root"><\/div>/);
  const catalogResponse = await fetch(`${origin}/api/catalog`);
  assert.equal(catalogResponse.status, 200);
  const catalog = await catalogResponse.json();
  assert.ok(catalog.areas.length > 0);
  const sessionResponse = await fetch(`${origin}/api/session`, { method: 'POST', headers: { Origin: origin } });
  assert.equal(sessionResponse.status, 200);
  const session = await sessionResponse.json();
  assert.equal(session.state.schemaVersion, 1);
  assert.ok(Array.isArray(session.state.inventory));
}
const unavailableAsset = await fetch(`${vite}/assets/data/missing.spr`);
assert.equal(unavailableAsset.status, 404);
assert.equal((await unavailableAsset.json()).error.code, 'ASSET_UNAVAILABLE');
console.log('Smoke passed: built UI, Vite UI, proxied catalog/session with allowed origins, MariaDB health, and expected missing-client asset fallback.');
ONBOARDING_HELPER_9

bash "$task_root/install-native.sh"
mkdir -p "$task_root/fifabet-tools" "$task_root/fifabet-data"
npm install --prefix "$task_root/fifabet-tools" --cache "$task_root/npm-cache" \
  --ignore-scripts --no-audit --no-fund --save-exact pnpm@10.32.0
cd /workspace/fifabet-arena
"$task_root/fifabet-tools/node_modules/.bin/pnpm" install --frozen-lockfile \
  --store-dir "$task_root/fifabet-pnpm-store"
bash "$task_root/ragnarok/install.sh"
cd /workspace/antigas-tfs
if [[ ! -e config.lua ]]; then cp config.example.lua config.lua; fi
bash "$task_root/build-antigas.sh"
