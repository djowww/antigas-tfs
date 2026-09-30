#include "otpch.h"

#include "authentication.h"
#include "tools.h"

namespace {
AuthenticationResult failed(AuthenticationStatus status)
{
	AuthenticationResult result;
	result.status = status;
	return result;
}

AuthenticationResult loadAccount(const AuthAccountRow& row)
{
	AuthenticationResult result;
	result.status = AuthenticationStatus::Success;
	result.account.id = row.id;
	result.account.accountType = static_cast<AccountType_t>(row.type);
	result.account.premiumDays = row.premiumDays;
	result.account.lastDay = row.lastDay;
	result.accountId = row.id;
	return result;
}
}

AuthenticationResult authenticateLoginServer(AuthenticationDataSource& data, uint32_t accountNumber, const std::string& password)
{
	AuthAccountRow accountRow;
	const AuthQueryStatus accountQuery = data.getAccount(accountNumber, accountRow);
	if (accountQuery == AuthQueryStatus::Error) {
		return failed(AuthenticationStatus::DatabaseError);
	}
	if (accountQuery == AuthQueryStatus::Empty || transformToSHA1(password) != accountRow.password) {
		return failed(AuthenticationStatus::InvalidCredentials);
	}

	AuthenticationResult result = loadAccount(accountRow);
	std::vector<AuthCharacterRow> characterRows;
	const AuthQueryStatus charactersQuery = data.getCharacters(accountRow.id, characterRows);
	if (charactersQuery == AuthQueryStatus::Error) {
		return failed(AuthenticationStatus::DatabaseError);
	}
	for (const AuthCharacterRow& character : characterRows) {
		if (character.deletion == 0) {
			result.account.characters.push_back(character.name);
		}
	}
	std::sort(result.account.characters.begin(), result.account.characters.end());
	return result;
}

AuthenticationResult authenticateGameWorld(AuthenticationDataSource& data, uint32_t accountNumber, const std::string& password, const std::string& characterName)
{
	AuthAccountRow accountRow;
	const AuthQueryStatus accountQuery = data.getAccount(accountNumber, accountRow);
	if (accountQuery == AuthQueryStatus::Error) {
		return failed(AuthenticationStatus::DatabaseError);
	}
	if (accountQuery == AuthQueryStatus::Empty || transformToSHA1(password) != accountRow.password) {
		return failed(AuthenticationStatus::InvalidCredentials);
	}

	AuthCharacterRow characterRow;
	const AuthQueryStatus characterQuery = data.getCharacter(characterName, characterRow);
	if (characterQuery == AuthQueryStatus::Error) {
		return failed(AuthenticationStatus::DatabaseError);
	}
	if (characterQuery == AuthQueryStatus::Empty || characterRow.accountId != accountRow.id || characterRow.deletion != 0) {
		return failed(AuthenticationStatus::InvalidCharacter);
	}

	AuthenticationResult result = loadAccount(accountRow);
	result.characterName = characterRow.name;
	return result;
}
