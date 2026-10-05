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
- **Pinned fetches come from our site first** (`$AB_DEPS_BASE/<name>/<file>`, default
  `https://autobleem.retromenele.pl/deps`, uploaded once with autobleem-repo's `repo_publish.sh deps <name> FILE`), with
  the upstream address as the fallback: `fetch <our url> <sha256> <file> <upstream url>`. A file that does not match
  the sha256 is skipped like a missing one.
- **Releases and nightlies (the owner's lead, 2026-10-05):** the download site and the Store take **only v\* releases**.
  A v* tag's `site` job (`.github/workflows/build.yml`) publishes, with autobleem-repo's `repo_publish.sh --local`:
  each port's `-source.tar.gz` to `source/<id>/` (the address `tools/mkmod.py` puts into SOURCE.txt; kept at least
  3 years after the port's last release, never replaced with other bytes), then the `.mod`, the icon and the `pe/<id>`
  item descriptor made by `tools/store_item.py` (title, version, author, licence, description from `port.ini`,
  `source_url`, the one .mod in files[]) to `store psc`; the site's index run lists them in the catalog and on the
  Store page. A new port needs nothing more than its `port.ini`. Nightlies (develop pushes) stay GitHub pre-release
  assets: the `nightly` release carries every `.mod` with its `-source.tar.gz` next to it (the build job fails when a
  `.mod` has no source archive), and nothing of them reaches the site.
- **A release is a gate:** a port that fails to build on a tag stops the whole `build` job, so `site` never runs and
  nothing of that tag is published (`store_item.py` also refuses a missing `.mod` or source). Fix the port and tag again.
- A package's launcher_filename is the key of its program in the launcher's `rc/pe_compat.ini`: keep `[pad]` in
  `port.ini` and that file in step (the pad mode and flags are the launcher's, not the package's).
- Build only in the autobleem-build image (`docker run ... ci/build.sh <port>`); delete `build/`, `out/` and
  `build_data/` on a shared build server afterwards. The CI workflow runs only when `AB_CI_ENABLED` is set.
- The source archive of a port must be complete: when a build step needs something else, it belongs in the
  archive (or is a pinned fetch named in `SOURCE.txt`).
