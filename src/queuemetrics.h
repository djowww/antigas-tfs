#ifndef FS_QUEUE_METRICS_H
#define FS_QUEUE_METRICS_H

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <limits>

inline uint64_t getQueueAgeMilliseconds(const std::chrono::steady_clock::time_point& enqueuedAt, const std::chrono::steady_clock::time_point& now) noexcept
{
	if (now <= enqueuedAt) {
		return 0;
	}

	const std::chrono::milliseconds age = std::chrono::duration_cast<std::chrono::milliseconds>(now - enqueuedAt);
	return age.count() > 0 ? static_cast<uint64_t>(age.count()) : 0;
}

inline uint64_t getElapsedMicroseconds(const std::chrono::steady_clock::time_point& startedAt, const std::chrono::steady_clock::time_point& finishedAt) noexcept
{
	if (finishedAt <= startedAt) {
		return 0;
	}

	const std::chrono::microseconds elapsed = std::chrono::duration_cast<std::chrono::microseconds>(finishedAt - startedAt);
	return elapsed.count() > 0 ? static_cast<uint64_t>(elapsed.count()) : 0;
}

struct QueueMetricsSnapshot {
	uint64_t queuedCount = 0;
	uint64_t trackedPayloadBytes = 0;
	uint64_t peakQueuedCount = 0;
	uint64_t peakTrackedPayloadBytes = 0;
	uint64_t totalQueuedCount = 0;
	uint64_t totalDequeuedCount = 0;
	uint64_t completedTaskCount = 0;
	uint64_t totalTaskExecutionMicroseconds = 0;
	uint64_t maxTaskExecutionMicroseconds = 0;
	bool counterAnomaly = false;
};

// Callers serialize updates and snapshots with the mutex that protects their queue.
// Payload bytes are explicitly declared by producers; they are not total memory use.
class QueueMetrics {
	public:
		void taskQueued(uint64_t payloadBytes) noexcept
		{
			increment(queuedCount);
			increment(totalQueuedCount);

			if (payloadBytes > std::numeric_limits<uint64_t>::max() - trackedPayloadBytes) {
				trackedPayloadBytes = std::numeric_limits<uint64_t>::max();
				counterAnomaly = true;
			} else {
				trackedPayloadBytes += payloadBytes;
			}

			if (queuedCount > peakQueuedCount) {
				peakQueuedCount = queuedCount;
			}
			if (trackedPayloadBytes > peakTrackedPayloadBytes) {
				peakTrackedPayloadBytes = trackedPayloadBytes;
			}
		}

		void taskDequeued(uint64_t payloadBytes) noexcept
		{
			if (queuedCount == 0 || payloadBytes > trackedPayloadBytes) {
				counterAnomaly = true;
				queuedCount = 0;
				trackedPayloadBytes = 0;
				return;
			}

			--queuedCount;
			trackedPayloadBytes -= payloadBytes;
			increment(totalDequeuedCount);
		}

		void taskExecuted(uint64_t executionMicroseconds) noexcept
		{
			increment(completedTaskCount);
			if (executionMicroseconds > std::numeric_limits<uint64_t>::max() - totalTaskExecutionMicroseconds) {
				totalTaskExecutionMicroseconds = std::numeric_limits<uint64_t>::max();
				counterAnomaly = true;
			} else {
				totalTaskExecutionMicroseconds += executionMicroseconds;
			}

			if (executionMicroseconds > maxTaskExecutionMicroseconds) {
				maxTaskExecutionMicroseconds = executionMicroseconds;
			}
		}

		QueueMetricsSnapshot snapshot() const noexcept
		{
			QueueMetricsSnapshot result;
			result.queuedCount = queuedCount;
			result.trackedPayloadBytes = trackedPayloadBytes;
			result.peakQueuedCount = peakQueuedCount;
			result.peakTrackedPayloadBytes = peakTrackedPayloadBytes;
			result.totalQueuedCount = totalQueuedCount;
			result.totalDequeuedCount = totalDequeuedCount;
			result.completedTaskCount = completedTaskCount;
			result.totalTaskExecutionMicroseconds = totalTaskExecutionMicroseconds;
			result.maxTaskExecutionMicroseconds = maxTaskExecutionMicroseconds;
			result.counterAnomaly = counterAnomaly;
			return result;
		}

	private:
		void increment(uint64_t& counter) noexcept
		{
			if (counter == std::numeric_limits<uint64_t>::max()) {
				counterAnomaly = true;
			} else {
				++counter;
			}
		}

		uint64_t queuedCount = 0;
		uint64_t trackedPayloadBytes = 0;
		uint64_t peakQueuedCount = 0;
		uint64_t peakTrackedPayloadBytes = 0;
		uint64_t totalQueuedCount = 0;
		uint64_t totalDequeuedCount = 0;
		uint64_t completedTaskCount = 0;
		uint64_t totalTaskExecutionMicroseconds = 0;
		uint64_t maxTaskExecutionMicroseconds = 0;
		bool counterAnomaly = false;
};

#endif
