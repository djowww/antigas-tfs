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
- Command-log filenames now fall back to the numeric player GUID when a character name is empty or contains a path separator; normal character log names remain unchanged. Added a Python source-invariant regression.
- Authenticated Antigas Coins pages now explicitly send private no-store response headers, including Pix QR images containing the payment payload. Added a source-invariant regression to the Python CI job; PHP runtime validation remains unavailable locally.
- Added `php -l` over every tracked PHP file to the content CI job. All seven tracked PHP files also passed local PHP 8.3.35 NTS syntax lint using an official portable runtime whose SHA-256 was verified; the hosted workflow remains pending.
- Bounded launcher ZIP extraction against the actual bytes emitted while decompressing, in addition to trusting declared entry sizes. A focused regression covers the exact limit and first rejected overflow byte.
- Hardened `siteTHtml` to emit only bare `strong`, `em`, `br` and `code` tags; attributes on otherwise allowed tags are removed. Added a PHP regression and wired it into the content CI job.
- Replaced 81 `assert` checks in five production deployment scripts with explicit runtime preconditions, so Python optimization cannot remove build, hash, backup, service-state or smoke-test gates. Added an optimized-interpreter regression to the Python CI suite.
- Replaced fixed `.v44-new` through `.v47-new` deployment temp names with exclusive randomized files; data is flushed and metadata/fsync operate through the open descriptor so a pre-planted symlink is not followed. Added regressions for safe replacement and the symlink case, with a hardlink fallback on Windows when symlink creation is denied.
- Removed the unused legacy `analyzersLib.lua` serializer/deserializer pair; its deserializer called `loadstring`, and normal startup already replaced both globals with the lamp-state implementations. Added a source regression for this invariant.
- Fixed `reserveScriptEnv` so the rejected 17th nested Lua callback does not increment the global environment index out of range. Added a shared 16-slot index helper and a native boundary/unwind test, included in the sanitizer CTest matrix.
- Capped each TCP connection's pending output queue at 64 `OutputMessage` objects, counting the in-flight write. Each object owns a fixed 65,500-byte buffer, so this bounds queued message buffers to roughly 4 MiB per connection; excess output closes only that slow connection. Added a native boundary test and source-order regression. The cap is a conservative safeguard pending staging traffic metrics; aggregate memory exposure from unbounded accepted connections remains a separate `NET-01` concern.
- Hardened `DatabaseManager::optimizeTables` to quote metadata-derived table identifiers by doubling embedded backticks. Normal table names keep the same SQL spelling. Added native edge-case tests and a source regression; this closes an identifier-injection surface but does not replace the wider `DB-01` audit of manual SQL construction and connection charset.
- Made all 14 assertion-based validation utilities under `tests/` refuse Python `-O` before importing dependencies or touching staging; the regression dynamically checks every such script.
- Added `.github/workflows/security-build.yml` with release, release-hardened, ASan/UBSan, and separate TSan builds, plus Lua/Python and Windows launcher checks; added C++/C# CodeQL and full-history Gitleaks workflows and monthly Dependabot checks. Third-party Actions are pinned to full SHAs.
- Replaced the Market's recursive backpack inventory walk with iterative depth-first traversal and a 10,000-node limit. Reads reject an over-limit scan, and trade operations fail before asset transfer. `Container::queryAdd` prevents cycles but has no depth cap, so this bounds Market's work for nested player-controlled inventory. A LuaJIT regression now exercises a 10,000-item nested chain and checks exact-limit acceptance and over-limit rejection; the security workflow runs it. Mocked containers do not replace staging validation of the server bindings.
- Updated the Lua syntax workflow to treat data/globalevents/lib/lamp_states.lua as persisted table data: it prefixes the file with return in a temporary path and compiles the wrapper without executing its contents.
- Replaced ProtocolStatus's never-pruned per-IP map with a mutex-protected steady-clock expiry cache. It stores at most 65,536 source addresses, rejects unseen addresses at capacity, and reclaims at most 256 expired addresses per query. This bounds memory and cleanup work while preserving the configured per-address timeout; the status protocol may refuse new monitors during a full active window. Added an isolated C++ regression target to the CMake/CI workflow.
- Hardened NetworkMessage cursor movement: `skipBytes` now rejects negative or unavailable ranges, and `getPreviousByte` refuses to underflow or read past its logical/buffer bounds. Added a dedicated CMake regression target for valid and malformed cursor operations.
- Fixed ScriptReader's over-depth include rejection so the rejected fourth include is removed from the depth counter before the valid three-file stack is unwound. Added an isolated CTest covering rejection, cleanup and reuse.
- Centralized local calendar conversion: Windows uses `localtime_s`; POSIX copies `std::localtime` results under a mutex. Date strings, command logs and global-event timer setup use the helper. An eight-thread regression with 40,000 conversions passed locally on MSVC and is wired into CTest and sanitizer CI jobs.
- Hardened OTCv8 new-walking parsing against truncated and all-invalid direction lists before scheduling game work. The dispatcher callback also checks the list before reading its first direction; added a dedicated CMake regression target.
- Added an optional Clang/libFuzzer target for NetworkMessage cursor operations and the OTCv8 walking parser. Its separate Ubuntu job runs with ASan/UBSan, seeded valid/truncated/over-limit inputs, a 30-second smoke budget, and uploads crash artifacts plus the mutated corpus when the job fails.
- Added a strict `NetworkMessage::isReadPositionValid` check and routed packet-derived dispatcher tasks through guarded overloads. Truncated text, house-access and extended-opcode messages can no longer enqueue mutations before the packet-level disconnect check.
- Fixed `Economy.inventory` traversal of sparse containers: empty slots returned by `Container:getItem` are skipped instead of dereferenced as nil, and the scan cap now rejects the first node beyond 10,000. Added `tests/economy-inventory-tests.lua` for sparse/nested containers and exact scan-limit behavior; the LuaJIT CI content job runs it.
- Added `BoundedContentReader` to cap manifest response bytes during streaming, including when the HTTP response has no trustworthy `Content-Length`; the helper regression accepts exactly 64 KiB and rejects a 64 KiB + 1 byte response. The launcher now checks a local manifest's file size before deserializing it.
- Initialize and release MySQL client thread-specific state in `DatabaseTasks::threadMain`; async queries use a database handle created on the dispatcher, so the worker must initialize its own client TLS. Initialization failure now stops that worker instead of calling MySQL APIs without the required thread state. Added a static source-invariant regression to the CI Python suite.
- Bound scheduler tombstone retention by compacting the priority queue when cancelled tasks reach the active queued-task count, and after active tasks expire if the threshold is crossed. Preserve the original heap and active event IDs; wake the scheduler when a compaction removes entries, and destroy removed task closures outside the queue mutex. Compaction allocation failure falls back to the existing lazy expiry. Added a native 10,000-task queue regression and enabled it in the sanitizer/test workflow.
- Avoid a scheduler task lifetime race in `Scheduler::addEvent`: copy the event ID before publishing the raw task pointer to the worker, then return only the copied value after unlocking. Added a source-invariant regression for the publish/unlock/return order.

