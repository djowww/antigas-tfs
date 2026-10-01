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

#include "tasks.h"
#include "game.h"
#include "workerexceptiondiagnostic.h"

#include <exception>

extern Game g_game;

void Dispatcher::threadMain()
{
	try {
		threadMainLoop();
	} catch (const std::exception& exception) {
		WorkerExceptionDiagnostic::log("Dispatcher", exception.what());
		throw;
	} catch (...) {
		WorkerExceptionDiagnostic::log("Dispatcher", nullptr);
		throw;
	}
}

void Dispatcher::threadMainLoop()
{
	// NOTE: second argument defer_lock is to prevent from immediate locking
	std::unique_lock<std::mutex> taskLockUnique(taskLock, std::defer_lock);

	while (getState() != THREAD_STATE_TERMINATED) {
		// check if there are tasks waiting
		taskLockUnique.lock();

		if (taskList.empty()) {
			//if the list is empty wait for signal
			taskSignal.wait(taskLockUnique);
		}

		if (!taskList.empty()) {
			// take the first task
			Task* task = taskList.front();
			taskList.pop_front();
			queueMetrics.taskDequeued(task->getTrackedPayloadBytes());
			taskLockUnique.unlock();

			if (!task->hasExpired()) {
				++dispatcherCycle;
				// Execute it. A worker-level boundary reports failures and rethrows
				// so partially applied world operations still fail fast.
				(*task)();

				g_game.map.clearSpectatorCache();
			}
			delete task;
		} else {
			taskLockUnique.unlock();
		}
	}
}

void Dispatcher::addTask(Task* task, bool push_front /*= false*/)
{
	bool do_signal = false;

	taskLock.lock();

	if (getState() == THREAD_STATE_RUNNING) {
		do_signal = taskList.empty();

		if (push_front) {
			taskList.push_front(task);
		} else {
			taskList.push_back(task);
		}
		queueMetrics.taskQueued(task->getTrackedPayloadBytes());
	} else {
		delete task;
	}

	taskLock.unlock();

	// send a signal if the list was empty
	if (do_signal) {
		taskSignal.notify_one();
	}
}

void Dispatcher::addTaskAndStop(Task* task)
{
	bool do_signal = false;
	{
		std::lock_guard<std::mutex> lockClass(taskLock);
		if (getState() == THREAD_STATE_RUNNING) {
			do_signal = taskList.empty();
			taskList.push_back(task);
			queueMetrics.taskQueued(task->getTrackedPayloadBytes());
			setState(THREAD_STATE_CLOSING);
		} else {
			delete task;
		}
	}

	if (do_signal) {
		taskSignal.notify_one();
	}
}

void Dispatcher::shutdown()
{
	Task* task = createTask([this]() {
		setState(THREAD_STATE_TERMINATED);
		taskSignal.notify_one();
	});

	std::lock_guard<std::mutex> lockClass(taskLock);
	taskList.push_back(task);
	queueMetrics.taskQueued(task->getTrackedPayloadBytes());

	taskSignal.notify_one();
}

QueueMetricsSnapshot Dispatcher::getQueueMetrics()
{
	std::lock_guard<std::mutex> lock(taskLock);
	return queueMetrics.snapshot();
}
