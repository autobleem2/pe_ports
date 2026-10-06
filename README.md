# pe_ports

Open-source programs for the PlayStation Classic, built from public source in the
[autobleem-build](https://github.com/autobleem2/autobleem-build) image and packed as **PE packages** (`.mod`) - the
form AutoBleem's `proc_pe` scanner processor turns into an App when the file is dropped into the stick's `Mods/`
folder. Each package comes with its **corresponding source** (a separate archive, never inside the package), so the
GPL's source duties are met by our own build, not by a third party's binary.

Wave 1 (this repository's first release): **OpenLara**, **Commander Genius** (Keen 1), **OpenJazz** (Jazz Jackrabbit
1) and **TyrQuake** (Quake shareware). Then **ioquake3** (set up for OpenArena) and its separate data package
**OpenArena data** (`requires=` in port.ini; `kind=data`, see below), and **LZDoom** (set up for Freedoom) with its data package **Freedoom data**.

```
git clone --recurse-submodules <this repository>
ci/build.sh openlara|commanderkeen|openjazz|tyrquake|ioquake3|openarenadata|lzdoom|freedoomdata|all     # inside ghcr.io/autobleem2/autobleem-build
```

The result is in `out/`:

| file | what |
|---|---|
| `<id>-<version>.mod` | the package: the program, its launcher files, the allowed shareware data, `SOURCE.txt`, `licences/` |
| `<id>-<version>-source.tar.gz` | the corresponding source: the pinned upstream and its submodules, our patches, these build scripts, `BUILD-INFO.txt` with the build image's digest |

On the build server: `docker run --rm -u $(id -u):$(id -g) -v $PWD:/src -w /src -e AB_BUILD_IMAGE_DIGEST=<RepoDigest>
ghcr.io/autobleem2/autobleem-build:develop ci/build.sh all`, then delete `build/`.

## Layout

```
ci/build.sh                 builds a port in the image (gcc-6 against the console's sysroot), checks the binary,
                            calls tools/mkmod.py
tools/mkmod.py              packs the .mod and the source archive; writes launch.sh, launcher.cfg, the icon, SOURCE.txt
ports/<id>/
    upstream/               the program's source: a git submodule pinned to an exact commit, never edited
    patches/*.patch         our changes over it (applied to a copy at build time)
    port.ini                name, version, licence, upstream URL and commit, what to put in the launcher's
                            compatibility list (pad mode and flags), the data notes
    build.sh                defines port_build: compiles the program into $STAGE
    data/                   only shareware the licence lets us hand out, unmodified, with its licence files
.github/workflows/build.yml the same in CI; gated by AB_CI_ENABLED, so it runs only once this repository exists
```

### port.ini

`[port]` id, name, version (`<upstream>-<our revision>`), description, licence (SPDX), `licence_files` (paths in the
upstream, copied into the package's `licences/`), upstream URL and commit, publisher/year (the launcher shows
them), `copyright` and `changes` (printed in `SOURCE.txt`, `;`-separated), `icon_text` (the generated icon's
lines, `|`-separated), optional `export_exclude` (upstream files that are not source of the program and stay out of
the build and the source archive), optional `requires` (port ids that must be installed first: the Store item's
`requires`), optional `kind=data` (a package of game files with no program: `ci/build.sh` checks no binary; its
`ports/<id>/upstream/` holds only a note naming the pinned archive the build fetches) and `xz_preset` (the package's
xz level, 9 unless the data is already compressed). `[launcher]` the `filename` (also the key of the program in the launcher's
compatibility list `rc/pe_compat.ini`), the `binary`, `args`, `env`. `[pad]` and `[data]` as below.

### What a package is

A Debian archive (`ar`: `debian-binary`, `control.tar.gz`, `data.tar.xz`) whose data holds one folder
`media/project_eris/etc/project_eris/SUP/launchers/<filename>/`:

- `launch.sh`, `launcher.cfg`, `<filename>.png` - **generated** by `tools/mkmod.py` (nothing taken from anywhere:
  the icon is the name in plain pixel letters);
- the program (statically linked where it needs more than the console and the launcher's SDL2 family give);
- the shareware data where allowed, unmodified, with its licence files;
- `SOURCE.txt` (licence, source URL, commit, the sha256 of the source archive, the written offer, upstream
  copyright, our changes) and `licences/`.

The mod's `launch.sh` runs inside AutoBleem's PE environment (`rc/pe_run.sh`): it sources
`/var/volatile/project_eris.cfg`, works in `/var/volatile/launchtmp` (the App's folder) and writes its log to
`$RUNTIME_LOG_PATH`.

### The pad

Every port is written for **the console's own pad**, the one pad every 2020 package was built against and the only
one the launcher shows a PE program (`psc-kernel`, its default: any pad the player uses becomes that pad). The
launcher's `rc/pe_compat.ini` sets no pad for any program - a setting there would reach the original 2020 package of
the same `launcher_filename` too - so a port fits the pad, never the other way round: its config or a patch binds the
console pad's numbers. Those are SDL joystick buttons 0..9 = Triangle, Circle, Cross, Square, L2, R2, L1, R1, Select,
Start, and axes 0/1 = the d-pad (-32768 / 0 / 32767; the left stick past half travel moves them too); no hat, no other
axis. `port.ini`'s `[pad]` records that, the same for every port:

| port | PadMode | Dpad2Analog | Analog2Dpad | how it binds the pad |
|---|---|---|---|---|
| commanderkeen | psc-kernel | 0 | 1 | `files/cgenius.cfg` [input0]: Cross jump/confirm, Circle pogo, Square fire, Triangle run, L1 status, R1 camera, Select help, Start the menu; axes 0/1 steer |
| openjazz | psc-kernel | 0 | 1 | `patches/0002-psc-pad-buttons.patch`: Cross fire/confirm, Circle jump, Triangle weapon, Start the menu, Select pause |
| openlara | psc-kernel | 0 | 1 | the console pad's evdev codes (upstream) |
| tyrquake | psc-kernel | 0 | 1 | the 2020 mapping as an SDL game controller (`patches/0002-sdl-gamecontroller.patch`, `files/config.cfg`, `files/gamecontrollerdb.txt`): d-pad up/down walk, left/right turn (pad choice X, a pad with only a d-pad) or strafe (O, analog sticks; the left stick walks and strafes, the right stick turns and looks), Cross centre view, Square look down, Triangle look up, Circle strafe, Select free look, Start the menu, L1/R1 previous/next weapon, L2 jump, R2 fire |
| ioquake3 | psc-kernel | 0 | 1 | `files/psc/pad-psc.cfg`: Cross jump, Circle use item, Square crouch, Triangle scores, L1/R1 weapon, R2 fire, L2/Select look up/down, Start the menu; the d-pad turns and walks. With the pad mode x360-kernel (Game settings) `files/psc-pad.sh` picks d-pad or dual-analog bindings from player 1's pad |
| lzdoom | psc-kernel | 0 | 1 | `files/psc/common.cfg` switches the joystick on (`use_joystick`); `files/psc/pad-psc.cfg`: d-pad up/down walk and left/right turn, Cross fire (and OK in the menus, `patches/0001-menu-psc-pad.patch`), R2 fire, Square use, Circle strafe (held, with the d-pad; Back in the menus), L2 run (held), L1/R1 weapon, Triangle automap, Select always run on/off, Start the menu (`files/psc-pad.sh` writes the axis map into lzdoom.ini). With the pad mode x360-kernel it picks d-pad or dual-analog bindings from player 1's pad |

### Where the source goes

`SOURCE.txt` in each package names the address of its source archive:
`https://autobleem.retromenele.pl/source/<id>/<id>-<version>-source.tar.gz` (`AB_SOURCE_BASE` changes the base).
Hosting those files next to the packages - and keeping them for at least three years after a port's last release - is
the Store/site side of the work; nothing here uploads anything. A build step that fetches a file (Commander Genius:
the Boost 1.74.0 headers, header-only) pins its sha256 in `ports/<id>/build.sh` and the package's `SOURCE.txt` says so.

### Never in this repository

- the 2020 remap libraries (`sdl_remap_arm.so`, `drastic_sdl_remap.so`), the 2020 pad-select pictures, any
  third-party logo;
- another port's committed binary: every binary here is built from the pinned source;
- game data that is not free to hand out (Keen 4, saved games, a retail game's files).

## Licence

The scripts, port descriptions and the workflow are MIT (`LICENSE`). Every port keeps its upstream's licence; the
packages print it.