Enable the isolated C++ regressions when configuring the server build, then build and run CTest:

```sh
cmake -S . -B build \
  -DTFS_BUILD_RARITY_TESTS=ON \
  -DTFS_BUILD_STATUS_QUERY_TESTS=ON \
  -DTFS_BUILD_SCHEDULER_TESTS=ON \
  -DTFS_BUILD_SCRIPT_ENVIRONMENT_INDEX_TESTS=ON \
	-DTFS_BUILD_CONNECTION_OUTPUT_QUEUE_TESTS=ON \
  -DTFS_BUILD_NETWORKMESSAGE_TESTS=ON
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure
```

## How to run safe regression tests

From `tests/`:

```sh
python -m unittest test_load_test test_staging_safety test_recovery_script test_database_task_thread_affinity test_scheduler_lifetime test_report_bug_path test_dispatcher_shutdown_order test_connection_shutdown_serialization test_lamp_state_parser -v
```

From the repository root, with LuaJIT 2.1 installed:

```sh
luajit tests/economy-inventory-tests.lua
luajit tests/lamp-state-parser-tests.lua
luajit tests/rarity-economy-tests.lua
```

The mutating probes additionally support local self-tests where available. Never set `ANTIGAS_ALLOW_STAGING_MUTATIONS=1` outside a reviewed isolated staging window. These guards reduce accidental targeting; they do not replace OS/database isolation, credentials scoped to staging, firewall restrictions, or operator review.

