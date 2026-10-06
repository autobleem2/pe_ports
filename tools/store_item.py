#!/usr/bin/env python3
"""Write the AutoBleem Store's `pe` items for a release's packages (autobleem-repo CLAUDE.md, "The AutoBleem
Store's catalog"), ready for `repo_publish.sh store psc ...`:

    tools/store_item.py --out out --dest store-out

For every ports/<id>/port.ini whose out/<id>-<version>.mod exists, <dest>/ gets the .mod, <id>.png (the generated
icon, the same as inside the package) and <id>.item.json: id pe/<id>, kind pe, title, version, author, licence,
description from port.ini, `source_url` = the package's source archive on the site (AB_SOURCE_BASE, the address
mkmod.py writes into SOURCE.txt) and the one .mod in files[] (the catalog adds its size and sha256 when the site
indexes). A port without its .mod or its source archive in out/ is an error: a release is whole or not published
(--only <id>... limits the ports). The source archive is never one of the files. An engine port's `uses=` (the
content kinds it runs) is written as `uses`. A data port (port.ini has a [package] section) makes a `package` item
instead (packages spec, 8.1): id pkg/<id>, kind package, category packages, `provides` the content kinds, its one
file the package zip, no source archive (the zip holds the game's own files). Only the standard library.
"""
import argparse
import configparser
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import mkmod  # noqa: E402


def package_item(cfg, out, dest):
    """The `package` item of a data port: the zip (and the generated icon) go to dest, the descriptor beside them."""
    p = cfg["port"]
    pid, ver = p["id"], p["version"]
    zipname = "%s-%s.zip" % (pid, ver)
    if not os.path.isfile(os.path.join(out, zipname)):
        sys.exit("%s is not in %s - the release is incomplete" % (zipname, out))
    kinds, _games = mkmod.package_entries(cfg)
    shutil.copyfile(os.path.join(out, zipname), os.path.join(dest, zipname))
    with open(os.path.join(dest, pid + ".png"), "wb") as f:
        f.write(mkmod.make_icon(pid, p["icon_text"].split("|")))
    item = {
        "id": "pkg/" + pid,
        "kind": "package",
        "title": p["name"],
        "version": ver,
        "author": p["publisher"],
        "licence": p["licence"],
        "description": p["description"],
        "category": "packages",
        "provides": kinds,
        "image": pid + ".png",
        "files": [{"name": zipname}],
    }
    with open(os.path.join(dest, pid + ".item.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(item, f, indent=2)
        f.write("\n")
    print("%s: %s" % (pid, zipname))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="where ci/build.sh left the .mod files")
    ap.add_argument("--dest", required=True, help="where the descriptors, icons and .mod files go")
    ap.add_argument("--ports", default=os.path.join(ROOT, "ports"))
    ap.add_argument("--only", nargs="*", help="port ids (default: every port)")
    a = ap.parse_args()

    base = os.environ.get("AB_SOURCE_BASE", "https://autobleem.retromenele.pl/source").rstrip("/")
    ids = a.only or sorted(d for d in os.listdir(a.ports) if os.path.isfile(os.path.join(a.ports, d, "port.ini")))
    if not ids:
        sys.exit("no ports")
    os.makedirs(a.dest, exist_ok=True)
    for pid in ids:
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.optionxform = str
        cfg.read(os.path.join(a.ports, pid, "port.ini"), encoding="utf-8")
        p = cfg["port"]
        assert p["id"] == pid, "port.ini id differs from the folder: " + pid
        ver = p["version"]
        if mkmod.is_package_port(cfg):
            package_item(cfg, a.out, a.dest)
            continue
        mod = "%s-%s.mod" % (pid, ver)
        source = "%s-%s-source.tar.gz" % (pid, ver)
        if not os.path.isfile(os.path.join(a.out, mod)):
            sys.exit("%s is not in %s - the release is incomplete" % (mod, a.out))
        if not os.path.isfile(os.path.join(a.out, source)):
            sys.exit("%s is not in %s - a package without its source is not published" % (source, a.out))
        shutil.copyfile(os.path.join(a.out, mod), os.path.join(a.dest, mod))
        with open(os.path.join(a.dest, pid + ".png"), "wb") as f:
            f.write(mkmod.make_icon(pid, p["icon_text"].split("|")))
        item = {
            "id": "pe/" + pid,
            "kind": "pe",
            "title": p["name"],
            "version": ver,
            "author": p["publisher"],
            "licence": p["licence"],
            "description": p["description"],
            "source_url": "%s/%s/%s" % (base, pid, source),
            "image": pid + ".png",
            "files": [{"name": mod}],
        }
        if p.get("uses", "").strip():  # the content kinds the engine runs (the Store's "Needs game data" hint)
            item["uses"] = mkmod.check_kinds(p["uses"], "port %s: uses" % pid)
        with open(os.path.join(a.dest, pid + ".item.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(item, f, indent=2)
            f.write("\n")
        print("%s: %s" % (pid, mod))


if __name__ == "__main__":
    main()
