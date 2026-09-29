#include "scriptfilename.h"

#include <stdexcept>

namespace {
void require(bool condition, const char* message)
{
	if (!condition) {
		throw std::runtime_error(message);
	}
}

void testBoundedFilenameCopy()
{
	char filename[8];
	copyScriptFilename(filename, "orc.xml");
	require(std::string(filename) == "orc.xml", "short script names should be copied completely");

	copyScriptFilename(filename, "1234567890.xml");
	require(std::string(filename) == "1234567", "long display names should be safely truncated");

	char singleByte[1];
	copyScriptFilename(singleByte, "anything");
	require(singleByte[0] == '\0', "a one-byte destination must remain terminated");

	copyScriptFilename(filename, std::string());
	require(filename[0] == '\0', "an empty script name should be copied as an empty string");
}
}

int main()
{
	try {
		testBoundedFilenameCopy();
		return 0;
	} catch (const std::exception&) {
		return 1;
	}
}