The protocol fuzz target requires Clang/libFuzzer and the server's CMake dependencies. The CI job is the reference invocation; it seeds valid, truncated, over-limit, and cursor-past-end messages, fuzzes with ASan/UBSan for 30 seconds, and uploads crash artifacts and the mutated corpus on failure.

The production confirmation flags only prevent accidental invocation; they are not authorization, do not validate backups, and do not make an old release safe to deploy. No flag was supplied during this audit. New GitHub workflows are source-reviewed only; they need a GitHub run, and CodeQL availability depends on repository visibility/plan and settings.

## Follow-up verification — 2026-09-29

- `actionlint` 1.7.12 passed against all three workflow files in `.github/workflows/`. Its Windows AMD64 release archive and the checksum file were verified against the checksum published on the official release page.
- Gitleaks 8.30.1 reported zero findings in both the complete local Git history and current working tree, with nested archive depth 2. Its Windows x32 release archive and checksum file were verified against the official release checksum. This is local repository evidence only; it does not inspect GitHub-side secrets or other clones.
- Re-ran the local Python regression suite using the workspace-bundled Python runtime: all 14 tests passed.
- At that checkpoint, after the Market inventory change, the same 14 Python tests passed again, all three workflows passed `actionlint`, the current-tree Gitleaks scan reported zero findings, and a focused source-invariant check confirmed iterative traversal, the cap, and fail-closed callers. LuaJIT validation was pending at the time; a later follow-up below records native parsing and tests.
- `git diff --check` passed. The full server build, Lua runtime validation, CI-hosted workflow, production or staging test remain unavailable in this environment.
- Compiled tests/status-query-rate-limiter-tests.cpp with Visual Studio 18 MSVC using strict warnings and ran it 20 consecutive times. Timeout boundaries, the 65,536-IP cache cap, the 256-entry cleanup budget, reclamation of 10,000 expired IPs across bounded batches, nonpositive timeouts and concurrent distinct/same-IP requests all passed. This tests the isolated cache helper; it does not build/link the server.
- At that checkpoint, the new Economy inventory regression source was wired into CI but could not yet be executed locally. A later follow-up below records its successful run in a locally built LuaJIT; the hosted workflow remains unrun.
- The launcher Release build passed with zero warnings/errors, and the standalone bounded-read regression passed locally. Its GitHub Windows job is source-configured but has not run from this checkout.

## Follow-up verification — 2026-09-29 (database thread initialization)

- The worker now initializes MySQL client thread-specific state before any async query and releases it before the worker exits. `Database::databaseLock` serializes calls that share the handle with the dispatcher during shutdown.
- All 15 local Python regression tests passed, including the new source-invariant check; all three workflows passed `actionlint`; `git diff --check` passed.
- This Windows environment has MSVC but lacks the full server dependency/build chain and a reachable staging database, so the changed C++ server code and actual MySQL/MariaDB threaded behavior have not been compiled or exercised here. The source-level test only guards call ordering and cleanup placement.

## Follow-up verification — 2026-09-29 (scheduler cancellation retention)

- The isolated scheduler queue regression compiled with Visual Studio 18 MSVC using `/W4 /WX` and passed 20 consecutive runs. It checks the compaction threshold, cancelled-callback release, due-time heap order, empty-queue behavior, and removal of 5,000 stale entries from a 10,000-task queue.
- The test target is enabled in all server CI build variants, including separate ASan/UBSan and TSan jobs. CMake and the project's Linux/PkgConfig dependency chain are unavailable locally; compiling `src/scheduler.cpp` directly with MSVC stops at missing `boost/asio.hpp`. Therefore integration with the full server and race behavior still require GitHub Linux CI or isolated staging.
- The Python suite (15 tests), `actionlint` (all three workflows), `git diff --check`, and a full current-tree Gitleaks scan passed. The scan covered about 97 MB and found no leaks.
- A local MSVC AddressSanitizer build of the isolated queue test could not link because this Visual Studio installation lacks `clang_rt.asan_static_runtime_thunk-x86_64.lib`. The sanitizer workflow remains configured, but no sanitizer result is claimed for this change. No before/after load benchmark or live staging test was available.

## Follow-up verification — 2026-09-29 (scheduler task lifetime)

