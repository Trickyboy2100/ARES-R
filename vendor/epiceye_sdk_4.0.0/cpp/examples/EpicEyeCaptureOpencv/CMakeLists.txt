find_package(OpenCV REQUIRED)
include_directories(${OpenCV_INCLUDE_DIRS})
include_directories(${CMAKE_CURRENT_SOURCE_DIR})

add_executable(EpicEyeCaptureOpencv main.cpp)
target_link_libraries(
    EpicEyeCaptureOpencv
    PRIVATE
    epiceye_sdk::epiceye_sdk
    ${OpenCV_LIBS}
)
