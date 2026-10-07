#!/usr/bin/env bash
# Builds PE ports in the autobleem-build image (ghcr.io/autobleem2/autobleem-build) and packs them:
#
#   ci/build.sh openlara|commanderkeen|openjazz|tyrquake|ioquake3|openarenadata|lzdoom|freedoomdata|dosbox|liero|xargon|blastem    one port
#   ci/build.sh all                                         every port in ports/
#   ci/build.sh --target rpi|rpi64|pcusb <port>|all         the same for the Raspberry Pi 32-bit (rpi), the Raspberry Pi 64-bit (rpi64)
#                                                           or the PC stick (pcusb, i386) (default: --target psc)
#
# For each port the result is, in out/:
#   <id>-<version>.mod                  the PE package (what the Store hands out; the program, its launcher files,
#                                       the allowed shareware data, SOURCE.txt and the licence text); for --target rpi|rpi64|pcusb
#                                       <id>-<version>-<target>.mod ("Platform: RPI armhf" / "RPI64 arm64" / "PCUSB i386",
#                                       the same source archive)
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
# --target psc (the default): the PlayStation Classic, gcc-6 against the console's Debian Stretch sysroot, the launcher's
# SDL2 2.0.18 family shared (it is in /tmp/lib on the console, and ${PROJECT_ERIS_PATH}/lib holds a link to it while a
# mod runs), everything else static or the mod's own.
# --target rpi: the Raspberry Pi 32-bit (Raspberry Pi OS armhf): the image's Debian 12 cross compiler against its armhf
# libraries, the system's SDL2; the PE environment is rc/pe_run.sh of the launcher's Linux package. The game-data
# ports are not rebuilt (their packages are the psc build's).
# --target rpi64: the Raspberry Pi 64-bit (aarch64): the same image's aarch64-linux-gnu cross compiler against its arm64
# libraries (the Debian 12 ones; the Pi's Raspberry Pi OS is newer, the programs need nothing newer than glibc 2.36).
# --target pcusb: the PC stick (Debian 12 i386): i686-linux-gnu-gcc against the :i386 libraries, plain i686 with SSE2
# (-march=i686 -msse2 -mfpmath=sse). Both run on the system's SDL2 like the rpi target and share the Linux patches
# (NNNN-name.linux.patch) and port.ini keys (args.linux ...) of the three Linux targets.
#
# On the build server: docker run --rm -u $(id -u):$(id -g) -v $PWD:/src -w /src \
#                          -e AB_BUILD_IMAGE_DIGEST=<RepoDigest of the image> \
#                          ghcr.io/autobleem2/autobleem-build:develop ci/build.sh all
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD

JOBS="${JOBS:-$(nproc)}"
PSC=${AB_PSC_TOOLCHAIN:-/opt/psc}

# --target psc|rpi|rpi64|pcusb (default psc, or $AB_PE_TARGET): the machine the programs are built for. The data ports are
# shared by all of them and are not rebuilt for the others.
TARGET=${AB_PE_TARGET:-psc}
args=()
while [ $# -gt 0 ]; do
    case "$1" in
        --target) TARGET=${2:?--target needs psc, rpi, rpi64 or pcusb}; shift 2 ;;
        --target=*) TARGET=${1#--target=}; shift ;;
        *) args+=("$1"); shift ;;
    esac
done
set -- "${args[@]+"${args[@]}"}"
case "$TARGET" in psc | rpi | rpi64 | pcusb) ;; *) echo "unknown target: $TARGET (psc, rpi, rpi64 or pcusb)" >&2; exit 2 ;; esac
export JOBS PSC ROOT TARGET
# the checkout belongs to another user than the container's (git refuses "dubious ownership" otherwise)
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0='*'
# the PATH a build tool that runs on the build machine itself (lzdoom's and OpenAL's generators) must see
NATIVE_PATH=$PATH
if [ "$TARGET" = psc ]; then
    export CC="$PSC/bin/armv8-sony-linux-gnueabihf-gcc" CXX="$PSC/bin/armv8-sony-linux-gnueabihf-g++"
    export STRIP="$PSC/bin/armv8-sony-linux-gnueabihf-strip" AR="$PSC/bin/armv8-sony-linux-gnueabihf-ar"
    # what the app_* ports use for the console, plus nothing else
    export CPU_FLAGS="-mfloat-abi=hard -march=armv8-a -mfpu=neon-vfpv4"
    export PKG_CONFIG_LIBDIR="$PSC/sdl2/lib/pkgconfig"
    export SDL_PREFIX="$PSC/sdl2"
    # the toolchain files: the port's own (CMake ports), and the plain one gl4es is built with
    export TOOLCHAIN_PLAIN="$PSC/toolchain.cmake"
    # the static zlib a port links in
    export ZLIB_A="$PSC/sysroot/usr/lib/arm-linux-gnueabihf/libz.a" ZLIB_INC="$PSC/sysroot/usr/include"
    # sdl2-config of the console's SDL2 family first on the PATH (a Makefile that asks for it gets the console's flags)
    export PATH="$PSC/sdl2/bin:$PATH"
