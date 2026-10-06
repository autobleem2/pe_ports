# LZDoom 3.84, cross-built for the console (ARM hard-float, gcc-6). First the build tools the project runs while it
# builds (zipdir, lemon, re2c and two small probes) are compiled for the build machine; the second pass is the
# console program, which imports them (the project's own cross-compiling support, FORCE_CROSSCOMPILE).
# Sourced by ci/build.sh with $SRC (patched upstream), $STAGE (the launcher folder's files), $PORT_DIR.
port_build() {
    local host="$BUILD_DIR/host" cross="$BUILD_DIR/cross"
    # 1. the tools, natively (the build image's own compiler)
    (
        unset CC CXX STRIP AR PKG_CONFIG_LIBDIR SDL_PREFIX
        export PATH="${PATH#"$PSC/sdl2/bin":}"
        cmake -S "$SRC" -B "$host" -G Ninja -DCMAKE_BUILD_TYPE=Release -DNO_GTK=ON -DNO_OPENAL=ON
        ninja -C "$host" -j "$JOBS" zipdir lemon re2c
    )
    echo "host tools built"
}
