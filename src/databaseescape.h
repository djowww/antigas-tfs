#ifndef FS_DATABASE_ESCAPE_H
#define FS_DATABASE_ESCAPE_H

#include <climits>
#include <cstddef>
#include <limits>

namespace databaseEscape {

inline bool getOutputCapacity(std::size_t inputLength, std::size_t& outputCapacity)
{
	if (sizeof(std::size_t) > sizeof(unsigned long) && inputLength > static_cast<std::size_t>(ULONG_MAX)) {
		return false;
	}

	const std::size_t maxSize = std::numeric_limits<std::size_t>::max();
	if (inputLength > (maxSize - 2) / 2) {
		return false;
	}

	outputCapacity = (inputLength * 2) + 1;
	return true;
}

inline bool isValidOutputLength(unsigned long outputLength, std::size_t outputCapacity)
{
	return outputLength != ULONG_MAX && outputLength < outputCapacity;
}

} // namespace databaseEscape

#endif
