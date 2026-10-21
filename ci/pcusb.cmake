# The PC stick (PC-USB, Debian 12 i386): the autobleem-build image's gcc in 32-bit mode against its i386 multiarch libraries
# (/usr/lib/i386-linux-gnu: SDL2 2.26 family, GLES2, EGL, ALSA, zlib; headers in /usr/include). One toolchain file for every
# CMake port and for the libraries built with a port. The flags come from ci/build.sh (ARM_FLAGS holds the CPU switches:
# -m32 -march=i686 -mno-sse -mno-sse2 -mfpmath=387); the compilers are the wrapper scripts ci/build.sh writes to build/shim
# (gcc -m32, g++ -m32). PE_EXTRA_ROOT (environment) adds one more place for headers (the Boost headers a build fetched).
# CMake finds programs on the build machine, libraries and headers for the stick.
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR i686)

set(CMAKE_C_COMPILER   i386-gcc)
set(CMAKE_CXX_COMPILER i386-g++)
set(CMAKE_LIBRARY_ARCHITECTURE i386-linux-gnu)
set(CMAKE_C_FLAGS_INIT   "-m32 -march=i686 -mtune=generic -mno-sse -mno-sse2 -mfpmath=387")
set(CMAKE_CXX_FLAGS_INIT "-m32 -march=i686 -mtune=generic -mno-sse -mno-sse2 -mfpmath=387")

set(CMAKE_FIND_ROOT_PATH /usr)
if(DEFINED ENV{PE_EXTRA_ROOT})
    list(APPEND CMAKE_FIND_ROOT_PATH "$ENV{PE_EXTRA_ROOT}")
endif()
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
