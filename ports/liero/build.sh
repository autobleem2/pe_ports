# Liero 1.33: the author's own archive (https://www.liero.be/), laid byte for byte into LIERO/ of the package, with the
# pad map beside it (outside the game's files: the licence forbids changes to them) and the licence texts.
# Sourced by ci/build.sh with $STAGE (the package's root) and $PORT_DIR; mkmod.py writes package.ini and packs the zip.
port_build() {
    local key
    key() { sed -n "s/^$1=//p" "$PORT_DIR/port.ini" | head -n 1 | tr -d '\r'; }
    local file sha
    file=$(key archive_file)
    sha=$(key archive_sha256)
    # our site's mirror first (the same bytes, once published), the author's page as the fallback
    fetch "$AB_DEPS_BASE/liero/$file" "$sha" "$file" "$(key source_url)"
    mkdir -p "$STAGE/LIERO" "$STAGE/licences"
    unzip -q "$ROOT/build_data/$file" -d "$STAGE/LIERO"
    cp "$STAGE/LIERO/LIEROENG.TXT" "$STAGE/licences/Liero-1.33-licence.txt"
    cp "$STAGE/LIERO/LICENSE.TXT" "$STAGE/licences/Liero-LICENSE.txt"
    cp "$PORT_DIR/files/mapper.txt" "$STAGE/mapper.txt"
}
