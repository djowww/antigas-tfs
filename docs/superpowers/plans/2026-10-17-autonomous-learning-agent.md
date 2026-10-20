# Autonomous Learning Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended) or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a removable external learning agent that learns per-character navigation and hunting outcomes, including validated surface-to-cave transitions, without changing the game server or player data.

**Architecture:** The existing runner remains the authoritative protocol and safety boundary. It publishes validated observations over a localhost Unix stream socket to a separate learner process, which stores per-character experience and returns bounded high-level intents; runner admission, guardian, and protocol checks remain mandatory. Learning state lives in a separate SQLite file so stopping or uninstalling the agent cannot remove runner state or server data.

**Tech Stack:** Python 3 standard library, SQLite WAL with full synchronous commits, Unix-domain sockets, systemd service units, existing `tools.autonomous_players` runtime and unittest suite.

**Spec:** `docs/superpowers/specs/2026-10-17-autonomous-learning-agent-design.md`

## Global Constraints

- The controller is an external process and must not modify the game server binary, database schema, player accounts, item tables, or world map.
- “Sem limites” means continuous learning without a fixed episode count, subject to bounded CPU, memory, connection, latency, and rotated storage protections.
- The learner must never bypass guardian/supervisor latches, invent XP, teleport, force a floor transition, or restore death/item-loss state.
- A missing, corrupt, or stale learner state fails closed to the existing deterministic controller.
- The learner must be disabled by default and removable by selecting only learner-owned files and the learner service.
- No public rollout happens before isolated tests, shadow mode, and a one-character canary pass.

## Review Focus

- A blocked stair or cave path must create a character-scoped cooldown and select a known-safe alternative; test in Task 3.
- A real floor change must require observed map evidence before the edge becomes reusable; test in Task 3.
- A learner crash or stale socket must leave the deterministic runner active with no queued unsafe intent; test in Task 4.
- A corrupt checkpoint must quarantine only learner state and preserve the last verified checkpoint; test in Task 2.
- Removal must select only learner-owned artifacts and leave runner/server state untouched; test in Task 5.

---

### Task 1: Define the observation and intent protocol

**Files:**
- Create: `tools/autonomous_players/learning_protocol.py`
- Modify: `tools/autonomous_players/world.py`
- Test: `tests/autonomous_players/test_learning_protocol.py`

**Interfaces:**
- Produces `LearningObservation.from_world(agent: str, world: World, goal: str, route_confidence: float) -> LearningObservation`.
- Produces `LearningIntent(agent: str, kind: str, payload: dict, issued_at: float, ttl: float)` and `LearningIntent.expired(now: float) -> bool`.
- Produces `encode_message(value: dict) -> bytes` and `decode_message(line: bytes) -> dict` using one JSON object per newline, maximum 32 KiB per message, and schema/version validation.

- [ ] **Step 1: Write failing protocol tests** for round-trip observations, rejection of unknown schema versions, message-size limits, finite timestamps/rewards, and intent expiry.
- [ ] **Step 2: Run `python -m unittest tests.autonomous_players.test_learning_protocol -v`** and verify the new tests fail because the protocol module is absent.
- [ ] **Step 3: Implement the dataclasses and JSON-line codec** with explicit allowlists for fields and intent kinds. Include only abstract state and observed facts; never serialize credentials, raw packets, or database credentials.
- [ ] **Step 4: Run the focused test file** and verify all protocol tests pass.
- [ ] **Step 5: Commit** `feat: add local learning observation protocol`.

### Task 2: Add isolated, recoverable learning storage

**Files:**
- Create: `tools/autonomous_players/learning_store.py`
- Test: `tests/autonomous_players/test_learning_store.py`

**Interfaces:**
- `LearningStore(path: Path, max_agents: int = 24, max_events: int = 100000)`.
- `record_transition(agent: str, state: str, action: str, next_state: str, outcome: dict, reward: float, at: float) -> None`.
- `route_edge(agent: str, source: str, destination: str, transition_id: int, success: bool, at: float) -> None`.
- `checkpoint(agent: str, payload: dict) -> str` and `restore_latest(agent: str) -> dict | None`.
- `quarantine_corrupt(agent: str) -> Path` and `summary(agent: str) -> dict`.

