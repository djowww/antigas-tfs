/**
 * Tibia GIMUD Server - a free and open-source MMORPG server emulator
 * Copyright (C) 2017  Alejandro Mujica <alejandrodemujica@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#ifndef FS_AUTHENTICATION_H_8F327B71962D4A70A388338CDA73F533
#define FS_AUTHENTICATION_H_8F327B71962D4A70A388338CDA73F533

#include "account.h"

#include <chrono>
#include <cstdint>
#include <functional>
#include <list>
#include <map>
#include <mutex>

inline bool isValidAccountTypeValue(int64_t value)
{
	return value >= ACCOUNT_TYPE_NORMAL && value <= ACCOUNT_TYPE_GOD;
}

inline bool isValidAccountTypeNumber(double value)
{
	return value == ACCOUNT_TYPE_NORMAL || value == ACCOUNT_TYPE_TUTOR ||
	       value == ACCOUNT_TYPE_SENIORTUTOR || value == ACCOUNT_TYPE_GAMEMASTER ||
	       value == ACCOUNT_TYPE_GOD;
}

enum class AuthenticationStatus {
	Success,
	InvalidCredentials,
	InvalidCharacter,
	DatabaseError,
};

struct AuthenticationResult {
	AuthenticationStatus status = AuthenticationStatus::DatabaseError;
	Account account;
	uint32_t accountId = 0;
	std::string characterName;
};

inline const char* authenticationFailureMessage(AuthenticationStatus status)
{
	return status == AuthenticationStatus::DatabaseError
		? "Login temporarily unavailable. Please try again later."
		: "Account number or password is not correct.";
}

enum class AuthQueryStatus {
	Found,
	Empty,
	Error,
};

struct AuthAccountRow {
	uint32_t id = 0;
	std::string password;
	int32_t type = 0;
	uint16_t premiumDays = 0;
	time_t lastDay = 0;
};

struct AuthCharacterRow {
	uint32_t accountId = 0;
	std::string name;
	uint64_t deletion = 0;
};

class AuthenticationDataSource
{
	public:
		virtual ~AuthenticationDataSource() = default;
		virtual AuthQueryStatus getAccount(uint32_t accountNumber, AuthAccountRow& row) = 0;
		virtual AuthQueryStatus getCharacters(uint32_t accountId, std::vector<AuthCharacterRow>& rows) = 0;
		virtual AuthQueryStatus getCharacter(const std::string& name, AuthCharacterRow& row) = 0;
};

AuthenticationResult authenticateLoginServer(AuthenticationDataSource& data, uint32_t accountNumber, const std::string& password);
AuthenticationResult authenticateGameWorld(AuthenticationDataSource& data, uint32_t accountNumber, const std::string& password, const std::string& characterName);

class AccountAuthenticationFailureLimiter
{
	public:
		typedef std::chrono::steady_clock Clock;
		typedef std::chrono::milliseconds Delay;
		typedef std::function<Clock::time_point()> NowFunction;

		explicit AccountAuthenticationFailureLimiter(std::size_t capacity = 65536,
		                                             Clock::duration expiration = std::chrono::minutes(10),
		                                             NowFunction now = NowFunction());
		Delay processResult(uint32_t accountNumber, AuthenticationStatus status);
		std::size_t size() const;

	private:
		struct Entry {
			uint8_t failures;
			Clock::time_point expiresAt;
			std::list<uint32_t>::iterator lruPosition;
		};

		void eraseEntry(std::map<uint32_t, Entry>::iterator entry);

		const std::size_t capacity;
		const Clock::duration expiration;
		NowFunction now;
		mutable std::mutex mutex;
		std::list<uint32_t> lru;
		std::map<uint32_t, Entry> entries;
};

AccountAuthenticationFailureLimiter& getAccountAuthenticationFailureLimiter();

#endif
