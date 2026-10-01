#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "databasetasks.h"
#include "scheduler.h"
#include "rsa.h"
#include <cstdio>
#include <future>
#include <stdexcept>
#include <thread>
#include <vector>

DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;

namespace {
void require(bool ok, const char* message)
{
	if (!ok) throw std::runtime_error(message);
}

void ready(std::future<void>& completion, const char* message)
{
	require(completion.wait_for(std::chrono::seconds(3)) == std::future_status::ready, message);
	completion.get();
}

class FixtureScheduler : public Scheduler {
	public:
		std::mutex& mutex() { return eventLock; }
};

struct Gate {
	std::promise<void> entered;
	std::promise<void> releasePromise;
	std::shared_future<void> release = releasePromise.get_future().share();
};

class BlockingDestructionTask : public SchedulerTask {
	public:
		BlockingDestructionTask(uint32_t delay, const std::function<void()>& callback, std::shared_ptr<Gate> gate) :
			SchedulerTask(delay, callback), gate(std::move(gate)) {}
		~BlockingDestructionTask() {
			gate->entered.set_value();
			gate->release.wait();
		}
	private:
		std::shared_ptr<Gate> gate;
};

class CancellationTask : public SchedulerTask {
	public:
		CancellationTask(const std::function<void()>& callback, std::promise<void>& destroyed) :
			SchedulerTask(30000, callback), destroyed(destroyed) {}
		~CancellationTask() { destroyed.set_value(); }
	private:
		std::promise<void>& destroyed;
};

void normalExecutionAndCancellation()
{
	FixtureScheduler scheduler;
	scheduler.start();
	auto executed = std::make_shared<std::promise<void>>();
	auto execution = executed->get_future();
	require(scheduler.addEvent(createSchedulerTask(50, [executed]() { executed->set_value(); })) != 0,
	        "running scheduler must accept a normal event");
	ready(execution, "normal event must execute through the real dispatcher");
	std::atomic<unsigned> cancelledExecutions{0};
	std::promise<void> destroyed;
	auto destruction = destroyed.get_future();
	const auto id = scheduler.addEvent(new CancellationTask([&]() { ++cancelledExecutions; }, destroyed));
	require(id != 0 && scheduler.stopEvent(id), "pending event must be cancellable");
	ready(destruction, "cancelled task must be released");
	require(!scheduler.stopEvent(id) && cancelledExecutions == 0, "cancelled event must not run or cancel twice");
	scheduler.shutdown();
	scheduler.join();
}

void queueMetricsTrackTombstonesAndCompaction()
{
	FixtureScheduler scheduler;
	scheduler.start();
	std::vector<uint32_t> ids;
	for (std::size_t index = 0; index < 4; ++index) {
		const std::size_t trackedBytes = 11 + index;
		const uint32_t eventId = scheduler.addEvent(createSchedulerTask(30000, []() {}, trackedBytes));
		require(eventId != 0, "running scheduler must accept metrics fixtures");
		ids.push_back(eventId);
	}

	SchedulerQueueMetricsSnapshot snapshot = scheduler.getQueueMetrics();
	require(snapshot.activeEventCount == 4 && snapshot.retained.queuedCount == 4, "scheduler metrics must expose active and retained event counts separately");
	require(snapshot.retained.trackedPayloadBytes == 50, "scheduler metrics must sum explicitly tracked event payloads");

	require(scheduler.stopEvent(ids[0]), "scheduler must cancel the first metrics event");
	snapshot = scheduler.getQueueMetrics();
	require(snapshot.activeEventCount == 3 && snapshot.retained.queuedCount == 4 && snapshot.cancelledRetainedCount == 1, "cancelled tombstone remains counted until compaction");
	require(snapshot.retained.trackedPayloadBytes == 50, "tombstone payload remains counted while its node is retained");

	require(scheduler.stopEvent(ids[1]), "scheduler must cancel the second metrics event");
	snapshot = scheduler.getQueueMetrics();
	require(snapshot.activeEventCount == 2 && snapshot.retained.queuedCount == 2 && snapshot.cancelledRetainedCount == 0, "compaction must remove cancelled nodes from retained counts");
	require(snapshot.retained.trackedPayloadBytes == 27, "compaction must remove cancelled payload bytes");

	require(scheduler.stopEvent(ids[2]) && scheduler.stopEvent(ids[3]), "scheduler must cancel remaining metrics events");
	snapshot = scheduler.getQueueMetrics();
	require(snapshot.activeEventCount == 0 && snapshot.retained.queuedCount == 0 && snapshot.retained.trackedPayloadBytes == 0, "cancelling all events must clear current queue metrics");
	scheduler.shutdown();
	scheduler.join();
}

void shutdownRacesWithFirstWorkerLock()
{
	for (unsigned attempt = 0; attempt < 50; ++attempt) {
		FixtureScheduler scheduler;
		std::unique_lock<std::mutex> held(scheduler.mutex());
		scheduler.start();
		std::promise<void> shutdownStarted;
		auto started = shutdownStarted.get_future();
		std::thread shutdown([&]() {
			shutdownStarted.set_value();
			scheduler.shutdown();
		});
		ready(started, "shutdown contender must start");
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
		held.unlock();
		shutdown.join();
		scheduler.join();
	}
}

void shutdownWhileTimedTaskExpires()
{
	FixtureScheduler scheduler;
	auto gate = std::make_shared<Gate>();
	auto destroying = gate->entered.get_future();
	std::atomic<unsigned> unexpectedExecutions{0};
	const uint32_t delay = 2000;
	auto* task = new BlockingDestructionTask(delay, [&]() { ++unexpectedExecutions; }, gate);
	const auto deadline = task->getCycle();
	scheduler.start();
	require(scheduler.addEvent(task) != 0, "running scheduler must accept the deadline fixture");
	std::this_thread::sleep_for(std::chrono::milliseconds(100));
	std::thread shutdown([&]() { scheduler.shutdown(); });
	ready(destroying, "shutdown must hold the queue lock while destroying the fixture");
	require(std::chrono::system_clock::now() < deadline, "shutdown must own the queue lock before the task deadline");
	std::this_thread::sleep_until(deadline + std::chrono::milliseconds(20));
	gate->releasePromise.set_value();
	shutdown.join();
	scheduler.join();
	require(unexpectedExecutions == 0, "shutdown deadline task must never execute");
}

void addEventAfterShutdownReleasesTask()
{
	FixtureScheduler scheduler;
	scheduler.shutdown();
	std::shared_ptr<int> retained(new int(1));
	std::weak_ptr<int> closure = retained;
	SchedulerTask* task = createSchedulerTask(1000, [retained]() {});
	retained.reset();
	require(scheduler.addEvent(task) == 0, "stopped scheduler must reject a new event");
	require(closure.expired(), "rejected event must release its callback closure");
}

void duplicateEventIdPreservesExistingId()
{
	FixtureScheduler scheduler;
	scheduler.start();
	std::shared_ptr<int> retained(new int(2));
	std::weak_ptr<int> existingClosure = retained;
	SchedulerTask* existing = createSchedulerTask(30000, [retained]() {});
	existing->setEventId(77);
	retained.reset();
	require(scheduler.addEvent(existing) == 77, "scheduler must accept the original event id");

	std::shared_ptr<int> duplicateRetained(new int(3));
	std::weak_ptr<int> duplicateClosure = duplicateRetained;
	SchedulerTask* duplicate = createSchedulerTask(30000, [duplicateRetained]() {});
	duplicate->setEventId(77);
	duplicateRetained.reset();
	require(scheduler.addEvent(duplicate) == 0, "scheduler must reject a duplicate event id");
	require(duplicateClosure.expired(), "rejected duplicate task must release its callback closure");
	require(scheduler.stopEvent(77), "rejecting a duplicate must preserve the original active event id");
	scheduler.shutdown();
	scheduler.join();
	require(existingClosure.expired(), "cancelling the original event must release its closure");
}
}

