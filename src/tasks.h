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

#ifndef FS_TASKS_H_A66AC384766041E59DCA059DAB6E1976
#define FS_TASKS_H_A66AC384766041E59DCA059DAB6E1976

#include <condition_variable>
#include "queuemetrics.h"
#include "thread_holder_base.h"
#include "enums.h"

const int DISPATCHER_TASK_EXPIRATION = 2000;
const auto SYSTEM_TIME_ZERO = std::chrono::system_clock::time_point(std::chrono::milliseconds(0));

class Task
{
	public:
		// DO NOT allocate this class on the stack
		explicit Task(std::function<void (void)> f, std::size_t trackedPayloadBytes = 0) :
			func(std::move(f)), trackedPayloadBytes(trackedPayloadBytes) {}
		Task(uint32_t ms, std::function<void (void)> f, std::size_t trackedPayloadBytes = 0) :
			expiration(std::chrono::system_clock::now() + std::chrono::milliseconds(ms)),
			func(std::move(f)), trackedPayloadBytes(trackedPayloadBytes) {}

		virtual ~Task() = default;
		void operator()() {
			func();
		}

		void setDontExpire() {
			expiration = SYSTEM_TIME_ZERO;
		}

		bool hasExpired() const {
			if (expiration == SYSTEM_TIME_ZERO) {
				return false;
			}
			return expiration < std::chrono::system_clock::now();
		}
		std::size_t getTrackedPayloadBytes() const {
			return trackedPayloadBytes;
		}

	protected:
		// Expiration has another meaning for scheduler tasks,
		// then it is the time the task should be added to the
		// dispatcher
		std::chrono::system_clock::time_point expiration = SYSTEM_TIME_ZERO;
		std::function<void (void)> func;
		std::size_t trackedPayloadBytes = 0;
};

inline Task* createTask(const std::function<void (void)>& f, std::size_t trackedPayloadBytes = 0)
{
	return new Task(f, trackedPayloadBytes);
}

inline Task* createTask(uint32_t expiration, const std::function<void (void)>& f, std::size_t trackedPayloadBytes = 0)
{
	return new Task(expiration, f, trackedPayloadBytes);
}

class Dispatcher : public ThreadHolder<Dispatcher> {
	public:
		void addTask(Task* task, bool push_front = false);
		void addTaskAndStop(Task* task);

		void shutdown();
		QueueMetricsSnapshot getQueueMetrics();

		uint64_t getDispatcherCycle() const {
			return dispatcherCycle;
		}

		void threadMain();

	private:
		void threadMainLoop();

	protected:
		std::thread thread;
		std::mutex taskLock;
		std::condition_variable taskSignal;

		std::list<Task*> taskList;
		QueueMetrics queueMetrics;
		uint64_t dispatcherCycle = 0;
};

extern Dispatcher g_dispatcher;

#endif
