# pe_ports

Open-source programs for the PlayStation Classic, built from public source in the
[autobleem-build](https://github.com/autobleem2/autobleem-build) image and packed as **PE packages** (`.mod`) - the
form AutoBleem's `proc_pe` scanner processor turns into an App when the file is dropped into the stick's `Mods/`
folder. Each package comes with its **corresponding source** (a separate archive, never inside the package), so the
GPL's source duties are met by our own build, not by a third party's binary.

Wave 1 (this repository's first release): **OpenLara**, **Commander Genius** (Keen 1), **OpenJazz** (Jazz Jackrabbit
1) and **TyrQuake** (Quake shareware).

```
git clone --recurse-submodules <this repository>
ci/build.sh openlara|commanderkeen|openjazz|tyrquake|all     # inside ghcr.io/autobleem2/autobleem-build
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
the build and the source archive). `[launcher]` the `filename` (also the key of the program in the launcher's
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

The pad flags are **not** in the package; the launcher reads them from its `rc/pe_compat.ini`, one section per
`launcher_filename`. `port.ini` records what that section should say, so the two stay in step:

| port | PadMode | Dpad2Analog | Analog2Dpad |
|---|---|---|---|
| openlara | psc-kernel | 0 | 1 |
| commanderkeen | psc-kernel | 0 | 1 |
| openjazz | psc-kernel | 0 | 1 |
| tyrquake | psc-kernel | 0 | 1 |

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
