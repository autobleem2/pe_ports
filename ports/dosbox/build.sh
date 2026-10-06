# DOSBox 0.74 (the 2020 SDL2 tree): compiled from the sources configure built for the console (files/sources.txt,
# files/config.h, files/Makefile.psc - ports/dosbox/regen.sh makes the first two again), then the launcher folder's files.
# Sourced by ci/build.sh with $SRC (the upstream, patched), $STAGE (the launcher folder's files), $PORT_DIR.
port_build() {
    cp "$PORT_DIR/files/config.h" "$PORT_DIR/files/Makefile.psc" "$PORT_DIR/files/sources.txt" "$SRC/"
    # the flags of the 2020 package (the tested ones); the dynamic recompiler is in config.h (C_DYNREC)
    make -C "$SRC" -f Makefile.psc -j "$JOBS" CXX="$CXX" CXXFLAGS="-O3 -marm -mtune=cortex-a7 -mfpu=neon-vfpv4 -mfloat-abi=hard"
    cp "$SRC/dosbox" "$STAGE/dosbox"
    "$STRIP" "$STAGE/dosbox"
    # the start script (it builds the run's conf from the chosen game), the base settings and the default pad map
    cp "$PORT_DIR/files/psc-dosbox.sh" "$PORT_DIR/files/dosbox.conf" "$PORT_DIR/files/mapper.txt" "$STAGE/"
}
