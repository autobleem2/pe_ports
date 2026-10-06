#!/usr/bin/env bash
# Proves patch 0002's key numbering against the SDL headers of the build image: the patched common/in_sdl.c is
# compiled with a fake pad (every button and both triggers pressed) and every key that reaches Key_Event must be
# one of keys.h's (K_GCA..K_LAST-1). Run it inside the image from the repository root:
#   docker run --rm -v $PWD:/src -w /src ghcr.io/autobleem2/autobleem-build:develop ports/tyrquake/tests/run.sh
set -euo pipefail
cd "$(dirname "$0")/../../.."
PORT=$PWD/ports/tyrquake
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
(cd "$PORT/upstream" && tar --exclude=.git -cf - .) | tar -x -C "$W"
for p in "$PORT"/patches/*.patch; do patch -s -p1 -d "$W" < "$p"; done
cp "$PORT/tests/gc_keys.c" "$W/common/gc_keys.c"
SDLINC=${AB_PSC_TOOLCHAIN:-/opt/psc}/sdl2/include/SDL2
# the engine's other symbols are never called by IN_Commands: left unresolved on purpose
gcc -g -O0 -w -fno-pie -no-pie -DNQ_HACK -I"$W/NQ" -I"$W/common" -I"$W/include" -I"$SDLINC" \
    -Wl,--unresolved-symbols=ignore-all -o "$W/gc_keys" "$W/common/gc_keys.c"
"$W/gc_keys"
