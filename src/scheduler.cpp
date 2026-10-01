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

void Scheduler::threadMain()
{
	std::unique_lock<std::mutex> eventLockUnique(eventLock, std::defer_lock);
	while (getState() != THREAD_STATE_TERMINATED) {
		std::cv_status ret = std::cv_status::no_timeout;

		eventLockUnique.lock();
		// Shutdown may have completed after the loop condition was read, before
		// this lock was acquired. Do not wait after its notification is gone.
		if (getState() == THREAD_STATE_TERMINATED) {
			eventLockUnique.unlock();
			break;
		}
		if (eventList.empty()) {
			eventSignal.wait(eventLockUnique);
		} else {
			ret = eventSignal.wait_until(eventLockUnique, eventList.top()->getCycle());
		}

		// the mutex is locked again now...
		// A timeout does not guarantee the queue still contains the old head:
		// cancellation/shutdown can remove it while wait_until releases the lock.
		if (getState() == THREAD_STATE_TERMINATED || eventList.empty()) {
			eventLockUnique.unlock();
			continue;
		}
		if (ret == std::cv_status::timeout) {
			// ok we had a timeout, so there has to be an event we have to execute...
			SchedulerTask* task = eventList.top();
			eventList.pop();

			// check if the event was stopped
			auto it = eventIds.find(task->getEventId());
			if (it == eventIds.end()) {
				eventLockUnique.unlock();
				delete task;
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
		} else {
			eventLockUnique.unlock();
		}
	}
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
	setState(THREAD_STATE_TERMINATED);
	eventLock.lock();

	//this list should already be empty
	while (!eventList.empty()) {
		SchedulerTask* task = eventList.top();
		eventList.pop();
		delete task;
	}

	eventIds.clear();
	eventLock.unlock();
	eventSignal.notify_one();
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

