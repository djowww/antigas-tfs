#include "scriptenvironmentindex.h"

#include <stdexcept>

namespace {
void require(bool condition, const char* message)
{
	if (!condition) {
		throw std::runtime_error(message);
	}
}

void testOverflowRefusalPreservesActiveStack()
{
	ScriptEnvironmentIndex index;
	require(index.current() == -1, "script environment stack should start empty");

	for (std::int32_t depth = 0; depth < ScriptEnvironmentIndex::CAPACITY; ++depth) {
		require(index.reserve(), "every available script environment should be reservable");
		require(index.current() == depth, "reservation should select the next in-range environment");
	}

	require(!index.reserve(), "the first reservation beyond capacity should fail");
	require(index.current() == ScriptEnvironmentIndex::CAPACITY - 1,
	        "a failed reservation must not advance beyond the last environment");

	for (std::int32_t depth = ScriptEnvironmentIndex::CAPACITY - 1; depth >= 0; --depth) {
		require(index.current() == depth, "unwind should retain the active environment index");
		require(index.release(), "each successful reservation should unwind exactly once");
	}

	require(index.current() == -1, "unwinding all active callbacks should restore the empty stack");
	require(!index.release(), "releasing an empty script environment stack should fail");
	require(index.current() == -1, "failed release must not corrupt the stack index");
}
}

int main()
{
	try {
		testOverflowRefusalPreservesActiveStack();
		return 0;
	} catch (const std::exception&) {
		return 1;
	}
}
