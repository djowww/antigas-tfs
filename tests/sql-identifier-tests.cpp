#include "sqlidentifier.h"

#include <stdexcept>

namespace {
void require(bool condition, const char* message)
{
	if (!condition) {
		throw std::runtime_error(message);
	}
}

void testIdentifierQuoting()
{
	require(quoteSqlIdentifier("players") == "`players`",
	        "ordinary table names should retain their existing SQL spelling");
	require(quoteSqlIdentifier("Guild Members") == "`Guild Members`",
	        "identifier characters other than backticks should be preserved");
	require(quoteSqlIdentifier("x` WHERE 1=1 -- ") == "`x`` WHERE 1=1 -- `",
	        "embedded backticks should be doubled inside the quoted identifier");
	require(quoteSqlIdentifier("") == "``", "empty identifiers should remain contained in quotes");
}
}

int main()
{
	try {
		testIdentifierQuoting();
		return 0;
	} catch (const std::exception&) {
		return 1;
	}
}
