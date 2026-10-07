# ioquake3 (the 2020 line) for the console: the client and its OpenGL 1 renderer, SDL2 shared from the launcher, every
# other library built in. The renderer is a separate .so the engine loads next to itself; it reaches the GPU through
# lib/libGL.so.1 of this package (gl4es, built below from the pinned release): the console has OpenGL ES only, and
# gl4es turns the renderer's OpenGL 1 calls into OpenGL ES 2 ones on the context SDL made. The launcher points SDL at
# it (SDL_VIDEO_GL_DRIVER) so that SDL_GL_GetProcAddress, which the renderer asks for every GL function, finds gl4es's
# functions and not the OpenGL ES ones of the context - nothing links to it.
# ARCH=armv7l (not "arm"): only that name turns on the engine's ARM QVM compiler, and the game of OpenArena (its
# game, cgame and ui QVMs) would otherwise run in the interpreter. The 64-bit Pi (ARCH=aarch64) has no QVM compiler in this
# engine, so it interprets them; the PC stick (ARCH=x86) has the x86 one. The programs are named after the ARCH
# (ioquake3.armv7l, ioquake3.aarch64, ioquake3.x86; port.ini binary / binary.<target>).
# Sourced by ci/build.sh with $SRC (patched upstream), $STAGE (the launcher folder's files), $PORT_DIR.
port_build() {
    # BUILD_DIR is the Makefile's own variable for its output folder too (ci/build.sh exports one): name it
    local obj="$BUILD_DIR/obj" arch=armv7l arm=-marm
    case "$TARGET" in
        rpi64) arch=aarch64 arm= ;;
        pcusb) arch=x86 arm= ;;
    esac
    CFLAGS="$CPU_FLAGS $arm" make -C "$SRC" -j "$JOBS" release BUILD_DIR="$obj" \
        PLATFORM=linux ARCH=$arch COMPILE_ARCH=$arch CROSS_COMPILING=1 CC="$CC" \
        USE_INTERNAL_LIBS=1 USE_LOCAL_HEADERS=1 \
        USE_OPENAL=0 USE_CURL=0 USE_VOIP=0 USE_MUMBLE=0 USE_FREETYPE=0 USE_RENDERER_DLOPEN=1 \
        BUILD_CLIENT=1 BUILD_SERVER=0 BUILD_STANDALONE=0 BUILD_GAME_SO=0 BUILD_GAME_QVM=0 \
        BUILD_BASEGAME=0 BUILD_MISSIONPACK=0 BUILD_RENDERER_OPENGL2=0 \
        SDL_CFLAGS="$(pkg-config --cflags sdl2)" SDL_LIBS="$(pkg-config --libs sdl2)"
    local out="$obj/release-linux-$arch"
    cp "$out/ioquake3.$arch" "$out/renderer_opengl1_$arch.so" "$STAGE/"
    "$STRIP" "$STAGE/ioquake3.$arch" "$STAGE/renderer_opengl1_$arch.so"
    check_binary "$STAGE/renderer_opengl1_$arch.so"

    # our start-up helper and the pad's bindings (files/)
    cp "$PORT_DIR/files/psc-pad.sh" "$STAGE/psc-pad.sh"
    mkdir -p "$STAGE/psc"
    cp "$PORT_DIR/files/psc/"*.cfg "$STAGE/psc/"

    # gl4es 1.1.6 (MIT): OpenGL 1.x/2.1 on top of OpenGL ES 2, for a GL context that SDL made (NOX11, NOEGL: it creates no
    # context of its own and loads the console's libGLESv2.so.2 at run time). Fetched against a pinned sha256, shipped
    # next to the program in lib/.
    local g4=gl4es-1.1.6
    fetch "$AB_DEPS_BASE/gl4es/$g4.tar.gz"         dca1d897e492a0cb163a3390f273fbd4cc7ab2367d236d93dc2b321ce108ed5c "$g4.tar.gz"         "https://github.com/ptitSeb/gl4es/archive/refs/tags/v1.1.6.tar.gz"
    mkdir -p "$BUILD_DIR/gl4es"
    tar -xzf "$ROOT/build_data/$g4.tar.gz" -C "$BUILD_DIR/gl4es"
    cmake -S "$BUILD_DIR/gl4es/$g4" -B "$BUILD_DIR/gl4es/build" -DCMAKE_BUILD_TYPE=Release         -DCMAKE_TOOLCHAIN_FILE="$TOOLCHAIN_PLAIN" -DCMAKE_SKIP_RPATH=ON -DCMAKE_C_FLAGS="$CPU_FLAGS"         -DNOX11=ON -DNOEGL=ON -DDEFAULT_ES=2
    make -C "$BUILD_DIR/gl4es/build" -j "$JOBS"
    mkdir -p "$STAGE/lib"
    cp -L "$BUILD_DIR/gl4es/$g4/lib/libGL.so.1" "$STAGE/lib/libGL.so.1"
    "$STRIP" "$STAGE/lib/libGL.so.1"
    check_binary "$STAGE/lib/libGL.so.1"
    cp "$BUILD_DIR/gl4es/$g4/LICENSE" "$SRC/COPYING-gl4es"
}
