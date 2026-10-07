# pe_ports

Open-source programs for the PlayStation Classic, built from public source in the
[autobleem-build](https://github.com/autobleem2/autobleem-build) image and packed as **PE packages** (`.mod`) - the
form AutoBleem's `proc_pe` scanner processor turns into an App when the file is dropped into the stick's `Mods/`
folder. Each package comes with its **corresponding source** (a separate archive, never inside the package), so the
GPL's source duties are met by our own build, not by a third party's binary.

Wave 1 (this repository's first release): **OpenLara**, **Commander Genius** (Keen 1), **OpenJazz** (Jazz Jackrabbit
1) and **TyrQuake** (Quake shareware). Then **ioquake3** (set up for OpenArena) and its separate data package
**OpenArena data** (`requires=` in port.ini; `kind=data`, see below), and **LZDoom** (set up for Freedoom) with its data package **Freedoom data**. And **BlastEm** (a Mega Drive emulator; the player brings the games).

**DOS games** (APPS-10): **DOSBox** is an engine App (`Uses=dos-game`); **Liero** and **Xargon** are *data ports* -
game files that come as **packages** (a zip with a `package.ini` for the stick's `Packages/` folder, packages spec
`docs/packages.md` of the hub), built here and listed in the Store as `package` items.

```
git clone --recurse-submodules <this repository>
ci/build.sh openlara|commanderkeen|openjazz|tyrquake|ioquake3|openarenadata|lzdoom|freedoomdata|dosbox|liero|xargon|blastem|all     # inside ghcr.io/autobleem2/autobleem-build
```

The result is in `out/`:

| file | what |
|---|---|
| `<id>-<version>.mod` | the package: the program, its launcher files, the allowed shareware data, `SOURCE.txt`, `licences/` |
| `<id>-<version>-source.tar.gz` | the corresponding source: the pinned upstream and its submodules, our patches, these build scripts, `BUILD-INFO.txt` with the build image's digest |
| `<id>-<version>.zip` | a **data port's** package (liero, xargon): `package.ini`, the game's files unchanged, our pad map, `licences/`, `SOURCE.txt` (where the files come from); no source archive - there is no program |

On the build server: `docker run --rm -u $(id -u):$(id -g) -v $PWD:/src -w /src -e AB_BUILD_IMAGE_DIGEST=<RepoDigest>
ghcr.io/autobleem2/autobleem-build:develop ci/build.sh all`, then delete `build/`.

## Layout

```
ci/build.sh                 builds a port in the image (gcc-6 against the console's sysroot), checks the binary,
                            calls tools/mkmod.py
tools/mkmod.py              packs the .mod and the source archive; writes launch.sh, launcher.cfg, the icon, SOURCE.txt;
                            for a data port packs the package zip and writes its package.ini
tools/store_item.py         the Store items: `pe` for a .mod, `package` for a data port's zip
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

`[port]` id, name, version (`<upstream>-<our revision>`), description, licence (SPDX), `category` (the package type:
games, emulators, tools, media, other or packages (game data) - written into the control file and the Store item; the launcher files the
App in that category as "<name> (mod)"), `licence_files` (paths in the
upstream, copied into the package's `licences/`), upstream URL and commit, publisher/year (the launcher shows
them), `copyright` and `changes` (printed in `SOURCE.txt`, `;`-separated), `icon_text` (the generated icon's
lines, `|`-separated), optional `icon_file` (a PNG of the port's folder used as the App's image instead of the generated icon), optional `export_exclude` (upstream files that are not source of the program and stay out of
the build and the source archive), optional `requires` (port ids that must be installed first: the Store item's
`requires`), optional `kind=data` (a package of game files with no program: `ci/build.sh` checks no binary; its
`ports/<id>/upstream/` holds only a note naming the pinned archive the build fetches) and `xz_preset` (the package's
xz level, 9 unless the data is already compressed). `[launcher]` the `filename` (also the key of the program in the launcher's
compatibility list `rc/pe_compat.ini`), the `binary`, `args`, `env`, `pre` (`|`-separated lines run before the
program; a script of the package is sourced there). `[pad]` and `[data]` as below.

An engine that runs game packages says so in `[port]`: `uses=` (a `;` list of content kinds - lower case, digits,
single `-`, e.g. `dos-game`) goes to `launcher.cfg` as `launcher_uses` (proc_pe makes it `Uses=` of the App) and to the
Store item as `uses`; `package_dir=` (folders of the App that hold its own game data) as `launcher_package_dir`;
`category=` (`games`, `emulators`, ...) is the App's type in the launcher's lists.

### Data ports (game files as packages)

A port whose `port.ini` has a `[package]` section has **no program, no `upstream/`, no `[launcher]`**: its `build.sh`
fetches the game's archive with `fetch` against a **pinned sha256** (the `archive_sha256` of `[data]`, read from
there), lays the files into `$STAGE` (the package's root: the game's files unchanged in their own folder, a pad map,
`licences/`) and `ci/build.sh` calls `mkmod.py`, which writes `package.ini` and the generated icon and `SOURCE.txt`
and packs `out/<id>-<version>.zip` (the same bytes every time). `[package]`: `content_kind` (one kind),
`games=id|title|file;...` (paths inside the package), `start=file|title;...` (the programs that start the game: the
game, its setup - the launcher asks when there are two or more), `mapper=` (the game's pad map) and `dosbox.<name>=`
(`cycles`, `memsize`, `sound` - the DOSBox engine's per-game settings; `start`, `mapper` and `dosbox.*` for the
`dos-game` kind only), `replaces=`. `[data]`: `source_url`, `archive_file`, `archive_sha256`, `game_folder`,
`licence_note`. A game's files are **never** changed: what a port adds sits outside the game's folder.

**Game data as a `.mod`** (freedoomdata, openarenadata): a `kind=data` port with a `[datapackage]` section (the keys of
`[package]`: `content_kind`, `games=id|title|file;...`, and an optional shorter `description`, 200 characters at most)
is still built as a `.mod` (so the Store's `pe/<id>` items and `requires=` keep working), but its launcher folder is
the package: the game's files, `package.ini` (written by `mkmod.py`), the icon, `licences/` and `SOURCE.txt`, and no
`launch.sh`; `launcher.cfg` says `launcher_package="1"`. proc_pe (1.2.0 and later) unpacks it into
`Packages/pe-<filename>/` - never into `Apps/` - and removes the App an older version of the same mod made. The kind
is one of the launcher's table (`rc/packages.ini`): `doom-iwad` for Freedoom, `q3-openarena` for OpenArena.

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
| dosbox | psc-kernel | 0 | 1 | DOSBox's own mapper (`files/mapper.txt`, or the game package's `mapper=` file): the d-pad is the arrows, Cross/Square/Start Enter, Circle/Select Escape; no keyboard mode of the pad needed |
| blastem | psc-kernel | 0 | 1 | `patches/0001-psc-pad-mapping.patch`: an SDL game-controller mapping for the console pad; `patches/0002-psc-defaults.patch` binds it: Cross/Circle/Square = A/B/C, Triangle/L1/R1 = X/Y/Z, Start, Select = Mode, L2 and R2 open the menu, the d-pad on the half-axes |

The DOS games' pad maps are the packages' own (`ports/liero/files/mapper.txt`, `ports/xargon/files/mapper.txt`): the
keys each game's own documentation lists, on the same pad.

### The Linux targets: Raspberry Pi 32-bit (`--target rpi`), Raspberry Pi 64-bit (`--target rpi64`), PC stick (`--target pcusb`)

The eight engines (BlastEm, Commander Genius, DOSBox, ioquake3, LZDoom, OpenJazz, OpenLara, TyrQuake) are also built for the
Pi 400 (Raspberry Pi OS armhf): `ci/build.sh --target rpi <port>|all` in the same image, with its `arm-linux-gnueabihf`
compiler against the Debian 12 armhf libraries (the system's SDL2, GLES2, EGL, ALSA; nothing of SDL ships) - `ci/rpi.cmake` is
the CMake toolchain file of the CMake ports and of gl4es / OpenAL Soft. The result is `<id>-<version>-rpi.mod`, a package of
the same format with `Platform: RPI armhf` in the control file (`proc_pe` turns it into an App with `Exec.rpi=run.sh`, so
a machine lists only its own packages) and the same source archive as the console's (its `BUILD-INFO.txt` names both
toolchains). The 64-bit Pi (`--target rpi64`, `<id>-<version>-rpi64.mod`, `Platform: RPI64 arm64`, `Exec.rpi64=run.sh`,
`aarch64-linux-gnu`, `ci/rpi64.cmake`) and the PC stick (`--target pcusb`, `<id>-<version>-pcusb.mod`, `Platform: PCUSB i386`,
`Exec.pcusb=run.sh`, `i686-linux-gnu` with `-march=i686 -msse2`, `ci/pcusb.cmake`) are built the same way in the same image
against its arm64 / i386 libraries, and run on their own system SDL2. The game data (`freedoomdata`, `openarenadata`, the DOS games) is the same package on every machine and is not
rebuilt: the Linux targets skip those ports and `tools/store_item.py --target <target>` takes their files from the console's build.
What differs per target in a port: `NNNN-name.psc.patch` is the console's, `.linux.patch` is every Linux target's (rpi, rpi64,
pcusb), `.rpi.patch` / `.rpi64.patch` / `.pcusb.patch` one machine's (the rest apply to all, in name order); `port.ini` takes
`args.<t>=`, `env.<t>=`, `pre.<t>=`, `binary.<t>=` and `changes.<t>=` next to the common keys, `<t>` being a target or `linux`
(looked up as target, then `linux`, then the plain key), and `build.sh` reads `$TARGET`, `$CPU_FLAGS` and, for the Linux
targets, `$MULTIARCH` / `$TRIPLET`. The pad is the same: the Pi runs the launcher's virtual console pad (`psc-kernel`), so the pad patches and bindings
are shared; the launcher's Pi package carries the PE runner (`rc/pe_run.sh`) these packages start through.

| port | what the Linux builds change |
|---|---|
| blastem | the menu uses Nuklear's built-in font only (`patches/0006-builtin-font.linux.patch`: DejaVu Sans, which fontconfig names first on a Pi, aborts Nuklear's font baker; the PC stick has fontconfig too); portable cores on every target (the recompiler is x86 and untested here), GLES2 through SDL2; `pkg-config` finds the target's `glesv2.pc` itself |
| commanderkeen | `ci/rpi.cmake`, the system's SDL2 family |
| dosbox | `-std=gnu++14` (the console's gcc 6 dialect; gcc 12 defaults to C++17, which refuses the tree's exception specifications); rpi64: no recompiler (dynrec has no aarch64 back end), config.h patched for a 64-bit CPU; pcusb: the x86 dynamic core and FPU, no PIE |
| ioquake3 | gl4es is built for each machine and sits on the system SDL's KMSDRM GLES2 context; the program is `ioquake3.<ARCH>` (armv7l, aarch64, x86 - `binary.<t>`); aarch64 interprets the game's QVMs |
| lzdoom | `ci/rpi.cmake`; OpenAL Soft is built for the Pi (ALSA) and ships in `lib/` |
| openjazz | nothing |
| openlara | upstream's SDL2 + GLES2 platform (`src/platform/sdl2`) instead of the console's wayland-egl/evdev one; `HOME` is the App's folder; `patches/0002-sdl2-log-errors.linux.patch` logs SDL's errors; the launch script shows a text screen and stops when the Tomb Raider data is missing (`pre.linux`) |
| tyrquake | the console's ABGR8888 / desktop-size patch is not applied |

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
