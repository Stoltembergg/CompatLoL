# SPDX-License-Identifier: GPL-3.0-only
cmake_minimum_required(VERSION 3.20)
project(CompatLoLLLVMProbe LANGUAGES CXX)
if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux")
  message(FATAL_ERROR "LLVM probe is for standalone Indium on Linux")
endif()
if(NOT IS_DIRECTORY "${INDIUM_SOURCE}" OR NOT IS_DIRECTORY "${INDIUM_BUILD}")
  message(FATAL_ERROR "INDIUM_SOURCE and INDIUM_BUILD are required")
endif()
find_package(LLVM REQUIRED CONFIG)
find_library(IRIDIUM_LIBRARY NAMES iridium PATHS "${INDIUM_BUILD}" NO_DEFAULT_PATH REQUIRED)
add_executable(llvm_probe main.cpp)
target_compile_features(llvm_probe PRIVATE cxx_std_17)
target_include_directories(llvm_probe PRIVATE
  "${INDIUM_SOURCE}/include" "${INDIUM_SOURCE}/private-include"
  "${CMAKE_CURRENT_SOURCE_DIR}/../../third_party/json" ${LLVM_INCLUDE_DIRS})
target_link_libraries(llvm_probe PRIVATE "${IRIDIUM_LIBRARY}" ${CMAKE_DL_LIBS})
set_target_properties(llvm_probe PROPERTIES BUILD_RPATH "${INDIUM_BUILD}")
