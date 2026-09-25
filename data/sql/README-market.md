# Antigas Market

Before enabling the server-side Market event, run `market.sql` once against the same MySQL/MariaDB database used by the game server. The migration is additive and uses `CREATE TABLE IF NOT EXISTS`; it does not alter player, account, depot, or existing shop tables.

The Market uses extended opcode `202` and the Gold Coin item ID `3031` plus Antigas Coin item ID `5130` from this server's `items.srv`. Listings reserve their item or full currency amount. Partial fills are supported. Cancellation and trade proceeds create claims which are collected into the character's depot with the Market's **Collect depot** button.

The server intentionally rejects containers, fluid containers, doors, fields, splashes, and inventory instances carrying a unique/action ID. Such objects cannot safely be recreated from only an item ID and quantity. Buy and sell offers are limited to 15 active offers per character; an order's reserved total is capped at 100,000,000 Gold or 10,000 Antigas Coins to bound coin stack creation during depot delivery.

## Rollout checklist

1. Apply `market.sql` to the game database.
2. Deploy `data/creaturescripts/scripts/market.lua`, `data/creaturescripts/creaturescripts.xml`, and `data/creaturescripts/scripts/login.lua`.
3. Deploy the `Cliente/modules/game_market_antigas` module. The original `game_market` files remain untouched (the stock client module speaks the native Tibia Market protocol, which this server base does not implement).
4. Restart the game server and distribute the updated client.
5. Verify listing creation, partial fills, cancellation, both currencies, offline claims, and depot collection with two test characters before enabling for players.
