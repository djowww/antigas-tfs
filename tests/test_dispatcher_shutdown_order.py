import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class DispatcherShutdownOrderTests(unittest.TestCase):
    def test_worker_reports_then_rethrows_unhandled_exceptions(self):
        source = (ROOT / "src" / "tasks.cpp").read_text(encoding="utf-8")
        worker_entry = source.split("void Dispatcher::threadMain()", 1)[1].split("\n}", 1)[0]

        self.assertIn("threadMainLoop();", worker_entry)
        self.assertIn('WorkerExceptionDiagnostic::log("Dispatcher", exception.what())', worker_entry)
        self.assertIn('WorkerExceptionDiagnostic::log("Dispatcher", nullptr)', worker_entry)
        self.assertEqual(worker_entry.count("throw;"), 2)

    def test_final_cleanup_task_and_dispatcher_close_share_the_queue_lock(self):
        source = (ROOT / "src" / "tasks.cpp").read_text(encoding="utf-8")
        method = source.split("void Dispatcher::addTaskAndStop(Task* task)", 1)[1]
        method = method.split("void Dispatcher::shutdown()", 1)[0]

        self.assertIn("std::lock_guard<std::mutex> lockClass(taskLock)", method)
        self.assertLess(method.index("taskList.push_back(task);"), method.index("setState(THREAD_STATE_CLOSING);"))

        add_task = source.split("void Dispatcher::addTask(Task* task", 1)[1]
        add_task = add_task.split("void Dispatcher::addTaskAndStop", 1)[0]
        self.assertIn("if (getState() == THREAD_STATE_RUNNING)", add_task)
        self.assertIn("delete task;", add_task)

    def test_all_server_shutdown_paths_use_the_atomic_dispatcher_barrier(self):
        game = (ROOT / "src" / "game.cpp").read_text(encoding="utf-8")
        shutdown_case = game.split("case GAME_STATE_SHUTDOWN:", 1)[1].split("case GAME_STATE_CLOSED:", 1)[0]
        self.assertLess(shutdown_case.index("g_scheduler.stop();"), shutdown_case.index("g_databaseTasks.stop();"))
        self.assertLess(shutdown_case.index("g_databaseTasks.stop();"), shutdown_case.index("g_dispatcher.addTaskAndStop("))
        self.assertNotIn("g_dispatcher.stop();", shutdown_case)

        otserv = (ROOT / "src" / "otserv.cpp").read_text(encoding="utf-8")
        console_handler = otserv.split("SetConsoleCtrlHandler(", 1)[1].split("}, 1);", 1)[0]
        self.assertRegex(console_handler, re.compile(
            r"g_dispatcher\.addTaskAndStop\(createTask\(\s*std::bind\(&Game::shutdown, &g_game\)\s*\)\);"
        ))
        self.assertNotIn("g_dispatcher.stop();", console_handler)


if __name__ == "__main__":
    unittest.main()
