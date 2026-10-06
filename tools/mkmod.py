#!/usr/bin/env python3
"""Packs one built port into a PE package (.mod) and its corresponding-source archive.

    tools/mkmod.py <id> --stage DIR --src DIR --out DIR

<id>     the port (ports/<id>/port.ini)
--stage  the launcher folder's files as the port's build left them: the program, its libraries, the allowed
         shareware data, our config files
--src    the patched upstream tree the program was built from (the licence files are taken from it)
--out    where out/<id>-<version>.mod and out/<id>-<version>-source.tar.gz go

What it adds to the stage: launch.sh and launcher.cfg (generated from port.ini - nothing of any third party's),
a plain generated icon, SOURCE.txt (licence, source URL and commit, the sha256 of the source archive, the written
offer, the upstream copyright lines, our changes) and the licence texts. The source archive is NEVER inside the
.mod: it is hosted next to it and SOURCE.txt names it.

A data port (port.ini has a [package] section: game files, no program) is packed by `tools/mkmod.py <id> --stage DIR
--out DIR` into out/<id>-<version>.zip instead - a package for the stick's Packages/ folder (packages spec 2.2, 2.3):
the staged files as they are, plus package.ini, the generated icon and SOURCE.txt (no --src, no source archive).

A .mod is a Debian archive (ar: debian-binary, control.tar.gz, data.tar.xz) whose data holds one launcher folder
media/project_eris/etc/project_eris/SUP/launchers/<filename>/ - the form the launcher's proc_pe reads. Everything
is deterministic (times from SOURCE_DATE_EPOCH or the repository's last commit, owner root).

Environment:
    AB_BUILD_IMAGE_DIGEST   the build image's RepoDigest (sha256:...), written into BUILD-INFO.txt (required;
                            AB_ALLOW_NO_DIGEST=1 lets a local test run without)
    AB_BUILD_IMAGE          the image name (default ghcr.io/autobleem2/autobleem-build:develop)
    AB_SOURCE_BASE          where the source archives are hosted (default https://autobleem.retromenele.pl/source)
"""
import argparse
import configparser
import gzip
import hashlib
import io
import lzma
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAUNCHERS = "media/project_eris/etc/project_eris/SUP/launchers/"
MAINTAINER = "AutoBleem team"

# ---------------------------------------------------------------------------------------------------------
# the plain generated icon: a coloured square with the name in big pixel letters (a 5x7 font of our own)
# ---------------------------------------------------------------------------------------------------------
GLYPHS = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 11001 10101 10011 10001 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 11011 10001", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11110 00001 00001 01110 00001 00001 11110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    "-": "00000 00000 00000 11111 00000 00000 00000", ".": "00000 00000 00000 00000 00000 01100 01100",
    " ": "00000 00000 00000 00000 00000 00000 00000",
}


