# OpenJazz (the 2020 SDL2 tree): upstream's Makefile.psc with the console's compiler and flags.
# Sourced by ci/build.sh with $SRC (the upstream, patched), $STAGE (the launcher folder's files), $PORT_DIR.
port_build() {
    # Makefile.psc adds -DUSE_SOCKETS, sdl2-config's flags and -lm to the CXXFLAGS of the environment
    CXXFLAGS="$PSC_FLAGS -O3 -DAB_PSC" make -C "$SRC" -f Makefile.psc -j "$JOBS" CXX="$CXX" OpenJazz
    cp "$SRC/OpenJazz" "$STAGE/OpenJazz"
    "$STRIP" "$STAGE/OpenJazz"
    # the menu logo blob upstream ships next to the program
    cp "$SRC/openjazz.000" "$STAGE/"
    cp -a "$PORT_DIR/data/." "$STAGE/"
}
