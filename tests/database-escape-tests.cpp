#include "databaseescape.h"

#include <limits>
#include <stdexcept>

namespace {
void require(bool condition, const char* message)
{
	if (!condition) {
		throw std::runtime_error(message);
	}
}
}

int main()
{
	try {
		std::size_t capacity = 0;
		require(databaseEscape::getOutputCapacity(0, capacity), "empty input must have room for the C API terminator");
		require(capacity == 1, "empty input capacity must be one byte");
		require(databaseEscape::isValidOutputLength(0, capacity), "zero escaped bytes fit an empty-input buffer");

		require(databaseEscape::getOutputCapacity(4, capacity), "ordinary input must have a bounded output buffer");
		require(capacity == 9, "escape capacity must reserve two bytes per input byte and a terminator");
		require(databaseEscape::isValidOutputLength(8, capacity), "maximum escaped content fits before the terminator");
		require(!databaseEscape::isValidOutputLength(9, capacity), "length reaching capacity must be rejected");
		require(!databaseEscape::isValidOutputLength(10, capacity), "length beyond capacity must be rejected");
		require(!databaseEscape::isValidOutputLength(ULONG_MAX, capacity), "C API error sentinel must be rejected");

		const std::size_t maxSize = std::numeric_limits<std::size_t>::max();
		require(!databaseEscape::getOutputCapacity((maxSize - 2) / 2 + 1, capacity), "capacity overflow must be rejected");
		if (sizeof(std::size_t) > sizeof(unsigned long)) {
			require(!databaseEscape::getOutputCapacity(static_cast<std::size_t>(ULONG_MAX) + 1, capacity), "input beyond the C API length type must be rejected");
		}
		return 0;
	} catch (const std::exception&) {
		return 1;
	}
}
