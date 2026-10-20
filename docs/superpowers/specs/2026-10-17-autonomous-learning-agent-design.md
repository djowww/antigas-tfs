# Autonomous Learning Agent Design

## Status

Design proposal for review. This document does not authorize production deployment.

## Goal

Provide a removable, server-independent learning controller that lets the twenty existing test characters improve navigation and hunting from their own observed outcomes, including real transitions from Rook surface areas into rat-cave floors, while preserving ordinary game rules and character progress.

## Intent and boundaries

The controller is an external process. It owns its policy, episodic memory, route cache, metrics, and launch configuration; it does not modify the game server binary, database schema, player accounts, item tables, or world map. Removing or stopping the controller leaves the server and the characters' saved progress intact.

"Sem limites" applies to the learning horizon and the number of experiences retained by policy, subject to bounded storage rotation and the existing admission, CPU, memory, connection, and latency protections. The controller must never bypass those protections, invent XP, teleport a character, force a floor transition, or suppress a death or item loss.

## Current failure to address

The existing policy is a persistent tabular Q-learning layer over safe high-level actions, but navigation is still constrained by the observed world and by a static Rook route set. A floor change is authorized only after a matching live stair/object observation, and failed paths do not produce a durable navigation memory with enough context to select a different floor transition later. This explains why the agents can move on the surface while failing to make repeatable progress into caves.

## Recommended architecture

### 1. Separate learner process

Add a standalone `autonomous-learning-agent` process that consumes read-only observations and emits only the same ordinary movement, speech, combat, inventory, and logout intents already accepted by `PlayerRunner`. The process communicates with the existing runner through a versioned local IPC protocol or a file-backed queue selected at deployment time; no inbound internet API is required.

The process must be independently startable, stoppable, and removable. Its configuration names the target accounts, maximum active sessions, observation interval, learning-store directory, and rollout mode. A missing, corrupt, or stale learner state fails closed to the existing deterministic controller.

### 2. Persistent per-character experience memory

For each character, store timestamped transitions with:

- abstract state: floor, region, health band, food band, nearby threat band, route confidence, and current goal;
- action: movement direction, stair attempt, hunt, retreat, supply, conversation, or wait;
- outcome: observed position change, floor change, damage, death, XP delta, loot, timeout, blocked step, or successful return;
- reward components: survival, progress, successful combat, XP, recovered health, route discovery, and penalties for repeated blocked or unsafe actions.

The store is append-only during a run, periodically checkpointed, and rotated by size while retaining per-character summaries. Checkpoints use atomic replacement and checksum verification. The learner must resume from the last verified checkpoint after restart without rewriting character data.

### 3. Hierarchical navigation learning

Represent navigation as a graph of observed regions. Nodes contain validated tiles and floor identifiers; edges contain the exact observed stair or transition object, direction, confidence, success count, failure count, and last verification time. A candidate edge is not usable until the client observes the transition and confirms the new floor in a subsequent map/update event.

The planner operates in three layers:

1. local movement over currently observed walkable tiles;
2. regional route choice among previously successful surface and cave segments;
3. cautious exploration of an unverified boundary when health, food, escape route, and server-health gates permit it.

Blocked paths and failed transitions are learned as negative edges with cooldowns and bounded retry budgets. A moving monster or changed map observation invalidates only the affected edge instead of poisoning the whole route graph.

### 4. Individual learning and curriculum

Every character has an independent policy namespace, RNG seed, route confidence, and curriculum state. Characters may share immutable map facts and aggregate route statistics, but one character's death or mistake cannot rewrite another character's progress.

The curriculum unlocks a deeper hunting region only after the character has:

- observed a valid transition edge;
- survived the transition and at least one combat cycle;
- retained a valid retreat path to a temple or known safe tile;
- met the existing food, health, and equipment checks.

The controller may continue learning indefinitely from new observations. It does not automatically raise the number of public sessions or alter the existing target population.

### 5. Safety and removal

The current guardian, supervisor, connection pacing, timeout handling, death recovery, and non-CPU suspension latches remain authoritative. The learner cannot clear a suspension, reset a recovery counter, or override a failed health observation. All intents pass through the existing admission and protocol validation layers.

Stopping the learner must cancel only its own queued actions and close its own IPC handles. It must not stop `antigas74.service`, modify MySQL, delete state, or disconnect human players. An explicit uninstall command removes only the learner unit, its executable/configuration, and its private rotated checkpoints after a dry-run inventory; character rows and server state remain untouched.

## Data flow

```text
server client observations
        |
        v
existing PlayerRunner -> validated observation journal -> learner IPC
                                                   |
                                                   v
                                  per-character policy + route memory
                                                   |
                                                   v
                                  bounded intent queue and metrics
                                                   |
                                                   v
                                  existing runner/admission gates
```

The learner never treats a requested action as success. It waits for the next observed state and records the actual result. XP, death, inventory, floor, and position values come only from server observations.

## Failure handling

- IPC unavailable or learner crash: use the existing deterministic controller and record a learner-degraded metric.
- Corrupt checkpoint: quarantine that checkpoint, load the last verified checkpoint, and continue with the existing policy.
- Stale world observation: stop exploration and request a fresh map observation; do not guess a floor or stair.
- Repeated blocked route: mark the edge cooling down and choose a known-safe alternative or retreat.
- Health, latency, memory, SQL, or queue guard failure: suspend admissions and actions according to the existing guardian.
- Unexpected protocol packet: preserve the current fail-closed behavior and stop the affected session.

## Verification strategy

Tests must cover the learner without connecting to production:

1. policy persistence and checksum recovery for two independent characters;
2. successful observed stair transition from surface to cave and back;
3. blocked stair/path learning, cooldown, and alternate-route selection;
4. death and timeout records without artificial XP or inventory restoration;
5. learner crash fallback to the deterministic controller;
6. removal dry-run proving that only learner-owned files/services are selected;
7. isolated multi-hour simulation with bounded CPU, memory, queue, and storage growth;
8. one-client canary against the existing QA fixture before any public session is considered.

Success requires real position changes across floors, real combat/XP observations, recoveries after damage, persistence across a restart, and no changes to human-player rows or server binaries. A green unit test suite alone is insufficient evidence.

## Rollout

1. Implement and test the learner in an isolated worktree and QA fixture.
2. Run a shadow mode that learns from observations but emits no actions.
3. Run one disposable test character with the existing guardian active.
4. Review metrics and route evidence; only then consider a controlled increase.
5. Keep the learner disabled by default until explicitly started. The previous twenty-character controller remains the fallback.

## Open decisions for implementation planning

- Choose Unix-domain IPC versus a file-backed queue after measuring the existing runner boundaries.
- Choose the checkpoint format and rotation threshold based on measured event volume.
- Define the exact cave-region seed edges from fresh server observations rather than importing unverified coordinates.

