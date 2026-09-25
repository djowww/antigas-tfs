-- Additive migration: existing offers/claims are retained.
CREATE TABLE IF NOT EXISTS market_requests (
 player_guid INT UNSIGNED NOT NULL,
 request_id VARCHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 action VARCHAR(16) NOT NULL,
 request_json TEXT NOT NULL,
 response VARCHAR(512) NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(player_guid,request_id),
 KEY market_requests_date(created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
