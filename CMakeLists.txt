cmake_minimum_required(VERSION 3.16)
project(tfs LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(PkgConfig REQUIRED)
pkg_check_modules(LUAJIT REQUIRED IMPORTED_TARGET luajit)
pkg_check_modules(PUGIXML REQUIRED IMPORTED_TARGET pugixml)
pkg_check_modules(MYSQL REQUIRED IMPORTED_TARGET mysqlclient)
pkg_check_modules(GMP REQUIRED IMPORTED_TARGET gmp)
find_package(Threads REQUIRED)
find_package(Boost 1.53 REQUIRED COMPONENTS system filesystem)

include(src/CMakeLists.txt)
list(REMOVE_ITEM tfs_SRC "${CMAKE_CURRENT_SOURCE_DIR}/src/otserv.cpp")
add_library(tfs_core STATIC ${tfs_SRC})
add_executable(tfs src/otserv.cpp)
target_link_libraries(tfs PRIVATE tfs_core)

target_include_directories(tfs_core PUBLIC src ${Boost_INCLUDE_DIRS})
target_link_libraries(tfs_core PUBLIC
	PkgConfig::LUAJIT
	PkgConfig::PUGIXML
	PkgConfig::MYSQL
	PkgConfig::GMP
	${Boost_LIBRARIES}
	Threads::Threads
)

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
	target_compile_options(tfs_core PRIVATE -Wall -fno-var-tracking -pipe -fvisibility=hidden -fno-strict-aliasing)
	target_compile_options(tfs PRIVATE -Wall -fno-var-tracking -pipe -fvisibility=hidden -fno-strict-aliasing)
endif()

option(TFS_BUILD_RARITY_TESTS "Build isolated rarity integration tests against the server core" OFF)
if(TFS_BUILD_RARITY_TESTS)
	enable_testing()
	add_executable(rarity-core-tests tests/rarity-core-tests.cpp)
	target_link_libraries(rarity-core-tests PRIVATE tfs_core)
	add_test(NAME rarity-core COMMAND rarity-core-tests)
	set_tests_properties(rarity-core PROPERTIES WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}")
endif()

option(TFS_BUILD_STATUS_QUERY_TESTS "Build isolated status query rate limiter tests" OFF)
if(TFS_BUILD_STATUS_QUERY_TESTS)
	enable_testing()
	add_executable(status-query-rate-limiter-tests tests/status-query-rate-limiter-tests.cpp)
	target_include_directories(status-query-rate-limiter-tests PRIVATE src)
	target_link_libraries(status-query-rate-limiter-tests PRIVATE Threads::Threads)
	add_test(NAME status-query-rate-limiter COMMAND status-query-rate-limiter-tests)
endif()

option(TFS_BUILD_SCHEDULER_TESTS "Build isolated scheduler event queue tests" OFF)
if(TFS_BUILD_SCHEDULER_TESTS)
	enable_testing()
	add_executable(scheduler-event-queue-tests tests/scheduler-event-queue-tests.cpp)
	target_include_directories(scheduler-event-queue-tests PRIVATE src)
	target_link_libraries(scheduler-event-queue-tests PRIVATE Threads::Threads)
	add_test(NAME scheduler-event-queue COMMAND scheduler-event-queue-tests)
endif()

option(TFS_BUILD_NETWORKMESSAGE_TESTS "Build packet cursor and parser regression tests" OFF)
if(TFS_BUILD_NETWORKMESSAGE_TESTS)
	enable_testing()
	add_executable(networkmessage-bounds-tests tests/networkmessage-bounds-tests.cpp)
	target_include_directories(networkmessage-bounds-tests PRIVATE src)
	target_link_libraries(networkmessage-bounds-tests PRIVATE tfs_core)
	add_test(NAME networkmessage-bounds COMMAND networkmessage-bounds-tests)

	add_executable(protocol-walk-parser-tests tests/protocol-walk-parser-tests.cpp)
	target_include_directories(protocol-walk-parser-tests PRIVATE src)
	target_link_libraries(protocol-walk-parser-tests PRIVATE tfs_core)
	add_test(NAME protocol-walk-parser COMMAND protocol-walk-parser-tests)
endif()
