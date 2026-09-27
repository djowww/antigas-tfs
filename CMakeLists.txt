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
add_executable(tfs ${tfs_SRC})

target_include_directories(tfs PRIVATE src ${Boost_INCLUDE_DIRS})
target_link_libraries(tfs PRIVATE
	PkgConfig::LUAJIT
	PkgConfig::PUGIXML
	PkgConfig::MYSQL
	PkgConfig::GMP
	${Boost_LIBRARIES}
	Threads::Threads
)

if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
	target_compile_options(tfs PRIVATE -Wall -fno-var-tracking -pipe -fvisibility=hidden -fno-strict-aliasing)
endif()
