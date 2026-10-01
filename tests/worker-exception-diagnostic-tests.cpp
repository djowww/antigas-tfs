#include "workerexceptiondiagnostic.h"

#include <cstdio>
#include <string>

int main()
{
	char output[WorkerExceptionDiagnostic::MAX_DIAGNOSTIC_BYTES];
	const std::string message = std::string("first\nsecond\r\x1B") + std::string(300, 'x');
	const std::size_t length = WorkerExceptionDiagnostic::format("Dispatcher", message.c_str(), output, sizeof(output));
	const std::string diagnostic(output, length);
	const std::string prefix = "[FATAL] Unhandled exception in Dispatcher: first?second??";
	if (diagnostic.compare(0, prefix.size(), prefix) != 0 || diagnostic.empty() || diagnostic.back() != '\n') {
		std::fputs("worker exception diagnostic prefix or terminator mismatch\n", stderr);
		return 1;
	}
	if (diagnostic.find('\r') != std::string::npos || diagnostic.find('\n') != diagnostic.size() - 1 ||
	        diagnostic.find('\x1B') != std::string::npos) {
		std::fputs("worker exception diagnostic contains an unsanitized control byte\n", stderr);
		return 1;
	}
	const std::size_t messageOffset = diagnostic.find(": ") + 2;
	if (diagnostic.size() - messageOffset - 1 != WorkerExceptionDiagnostic::MAX_EXCEPTION_MESSAGE_BYTES ||
	        diagnostic.compare(diagnostic.size() - 4, 3, "...") != 0) {
		std::fputs("worker exception diagnostic message was not bounded\n", stderr);
		return 1;
	}

	const std::size_t unknownLength = WorkerExceptionDiagnostic::format("DatabaseTasks", nullptr, output, sizeof(output));
	const std::string unknown(output, unknownLength);
	if (unknown != "[FATAL] Unhandled exception in DatabaseTasks: non-standard exception\n") {
		std::fputs("non-standard worker exception diagnostic mismatch\n", stderr);
		return 1;
	}

	const std::size_t shortLength = WorkerExceptionDiagnostic::format("Scheduler", "short", output, sizeof(output));
	const std::string shortMessage(output, shortLength);
	if (shortMessage != "[FATAL] Unhandled exception in Scheduler: short\n") {
		std::fputs("short worker exception diagnostic mismatch\n", stderr);
		return 1;
	}

	const std::string exactLimit(WorkerExceptionDiagnostic::MAX_EXCEPTION_MESSAGE_BYTES - 3, 'e');
	const std::size_t exactLength = WorkerExceptionDiagnostic::format("Scheduler", exactLimit.c_str(), output, sizeof(output));
	const std::string exactMessage(output, exactLength);
	if (exactMessage.find("...") != std::string::npos || exactMessage.back() != '\n') {
		std::fputs("exact-limit worker exception diagnostic was incorrectly marked truncated\n", stderr);
		return 1;
	}

	const std::string overLimit(WorkerExceptionDiagnostic::MAX_EXCEPTION_MESSAGE_BYTES - 2, 'o');
	const std::size_t overLength = WorkerExceptionDiagnostic::format("Scheduler", overLimit.c_str(), output, sizeof(output));
	const std::string overMessage(output, overLength);
	if (overMessage.compare(overMessage.size() - 4, 3, "...") != 0) {
		std::fputs("over-limit worker exception diagnostic was not marked truncated\n", stderr);
		return 1;
	}

	char guarded[10] = {'L', 0, 0, 0, 0, 0, 0, 0, 0, 'R'};
	const std::size_t truncatedLength = WorkerExceptionDiagnostic::format("Dispatcher", "message", guarded + 1, 8);
	if (truncatedLength != 8 || guarded[0] != 'L' || guarded[9] != 'R') {
		std::fputs("worker exception diagnostic exceeded its output buffer\n", stderr);
		return 1;
	}

	std::puts("worker exception diagnostic tests passed");
	return 0;
}