- `Scheduler::addEvent` now snapshots the ID before exposing the task to the scheduler thread. This prevents reading `task` after it may have been dispatched and destroyed; the 10 ms output-message timer demonstrates a short-delay caller in production code.
- The new Python source-invariant test passed with the full 16-test local Python suite. It checks that the ID copy precedes queue publication and that the task pointer is not dereferenced after `eventLock` is released. This does not reproduce the scheduling race dynamically.
- Full server compilation and TSan remain pending because CMake/Boost and the Linux server dependency chain are unavailable locally.

## Follow-up verification — 2026-09-29 (bug report path)

- `Player:onReportBug` preserves the existing per-character report filename for ordinary names. If a name contains `/` or `\\`, it falls back to the player's numeric GUID; the character name remains in the report contents.
- Added a Python source-invariant regression and wired it into the Python CI job. It checks source behavior rather than invoking the Lua handler; all tracked Lua files have since passed LuaJIT syntax compilation, but this callback still has no dedicated runtime test. Existing report files continue to receive reports for names without path separators.
- All 17 local Python regressions passed, all three GitHub workflows passed `actionlint`, and `git diff --check` passed. The validator used by the public character-registration site is private/outside this checkout, so legacy/imported name constraints remain unverified.
- Gitleaks scanned approximately 96.75 MB of the current checkout and reported no leaks. This local scan does not inspect hosted repositories, deployment files, or other clones.

## Follow-up verification — 2026-09-29 (dispatcher shutdown barrier)

- Normal and Windows console shutdown now append the final cleanup task and change dispatcher admission to `CLOSING` while holding the same queue mutex. Work accepted before this barrier remains ahead of cleanup; later scheduler/database callbacks are rejected and their tasks are deleted by the existing admission path.
- Added source-invariant regressions for the atomic queue transition and both shutdown call sites, then added them to the CI Python suite. All 19 local Python regressions passed, all three workflows passed `actionlint`, and `git diff --check` passed.
- Full server compilation and concurrent shutdown/TSan validation remain pending because CMake/Boost are unavailable locally. The regression is a source-order check, not a runtime thread test.

## Follow-up verification — 2026-09-29 (connection shutdown serialization)

- `ServiceManager::stop` now posts one I/O handler that closes all listeners first, then closes all tracked connections on the same single `io_service.run()` thread. `ConnectionManager::closeAll` swaps the registry under its mutex, releases that mutex, then marks and closes each connection under `connectionLock`.
- Added Python source-invariant checks for listener-before-socket ordering, per-connection locking, and avoiding global/connection lock inversion. Runtime I/O cancellation ordering and TSan still require a full server build and isolated staging.
- All 21 local Python regression tests passed, all three workflows passed `actionlint`, and `git diff --check` passed. The test asserts source ordering only and does not substitute for a concurrent runtime test.
- Gitleaks scanned approximately 96.77 MB of the checkout and reported no leaks; this does not inspect hosted secrets, production deployment files, or other clones.

## Follow-up verification — 2026-09-29 (lamp-state parser)

