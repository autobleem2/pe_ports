# OpenArena 0.8.8 game data: no compiling. The release archive is fetched (pinned sha256), eight of its pk3 files and its
# licence texts are taken out unmodified. The package is a data package (port.ini kind=data): its launcher folder holds
# baseoa/, which the ioquake3 package finds as fs_basepath (ports/ioquake3/files/psc-pad.sh).
# Sourced by ci/build.sh with $SRC (the data port's notes), $STAGE (the launcher folder's files), $PORT_DIR.
port_build() {
    local ver=openarena-0.8.8 zip=openarena-0.8.8.zip pak
    fetch "$AB_DEPS_BASE/openarena/$zip" \
        5a8faf7f5b51f351b0a1618c06b6b98a5f1a6758f1d39818de2c87df2a0bac4a "$zip" \
        "http://download.tuxfamily.org/openarena/rel/088/$zip" \
        "https://downloads.sourceforge.net/project/oarena/$zip"
    mkdir -p "$BUILD_DIR/zip" "$STAGE/baseoa"
    for pak in pak0 pak1-maps pak2-players pak4-textures pak5-TA pak6-misc pak6-patch085 pak6-patch088; do
        unzip -q -o "$ROOT/build_data/$zip" "$ver/baseoa/$pak.pk3" -d "$BUILD_DIR/zip"
        mv "$BUILD_DIR/zip/$ver/baseoa/$pak.pk3" "$STAGE/baseoa/$pak.pk3"
    done
    # the release's own licence and credit texts: mkmod.py copies them from $SRC into the package's licences/
    unzip -q -o "$ROOT/build_data/$zip" "$ver/COPYING" "$ver/CREDITS" "$ver/README" "$ver/readme_088.txt" -d "$BUILD_DIR/zip"
    cp "$BUILD_DIR/zip/$ver/COPYING" "$BUILD_DIR/zip/$ver/CREDITS" "$BUILD_DIR/zip/$ver/README" \
        "$BUILD_DIR/zip/$ver/readme_088.txt" "$SRC/"
    cp "$PORT_DIR/files/openarenadata.sh" "$STAGE/openarenadata.sh"
}
