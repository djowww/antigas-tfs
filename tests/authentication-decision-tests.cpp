#include "otpch.h"
#include "authentication.h"
#include "tools.h"

#include <stdexcept>
#include <atomic>
#include <thread>

static void require(bool condition, const char* message)
{
	if (!condition) throw std::runtime_error(message);
}

class FakeAuthenticationData : public AuthenticationDataSource
{
	public:
		AuthQueryStatus accountStatus = AuthQueryStatus::Found;
		AuthQueryStatus charactersStatus = AuthQueryStatus::Empty;
		AuthQueryStatus characterStatus = AuthQueryStatus::Found;
		AuthAccountRow account;
		std::vector<AuthCharacterRow> characters;
		AuthCharacterRow character;
		unsigned accountCalls = 0;
		unsigned charactersCalls = 0;
		unsigned characterCalls = 0;

		FakeAuthenticationData()
		{
			account.id = 42;
			account.password = transformToSHA1("synthetic-password");
			account.type = ACCOUNT_TYPE_NORMAL;
			account.premiumDays = 13;
			account.lastDay = 1234;
			character.accountId = 42;
			character.name = "Synthetic Character";
		}

		AuthQueryStatus getAccount(uint32_t accountNumber, AuthAccountRow& row) override
		{
			++accountCalls;
			if (accountStatus == AuthQueryStatus::Found && accountNumber == account.id) row = account;
			return accountStatus;
		}

		AuthQueryStatus getCharacters(uint32_t accountId, std::vector<AuthCharacterRow>& rows) override
		{
			++charactersCalls;
			require(accountId == account.id, "character list must query authenticated account id");
			rows = characters;
			return charactersStatus;
		}

		AuthQueryStatus getCharacter(const std::string&, AuthCharacterRow& row) override
		{
			++characterCalls;
			if (characterStatus == AuthQueryStatus::Found) row = character;
			return characterStatus;
		}
};

static void testAccountQueryOutcomes()
{
	for (AuthQueryStatus queryStatus : {AuthQueryStatus::Empty, AuthQueryStatus::Error}) {
		FakeAuthenticationData data;
		data.accountStatus = queryStatus;
		auto login = authenticateLoginServer(data, 42, "synthetic-password");
		require(login.status == (queryStatus == AuthQueryStatus::Error ? AuthenticationStatus::DatabaseError : AuthenticationStatus::InvalidCredentials), "loginserver account query outcome must be distinguished");
		require(data.accountCalls == 1 && data.charactersCalls == 0, "failed account query must not query character list");

		FakeAuthenticationData gameData;
		gameData.accountStatus = queryStatus;
		auto game = authenticateGameWorld(gameData, 42, "synthetic-password", "Synthetic Character");
		require(game.status == (queryStatus == AuthQueryStatus::Error ? AuthenticationStatus::DatabaseError : AuthenticationStatus::InvalidCredentials), "gameworld account query outcome must be distinguished");
		require(gameData.accountCalls == 1 && gameData.characterCalls == 0, "failed gameworld account query must not query character");
	}

	FakeAuthenticationData data;
	auto unknown = authenticateLoginServer(data, 999, "synthetic-password");
	require(unknown.status == AuthenticationStatus::InvalidCredentials, "missing account must map to generic invalid credentials");
	require(data.accountCalls == 1 && data.charactersCalls == 0, "unknown account must stop before character query");
}

static void testLoginserverDecisions()
{
	FakeAuthenticationData wrongPasswordData;
	auto wrongPassword = authenticateLoginServer(wrongPasswordData, 42, "wrong-password");
	require(wrongPassword.status == AuthenticationStatus::InvalidCredentials, "wrong password must be invalid credentials");
	require(wrongPasswordData.accountCalls == 1 && wrongPasswordData.charactersCalls == 0, "wrong password must not query characters");

	FakeAuthenticationData listErrorData;
	listErrorData.charactersStatus = AuthQueryStatus::Error;
	auto listError = authenticateLoginServer(listErrorData, 42, "synthetic-password");
	require(listError.status == AuthenticationStatus::DatabaseError, "character-list SQL error must not become successful empty list");
	require(listErrorData.accountCalls == 1 && listErrorData.charactersCalls == 1, "valid credentials must query the character list once");

	FakeAuthenticationData emptyListData;
	auto emptyList = authenticateLoginServer(emptyListData, 42, "synthetic-password");
	require(emptyList.status == AuthenticationStatus::Success, "empty successful character list is valid");
	require(emptyList.account.id == 42 && emptyList.account.premiumDays == 13 && emptyList.account.characters.empty(), "successful login must carry account fields and empty list");
	require(emptyListData.accountCalls == 1 && emptyListData.charactersCalls == 1, "successful login must query account and list once");

	FakeAuthenticationData listData;
	listData.charactersStatus = AuthQueryStatus::Found;
	AuthCharacterRow visibleZ;
	visibleZ.accountId = 42;
	visibleZ.name = "Visible Z";
	AuthCharacterRow deleted;
	deleted.accountId = 42;
	deleted.name = "Deleted";
	deleted.deletion = 77;
	AuthCharacterRow visibleA;
	visibleA.accountId = 42;
	visibleA.name = "Visible A";
	listData.characters.push_back(visibleZ);
	listData.characters.push_back(deleted);
	listData.characters.push_back(visibleA);
	auto visibleCharacters = authenticateLoginServer(listData, 42, "synthetic-password");
	require(visibleCharacters.status == AuthenticationStatus::Success, "found character list must authenticate");
	require(visibleCharacters.account.characters == std::vector<std::string>({"Visible A", "Visible Z"}), "loginserver must filter deleted and sort live characters");
}

