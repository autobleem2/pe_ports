# DOSBox 0.74 (the 2020 SDL2 tree) for the PlayStation Classic: the sources that upstream's own configure + make
# compiled for this target (sources.txt) with the config.h that configure made for it (--disable-opengl --with-sdl2,
# the ARM dynamic recompiler on). ports/dosbox/regen.sh makes both again. Run by build.sh from the copy of the
# upstream tree, which gets this file, config.h and sources.txt next to its configure.ac.
CXX ?= g++
SRCS := $(shell cat sources.txt)
OBJS := $(SRCS:.cpp=.o)
SDL_CFLAGS := $(shell sdl2-config --cflags)

%.o: %.cpp
	$(CXX) -DHAVE_CONFIG_H -I. -I$(dir $<) -Iinclude $(SDL_CFLAGS) $(CXXFLAGS) -c -o $@ $<

all: dosbox

# libpng and zlib (screenshots) are linked in: the console's list of libraries a package may need has neither
dosbox: $(OBJS)
	$(CXX) $(CXXFLAGS) -o $@ $(OBJS) -Wl,-Bstatic -lpng16 -lz -Wl,-Bdynamic -lasound -lm -ldl -lpthread -lSDL2

.PHONY: all
