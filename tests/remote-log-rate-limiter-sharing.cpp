#include "remotelogratelimiter.h"

RemoteLogRateLimiter& remoteLogRateLimiterFromSecondTranslationUnit()
{
	return remoteDiagnosticLogRateLimiter();
}
