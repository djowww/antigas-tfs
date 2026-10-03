#include "database-recovery.h"

#include <iostream>

int main()
{
	using databaseRecovery::shouldRetryRead;

	if (!shouldRetryRead(2006, 0, false, true)) {
		std::cerr << "error 2006 should retry an opted-in read once" << std::endl;
		return 1;
	}
	if (!shouldRetryRead(2013, 0, false, true)) {
		std::cerr << "error 2013 should retry an opted-in read once" << std::endl;
		return 1;
	}
	if (shouldRetryRead(1064, 0, false, true)) {
		std::cerr << "a SQL syntax error must not be retried" << std::endl;
		return 1;
	}
	if (shouldRetryRead(2006, 1, false, true)) {
		std::cerr << "a second read failure must not be retried" << std::endl;
		return 1;
	}
	if (shouldRetryRead(2006, 0, true, true)) {
		std::cerr << "a query inside a transaction must not be retried" << std::endl;
		return 1;
	}
	if (shouldRetryRead(2006, 0, false, false)) {
		std::cerr << "a query without explicit opt-in must not be retried" << std::endl;
		return 1;
	}

	return 0;
}
