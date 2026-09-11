#----------------------------------------------------------------
# Generated CMake target import file for configuration "Release".
#----------------------------------------------------------------

# Commands may need to know the format version.
set(CMAKE_IMPORT_FILE_VERSION 1)

# Import target "epiceye_sdk::epiceye_sdk" for configuration "Release"
set_property(TARGET epiceye_sdk::epiceye_sdk APPEND PROPERTY IMPORTED_CONFIGURATIONS RELEASE)
set_target_properties(epiceye_sdk::epiceye_sdk PROPERTIES
  IMPORTED_LOCATION_RELEASE "${_IMPORT_PREFIX}/lib/libepiceye_sdk.so"
  IMPORTED_SONAME_RELEASE "libepiceye_sdk.so"
  )

list(APPEND _cmake_import_check_targets epiceye_sdk::epiceye_sdk )
list(APPEND _cmake_import_check_files_for_epiceye_sdk::epiceye_sdk "${_IMPORT_PREFIX}/lib/libepiceye_sdk.so" )

# Commands beyond this point should not need to know the version.
set(CMAKE_IMPORT_FILE_VERSION)
