from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


class QueueMetricsWiringTests(unittest.TestCase):
    def test_dispatcher_accounts_only_after_enqueue_and_on_every_dequeue(self):
        source = (SRC / "tasks.cpp").read_text(encoding="utf-8-sig")
        self.assertLess(source.index("taskList.pop_front();"), source.index("queueMetrics.taskDequeued("))
        self.assertLess(source.index("taskList.push_back(task);"), source.index("queueMetrics.taskQueued("))
        self.assertIn("taskList.push_front(task);", source)
        self.assertIn("queueMetrics.taskQueued(task->getTrackedPayloadBytes());", source)
        self.assertIn("QueueMetricsSnapshot Dispatcher::getQueueMetrics()", source)

    def test_scheduler_counts_retained_tombstones_until_actual_removal(self):
        header = (SRC / "scheduler.h").read_text(encoding="utf-8-sig")
        source = (SRC / "scheduler.cpp").read_text(encoding="utf-8-sig")
        self.assertLess(header.index("Base::push(task);"), header.index("queueMetrics.taskQueued("))
        self.assertLess(header.index("Base::pop();"), header.index("queueMetrics.taskDequeued("))
        self.assertIn("queueMetrics.taskDequeued(task->getTrackedPayloadBytes());", header)
        self.assertIn("snapshot.activeEventCount = eventIds.size();", source)
        self.assertIn("snapshot.cancelledRetainedCount = snapshot.retained.queuedCount - snapshot.activeEventCount;", source)
        shutdown = source[source.index("void Scheduler::shutdown()") : source.index("SchedulerQueueMetricsSnapshot Scheduler::getQueueMetrics()")]
        self.assertLess(shutdown.index("eventList.pop();"), shutdown.index("delete task;"))

    def test_database_queue_tracks_query_bytes_on_enqueue_worker_and_flush(self):
        source = (SRC / "databasetasks.cpp").read_text(encoding="utf-8-sig")
        header = (SRC / "databasetasks.h").read_text(encoding="utf-8-sig")
        self.assertIn("tasks.emplace_back(query, callback, store);\n\t\tqueueMetrics.taskQueued(query.size());", source)
        self.assertIn("const std::size_t queryBytes = tasks.front().query.size();", source)
        self.assertIn("queueMetrics.taskDequeued(queryBytes);", source)
        self.assertIn("getQueueAgeMilliseconds(tasks.front().enqueuedAt", source)
        self.assertIn("queueMetrics.taskExecuted(executionMicroseconds);", source)
        self.assertIn("getElapsedMicroseconds(startedAt", source)
        run_task = source[source.index("uint64_t DatabaseTasks::runTask(") : source.index("void DatabaseTasks::flush()")]
        self.assertLess(run_task.index("getElapsedMicroseconds(startedAt"), run_task.index("if (task.callback)"))
        self.assertIn("enqueuedAt(std::chrono::steady_clock::now())", header)
        self.assertIn("struct DatabaseQueueMetricsSnapshot", header)
        self.assertIn("DatabaseQueueMetricsSnapshot DatabaseTasks::getQueueMetrics()", source)
        worker = source[source.index("void DatabaseTasks::threadMainLoop()") : source.index("void DatabaseTasks::addTask(")]
        flush = source[source.index("void DatabaseTasks::flush()") : source.index("DatabaseQueueMetricsSnapshot DatabaseTasks::getQueueMetrics()")]
        self.assertLess(worker.index("runTask(task);"), worker.index("queueMetrics.taskExecuted(executionMicroseconds);"))
        self.assertIn("queueMetrics.taskExecuted(executionMicroseconds);", flush)

    def test_remote_extended_opcode_payload_is_explicitly_tracked(self):
        protocol = (SRC / "protocolgame.cpp").read_text(encoding="utf-8-sig")
        helper = (SRC / "protocolgame.h").read_text(encoding="utf-8-sig")
        self.assertIn("addGameTaskWithTrackedPayload(msg, buffer.size(),", protocol)
        self.assertIn("createTask(std::bind(function, &g_game, std::forward<Args>(args)...), trackedPayloadBytes)", helper)
        self.assertIn("const std::size_t trackedPathBytes = path.size() * sizeof(Direction);", protocol)
        self.assertIn("}, trackedPathBytes));", protocol)

    def test_periodic_log_uses_aggregate_values_and_has_no_queue_cap(self):
        source = (SRC / "otserv.cpp").read_text(encoding="utf-8-sig")
        self.assertIn("[QueueMetrics] dispatcher queued=", source)
        self.assertIn("queued_sql_bytes=", source)
        self.assertIn("total_enqueued=", source)
        self.assertIn("total_dequeued=", source)
        self.assertIn("oldest_queued_age_ms=", source)
        self.assertIn("completed_tasks=", source)
        self.assertIn("total_execution_us=", source)
        self.assertIn("max_execution_us=", source)
        self.assertIn("scheduleQueueMetricsLog();", source)
        self.assertIn("g_scheduler.addEvent(createSchedulerTask(60000", source)
        self.assertIn("counter_anomaly=", source)
        self.assertNotIn("query.str()", source)
        header = (SRC / "queuemetrics.h").read_text(encoding="utf-8-sig")
        self.assertIn("trackedPayloadBytes", header)
        self.assertIn("they are not total memory use", header)

    def test_native_metrics_regression_is_wired_to_cmake_and_ci(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8-sig")
        workflow = (ROOT / ".github" / "workflows" / "security-build.yml").read_text(encoding="utf-8-sig")
        self.assertIn("TFS_BUILD_QUEUE_METRICS_TESTS", cmake)
        self.assertIn("queue-metrics-tests", cmake)
        self.assertIn("TFS_BUILD_QUEUE_METRICS_TESTS=ON", workflow)
        self.assertIn("test_queue_metrics", workflow)


if __name__ == "__main__":
    unittest.main()
