# The PlayStation Classic: gcc-6 against the Debian Stretch sysroot of the autobleem-build image, the launcher's
# SDL2 2.0.18 family (SDL2, SDL2_image, SDL2_mixer, SDL2_ttf) in /opt/psc/sdl2. PE_EXTRA_ROOT (environment) adds
# one more place for headers (the Boost headers the build fetched).
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR arm)

if(DEFINED ENV{PSC})
    set(_psc "$ENV{PSC}")
else()
    set(_psc "/opt/psc")
endif()
set(CMAKE_C_COMPILER   "${_psc}/bin/armv8-sony-linux-gnueabihf-gcc")
set(CMAKE_CXX_COMPILER "${_psc}/bin/armv8-sony-linux-gnueabihf-g++")
set(CMAKE_SYSROOT "${_psc}/sysroot")

set(CMAKE_FIND_ROOT_PATH "${_psc}/sysroot" "${_psc}/sdl2")
if(DEFINED ENV{PE_EXTRA_ROOT})
    list(APPEND CMAKE_FIND_ROOT_PATH "$ENV{PE_EXTRA_ROOT}")
endif()
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

set(CMAKE_C_FLAGS_INIT   "-mfloat-abi=hard -march=armv8-a -mfpu=neon-vfpv4")
set(CMAKE_CXX_FLAGS_INIT "-mfloat-abi=hard -march=armv8-a -mfpu=neon-vfpv4")
