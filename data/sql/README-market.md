# Antigas Market

Before enabling the server-side Market event, apply the required SQL migrations to the same MySQL/MariaDB database used by the game server. For a new installation, apply `market.sql`, `market-v2.sql`, and `market-v3.sql` in that order. For an installation already using Market v2, apply only `market-v3.sql` before deploying the updated `market.lua`. These migrations are additive, use InnoDB, and can be repeated on MariaDB; they do not alter player, account, depot, or existing shop tables.

### MySQL compatibility

`market-v3.sql` ends with `CREATE INDEX IF NOT EXISTS`, which MariaDB supports but MySQL 8.4's `CREATE INDEX` syntax does not include. On MySQL, apply the `CREATE TABLE` statement at the start of `market-v3.sql`, then check whether the catalog index already exists:

```sql
SELECT 1
FROM information_schema.statistics
WHERE table_schema = DATABASE()
  AND table_name = 'market_offers'
  AND index_name = 'market_catalog_prices';
```

If the query returns no row, create the index once:

```sql
CREATE INDEX market_catalog_prices
  ON market_offers(status,item_id,currency_id,side,unit_price);
```

The Market uses extended opcode `202` and the Gold Coin item ID `3031` plus Antigas Coin item ID `5130` from this server's `items.srv`. Listings reserve their item or full currency amount. Partial fills are supported. Cancellation and trade proceeds create claims which are collected into the character's depot with the Market's **Collect depot** button.

The server intentionally rejects containers, fluid containers, doors, fields, splashes, and inventory instances carrying a unique/action ID. Such objects cannot safely be recreated from only an item ID and quantity. Buy and sell offers are limited to 15 active offers per character; an order's reserved total is capped at 100,000,000 Gold or 10,000 Antigas Coins to bound coin stack creation during depot delivery.

## Rollout checklist

1. Apply the appropriate migration sequence above to the game database before deploying the updated Market Lua files.
2. Deploy `data/creaturescripts/scripts/market.lua`, `data/creaturescripts/creaturescripts.xml`, and `data/creaturescripts/scripts/login.lua`.
3. Deploy the `Cliente/modules/game_market_antigas` module. The original `game_market` files remain untouched (the stock client module speaks the native Tibia Market protocol, which this server base does not implement).
4. Restart the game server and distribute the updated client.
5. Verify listing creation, partial fills, cancellation, both currencies, offline claims, and depot collection with two test characters before enabling for players.
