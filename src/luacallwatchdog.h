#ifndef TFS_LUA_CALL_WATCHDOG_H
#define TFS_LUA_CALL_WATCHDOG_H

#include <lua.hpp>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>

// Report completed slow calls, including time in native bindings. This is not
// an infinite-loop detector or an execution deadline. No hooks are installed:
// count hooks do not reliably observe compiled LuaJIT traces.
class LuaCallWatchdog {
public:
	using Clock = uint64_t (*)();
	using Reporter = void (*)(const char*, int, uint64_t);

	explicit LuaCallWatchdog(lua_State* state, int nargs = 0, Clock clock = monotonicMillis,
	                         Reporter reporter = report, uint64_t budget = 1000) :
		clock(clock), reporter(reporter), budget(budget)
	{
		lua_Debug debug = {};
		const int functionIndex = lua_gettop(state) - nargs;
		if (functionIndex > 0 && lua_isfunction(state, functionIndex)) {
			lua_pushvalue(state, functionIndex);
			if (lua_getinfo(state, ">S", &debug)) {
				std::snprintf(source, sizeof(source), "%s", debug.short_src);
				line = debug.linedefined;
			}
		}
		started = clock();
	}

	~LuaCallWatchdog()
	{
		const uint64_t elapsed = clock() - started;
		if (elapsed >= budget) reporter(source, line, elapsed);
	}

	LuaCallWatchdog(const LuaCallWatchdog&) = delete;
	LuaCallWatchdog& operator=(const LuaCallWatchdog&) = delete;

private:
	static uint64_t monotonicMillis()
	{
		return std::chrono::duration_cast<std::chrono::milliseconds>(
			std::chrono::steady_clock::now().time_since_epoch()).count();
	}

	static void report(const char* source, int line, uint64_t elapsed)
	{
		std::fprintf(stderr, "[Lua diagnostic] Slow script invocation (%llu ms) at %s:%d\n",
		             static_cast<unsigned long long>(elapsed), source, line);
	}

	Clock clock;
	Reporter reporter;
	uint64_t budget;
	uint64_t started;
	char source[LUA_IDSIZE] = "unknown";
	int line = -1;
};

#endif
