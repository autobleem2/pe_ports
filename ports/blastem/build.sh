# BlastEm 1.0.0: the Makefile of the upstream with its portable 68000 and Z80 cores (the dynamic recompiler is x86
# only), OpenGL ES 2 through the launcher's SDL2, the bundled zlib. The cores are generated from the .cpu files by the
# upstream's cpu_dsl.py (python3 is in the build image). No GTK (the file chooser is BlastEm's own), no GLEW.
# Sourced by ci/build.sh with $SRC (patched upstream), $STAGE (the launcher folder's files), $PORT_DIR.
port_build() {
    chmod +x "$SRC/cpu_dsl.py"
    if [ "$TARGET" = psc ]; then
        # sdl2.pc is the launcher's SDL2; the console sysroot's glesv2.pc would add -L/usr/lib/arm-linux-gnueabihf, which
        # the linker takes for the host's own library, so a one-line glesv2.pc of ours names just the library
        mkdir -p "$BUILD_DIR/pc"
        printf '%s\n' 'Name: glesv2' 'Description: OpenGL ES 2 (the console sysroot)' 'Version: 2.0' 'Libs: -lGLESv2' \
            > "$BUILD_DIR/pc/glesv2.pc"
        export PKG_CONFIG_LIBDIR="$PSC/sdl2/lib/pkgconfig:$BUILD_DIR/pc"
    fi
    # (the Linux targets: the image's sdl2.pc and glesv2.pc of the target, PKG_CONFIG_LIBDIR from ci/build.sh)
    # OPT is what the Makefile puts into both CFLAGS and LDFLAGS; CPU is not x86, so it builds the portable cores. The
    # recompiler is x86 (and the PC stick is i386): the portable cores are what the console and the Pi run and what was
    # tested, so the stick takes them too - "i686core" is no CPU the Makefile knows, which is how it gets them
    local cpu=armv7 arm=-marm
    case "$TARGET" in
        rpi64) cpu=aarch64 arm= ;;
        pcusb) cpu=i686core arm= ;;
    esac
    make -C "$SRC" -j "$JOBS" blastem CC="$CC" OS=Linux CPU=$cpu USE_GLES=1 \
        OPT="-O2 -flto=$JOBS $CPU_FLAGS $arm -DAB_PSC"
    cp "$SRC/blastem" "$STAGE/blastem"
    "$STRIP" "$STAGE/blastem"

    # what the program reads from its own folder at run time
    cp "$SRC/default.cfg" "$SRC/rom.db" "$SRC/systems.cfg" "$SRC/gamecontrollerdb.txt" "$STAGE/"
    cp -a "$SRC/shaders" "$SRC/images" "$STAGE/"

    # our start-up script and the games folder's note
    cp "$PORT_DIR/files/psc-setup.sh" "$STAGE/psc-setup.sh"
    mkdir -p "$STAGE/psc"
    cp "$PORT_DIR/files/roms-README.txt" "$STAGE/psc/roms-README.txt"
}
