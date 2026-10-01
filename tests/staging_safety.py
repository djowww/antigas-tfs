"""Fail-closed guard for tests that create or mutate game/database fixtures.

Only isolated staging databases and the repository's loopback staging game
ports are accepted. Unit/self-tests do not call this function.
"""
import json
import os
import re
from pathlib import Path

_SAFE_DATABASE = re.compile(r"[a-z0-9_]{1,64}(?:_test|_qa|_staging|_stage)(?:_v[0-9]+)?\Z", re.IGNORECASE)
_PRODUCTION_TOKEN = re.compile(r"(?:^|_)(?:prod|production|live|online|official|main)(?:_|$)", re.IGNORECASE)
_STAGING_GAME_PORTS = frozenset((7176, 7186))
_PRODUCTION_RSA_PUBLIC = Path("/opt/antigas-security-v26/rsa-public.json")
_STAGING_RSA_PUBLIC = Path("/opt/imperium772-staging/server/staging-rsa-public.json")
_STAGING_SERVICE_USER = "tfs74-stage"
_STAGING_ENV_FILE = "/etc/imperium772-staging.env"
_PRODUCTION_ENV_FILE = "/etc/imperium772.env"


def require_staging_target(environ=None):
    """Return (database, game_port) only after explicit, safe staging checks."""
    env = os.environ if environ is None else environ
    if env.get("ANTIGAS_ALLOW_STAGING_MUTATIONS") != "1":
        raise SystemExit("Refusing database/network mutations: set ANTIGAS_ALLOW_STAGING_MUTATIONS=1 only for an approved isolated staging run.")

    database = env.get("TFS_DB_NAME", "")
    if not _SAFE_DATABASE.fullmatch(database) or _PRODUCTION_TOKEN.search(database):
        raise SystemExit("Refusing database/network mutations: TFS_DB_NAME must be an isolated *_test, *_qa, or *_staging database name.")

    try:
        game_port = int(env.get("ANTIGAS_STAGING_GAME_PORT", ""))
    except (TypeError, ValueError):
        game_port = 0
    if game_port not in _STAGING_GAME_PORTS:
        raise SystemExit("Refusing game-server traffic: ANTIGAS_STAGING_GAME_PORT must be an approved loopback staging port (7176 or 7186).")

    return database, game_port


def require_isolated_staging_service(value):
    """Fail closed unless systemd will run staging as its isolated user/env."""
    if value("imperium772-staging", "User") != _STAGING_SERVICE_USER:
        raise SystemExit("Refusing maintenance: staging systemd unit must run as tfs74-stage.")

    env_files = value("imperium772-staging", "EnvironmentFiles")
    if _STAGING_ENV_FILE not in env_files or _PRODUCTION_ENV_FILE in env_files:
        raise SystemExit("Refusing maintenance: staging must load only its dedicated environment file.")


def pin_staging_rsa_public(environ=None, path=_STAGING_RSA_PUBLIC):
    """Force live staging probes to use the key paired with the staging server."""
    env = os.environ if environ is None else environ
    public_key = Path(path)
    if not public_key.is_file():
        raise SystemExit(f"Refusing staging login: RSA public key is missing: {public_key}")
    env["ANTIGAS_RSA_PUBLIC"] = str(public_key)
    return public_key


def rsa_public_modulus(environ=None):
    """Load the selected public modulus, keeping production as the CLI fallback."""
    env = os.environ if environ is None else environ
    path = Path(env.get("ANTIGAS_RSA_PUBLIC", str(_PRODUCTION_RSA_PUBLIC)))
    try:
        modulus = int(json.loads(path.read_text(encoding="utf-8"))["modulus"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"Could not load RSA public modulus from {path}") from error
    if modulus <= 0:
        raise SystemExit(f"Invalid RSA public modulus in {path}")
    return modulus