def icon_pixels(port_id, lines, size=256):
    """size x size rows of (r, g, b, a): a gradient square in a colour taken from the id, the name in white letters."""
    digest = hashlib.md5(port_id.encode()).digest()
    base = [60 + digest[i] % 110 for i in range(3)]
    px = [[None] * size for _ in range(size)]
    for y in range(size):
        k = 0.55 + 0.45 * (1 - y / (size - 1))
        row = (min(255, int(c * k * 1.25)) for c in base)
        r, g, b = row
        for x in range(size):
            px[y][x] = (r, g, b, 255)
    border = 8
    for y in range(size):
        for x in range(size):
            if x < border or y < border or x >= size - border or y >= size - border:
                px[y][x] = (235, 235, 235, 255)
    # text: the biggest scale at which every line fits in the square with a margin
    margin = 28
    inner = size - 2 * margin
    scale = 12
    while scale > 2 and max(len(t) for t in lines) * 6 * scale - scale > inner:
        scale -= 1
    line_h = 7 * scale
    gap = 2 * scale
    total_h = len(lines) * line_h + (len(lines) - 1) * gap
    y0 = (size - total_h) // 2
    for n, text in enumerate(lines):
        w = len(text) * 6 * scale - scale
        x0 = (size - w) // 2
        for i, ch in enumerate(text.upper()):
            rows = GLYPHS.get(ch, GLYPHS[" "]).split()
            for gy, bits in enumerate(rows):
                for gx, bit in enumerate(bits):
                    if bit != "1":
                        continue
                    for dy in range(scale):
                        for dx in range(scale):
                            x = x0 + i * 6 * scale + gx * scale + dx
                            y = y0 + n * (line_h + gap) + gy * scale + dy
                            # a dark shadow one step down and right, then the letter
                            sx, sy = x + max(1, scale // 5), y + max(1, scale // 5)
                            if 0 <= sx < size and 0 <= sy < size and px[sy][sx][0] != 255:
                                px[sy][sx] = (20, 20, 20, 255)
                            px[y][x] = (255, 255, 255, 255)
    return px


def make_icon(port_id, lines, size=256):
    """The icon as RGBA PNG bytes."""
    px = icon_pixels(port_id, lines, size)
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            raw.extend(px[y][x])

    def chunk(kind, data):
        body = kind + data
        return len(data).to_bytes(4, "big") + body + (zlib.crc32(body) & 0xFFFFFFFF).to_bytes(4, "big")

    header = size.to_bytes(4, "big") * 2 + bytes([8, 6, 0, 0, 0])
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")


# ---------------------------------------------------------------------------------------------------------
# tar and ar helpers
# ---------------------------------------------------------------------------------------------------------
def tar_info(name, mtime, mode, kind=tarfile.REGTYPE, size=0):
    info = tarfile.TarInfo(name)
    info.mtime = mtime
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    info.mode = mode
    info.type = kind
    info.size = size
    return info


def ar_bytes(members, mtime):
    out = b"!<arch>\n"
    for name, data in members:
        out += (name + "/").ljust(16).encode() + str(mtime).encode().ljust(12) + b"0".ljust(6) + b"0".ljust(6)
        out += b"100644".ljust(8) + str(len(data)).encode().ljust(10) + b"`\n" + data
        if len(data) % 2:
            out += b"\n"
    return out


def run(*args, cwd=None):
    return subprocess.run(args, cwd=cwd, check=True, stdout=subprocess.PIPE).stdout


def file_mode(path):
    return 0o755 if os.stat(path).st_mode & 0o111 else 0o644


# ---------------------------------------------------------------------------------------------------------
# the source archive
# ---------------------------------------------------------------------------------------------------------
def add_git_tree(out_tar, repo, prefix, mtime, excludes):
    """git archive HEAD of `repo` (and of its submodules, recursively) into out_tar under `prefix`. A tree with no
    .git (this repository rebuilt from a source archive) is added as it is."""
    if not os.path.exists(os.path.join(repo, ".git")):
        for base, dirs, names in os.walk(repo):
            dirs.sort()
            rel = os.path.relpath(base, repo).replace(os.sep, "/")
            if rel != "." and rel.split("/")[0] in excludes:
                dirs[:] = []
                continue
            for n in sorted(names):
                top = n if rel == "." else rel.split("/")[0]
                if top in excludes:
                    continue
                add_file(out_tar, os.path.join(base, n), prefix + "/" + (n if rel == "." else rel + "/" + n), mtime)
        return
    data = run("git", "-c", "safe.directory=*", "-C", repo, "archive", "--format=tar", "HEAD")
    with tarfile.open(fileobj=io.BytesIO(data)) as src:
        for m in src:
            top = m.name.split("/")[0]
            if top in excludes or m.name in excludes or m.name.rstrip("/") in excludes:
                continue
            m.mtime = mtime
            m.uid = m.gid = 0
            m.uname = m.gname = "root"
            m.name = prefix + "/" + m.name.removeprefix("./") if m.name not in (".", "./") else prefix
            if m.isreg():
                out_tar.addfile(m, src.extractfile(m))
            else:
                out_tar.addfile(m)
    status = subprocess.run(["git", "-c", "safe.directory=*", "-C", repo, "submodule", "status"], stdout=subprocess.PIPE,
                            text=True, check=False).stdout
    for line in status.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            sub = parts[1]
            if os.path.exists(os.path.join(repo, sub, ".git")):
                add_git_tree(out_tar, os.path.join(repo, sub), prefix + "/" + sub, mtime, set())


def add_file(out_tar, path, arcname, mtime):
    info = tar_info(arcname, mtime, file_mode(path), size=os.path.getsize(path))
    with open(path, "rb") as f:
        out_tar.addfile(info, f)


def add_bytes(out_tar, data, arcname, mtime, mode=0o644):
    out_tar.addfile(tar_info(arcname, mtime, mode, size=len(data)), io.BytesIO(data))


def make_source(port, cfg, out_dir, mtime, build_info):
    """out/<id>-<version>-source.tar.gz; returns (path, sha256)."""
    pid, ver = cfg["port"]["id"], cfg["port"]["version"]
    top = "%s-%s-source" % (pid, ver)
    path = os.path.join(out_dir, top + ".tar.gz")
    excludes = set(cfg["port"].get("export_exclude", "").split())
    pdir = os.path.join(ROOT, "ports", pid)
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.GNU_FORMAT) as t:
        t.addfile(tar_info(top, mtime, 0o755, tarfile.DIRTYPE))
        add_git_tree(t, os.path.join(pdir, "upstream"), top + "/ports/%s/upstream" % pid, mtime, excludes)
        # our patches, the port's recipe, the generator and the CI script, the licence of these scripts
        files = []
        for base, dirs, names in os.walk(pdir):
            # not the upstream (added above) and not the shipped game data (data is no source of the program)
            dirs[:] = sorted(d for d in dirs if d not in ("upstream", "data"))
            for n in sorted(names):
                files.append(os.path.join(base, n))
        for extra in ("ci/build.sh", "tools/mkmod.py", "LICENSE", "README.md"):
            files.append(os.path.join(ROOT, extra))
        for f in files:
            add_file(t, f, top + "/" + os.path.relpath(f, ROOT).replace(os.sep, "/"), mtime)
        add_bytes(t, build_info.encode(), top + "/BUILD-INFO.txt", mtime)
    with gzip.GzipFile(path, "wb", mtime=0, compresslevel=9) as gz:
        gz.write(raw.getvalue())
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return path, sha


