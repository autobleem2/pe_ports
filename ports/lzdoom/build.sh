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
        export PATH="${PATH#"$PSC/sdl2/bin":}"
        cmake -S "$SRC" -B "$host" -G Ninja -DCMAKE_BUILD_TYPE=Release -DNO_GTK=ON
        ninja -C "$host" -j "$JOBS" zipdir lemon re2c updaterevision arithchk qnan
    )

    # 2. the program for the console
    cmake -S "$SRC" -B "$cross" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_TOOLCHAIN_FILE="$PORT_DIR/psc.cmake" -DIMPORT_EXECUTABLES="$host/ImportExecutables.cmake" \
        -DCMAKE_DISABLE_FIND_PACKAGE_OpenMP=ON -DNO_GTK=ON -DCMAKE_SKIP_RPATH=ON \
        -DCMAKE_C_FLAGS_RELEASE="-O3 -DNDEBUG" -DCMAKE_CXX_FLAGS_RELEASE="-O3 -DNDEBUG"
    ninja -C "$cross" -j "$JOBS"
    cp "$cross/lzdoom" "$STAGE/lzdoom"
    "$STRIP" "$STAGE/lzdoom"
    cp "$cross/lzdoom.pk3" "$cross/brightmaps.pk3" "$cross/lights.pk3" "$cross/game_support.pk3" "$STAGE/"
}
