# Security hardening work log

This document records safe repository changes made during the 2026-09-29 audit. All changes are on the local `security-hardening` branch. Nothing was pushed to GitHub or applied to the online server.

## Changes made

- Added `tests/staging_safety.py`: mutation probes require explicit approval, an isolated database name ending in `_test`, `_qa`, `_stage`, or `_staging` (optional `_vN`), and a dedicated staging game port (7176 or 7186). Production-like database tokens and the production game port are rejected.
- Guarded the seven mutating achievement, bestiary, ground-rarity, loot, quest-log, and rarity probes before their DB/network work. Removed production DB defaults and an external private test-protocol dependency from the Bestiary and Quest Log probes; made those modules safe to import.
- Release pending TCP connections from `ConnectionManager` when `async_accept` fails/is cancelled or services disappear during an accept callback.
- Make the delayed `Creature:sendColorText` callback store player IDs instead of nested player userdata, then resolve live players when the callback runs.
- Fix the Lua watchdog time-unit mismatch: `os.mtime()` is milliseconds, so its baseline and 1-second threshold now use milliseconds consistently.
- Hardened `deploy/systemd/staging-maintenance-recovery.sh` so it attempts all three recovery actions even if one fails; it exits nonzero when any action fails.
- Added explicit `--confirm-production-deploy` gates to the five archived deployment scripts and `--confirm-production-change` gates to both production Nginx scripts. Importing the Python scripts no longer runs a deployment phase.
- Added unit/regression coverage for staging target validation and recovery behavior.
- Added `.github/workflows/security-build.yml` with release, release-hardened, ASan/UBSan, and separate TSan builds, plus Lua/Python and Windows launcher checks; added C++/C# CodeQL and full-history Gitleaks workflows and monthly Dependabot checks. Third-party Actions are pinned to full SHAs.
- Replaced the Market's recursive backpack inventory walk with iterative depth-first traversal and a 10,000-node limit. Reads reject an over-limit scan, and trade operations fail before asset transfer. `Container::queryAdd` prevents cycles but has no depth cap, so this bounds Market's work for nested player-controlled inventory. LuaJIT is unavailable locally; the existing CI syntax step remains unrun on GitHub.
- Updated the Lua syntax workflow to treat data/globalevents/lib/lamp_states.lua as persisted table data: it prefixes the file with return in a temporary path and compiles the wrapper without executing its contents.
- Replaced ProtocolStatus's never-pruned per-IP map with a mutex-protected steady-clock expiry cache. It stores at most 65,536 source addresses, rejects unseen addresses at capacity, and reclaims at most 256 expired addresses per query. This bounds memory and cleanup work while preserving the configured per-address timeout; the status protocol may refuse new monitors during a full active window. Added an isolated C++ regression target to the CMake/CI workflow.
- Hardened NetworkMessage cursor movement: `skipBytes` now rejects negative or unavailable ranges, and `getPreviousByte` refuses to underflow or read past its logical/buffer bounds. Added a dedicated CMake regression target for valid and malformed cursor operations.
## How to run safe regression tests

From `tests/`:

```sh
python -m unittest test_load_test test_staging_safety test_recovery_script -v
```

The mutating probes additionally support local self-tests where available. Never set `ANTIGAS_ALLOW_STAGING_MUTATIONS=1` outside a reviewed isolated staging window. These guards reduce accidental targeting; they do not replace OS/database isolation, credentials scoped to staging, firewall restrictions, or operator review.

The production confirmation flags only prevent accidental invocation; they are not authorization, do not validate backups, and do not make an old release safe to deploy. No flag was supplied during this audit. New GitHub workflows are source-reviewed only; they need a GitHub run, and CodeQL availability depends on repository visibility/plan and settings.

## Follow-up verification — 2026-09-29

- `actionlint` 1.7.12 passed against all three workflow files in `.github/workflows/`. Its Windows AMD64 release archive and the checksum file were verified against the checksum published on the official release page.
- Gitleaks 8.30.1 reported zero findings in both the complete local Git history and current working tree, with nested archive depth 2. Its Windows x32 release archive and checksum file were verified against the official release checksum. This is local repository evidence only; it does not inspect GitHub-side secrets or other clones.
- Re-ran the local Python regression suite using the workspace-bundled Python runtime: all 14 tests passed.
- After the Market inventory change, the same 14 Python tests passed again, all three workflows passed `actionlint`, the current-tree Gitleaks scan reported zero findings, and a focused source-invariant check confirmed iterative traversal, the cap, and fail-closed callers. These checks do not parse or execute Lua; LuaJIT validation remains pending.
- `git diff --check` passed. The full server build, Lua runtime validation, CI-hosted workflow, production or staging test remain unavailable in this environment.
- Compiled tests/status-query-rate-limiter-tests.cpp with Visual Studio 18 MSVC using strict warnings and ran it 20 consecutive times. Timeout boundaries, the 65,536-IP cache cap, the 256-entry cleanup budget, reclamation of 10,000 expired IPs across bounded batches, nonpositive timeouts and concurrent distinct/same-IP requests all passed. This tests the isolated cache helper; it does not build/link the server.

## Deferred changes

No wire protocol, gameplay, login format, database schema, production configuration, firewall, TLS, account hash, or client behavior was changed. The Lua watchdog change is diagnostic/performance code and still needs LuaJIT staging validation. Connection-cap values require traffic measurements; password hashing needs a compatibility plan; C++ task exception isolation needs semantic review. Status-query state has a 65,536-IP cap and incremental cleanup; a full cache may temporarily refuse unseen status clients. The separate unauthenticated game TCP accept surface still lacks measured connection admission limits. Those issues and external validation gaps are tracked in [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md).
