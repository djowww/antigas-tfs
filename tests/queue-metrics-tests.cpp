#include <cstddef>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>

#include "queuemetrics.h"

namespace {
void require(bool condition, const char* message)
{
	if (!condition) {
		throw std::runtime_error(message);
	}
}

void testQueueAccountingAndHighWater()
{
	QueueMetrics metrics;
	metrics.taskQueued(5);
	metrics.taskQueued(7);
	QueueMetricsSnapshot snapshot = metrics.snapshot();
	require(snapshot.queuedCount == 2 && snapshot.trackedPayloadBytes == 12, "enqueue must update current task and payload counts");
	require(snapshot.peakQueuedCount == 2 && snapshot.peakTrackedPayloadBytes == 12, "enqueue must update queue high-water values");
	require(snapshot.totalQueuedCount == 2 && snapshot.totalDequeuedCount == 0, "enqueue totals must expose queue input volume");

	metrics.taskDequeued(7);
	snapshot = metrics.snapshot();
	require(snapshot.queuedCount == 1 && snapshot.trackedPayloadBytes == 5, "dequeue must subtract only the removed task's payload");
	require(snapshot.peakQueuedCount == 2 && snapshot.peakTrackedPayloadBytes == 12, "dequeue must not reduce high-water values");
	require(snapshot.totalQueuedCount == 2 && snapshot.totalDequeuedCount == 1, "dequeue totals must expose queue service volume");

	metrics.taskDequeued(5);
	snapshot = metrics.snapshot();
	require(snapshot.queuedCount == 0 && snapshot.trackedPayloadBytes == 0, "draining the queue must clear current metrics");
	require(snapshot.totalQueuedCount == 2 && snapshot.totalDequeuedCount == 2, "draining must retain cumulative queue totals");
}

void testQueueAgeUsesMonotonicElapsedTime()
{
	const std::chrono::steady_clock::time_point enqueuedAt;
	const std::chrono::steady_clock::time_point later = enqueuedAt + std::chrono::seconds(2) + std::chrono::milliseconds(345);
	require(getQueueAgeMilliseconds(enqueuedAt, later) == 2345, "queue age must report monotonic elapsed milliseconds");
	require(getQueueAgeMilliseconds(later, enqueuedAt) == 0, "queue age must fail closed if the sample precedes enqueue time");
	require(getElapsedMicroseconds(enqueuedAt, later) == 2345000, "execution duration must retain microsecond precision");
	require(getElapsedMicroseconds(later, enqueuedAt) == 0, "execution duration must fail closed for a reversed sample");
}

void testTaskExecutionMetrics()
{
	QueueMetrics metrics;
	metrics.taskExecuted(125);
	metrics.taskExecuted(275);
	QueueMetricsSnapshot snapshot = metrics.snapshot();
	require(snapshot.completedTaskCount == 2, "completed task count must include executions");
	require(snapshot.totalTaskExecutionMicroseconds == 400, "execution metric must accumulate durations");
	require(snapshot.maxTaskExecutionMicroseconds == 275, "execution metric must retain its maximum");
}

void testExecutionDurationCounterSaturates()
{
	QueueMetrics metrics;
	metrics.taskExecuted(std::numeric_limits<uint64_t>::max());
	metrics.taskExecuted(1);
	QueueMetricsSnapshot snapshot = metrics.snapshot();
	require(snapshot.counterAnomaly, "execution duration overflow must be visible");
	require(snapshot.totalTaskExecutionMicroseconds == std::numeric_limits<uint64_t>::max(), "execution duration overflow must saturate instead of wrapping");
}

void testInvalidDequeueFailsMetricsClosed()
{
	QueueMetrics metrics;
	metrics.taskDequeued(0);
	QueueMetricsSnapshot snapshot = metrics.snapshot();
	require(snapshot.counterAnomaly, "underflow must be visible instead of wrapping metric counters");
	require(snapshot.queuedCount == 0 && snapshot.trackedPayloadBytes == 0, "underflow must not expose wrapped values");
}

void testPayloadCounterSaturatesInsteadOfWrapping()
{
	QueueMetrics metrics;
	metrics.taskQueued(std::numeric_limits<uint64_t>::max());
	metrics.taskQueued(1);
	QueueMetricsSnapshot snapshot = metrics.snapshot();
	require(snapshot.counterAnomaly, "payload overflow must be visible");
	require(snapshot.trackedPayloadBytes == std::numeric_limits<uint64_t>::max(), "payload overflow must saturate instead of wrapping");
}
}

int main()
{
	try {
		testQueueAccountingAndHighWater();
		testQueueAgeUsesMonotonicElapsedTime();
		testTaskExecutionMetrics();
		testExecutionDurationCounterSaturates();
		testInvalidDequeueFailsMetricsClosed();
		testPayloadCounterSaturatesInsteadOfWrapping();
		std::cout << "Queue metrics tests passed." << std::endl;
		return 0;
	} catch (const std::exception& error) {
		std::cerr << error.what() << std::endl;
		return 1;
	}
}
