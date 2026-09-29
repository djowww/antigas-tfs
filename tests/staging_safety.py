"""Fail-closed guard for tests that create or mutate game/database fixtures.

Only isolated staging databases and the repository's loopback staging game
ports are accepted. Unit/self-tests do not call this function.
"""
import os
import re

_SAFE_DATABASE = re.compile(r"[a-z0-9_]{1,64}(?:_test|_qa|_staging|_stage)(?:_v[0-9]+)?\Z", re.IGNORECASE)
_PRODUCTION_TOKEN = re.compile(r"(?:^|_)(?:prod|production|live|online|official|main)(?:_|$)", re.IGNORECASE)
_STAGING_GAME_PORTS = frozenset((7176, 7186))


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