# ---------------------------------------------------------------------------------------------------------
# the generated launcher files
# ---------------------------------------------------------------------------------------------------------
def launch_sh(cfg):
    pid = cfg["port"]["id"]
    binary = cfg["launcher"]["binary"]
    args = cfg["launcher"].get("args", "").strip()
    env = cfg["launcher"].get("env", "").strip()
    pre = [l for l in cfg["launcher"].get("pre", "").split("|") if l.strip()]
    lines = [
        "#!/bin/sh",
        "# %s - generated by pe_ports tools/mkmod.py from port.ini; do not edit" % cfg["port"]["name"],
        '. "/var/volatile/project_eris.cfg"',
        'cd "/var/volatile/launchtmp"',
        'chmod +x "%s"' % binary,
        'echo -n 2 > "/data/power/disable"',
    ]
    lines += [l.strip() for l in pre]
    lines.append('%s./%s%s > "${RUNTIME_LOG_PATH}/%s.log" 2>&1' % (env + " " if env else "", binary, " " + args if args else "", pid))
    lines.append('echo -n 1 > "/data/power/disable"')
    return "\n".join(lines) + "\n"


KIND_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")  # the packages spec's grammar of a content kind and of an id


def check_kinds(value, what):
    """The kinds of a `;` list ('dos-game;quake-id1'), each in the grammar of packages.md section 3.2 (max 40)."""
    kinds = [k.strip() for k in value.split(";") if k.strip()]
    for k in kinds:
        if len(k) > 40 or not KIND_RE.match(k):
            raise SystemExit("%s: %r is not a content kind (lower case, digits, single '-', 40 characters at most)" % (what, k))
    return kinds


