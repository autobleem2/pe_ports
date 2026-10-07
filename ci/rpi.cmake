# The Raspberry Pi 32-bit (Raspberry Pi OS armhf, Debian 12): the autobleem-build image's cross compiler against its armhf
# multiarch libraries (/usr/lib/arm-linux-gnueabihf: SDL2 2.26 family, GLES2, EGL, ALSA, zlib; headers in /usr/include).
# One toolchain file for every CMake port and for the libraries built with a port (gl4es, OpenAL Soft). The flags come
# from ci/build.sh (ARM_FLAGS); PE_EXTRA_ROOT (environment) adds one more place for headers (the Boost headers a build
# fetched). CMake finds programs on the build machine, libraries and headers for the Pi.
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(CMAKE_C_COMPILER   arm-linux-gnueabihf-gcc)
set(CMAKE_CXX_COMPILER arm-linux-gnueabihf-g++)
set(CMAKE_LIBRARY_ARCHITECTURE arm-linux-gnueabihf)

set(CMAKE_FIND_ROOT_PATH /usr/arm-linux-gnueabihf /usr)
if(DEFINED ENV{PE_EXTRA_ROOT})
    list(APPEND CMAKE_FIND_ROOT_PATH "$ENV{PE_EXTRA_ROOT}")
endif()
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

set(CMAKE_C_FLAGS_INIT   "-mfloat-abi=hard -march=armv7-a -mfpu=neon-vfpv4")
set(CMAKE_CXX_FLAGS_INIT "-mfloat-abi=hard -march=armv7-a -mfpu=neon-vfpv4")