int main(int argc, char** argv)
{
	try {
		const std::string scenario = argc == 1 ? "all" : argc == 2 ? argv[1] : "invalid";
		require(scenario == "all" || scenario == "normal" || scenario == "shutdown-race" || scenario == "deadline" ||
		        scenario == "rejected-after-shutdown" || scenario == "duplicate-event-id",
		        "fixture scenario must be all, normal, shutdown-race, deadline, rejected-after-shutdown or duplicate-event-id");
		g_dispatcher.start();
		if (scenario == "all" || scenario == "normal") {
			normalExecutionAndCancellation();
			queueMetricsTrackTombstonesAndCompaction();
		}
		if (scenario == "all" || scenario == "shutdown-race") shutdownRacesWithFirstWorkerLock();
		if (scenario == "all" || scenario == "deadline") shutdownWhileTimedTaskExpires();
		if (scenario == "all" || scenario == "rejected-after-shutdown") addEventAfterShutdownReleasesTask();
		if (scenario == "all" || scenario == "duplicate-event-id") duplicateEventIdPreservesExistingId();
		g_dispatcher.shutdown();
		g_dispatcher.join();
		std::cout << "PASS: isolated real scheduler scenario " << scenario << "." << std::endl;
		return 0;
	} catch (const std::exception& error) {
		std::cerr << "FAIL: " << error.what() << std::endl;
		return 1;
	}
}
