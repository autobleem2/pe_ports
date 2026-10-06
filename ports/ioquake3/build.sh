# ioquake3 (the 2020 line) for the console: the client and its OpenGL 1 renderer, SDL2 shared from the launcher, every
# other library built in. The renderer is a separate .so the engine loads next to itself; it reaches the GPU through
# the libGL.so.1 of the PE environment (gl4es), which the engine opens through SDL at run time - nothing links to it.
# ARCH=armv7l (not "arm"): only that name turns on the engine's ARM QVM compiler, and the game of OpenArena (its
# game, cgame and ui QVMs) would otherwise run in the interpreter.
# Sourced by ci/build.sh with $SRC (patched upstream), $STAGE (the launcher folder's files), $PORT_DIR.
port_build() {
    CFLAGS="$PSC_FLAGS -marm" make -C "$SRC" -j "$JOBS" release \
        PLATFORM=linux ARCH=armv7l COMPILE_ARCH=armv7l CROSS_COMPILING=1 CC="$CC" \
        USE_INTERNAL_LIBS=1 USE_LOCAL_HEADERS=1 \
        USE_OPENAL=0 USE_CURL=0 USE_VOIP=0 USE_MUMBLE=0 USE_FREETYPE=0 USE_RENDERER_DLOPEN=1 \
        BUILD_CLIENT=1 BUILD_SERVER=0 BUILD_STANDALONE=0 BUILD_GAME_SO=0 BUILD_GAME_QVM=0 \
        BUILD_BASEGAME=0 BUILD_MISSIONPACK=0 BUILD_RENDERER_OPENGL2=0 \
        SDL_CFLAGS="$(pkg-config --cflags sdl2)" SDL_LIBS="$(pkg-config --libs sdl2)"
    local out="$SRC/build/release-linux-armv7l"
    cp "$out/ioquake3.armv7l" "$out/renderer_opengl1_armv7l.so" "$STAGE/"
    "$STRIP" "$STAGE/ioquake3.armv7l" "$STAGE/renderer_opengl1_armv7l.so"
    check_binary "$STAGE/renderer_opengl1_armv7l.so"

    # our start-up helper and the pad's bindings (files/)
    cp "$PORT_DIR/files/psc-pad.sh" "$STAGE/psc-pad.sh"
    mkdir -p "$STAGE/psc"
    cp "$PORT_DIR/files/psc/"*.cfg "$STAGE/psc/"
}