- [ ] **Step 1: Write failing storage tests** for independent agent namespaces, WAL/full-sync setup, atomic checkpoint restore, bounded event rotation, checksum mismatch quarantine, and preservation of a prior verified checkpoint.
- [ ] **Step 2: Run `python -m unittest tests.autonomous_players.test_learning_store -v`** and verify failure before implementation.
- [ ] **Step 3: Implement `LearningStore`** in a separate SQLite schema/version from `state.db`; use atomic temporary checkpoint files plus checksum rows, reject nonfinite values and oversized payloads, and never connect to game MySQL.
- [ ] **Step 4: Run the focused tests** and verify they pass, including reopening the database after a simulated process crash.
- [ ] **Step 5: Commit** `feat: persist autonomous learning experiences separately`.

### Task 3: Implement learned regional navigation and curriculum

**Files:**
- Create: `tools/autonomous_players/learned_navigation.py`
- Modify: `tools/autonomous_players/progression.py`
- Modify: `tools/autonomous_players/learning.py`
- Test: `tests/autonomous_players/test_learned_navigation.py`

**Interfaces:**
- `RegionGraph.observe_transition(agent: str, before: Position, after: Position, transition_id: int, observed_at: float) -> bool` returns true only for a newly verified edge.
- `RegionGraph.record_failure(agent: str, source: Position, target: Position, reason: str, at: float) -> None`.
- `RegionGraph.next_goal(agent: str, current: Position, safe_routes: tuple[Position, ...], now: float) -> Position | None`.
- `Curriculum.ready_for(agent: str, region: str, observation: LearningObservation) -> bool`.
- `Curriculum.record(agent: str, outcome: dict) -> None`.

- [ ] **Step 1: Write failing navigation tests** for surface-to-cave edge verification, return-edge verification, blocked-edge cooldown, alternate route selection, moving-target invalidation, and curriculum refusal when health/food/retreat conditions are not met.
- [ ] **Step 2: Run `python -m unittest tests.autonomous_players.test_learned_navigation -v`** and confirm failure.
- [ ] **Step 3: Implement `RegionGraph`** over observed tiles and validated transitions only; store negative edges with bounded retry/cooldown and leave static route knowledge advisory. Implement curriculum gates using existing health, inventory, retreat, and guardian facts.
- [ ] **Step 4: Update `Progression`** to consult the learned graph after deterministic local routing, record actual outcomes after the next observation, and preserve existing floor authorization and fail-closed behavior. No code path may synthesize a floor change.
- [ ] **Step 5: Run focused navigation tests plus `python -m unittest tests.autonomous_players.test_progression tests.autonomous_players.test_routes -v`** and verify all pass.
- [ ] **Step 6: Commit** `feat: learn validated cave routes per character`.

### Task 4: Add the standalone learner and runner bridge

**Files:**
- Create: `tools/autonomous_learning_agent.py`
- Create: `tools/autonomous_players/learning_bridge.py`
- Modify: `tools/autonomous_players/app.py`
- Modify: `tools/autonomous_players/runtime.py`
- Test: `tests/autonomous_players/test_learning_bridge.py`
- Test: `tests/autonomous_players/test_learning_agent.py`

**Interfaces:**
- `LearningBridge(socket_path: Path, connect_timeout: float, intent_ttl: float)` with `publish(observation: LearningObservation) -> None`, `poll_intent() -> LearningIntent | None`, and `close() -> None`.
- `LearningAgent.handle(observation: LearningObservation) -> LearningIntent | None`.
- CLI `python -m tools.autonomous_learning_agent --socket PATH --state PATH --shadow`.

- [ ] **Step 1: Write failing bridge/agent tests** for local socket framing, shadow mode, stale-socket fallback, expired-intent rejection, per-agent policy isolation, and clean shutdown cancelling only learner-owned queues.
- [ ] **Step 2: Run both focused test files** and verify failure.
- [ ] **Step 3: Implement the bridge** with a bounded queue, one observation in flight per agent, short connect/read timeouts, no network addresses, and fail-closed behavior when the learner is absent.
- [ ] **Step 4: Implement the standalone learner** using `LearningStore`, `Policy`, `RegionGraph`, and `Curriculum`; in shadow mode it records decisions but returns no intents. In active mode it returns only existing high-level action types.
- [ ] **Step 5: Integrate `app.py`/`runtime.py`** so observations are published after validated world updates, results are recorded only from the next observed state, and any learner intent is passed through the existing admission/protocol checks before transmission.
- [ ] **Step 6: Run focused tests plus the complete suite** with `python -m unittest discover -s tests/autonomous_players -p 'test_*.py'`; expected result is all existing tests plus new bridge/agent tests passing.
- [ ] **Step 7: Commit** `feat: run autonomous learning as removable companion process`.