- Replaced executable `loadstring` parsing of persisted lamp states with a data-only parser for the existing `Position(x, y, z) = itemId` serialization. It validates map bounds and known lamp IDs, rejects duplicate/malformed entries, scans linearly without copying the remaining file for each entry, and caps parsing at 8 MiB and 100,000 entries; file reads are bounded too.
- A local read-only check confirmed the checked-in persistence file is 3,420 bytes with 90 canonical entries, all within coordinate/floor bounds and using IDs from the lamp map. Added a LuaJIT regression that tests this real fixture, round-tripping, malformed inputs, code-execution rejection, byte and entry limits; the GitHub LuaJIT job invokes it.
- The 22-test Python suite, `actionlint` on all three workflows, and parsing of all 33 tracked Python files passed locally. Built upstream LuaJIT 2.1.1788856981 for x64 from the [official source repository](https://luajit.org/download.html) using the [official MSVC build instructions](https://luajit.org/install.html) in a temporary directory; the lamp-state and economy inventory regressions passed, and all 750 tracked Lua files passed LuaJIT bytecode compilation. This does not substitute for the hosted workflow or an in-server Lua test.
- The protocol fuzzer entrypoint compiled and linked with MSVC and ran the four seed cases plus 256 deterministic input lengths. Existing C4244 in `position.h` required suppression for this isolated smoke harness; this is not a coverage-guided fuzz run. The Clang/libFuzzer ASan/UBSan CI job passes `actionlint`, but has not run on GitHub.

## Follow-up verification — 2026-09-29 (deployment temp files)

- The four legacy deploy helpers now use exclusive randomized same-directory temporary files and descriptor-based copy/metadata/fsync before atomic replacement. No deployment phase was run.
- All 30 local Python tests passed, including atomic replacement for every helper, flush-before-fsync order, and protection against a pre-planted legacy path. Windows denied symlink creation with `WinError 1314`; the test used a hardlink fallback. The actual symlink fixture is available to Linux CI, which has not run from this checkout. All six deployment-precondition tests also passed under `python -O`.
- `actionlint` passed all three workflows, AST parsing passed all 35 tracked Python files, Gitleaks found no leaks in a ~96.85 MB working-tree scan, and `git diff --check` passed. Production directory ownership and permissions still require a host-side audit.

## Follow-up verification — 2026-09-29 (legacy Lua deserializer)

- Removed the unused analyzer serializer/deserializer pair from `analyzersLib.lua`; it generated function source expressions and evaluated arbitrary strings with `loadstring`. The in-repository caller search was empty, and `data/lib/lib.lua` loads the `lamp_states.lua` implementations after `core.lua`; `Player.sendOpcode` still resolves the same active global serializer at runtime.
- The source regression verifies the legacy pair is absent and checks the bootstrap order. All 31 Python regressions, LuaJIT syntax/loadfile, the lamp-state parser regression, and a standalone bootstrap smoke passed. A fresh Lua `loadstring(...)` scan found no calls, and Gitleaks reported no findings in a ~96.86 MB working-tree scan. No Lua protocol or gameplay data changed; live server initialization has not been tested in staging.

## Follow-up verification — 2026-09-29 (Lua callback stack bound)

- A failed 17th reservation previously left the global index at 16, so a later callback unwind could index beyond the 16-entry array. The shared index helper now refuses overflow without changing state, and reset guards the array access while keeping the prior unwind order.
- The native capacity regression compiled with MSVC `/W4 /WX` and passed. It fills 16 entries, verifies the 17th fails in place, releases every active entry, and checks underflow rejection. CMake/CTest and the sanitizer workflow include the target; a full TFS build and hosted CI are still pending.

## Follow-up verification — 2026-09-29 (connection output queue bound)

- `Connection::send` now rejects a 65th pending output message and force-closes that connection. The count includes the message currently being written; each `OutputMessage` owns a fixed 65,500-byte buffer, making the pending message-buffer ceiling roughly 4 MiB per connection.
- The standalone native boundary test compiled with MSVC `/W4 /WX` and passed 20 consecutive runs. All 33 local Python regressions passed, including source checks that the overflow guard runs before queue append and that CMake/CI include the native test. `git diff --check` passed.
- The full server/CMake build, hosted CI, and staging traffic measurements were unavailable. The limit is conservative pending observed output bursts; it does not cap aggregate connections or total server memory.

## Follow-up verification — 2026-09-29 (SQL identifier quoting)

- `DatabaseManager::optimizeTables` used table names read from `information_schema` as SQL identifiers. Embedded backticks are now doubled before enclosing the identifier in backticks; normal names are unchanged.
- The standalone C++11-compatible regression compiled with MSVC `/W4 /WX` and passed. The Python suite includes checks that the metadata value goes through the helper and that CMake/CI run the native test. A real DB integration test was not possible locally.

## Deferred changes

No wire protocol, gameplay, login format, database schema, production configuration, firewall, TLS, account hash, or client behavior was changed. The Lua watchdog change is diagnostic/performance code and still needs LuaJIT staging validation. The output queue has a conservative 64-message cap pending traffic measurements; socket and dispatcher shutdown fixes still need a full build plus TSan/staging validation; password hashing needs a compatibility plan; C++ task exception isolation needs semantic review. Status-query state has a 65,536-IP cap and incremental cleanup; a full cache may temporarily refuse unseen status clients. The separate unauthenticated game TCP accept surface still lacks measured connection admission limits. Those issues and external validation gaps are tracked in [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md).
