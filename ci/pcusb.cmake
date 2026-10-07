# The PC stick (Debian 12 i386): the autobleem-build image's i686-linux-gnu cross compiler against its :i386 multiarch
# libraries (/usr/lib/i386-linux-gnu: SDL2 2.26 family, GLES2, EGL, ALSA, zlib; headers in /usr/include and
# /usr/include/i386-linux-gnu). One toolchain file for every CMake port and for the libraries built with a port (gl4es,
# OpenAL Soft). The flags come from ci/build.sh (CPU_FLAGS: plain i686 like the launcher, no SSE2); PE_EXTRA_ROOT (environment) adds one more
# place for headers (the Boost headers a build fetched). CMake finds programs on the build machine, libraries and headers for
# the stick.
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR i686)

set(CMAKE_C_COMPILER   i686-linux-gnu-gcc)
set(CMAKE_CXX_COMPILER i686-linux-gnu-g++)
set(CMAKE_LIBRARY_ARCHITECTURE i386-linux-gnu)

set(CMAKE_FIND_ROOT_PATH /usr/i686-linux-gnu /usr)
if(DEFINED ENV{PE_EXTRA_ROOT})
    list(APPEND CMAKE_FIND_ROOT_PATH "$ENV{PE_EXTRA_ROOT}")
endif()
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

set(CMAKE_C_FLAGS_INIT   "-march=i686 -mtune=generic -D_FILE_OFFSET_BITS=64")
set(CMAKE_CXX_FLAGS_INIT "-march=i686 -mtune=generic -D_FILE_OFFSET_BITS=64")
