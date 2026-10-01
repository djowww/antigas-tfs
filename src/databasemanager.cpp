/**
 * Tibia GIMUD Server - a free and open-source MMORPG server emulator
 * Copyright (C) 2017  Alejandro Mujica <alejandrodemujica@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#include "otpch.h"

#include "configmanager.h"
#include "databasemanager.h"
#include "luascript.h"
#include "sqlidentifier.h"

extern ConfigManager g_config;

bool DatabaseManager::optimizeTables()
{
	Database* db = Database::getInstance();
	std::ostringstream query;

	std::string escapedDatabase;
	if (!db->escapeString(g_config.getString(ConfigManager::MYSQL_DB), escapedDatabase)) return false;
	query << "SELECT `TABLE_NAME` FROM `information_schema`.`TABLES` WHERE `TABLE_SCHEMA` = " << escapedDatabase << " AND `DATA_FREE` > 0";
	DBResult_ptr result = db->storeQuery(query.str());
	if (!result) {
		return false;
	}

	do {
		std::string tableName = result->getString("TABLE_NAME");
		std::cout << "> Optimizing table " << tableName << "..." << std::flush;

		query.str(std::string());
		query << "OPTIMIZE TABLE " << quoteSqlIdentifier(tableName);

		if (db->executeQuery(query.str())) {
			std::cout << " [success]" << std::endl;
		} else {
			std::cout << " [failed]" << std::endl;
		}
	} while (result->next());
	return true;
}

bool DatabaseManager::tableExists(const std::string& tableName, bool* querySucceeded)
{
	if (querySucceeded) *querySucceeded = false;
	Database* db = Database::getInstance();

	std::string escapedDatabase;
	std::string escapedTable;
	if (!db->escapeString(g_config.getString(ConfigManager::MYSQL_DB), escapedDatabase)
		|| !db->escapeString(tableName, escapedTable)) return false;

	std::ostringstream query;
	query << "SELECT `TABLE_NAME` FROM `information_schema`.`tables` WHERE `TABLE_SCHEMA` = " << escapedDatabase << " AND `TABLE_NAME` = " << escapedTable << " LIMIT 1";
	bool succeeded = false;
	DBResult_ptr result = db->storeQuery(query.str(), &succeeded);
	if (querySucceeded) *querySucceeded = succeeded;
	return result != nullptr;
}

bool DatabaseManager::isDatabaseSetup(bool* querySucceeded)
{
	if (querySucceeded) *querySucceeded = false;
	Database* db = Database::getInstance();
	std::string escapedDatabase;
	if (!db->escapeString(g_config.getString(ConfigManager::MYSQL_DB), escapedDatabase)) return false;
	std::ostringstream query;
	query << "SELECT `TABLE_NAME` FROM `information_schema`.`tables` WHERE `TABLE_SCHEMA` = " << escapedDatabase;
	bool succeeded = false;
	DBResult_ptr result = db->storeQuery(query.str(), &succeeded);
	if (querySucceeded) *querySucceeded = succeeded;
	return result != nullptr;
}

int32_t DatabaseManager::getDatabaseVersion()
{
	bool querySucceeded = false;
	const bool configTableExists = tableExists("server_config", &querySucceeded);
	if (!querySucceeded) return -1;
	if (!configTableExists) {
		Database* db = Database::getInstance();
		db->executeQuery("CREATE TABLE `server_config` (`config` VARCHAR(50) NOT NULL, `value` VARCHAR(256) NOT NULL DEFAULT '', UNIQUE(`config`)) ENGINE = InnoDB");
		db->executeQuery("INSERT INTO `server_config` VALUES ('db_version', 0)");
		return 0;
	}

	int32_t version = 0;
	if (getDatabaseConfig("db_version", version)) {
		return version;
	}
	return -1;
}

bool DatabaseManager::getDatabaseConfig(const std::string& config, int32_t& value, bool* querySucceeded)
{
	if (querySucceeded) *querySucceeded = false;
	Database* db = Database::getInstance();
	std::string escapedConfig;
	if (!db->escapeString(config, escapedConfig)) return false;
	std::ostringstream query;
	query << "SELECT `value` FROM `server_config` WHERE `config` = " << escapedConfig;

	bool succeeded = false;
	DBResult_ptr result = db->storeQuery(query.str(), &succeeded);
	if (querySucceeded) *querySucceeded = succeeded;
	if (!result) {
		return false;
	}

	value = result->getNumber<int32_t>("value");
	return true;
}

void DatabaseManager::registerDatabaseConfig(const std::string& config, int32_t value)
{
	Database* db = Database::getInstance();
	std::ostringstream query;
	std::string escapedConfig;
	if (!db->escapeString(config, escapedConfig)) return;

	int32_t tmp;
	bool querySucceeded = false;
	const bool configExists = getDatabaseConfig(config, tmp, &querySucceeded);
	if (!querySucceeded) return;

	if (!configExists) {
		query << "INSERT INTO `server_config` VALUES (" << escapedConfig << ", '" << value << "')";
	} else {
		query << "UPDATE `server_config` SET `value` = '" << value << "' WHERE `config` = " << escapedConfig;
	}

	db->executeQuery(query.str());
}
