#include "callbackgeneration.h"

#include <iostream>
#include <stdexcept>

namespace {
void require(bool condition, const char* message)
{
	if (!condition) {
		throw std::runtime_error(message);
	}
}

void queuedCallbackIsInvalidatedBeforeOwnerDataIsReleased()
{
	CallbackGeneration generation;
	const CallbackGeneration::Snapshot scheduledAt = generation.snapshot();
	bool ownerDataAlive = true;
	unsigned executions = 0;
	std::function<void()> callback = generation.guard(scheduledAt, [&]() {
		require(ownerDataAlive, "stale callback must not access released owner data");
		++executions;
	});

	// Model a callback already removed from the scheduler queue and waiting in
	// the dispatcher while a reload invalidates and releases its owner.
	generation.invalidate();
	ownerDataAlive = false;
	callback();
	require(executions == 0, "invalidated callback must be discarded");
}

void currentCallbackRunsOnce()
{
	CallbackGeneration generation;
	const CallbackGeneration::Snapshot scheduledAt = generation.snapshot();
	unsigned executions = 0;
	std::function<void()> callback = generation.guard(scheduledAt, [&]() { ++executions; });

	callback();
	require(executions == 1, "callback in the current generation must execute");

	generation.invalidate();
	callback();
	require(executions == 1, "callback must stop executing after invalidation");
}

void destroyedOwnerInvalidatesQueuedCallback()
{
	std::function<void()> callback;
	unsigned executions = 0;
	{
		CallbackGeneration generation;
		callback = generation.guard(generation.snapshot(), [&]() { ++executions; });
	}

	callback();
	require(executions == 0, "callback must be a no-op after its generation owner is destroyed");
}
}

int main()
{
	try {
		queuedCallbackIsInvalidatedBeforeOwnerDataIsReleased();
		currentCallbackRunsOnce();
		destroyedOwnerInvalidatesQueuedCallback();
	} catch (const std::exception& exception) {
		std::cerr << "FAIL: " << exception.what() << std::endl;
		return 1;
	}

	std::cout << "Callback generation regressions passed." << std::endl;
	return 0;
}
