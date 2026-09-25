#include <stdio.h>
#include <string.h>

#include <lua.h>
#include <lauxlib.h>
#include <lualib.h>

int main(int argc, char **argv)
{
	int execute = 1;
	int firstFile = 1;
	if (argc > 1 && strcmp(argv[1], "--syntax-only") == 0) {
		execute = 0;
		firstFile = 2;
	}
	if (argc <= firstFile) {
		fprintf(stderr, "Usage: lua52_runner [--syntax-only] file.lua [file.lua ...]\n");
		return 2;
	}

	lua_State *state = luaL_newstate();
	if (!state) {
		fprintf(stderr, "Could not create Lua state.\n");
		return 2;
	}
	if (execute) {
		luaL_openlibs(state);
	}

	for (int i = firstFile; i < argc; ++i) {
		if (luaL_loadfile(state, argv[i]) != 0) {
			fprintf(stderr, "%s: %s\n", argv[i], lua_tostring(state, -1));
			lua_close(state);
			return 1;
		}
		if (execute && lua_pcall(state, 0, 0, 0) != 0) {
			fprintf(stderr, "%s: %s\n", argv[i], lua_tostring(state, -1));
			lua_close(state);
			return 1;
		}
		if (!execute) {
			lua_pop(state, 1);
		}
	}

	lua_close(state);
	return 0;
}
