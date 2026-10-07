# DOSBox 0.74 (the 2020 SDL2 tree): compiled from the sources configure built for the console (files/sources.txt,
# files/config.h, files/Makefile.psc - ports/dosbox/regen.sh makes the first two again), then the launcher folder's files.
# The same sources, config.h and flags serve the Raspberry Pi 32-bit (--target rpi: the image's cross compiler, the armhf SDL2).
# The 64-bit Pi and the PC stick take the same sources with the config.h that configure makes for their CPU (below).
# Sourced by ci/build.sh with $SRC (the upstream, patched), $STAGE (the launcher folder's files), $PORT_DIR.
port_build() {
    cp "$PORT_DIR/files/config.h" "$PORT_DIR/files/Makefile.psc" "$PORT_DIR/files/sources.txt" "$SRC/"
    # the dialect of the console's gcc 6 (gnu++14): the tree has dynamic exception specifications, which the Linux
    # targets' image compiler (gcc 12, gnu++17 by default) refuses
    local std= flags
    [ "$TARGET" = psc ] || std="-std=gnu++14"
    case "$TARGET" in
        psc | rpi)
            # the flags of the 2020 package (the tested ones); the dynamic recompiler is in config.h (C_DYNREC)
            flags="-O3 -marm -mtune=cortex-a7 -mfpu=neon-vfpv4 -mfloat-abi=hard" ;;
        rpi64)
            # DOSBox's recompiler (dynrec) has no aarch64 back end: the plain interpreting core, and what configure says
            # for a 64-bit CPU with no recompiler (C_TARGETCPU UNKNOWN, 8-byte pointers and longs)
            sed -i -e 's/^#define C_TARGETCPU .*/#define C_TARGETCPU UNKNOWN/' -e '/^#define C_DYNREC 1$/d' \
                -e 's/^#define SIZEOF_INT_P 4$/#define SIZEOF_INT_P 8/' -e 's/^#define SIZEOF_UNSIGNED_LONG 4$/#define SIZEOF_UNSIGNED_LONG 8/' "$SRC/config.h"
            flags="-O3 -march=armv8-a" ;;
        pcusb)
            # what configure says for a 32-bit x86 with gcc: the x86 dynamic core and FPU, inlined core memory functions,
            # unaligned access; no PIE (the dynamic core's generated code and its own register use do not mix with it)
            sed -i -e 's/^#define C_TARGETCPU .*/#define C_TARGETCPU X86/' -e '/^#define C_DYNREC 1$/d' \
                -e 's|^/\* #undef C_DYNAMIC_X86 \*/$|#define C_DYNAMIC_X86 1|' -e 's|^/\* #undef C_FPU_X86 \*/$|#define C_FPU_X86 1|' \
                -e 's|^/\* #undef C_CORE_INLINE \*/$|#define C_CORE_INLINE 1|' -e 's|^/\* #undef C_UNALIGNED_MEMORY \*/$|#define C_UNALIGNED_MEMORY 1|' "$SRC/config.h"
            flags="-O3 $CPU_FLAGS -fno-pie -no-pie -fomit-frame-pointer" ;;
    esac
    make -C "$SRC" -f Makefile.psc -j "$JOBS" CXX="$CXX" CXXFLAGS="$flags $std"
    cp "$SRC/dosbox" "$STAGE/dosbox"
    "$STRIP" "$STAGE/dosbox"
    # the start script (it builds the run's conf from the chosen game), the base settings and the default pad map
    cp "$PORT_DIR/files/psc-dosbox.sh" "$PORT_DIR/files/dosbox.conf" "$PORT_DIR/files/mapper.txt" "$STAGE/"
}
