# OpenLara: upstream's own PlayStation Classic target (src/platform/psc/build.sh) with our compiler and flags.
# Sourced by ci/build.sh with $SRC (patched upstream), $STAGE (the launcher folder's files), $CXX, $PSC_FLAGS.
port_build() {
    local d="$SRC/src/platform/psc"
    # the console's EGL / GLES2 / wayland / ALSA / udev are in the sysroot (headers and link stubs);
    # WL_EGL_PLATFORM makes EGL's native window the wayland one (the sysroot's EGL header defaults to X11's)
    ( cd "$d" && "$CXX" -std=c++11 -O3 -s $PSC_FLAGS -fno-exceptions -fno-rtti -ffunction-sections -fdata-sections \
        -Wl,--gc-sections -static-libgcc -static-libstdc++ -DNDEBUG -D__PSC__ -DWL_EGL_PLATFORM \
        main.cpp ../../libs/stb_vorbis/stb_vorbis.c ../../libs/minimp3/minimp3.cpp ../../libs/tinf/tinflate.c \
        -I../../ -lGLESv2 -lEGL -lm -lrt -lpthread -lasound -ludev -lwayland-client -lwayland-egl \
        -o "$STAGE/OpenLara" )
}
