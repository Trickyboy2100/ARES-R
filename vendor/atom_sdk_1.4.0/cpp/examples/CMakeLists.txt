cmake_minimum_required(VERSION 3.16)
project(atom_sdk_examples LANGUAGES CXX)

# Windows 包只发布了 Release 版本的 atom_sdk_cpp.dll/.lib；exe 和它链接的每个
# DLL 必须用同一种 C 运行时库（/MD 对 /MDd），Debug 配置下链接会导致运行时
# "abort() has been called" 崩溃。这里把可选配置锁死成只有 Release，这样
# `cmake --build build`（不加 --config）也不会误建出 Debug 版本。
if(WIN32)
  set(CMAKE_CONFIGURATION_TYPES "Release" CACHE STRING "" FORCE)
endif()

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# cpp/ 下按平台分了 linux-x86_64/linux-arm64/windows-x64 三个子目录，
# 根据当前编译所在的平台自动选择对应目录，压缩包在任何一个平台解压后都能直接编译。
if(WIN32)
  set(ATOM_SDK_PLATFORM_DIR "windows-x64")
elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64")
  set(ATOM_SDK_PLATFORM_DIR "linux-arm64")
else()
  set(ATOM_SDK_PLATFORM_DIR "linux-x86_64")
endif()
set(ATOM_SDK_ROOT "${CMAKE_CURRENT_LIST_DIR}/../${ATOM_SDK_PLATFORM_DIR}/atom_sdk-1.4.0")
find_package(Threads REQUIRED)
find_library(ATOM_SDK_LIBRARY
    NAMES atom_sdk_cpp
    PATHS "${ATOM_SDK_ROOT}/lib"
    NO_DEFAULT_PATH
)
if(NOT ATOM_SDK_LIBRARY)
    message(FATAL_ERROR "Cannot find atom_sdk_cpp under ${ATOM_SDK_ROOT}/lib")
endif()

set(EXAMPLES
    basic_runtime
    graph_node_workflow
    graph_workflow
    run_single_node
    runtime_workflow
    test_activation
)
foreach(example IN LISTS EXAMPLES)
    add_executable(atom_sdk_example_${example} ${example}.cpp)
    target_include_directories(atom_sdk_example_${example} PRIVATE
        "${ATOM_SDK_ROOT}/include"
    )
    target_link_libraries(atom_sdk_example_${example} PRIVATE
        "${ATOM_SDK_LIBRARY}"
        Threads::Threads
    )
endforeach()
