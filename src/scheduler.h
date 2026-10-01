/**
 * Tibia GIMUD Server - a free and open-source MMORPG server emulator
 * Copyright (C) 2017  Alejandro Mujica <alejandrodemujica@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#ifndef FS_SCHEDULER_H_2905B3D5EAB34B4BA8830167262D2DC1
#define FS_SCHEDULER_H_2905B3D5EAB34B4BA8830167262D2DC1

#include "tasks.h"
#include <algorithm>
#include <cstddef>
#include <new>
#include <stdexcept>
#include <unordered_set>
#include <queue>
#include <vector>

#include "thread_holder_base.h"

static constexpr int32_t SCHEDULER_MINTICKS = 50;

class SchedulerTask : public Task
{
	public:
		void setEventId(uint32_t id) {
			eventId = id;
		}
		uint32_t getEventId() const {
			return eventId;
		}

		std::chrono::system_clock::time_point getCycle() const {
			return expiration;
		}

	protected:
		SchedulerTask(uint32_t delay, const std::function<void (void)>& f, std::size_t trackedPayloadBytes = 0) :
			Task(delay, f, trackedPayloadBytes) {}

		uint32_t eventId = 0;

		friend SchedulerTask* createSchedulerTask(uint32_t, const std::function<void (void)>&, std::size_t);
};

inline SchedulerTask* createSchedulerTask(uint32_t delay, const std::function<void (void)>& f, std::size_t trackedPayloadBytes = 0)
{
	return new SchedulerTask(delay, f, trackedPayloadBytes);
}

struct TaskComparator {
	bool operator()(const SchedulerTask* lhs, const SchedulerTask* rhs) const {
		return lhs->getCycle() > rhs->getCycle();
	}
};

class SchedulerTaskQueue : public std::priority_queue<SchedulerTask*, std::deque<SchedulerTask*>, TaskComparator>
{
		using Base = std::priority_queue<SchedulerTask*, std::deque<SchedulerTask*>, TaskComparator>;
	public:
		void push(SchedulerTask* task) {
			Base::push(task);
			queueMetrics.taskQueued(task->getTrackedPayloadBytes());
		}

		void pop() {
			SchedulerTask* task = Base::top();
			Base::pop();
			queueMetrics.taskDequeued(task->getTrackedPayloadBytes());
		}

		QueueMetricsSnapshot getMetrics() const {
			return queueMetrics.snapshot();
		}

		// Limit retained cancelled nodes to roughly the number of live queued tasks.
		bool needsCompaction(std::size_t activeTaskCount) const {
			return this->size() > activeTaskCount && this->size() - activeTaskCount >= activeTaskCount;
		}

		// Return removed tasks so callers can run their destructors after unlocking.
		std::vector<SchedulerTask*> discardCancelled(const std::unordered_set<uint32_t>& activeEventIds) {
			std::vector<SchedulerTask*> cancelledTasks;
			if (this->size() > activeEventIds.size()) {
				try {
					cancelledTasks.reserve(this->size() - activeEventIds.size());
				} catch (const std::bad_alloc&) {
					return cancelledTasks;
				} catch (const std::length_error&) {
					return cancelledTasks;
				}
			}
			auto newEnd = std::remove_if(this->c.begin(), this->c.end(), [&activeEventIds, &cancelledTasks](SchedulerTask* task) {
				if (activeEventIds.find(task->getEventId()) != activeEventIds.end()) {
					return false;
				}

				cancelledTasks.push_back(task);
				return true;
			});
			this->c.erase(newEnd, this->c.end());
			std::make_heap(this->c.begin(), this->c.end(), this->comp);
			for (SchedulerTask* task : cancelledTasks) {
				queueMetrics.taskDequeued(task->getTrackedPayloadBytes());
			}
			return cancelledTasks;
		}

	private:
		QueueMetrics queueMetrics;
};

struct SchedulerQueueMetricsSnapshot {
	QueueMetricsSnapshot retained;
	uint64_t activeEventCount = 0;
	uint64_t cancelledRetainedCount = 0;
};

class Scheduler : public ThreadHolder<Scheduler>
{
	public:
		uint32_t addEvent(SchedulerTask* task);
		bool stopEvent(uint32_t eventId);
		SchedulerQueueMetricsSnapshot getQueueMetrics();

		void shutdown();

		void threadMain();
	protected:
		std::thread thread;
		std::mutex eventLock;
		std::condition_variable eventSignal;

		uint32_t lastEventId {0};
		SchedulerTaskQueue eventList;
		std::unordered_set<uint32_t> eventIds;
};

extern Scheduler g_scheduler;

#endif
