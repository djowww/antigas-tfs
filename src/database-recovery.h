#ifndef FS_DATABASE_RECOVERY_H
#define FS_DATABASE_RECOVERY_H

namespace databaseRecovery {

inline bool isConnectionFailure(unsigned int error) noexcept
{
	// MySQL/MariaDB client error codes: connection/host, server gone/lost,
	// commands out of sync, and ER_SERVER_SHUTDOWN.
	return error == 2002U || error == 2003U || error == 2006U || error == 2013U
		|| error == 2014U || error == 1053U;
}

inline bool shouldRetryRead(unsigned int error, unsigned int attempt,
		bool transactionOpen, bool optedIn) noexcept
{
	return optedIn && attempt == 0U && !transactionOpen && isConnectionFailure(error);
}

} // namespace databaseRecovery

#endif