def launcher_cfg(cfg):
    p = cfg["port"]
    lines = ['launcher_filename="%s"' % cfg["launcher"]["filename"], 'launcher_title="%s"' % p["name"],
             'launcher_publisher="%s"' % p["publisher"], 'launcher_year="%s"' % p["year"]]
    # the engine's game-data kinds and data folders (packages spec 2.3): proc_pe copies them to app.ini's Uses=/PackageDir=
    if p.get("uses", "").strip():
        lines.append('launcher_uses="%s"' % ";".join(check_kinds(p["uses"], "port %s: uses" % p["id"])))
    if p.get("package_dir", "").strip():
        dirs = [d.strip() for d in p["package_dir"].split(";") if d.strip()]
        for d in dirs:
            if d.startswith("/") or ".." in d.split("/") or "\\" in d or '"' in d:
                raise SystemExit("port %s: package_dir %r is not a folder inside the App" % (p["id"], d))
        lines.append('launcher_package_dir="%s"' % ";".join(dirs))
    return "\n".join(lines) + "\n"


def source_txt(cfg, source_url, sha, digest, image):
    p = cfg["port"]
    gpl = p["licence"].upper().startswith(("GPL", "LGPL", "AGPL"))
    out = []
    out.append("SOURCE.txt - %s %s" % (p["name"], p["version"]))
    out.append("=" * len(out[0]))
    out.append("")
    out.append("This package is built from public source by AutoBleem's own build (the pe_ports repository, in the")
    out.append("autobleem-build image). It is not a repack of anybody else's binary.")
    out.append("")
    out.append("Licence:           %s (the text is in the licences/ folder of this package)" % p["licence"])
    out.append("Upstream:          %s" % p["upstream_url"])
    out.append("Upstream commit:   %s%s" % (p["upstream_commit"], " (%s)" % p["upstream_note"] if p.get("upstream_note") else ""))
    out.append("Source archive:    %s" % source_url)
    out.append("SHA-256 of it:     %s" % sha)
    out.append("Build image:       %s@%s" % (image.split(":")[0], digest))
    out.append("")
    out.append("The source archive holds the pinned upstream (and its submodules), our patches, the build scripts")
    out.append("(ci/build.sh, tools/mkmod.py, ports/%s/build.sh) and BUILD-INFO.txt with the build image. It is" % p["id"])
    out.append("not part of this package (it would only fill the stick).")
    out.append("")
    if gpl:
        out.append("Written offer: for three years from the date AutoBleem last distributed this package, anyone who")
        out.append("received it may obtain the complete corresponding source from the address above, or - if that")
        out.append("address is gone - on request through the AutoBleem project page (https://github.com/autobleem2),")
        out.append("for a charge no more than the cost of physically performing the distribution.")
        out.append("")
    else:
        out.append("The licence does not require the source to be offered; it is provided anyway at the address above.")
        out.append("")
    out.append("Upstream copyright:")
    for part in p["copyright"].split(";"):
        out.append("  " + part.strip())
    out.append("")
    out.append("Our changes to the upstream:")
    for part in p["changes"].split(";"):
        out.append("  - " + part.strip())
    out.append("  - launch.sh, launcher.cfg and the icon are generated by tools/mkmod.py (not taken from anywhere)")
    out.append("")
    if cfg.has_section("data") and cfg["data"].get("shipped", "none") != "none":
        out.append("Game data shipped in this package (not part of the program's source or licence):")
        out.append("  " + cfg["data"]["shipped_note"])
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------------------
# a data port: a package (zip with package.ini) for Packages/ instead of a .mod (packages spec, 2.3)
# ---------------------------------------------------------------------------------------------------------
def is_package_port(cfg):
    return cfg.has_section("package")