### Task 5: Package the disabled-by-default service and removal workflow

**Files:**
- Create: `deploy/autonomous-learning/autonomous-learning-agent.service`
- Create: `deploy/autonomous-learning/learning-agent.json`
- Create: `deploy/autonomous-learning/remove-learning-agent.sh`
- Create: `tests/autonomous_players/test_learning_deployment.py`

**Interfaces:**
- Service runs `python3 -m tools.autonomous_learning_agent` as `antigas-players`, uses only `AF_UNIX`, its own state directory, `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `CPUQuota=10%`, and `MemoryMax=128M`.
- Removal script supports `--dry-run` and requires an explicit `--apply`; its allowlist is limited to the learner unit, learner config, learner executable/package files, socket directory, and learner state directory.

- [ ] **Step 1: Write failing deployment tests** for disabled-by-default unit state, no internet address family, resource limits, dry-run allowlist, and refusal to select `state.db`, runtime config, game service files, or MySQL paths.
- [ ] **Step 2: Run the focused deployment test file** and verify failure.
- [ ] **Step 3: Implement the unit, config template, and removal script** with explicit paths and a dry-run inventory before any deletion. Do not enable or start the unit in this task.
- [ ] **Step 4: Run deployment tests and a shellcheck-equivalent syntax check**; verify the script is read-only unless `--apply` is supplied.
- [ ] **Step 5: Commit** `ops: package removable learning agent safely`.

### Task 6: Isolated simulation and staged verification

**Files:**
- Create: `tests/autonomous_players/test_learning_simulation.py`
- Create: `tools/autonomous_learning_simulation.py`
- Modify: `docs/superpowers/specs/2026-10-17-autonomous-learning-agent-design.md` only for verified results after testing.

**Interfaces:**
- CLI `python -m tools.autonomous_learning_simulation --agents 20 --duration SECONDS --seed SEED --state PATH` produces machine-readable JSON metrics and never connects to production.

- [ ] **Step 1: Write failing simulation tests** for twenty independent policies, observed surface-to-cave transition, blocked-path recovery, death recording without XP restoration, restart persistence, and CPU/storage bounds.
- [ ] **Step 2: Run the focused simulation tests** and verify failure.
- [ ] **Step 3: Implement the deterministic fixture and metrics** using the same protocol/store/graph interfaces, with no production host, account, password, or socket defaults.
- [ ] **Step 4: Run the isolated simulation for a bounded multi-hour-equivalent workload** and verify real movement/XP outcome metrics, zero artificial XP writes, bounded resource growth, and checkpoint recovery.
- [ ] **Step 5: Run the full test suite and record only verified evidence** in the spec/ledger.
- [ ] **Step 6: Commit** `test: verify autonomous learning in isolated simulation`.

### Task 7: QA shadow mode and one-character canary preparation

**Files:**
- Create: `output/autonomous_learning_shadow.ps1`
- Create: `output/autonomous_learning_read_status.ps1`
- Test: `tests/autonomous_players/test_learning_canary.py`

**Interfaces:**
- Read-only status helper reports learner process state, checkpoint freshness, per-agent route-edge counts, decisions, blocked-path cooldowns, and resource metrics without printing secrets.
- Shadow launcher starts only the learner against the existing QA fixture and refuses production hostnames unless an explicit QA marker is present.

- [ ] **Step 1: Write failing canary tests** for QA-only endpoint validation, no-op shadow intents, status redaction, and one-character rollout selection.
- [ ] **Step 2: Implement the read-only helper and shadow launcher**; do not enable the production unit.
- [ ] **Step 3: Run the canary tests and an isolated one-character QA session**; verify at least one real observed floor transition, combat/XP observation, return/retreat, checkpoint reload, and no changes to production.
- [ ] **Step 4: Review evidence and stop.** A public rollout, population increase, or service enablement requires a separate explicit decision after the canary.
- [ ] **Step 5: Commit** `test: prepare isolated learning canary evidence`.

