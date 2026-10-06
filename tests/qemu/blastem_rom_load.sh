#!/bin/sh
# BlastEm's ROM load on the console's own libc: the real PSC binary of a .mod under qemu-arm, with the libraries
# copied off a console, once per synthetic ROM (256 KB, 1/2/4 MB, a ROM in a .zip; SMD files listed only). A 32-bit ARM malloc
# aligns to 8, which a PC test never shows (util.c aligned_calloc stored the alignment instead of the real shift and
# every ROM over 512 KB crashed in free()). Nothing is written outside a temporary folder.
#
#   tests/qemu/blastem_rom_load.sh BLASTEM.mod PSCLIB [--expect-crash] [FRAMES]
#
# BLASTEM.mod   the Debian package the build made (needs dpkg-deb)
# PSCLIB        the console's library tree (/lib, /usr/lib, /tmp/lib, copied off read-only); it holds files of the
#               console and stays out of git (the kit lives in the project's git-ignored tmp folder)
# --expect-crash  the contrast run on a binary that still has the bug: succeeds only when the 1 MB ROM dies
#                 and the 256 KB one runs
# needs qemu-arm (qemu-user), python3. The build image has no qemu: run it in a side container, e.g.
#   docker run --rm -v $PWD:/w python:3.12-slim sh -c 'apt-get update -q && apt-get install -y -q qemu-user dpkg \
#       && /w/tests/qemu/blastem_rom_load.sh /w/out/blastem-1.0.0-3.mod /w/psclib'
# Exit 0 = every ROM behaved as expected.
set -u
MOD=$1; LIB=$2; shift 2
EXPECT=ok
if [ "${1:-}" = "--expect-crash" ]; then EXPECT=crash; shift; fi
FRAMES=${1:-60}
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT

dpkg-deb -x "$MOD" "$W/mod" || exit 2
APP=$(dirname "$(find "$W/mod" -name blastem -type f | head -1)")
[ -f "$APP/blastem" ] || { echo "no blastem binary in $MOD"; exit 2; }
echo "binary: $(md5sum "$APP/blastem" | cut -d' ' -f1)  $MOD"

# a private copy of the library tree with the sonames the dynamic loader asks for
cp -a "$LIB" "$W/lib"
L=$W/lib
mkdir -p "$L/media/project_eris/lib"
ln -sf ../../../tmp/lib/libSDL2-2.0.so.0.18.0 "$L/media/project_eris/lib/libSDL2-2.0.so.0"
cp "$L/tmp/lib/libSDL2-2.0.so.0.18.0" "$L/usr/lib/libSDL2-2.0.so.0" 2>/dev/null
(cd "$L/usr/lib" && for pair in libdrm.so.2.4.0:libdrm.so.2 libwayland-client.so.0.3.0:libwayland-client.so.0 \
    libffi.so.6.0.4:libffi.so.6 libwayland-cursor.so.0.0.0:libwayland-cursor.so.0 \
    libxkbcommon.so.0.0.0:libxkbcommon.so.0 libasound.so.2.0.0:libasound.so.2 \
    libwayland-server.so.0.1.0:libwayland-server.so.0 libexpat.so.1.8.10:libexpat.so.1 \
    libstdc++.so.6.0.28:libstdc++.so.6; do ln -sf "${pair%%:*}" "${pair##*:}"; done)
(cd "$L/lib" && for pair in libudev.so.1.6.4:libudev.so.1 libcap.so.2.25:libcap.so.2; do
    ln -sf "${pair%%:*}" "${pair##*:}"; done)

python3 "$HERE/mkrom.py" "$W/test256.bin" 256 >/dev/null
python3 "$HERE/mkrom.py" "$W/test1024.bin" 1024 >/dev/null
python3 "$HERE/mkrom.py" "$W/test2048.bin" 2048 >/dev/null
python3 "$HERE/mkrom.py" "$W/test4096.bin" 4096 >/dev/null
python3 "$HERE/mkrom.py" "$W/test256-smd.smd" 256 smd >/dev/null
python3 "$HERE/mkrom.py" "$W/test1024-smd.smd" 1024 smd >/dev/null
python3 "$HERE/mkrom.py" "$W/test2048.zip" 2048 zip >/dev/null

BAD=0
# the SMD files are run and listed but not judged: an SMD file dies in load_media's second romclose (load_smd_rom
# already closed it: "double free or corruption") at any size, with the fix too - a different, older upstream bug
for name in test256.bin test1024.bin test2048.bin test4096.bin test2048.zip test256-smd.smd test1024-smd.smd; do
    H=$W/home-$name; mkdir -p "$H"
    (cd "$APP" && HOME=$H QEMU_LD_PREFIX=$L timeout 300 qemu-arm -L "$L" ./blastem -b "$FRAMES" "$W/$name") \
        > "$W/q.log" 2>&1
    rc=$?
    note=$(grep -v -e 'subsystem type' "$W/q.log" | tail -2 | tr '\n' ' ')
    echo "$name: rc=$rc  $note"
    crashed=0
    [ $rc -ne 0 ] && crashed=1
    grep -q 'invalid pointer' "$W/q.log" && crashed=1
    case $name in *.smd) continue ;; esac
    if [ "$EXPECT" = crash ]; then
        # the contrast: the small ROM runs, the 1 MB plain ROM dies (the others are listed, not judged)
        [ "$name" = test256.bin ] && [ $crashed -ne 0 ] && BAD=1
        [ "$name" = test1024.bin ] && [ $crashed -eq 0 ] && BAD=1
    else
        [ $crashed -ne 0 ] && BAD=1
    fi
done
if [ $BAD -eq 0 ]; then echo "RESULT: as expected ($EXPECT)"; else echo "RESULT: NOT as expected ($EXPECT)"; fi
exit $BAD
