#define FS_TOOLS_H_5F9A9742DA194628830AA1C64909AE43

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <string>

inline std::string asLowerCaseString(std::string value)
{
	std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) {
		return static_cast<char>(std::tolower(c));
	});
	return value;
}

#include "../src/script.h"

int main()
{
	ScriptReader reader;
	const std::string sourceFile(__FILE__);
	for (int depth = 0; depth < 3; ++depth) {
		if (!reader.open(sourceFile)) {
			std::cerr << "Failed to open test source at a supported include depth\n";
			return 1;
		}
	}

	if (reader.open(sourceFile)) {
		std::cerr << "An include deeper than the three-file stack was accepted\n";
		return 1;
	}
	if (reader.RecursionDepth != -1) {
		std::cerr << "Rejecting excessive include depth did not close the open file stack\n";
		return 1;
	}

	if (!reader.open(sourceFile)) {
		std::cerr << "ScriptReader could not be reused after rejecting excessive depth\n";
		return 1;
	}
	reader.close();
	std::cout << "PASS: ScriptReader rejects excessive nested includes and closes valid handles\n";
	return 0;
}
