#!/bin/sh
# The Linux packages' programs under qemu user mode on the machine's own library family (Debian 12: armhf = Raspberry Pi OS
# bookworm for rpi, arm64 for rpi64, i386 for pcusb): for every <id>-<version>-<target>.mod the program's dependencies are listed by the loader (a "not found" fails), then the
# program is started with every symbol bound at once (LD_BIND_NOW=1: a missing or wrongly versioned symbol dies here, not
# when the owner reaches that code path) in a headless way the engine allows - its own help or version output, BlastEm's
# frame-limited run on synthetic ROMs, ioquake3's dedicated mode. Video and audio are SDL's dummy drivers, so no window opens.
#
#   tests/qemu/smoke.sh TARGET OUTDIR SYSROOT [ID...]        (TARGET: rpi, rpi64 or pcusb)
#
# OUTDIR   where ci/build.sh --target <target> left the .mod files
# SYSROOT  a copy of the build image's /usr/lib/<multiarch> (arm-linux-gnueabihf, aarch64-linux-gnu, i386-linux-gnu) under
#          usr/lib/, with lib -> usr/lib and usr/lib/<loader> -> <multiarch>/<loader> (ld-linux-armhf.so.3,
#          ld-linux-aarch64.so.1, ld-linux.so.2: the image's multiarch libraries of that machine)
# needs qemu-arm / qemu-aarch64 / qemu-i386 (qemu-user), dpkg-deb, python3: run in a side container (the build image has no
# qemu), e.g.
#   docker run --rm -v $PWD:/w apps13-qemu sh /w/tests/qemu/smoke.sh rpi64 /w/out /w/sysroot
# Exit 0 = every program started.
set -u
TARGET=$1; OUT=$2; ROOT=$3; shift 3
case "$TARGET" in
    rpi) QEMU=qemu-arm; LDSO=ld-linux-armhf.so.3; IOQ=ioquake3.armv7l ;;
    rpi64) QEMU=qemu-aarch64; LDSO=ld-linux-aarch64.so.1; IOQ=ioquake3.aarch64 ;;
    # pcusb: a plain i686 like the launcher - the emulated CPU is a Pentium III (SSE1, no SSE2: the stick's own libSDL2 needs SSE1), so an SSE2 instruction a program
    # reaches without asking cpuid first dies here with SIGILL
    pcusb) QEMU=qemu-i386; LDSO=ld-linux.so.2; IOQ=ioquake3.x86; export QEMU_CPU=pentium3 ;;
    *) echo "unknown target: $TARGET (rpi, rpi64 or pcusb)"; exit 2 ;;
esac
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT
export QEMU_LD_PREFIX=$ROOT SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy LD_BIND_NOW=1
BAD=0

