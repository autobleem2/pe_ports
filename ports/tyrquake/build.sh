# TyrQuake 0.66, the SDL2 software renderer (video, sound and input all SDL), the game data from data/.
# Sourced by ci/build.sh with $SRC (patched upstream), $STAGE (the launcher folder's files), $PORT_DIR.
port_build() {
    # the Makefile calls ImageMagick's `convert` once, for the window icon's header: shim/convert stands in for it
    chmod +x "$PORT_DIR/shim/convert"
    export PATH="$PORT_DIR/shim:$PATH"
    # the Makefile appends its own -O2 and warnings to the CFLAGS of the environment
    CFLAGS="$PSC_FLAGS -O3" make -C "$SRC" -j "$JOBS" bin/tyr-quake USE_SDL=Y \
        CC="$CC" STRIP="$STRIP" \
        SDL_CFLAGS="$(pkg-config --cflags sdl2)" SDL_LFLAGS="$(pkg-config --libs sdl2)"
    cp "$SRC/bin/tyr-quake" "$STAGE/tyr-quake"
    "$STRIP" "$STAGE/tyr-quake"
    cp -a "$PORT_DIR/data/." "$STAGE/"
    # our own start-up settings: the console pad on the keys the engine reads (files/)
    mkdir -p "$STAGE/.tyrquake/id1"
    cp "$PORT_DIR/files/config.cfg" "$PORT_DIR/files/video.cfg" "$STAGE/.tyrquake/id1/"
}
