# pe_ports - developer notes

What this repository is and its layout: `README.md`. Rules that matter when you change it:

- **Upstreams are pinned submodules and are never edited.** Our changes are `ports/<id>/patches/NNNN-*.patch`
  (make one by editing inside the submodule, `git -C ports/<id>/upstream diff > ...`, then
  `git -C ports/<id>/upstream checkout -- .`; a patch that follows another is made against the first one applied).
  Submodules are checked out with `core.autocrlf false` - a patch must not carry CRLF.
- **Nothing third party goes in as a file we did not build or generate.** No committed binaries, no logos, no remap
  libraries, no pad-select pictures. `launch.sh`, `launcher.cfg` and the icon come from `tools/mkmod.py`.
- **Game data only when the licence lets us hand it out**, byte for byte, with its licence file, under
  `ports/<id>/data/` (`.gitattributes` keeps it binary). Say what and why in `port.ini` `[data]`.
- **A dependency that is not in git is fetched with `fetch` (ci/build.sh) against a pinned sha256**, never "latest",
  and named in the port's `changes=` so `SOURCE.txt` shows it.
- A package's launcher_filename is the key of its program in the launcher's `rc/pe_compat.ini`: keep `[pad]` in
  `port.ini` and that file in step (the pad mode and flags are the launcher's, not the package's).
- Build only in the autobleem-build image (`docker run ... ci/build.sh <port>`); delete `build/`, `out/` and
  `build_data/` on a shared build server afterwards. The CI workflow runs only when `AB_CI_ENABLED` is set.
- The source archive of a port must be complete: when a build step needs something else, it belongs in the
  archive (or is a pinned fetch named in `SOURCE.txt`).
