#include "otpch.h"
#include "authentication.h"
#include "tools.h"

#include <stdexcept>

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

int main()
{
	try {
		testAccountQueryOutcomes();
		testLoginserverDecisions();
		testGameworldDecisions();
		testPublicErrorMapping();
		std::cout << "PASS: synthetic loginserver/gameworld auth outcomes and public error mapping." << std::endl;
		return 0;
	} catch (const std::exception& error) {
		std::cerr << "FAIL: " << error.what() << std::endl;
		return 1;
	}
}
