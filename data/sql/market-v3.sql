-- Additive migration. Do not rebuild offers, claims or request receipts.
CREATE TABLE IF NOT EXISTS market_history (
 id INT UNSIGNED NOT NULL AUTO_INCREMENT,
 player_guid INT UNSIGNED NOT NULL,
 offer_id INT UNSIGNED NOT NULL,
 event_type VARCHAR(16) NOT NULL,
 item_id SMALLINT UNSIGNED NOT NULL,
 item_name VARCHAR(100) NOT NULL,
 quantity INT UNSIGNED NOT NULL,
 unit_price INT UNSIGNED NOT NULL,
 currency_id SMALLINT UNSIGNED NOT NULL,
 total INT UNSIGNED NOT NULL,
 claim_id INT UNSIGNED NOT NULL,
 destination VARCHAR(32) NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (id),
 KEY player_history (player_guid,id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE INDEX IF NOT EXISTS market_catalog_prices
 ON market_offers(status,item_id,currency_id,side,unit_price);