def _plain(value, what, limit):
    """A value of package.ini: one line, no '#' (a comment starts anywhere), at most `limit` characters."""
    value = value.strip()
    if not value or "\n" in value or "\r" in value or "#" in value or len(value) > limit:
        raise SystemExit("package.ini %s: %r is empty, has a '#' or a line break, or is longer than %d" % (what, value, limit))
    return value


def _inside(path, what):
    """A path inside the package: relative, '/' separators, no '..'."""
    if (not path or path.startswith("/") or "\\" in path or ":" in path or ".." in path.split("/")
            or any(c in path for c in "#\r\n|;")):
        raise SystemExit("package.ini %s: %r is not a path inside the package" % (what, path))
    return path


def package_entries(cfg):
    """The data port's [package] section as numbered games: a list of dicts (id, title, file, starts, mapper, dosbox)."""
    pid = cfg["port"]["id"]
    sec = cfg["package"]
    kinds = check_kinds(sec.get("content_kind", ""), "port %s: content_kind" % pid)
    if not kinds:
        raise SystemExit("port %s: [package] needs content_kind" % pid)
    games = []
    for item in [g for g in sec.get("games", "").split(";") if g.strip()]:
        parts = [x.strip() for x in item.split("|")]
        if len(parts) != 3:
            raise SystemExit("port %s: a game in games= is id|title|file, not %r" % (pid, item))
        gid, title, file = parts
        if len(gid) > 40 or not KIND_RE.match(gid):
            raise SystemExit("port %s: game id %r is not [a-z0-9] with single '-' (40 at most)" % (pid, gid))
        games.append({"id": gid, "title": _plain(title, "game title", 80), "file": _inside(file, "game file"), "kind": kinds[0]})
    if not games:
        raise SystemExit("port %s: [package] needs games=id|title|file;..." % pid)
    if len({g["id"] for g in games}) != len(games):
        raise SystemExit("port %s: two games with one id" % pid)
    starts = []
    for item in [s for s in sec.get("start", "").split(";") if s.strip()]:
        file, _, title = item.partition("|")
        starts.append((_inside(file.strip(), "start file"), _plain(title or file, "start title", 80)))
    mapper = _inside(sec["mapper"].strip(), "mapper") if sec.get("mapper", "").strip() else ""
    dosbox = {}
    for key in sec:
        if key.startswith("dosbox."):
            name = key[len("dosbox."):]
            if not re.match(r"^[a-z0-9]+$", name):
                raise SystemExit("port %s: %s is not a DOSBox setting name" % (pid, key))
            dosbox[name] = _plain(sec[key], key, 80)
    if (starts or mapper or dosbox) and kinds[0] != "dos-game":
        raise SystemExit("port %s: start=, mapper= and dosbox.* belong to the dos-game kind only" % pid)
    for g in games:
        g.update(starts=starts, mapper=mapper, dosbox=dosbox)
    return kinds, games


