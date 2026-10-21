#!/usr/bin/env bash
# Builds PE ports in the autobleem-build image (ghcr.io/autobleem2/autobleem-build) and packs them:
#
#   ci/build.sh openlara|commanderkeen|openjazz|tyrquake|ioquake3|openarenadata|lzdoom|freedoomdata|dosbox|liero|xargon|blastem    one port
#   ci/build.sh all                                         every port in ports/
#   ci/build.sh --target rpi <port>|all                     the same for the Raspberry Pi 32-bit (default: --target psc)
#   ci/build.sh --target rpi64 <port>|all                   the same for the Raspberry Pi 64-bit
#   ci/build.sh --target pcusb <port>|all                   the same for the PC stick (PC-USB: 32-bit x86, i386, no SSE2)
#
# For each port the result is, in out/:
#   <id>-<version>.mod                  the PE package (what the Store hands out; the program, its launcher files,
#                                       the allowed shareware data, SOURCE.txt and the licence text); for --target rpi
#                                       <id>-<version>-rpi.mod ("Platform: RPI armhf", the same source archive), for
#                                       --target rpi64 <id>-<version>-rpi64.mod ("Platform: RPI arm64")
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
# --target rpi64: the Raspberry Pi 64-bit (Raspberry Pi OS arm64): the same with the image's aarch64 cross compiler against
# its Debian 12 arm64 libraries.
# --target pcusb: the PC stick (PC-USB, a Linux on a USB stick for old PCs): 32-bit x86 (i386, ELF Intel 80386), no SSE or
# SSE2 (-march=i686 -mno-sse -mno-sse2, x87 floating point: the machines it is for include Pentium III and Athlon XP class
# CPUs), against the Debian 12 i386 libraries of the image, the system's SDL2.
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
# shared by all and are not rebuilt for rpi, rpi64 or pcusb.
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
    export ARM_FLAGS="-mfloat-abi=hard -march=armv8-a -mfpu=neon-vfpv4"
    export PKG_CONFIG_LIBDIR="$PSC/sdl2/lib/pkgconfig"
    export SDL_PREFIX="$PSC/sdl2"
    # the toolchain files: the port's own (CMake ports), and the plain one gl4es is built with
    export TOOLCHAIN_PLAIN="$PSC/toolchain.cmake"
    # the static zlib a port links in
    export ZLIB_A="$PSC/sysroot/usr/lib/arm-linux-gnueabihf/libz.a" ZLIB_INC="$PSC/sysroot/usr/include"
    # sdl2-config of the console's SDL2 family first on the PATH (a Makefile that asks for it gets the console's flags)
    export PATH="$PSC/sdl2/bin:$PATH"
elif [ "$TARGET" = pcusb ]; then
    # the PC stick (PC-USB, Debian 12 i386 libraries): the image's own gcc in 32-bit mode (-m32) against its i386 multiarch
    # libraries (SDL2 2.26 family, GLES2, EGL, ALSA, zlib); SDL2 is the system's on the stick, nothing of it ships.
    # The CPU is a 32-bit x86 without SSE and SSE2 (i686 instruction set, x87 floating point): ARM_FLAGS, the name the
    # ports' recipes use for "the target's CPU switches", holds them. The build tools (strip, ar, readelf, objdump) are the
    # image's own: they read i386 ELF files too. A Makefile that asks for CC gets a one-line wrapper script (CC may not
    # hold a word with spaces: some recipes quote it).
    PE_TRIPLE=i386-linux-gnu
    export ARM_FLAGS="-m32 -march=i686 -mtune=generic -mno-sse -mno-sse2 -mfpmath=387"
    export TOOLCHAIN_PLAIN="$ROOT/ci/pcusb.cmake"
    export PE_TRIPLE
    mkdir -p "$ROOT/build/shim"
    # the image's 32-bit x86 cross compiler when it has one (the plain gcc -m32 needs the 32-bit libgcc of gcc-multilib), looking
    # for the i386 multiarch libraries too; otherwise gcc -m32
    if command -v i686-linux-gnu-gcc > /dev/null 2>&1; then
        pc_cc="i686-linux-gnu-gcc -L/usr/lib/$PE_TRIPLE -Wl,-rpath-link,/usr/lib/$PE_TRIPLE"
        pc_cxx="i686-linux-gnu-g++ -L/usr/lib/$PE_TRIPLE -Wl,-rpath-link,/usr/lib/$PE_TRIPLE"
    else
        pc_cc="gcc -m32"
        pc_cxx="g++ -m32"
    fi
    echo "pcusb compiler: $pc_cc"
    ls -d /usr/i686-linux-gnu /usr/lib/gcc-cross/i686-linux-gnu/* /usr/lib/gcc/x86_64-linux-gnu/*/32 /usr/lib/$PE_TRIPLE /usr/include/$PE_TRIPLE 2>&1 | sed 's/^/    /' || true
    printf '%s\n' '#!/bin/sh' "exec $pc_cc \"\$@\"" > "$ROOT/build/shim/i386-gcc"
    printf '%s\n' '#!/bin/sh' "exec $pc_cxx \"\$@\"" > "$ROOT/build/shim/i386-g++"
    printf '%s\n' '#!/bin/sh' 'exec pkg-config sdl2 "$@"' > "$ROOT/build/shim/sdl2-config"
    chmod +x "$ROOT/build/shim/i386-gcc" "$ROOT/build/shim/i386-g++" "$ROOT/build/shim/sdl2-config"
    export PATH="$ROOT/build/shim:$PATH"
    export CC=i386-gcc CXX=i386-g++ STRIP=strip AR=ar
    export PKG_CONFIG_LIBDIR=/usr/lib/$PE_TRIPLE/pkgconfig:/usr/share/pkgconfig
    export ZLIB_A=/usr/lib/$PE_TRIPLE/libz.a ZLIB_INC=/usr/include
