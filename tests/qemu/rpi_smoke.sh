#!/bin/sh
# The Pi packages' programs under qemu-arm on the Pi's own library family (Debian 12 armhf = Raspberry Pi OS bookworm):
# for every <id>-<version>-rpi.mod the program's dependencies are listed by the loader (a "not found" fails), then the
# program is started with every symbol bound at once (LD_BIND_NOW=1: a missing or wrongly versioned symbol dies here, not
# when the owner reaches that code path) in a headless way the engine allows - its own help or version output, BlastEm's
# frame-limited run on synthetic ROMs, ioquake3's dedicated mode. Video and audio are SDL's dummy drivers, so no window opens.
#
#   tests/qemu/rpi_smoke.sh OUTDIR SYSROOT [ID...]
#
# OUTDIR   where ci/build.sh --target rpi left the .mod files
# SYSROOT  a copy of the build image's /usr/lib/arm-linux-gnueabihf under usr/lib/, with lib -> usr/lib and
#          usr/lib/ld-linux-armhf.so.3 -> arm-linux-gnueabihf/ld-linux-armhf.so.3 (the image's armhf multiarch libraries)
# needs qemu-arm (qemu-user), dpkg-deb, python3: run in a side container (the build image has no qemu), e.g.
#   docker run --rm -v $PWD:/w apps13-qemu sh /w/tests/qemu/rpi_smoke.sh /w/out /w/sysroot
# Exit 0 = every program started.
set -u
OUT=$1; ROOT=$2; shift 2
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
export QEMU_LD_PREFIX=$ROOT SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy LD_BIND_NOW=1
BAD=0

ids=${*:-blastem commanderkeen dosbox ioquake3 lzdoom openjazz openlara tyrquake}
for id in $ids; do
    mod=$(ls "$OUT"/"$id"-*-rpi.mod 2> /dev/null | head -1)
    if [ -z "$mod" ]; then echo "$id: NO PACKAGE in $OUT"; BAD=1; continue; fi
    dpkg-deb -x "$mod" "$W/$id" || { echo "$id: cannot unpack"; BAD=1; continue; }
    app=$(dirname "$(find "$W/$id" -name launch.sh -type f | head -1)")
    case "$id" in
        blastem) bin=blastem ;; commanderkeen) bin=CGeniusExe ;; dosbox) bin=dosbox ;; ioquake3) bin=ioquake3.armv7l ;;
        lzdoom) bin=lzdoom ;; openjazz) bin=OpenJazz ;; openlara) bin=OpenLara ;; tyrquake) bin=tyr-quake ;;
    esac
    echo "=== $id: $(basename "$mod")"
    H=$app # the launch script sets HOME to the App's own folder
    # 1. the loader's own list: every NEEDED library must be found (the program's folder first, as the launch scripts set it)
    list=$(cd "$app" && LD_BIND_NOW= LD_LIBRARY_PATH="$app/lib" qemu-arm -L "$ROOT" "$ROOT/lib/ld-linux-armhf.so.3" --list "./$bin" 2>&1)
    if echo "$list" | grep -q 'not found'; then echo "$list" | grep 'not found'; echo "$id: LIBRARY MISSING"; BAD=1; continue; fi
    echo "    libraries: $(echo "$list" | grep -c '=>') found, none missing"
    # the program's own libraries (ioquake3's renderer and gl4es, LZDoom's OpenAL Soft) the same way
    for so in $(cd "$app" && find . -maxdepth 2 -name '*.so*' -type f | sort); do
        solist=$(cd "$app" && LD_BIND_NOW= LD_LIBRARY_PATH="$app/lib" qemu-arm -L "$ROOT" "$ROOT/lib/ld-linux-armhf.so.3" --list "$so" 2>&1)
        if echo "$solist" | grep -q 'not found'; then echo "$solist" | grep 'not found'; echo "$id: LIBRARY MISSING for $so"; BAD=1; fi
        echo "    own library $so: $(echo "$solist" | grep -c '=>') found"
    done
    # 2. the program itself
    case "$id" in
        blastem)
            python3 "$HERE/mkrom.py" "$W/rom.bin" 2048 > /dev/null
            cmd="./blastem -b 60 $W/rom.bin" ;;
        commanderkeen) cmd="./CGeniusExe --help" ;;
        dosbox) cmd="./dosbox -version" ;;
        ioquake3) cmd="./ioquake3.armv7l +set dedicated 1 +set com_basegame baseoa +set fs_basepath $W/nodata +set sv_pure 0 +version +quit" ;;
        lzdoom) cmd="./lzdoom -h" ;;
        openjazz) cmd="./OpenJazz --help" ;;
        openlara) cmd="./OpenLara" ;;
        tyrquake) cmd="./tyr-quake -help" ;;
    esac
    (cd "$app" && HOME=$H LD_LIBRARY_PATH="$app/lib" timeout 30 qemu-arm -L "$ROOT" $cmd) > "$W/run-$id.log" 2>&1
    rc=$?
    [ $rc -ne 124 ] || rc="124 (still running after 30 s, stopped - the engine started)"
    echo "    rc=$rc: $cmd" | sed "s#$W#<tmp>#g"
    grep -v '^$' "$W/run-$id.log" | head -6 | cut -c1-150 | sed 's/^/    | /'
    # what must not be in the output: a loader or symbol error, a crash
    if grep -qE 'symbol lookup error|undefined symbol|cannot open shared object|version .GLIBC|Segmentation|Aborted|Illegal instruction' "$W/run-$id.log"; then
        echo "$id: STARTUP FAILED"; BAD=1
    fi
done
if [ $BAD -eq 0 ]; then echo "RESULT: every program started"; else echo "RESULT: FAILED"; fi
exit $BAD
