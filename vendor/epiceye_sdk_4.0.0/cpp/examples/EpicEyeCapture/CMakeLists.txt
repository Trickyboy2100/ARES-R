include_directories(thirdparty)

add_executable(EpicEyeCapture main.cpp thirdparty/lodepng.cpp)
target_link_libraries(EpicEyeCapture PRIVATE epiceye_sdk::epiceye_sdk)
