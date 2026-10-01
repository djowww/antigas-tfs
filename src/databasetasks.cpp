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

#include "databasetasks.h"
#include "tasks.h"
#include "workerexceptiondiagnostic.h"

#include <exception>

extern Dispatcher g_dispatcher;


void DatabaseTasks::start()
{
	db.connect();
	ThreadHolder::start();
}

void DatabaseTasks::threadMain()
{
	try {
		threadMainLoop();
	} catch (const std::exception& exception) {
		WorkerExceptionDiagnostic::log("DatabaseTasks", exception.what());
		throw;
	} catch (...) {
		WorkerExceptionDiagnostic::log("DatabaseTasks", nullptr);
		throw;
	}
}

void DatabaseTasks::threadMainLoop()
{
	// This worker uses the shared MySQL handle, so initialize its client TLS first.
	if (mysql_thread_init() != 0) {
		std::cerr << "[DatabaseTasks] Failed to initialize MySQL thread state." << std::endl;
		setState(THREAD_STATE_TERMINATED);
		return;
	}

	std::unique_lock<std::mutex> taskLockUnique(taskLock, std::defer_lock);
	while (getState() != THREAD_STATE_TERMINATED) {
		taskLockUnique.lock();
		if (tasks.empty()) {
			taskSignal.wait(taskLockUnique);
		}

		if (!tasks.empty()) {
			const std::size_t queryBytes = tasks.front().query.size();
			DatabaseTask task = std::move(tasks.front());
			tasks.pop_front();
			queueMetrics.taskDequeued(queryBytes);
			taskLockUnique.unlock();
			const uint64_t executionMicroseconds = runTask(task);
			taskLockUnique.lock();
			queueMetrics.taskExecuted(executionMicroseconds);
			taskLockUnique.unlock();
		} else {
			taskLockUnique.unlock();
		}
	}

	mysql_thread_end();
}

void DatabaseTasks::addTask(const std::string& query, const std::function<void(DBResult_ptr, bool)>& callback/* = nullptr*/, bool store/* = false*/)
{
	bool signal = false;
	taskLock.lock();
	if (getState() == THREAD_STATE_RUNNING) {
		signal = tasks.empty();
		tasks.emplace_back(query, callback, store);
		queueMetrics.taskQueued(query.size());
	}
	taskLock.unlock();

	if (signal) {
		taskSignal.notify_one();
	}
}

uint64_t DatabaseTasks::runTask(const DatabaseTask& task)
{
	bool success;
	DBResult_ptr result;
	const std::chrono::steady_clock::time_point startedAt = std::chrono::steady_clock::now();
	if (task.store) {
		result = db.storeQuery(task.query, &success);
	} else {
		result = nullptr;
		success = db.executeQuery(task.query);
	}
	const uint64_t executionMicroseconds = getElapsedMicroseconds(startedAt, std::chrono::steady_clock::now());

	if (task.callback) {
		g_dispatcher.addTask(createTask(std::bind(task.callback, result, success)));
	}
	return executionMicroseconds;
}

void DatabaseTasks::flush()
{
	while (!tasks.empty()) {
		const std::size_t queryBytes = tasks.front().query.size();
		const uint64_t executionMicroseconds = runTask(tasks.front());
		queueMetrics.taskExecuted(executionMicroseconds);
		queueMetrics.taskDequeued(queryBytes);
		tasks.pop_front();
	}
}

DatabaseQueueMetricsSnapshot DatabaseTasks::getQueueMetrics()
{
	std::lock_guard<std::mutex> lock(taskLock);
	DatabaseQueueMetricsSnapshot snapshot;
	snapshot.queue = queueMetrics.snapshot();
	if (!tasks.empty()) {
		snapshot.oldestQueuedAgeMs = getQueueAgeMilliseconds(tasks.front().enqueuedAt, std::chrono::steady_clock::now());
	}
	return snapshot;
}

void DatabaseTasks::shutdown()
{
	taskLock.lock();
	setState(THREAD_STATE_TERMINATED);
	taskLock.unlock();
	taskSignal.notify_one();
	join();

	// Finish any task already removed by the worker before running the remaining FIFO.
	taskLock.lock();
	flush();
	taskLock.unlock();
}