static void testGameworldDecisions()
{
	FakeAuthenticationData wrongPasswordData;
	auto wrongPassword = authenticateGameWorld(wrongPasswordData, 42, "wrong-password", "Synthetic Character");
	require(wrongPassword.status == AuthenticationStatus::InvalidCredentials, "gameworld wrong password must be invalid credentials");
	require(wrongPasswordData.accountCalls == 1 && wrongPasswordData.characterCalls == 0, "wrong password must not query character");

	FakeAuthenticationData missingCharacterData;
	missingCharacterData.characterStatus = AuthQueryStatus::Empty;
	auto missingCharacter = authenticateGameWorld(missingCharacterData, 42, "synthetic-password", "Missing");
	require(missingCharacter.status == AuthenticationStatus::InvalidCharacter, "missing character must be invalid character");
	require(missingCharacterData.accountCalls == 1 && missingCharacterData.characterCalls == 1, "valid credentials must query character once");

	FakeAuthenticationData characterErrorData;
	characterErrorData.characterStatus = AuthQueryStatus::Error;
	auto characterError = authenticateGameWorld(characterErrorData, 42, "synthetic-password", "Synthetic Character");
	require(characterError.status == AuthenticationStatus::DatabaseError, "character SQL error must be database error");

	FakeAuthenticationData ownerMismatchData;
	ownerMismatchData.character.accountId = 99;
	auto ownerMismatch = authenticateGameWorld(ownerMismatchData, 42, "synthetic-password", "Synthetic Character");
	require(ownerMismatch.status == AuthenticationStatus::InvalidCharacter, "character owned by another account must be rejected");

	FakeAuthenticationData deletedCharacterData;
	deletedCharacterData.character.deletion = 1;
	auto deletedCharacter = authenticateGameWorld(deletedCharacterData, 42, "synthetic-password", "Synthetic Character");
	require(deletedCharacter.status == AuthenticationStatus::InvalidCharacter, "deleted character must be rejected");

	FakeAuthenticationData validData;
	auto valid = authenticateGameWorld(validData, 42, "synthetic-password", "Synthetic Character");
	require(valid.status == AuthenticationStatus::Success && valid.accountId == 42, "valid gameworld credentials must succeed");
	require(valid.characterName == "Synthetic Character", "gameworld must return canonical character name");
	require(validData.accountCalls == 1 && validData.characterCalls == 1, "gameworld success must query account and character once");
}

static void testPublicErrorMapping()
{
	const char* generic = authenticationFailureMessage(AuthenticationStatus::InvalidCredentials);
	require(std::string(generic) == authenticationFailureMessage(AuthenticationStatus::InvalidCharacter), "invalid character must use generic public message");
	require(std::string(generic) == "Account number or password is not correct.", "invalid credentials text must remain generic");
	require(std::string(authenticationFailureMessage(AuthenticationStatus::DatabaseError)) == "Login temporarily unavailable. Please try again later.", "database error must report temporary unavailability");
}

