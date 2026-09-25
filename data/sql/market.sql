-- Run once against the game database before enabling the Market module.
-- Listings escrow assets until completion/cancellation; claims are delivered to depot.
CREATE TABLE IF NOT EXISTS `market_offers` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `owner_guid` INT UNSIGNED NOT NULL,
  `side` TINYINT UNSIGNED NOT NULL COMMENT '0 = sell item, 1 = buy item',
  `item_id` SMALLINT UNSIGNED NOT NULL,
  `item_subtype` SMALLINT NOT NULL DEFAULT -1,
  `item_name` VARCHAR(100) NOT NULL,
  `category` VARCHAR(24) NOT NULL,
  `remaining` INT UNSIGNED NOT NULL,
  `unit_price` INT UNSIGNED NOT NULL,
  `currency_id` SMALLINT UNSIGNED NOT NULL,
  `status` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '1 = active, 2 = completed/cancelled',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `market_browse` (`status`, `category`, `currency_id`, `item_id`),
  KEY `market_owner` (`owner_guid`, `status`),
  KEY `market_match` (`status`, `side`, `item_id`, `item_subtype`, `currency_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS `market_claims` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `player_guid` INT UNSIGNED NOT NULL,
  `kind` TINYINT UNSIGNED NOT NULL COMMENT '0 = item, 1 = currency',
  `item_id` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  `item_subtype` SMALLINT NOT NULL DEFAULT -1,
  `item_count` INT UNSIGNED NOT NULL DEFAULT 0,
  `currency_id` SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  `currency_amount` INT UNSIGNED NOT NULL DEFAULT 0,
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `market_claim_owner` (`player_guid`, `id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
