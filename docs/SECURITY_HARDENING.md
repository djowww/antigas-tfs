# Security hardening work log

This document records safe repository changes made during the 2026-09-29 audit. All changes are on the local `security-hardening` branch. Nothing was pushed to GitHub or applied to the online server.

## Changes made

- Added `tests/staging_safety.py`: mutation probes require explicit approval, an isolated database name ending in `_test`, `_qa`, `_stage`, or `_staging` (optional `_vN`), and a dedicated staging game port (7176 or 7186). Production-like database tokens and the production game port are rejected.
- Guarded the seven mutating achievement, bestiary, ground-rarity, loot, quest-log, and rarity probes before their DB/network work. Removed production DB defaults and an external private test-protocol dependency from the Bestiary and Quest Log probes; made those modules safe to import.
- Release pending TCP connections from `ConnectionManager` when `async_accept` fails/is cancelled or services disappear during an accept callback.
- Fix the Lua watchdog time-unit mismatch: `os.mtime()` is milliseconds, so its baseline and 1-second threshold now use milliseconds consistently.
- Hardened `deploy/systemd/staging-maintenance-recovery.sh` so it attempts all three recovery actions even if one fails; it exits nonzero when any action fails.
- Added explicit `--confirm-production-deploy` gates to the five archived deployment scripts and `--confirm-production-change` gates to both production Nginx scripts. Importing the Python scripts no longer runs a deployment phase.
- Added unit/regression coverage for staging target validation and recovery behavior.
- Added `.github/workflows/security-build.yml` with release, release-hardened, ASan/UBSan, and separate TSan builds, plus Lua/Python and Windows launcher checks; added C++/C# CodeQL and full-history Gitleaks workflows and monthly Dependabot checks. Third-party Actions are pinned to full SHAs.

## How to run safe regression tests

From `tests/`:

```sh
python -m unittest test_load_test test_staging_safety test_recovery_script -v
```

The mutating probes additionally support local self-tests where available. Never set `ANTIGAS_ALLOW_STAGING_MUTATIONS=1` outside a reviewed isolated staging window. These guards reduce accidental targeting; they do not replace OS/database isolation, credentials scoped to staging, firewall restrictions, or operator review.

The production confirmation flags only prevent accidental invocation; they are not authorization, do not validate backups, and do not make an old release safe to deploy. No flag was supplied during this audit. New GitHub workflows are source-reviewed only; they need a GitHub run, and CodeQL availability depends on repository visibility/plan and settings.

## Deferred changes

No server protocol, gameplay, login format, database schema, production configuration, firewall, TLS, account hash, or client behavior was changed. The Lua watchdog change is diagnostic/performance code and still needs LuaJIT staging validation. Connection-cap values require traffic measurements; password hashing needs a compatibility plan; C++ task exception isolation needs semantic review. Those issues and external validation gaps are tracked in [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md).
