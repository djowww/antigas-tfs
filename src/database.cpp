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
#include "database.h"

#include <errmsg.h>
#include <cstdlib>

extern ConfigManager g_config;

Database::~Database()
{
	if (handle != nullptr) {
		mysql_close(handle);
	}
}

bool Database::connect()
{
	// connection handle initialization
	handle = mysql_init(nullptr);
	if (!handle) {
		std::cout << std::endl << "Failed to initialize MySQL connection handle." << std::endl;
		return false;
	}

	// automatic reconnect
	bool reconnect = true;
	mysql_options(handle, MYSQL_OPT_RECONNECT, &reconnect);

	// connects to database
	if (!mysql_real_connect(handle, g_config.getString(ConfigManager::MYSQL_HOST).c_str(), g_config.getString(ConfigManager::MYSQL_USER).c_str(), g_config.getString(ConfigManager::MYSQL_PASS).c_str(), g_config.getString(ConfigManager::MYSQL_DB).c_str(), g_config.getNumber(ConfigManager::SQL_PORT), g_config.getString(ConfigManager::MYSQL_SOCK).c_str(), 0)) {
		std::cout << std::endl << "MySQL Error Message: " << mysql_error(handle) << std::endl;
		return false;
	}

	DBResult_ptr result = storeQuery("SHOW VARIABLES LIKE 'max_allowed_packet'");
	if (result) {
		maxPacketSize = result->getNumber<uint64_t>("Value");
	}
	return true;
}

bool Database::beginTransaction(bool strict)
{
	databaseLock.lock();
	if (transactionOpen) { databaseLock.unlock(); return false; }
	strictTransaction = strict;
	transactionFailed = false;
	bool reconnect = !strict;
	mysql_options(handle, MYSQL_OPT_RECONNECT, &reconnect);
	if (!executeQuery("BEGIN")) {
		strictTransaction = false;
		reconnect = true;
		mysql_options(handle, MYSQL_OPT_RECONNECT, &reconnect);
		databaseLock.unlock();
		return false;
	}
	transactionOpen = true;
	return true;
}

bool Database::rollback()
{
	if (mysql_rollback(handle) != 0) {
		std::cout << "[Error - mysql_rollback] Message: " << mysql_error(handle) << std::endl;
		if (strictTransaction) std::abort();
		transactionOpen = false;
		databaseLock.unlock();
		return false;
	}

	transactionOpen = strictTransaction = transactionFailed = false;
	bool reconnect = true;
	mysql_options(handle, MYSQL_OPT_RECONNECT, &reconnect);
	databaseLock.unlock();
	return true;
}

bool Database::commit()
{
	if (strictTransaction && transactionFailed) { rollback(); return false; }
	if (mysql_commit(handle) != 0) {
		std::cout << "[Error - mysql_commit] Message: " << mysql_error(handle) << std::endl;
		// An uncertain commit must never be retried or compensated as if rolled back.
		// Restart without saving memory; InnoDB's committed state is authoritative.
		if (strictTransaction) std::abort();
		transactionOpen = false;
		databaseLock.unlock();
		return false;
	}

	transactionOpen = strictTransaction = transactionFailed = false;
	bool reconnect = true;
	mysql_options(handle, MYSQL_OPT_RECONNECT, &reconnect);
	databaseLock.unlock();
	return true;
}

bool Database::executeQuery(const std::string& query)
{
	bool success = true;

	// executes the query
	databaseLock.lock();
	if (strictTransaction && transactionFailed) { databaseLock.unlock(); return false; }

	while (mysql_real_query(handle, query.c_str(), query.length()) != 0) {
		std::cout << "[Error - mysql_real_query] Query: " << query.substr(0, 256) << std::endl << "Message: " << mysql_error(handle) << std::endl;
		auto error = mysql_errno(handle);
		if (strictTransaction) {
			transactionFailed = true;
			if (error == CR_SERVER_LOST || error == CR_SERVER_GONE_ERROR || error == CR_CONN_HOST_ERROR || error == 1053 || error == CR_CONNECTION_ERROR) std::abort();
			success = false;
			break;
		}
		if (error != CR_SERVER_LOST && error != CR_SERVER_GONE_ERROR && error != CR_CONN_HOST_ERROR && error != 1053/*ER_SERVER_SHUTDOWN*/ && error != CR_CONNECTION_ERROR) {
			success = false;
			break;
		}
		std::this_thread::sleep_for(std::chrono::seconds(1));
	}

	MYSQL_RES* m_res = mysql_store_result(handle);
	databaseLock.unlock();

	if (m_res) {
		mysql_free_result(m_res);
	}

	return success;
}

