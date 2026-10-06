# Freedoom 0.13.0 game data: no compiling. The release archive is fetched (pinned sha256), the two WAD files and the
# licence texts are taken out unmodified. The package is a game-data package (port.ini kind=data, [datapackage]): its folder holds
# freedoom1.wad and freedoom2.wad, which the launcher hands to lzdoom as AB_PKG_FILE (ports/lzdoom/files/psc-pad.sh).
# Sourced by ci/build.sh with $SRC (the data port's notes), $STAGE (the launcher folder's files), $PORT_DIR.
port_build() {
    local ver=freedoom-0.13.0 zip=freedoom-0.13.0.zip
    fetch "https://autobleem.retromenele.pl/mirror/freedoom/$zip" \
        3f9b264f3e3ce503b4fb7f6bdcb1f419d93c7b546f4df3e874dd878db9688f59 "$zip" \
        "https://github.com/freedoom/freedoom/releases/download/v0.13.0/$zip"
    mkdir -p "$BUILD_DIR/zip" "$STAGE"
    unzip -q -o "$ROOT/build_data/$zip" "$ver/freedoom1.wad" "$ver/freedoom2.wad" -d "$BUILD_DIR/zip"
    mv "$BUILD_DIR/zip/$ver/freedoom1.wad" "$BUILD_DIR/zip/$ver/freedoom2.wad" "$STAGE/"
    # the release's own licence and credit texts: mkmod.py copies them from $SRC into the package's licences/
    unzip -q -o "$ROOT/build_data/$zip" "$ver/COPYING.txt" "$ver/CREDITS.txt" "$ver/CREDITS-MUSIC.txt" -d "$BUILD_DIR/zip"
    cp "$BUILD_DIR/zip/$ver/COPYING.txt" "$BUILD_DIR/zip/$ver/CREDITS.txt" "$BUILD_DIR/zip/$ver/CREDITS-MUSIC.txt" "$SRC/"
}
