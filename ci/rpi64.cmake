# The Raspberry Pi 64-bit (aarch64): the autobleem-build image's cross compiler against its arm64 multiarch libraries
# (/usr/lib/aarch64-linux-gnu: SDL2 2.26 family, GLES2, EGL, ALSA, zlib; headers in /usr/include). One toolchain file for
# every CMake port and for the libraries built with a port (gl4es, OpenAL Soft). The flags come from ci/build.sh
# (CPU_FLAGS); PE_EXTRA_ROOT (environment) adds one more place for headers (the Boost headers a build fetched). CMake finds
# programs on the build machine, libraries and headers for the Pi.
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR aarch64)

set(CMAKE_C_COMPILER   aarch64-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER aarch64-linux-gnu-g++)
set(CMAKE_LIBRARY_ARCHITECTURE aarch64-linux-gnu)

set(CMAKE_FIND_ROOT_PATH /usr/aarch64-linux-gnu /usr)
if(DEFINED ENV{PE_EXTRA_ROOT})
    list(APPEND CMAKE_FIND_ROOT_PATH "$ENV{PE_EXTRA_ROOT}")
endif()
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

set(CMAKE_C_FLAGS_INIT   "-march=armv8-a")
set(CMAKE_CXX_FLAGS_INIT "-march=armv8-a")
