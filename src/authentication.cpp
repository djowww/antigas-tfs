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
	if (!isValidAccountTypeValue(row.type)) {
		return failed(AuthenticationStatus::DatabaseError);
	}

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
	if (result.status != AuthenticationStatus::Success) {
		return result;
	}

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

	AuthenticationResult result = loadAccount(accountRow);
	if (result.status != AuthenticationStatus::Success) {
		return result;
	}

	AuthCharacterRow characterRow;
	const AuthQueryStatus characterQuery = data.getCharacter(characterName, characterRow);
	if (characterQuery == AuthQueryStatus::Error) {
		return failed(AuthenticationStatus::DatabaseError);
	}
	if (characterQuery == AuthQueryStatus::Empty || characterRow.accountId != accountRow.id || characterRow.deletion != 0) {
		return failed(AuthenticationStatus::InvalidCharacter);
	}

	result.characterName = characterRow.name;
	return result;
}

AccountAuthenticationFailureLimiter::AccountAuthenticationFailureLimiter(std::size_t capacity,
	                                                                        Clock::duration expiration,
	                                                                        NowFunction now) :
	capacity(capacity), expiration(expiration), now(std::move(now))
{}

void AccountAuthenticationFailureLimiter::eraseEntry(std::map<uint32_t, Entry>::iterator entry)
{
	lru.erase(entry->second.lruPosition);
	entries.erase(entry);
}

AccountAuthenticationFailureLimiter::Delay AccountAuthenticationFailureLimiter::processResult(uint32_t accountNumber, AuthenticationStatus status)
{
	if (accountNumber == 0) {
		return Delay::zero();
	}

	std::lock_guard<std::mutex> lock(mutex);
	if (status == AuthenticationStatus::Success) {
		std::map<uint32_t, Entry>::iterator existing = entries.find(accountNumber);
		if (existing != entries.end()) {
			eraseEntry(existing);
		}
		return Delay::zero();
	}
	if (status != AuthenticationStatus::InvalidCredentials || capacity == 0) {
		return Delay::zero();
	}

	Clock::time_point currentTime;
	try {
		currentTime = now ? now() : Clock::now();
	} catch (...) {
		return Delay::zero();
	}

	std::map<uint32_t, Entry>::iterator entry = entries.find(accountNumber);
	if (entry != entries.end() && entry->second.expiresAt <= currentTime) {
		eraseEntry(entry);
		entry = entries.end();
	}

	if (entry == entries.end()) {
		if (entries.size() >= capacity) {
			while (!lru.empty()) {
				std::map<uint32_t, Entry>::iterator oldest = entries.find(lru.front());
				if (oldest == entries.end()) {
					lru.pop_front();
					continue;
				}
				eraseEntry(oldest);
				break;
			}
			if (entries.size() >= capacity) {
				return Delay::zero();
			}
		}

		try {
			lru.push_back(accountNumber);
			Entry value;
			value.failures = 1;
			value.expiresAt = currentTime + expiration;
			value.lruPosition = --lru.end();
			try {
				entries.insert(std::make_pair(accountNumber, value));
			} catch (...) {
				lru.pop_back();
				return Delay::zero();
			}
		} catch (...) {
			return Delay::zero();
		}
		return Delay::zero();
	}

	if (entry->second.failures < 10) {
		++entry->second.failures;
	}
	entry->second.expiresAt = currentTime + expiration;
	lru.splice(lru.end(), lru, entry->second.lruPosition);
	if (entry->second.failures <= 2) {
		return Delay::zero();
	}
	const uint8_t delayedFailures = static_cast<uint8_t>(entry->second.failures - 2);
	return Delay(std::min<uint32_t>(2000, static_cast<uint32_t>(delayedFailures) * 250));
}

std::size_t AccountAuthenticationFailureLimiter::size() const
{
	std::lock_guard<std::mutex> lock(mutex);
	return entries.size();
}

AccountAuthenticationFailureLimiter& getAccountAuthenticationFailureLimiter()
{
	static AccountAuthenticationFailureLimiter limiter;
	return limiter;
}
