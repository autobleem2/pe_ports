#!/usr/bin/env bash
# Builds PE ports in the autobleem-build image (ghcr.io/autobleem2/autobleem-build) and packs them:
#
#   ci/build.sh openlara|commanderkeen|openjazz|tyrquake|ioquake3|openarenadata|lzdoom|freedoomdata|dosbox|liero|xargon|blastem    one port
#   ci/build.sh all                                         every port in ports/
#
# For each port the result is, in out/:
#   <id>-<version>.mod                  the PE package (what the Store hands out; the program, its launcher files,
#                                       the allowed shareware data, SOURCE.txt and the licence text)
#   <id>-<version>-source.tar.gz        the corresponding source (never part of the .mod): the pinned upstream and
#                                       its submodules, our patches, these build scripts and the build image digest
#
# A data port (port.ini has a [package] section: liero, xargon) has no program and no upstream: its build.sh fetches
# the game's archive against a pinned sha256 and lays the package's files into $STAGE, and mkmod.py packs the package
# zip for the stick's Packages/ folder (packages spec, 2.3): out/<id>-<version>.zip, no source archive.
#
# A port is a folder ports/<id>/ (README.md "Layout"). Its upstream is a pinned submodule, never edited: each build
# copies it into build/<id>/src and applies patches/*.patch there. Its build.sh defines port_build, which compiles
# the program and lays the launcher folder's files into $STAGE.
#
# The target is the PlayStation Classic only (the PE environment exists nowhere else): gcc-6 against the console's
# Debian Stretch sysroot, the launcher's SDL2 2.0.18 family shared (it is in /tmp/lib on the console, and
# ${PROJECT_ERIS_PATH}/lib holds a link to it while a mod runs), everything else static or the mod's own.
#
# On the build server: docker run --rm -u $(id -u):$(id -g) -v $PWD:/src -w /src \
#                          -e AB_BUILD_IMAGE_DIGEST=<RepoDigest of the image> \
#                          ghcr.io/autobleem2/autobleem-build:develop ci/build.sh all
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD

JOBS="${JOBS:-$(nproc)}"
PSC=${AB_PSC_TOOLCHAIN:-/opt/psc}
export JOBS PSC ROOT
# the checkout belongs to another user than the container's (git refuses "dubious ownership" otherwise)
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0='*'
export CC="$PSC/bin/armv8-sony-linux-gnueabihf-gcc" CXX="$PSC/bin/armv8-sony-linux-gnueabihf-g++"
export STRIP="$PSC/bin/armv8-sony-linux-gnueabihf-strip" AR="$PSC/bin/armv8-sony-linux-gnueabihf-ar"
# what the app_* ports use for the console, plus nothing else
export PSC_FLAGS="-mfloat-abi=hard -march=armv8-a -mfpu=neon-vfpv4"
export PKG_CONFIG_LIBDIR="$PSC/sdl2/lib/pkgconfig"
export SDL_PREFIX="$PSC/sdl2"

# sdl2-config of the console's SDL2 family first on the PATH (a Makefile that asks for it gets the console's flags)
export PATH="$PSC/sdl2/bin:$PATH"

banner() { printf '\n==== %s ====\n' "$*"; }

# fetch <url> <sha256> <file> [<fallback url>...]: a build dependency that is not in git, into build_data/ (kept
# between builds), checked against the pinned sha256. The urls are tried in turn; a download that does not match the
# sha256 counts as a failed one, so a wrong or half-uploaded mirror file falls through to the next url.
fetch() {
    local sha="$2" file="$ROOT/build_data/$3" url
    mkdir -p "$ROOT/build_data"
    if [ ! -f "$file" ] || ! echo "$sha  $file" | sha256sum -c --status; then
        for url in "$1" "${@:4}"; do
            echo "fetch: $url"
            rm -f "$file.part"
            if curl -fL --retry 3 -o "$file.part" "$url" && echo "$sha  $file.part" | sha256sum -c --status; then
                mv "$file.part" "$file"
                break
            fi
            rm -f "$file.part"
            echo "fetch: $url failed or does not match the pinned sha256" >&2
        done
    fi
    echo "$sha  $file" | sha256sum -c
}
export -f fetch

# build dependencies that are not in git are mirrored on our own site (deps/<name>/, published with
# tools/repo_publish.sh deps of autobleem-repo) and fetched from there first, the upstream address being the fallback
export AB_DEPS_BASE="${AB_DEPS_BASE:-https://autobleem.retromenele.pl/deps}"

