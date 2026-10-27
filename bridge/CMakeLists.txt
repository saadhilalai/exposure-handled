cmake_minimum_required(VERSION 3.20)
project(camera_agent_bridge LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Sony's SDK is not in this repo (license). Point this at your own download.
set(SONY_SDK_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/RemoteCli" CACHE PATH
    "RemoteCli folder from Sony's Camera Remote SDK package")
set(CRSDK_INCLUDE_DIR "${SONY_SDK_DIR}/app/CRSDK")
set(CRSDK_LIB_DIR "${SONY_SDK_DIR}/external/crsdk")
if(NOT EXISTS "${CRSDK_INCLUDE_DIR}/CameraRemote_SDK.h")
    message(FATAL_ERROR "Sony Camera Remote SDK not found at ${SONY_SDK_DIR}. See README.md.")
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter)
find_package(Threads REQUIRED)
find_library(CR_CORE_LIB Cr_Core HINTS "${CRSDK_LIB_DIR}" NO_DEFAULT_PATH REQUIRED)

# Property code -> name table, generated from the local SDK header.
set(GENERATED_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
add_custom_command(
    OUTPUT "${GENERATED_DIR}/property_names.inc"
    COMMAND ${CMAKE_COMMAND} -E make_directory "${GENERATED_DIR}"
    COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_property_names.py"
            "${CRSDK_INCLUDE_DIR}/CrDeviceProperty.h" "${GENERATED_DIR}/property_names.inc"
    DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_property_names.py" "${CRSDK_INCLUDE_DIR}/CrDeviceProperty.h"
)
add_custom_target(property_names DEPENDS "${GENERATED_DIR}/property_names.inc")

function(add_camera_program name source)
    add_executable(${name} ${source})
    add_dependencies(${name} property_names)
    # SYSTEM: don't report warnings from Sony's headers, only from our code.
    target_include_directories(${name} SYSTEM PRIVATE "${CRSDK_INCLUDE_DIR}")
    target_include_directories(${name} PRIVATE "${GENERATED_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/src")
    target_link_libraries(${name} PRIVATE "${CR_CORE_LIB}" Threads::Threads)
    target_compile_options(${name} PRIVATE -Wall -Wextra)
    if(APPLE)
        # On macOS the SDK loads its USB/network adapters from
        # <program folder>/Contents/Frameworks/CrAdapter (same layout as Sony's sample).
        set_target_properties(${name} PROPERTIES BUILD_RPATH "@executable_path")
        add_custom_command(TARGET ${name} POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                    "${CRSDK_LIB_DIR}/libCr_Core.dylib"
                    "${CRSDK_LIB_DIR}/libmonitor_protocol.dylib"
                    "${CRSDK_LIB_DIR}/libmonitor_protocol_pf.dylib"
                    $<TARGET_FILE_DIR:${name}>
            COMMAND ${CMAKE_COMMAND} -E copy_directory
                    "${CRSDK_LIB_DIR}/CrAdapter"
                    $<TARGET_FILE_DIR:${name}>/Contents/Frameworks/CrAdapter
        )
    else()
        # On Linux (the Raspberry Pi), the same layout as Sony's own Linux sample: Sony's libraries and its
        # CrAdapter folder sit next to the program and are found through $ORIGIN. Sony's sample also builds
        # with these two flags on Linux (-fsigned-char: Raspberry Pi OS treats plain char as unsigned).
        set_target_properties(${name} PROPERTIES BUILD_RPATH "$ORIGIN" INSTALL_RPATH "$ORIGIN")
        target_compile_options(${name} PRIVATE -fsigned-char -fstack-protector-all)
        add_custom_command(TARGET ${name} POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_directory "${CRSDK_LIB_DIR}" $<TARGET_FILE_DIR:${name}>
        )
    endif()
endfunction()

add_camera_program(probe_readonly src/probe_readonly.cpp)
add_camera_program(camera_bridge src/camera_bridge.cpp)
