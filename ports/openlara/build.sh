# OpenLara: upstream's own PlayStation Classic target (src/platform/psc/build.sh) with our compiler and flags.
# Sourced by ci/build.sh with $SRC (patched upstream), $STAGE (the launcher folder's files), $CXX, $ARM_FLAGS.
port_build() {
    if [ "$TARGET" = rpi ]; then
        # the Pi has no compositor: upstream's psc platform (wayland-egl, evdev) is the console's; the SDL2 + GLES2 one
        # (src/platform/sdl2, KMSDRM through the system's SDL2) is what runs here, the pad through SDL's game controller
        # (the launcher's controller database, SDL_GAMECONTROLLERCONFIG_FILE)
        ( cd "$SRC/src/platform/sdl2" && "$CXX" -DSDL2_GLES -std=c++11 $(pkg-config --cflags sdl2) -O3 -s $ARM_FLAGS \
            -fno-exceptions -fno-rtti -ffunction-sections -fdata-sections -Wl,--gc-sections -DNDEBUG -D__SDL2__ \
            main.cpp ../../libs/stb_vorbis/stb_vorbis.c ../../libs/minimp3/minimp3.cpp ../../libs/tinf/tinflate.c \
            -I../../ -o "$STAGE/OpenLara" $(pkg-config --libs sdl2) -lGLESv2 -lEGL -lm -lrt -lpthread -lasound -ludev )
        return
    fi
    local d="$SRC/src/platform/psc"
    # the console's EGL / GLES2 / wayland / ALSA / udev are in the sysroot (headers and link stubs);
    # WL_EGL_PLATFORM makes EGL's native window the wayland one (the sysroot's EGL header defaults to X11's)
    ( cd "$d" && "$CXX" -std=c++11 -O3 -s $ARM_FLAGS -fno-exceptions -fno-rtti -ffunction-sections -fdata-sections \
        -Wl,--gc-sections -static-libgcc -static-libstdc++ -DNDEBUG -D__PSC__ -DWL_EGL_PLATFORM \
        main.cpp ../../libs/stb_vorbis/stb_vorbis.c ../../libs/minimp3/minimp3.cpp ../../libs/tinf/tinflate.c \
        -I../../ -lGLESv2 -lEGL -lm -lrt -lpthread -lasound -ludev -lwayland-client -lwayland-egl \
        -o "$STAGE/OpenLara" )
}
