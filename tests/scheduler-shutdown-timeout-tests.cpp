#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "databasetasks.h"
#include "scheduler.h"
#include "rsa.h"
#include <dlfcn.h>
#include <pthread.h>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <future>
#include <stdexcept>
#include <vector>

// Linux executable-only pthread seams observe the exact native mutex/condition
// of the fixture Scheduler. Calls are forwarded to the real pthread functions.
// No socket, database, scheduler gameplay event or world is started.
DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;

namespace {
using MutexLockFunction = int (*)(pthread_mutex_t*);
using SignalFunction = int (*)(pthread_cond_t*);
using TimedWaitFunction = int (*)(pthread_cond_t*, pthread_mutex_t*, const timespec*);

MutexLockFunction realMutexLock()
{
	static auto function = reinterpret_cast<MutexLockFunction>(dlsym(RTLD_NEXT, "pthread_mutex_lock"));
	if (!function) {
		std::fputs("FAIL: real mutex function unavailable\n", stderr);
		std::_Exit(1);
	}
	return function;
}

TimedWaitFunction realTimedWait()
{
	static auto function = reinterpret_cast<TimedWaitFunction>(dlsym(RTLD_NEXT, "pthread_cond_timedwait"));
	if (!function) {
		std::fputs("FAIL: real timed wait function unavailable\n", stderr);
		std::_Exit(1);
	}
	return function;
}

SignalFunction realSignal()
{
	static auto function = reinterpret_cast<SignalFunction>(dlsym(RTLD_NEXT, "pthread_cond_signal"));
	if (!function) {
		std::fputs("FAIL: real condition signal function unavailable\n", stderr);
		std::_Exit(1);
	}
	return function;
}

struct Gate {
	std::promise<void> entered;
	std::promise<void> releasePromise;
	std::shared_future<void> release = releasePromise.get_future().share();
};

struct LockPause {
	pthread_mutex_t* mutex;
	Gate gate;
	std::atomic<bool> armed{true};
	explicit LockPause(pthread_mutex_t* mutex) : mutex(mutex) {}
};

struct WaitObservation {
	pthread_cond_t* condition;
	pthread_mutex_t* mutex;
	std::promise<void> entered;
	std::atomic<bool> observed{false};
	std::atomic<int> result{-1};
	std::atomic<unsigned> calls{0};
	WaitObservation(pthread_cond_t* condition, pthread_mutex_t* mutex) : condition(condition), mutex(mutex) {}
};

std::atomic<LockPause*> lockPause{nullptr};
std::atomic<WaitObservation*> waitObservation{nullptr};
std::atomic<pthread_cond_t*> signalObservation{nullptr};
std::atomic<unsigned> observedSignals{0};

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
		pthread_mutex_t* nativeMutex() { return eventLock.native_handle(); }
		pthread_cond_t* nativeCondition() { return eventSignal.native_handle(); }
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
	std::promise<void> executed;
	auto execution = executed.get_future();
	require(scheduler.addEvent(createSchedulerTask(50, [&]() { executed.set_value(); })) != 0,
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

void shutdownBeforeWorkerLock()
{
	FixtureScheduler scheduler;
	LockPause pause(scheduler.nativeMutex());
	auto entered = pause.gate.entered.get_future();
	std::unique_lock<std::mutex> held(scheduler.mutex());
	lockPause.store(&pause, std::memory_order_release);
	scheduler.start();
	ready(entered, "fixture must pause the worker's first exact scheduler lock");
	held.unlock();
	// The worker already observed RUNNING at its loop condition, but has not
	// acquired eventLock. Complete shutdown and its notification before relock.
	scheduler.shutdown();
	pause.gate.releasePromise.set_value();
	scheduler.join();
	lockPause.store(nullptr, std::memory_order_release);
}

void shutdownWhileDeadlineExpires()
{
	FixtureScheduler scheduler;
	WaitObservation observation(scheduler.nativeCondition(), scheduler.nativeMutex());
	auto waiting = observation.entered.get_future();
	auto gate = std::make_shared<Gate>();
	auto destroying = gate->entered.get_future();
	std::atomic<unsigned> unexpectedExecutions{0};
	auto* task = new BlockingDestructionTask(2000, [&]() { ++unexpectedExecutions; }, gate);
	const auto deadline = task->getCycle();
	waitObservation.store(&observation, std::memory_order_release);
	scheduler.start();
	require(scheduler.addEvent(task) != 0, "running scheduler must accept the deadline fixture");
	ready(waiting, "fixture must observe the exact scheduler timed wait");
	std::thread shutdown([&]() { scheduler.shutdown(); });
	ready(destroying, "shutdown must hold the queue lock while destroying the fixture");
	require(std::chrono::system_clock::now() < deadline, "shutdown fixture must own the queue lock before its deadline");
	// The real timed wait expires while shutdown holds the mutex, so its return
	// after relock must be ETIMEDOUT even though the queue was emptied.
	std::this_thread::sleep_until(deadline + std::chrono::milliseconds(20));
	gate->releasePromise.set_value();
	shutdown.join();
	scheduler.join();
	waitObservation.store(nullptr, std::memory_order_release);
	require(observation.result == ETIMEDOUT, "the real scheduler wait must return timeout after relock");
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
	const auto mark = [](const char* phase) {
		std::fprintf(stderr, "scheduler-duplicate-event-id: %s\n", phase);
	};
	FixtureScheduler scheduler;
	WaitObservation timedWait(scheduler.nativeCondition(), scheduler.nativeMutex());
	auto waitingForDeadline = timedWait.entered.get_future();
	waitObservation.store(&timedWait, std::memory_order_release);
	observedSignals.store(0, std::memory_order_relaxed);
	signalObservation.store(scheduler.nativeCondition(), std::memory_order_release);
	mark("before-start");
	scheduler.start();
	mark("after-start");
	std::shared_ptr<int> retained(new int(2));
	std::weak_ptr<int> existingClosure = retained;
	SchedulerTask* existing = createSchedulerTask(30000, [retained]() {});
	existing->setEventId(77);
	retained.reset();
	mark("before-add-original");
	require(scheduler.addEvent(existing) == 77, "scheduler must accept the original event id");
	mark("after-add-original");
	ready(waitingForDeadline, "fixture must observe the scheduled original event deadline");

	std::shared_ptr<int> duplicateRetained(new int(3));
	std::weak_ptr<int> duplicateClosure = duplicateRetained;
	SchedulerTask* duplicate = createSchedulerTask(30000, [duplicateRetained]() {});
	duplicate->setEventId(77);
	duplicateRetained.reset();
	mark("before-reject-duplicate");
	require(scheduler.addEvent(duplicate) == 0, "scheduler must reject a duplicate event id");
	mark("after-reject-duplicate");
	require(duplicateClosure.expired(), "rejected duplicate task must release its closure");
	mark("before-cancel-original");
	require(scheduler.stopEvent(77), "rejecting a duplicate must preserve the original active event id");
	mark("after-cancel-original");
	std::fprintf(stderr, "scheduler-duplicate-event-id: signals after cancel %u\n", observedSignals.load(std::memory_order_relaxed));
	mark("before-shutdown");
	scheduler.shutdown();
	mark("after-shutdown");
	std::fprintf(stderr, "scheduler-duplicate-event-id: signals after shutdown %u\n", observedSignals.load(std::memory_order_relaxed));
	scheduler.join();
	mark("after-join");
	waitObservation.store(nullptr, std::memory_order_release);
	signalObservation.store(nullptr, std::memory_order_release);
	require(existingClosure.expired(), "cancelling the original event must release its closure");
}
}

extern "C" int pthread_mutex_lock(pthread_mutex_t* mutex) noexcept
{
	if (auto* pause = lockPause.load(std::memory_order_acquire)) {
		if (mutex == pause->mutex && pause->armed.exchange(false)) {
			pause->gate.entered.set_value();
			pause->gate.release.wait();
		}
	}
	return realMutexLock()(mutex);
}

extern "C" int pthread_cond_signal(pthread_cond_t* condition)
{
	if (condition == signalObservation.load(std::memory_order_acquire)) {
		observedSignals.fetch_add(1, std::memory_order_relaxed);
	}
	return realSignal()(condition);
}

extern "C" int pthread_cond_timedwait(pthread_cond_t* condition, pthread_mutex_t* mutex, const timespec* deadline)
{
	WaitObservation* observation = waitObservation.load(std::memory_order_acquire);
	const bool matching = observation && condition == observation->condition && mutex == observation->mutex;
	const unsigned callNumber = matching ? observation->calls.fetch_add(1, std::memory_order_relaxed) + 1 : 0;
	const bool tracked = matching && !observation->observed.exchange(true);
	if (matching) std::fprintf(stderr, "scheduler-duplicate-event-id: timed wait %u enter\n", callNumber);
	if (tracked) observation->entered.set_value();
	const int result = realTimedWait()(condition, mutex, deadline);
	if (tracked) observation->result.store(result);
	if (matching) std::fprintf(stderr, "scheduler-duplicate-event-id: timed wait %u return %d\n", callNumber, result);
	return result;
}

int main(int argc, char** argv)
{
	try {
		const std::string scenario = argc == 1 ? "all" : argc == 2 ? argv[1] : "invalid";
		require(scenario == "all" || scenario == "normal" || scenario == "before-lock" || scenario == "after-relock" || scenario == "rejected-after-shutdown" || scenario == "duplicate-event-id",
		        "fixture scenario must be all, normal, before-lock, after-relock, rejected-after-shutdown or duplicate-event-id");
		// Resolve before worker threads start; unrelated pthread calls never
		// arm the fixture observations or change the native call semantics.
		(void)realMutexLock();
		(void)realTimedWait();
		(void)realSignal();
		g_dispatcher.start();
		if (scenario == "all" || scenario == "normal") {
			normalExecutionAndCancellation();
			queueMetricsTrackTombstonesAndCompaction();
		}
		if (scenario == "all" || scenario == "before-lock") shutdownBeforeWorkerLock();
		if (scenario == "all" || scenario == "after-relock") shutdownWhileDeadlineExpires();
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
