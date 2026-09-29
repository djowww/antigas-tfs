#include "timeutils.h"

#include <atomic>
#include <iostream>
#include <thread>
#include <vector>

namespace {

bool sameTime(const std::tm& left, const std::tm& right)
{
	return left.tm_sec == right.tm_sec && left.tm_min == right.tm_min && left.tm_hour == right.tm_hour &&
		left.tm_mday == right.tm_mday && left.tm_mon == right.tm_mon && left.tm_year == right.tm_year &&
		left.tm_isdst == right.tm_isdst;
}

} // namespace

int main()
{
	const std::size_t threadCount = 8;
	const std::size_t iterations = 5000;
	std::vector<std::time_t> timestamps(threadCount);
	std::vector<std::tm> expected(threadCount);
	for (std::size_t index = 0; index < threadCount; ++index) {
		timestamps[index] = static_cast<std::time_t>(1609459200 + index * 98765);
		if (!getLocalTime(timestamps[index], expected[index])) {
			std::cerr << "Failed to convert a valid timestamp\n";
			return 1;
		}
	}

	std::atomic<bool> failed(false);
	std::vector<std::thread> workers;
	workers.reserve(threadCount);
	for (std::size_t index = 0; index < threadCount; ++index) {
		workers.emplace_back([&, index]() {
			for (std::size_t iteration = 0; iteration < iterations; ++iteration) {
				std::tm actual;
				if (!getLocalTime(timestamps[index], actual) || !sameTime(actual, expected[index])) {
					failed.store(true);
					return;
				}
			}
		});
	}

	for (std::thread& worker : workers) {
		worker.join();
	}
	if (failed.load()) {
		std::cerr << "Concurrent timestamp conversions returned mixed calendar fields\n";
		return 1;
	}

	std::cout << "PASS: concurrent local-time conversions preserve each timestamp\n";
	return 0;
}