DBResult_ptr Database::storeQuery(const std::string& query)
{
	databaseLock.lock();
	if (strictTransaction && transactionFailed) { databaseLock.unlock(); return nullptr; }

	retry:
	while (mysql_real_query(handle, query.c_str(), query.length()) != 0) {
		std::cout << "[Error - mysql_real_query] Query: " << query << std::endl << "Message: " << mysql_error(handle) << std::endl;
		auto error = mysql_errno(handle);
		if (strictTransaction) {
			transactionFailed = true;
			if (error == CR_SERVER_LOST || error == CR_SERVER_GONE_ERROR || error == CR_CONN_HOST_ERROR || error == 1053 || error == CR_CONNECTION_ERROR) std::abort();
			databaseLock.unlock();
			return nullptr;
		}
		if (error != CR_SERVER_LOST && error != CR_SERVER_GONE_ERROR && error != CR_CONN_HOST_ERROR && error != 1053/*ER_SERVER_SHUTDOWN*/ && error != CR_CONNECTION_ERROR) {
			break;
		}
		std::this_thread::sleep_for(std::chrono::seconds(1));
	}

	// we should call that every time as someone would call executeQuery('SELECT...')
	// as it is described in MySQL manual: "it doesn't hurt" :P
	MYSQL_RES* res = mysql_store_result(handle);
	if (res == nullptr) {
		std::cout << "[Error - mysql_store_result] Query: " << query << std::endl << "Message: " << mysql_error(handle) << std::endl;
		auto error = mysql_errno(handle);
		if (strictTransaction) {
			transactionFailed = true;
			if (error == CR_SERVER_LOST || error == CR_SERVER_GONE_ERROR || error == CR_CONN_HOST_ERROR || error == 1053 || error == CR_CONNECTION_ERROR) std::abort();
			databaseLock.unlock();
			return nullptr;
		}
		if (error != CR_SERVER_LOST && error != CR_SERVER_GONE_ERROR && error != CR_CONN_HOST_ERROR && error != 1053/*ER_SERVER_SHUTDOWN*/ && error != CR_CONNECTION_ERROR) {
			databaseLock.unlock();
			return nullptr;
		}
		goto retry;
	}
	databaseLock.unlock();

	// retrieving results of query
	DBResult_ptr result = std::make_shared<DBResult>(res);
	if (!result->hasNext()) {
		return nullptr;
	}
	return result;
}

std::string Database::escapeString(const std::string& s) const
{
	const size_t maxLength = (s.length() * 2) + 1;
	std::string escaped;
	escaped.reserve(maxLength + 2);
	escaped.push_back('\'');

	if (!s.empty()) {
		char* output = new char[maxLength];
		const unsigned long escapedLength = mysql_real_escape_string(handle, output, s.c_str(), s.length());
		escaped.append(output, escapedLength);
		delete[] output;
	}

	escaped.push_back('\'');
	return escaped;
}

std::string Database::escapeBlob(const char* s, uint32_t length) const
{
	static constexpr char hex[] = "0123456789ABCDEF";
	std::string escaped = "UNHEX('";
	escaped.reserve((static_cast<size_t>(length) * 2) + 9);
	for (uint32_t i = 0; i < length; ++i) {
		const auto byte = static_cast<uint8_t>(s[i]);
		escaped.push_back(hex[byte >> 4]);
		escaped.push_back(hex[byte & 0x0F]);
	}
	escaped.append("')");
	return escaped;
}

DBResult::DBResult(MYSQL_RES* res)
{
	handle = res;

	size_t i = 0;

	MYSQL_FIELD* field = mysql_fetch_field(handle);
	while (field) {
		listNames[field->name] = i++;
		field = mysql_fetch_field(handle);
	}

	row = mysql_fetch_row(handle);
}

DBResult::~DBResult()
{
	mysql_free_result(handle);
}

std::string DBResult::getString(const std::string& s) const
{
	auto it = listNames.find(s);
	if (it == listNames.end()) {
		std::cout << "[Error - DBResult::getString] Column '" << s << "' does not exist in result set." << std::endl;
		return std::string();
	}

	if (row[it->second] == nullptr) {
		return std::string();
	}

	return std::string(row[it->second]);
}

const char* DBResult::getStream(const std::string& s, unsigned long& size) const
{
	auto it = listNames.find(s);
	if (it == listNames.end()) {
		std::cout << "[Error - DBResult::getStream] Column '" << s << "' doesn't exist in the result set" << std::endl;
		size = 0;
		return nullptr;
	}

	if (row[it->second] == nullptr) {
		size = 0;
		return nullptr;
	}

	size = mysql_fetch_lengths(handle)[it->second];
	return row[it->second];
}

bool DBResult::hasNext() const
{
	return row != nullptr;
}

bool DBResult::next()
{
	row = mysql_fetch_row(handle);
	return row != nullptr;
}

DBInsert::DBInsert(std::string query) : query(std::move(query))
{
	this->length = this->query.length();
}

bool DBInsert::addRow(const std::string& row)
{
	// adds new row to buffer
	const size_t rowLength = row.length();
	length += rowLength;
	if (length > Database::getInstance()->getMaxPacketSize() && !execute()) {
		return false;
	}

	if (values.empty()) {
		values.reserve(rowLength + 2);
		values.push_back('(');
		values.append(row);
		values.push_back(')');
	} else {
		values.reserve(values.length() + rowLength + 3);
		values.push_back(',');
		values.push_back('(');
		values.append(row);
		values.push_back(')');
	}
	return true;
}

bool DBInsert::addRow(std::ostringstream& row)
{
	bool ret = addRow(row.str());
	row.str(std::string());
	return ret;
}

bool DBInsert::execute()
{
	if (values.empty()) {
		return true;
	}

	// executes buffer
	bool res = Database::getInstance()->executeQuery(query + values);
	values.clear();
	length = query.length();
	return res;
}
