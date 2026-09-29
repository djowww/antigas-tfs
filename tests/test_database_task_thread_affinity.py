import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DatabaseTaskThreadAffinityTests(unittest.TestCase):
    def test_worker_initializes_and_releases_mysql_thread_state(self):
        source = (ROOT / "src" / "databasetasks.cpp").read_text(encoding="utf-8")
        start_body = source.split("void DatabaseTasks::start()", 1)[1].split("\n}", 1)[0]
        worker_body = source.split("void DatabaseTasks::threadMain()", 1)[1].split("\n}", 1)[0]

        self.assertIn("db.connect();", start_body)
        self.assertLess(worker_body.index("mysql_thread_init()"), worker_body.index("runTask(task)"))
        self.assertGreater(worker_body.index("mysql_thread_end();"), worker_body.rindex("\n\t}"))


if __name__ == "__main__":
    unittest.main()