else
    # the Raspberry Pi (Raspberry Pi OS, Debian 12 libraries): the image's cross compiler against its multiarch libraries
    # (SDL2 2.26 family, GLES2, EGL, ALSA, zlib); SDL2 is the system's on the Pi, nothing of it ships. rpi is armhf (32-bit),
    # rpi64 is arm64 (aarch64: hard float and NEON are part of the architecture, so no float-ABI or FPU switch)
    if [ "$TARGET" = rpi64 ]; then
        PE_TRIPLE=aarch64-linux-gnu
        export ARM_FLAGS="-march=armv8-a"
        export TOOLCHAIN_PLAIN="$ROOT/ci/rpi64.cmake"
    else
        PE_TRIPLE=arm-linux-gnueabihf
        export ARM_FLAGS="-mfloat-abi=hard -march=armv7-a -mfpu=neon-vfpv4"
        export TOOLCHAIN_PLAIN="$ROOT/ci/rpi.cmake"
    fi
    export PE_TRIPLE
    export CC=$PE_TRIPLE-gcc CXX=$PE_TRIPLE-g++ STRIP=$PE_TRIPLE-strip AR=$PE_TRIPLE-ar
    export PKG_CONFIG_LIBDIR=/usr/lib/$PE_TRIPLE/pkgconfig:/usr/share/pkgconfig
    export ZLIB_A=/usr/lib/$PE_TRIPLE/libz.a ZLIB_INC=/usr/include
    # a Makefile that asks for `sdl2-config` gets the target's SDL2 flags (the host's own script would name x86 paths)
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

# check_binary <file>...: it must be an ARM hard-float ELF (aarch64 for rpi64) the machine can load, and need nothing but the console's
# own libraries, the SDL2 family or what the mod brings (a mod's libraries sit next to its program)
check_binary() {
    local f
    for f in "$@"; do
        if [ "$TARGET" = rpi64 ]; then
            file "$f" | grep -q 'ELF 64-bit LSB.*ARM aarch64'
        elif [ "$TARGET" = pcusb ]; then
            file "$f" | grep -q 'ELF 32-bit LSB.*Intel 80386'
        else
            file "$f" | grep -q 'ELF 32-bit LSB.*ARM'
        fi
        local lib needed readelf
        if [ "$TARGET" = psc ]; then
            bash /opt/ab/tools/check_psc_binary.sh "$f" "$PSC"
            readelf="$PSC/bin/armv8-sony-linux-gnueabihf-readelf"
        else
            # the Pi: hard float (armhf; aarch64 has no such tag), and nothing newer than the glibc of the image's Debian 12
            # (Raspberry Pi OS bookworm)
            readelf=$PE_TRIPLE-readelf
            if [ "$TARGET" = pcusb ]; then
                readelf=readelf
                # no SSE or SSE2: not one instruction that names an xmm register (the stick's CPUs may lack them)
                # (counted, not grep -q: it would end the pipe early and pipefail would call that a failure)
                local sse
                sse=$(objdump -d --no-show-raw-insn "$f" | grep -cE '%xmm[0-7]' || true)
                if [ "${sse:-0}" -gt 0 ]; then
                    echo "    ERROR: $(basename "$f") uses SSE/SSE2: $sse instructions with xmm registers" >&2
                    return 1
                fi
            fi
            if [ "$TARGET" = rpi ]; then "$readelf" -A "$f" | grep -q 'Tag_ABI_VFP_args: VFP registers'; fi
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
            echo "    ERROR: $(basename "$f") needs $lib, which is neither the console's, SDL2 nor shipped with the mod" >&2
            return 1
        done
    done
    echo "    every library is the console's, SDL2 or the mod's own"
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
        # NNNN-name.psc.patch / .rpi.patch / .rpi64.patch / .pcusb.patch belong to one target; the rest to all (applied in name order)
        case "$p" in
            *.psc.patch) [ "$TARGET" = psc ] || continue ;;
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
        # (binary.<target>= wins over binary=, as in mkmod.py)
        bin=$(sed -n "s/^binary\\.$TARGET=//p" "$dir/port.ini" | head -n 1 | tr -d '\r')
        [ -n "$bin" ] || bin=$(sed -n 's/^binary=//p' "$dir/port.ini" | head -n 1 | tr -d '\r')
        check_binary "$STAGE/$bin"
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
