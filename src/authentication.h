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

#endif