# check_binary <file>...: it must be an ARM hard-float ELF the console can load, and need nothing but the console's
# own libraries, the SDL2 family or what the mod brings (a mod's libraries sit next to its program)
check_binary() {
    local f
    for f in "$@"; do
        file "$f" | grep -q 'ELF 32-bit LSB.*ARM'
        bash /opt/ab/tools/check_psc_binary.sh "$f" "$PSC"
        local lib needed
        needed=$("$PSC/bin/armv8-sony-linux-gnueabihf-readelf" -d "$f" | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p')
        echo "    needs: $(echo $needed)"
        for lib in $needed; do
            if echo "$lib" | grep -qE "$PE_ALLOWED_LIBS"; then continue; fi
            if [ -f "$(dirname "$f")/$lib" ]; then continue; fi
            echo "    ERROR: $(basename "$f") needs $lib, which is neither the console's, SDL2 nor shipped with the mod" >&2
            return 1
        done
    done
    echo "    every library is the console's, SDL2 or the mod's own"
}
# the console's own system (glibc family, the compiler runtime, ALSA, udev, wayland, EGL/GLES2) and the launcher's
# SDL2 family; libudev and libxkbcommon are in the console's firmware (the 2020 mods needed them too)
export PE_ALLOWED_LIBS='^(libc|libm|libdl|libpthread|librt|libresolv|libutil|ld-linux[-a-z0-9_.]*|libgcc_s|libstdc\+\+|libSDL2-2\.0|libSDL2_image-2\.0|libSDL2_mixer-2\.0|libSDL2_ttf-2\.0|libasound|libudev|libxkbcommon|libEGL|libGLESv2|libGL|libwayland-[a-z]+|libdrm)\.so'

# a data port: the package zip (no program to check, nothing to compile, no source archive)
build_package() { # build_package <id> <port dir>
    export PORT_DIR=$2 BUILD_DIR=$ROOT/build/$1
    export STAGE=$BUILD_DIR/stage
    rm -rf "$BUILD_DIR"
    mkdir -p "$STAGE" out
    unset -f port_build 2>/dev/null || true
    # shellcheck disable=SC1091
    . "$2/build.sh"
    port_build
    python3 tools/mkmod.py "$1" --stage "$STAGE" --out out
}

build_port() { # build_port <id>
    local id="$1" dir="$ROOT/ports/$1"
    [ -f "$dir/port.ini" ] || { echo "no such port: $id" >&2; exit 2; }
    banner "$id"
    if grep -q '^\[package\]' "$dir/port.ini"; then
        build_package "$id" "$dir"
        return
    fi
    [ -n "$(ls -A "$dir/upstream" 2>/dev/null)" ] || { echo "ports/$id/upstream is empty: git submodule update --init --recursive" >&2; exit 1; }

    export PORT_DIR=$dir BUILD_DIR=$ROOT/build/$id
    export SRC=$BUILD_DIR/src STAGE=$BUILD_DIR/stage
    rm -rf "$BUILD_DIR"
    mkdir -p "$SRC" "$STAGE"
    # the pinned upstream as it is in git (not what a checkout's line-ending or filter settings made of it); the
    # source archive of a release (no .git in it) is built from the plain tree. export_exclude= names files of
    # the upstream that are not source of the program (README.md, "port.ini")
    local excl=() excl_dot=() e
    for e in $(sed -n 's/^export_exclude=//p' "$dir/port.ini" | head -n 1 | tr -d '\r'); do
        excl+=(--exclude="$e")
        excl_dot+=(--exclude="./$e")
    done
    if [ -e "$dir/upstream/.git" ]; then
        git -C "$dir/upstream" archive --format=tar HEAD | tar -x -C "$SRC" --anchored "${excl[@]}"
    else
        (cd "$dir/upstream" && tar -c --anchored "${excl_dot[@]}" .) | tar -x -C "$SRC"
    fi
    local p
    for p in "$dir"/patches/*.patch; do
        [ -f "$p" ] || continue
        echo "patch: ${p#"$ROOT"/}"
        patch -d "$SRC" -p1 --no-backup-if-mismatch < "$p"
    done

    unset -f port_build 2>/dev/null || true
    # shellcheck disable=SC1091
    . "$dir/build.sh"
    port_build
    # a data package (kind=data in port.ini) carries game files and a small notice script, no program to check
    if [ "$(sed -n 's/^kind=//p' "$dir/port.ini" | head -n 1 | tr -d '\r')" = data ]; then
        echo "    data package: no binary to check"
    else
        check_binary "$STAGE/$(sed -n 's/^binary=//p' "$dir/port.ini" | head -n 1 | tr -d '\r')"
    fi

    mkdir -p out
    python3 tools/mkmod.py "$id" --stage "$STAGE" --src "$SRC" --out out
}

[ $# -gt 0 ] || { echo "usage: $0 <port>|all" >&2; exit 2; }
for target in "$@"; do
    case "$target" in
        all) for d in ports/*/; do build_port "$(basename "$d")"; done ;;
        *) build_port "$target" ;;
    esac
done
