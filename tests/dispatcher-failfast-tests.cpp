#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "scheduler.h"
#include "databasetasks.h"
#include "rsa.h"

#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <stdexcept>
#include <typeinfo>

// Same production-core globals as events-reset-tests. Only the dispatcher is
// started: no database connection, scheduler, socket, or live world is started.
DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;

namespace {
constexpr const char* FIXTURE_MESSAGE = "dispatcher failfast test fixture\nsecond line\x1B";
constexpr const char* QUEUED_MARKER = "DISPATCHER_FAILFAST_TASKS_QUEUED";
constexpr const char* EXPECTED_MARKER = "DISPATCHER_FAILFAST_EXPECTED_TERMINATION";
constexpr const char* POSTERIOR_MARKER = "DISPATCHER_FAILFAST_POSTERIOR_EXECUTED";

[[noreturn]] void failUnexpectedly() noexcept
{
	std::fputs("DISPATCHER_FAILFAST_UNEXPECTED_FAILURE\n", stderr);
	std::fflush(stderr);
	std::_Exit(1);
}

[[noreturn]] void handleTermination() noexcept
{
	const std::exception_ptr exception = std::current_exception();
	if (exception) {
		try {
			std::rethrow_exception(exception);
		} catch (const std::runtime_error& error) {
			if (typeid(error) == typeid(std::runtime_error) &&
			        std::strcmp(error.what(), FIXTURE_MESSAGE) == 0) {
				std::puts(EXPECTED_MARKER);
				std::fflush(stdout);
				std::_Exit(86);
			}
		} catch (...) {
			// No unrelated exception is accepted as evidence of this fixture.
		}
	}
	failUnexpectedly();
}
}

int main()
{
	std::set_terminate(handleTermination);
	try {
		std::mutex barrierMutex;
		std::condition_variable barrierSignal;
		bool readyToThrow = false;
		std::promise<void> firstTaskStarted;
		auto firstStarted = firstTaskStarted.get_future();

		g_dispatcher.start();
		g_dispatcher.addTask(createTask([&]() {
			std::unique_lock<std::mutex> barrierLock(barrierMutex);
			firstTaskStarted.set_value();
			barrierSignal.wait(barrierLock, [&]() { return readyToThrow; });
			barrierLock.unlock();
			throw std::runtime_error(FIXTURE_MESSAGE);
		}, 17));
		if (firstStarted.wait_for(std::chrono::seconds(3)) != std::future_status::ready) {
			failUnexpectedly();
		}
		g_dispatcher.addTask(createTask([]() {
			std::puts(POSTERIOR_MARKER);
			std::fflush(stdout);
			failUnexpectedly();
		}, 23));
		const QueueMetricsSnapshot pending = g_dispatcher.getQueueMetrics();
		if (pending.queuedCount != 1 || pending.trackedPayloadBytes != 23 ||
		        pending.peakQueuedCount != 1 || pending.peakTrackedPayloadBytes != 23 || pending.counterAnomaly) {
			failUnexpectedly();
		}

		// The throwing task cannot leave its barrier until the posterior task
		// has been published to the real production dispatcher queue.
		std::puts(QUEUED_MARKER);
		std::fflush(stdout);
		{
			std::lock_guard<std::mutex> barrierLock(barrierMutex);
			readyToThrow = true;
		}
		barrierSignal.notify_one();

		g_dispatcher.join();
	} catch (...) {
		failUnexpectedly();
	}
	failUnexpectedly();
}