def package_ini(cfg, stage, image):
    """The text of package.ini for the data port `cfg` over the staged files `stage` (every file named must be there)."""
    p = cfg["port"]
    kinds, games = package_entries(cfg)
    must = [g["file"] for g in games] + [s[0] for g in games for s in g["starts"]] + [g["mapper"] for g in games if g["mapper"]]
    for rel in must:
        if not os.path.isfile(os.path.join(stage, *rel.split("/"))):
            raise SystemExit("port %s: %s is not in the staged package" % (p["id"], rel))
    pid = p["id"]
    if len(pid) > 40 or not KIND_RE.match(pid):
        raise SystemExit("port id %r is not a package id" % pid)
    out = ["[package]", "Title=" + _plain(p["name"], "Title", 80), "Kind=" + ";".join(kinds), "Id=" + pid,
           "Version=" + _plain(p["version"], "Version", 40), "Licence=" + _plain(p["licence"], "Licence", 120),
           "Author=" + _plain(p["publisher"], "Author", 120), "Description=" + _plain(p["description"], "Description", 200),
           "Image=" + image]
    if cfg["package"].get("replaces", "").strip():
        out.append("Replaces=" + ";".join(r.strip() for r in cfg["package"]["replaces"].split(";") if r.strip()))
    for n, g in enumerate(games, 1):
        out += ["Game%d.Id=%s" % (n, g["id"]), "Game%d.Title=%s" % (n, g["title"]), "Game%d.File=%s" % (n, g["file"])]
        for m, (file, title) in enumerate(g["starts"], 1):
            out += ["Game%d.Start%d.File=%s" % (n, m, file), "Game%d.Start%d.Title=%s" % (n, m, title)]
        for name, value in sorted(g["dosbox"].items()):
            out.append("Game%d.Dosbox.%s=%s" % (n, name.capitalize(), value))
        if g["mapper"]:
            out.append("Game%d.Mapper=%s" % (n, g["mapper"]))
    return "\n".join(out) + "\n"


def package_source_txt(cfg):
    p, d = cfg["port"], cfg["data"]
    out = ["SOURCE.txt - %s %s" % (p["name"], p["version"])]
    out.append("=" * len(out[0]))
    out += ["", "This package holds game data, not a program: there is no source code to offer.", "",
            "Licence:           %s (the text is in the licences/ folder of this package)" % p["licence"],
            "Where the files come from:", "  %s" % d["source_url"],
            "  file %s, sha256 %s" % (d["archive_file"], d["archive_sha256"]), "",
            "The game's own files are that archive's files, byte for byte, in the folder %s/ - nothing in them was" % d["game_folder"],
            "changed, added or removed (the licence allows spreading them only that way). What AutoBleem added sits",
            "outside that folder: package.ini (what the launcher reads), the pad map, the icon, licences/ and this file.", ""]
    if d.get("licence_note", "").strip():
        out += ["Licence note:"] + ["  " + part.strip() for part in d["licence_note"].split(";") if part.strip()] + [""]
    return "\n".join(out)


