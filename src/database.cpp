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
	std::lock_guard<std::recursive_mutex> lock(databaseLock);
	return ensureConnection();
}

bool Database::ensureConnection()
{
	if (connected) return true;
	if (std::chrono::steady_clock::now() < retryAfter) return false;
	if (handle) mysql_close(handle);
	handle = mysql_init(nullptr);
	if (!handle) { connectionFailed(); return false; }
	// Never replay a statement implicitly, particularly an ambiguous write.
	bool reconnect = false;
	unsigned int timeout = 1;
	mysql_options(handle, MYSQL_OPT_RECONNECT, &reconnect);
	mysql_options(handle, MYSQL_OPT_CONNECT_TIMEOUT, &timeout);
	mysql_options(handle, MYSQL_OPT_READ_TIMEOUT, &timeout);
	mysql_options(handle, MYSQL_OPT_WRITE_TIMEOUT, &timeout);
	if (!mysql_real_connect(handle, g_config.getString(ConfigManager::MYSQL_HOST).c_str(), g_config.getString(ConfigManager::MYSQL_USER).c_str(), g_config.getString(ConfigManager::MYSQL_PASS).c_str(), g_config.getString(ConfigManager::MYSQL_DB).c_str(), g_config.getNumber(ConfigManager::SQL_PORT), g_config.getString(ConfigManager::MYSQL_SOCK).c_str(), 0)) {
		std::cout << "[Database] Connection unavailable; cooling down before recovery." << std::endl;
		connectionFailed();
		return false;
	}
	// Bound lock waits as well as socket waits, including the login recovery fence.
	const char* setup = "SET SESSION innodb_lock_wait_timeout=1";
	if (mysql_real_query(handle, setup, strlen(setup)) != 0) {
		connectionFailed();
		return false;
	}
	connected = true;
	return true;
}

void Database::connectionFailed()
{
	// Closing the original session makes every pre-COMMIT failure a rollback.
	if (handle) mysql_close(handle);
	handle = mysql_init(nullptr);
	connected = false;
	retryAfter = std::chrono::steady_clock::now() + std::chrono::seconds(2);
}

void Database::queryFailed()
{
	if (transactionOpen) transactionFailed = true;
	unsigned int error = handle ? mysql_errno(handle) : CR_CONNECTION_ERROR;
	std::cout << "[Database] Query failed (code " << error << "); not replayed." << std::endl;
	if (error == CR_SERVER_LOST || error == CR_SERVER_GONE_ERROR || error == CR_CONN_HOST_ERROR
		|| error == CR_CONNECTION_ERROR || error == 1053 || error == CR_COMMANDS_OUT_OF_SYNC) connectionFailed();
}

void Database::finishTransaction()
{
	transactionOpen = strictTransaction = transactionFailed = false;
	databaseLock.unlock();
}

bool Database::beginTransaction(bool strict)
{
	databaseLock.lock();
	if (transactionOpen || !ensureConnection()) { databaseLock.unlock(); return false; }
	if (!executeQuery("BEGIN")) {
		databaseLock.unlock();
		return false;
	}
	transactionOpen = true;
	strictTransaction = strict;
	transactionFailed = false;
	return true;
}

bool Database::rollback()
{
	if (!transactionOpen) return false;
	if (connected && mysql_rollback(handle) != 0) connectionFailed();
	// No COMMIT was sent. A discarded session cannot commit this transaction.
	finishTransaction();
	return true;
}

bool Database::commit(bool& uncertain)
{
	uncertain = false;
	if (!transactionOpen) return false;
	if (transactionFailed || !connected) { rollback(); return false; }
	if (mysql_commit(handle) != 0) {
		// Do not undo or retry an ambiguous COMMIT. The caller must isolate its state.
		uncertain = true;
		std::cout << "[Database] Commit outcome unknown; isolate affected state." << std::endl;
		connectionFailed();
		finishTransaction();
		return false;
	}
	finishTransaction();
	return true;
}

bool Database::executeQuery(const std::string& query)
{
	std::lock_guard<std::recursive_mutex> lock(databaseLock);
	if (transactionFailed || (transactionOpen && !connected) || !ensureConnection()) return false;
	if (mysql_real_query(handle, query.c_str(), query.length()) != 0) { queryFailed(); return false; }
	MYSQL_RES* res = mysql_store_result(handle);
	if (res) mysql_free_result(res);
	else if (mysql_field_count(handle) != 0) { queryFailed(); return false; }
	return true;
}

DBResult_ptr Database::storeQuery(const std::string& query, bool* success)
{
	std::lock_guard<std::recursive_mutex> lock(databaseLock);
	if (success) *success = false;
	if (transactionFailed || (transactionOpen && !connected) || !ensureConnection()) return nullptr;
	if (mysql_real_query(handle, query.c_str(), query.length()) != 0) { queryFailed(); return nullptr; }
	MYSQL_RES* res = mysql_store_result(handle);
	if (!res) { queryFailed(); return nullptr; }
	if (success) *success = true;
	DBResult_ptr result = std::make_shared<DBResult>(res);
	if (!result->hasNext()) {
		return nullptr;
	}
	return result;
}

std::string Database::escapeString(const std::string& s) const
{
	std::lock_guard<std::recursive_mutex> lock(databaseLock);
	if (!handle) return escapeBlob(s.data(), s.size());
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