else
    # a Linux machine with a normal distribution (Debian 12 libraries): the image's cross compiler against its multiarch
    # libraries (SDL2 2.26 family, GLES2, EGL, ALSA, zlib); SDL2 is the system's there, nothing of it ships.
    #   rpi    the Raspberry Pi 32-bit (Raspberry Pi OS armhf)
    #   rpi64  the Raspberry Pi 64-bit (aarch64)
    #   pcusb  the PC stick (Debian 12 i386; plain i686 plus SSE2, which every PC of the last twenty years has)
    case "$TARGET" in
        rpi)
            export MULTIARCH=arm-linux-gnueabihf TRIPLET=arm-linux-gnueabihf
            export CPU_FLAGS="-mfloat-abi=hard -march=armv7-a -mfpu=neon-vfpv4" ;;
        rpi64)
            export MULTIARCH=aarch64-linux-gnu TRIPLET=aarch64-linux-gnu
            export CPU_FLAGS="-march=armv8-a" ;;
        pcusb)
            export MULTIARCH=i386-linux-gnu TRIPLET=i686-linux-gnu
            export CPU_FLAGS="-march=i686 -msse2 -mfpmath=sse -mtune=generic -D_FILE_OFFSET_BITS=64" ;;
    esac
    export CC=$TRIPLET-gcc CXX=$TRIPLET-g++ STRIP=$TRIPLET-strip AR=$TRIPLET-ar
    export PKG_CONFIG_LIBDIR=/usr/lib/$MULTIARCH/pkgconfig:/usr/share/pkgconfig
    export TOOLCHAIN_PLAIN="$ROOT/ci/$TARGET.cmake"
    export ZLIB_A=/usr/lib/$MULTIARCH/libz.a ZLIB_INC=/usr/include
    # a Makefile that asks for `sdl2-config` gets the target's SDL2 flags (the host's own script would name x86_64 paths)
    mkdir -p "$ROOT/build/shim"
    printf '%s\n' '#!/bin/sh' 'exec pkg-config sdl2 "$@"' > "$ROOT/build/shim/sdl2-config"
    chmod +x "$ROOT/build/shim/sdl2-config"
    export PATH="$ROOT/build/shim:$PATH"
fi
export NATIVE_PATH

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

# check_binary <file>...: it must be an ELF of the target's machine (ARM hard-float for the console and the 32-bit Pi, aarch64
# for the 64-bit Pi, Intel 80386 for the PC stick) and need nothing but the system's own libraries, the SDL2 family or what the
# mod brings (a mod's libraries sit next to its program)
check_binary() {
    local f
    for f in "$@"; do
        local lib needed readelf
        case "$TARGET" in
            psc | rpi) file "$f" | grep -q 'ELF 32-bit LSB.*ARM' ;;
            rpi64) file "$f" | grep -q 'ELF 64-bit LSB.*ARM aarch64' ;;
            pcusb) file "$f" | grep -q 'ELF 32-bit LSB.*Intel 80386' ;;
        esac
        if [ "$TARGET" = psc ]; then
            bash /opt/ab/tools/check_psc_binary.sh "$f" "$PSC"
            readelf="$PSC/bin/armv8-sony-linux-gnueabihf-readelf"
        else
            # the Linux machines: nothing newer than the glibc of the image's Debian 12 (Raspberry Pi OS bookworm and later,
            # the PC stick's Debian 12); the 32-bit Pi's binaries are hard float
            readelf=$TRIPLET-readelf
            if [ "$TARGET" = rpi ]; then
                "$readelf" -A "$f" | grep -q 'Tag_ABI_VFP_args: VFP registers'
            fi
            if "$readelf" --dyn-syms -W "$f" | grep -oE 'GLIBC_2\.[0-9]+' | sed 's/GLIBC_2\.//' | awk '$1 > 36 { bad = 1 } END { exit !bad }'; then
                echo "    ERROR: $(basename "$f") needs a glibc newer than 2.36" >&2
                return 1
            fi
        fi
        needed=$("$readelf" -d "$f" | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p')
        echo "    needs: $(echo $needed)"
        for lib in $needed; do
            if echo "$lib" | grep -qE "$PE_ALLOWED_LIBS"; then continue; fi
            if [ -f "$(dirname "$f")/$lib" ]; then continue; fi
            echo "    ERROR: $(basename "$f") needs $lib, which is neither the system's, SDL2 nor shipped with the mod" >&2
            return 1
        done
    done
    echo "    every library is the system's, SDL2 or the mod's own"
}
# the console's own system (glibc family, the compiler runtime, ALSA, udev, wayland, EGL/GLES2) and the launcher's
# SDL2 family; libudev and libxkbcommon are in the console's firmware (the 2020 mods needed them too). The Pi takes the
# same list: they are its own system libraries too (the system's SDL2 depends on them)
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

