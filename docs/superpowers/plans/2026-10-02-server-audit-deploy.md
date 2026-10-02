# Server Audit and Deployment Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Review the current Antigas TFS server repository, validate the MySQL disconnect recovery change, build a production binary, deploy it to the online server, and monitor the service journal afterward.

**Architecture:** Keep automatic replay limited to explicitly opted-in idempotent login and ban reads outside transactions. Run the repository's native, Python, Lua, and static-analysis checks, then build the Ubuntu 22.04 hardened release artifact. Use the established backup, graceful stop, atomic install, restart, health-check, and rollback procedures.

**Tech Stack:** C++11, CMake, MariaDB Connector/C, Boost, LuaJIT, CTest, Python, GitHub Actions Ubuntu 22.04 release-hardened workflow, systemd.

**Spec:** User request in this conversation; operational policy in `docs/database-recovery.md`, `docs/SECURITY_AUDIT.md`, and `.github/workflows/security-build.yml`.

## Global Constraints

- Do not expose or package `config.lua`, credentials, player data, database dumps, or raw production logs.
- Retry only idempotent read queries when explicitly opted in, only once, and only outside a transaction; never replay writes or transaction queries.
- Build the production binary with the Ubuntu 22.04 hardened flags and retain the exact tested artifact hash.
- Back up the current executable and stop gracefully before install; on rollback restore the executable only, never an older player database.
- Deploy only the reviewed artifact; confirm service status, online marker, TCP listeners, and post-deploy error logs.

## Review Focus

- MySQL error 2006 during account or character authentication: the bounded read recovery policy test must permit one reconnect/retry.
- Any SQL failure inside a transaction: recovery-policy test must forbid replay.
- A repeated transient error after reconnect: recovery-policy test must forbid a second retry.
- Non-connection SQL errors: recovery-policy test must forbid retry.
- Login and ban lookup call sites: review the opted-in calls and confirm ordinary writes retain the default no-retry behavior.
- House container removals: cover direct and nested house containers, and ensure player-held containers remain outside house-item policy while the holder is on a HouseTile.

---

### Task 1: Database read recovery regression

**Files:**
- Create: `src/database-recovery.h`
- Create: `tests/database-recovery-policy-tests.cpp`
- Modify: `CMakeLists.txt`, `src/database.cpp`, `src/database.h`, `src/iologindata.cpp`, `src/ban.cpp`, `tests/ban-lookup-tests.cpp`, `docs/database-recovery.md`

**Interfaces:**
- Produces: `databaseRecovery::shouldRetryRead(unsigned int error, unsigned int attempt, bool transactionOpen, bool optedIn)`.
- The helper returns true only for a transient connection error on attempt zero when retry is opted in and no transaction is open.

- [x] Write the failing `database-recovery-policy` native test covering MySQL error 2006, a non-connection error, a second attempt, an open transaction, and opt-in disabled.
- [x] Run the native test and confirm it fails because the recovery policy helper is absent.
- [x] Add the smallest policy helper and use it in `Database::storeQuery`; retain one reconnect attempt for the explicitly opted-in login and ban reads.
- [x] Run the focused native test and the existing login/ban regressions; expected: all pass.
- [x] Update the database recovery documentation with the tested limits.

### Task 2: Full repository review and regression gates

**Files:** all tracked server files under `src/`, `data/`, `deploy/`, `tests/`, `.github/`, and CMake/documentation.

**Interfaces:** consumes the recovery behavior from Task 1; produces an audit findings list and a reviewed release candidate.

- [x] Compare the current source and test coverage with `docs/SECURITY_AUDIT.md`, `docs/security-audit-progress-2026-09-30.md`, and the Cppcheck exception inventory.
- [x] Re-run safe Python, Lua syntax/economy, native CTest, Cppcheck, secret-scan, and workflow validation gates against the final review fixes; do not run player-data or production-mutating test harnesses. Full Python 113/113; CI Python subset 108/108; CTest 32/32; Cppcheck 2.13.0 on 74 units with 46 baseline diagnostics and zero new/stale entries; Gitleaks 8.30.1 on `src/`, `tests/`, `docs/`, and `.github/` found no leaks; `git diff --check` passed. LuaJIT syntax/six regressions, PHP syntax/site regression, and actionlint 1.7.12 had passed in the preceding audit and their inputs did not change.
- [x] Triage HouseTile authorization; add failing production-core regressions for ground and player-held direct/nested containers and correct the permission boundary.

### Task 3: Release build and artifact verification

**Files:** `.github/workflows/security-build.yml` and the release build output only.

- [x] Build the complete server with the Ubuntu 22.04 release-hardened settings and run CTest after the final authorization fix; CTest 32/32 passed.
- [x] Record the final tested binary SHA-256 and verify its ELF hardening properties: `BDDBA72E3F2183F44E84C5AA548D1E542888F6D82D6ADC68CF57C9B4E086E9CE`; ELF64 PIE, GNU_RELRO, BIND_NOW.

### Task 4: Production deployment and monitoring

**Files:** production deployment state only; preserve repository credentials and local runtime configuration.

**Preflight/deployment note (2026-10-02):** The read-only preflight passed: the active process matched the installed binary, systemd target matched, both listeners and public TCP checks succeeded, and the private backup directory was writable. The first candidate startup exceeded the initial 90-second health window; rollback restored the prior executable and verified the old service healthy. The corrected second attempt used a 300-second health window and installed the reviewed artifact successfully. Final process and installed binary hashes match `BDDBA72E3F2183F44E84C5AA548D1E542888F6D82D6ADC68CF57C9B4E086E9CE`; the online marker, listeners 7173/7174, and public TCP checks passed. The prior executable was kept in a private server-side backup; its exact location is omitted from this public plan. The full 10-minute sanitized monitor completed with 37 lines, 0 errors, 0 warnings, 0 MySQL 2006 disconnects, and 0 retry/reconnect mentions. No raw production journal lines were emitted. Live player login was not exercised.

- [x] Verify production is healthy and identify the running binary hash before changing anything; repeat the same check before any retry.
- [x] Back up the executable, perform the documented graceful stop, install the tested artifact atomically, and restart the systemd service.
- [x] Confirm the new process hash, `Server Online` marker, listeners on 7173/7174, and external TCP reachability.
- [x] Follow the service journal for 10 minutes after startup; report any error/warning entries and whether the login recovery message recurs.
- [x] If health checks fail, restore the backed-up executable and verify production returns online; do not restore database contents. The first attempt rolled back cleanly before the corrected second attempt succeeded.
