#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <deque>
#include <functional>
#include <iostream>
#include <list>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>

#include "scheduler.h"

namespace {
void require(bool condition, const char* message)
{
	if (!condition) {
		throw std::runtime_error(message);
	}
}

SchedulerTask* makeTask(uint32_t eventId, uint32_t delay, const std::shared_ptr<int>& retained, std::size_t trackedPayloadBytes = 0)
{
	SchedulerTask* task = createSchedulerTask(delay, [retained]() {}, trackedPayloadBytes);
	task->setEventId(eventId);
	return task;
}

void testCancelledTasksAreRemovedAtBoundedRatio()
{
	SchedulerTaskQueue tasks;
	std::unordered_set<uint32_t> activeEventIds;
	std::shared_ptr<int> retainedFirst(new int(1));
	std::weak_ptr<int> firstClosure = retainedFirst;
	std::shared_ptr<int> retainedSecond(new int(2));
	std::weak_ptr<int> secondClosure = retainedSecond;

	tasks.push(makeTask(1, 1000, retainedFirst, 10));
	tasks.push(makeTask(2, 2000, retainedSecond, 20));
	tasks.push(makeTask(3, 3000, std::shared_ptr<int>(new int(3)), 7));
	tasks.push(makeTask(4, 4000, std::shared_ptr<int>(new int(4)), 3));
	QueueMetricsSnapshot initialMetrics = tasks.getMetrics();
	require(initialMetrics.queuedCount == 4 && initialMetrics.trackedPayloadBytes == 40, "scheduler metrics must count physical tasks and declared payload bytes");
	require(initialMetrics.peakQueuedCount == 4 && initialMetrics.peakTrackedPayloadBytes == 40, "scheduler metrics must retain high-water values");
	activeEventIds.insert(1);
	activeEventIds.insert(2);
	activeEventIds.insert(3);
	activeEventIds.insert(4);
	retainedFirst.reset();
	retainedSecond.reset();

	activeEventIds.erase(1);
	require(!tasks.needsCompaction(activeEventIds.size()), "one stale task among three active tasks should not rebuild the heap");
	activeEventIds.erase(2);
	require(tasks.needsCompaction(activeEventIds.size()), "compaction should start when stale tasks equal active tasks");
	std::vector<SchedulerTask*> cancelledTasks = tasks.discardCancelled(activeEventIds);
	require(cancelledTasks.size() == 2, "compaction should return each cancelled task for destruction outside the queue lock");
	for (SchedulerTask* task : cancelledTasks) {
		delete task;
	}

	require(tasks.size() == 2, "compaction should retain only active tasks");
	QueueMetricsSnapshot compactedMetrics = tasks.getMetrics();
	require(compactedMetrics.queuedCount == 2 && compactedMetrics.trackedPayloadBytes == 10, "compaction must remove metrics for cancelled tombstones");
	require(firstClosure.expired() && secondClosure.expired(), "compaction should release cancelled task closures");
	require(tasks.top()->getEventId() == 3, "compaction should preserve the earliest active task");
	SchedulerTask* firstActive = tasks.top();
	tasks.pop();
	QueueMetricsSnapshot afterFirstPop = tasks.getMetrics();
	require(afterFirstPop.queuedCount == 1 && afterFirstPop.trackedPayloadBytes == 3, "scheduler pop must remove the task's tracked payload bytes");
	delete firstActive;
	require(tasks.top()->getEventId() == 4, "compaction should preserve the next active task");
	SchedulerTask* secondActive = tasks.top();
	tasks.pop();
	delete secondActive;
	QueueMetricsSnapshot emptyMetrics = tasks.getMetrics();
	require(emptyMetrics.queuedCount == 0 && emptyMetrics.trackedPayloadBytes == 0, "empty scheduler queue must report no pending work");
}

void testCompactionRemovesEveryCancelledTask()
{
	SchedulerTaskQueue tasks;
	std::unordered_set<uint32_t> activeEventIds;
	std::shared_ptr<int> retained(new int(5));
	std::weak_ptr<int> closure = retained;
	tasks.push(makeTask(5, 100000, retained, 11));
	activeEventIds.insert(5);
	retained.reset();
	activeEventIds.erase(5);

	require(tasks.needsCompaction(activeEventIds.size()), "a queue with only cancelled tasks should compact immediately");
	std::vector<SchedulerTask*> cancelledTasks = tasks.discardCancelled(activeEventIds);
	for (SchedulerTask* task : cancelledTasks) {
		delete task;
	}
	require(tasks.empty(), "compaction should empty a fully cancelled queue");
	QueueMetricsSnapshot metrics = tasks.getMetrics();
	require(metrics.queuedCount == 0 && metrics.trackedPayloadBytes == 0, "full cancellation compaction must clear queue metrics");
	require(!tasks.needsCompaction(0), "an empty queue should not trigger compaction");
	require(closure.expired(), "fully cancelled task closure should be released");
}

void testLargeCancellationBatchPreservesHeapOrder()
{
	SchedulerTaskQueue tasks;
	std::unordered_set<uint32_t> activeEventIds;
	const uint32_t eventCount = 10000;
	const uint32_t cancelledCount = eventCount / 2;
	for (uint32_t eventId = 1; eventId <= eventCount; ++eventId) {
		tasks.push(makeTask(eventId, 100000 + eventId * 10, std::shared_ptr<int>()));
		activeEventIds.insert(eventId);
	}
	for (uint32_t eventId = 1; eventId <= cancelledCount; ++eventId) {
		activeEventIds.erase(eventId);
	}

	require(tasks.needsCompaction(activeEventIds.size()), "large cancellation batches should cross the same compaction threshold");
	std::vector<SchedulerTask*> cancelledTasks = tasks.discardCancelled(activeEventIds);
	require(cancelledTasks.size() == cancelledCount, "large compaction should remove exactly the cancelled tasks");
	for (SchedulerTask* task : cancelledTasks) {
		delete task;
	}
	require(tasks.size() == eventCount - cancelledCount, "large compaction should preserve every active task");

	uint32_t previousEventId = cancelledCount;
	while (!tasks.empty()) {
		SchedulerTask* task = tasks.top();
		tasks.pop();
		require(task->getEventId() > previousEventId, "heap rebuild should preserve active tasks in due-time order");
		previousEventId = task->getEventId();
		delete task;
	}
}
}

int main()
{
	try {
		testCancelledTasksAreRemovedAtBoundedRatio();
		testCompactionRemovesEveryCancelledTask();
		testLargeCancellationBatchPreservesHeapOrder();
		std::cout << "Scheduler event queue tests passed." << std::endl;
		return 0;
	} catch (const std::exception& error) {
		std::cerr << error.what() << std::endl;
		return 1;
	}
}
