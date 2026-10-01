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

#include "otpch.h"

#include "scheduler.h"
#include <cstdio>
#include <cstdlib>

void Scheduler::threadMain()
{
	const bool debugScheduler = std::getenv("TFS_SCHEDULER_DEBUG") != nullptr;
	const auto traceScheduler = [this, debugScheduler](const char* phase) {
		if (debugScheduler) {
			std::fprintf(stderr, "scheduler-debug %s state=%d queue=%zu ids=%zu\n", phase,
			             static_cast<int>(getState()), eventList.size(), eventIds.size());
		}
	};
	std::unique_lock<std::mutex> eventLockUnique(eventLock);
	traceScheduler("worker-start");
	while (getState() != THREAD_STATE_TERMINATED) {
		if (eventList.empty()) {
			traceScheduler("empty-wait-before");
			eventSignal.wait(eventLockUnique, [this]() {
				return getState() == THREAD_STATE_TERMINATED || !eventList.empty();
			});
			traceScheduler("empty-wait-after");
			if (getState() == THREAD_STATE_TERMINATED) {
				break;
			}
			if (eventList.empty()) {
				continue;
			}
		} else {
			const std::chrono::system_clock::time_point nextCycle = eventList.top()->getCycle();
			traceScheduler("timed-wait-before");
			const bool queueChanged = eventSignal.wait_until(eventLockUnique, nextCycle, [this, nextCycle]() {
				return getState() == THREAD_STATE_TERMINATED || eventList.empty() ||
				       eventList.top()->getCycle() != nextCycle;
			});
			traceScheduler(queueChanged ? "timed-wait-predicate" : "timed-wait-timeout");
			if (getState() == THREAD_STATE_TERMINATED) {
				break;
			}
			if (queueChanged || eventList.empty()) {
				continue;
			}
		}

		SchedulerTask* task = eventList.top();
		eventList.pop();

		// A timed wait can expire after stopEvent has removed this id.
		auto it = eventIds.find(task->getEventId());
		if (it == eventIds.end()) {
			eventLockUnique.unlock();
			delete task;
			eventLockUnique.lock();
			continue;
		}
		eventIds.erase(it);
		std::vector<SchedulerTask*> cancelledTasks;
		if (eventList.needsCompaction(eventIds.size())) {
			cancelledTasks = eventList.discardCancelled(eventIds);
		}
		eventLockUnique.unlock();
		for (SchedulerTask* cancelledTask : cancelledTasks) {
			delete cancelledTask;
		}

		task->setDontExpire();
		g_dispatcher.addTask(task, true);
		eventLockUnique.lock();
	}
	traceScheduler("worker-exit");
}

uint32_t Scheduler::addEvent(SchedulerTask* task)
{
	bool do_signal = false;
	uint32_t eventId = 0;
	{
		std::unique_lock<std::mutex> lock(eventLock);
		if (getState() != THREAD_STATE_RUNNING) {
			lock.unlock();
			delete task;
			return 0;
		}

		if (task->getEventId() == 0) {
			if (++lastEventId == 0) {
				lastEventId = 1;
			}
			task->setEventId(lastEventId);
		}

		eventId = task->getEventId();
		bool insertedEventId = false;
		try {
			insertedEventId = eventIds.insert(eventId).second;
			if (!insertedEventId) {
				lock.unlock();
				delete task;
				return 0;
			}
			eventList.push(task);
		} catch (...) {
			if (insertedEventId) {
				eventIds.erase(eventId);
			}
			lock.unlock();
			delete task;
			return 0;
		}

		do_signal = (task == eventList.top());
	}

	if (do_signal) {
		eventSignal.notify_one();
	}

	return eventId;
}

bool Scheduler::stopEvent(uint32_t eventid)
{
	if (eventid == 0) {
		return false;
	}

	std::unique_lock<std::mutex> lockClass(eventLock);

	// search the event id..
	auto it = eventIds.find(eventid);
	if (it == eventIds.end()) {
		return false;
	}

	eventIds.erase(it);
	std::vector<SchedulerTask*> cancelledTasks;
	if (eventList.needsCompaction(eventIds.size())) {
		cancelledTasks = eventList.discardCancelled(eventIds);
	}
	lockClass.unlock();
	if (!cancelledTasks.empty()) {
		eventSignal.notify_one();
	}
	for (SchedulerTask* task : cancelledTasks) {
		delete task;
	}
	return true;
}

void Scheduler::shutdown()
{
	const bool debugScheduler = std::getenv("TFS_SCHEDULER_DEBUG") != nullptr;
	eventLock.lock();
	setState(THREAD_STATE_TERMINATED);
	if (debugScheduler) {
		std::fprintf(stderr, "scheduler-debug shutdown-locked state=%d queue=%zu ids=%zu\n",
		             static_cast<int>(getState()), eventList.size(), eventIds.size());
	}

	//this list should already be empty
	while (!eventList.empty()) {
		SchedulerTask* task = eventList.top();
		eventList.pop();
		delete task;
	}

	eventIds.clear();
	eventLock.unlock();
	if (debugScheduler) std::fprintf(stderr, "scheduler-debug shutdown-notify\n");
	eventSignal.notify_all();
}

SchedulerQueueMetricsSnapshot Scheduler::getQueueMetrics()
{
	std::lock_guard<std::mutex> lock(eventLock);
	SchedulerQueueMetricsSnapshot snapshot;
	snapshot.retained = eventList.getMetrics();
	snapshot.activeEventCount = eventIds.size();
	if (snapshot.retained.queuedCount > snapshot.activeEventCount) {
		snapshot.cancelledRetainedCount = snapshot.retained.queuedCount - snapshot.activeEventCount;
	}
	return snapshot;
}

