# Quest Log v36 — a personal journal

The journal follows the character's discoveries instead of revealing the full
quest catalog. The existing dark OTClient window, small fonts, straight borders,
search, filters, selection and two scrollbars are retained.

- Lists, search results, totals and direct detail requests are filtered on the
  server. Undiscovered names, regions, stages and rewards never reach the client.
- Only accepted or completed stages are shown. Shared storage state machines
  (such as Ape City) reveal a new stage only at its actual starting value.
- Postman and Explorer Society initiation can be discovered using their existing
  first-mission flags, before the later membership/rank flags exist.
- Notes use brief first-person descriptions. Internal storage counters, catalog
  percentages and implementation explanations are removed from the interface.
- The empty journal invites exploration; filters cover known entries only.
- Reward names are shown only for recorded single-choice chest finds. Shared
  reward flags and the Annihilator exit flag cannot prove a particular reward,
  so the journal does not claim one was collected.
- Rapid selection requests are combined. Old replies are discarded on search,
  page changes, new selections, closing and logout. Refresh waits for pending
  work; timeout recovery prevents permanently blocked updates. Detail scrolling
  survives updates; long unbroken words wrap within the existing panels.

No quest flags, rewards, map, database schema or original NPC/reward scripts are
changed. `questJournal.lua` contains presentation notes and reviewed discovery
triggers. `questCatalog.lua` remains the v35 audited source catalog. Chest quests
without a start flag appear only once their completion is recorded. Access
scrolls do not invent earlier mission progress.

Extended opcode 125 is retained. Responses add `journal=2`; the list totals and
detail stages describe known entries. v35 clients remain compatible but should
upgrade for the revised wording and interaction fixes. The v36 client refuses to
display the old unrestricted catalog from a server without `journal=2`.

## Validation

`tests/questlog-tests.lua` covers hidden quests/stages/rewards/counts, literal
search, guessed IDs, the empty journal, NPC initiation, scroll permissions,
storage resets, all 242 known entries across pages, player isolation, rejected
mutations, bounds and per-character rate limits.

`tests/questlog-ui-tests.lua` runs inside the actual Windows client offline with
a simulated transport. It covers open/close, search, filters, rapid selection,
malformed/stale replies, logout clearing, the empty journal, text wrapping and
both scrollbars at 800x600, 1024x768 and 1366x768.

`tests/questlog-live.py` uses two disposable ordinary accounts on the official
server, verifies discovered-only responses and isolation, and checks a newly
accepted stage after reconnect. It removes only its own marked test accounts.

## Release and recovery

The v36 release helper checked the current server endpoint and catalog
against the staged baseline, runs LuaJIT tests, and saves the previous endpoint.
The client package is rebuilt from the checksum-verified public v35 ZIP; only
the two Quest Log UI files and APP_VERSION change. Packaging is reproducible
on Windows and Linux, with an exhaustive comparison of all archive entries.

The production release is staged at `/root/releases/questlog-v36-20260927`.
To recover server behavior, restore `server-before/questlog.lua` to the endpoint
and restart `imperium772` with its configured graceful SIGTERM shutdown.
The added notes file then becomes unused. Website index/manifest backups are in
`website-before`; v35 remains available. No player-data rollback is required.
