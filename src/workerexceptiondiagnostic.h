#ifndef FS_WORKER_EXCEPTION_DIAGNOSTIC_H_6D2A34779A72413A9DCA65AB8467E1C2
#define FS_WORKER_EXCEPTION_DIAGNOSTIC_H_6D2A34779A72413A9DCA65AB8467E1C2

#include <cstddef>
#include <cstdio>

namespace WorkerExceptionDiagnostic {

constexpr std::size_t MAX_EXCEPTION_MESSAGE_BYTES = 256;
constexpr std::size_t MAX_DIAGNOSTIC_BYTES = 384;

inline void appendByte(char* output, std::size_t capacity, std::size_t& length, char value) noexcept
{
	if (length < capacity) {
		output[length++] = value;
	}
}

inline char sanitizeByte(unsigned char value) noexcept
{
	return value >= 0x20 && value <= 0x7E ? static_cast<char>(value) : '?';
}

inline void appendSanitized(char* output, std::size_t capacity, std::size_t& length,
		const char* text, std::size_t maxBytes) noexcept
{
	if (!text) {
		return;
	}
	for (std::size_t i = 0; i < maxBytes && text[i] != '\0'; ++i) {
		appendByte(output, capacity, length, sanitizeByte(static_cast<unsigned char>(text[i])));
	}
}

inline std::size_t format(const char* worker, const char* message,
		char* output, std::size_t capacity) noexcept
{
	if (!output || capacity == 0) {
		return 0;
	}

	std::size_t length = 0;
	static const char PREFIX[] = "[FATAL] Unhandled exception in ";
	appendSanitized(output, capacity, length, PREFIX, sizeof(PREFIX) - 1);
	appendSanitized(output, capacity, length, worker, 32);
	appendSanitized(output, capacity, length, ": ", 2);

	if (!message) {
		static const char UNKNOWN[] = "non-standard exception";
		appendSanitized(output, capacity, length, UNKNOWN, sizeof(UNKNOWN) - 1);
	} else {
		constexpr std::size_t MESSAGE_PREFIX_BYTES = MAX_EXCEPTION_MESSAGE_BYTES - 3;
		appendSanitized(output, capacity, length, message, MESSAGE_PREFIX_BYTES);
		if (message[MESSAGE_PREFIX_BYTES] != '\0') {
			appendSanitized(output, capacity, length, "...", 3);
		}
	}

	appendByte(output, capacity, length, '\n');
	return length;
}

inline void log(const char* worker, const char* message) noexcept
{
	try {
		char diagnostic[MAX_DIAGNOSTIC_BYTES];
		const std::size_t length = format(worker, message, diagnostic, sizeof(diagnostic));
		if (length != 0) {
			(void)std::fwrite(diagnostic, 1, length, stderr);
			(void)std::fflush(stderr);
		}
	} catch (...) {
		// A diagnostic failure must never replace the original worker exception.
	}
}

} // namespace WorkerExceptionDiagnostic

#endif