# port_value <port.ini> <key>: a [launcher] value for this target - `<key>.<target>`, else `<key>.linux` (every target but the
# console), else `<key>` (the order tools/mkmod.py's launcher_value reads them in)
port_value() {
    local k v
    for k in "$2.$TARGET" "$2.linux" "$2"; do
        [ "$k" != "$2.linux" ] || [ "$TARGET" != psc ] || continue
        v=$(sed -n "s/^$k=//p" "$1" | head -n 1 | tr -d '\r')
        if [ -n "$v" ]; then printf '%s' "$v"; return; fi
    done
}

build_port() { # build_port <id>
    local id="$1" dir="$ROOT/ports/$1"
    [ -f "$dir/port.ini" ] || { echo "no such port: $id" >&2; exit 2; }
    banner "$id ($TARGET)"
    # game data is the same on every machine: the packages the psc build makes are the Pi's too, not rebuilt
    if [ "$TARGET" != psc ] && grep -qE '^\[(package|datapackage)\]' "$dir/port.ini"; then
        echo "    game data: shared with the psc build, nothing to build for $TARGET"
        return
    fi
    if grep -q '^\[package\]' "$dir/port.ini"; then
        build_package "$id" "$dir"
        return
    fi
    [ -n "$(ls -A "$dir/upstream" 2>/dev/null)" ] || { echo "ports/$id/upstream is empty: git submodule update --init --recursive" >&2; exit 1; }

    export PORT_DIR=$dir BUILD_DIR=$ROOT/build/$id
    export SRC=$BUILD_DIR/src STAGE=$BUILD_DIR/stage
    # the CMake toolchain file of the port: its own psc.cmake on the console (it names the console's SDL2), the shared one on the Pi
    if [ "$TARGET" = psc ]; then export TOOLCHAIN_CMAKE=$dir/psc.cmake; else export TOOLCHAIN_CMAKE=$TOOLCHAIN_PLAIN; fi
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
        # NNNN-name.psc.patch (the console), .linux.patch (rpi, rpi64 and pcusb) and .rpi.patch / .rpi64.patch / .pcusb.patch
        # (one of them) belong to some targets; the rest to all (applied in name order)
        case "$p" in
            *.psc.patch) [ "$TARGET" = psc ] || continue ;;
            *.linux.patch) [ "$TARGET" != psc ] || continue ;;
            *.rpi.patch) [ "$TARGET" = rpi ] || continue ;;
            *.rpi64.patch) [ "$TARGET" = rpi64 ] || continue ;;
            *.pcusb.patch) [ "$TARGET" = pcusb ] || continue ;;
        esac
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
        check_binary "$STAGE/$(port_value "$dir/port.ini" binary)"
    fi

    mkdir -p out
    python3 tools/mkmod.py "$id" --target "$TARGET" --stage "$STAGE" --src "$SRC" --out out
}

[ $# -gt 0 ] || { echo "usage: $0 [--target psc|rpi|rpi64|pcusb] <port>|all" >&2; exit 2; }
for target in "$@"; do
    case "$target" in
        all) for d in ports/*/; do build_port "$(basename "$d")"; done ;;
        *) build_port "$target" ;;
    esac
done
