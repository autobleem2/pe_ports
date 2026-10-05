# Commander Genius 2.4.0: CMake, SDL2 renderer (no OpenGL, so no libGL), the launcher's shared SDL2 family.
# Sourced by ci/build.sh with $SRC (the upstream), $STAGE (the launcher folder's files), $PORT_DIR, fetch().
port_build() {
    # Boost's property_tree headers (header-only; the image has no Boost): the release tarball, pinned
    local boost=boost_1_74_0
    fetch "https://archives.boost.io/release/1.74.0/source/$boost.tar.bz2" \
        83bfc1507731a0906e387fc28b7ef5417d591429e51e788417fe9ff025e116b1 "$boost.tar.bz2"
    mkdir -p "$BUILD_DIR/boost"
    tar -xjf "$ROOT/build_data/$boost.tar.bz2" -C "$BUILD_DIR/boost" "$boost/boost"
    export PE_EXTRA_ROOT="$BUILD_DIR/boost/$boost"

    cmake -S "$SRC" -B "$BUILD_DIR/cmake" -G Ninja -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_TOOLCHAIN_FILE="$PORT_DIR/psc.cmake" \
        -DUSE_OPENGL=No -DUSE_SDL_TTF=No -DDOWNLOADER=No -DBUILD_TARGET=LINUX -DCMAKE_SKIP_RPATH=ON \
        -DBoost_INCLUDE_DIR="$PE_EXTRA_ROOT" -DBoost_NO_BOOST_CMAKE=ON \
        -DZLIB_LIBRARY="$PSC/sysroot/usr/lib/arm-linux-gnueabihf/libz.a" -DZLIB_INCLUDE_DIR="$PSC/sysroot/usr/include"
    ninja -C "$BUILD_DIR/cmake" -j "$JOBS"
    cp "$BUILD_DIR/cmake/src/CGeniusExe" "$STAGE/CGeniusExe"
    "$STRIP" "$STAGE/CGeniusExe"

    # CG's own graphics and help text (vfsroot/global), its music and sounds (hqp/global, the high quality pack
    # upstream carries) and the Keen 1 shareware episode; our settings
    mkdir -p "$STAGE/.CommanderGenius/global"
    cp -a "$SRC/vfsroot/global/." "$STAGE/.CommanderGenius/global/"
    cp -a "$SRC/hqp/global/." "$STAGE/.CommanderGenius/global/"
    cp -a "$PORT_DIR/data/." "$STAGE/"
    cp "$PORT_DIR/files/cgenius.cfg" "$PORT_DIR/files/games.cfg" "$STAGE/.CommanderGenius/"
}