static void testFailureLimiterProgressionAndExpiry()
{
	AccountAuthenticationFailureLimiter::Clock::time_point now;
	AccountAuthenticationFailureLimiter limiter(8, std::chrono::minutes(10), [&now]() { return now; });
	auto fail = [&limiter](uint32_t account) {
		return limiter.processResult(account, AuthenticationStatus::InvalidCredentials).count();
	};
	require(fail(42) == 0 && fail(42) == 0, "first two credential failures must be immediate");
	for (int failure = 3; failure <= 10; ++failure) {
		require(fail(42) == std::min(2000, (failure - 2) * 250), "progressive credential delay must increase to its cap");
	}
	require(fail(42) == 2000, "credential delay must stay capped at two seconds");
	now += std::chrono::minutes(10);
	require(fail(42) == 0 && limiter.size() == 1, "expired account state must restart at first failure");
}

static void testFailureLimiterStatusesAndZeroAccount()
{
	AccountAuthenticationFailureLimiter::Clock::time_point now;
	AccountAuthenticationFailureLimiter limiter(8, std::chrono::minutes(10), [&now]() { return now; });
	auto fail = [&limiter](AuthenticationStatus status) {
		return limiter.processResult(42, status).count();
	};
	require(limiter.processResult(0, AuthenticationStatus::InvalidCredentials).count() == 0 && limiter.size() == 0, "account zero must not allocate shared throttle state");
	require(fail(AuthenticationStatus::InvalidCredentials) == 0 && fail(AuthenticationStatus::InvalidCredentials) == 0, "initial invalid credentials must be tracked");
	require(fail(AuthenticationStatus::InvalidCharacter) == 0 && fail(AuthenticationStatus::DatabaseError) == 0, "invalid character and database error must not be penalized");
	require(fail(AuthenticationStatus::InvalidCredentials) == 250, "non-credential failures must not advance the counter");
	require(fail(AuthenticationStatus::Success) == 0 && limiter.size() == 0, "success must clear the account failure state");
	require(fail(AuthenticationStatus::InvalidCredentials) == 0 && fail(AuthenticationStatus::InvalidCredentials) == 0, "failures after success must start over");
}

static void testFailureLimiterCapacityAndExpiredLru()
{
	AccountAuthenticationFailureLimiter::Clock::time_point now;
	AccountAuthenticationFailureLimiter limiter(2, std::chrono::minutes(10), [&now]() { return now; });
	auto fail = [&limiter](uint32_t account) {
		return limiter.processResult(account, AuthenticationStatus::InvalidCredentials).count();
	};
	require(fail(1) == 0, "first account must be admitted");
	now += std::chrono::minutes(5);
	require(fail(2) == 0 && fail(2) == 0, "second account must be admitted and updated");
	now += std::chrono::minutes(5) + std::chrono::seconds(1);
	require(fail(3) == 0 && limiter.size() == 2, "expired least-recent entry must be recycled at capacity");
	require(fail(2) == 250, "non-expired LRU peer must retain its existing failure count");
	require(fail(3) == 0 && fail(3) == 250, "newly admitted account must retain its own state");
	require(fail(4) == 0 && limiter.size() == 2, "full non-expired LRU must fail open without growing state");
}

static void testFailureLimiterConcurrency()
{
	AccountAuthenticationFailureLimiter::Clock::time_point now;
	AccountAuthenticationFailureLimiter limiter(4, std::chrono::minutes(10), [&now]() { return now; });
	std::vector<std::thread> workers;
	std::atomic<int64_t> largestDelay(0);
	for (unsigned worker = 0; worker < 8; ++worker) {
		workers.push_back(std::thread([&limiter, &largestDelay]() {
			for (unsigned attempt = 0; attempt < 100; ++attempt) {
				const int64_t delay = limiter.processResult(42, AuthenticationStatus::InvalidCredentials).count();
				int64_t previous = largestDelay.load();
				while (previous < delay && !largestDelay.compare_exchange_weak(previous, delay)) {}
			}
		}));
	}
	for (std::thread& worker : workers) worker.join();
	require(largestDelay.load() == 2000 && limiter.size() == 1, "concurrent failures must remain bounded and serialized for one account");
	require(limiter.processResult(42, AuthenticationStatus::InvalidCredentials).count() == 2000, "concurrent failure count must remain capped after worker completion");
}

int main()
{
	try {
		testAccountQueryOutcomes();
		testLoginserverDecisions();
		testGameworldDecisions();
		testPublicErrorMapping();
		testFailureLimiterProgressionAndExpiry();
		testFailureLimiterStatusesAndZeroAccount();
		testFailureLimiterCapacityAndExpiredLru();
		testFailureLimiterConcurrency();
		std::cout << "PASS: synthetic auth outcomes, error mapping and bounded account failure limiter." << std::endl;
		return 0;
	} catch (const std::exception& error) {
		std::cerr << "FAIL: " << error.what() << std::endl;
		return 1;
	}
}
