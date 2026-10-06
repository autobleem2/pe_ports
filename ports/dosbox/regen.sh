#!/usr/bin/env bash
# Makes files/config.h and files/sources.txt again - what DOSBox's own autotools + configure produce for the console
# (--disable-opengl --with-sdl2, the ARM dynamic recompiler on) and the list of sources that make then compiles. Only
# needed when the pinned upstream commit changes; the normal build (build.sh, files/Makefile.psc) does not run it
# because the build image has no automake.
#
# Run it as root in the build image on a scratch copy of the upstream tree (LF line endings):
#   git -c core.autocrlf=false -c core.eol=lf -C ports/dosbox/upstream archive HEAD | tar -x -C DIR
#   docker run --rm -v DIR:/src -v $PWD/ports/dosbox/regen.sh:/regen.sh:ro -e OWNER=$(id -u):$(id -g) \
#       ghcr.io/autobleem2/autobleem-build:develop bash /regen.sh
# DIR/_gen/config.h and DIR/_gen/sources.txt replace the two files in ports/dosbox/files/ (DIR/_gen/make.log is the
# whole compile, DIR/_gen/needed.txt the libraries its own link line asked for).
set -euo pipefail
cd /src
trap 'chown -R "$OWNER" /src' EXIT
apt-get update -qq && apt-get install -y -qq automake autoconf libtool > /dev/null
chmod +x autogen.sh && ./autogen.sh
export PATH=/opt/psc/sdl2/bin:/opt/psc/bin:$PATH
T=armv8-sony-linux-gnueabihf
export CC=$T-gcc CXX=$T-g++ STRIP=$T-strip AR=$T-ar RANLIB=$T-ranlib
F="-O3 -marm -mtune=cortex-a7 -mfpu=neon-vfpv4 -mfloat-abi=hard"
export CFLAGS="$F" CXXFLAGS="$F"
./configure --host=$T --disable-opengl --with-sdl2 ac_cv_lib_X11_main=no ac_cv_header_X11_XKBlib_h=no
sed -i "s/C_TARGETCPU.*/C_TARGETCPU ARMV4LE/g" config.h
echo "#define C_DYNREC 1" >> config.h
mkdir -p _gen
cp config.h _gen/config.h
make -j"$(nproc)" V=1 > _gen/make.log 2>&1
for o in $(find src -name '*.o' | sort); do
    b=${o%.o}
    if [ -f "$b.cpp" ]; then echo "$b.cpp"; elif [ -f "$b.c" ]; then echo "$b.c"; else echo "no source for $o" >&2; exit 1; fi
done > _gen/sources.txt
$T-readelf -d src/dosbox | grep NEEDED > _gen/needed.txt
wc -l _gen/sources.txt
