# Xargon v3.0 (the registered trilogy, freeware since 2008): the archive RGB Classic Games hosts
# (https://classicdosgames.com/), its files laid byte for byte into XARGON/ of the package, with the pad map beside
# it and the freeware notice. Sourced by ci/build.sh with $STAGE (the package's root) and $PORT_DIR; mkmod.py
# writes package.ini and packs the zip.
port_build() {
    key() { sed -n "s/^$1=//p" "$PORT_DIR/port.ini" | head -n 1 | tr -d '\r'; }
    local file sha
    file=$(key archive_file)
    sha=$(key archive_sha256)
    # our site's mirror first (the same bytes, once published), the hosting page's file as the fallback
    fetch "$AB_DEPS_BASE/xargon/$file" "$sha" "$file" "$(key source_url)"
    # the archive's one folder (Xargon/) becomes XARGON/ - the folder's name is ours, the files are the archive's
    mkdir -p "$STAGE/licences" "$BUILD_DIR/unpack"
    unzip -q "$ROOT/build_data/$file" -d "$BUILD_DIR/unpack"
    mv "$BUILD_DIR/unpack/Xargon" "$STAGE/XARGON"
    cp "$PORT_DIR/files/Xargon-freeware.txt" "$STAGE/licences/Xargon-freeware.txt"
    cp "$PORT_DIR/files/mapper.txt" "$STAGE/mapper.txt"
    # Xargon asks for its sound and its game controller (Keyboard or Joystick) once per episode and saves the answers in
    # CONFIG.XR1/2/3; DOSBox's joystick makes it ask, and the pad cannot answer a Joystick calibration. These are the
    # files the game itself wrote when answered "digital sound yes, music yes, Keyboard" (the pad map turns the pad into
    # keys): the question never appears, only "Press ENTER if this is correct" (Triangle is Enter)
    for n in 1 2 3; do cp "$PORT_DIR/files/CONFIG.XR$n" "$STAGE/XARGON/CONFIG.XR$n"; done
}
