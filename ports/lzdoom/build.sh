# LZDoom 3.84, cross-built for the console (ARM hard-float, gcc-6). First the build tools the project runs while it
# builds (zipdir, lemon, re2c and two small probes) are compiled for the build machine; the second pass is the
# console program, which imports them (the project's own cross-compiling support, IMPORT_EXECUTABLES).
# No OpenMP (the console has no libgomp), no GTK, no FluidSynth (no headers or library for it here); OpenAL is
# loaded at run time (DYN_OPENAL: the project carries its own copy of the headers) from the OpenAL Soft that ships
# in the package, and so are libsndfile and libmpg123 (not shipped: Freedoom needs neither).
# Sourced by ci/build.sh with $SRC (patched upstream), $STAGE (the launcher folder's files), $PORT_DIR.
port_build() {
    local host="$BUILD_DIR/host" cross="$BUILD_DIR/cross"
    # 1. the tools, natively (the build image's own compiler, none of the console's environment)
    (
        unset CC CXX STRIP AR PKG_CONFIG_LIBDIR SDL_PREFIX CFLAGS CXXFLAGS
        export PATH="$NATIVE_PATH"
        cmake -S "$SRC" -B "$host" -G Ninja -DCMAKE_BUILD_TYPE=Release -DNO_GTK=ON
        ninja -C "$host" -j "$JOBS" zipdir lemon re2c updaterevision arithchk qnan
    )

    # 2. the program for the console (the Pi: the image's gcc 12 no longer pulls <limits> in by itself, which scripting/types.cpp
    # relies on - the header is included for every file instead of editing the pinned source; the toolchain file's
    # flags are given again, a CMAKE_CXX_FLAGS of ours replaces them)
    local extra=()
    # (and the image's armhf libjpeg/bzip2 would be linked as shared libraries a Pi may not have: the project's own copies)
    [ "$TARGET" = psc ] || extra=(-DCMAKE_CXX_FLAGS="$ARM_FLAGS -include limits" -DFORCE_INTERNAL_JPEG=ON -DFORCE_INTERNAL_BZIP2=ON)
    cmake -S "$SRC" -B "$cross" -G Ninja -DCMAKE_BUILD_TYPE=Release ${extra[@]+"${extra[@]}"} \
        -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN_CMAKE" -DIMPORT_EXECUTABLES="$host/ImportExecutables.cmake" \
        -DNO_OPENMP=ON -DFORCE_INTERNAL_ZLIB=ON -DNO_GTK=ON -DCMAKE_SKIP_RPATH=ON \
        -DCMAKE_C_FLAGS_RELEASE="-O3 -DNDEBUG" -DCMAKE_CXX_FLAGS_RELEASE="-O3 -DNDEBUG"
    ninja -C "$cross" -j "$JOBS"
    cp "$cross/lzdoom" "$STAGE/lzdoom"
    "$STRIP" "$STAGE/lzdoom"
    cp "$cross/lzdoom.pk3" "$cross/brightmaps.pk3" "$cross/lights.pk3" "$cross/game_support.pk3" "$STAGE/"
    # our start-up helper and the pad's bindings (files/)
    cp "$PORT_DIR/files/psc-pad.sh" "$STAGE/psc-pad.sh"
    cp "$PORT_DIR/files/alsoft.conf" "$STAGE/alsoft.conf"
    mkdir -p "$STAGE/psc"
    cp "$PORT_DIR/files/psc/"*.cfg "$STAGE/psc/"

    # 3. OpenAL Soft, which the engine opens at run time: built for the console (ALSA, loaded at run time) from the
    # pinned release, shipped next to the program in lib/ (the console's firmware has no OpenAL)
    local oal=openal-soft-1.19.1
    fetch "$AB_DEPS_BASE/openal/$oal.tar.bz2" \
        5c2f87ff5188b95e0dc4769719a9d89ce435b8322b4478b95dd4b427fe84b2e9 "$oal.tar.bz2" \
        "https://openal-soft.org/openal-releases/$oal.tar.bz2"
    mkdir -p "$BUILD_DIR/openal"
    tar -xjf "$ROOT/build_data/$oal.tar.bz2" -C "$BUILD_DIR/openal"
    # its two generator programs run on the build machine: built first with the image's own compiler, where the
    # project's build expects them (its own nested build would inherit the console compiler from the environment)
    mkdir -p "$BUILD_DIR/openal/build/native-tools"
    (
        unset CC CXX STRIP AR PKG_CONFIG_LIBDIR SDL_PREFIX CFLAGS CXXFLAGS
        export PATH="$NATIVE_PATH"
        cd "$BUILD_DIR/openal/build/native-tools"
        cmake -G Ninja "$BUILD_DIR/openal/$oal/native-tools"
        ninja
    )
    # (the Pi's gcc 12 forbids common symbols by default and OpenAL Soft 1.19.1 defines its tables in a header: -fcommon is the
    # old compilers' behaviour; the toolchain file's flags are given again, a CMAKE_C_FLAGS of ours replaces them)
    local oal_extra=()
    [ "$TARGET" = psc ] || oal_extra=(-DCMAKE_C_FLAGS="$ARM_FLAGS -fcommon")
    cmake -S "$BUILD_DIR/openal/$oal" -B "$BUILD_DIR/openal/build" -G Ninja -DCMAKE_BUILD_TYPE=Release ${oal_extra[@]+"${oal_extra[@]}"} \
        -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN_CMAKE" -DCMAKE_SKIP_RPATH=ON -DLIBTYPE=SHARED -DCMAKE_SHARED_LINKER_FLAGS=-Wl,--as-needed \
        -DALSOFT_UTILS=OFF -DALSOFT_EXAMPLES=OFF -DALSOFT_TESTS=OFF -DALSOFT_INSTALL=OFF \
        -DALSOFT_REQUIRE_ALSA=ON -DALSOFT_BACKEND_PULSEAUDIO=OFF -DALSOFT_BACKEND_OSS=OFF \
        -DALSOFT_BACKEND_SOLARIS=OFF -DALSOFT_BACKEND_SNDIO=OFF -DALSOFT_BACKEND_PORTAUDIO=OFF \
        -DALSOFT_BACKEND_JACK=OFF -DALSOFT_BACKEND_WAVE=OFF
    ninja -C "$BUILD_DIR/openal/build" -j "$JOBS"
    mkdir -p "$STAGE/lib"
    cp -L "$BUILD_DIR/openal/build/libopenal.so.1" "$STAGE/lib/libopenal.so.1"
    "$STRIP" "$STAGE/lib/libopenal.so.1"
    check_binary "$STAGE/lib/libopenal.so.1"
    cp "$BUILD_DIR/openal/$oal/COPYING" "$SRC/COPYING-openal-soft"
}
