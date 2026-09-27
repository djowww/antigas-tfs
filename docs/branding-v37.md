# Antigas branding cleanup — client v37

This release removes stale previous branding from player-facing client and
server text. The Bestiary catalog file is now `antigas_monster.lua`; its
locations display “All over Antigas” and “Antigas cities”. The client title,
release notice, GM title labels, server status name, `!serverinfo`, and custom
shield/backpack item names use Antigas.

The public client package is `Antigas-7.4-Client-v37.zip`. Client protocol and
gameplay data are unchanged. Database/schema names, service-unit identifiers,
filesystem paths, and historical release records intentionally remain as
internal compatibility identifiers; they are not shown to players.
