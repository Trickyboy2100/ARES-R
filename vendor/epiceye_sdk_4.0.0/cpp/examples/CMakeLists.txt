cmake_minimum_required(VERSION 3.23)
project(epiceye_sdk_examples LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(WIN32)
    set(EPICEYE_SDK_PLATFORM "windows-x64")
elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "aarch64|arm64")
    set(EPICEYE_SDK_PLATFORM "linux-arm64")
else()
    set(EPICEYE_SDK_PLATFORM "linux-x86_64")
endif()

unset(EPICEYE_SDK_ROOT CACHE)
set(EPICEYE_SDK_PACKAGE_DIR "${CMAKE_CURRENT_LIST_DIR}/../${EPICEYE_SDK_PLATFORM}/epiceye_sdk-4.0.0" CACHE PATH "EpicEye SDK package directory")
find_package(epiceye_sdk CONFIG REQUIRED PATHS "${EPICEYE_SDK_PACKAGE_DIR}" NO_DEFAULT_PATH)

if(WIN32)
    set(EPICEYE_SDK_RUNTIME "${EPICEYE_SDK_PACKAGE_DIR}/bin/epiceye_sdk.dll")
else()
    set(EPICEYE_SDK_RUNTIME "${EPICEYE_SDK_PACKAGE_DIR}/lib/libepiceye_sdk.so")
endif()

option(EPICEYE_BUILD_EXAMPLES_OPENCV "Build EpicEyeCaptureOpencv example" OFF)

set(EPICEYE_EXAMPLES
    SearchCamera
    CameraInfo
    TemperatureInfo
    CameraConfig
    CameraParameters
    EpicEyeCapture
    CameraIPConfig
    UndistortLut
    EpicRawOffline
    GetFrame
    Stream2D
    LineScan
    TextureToPointCloud
    HandEyeCalibration
    IntrinsicCalibration
    IntrinsicAccuracyCheck
    DiscoveryService
)

foreach(example IN LISTS EPICEYE_EXAMPLES)
    add_subdirectory(${example})
    if(WIN32)
        set(example_runtime_dir "${CMAKE_BINARY_DIR}/${example}/Release")
    else()
        set(example_runtime_dir "${CMAKE_BINARY_DIR}/${example}")
    endif()
    file(MAKE_DIRECTORY "${example_runtime_dir}")
    file(COPY "${EPICEYE_SDK_RUNTIME}" DESTINATION "${example_runtime_dir}")
endforeach()

if(EPICEYE_BUILD_EXAMPLES_OPENCV)
    find_package(OpenCV REQUIRED)
    add_subdirectory(EpicEyeCaptureOpencv)
    if(WIN32)
        set(opencv_runtime_dir "${CMAKE_BINARY_DIR}/EpicEyeCaptureOpencv/Release")
    else()
        set(opencv_runtime_dir "${CMAKE_BINARY_DIR}/EpicEyeCaptureOpencv")
    endif()
    file(MAKE_DIRECTORY "${opencv_runtime_dir}")
    file(COPY "${EPICEYE_SDK_RUNTIME}" DESTINATION "${opencv_runtime_dir}")
endif()
