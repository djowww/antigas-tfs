import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DatabaseTaskThreadAffinityTests(unittest.TestCase):
    def test_worker_initializes_and_releases_mysql_thread_state(self):
        source = (ROOT / "src" / "databasetasks.cpp").read_text(encoding="utf-8")
        start_body = source.split("void DatabaseTasks::start()", 1)[1].split("\n}", 1)[0]
        worker_entry = source.split("void DatabaseTasks::threadMain()", 1)[1].split("\n}", 1)[0]
        worker_body = source.split("void DatabaseTasks::threadMainLoop()", 1)[1].split("\n}", 1)[0]

        self.assertIn("db.connect();", start_body)
        self.assertIn("threadMainLoop();", worker_entry)
        self.assertIn('WorkerExceptionDiagnostic::log("DatabaseTasks", exception.what())', worker_entry)
        self.assertIn('WorkerExceptionDiagnostic::log("DatabaseTasks", nullptr)', worker_entry)
        self.assertEqual(worker_entry.count("throw;"), 2)
        self.assertLess(worker_body.index("mysql_thread_init()"), worker_body.index("runTask(task)"))
        self.assertGreater(worker_body.index("mysql_thread_end();"), worker_body.rindex("\n\t}"))

    def test_shutdown_joins_worker_before_flushing_remaining_fifo(self):
        source = (ROOT / "src" / "databasetasks.cpp").read_text(encoding="utf-8")
        shutdown = source.split("void DatabaseTasks::shutdown()", 1)[1].split("\n}", 1)[0]

        terminate = shutdown.index("setState(THREAD_STATE_TERMINATED);")
        unlock_before_join = shutdown.index("taskLock.unlock();", terminate)
        notify = shutdown.index("taskSignal.notify_one();", unlock_before_join)
        join = shutdown.index("join();", notify)
        lock_before_flush = shutdown.index("taskLock.lock();", join)
        flush = shutdown.index("flush();", lock_before_flush)
        unlock_after_flush = shutdown.index("taskLock.unlock();", flush)

        self.assertLess(terminate, unlock_before_join)
        self.assertLess(unlock_before_join, notify)
        self.assertLess(notify, join)
        self.assertLess(join, lock_before_flush)
        self.assertLess(lock_before_flush, flush)
        self.assertLess(flush, unlock_after_flush)


if __name__ == "__main__":
    unittest.main()