ids=${*:-blastem commanderkeen dosbox ioquake3 lzdoom openjazz openlara tyrquake}
for id in $ids; do
    mod=$(ls "$OUT"/"$id"-*-"$TARGET".mod 2> /dev/null | head -1)
    if [ -z "$mod" ]; then echo "$id: NO PACKAGE in $OUT"; BAD=1; continue; fi
    dpkg-deb -x "$mod" "$W/$id" || { echo "$id: cannot unpack"; BAD=1; continue; }
    app=$(dirname "$(find "$W/$id" -name launch.sh -type f | head -1)")
    case "$id" in
        blastem) bin=blastem ;; commanderkeen) bin=CGeniusExe ;; dosbox) bin=dosbox ;; ioquake3) bin=$IOQ ;;
        lzdoom) bin=lzdoom ;; openjazz) bin=OpenJazz ;; openlara) bin=OpenLara ;; tyrquake) bin=tyr-quake ;;
    esac
    echo "=== $id: $(basename "$mod")"
    H=$app # the launch script sets HOME to the App's own folder
    # 1. the loader's own list: every NEEDED library must be found (the program's folder first, as the launch scripts set it)
    list=$(cd "$app" && LD_BIND_NOW= LD_LIBRARY_PATH="$app/lib" $QEMU -L "$ROOT" "$ROOT/lib/$LDSO" --list "./$bin" 2>&1)
    if echo "$list" | grep -q 'not found'; then echo "$list" | grep 'not found'; echo "$id: LIBRARY MISSING"; BAD=1; continue; fi
    echo "    libraries: $(echo "$list" | grep -c '=>') found, none missing"
    # the program's own libraries (ioquake3's renderer and gl4es, LZDoom's OpenAL Soft) the same way
    for so in $(cd "$app" && find . -maxdepth 2 -name '*.so*' -type f | sort); do
        solist=$(cd "$app" && LD_BIND_NOW= LD_LIBRARY_PATH="$app/lib" $QEMU -L "$ROOT" "$ROOT/lib/$LDSO" --list "$so" 2>&1)
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
        ioquake3) cmd="./$IOQ +set dedicated 1 +set com_basegame baseoa +set fs_basepath $W/nodata +set sv_pure 0 +version +quit" ;;
        lzdoom) cmd="./lzdoom -h" ;;
        openjazz) cmd="./OpenJazz --help" ;;
        openlara) cmd="./OpenLara" ;;
        tyrquake) cmd="./tyr-quake -help" ;;
    esac
    (cd "$app" && HOME=$H LD_LIBRARY_PATH="$app/lib" timeout 30 $QEMU -L "$ROOT" $cmd) > "$W/run-$id.log" 2>&1
    rc=$?
    [ $rc -ne 124 ] || rc="124 (still running after 30 s, stopped - the engine started)"
    echo "    rc=$rc: $cmd" | sed "s#$W#<tmp>#g"
    grep -v '^$' "$W/run-$id.log" | head -6 | cut -c1-150 | sed 's/^/    | /'
    # what must not be in the output: a loader or symbol error, a crash
    if grep -qE 'symbol lookup error|undefined symbol|cannot open shared object|version .GLIBC|Segmentation|Aborted|Illegal instruction' "$W/run-$id.log"; then
        echo "$id: STARTUP FAILED"; BAD=1
    fi
    # 3. pcusb only: no SSE2 instruction in the program or its own libraries (objdump: every instruction that names an xmm register
    # must be an SSE1 one - movss/addps/xorps/cvtsi2ss ... - the whole SSE2 set (movd/movq/movdqa, any ...sd/...pd, p* integer
    # ops, cvt*2sd) is a violation). The stick's own Debian libSDL2 uses SSE1 (Pentium III), so SSE1 is the emulated floor.
    if [ "$TARGET" = pcusb ] && command -v objdump > /dev/null 2>&1; then
        sse_bad=0; ok2='^$'
        # ioquake3's qsnapvectorsse: its SSE2 path (cvtps2dq, cvtdq2ps) is chosen only when cpuid says SSE2 (code/qcommon/common.c, Com_DetectSSE)
        [ "$id" != ioquake3 ] || ok2='^(cvtps2dq|cvtdq2ps)$'
        # LZDoom's DoBlending_SSE2: called only when its CPU check (x86.cpp) says SSE2 (v_palette.cpp)
        okfn='^$'; [ "$id" != lzdoom ] || okfn='DoBlending_SSE2'
        for f in "$app/$bin" $(cd "$app" && find . -maxdepth 2 -name '*.so*' -type f | sed "s#^\.#$app#" | sort); do
            sse2=$(objdump -d "$f" 2> /dev/null | awk -F'\t' -v ok2="$ok2" -v okfn="$okfn" '
                /^[0-9a-f]+ <.*>:$/ { fn = $1 }
                $3 ~ /%xmm/ { split($3, a, " "); m = a[1]; sub(/^(rep|repz|repnz|lock|data16) /, "", m)
                    if (m ~ ok2 || fn ~ okfn) next
                    if (m !~ /^(movss|movaps|movups|movlps|movhps|movlhps|movhlps|movmskps|(add|sub|mul|div|sqrt|rsqrt|rcp|max|min|and|andn|or|xor|ucomi|comi|unpckl|unpckh)(ss|ps)|cmp[a-z]*(ss|ps)|shufps|cvtsi2ssl?|cvtss2si|cvttss2si|cvtpi2ps|cvtps2pi|cvttps2pi)$/) print m " " fn }')
            if [ -n "$sse2" ]; then
                echo "    SSE2 instructions in $(basename "$f"): $(echo "$sse2" | wc -l) (first: $(echo "$sse2" | head -3 | tr '\n' ';'))"
                sse_bad=1
            fi
        done
        [ $sse_bad -eq 0 ] || { echo "$id: SSE2 INSTRUCTIONS IN THE PROGRAM"; BAD=1; }
    fi
done
if [ $BAD -eq 0 ]; then echo "RESULT: every program started"; else echo "RESULT: FAILED"; fi
exit $BAD