def make_package(cfg, stage, out_dir, mtime):
    """out/<id>-<version>.zip from the staged package root `stage` (the game's files, the pad map, licences/ ... laid by
    the port's build.sh): adds package.ini, the icon and SOURCE.txt and packs everything deterministically."""
    p = cfg["port"]
    pid, ver = p["id"], p["version"]
    lic = os.path.join(stage, "licences")
    if not os.path.isdir(lic) or not os.listdir(lic):
        raise SystemExit("port %s: a package ships its licence texts in licences/ (build.sh lays them)" % pid)
    image = pid + ".png"
    ini = package_ini(cfg, stage, image)
    with open(os.path.join(stage, "package.ini"), "w", newline="\n", encoding="utf-8") as f:
        f.write(ini)
    with open(os.path.join(stage, image), "wb") as f:
        f.write(make_icon(pid, p["icon_text"].split("|")))
    with open(os.path.join(stage, "SOURCE.txt"), "w", newline="\n", encoding="utf-8") as f:
        f.write(package_source_txt(cfg))
    names = []
    for base, dirs, files in os.walk(stage):
        dirs.sort()
        rel = os.path.relpath(base, stage).replace(os.sep, "/")
        if rel != ".":
            names.append(rel + "/")
        names += [(rel + "/" if rel != "." else "") + n for n in sorted(files)]
    date = time.gmtime(max(mtime, 315532800))[:6]  # a zip cannot hold a time before 1980
    path = os.path.join(out_dir, "%s-%s.zip" % (pid, ver))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(names, key=lambda n: (n != "package.ini", n)):  # package.ini first, then by name
            info = zipfile.ZipInfo(name, date)
            info.create_system = 3
            if name.endswith("/"):
                info.external_attr = (0o40755 << 16) | 0x10
                z.writestr(info, b"")
            else:
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                with open(os.path.join(stage, *name.split("/")), "rb") as fh:
                    z.writestr(info, fh.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return path


def main_package(a, cfg):
    p = cfg["port"]
    assert p["id"] == a.id, "port.ini id differs from the folder"
    try:
        head = run("git", "-c", "safe.directory=*", "-C", ROOT, "log", "-1", "--format=%ct").decode().split()
        commit_time = int(head[0])
    except Exception:
        commit_time = 0
    mtime = int(os.environ.get("SOURCE_DATE_EPOCH", commit_time))
    os.makedirs(a.out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="mkpkg-")
    try:
        root = os.path.join(work, "pkg")
        shutil.copytree(a.stage, root, symlinks=False)  # the stage stays as the build left it
        path = make_package(cfg, root, a.out, mtime)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("%s  %d bytes  %s" % (os.path.basename(path), os.path.getsize(path), hashlib.sha256(open(path, "rb").read()).hexdigest()))


# ---------------------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--stage", required=True)
    ap.add_argument("--src", default="", help="the patched upstream (not for a data package)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    ini = os.path.join(ROOT, "ports", a.id, "port.ini")
    cfg.read(ini, encoding="utf-8")
    if is_package_port(cfg):
        return main_package(a, cfg)
    if not a.src:
        sys.exit("--src is required")
    p = cfg["port"]
    pid, ver = p["id"], p["version"]
    assert pid == a.id, "port.ini id differs from the folder"
    filename = cfg["launcher"]["filename"]

    image = os.environ.get("AB_BUILD_IMAGE", "ghcr.io/autobleem2/autobleem-build:develop")
    digest = os.environ.get("AB_BUILD_IMAGE_DIGEST", "")
    digest = digest.split("@")[-1]
    if not digest:
        if os.environ.get("AB_ALLOW_NO_DIGEST") == "1":
            digest = "sha256:unknown-local-test"
        else:
            sys.exit("AB_BUILD_IMAGE_DIGEST is not set (the build image's RepoDigest goes into the source archive)")
    base = os.environ.get("AB_SOURCE_BASE", "https://autobleem.retromenele.pl/source").rstrip("/")

    try:
        head = run("git", "-c", "safe.directory=*", "-C", ROOT, "log", "-1", "--format=%ct %H").decode().split()
        commit_time, ours = int(head[0]), head[1]
    except Exception:
        commit_time, ours = 0, "unknown"
    mtime = int(os.environ.get("SOURCE_DATE_EPOCH", commit_time))
    built = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(mtime))

    os.makedirs(a.out, exist_ok=True)
    build_info = "\n".join([
        "pe_ports commit:    %s" % ours,
        "port:               %s %s" % (pid, ver),
        "upstream commit:    %s" % p["upstream_commit"],
        "build image:        %s" % image,
        "build image digest: %s" % digest,
        "toolchain:          gcc-6 against the console's Debian Stretch sysroot (/opt/psc), SDL2 2.0.18 family",
        "rebuild:            docker run --rm -v $PWD:/src -w /src -e AB_BUILD_IMAGE_DIGEST=%s %s@%s ci/build.sh %s" %
        (digest, "ghcr.io/autobleem2/autobleem-build", digest, pid), ""])
    src_path, sha = make_source(a, cfg, a.out, mtime, build_info)
    source_url = "%s/%s/%s" % (base, pid, os.path.basename(src_path))

    work = tempfile.mkdtemp(prefix="mkmod-")
    try:
        folder = os.path.join(work, filename)
        shutil.copytree(a.stage, folder, symlinks=False)
        with open(os.path.join(folder, "launch.sh"), "w", newline="\n") as f:
            f.write(launch_sh(cfg))
        os.chmod(os.path.join(folder, "launch.sh"), 0o755)
        with open(os.path.join(folder, "launcher.cfg"), "w", newline="\n") as f:
            f.write(launcher_cfg(cfg))
        with open(os.path.join(folder, filename + ".png"), "wb") as f:
            f.write(make_icon(pid, p["icon_text"].split("|")))
        with open(os.path.join(folder, "SOURCE.txt"), "w", newline="\n") as f:
            f.write(source_txt(cfg, source_url, sha, digest, image))
        os.makedirs(os.path.join(folder, "licences"), exist_ok=True)
        for lic in p["licence_files"].split():
            # GsKit/LICENSE -> licences/GsKit-LICENSE.txt: the path in the name keeps two LICENSE files apart
            name = lic.replace("/", "-")
            if not name.lower().endswith(".txt"):
                name += ".txt"
            shutil.copyfile(os.path.join(a.src, lic), os.path.join(folder, "licences", name))

        # ---- data.tar.xz
        entries = []
        for base_dir, dirs, names in os.walk(folder):
            dirs.sort()
            rel = os.path.relpath(base_dir, work).replace(os.sep, "/")
            entries.append((rel, None))
            for n in sorted(names):
                entries.append((rel + "/" + n, os.path.join(base_dir, n)))
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w", format=tarfile.GNU_FORMAT) as t:
            t.addfile(tar_info("./", mtime, 0o755, tarfile.DIRTYPE))
            parts = LAUNCHERS.rstrip("/").split("/")
            for i in range(len(parts)):
                t.addfile(tar_info("./" + "/".join(parts[: i + 1]) + "/", mtime, 0o755, tarfile.DIRTYPE))
            size_kb = 0
            for rel, path in entries:
                name = "./" + LAUNCHERS + rel
                if path is None:
                    t.addfile(tar_info(name + "/", mtime, 0o755, tarfile.DIRTYPE))
                else:
                    mode = 0o755 if (file_mode(path) == 0o755 or os.path.basename(path) == "launch.sh") else 0o644
                    size_kb += os.path.getsize(path)
                    with open(path, "rb") as fh:
                        t.addfile(tar_info(name, mtime, mode, size=os.path.getsize(path)), fh)
        # preset 9 unless port.ini says otherwise: a package of already compressed game data (xz_preset=0) would
        # take minutes at 9 and shrink by nothing
        data = lzma.compress(raw.getvalue(), format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64,
                             preset=int(p.get("xz_preset", "9")))

        # ---- control.tar.gz (the Debian control file: the Description's continuation lines carry the metadata)
        desc = [p["description"]]
        control = [
            "Package: %s" % pid, "Version: %s" % ver, "Architecture: armhf", "Maintainer: %s" % MAINTAINER,
            "Installed-Size: %d" % ((size_kb + 1023) // 1024),
            "Description: %s" % p["name"],
            " Type: USB_MOD",
            " %s" % desc[0],
            " Author: %s" % p["publisher"],
            " Platform: SONYPSC armhf",
            " Git Commit: %s" % p["upstream_commit"][:7],
            " Built: %s" % built, ""]
        craw = io.BytesIO()
        with tarfile.open(fileobj=craw, mode="w", format=tarfile.GNU_FORMAT) as t:
            body = "\n".join(control).encode()
            t.addfile(tar_info("./control", mtime, 0o644, size=len(body)), io.BytesIO(body))
        cgz = gzip.compress(craw.getvalue(), mtime=0)

        mod_path = os.path.join(a.out, "%s-%s.mod" % (pid, ver))
        with open(mod_path, "wb") as f:
            f.write(ar_bytes([("debian-binary", b"2.0\n"), ("control.tar.gz", cgz), ("data.tar.xz", data)], mtime))
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print("%s  %d bytes  %s" % (os.path.basename(mod_path), os.path.getsize(mod_path), hashlib.sha256(open(mod_path, "rb").read()).hexdigest()))
    print("%s  %d bytes  %s" % (os.path.basename(src_path), os.path.getsize(src_path), sha))


if __name__ == "__main__":
    main()
