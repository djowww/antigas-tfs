#ifndef FS_TIMEUTILS_H_1CE3AC4F4EEA4F25B8451D41A10FCB1A
#define FS_TIMEUTILS_H_1CE3AC4F4EEA4F25B8451D41A10FCB1A

#include <ctime>
#ifndef _WIN32
#include <mutex>
#endif

inline bool getLocalTime(std::time_t timestamp, std::tm& result)
{
#ifdef _WIN32
	return localtime_s(&result, &timestamp) == 0;
#else
	static std::mutex localTimeMutex;
	const std::lock_guard<std::mutex> lock(localTimeMutex);
	const std::tm* sharedResult = std::localtime(&timestamp);
	if (!sharedResult) {
		return false;
	}
	result = *sharedResult;
	return true;
#endif
}

#endif
