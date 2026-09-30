#include "otpch.h"
#include "ban.h"
#include "database.h"
#include "databasetasks.h"
#include <stdexcept>

// Link this test with src/ban.cpp, not database.cpp/databasetasks.cpp.
// The production lookup runs against deterministic query results; no MySQL
// connection, task worker or live data is used.
namespace {
enum class Response { Error, Empty, Row };
Response response = Response::Empty;
std::map<std::string, std::string> fields;
std::vector<std::string> reads, queuedWrites;
struct FakeResult {
	std::map<std::string, std::string> values;
	std::vector<char*> columns;
};

void require(bool ok, const char* message)
{
	if (!ok) throw std::runtime_error(message);
}

void fixture(Response next, time_t expires = 0)
{
	response = next;
	fields = {{"reason", "fixture reason"}, {"expires_at", std::to_string(expires)},
	          {"banned_at", "100"}, {"banned_by", "7"}, {"name", "Fixture Moderator"}, {"1", "1"}};
	reads.clear();
	queuedWrites.clear();
}
}

DatabaseTasks g_databaseTasks;
Database::~Database() = default;

DBResult_ptr Database::storeQuery(const std::string& query, bool* success)
{
	reads.push_back(query);
	if (success) *success = response != Response::Error;
	if (response != Response::Row) return nullptr;
	auto* data = new FakeResult;
	data->values = fields;
	return std::make_shared<DBResult>(reinterpret_cast<MYSQL_RES*>(data));
}

std::string Database::escapeString(const std::string& value) const
{
	// This seam handles only the ASCII fixture reason, not untrusted SQL input.
	return "'" + value + "'";
}

DBResult::DBResult(MYSQL_RES* result) : handle(result)
{
	auto* data = reinterpret_cast<FakeResult*>(handle);
	for (auto& value : data->values) {
		listNames[value.first] = data->columns.size();
		data->columns.push_back(const_cast<char*>(value.second.c_str()));
	}
	row = data->columns.data();
}

DBResult::~DBResult()
{
	delete reinterpret_cast<FakeResult*>(handle);
}

std::string DBResult::getString(const std::string& field) const
{
	return reinterpret_cast<FakeResult*>(handle)->values.at(field);
}

void DatabaseTasks::addTask(const std::string& query,
                            const std::function<void(DBResult_ptr, bool)>&, bool)
{
	queuedWrites.push_back(query);
}

int main()
{
	try {
		BanInfo info;
		for (auto next : {Response::Error, Response::Empty}) {
			const auto expected = next == Response::Error ? BanLookupResult::Error : BanLookupResult::Clear;
			fixture(next);
			require(IOBan::lookupAccountBan(42, info) == expected, "account lookup must distinguish query failure from no ban");
			require(queuedWrites.empty(), "account error/empty result must not queue expiry cleanup");
			fixture(next);
			require(IOBan::lookupIpBan(1234, info) == expected, "IP lookup must distinguish query failure from no ban");
			require(queuedWrites.empty(), "IP error/empty result must not queue expiry cleanup");
			fixture(next);
			require(IOBan::lookupPlayerNamelock(9) == expected, "namelock lookup must distinguish query failure from no lock");
		}
		fixture(Response::Error);
		require(IOBan::lookupIpBan(0, info) == BanLookupResult::Clear && reads.empty(), "zero IP must retain the local/no-address behavior without querying");

		for (time_t expires : {time_t(0), time(nullptr) + 3600}) {
			fixture(Response::Row, expires);
			require(IOBan::lookupAccountBan(42, info) == BanLookupResult::Banned, "active/permanent account ban must remain blocked");
			require(info.reason == "fixture reason" && info.bannedBy == "Fixture Moderator" && info.expiresAt == expires, "active account ban must preserve its message data");
			require(queuedWrites.empty(), "active account ban must not be deleted");
			fixture(Response::Row, expires);
			require(IOBan::lookupIpBan(1234, info) == BanLookupResult::Banned, "active/permanent IP ban must remain blocked");
			require(info.expiresAt == expires && queuedWrites.empty(), "active IP ban must preserve expiry and avoid deletion");
		}
		fixture(Response::Row, time(nullptr) - 3600);
		require(IOBan::lookupAccountBan(42, info) == BanLookupResult::Clear, "expired account ban must retain access behavior");
		require(queuedWrites.size() == 2 && queuedWrites[0].find("INSERT INTO `account_ban_history`") == 0 && queuedWrites[1].find("DELETE FROM `account_bans`") == 0, "expired account ban must queue history before deletion");
		fixture(Response::Row, time(nullptr) - 3600);
		require(IOBan::lookupIpBan(1234, info) == BanLookupResult::Clear, "expired IP ban must retain access behavior");
		require(queuedWrites.size() == 1 && queuedWrites[0].find("DELETE FROM `ip_bans`") == 0, "expired IP ban must queue deletion");
		fixture(Response::Row);
		require(IOBan::lookupPlayerNamelock(9) == BanLookupResult::Banned, "existing namelock must remain blocked");
		std::cout << "PASS: production ban lookups distinguish error, clear, active and expired results without a database." << std::endl;
		return 0;
	} catch (const std::exception& error) {
		std::cerr << "FAIL: " << error.what() << std::endl;
		return 1;
	}
}
