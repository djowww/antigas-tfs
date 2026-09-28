"""Prepare isolated native QA; only its bounded loopback stub is permitted."""
from pathlib import Path
from zipfile import ZipFile
import argparse
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('--archive', type=Path, required=True)
parser.add_argument('--target', type=Path, required=True)
parser.add_argument('--shipped', action='store_true')
parser.add_argument('--loopback-port', type=int, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[3]
target = args.target.resolve()
target.mkdir(parents=True, exist_ok=True)
with ZipFile(args.archive) as archive:
    archive.extractall(target)
if not args.shipped:
    for module in ('game_groundrarity', 'game_interface', 'game_inventory'):
        shutil.copytree(root / 'Cliente/modules' / module, target / 'modules' / module, dirs_exist_ok=True)
state = target / 'qa-state'
for folder in ('appdata', 'localappdata', 'userprofile'):
    (state / folder).mkdir(parents=True, exist_ok=True)
init = (target / 'init.lua').read_text(encoding='utf-8')
if not 1024 <= args.loopback_port <= 65535:
    raise ValueError('Invalid ephemeral loopback port')
prefix = '''GROUND_REAL_REPORT = "ground-rarity-ui-real-report.txt"
local function blockedNetwork() error('Offline QA blocks network access') end
local nativeLoginWorld = g_game.loginWorld
function GROUND_BOOT_NATIVE_PLAYER()
  nativeLoginWorld('0', 'offline-qa', 'Offline QA', '127.0.0.1', LOOPBACK_PORT, 'OfflineQA', '', '')
end
g_game.loginWorld = blockedNetwork
for _, name in ipairs({'get', 'post', 'download', 'ws'}) do
  if g_http[name] then g_http[name] = blockedNetwork end
end
'''.replace('LOOPBACK_PORT', str(args.loopback_port))
init = init.replace('APP_NAME = "Antigas 7.4"', 'APP_NAME = "Antigas Ground Rarity Offline QA"')
init = init.replace('g_app.setName("Antigas 7.4")', 'g_app.setName("Antigas Ground Rarity Offline QA")')
init = init.replace('187.77.238.51:7173:772', '127.0.0.1:1:772')
init = init.replace('g_configs.loadSettings("/config.otml")', 'g_configs.loadSettings("/qa-state/ground-offline-qa-config.otml")\n  g_configs.getSettings().save = function() end')
init = init.replace('g_modules.ensureModuleLoaded("corelib")', 'g_modules.ensureModuleLoaded("corelib")\n  g_settings.save = function() end')
init = init.replace('g_modules.ensureModuleLoaded("gamelib")', 'g_modules.ensureModuleLoaded("gamelib")\n  ProtocolLogin.login = blockedNetwork')
init += '\ndofile("/ground-rarity-ui-real.lua")\n'
(target / 'init.lua').write_text(prefix + init, encoding='utf-8', newline='\n')
release = target / 'modules/client_release/release.otmod'
release.write_text(release.read_text(encoding='utf-8').replace('autoload: true', 'autoload: false'), encoding='utf-8', newline='\n')
shutil.copyfile(Path(__file__).with_name('ground-rarity-ui-real.lua'), target / 'ground-rarity-ui-real.lua')
(state / 'ground-offline-qa-config.otml').write_text('locale: en\nautologin: false\nambientLight: 100\nenableLights: false\n', encoding='utf-8')
write_state = state / 'userprofile/AppData/Roaming/OTClientV8/otclientv8/qa-state'
write_state.mkdir(parents=True, exist_ok=True)
print(target)
