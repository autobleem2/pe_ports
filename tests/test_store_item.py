"""tools/store_item.py: the Store's pe items from port.ini and a release's out/ folder; and, when autobleem-repo's
tools are around (PE_SITE_TOOLS, default the sibling pe-site worktree), the whole publish into a temp site tree."""
import configparser
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "tools", "store_item.py")
SITE_TOOLS = os.environ.get("PE_SITE_TOOLS") or os.path.abspath(os.path.join(ROOT, "..", "pe-site", "tools"))
ALL_PORTS = tuple(sorted(d for d in os.listdir(os.path.join(ROOT, "ports"))
                         if os.path.isfile(os.path.join(ROOT, "ports", d, "port.ini"))))


def port_version(pid):
    with open(os.path.join(ROOT, "ports", pid, "port.ini"), encoding="utf-8") as f:
        return [ln.split("=", 1)[1] for ln in f.read().splitlines() if ln.startswith("version=")][0].strip()


# the package's version is port.ini's: a version bump does not touch these tests
CK = "commanderkeen-" + port_version("commanderkeen")
SOURCE = "https://autobleem.retromenele.pl/source/commanderkeen/" + CK + "-source.tar.gz"


def is_data_port(pid):
    """a data port (port.ini has a [package] section) builds a package zip, not a .mod"""
    with open(os.path.join(ROOT, "ports", pid, "port.ini"), encoding="utf-8") as f:
        return "[package]" in f.read()


def all_ports():
    ports = os.path.join(ROOT, "ports")
    return sorted(d for d in os.listdir(ports) if os.path.isfile(os.path.join(ports, d, "port.ini")))


def release(out, ports=("commanderkeen",), source=True):
    os.makedirs(out, exist_ok=True)
    for pid in ports:
        ver = port_version(pid)
        if is_data_port(pid):
            with open(os.path.join(out, "%s-%s.zip" % (pid, ver)), "wb") as f:
                f.write(b"zip " + pid.encode())
            continue
        with open(os.path.join(out, "%s-%s.mod" % (pid, ver)), "wb") as f:
            f.write(b"mod " + pid.encode())
        if source:
            with open(os.path.join(out, "%s-%s-source.tar.gz" % (pid, ver)), "wb") as f:
                f.write(b"src " + pid.encode())


def run(*args, env=None):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env)


def test_descriptor_from_port_ini():
    with tempfile.TemporaryDirectory() as w:
        release(os.path.join(w, "out"))
        r = run("--out", os.path.join(w, "out"), "--dest", os.path.join(w, "d"), "--only", "commanderkeen")
        assert r.returncode == 0, r.stderr
        with open(os.path.join(w, "d", "commanderkeen.item.json"), encoding="utf-8") as f:
            d = json.load(f)
        assert d["id"] == "pe/commanderkeen" and d["kind"] == "pe"
        assert d["title"] == "Commander Genius (Keen 1)" and d["licence"] == "GPL-2.0"
        assert d["version"] == port_version("commanderkeen")
        assert d["source_url"] == SOURCE
        assert d["files"] == [{"name": CK + ".mod"}]  # the source archive is never a file
        assert d["image"] == "commanderkeen.png"
        assert d["category"] == "games"  # the package type: port.ini's, the same the .mod's control file carries
        with open(os.path.join(w, "d", "commanderkeen.png"), "rb") as f:
            assert f.read(8) == b"\x89PNG\r\n\x1a\n"
        assert os.path.isfile(os.path.join(w, "d", CK + ".mod"))


def expected_category(pid):
    """the owner's mapping: game ports are games, DOSBox and BlastEm emulators, the game-data mods packages"""
    with open(os.path.join(ROOT, "ports", pid, "port.ini"), encoding="utf-8") as f:
        text = f.read()
    if "\nkind=data" in text:
        return "packages"
    return "emulators" if pid in ("dosbox", "blastem") else "games"


def test_port_category_is_lower_case_and_checked():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import mkmod
    assert mkmod.port_category({"id": "x", "category": " Games "}) == "games"
    assert mkmod.port_category({"id": "x", "category": "packages"}) == "packages"
    assert mkmod.port_category({"id": "x"}) == ""  # untyped: the launcher files it under "PE apps"
    with pytest.raises(SystemExit):
        mkmod.port_category({"id": "x", "category": "pe"})  # PE apps is the launcher's home for untyped mods only


def test_every_mod_port_names_its_package_type():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import mkmod
    for pid in all_ports():
        if is_data_port(pid):
            continue  # a package zip: its Store item says packages itself (test_packages.py)
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(os.path.join(ROOT, "ports", pid, "port.ini"), encoding="utf-8")
        assert mkmod.port_category(cfg["port"]) == expected_category(pid), pid


def test_requires_names_the_packages_to_install_first():
    with tempfile.TemporaryDirectory() as w:
        release(os.path.join(w, "out"), ports=("lzdoom", "freedoomdata", "commanderkeen"))
        r = run("--out", os.path.join(w, "out"), "--dest", os.path.join(w, "d"),
                "--only", "lzdoom", "freedoomdata", "commanderkeen")
        assert r.returncode == 0, r.stderr
        items = {}
        for pid in ("lzdoom", "freedoomdata", "commanderkeen"):
            with open(os.path.join(w, "d", pid + ".item.json"), encoding="utf-8") as f:
                items[pid] = json.load(f)
        assert items["lzdoom"]["requires"] == ["pe/freedoomdata"]
        assert "requires" not in items["freedoomdata"] and "requires" not in items["commanderkeen"]


def test_requires_ioquake3_names_its_data_package():
    with tempfile.TemporaryDirectory() as w:
        release(os.path.join(w, "out"), ports=("ioquake3", "openarenadata", "commanderkeen"))
        r = run("--out", os.path.join(w, "out"), "--dest", os.path.join(w, "d"),
                "--only", "ioquake3", "openarenadata", "commanderkeen")
        assert r.returncode == 0, r.stderr
        items = {}
        for pid in ("ioquake3", "openarenadata", "commanderkeen"):
            with open(os.path.join(w, "d", pid + ".item.json"), encoding="utf-8") as f:
                items[pid] = json.load(f)
        assert items["ioquake3"]["requires"] == ["pe/openarenadata"]
        assert "requires" not in items["openarenadata"] and "requires" not in items["commanderkeen"]


def test_a_missing_package_stops_the_release():
    ports = all_ports()
    missing = ports[-1]
    with tempfile.TemporaryDirectory() as w:
        release(os.path.join(w, "out"), ports=tuple(p for p in ports if p != missing))
        r = run("--out", os.path.join(w, "out"), "--dest", os.path.join(w, "d"))
        assert r.returncode != 0 and missing in r.stderr and "incomplete" in r.stderr
        release(os.path.join(w, "out"), ports=(missing,))
        assert run("--out", os.path.join(w, "out"), "--dest", os.path.join(w, "d2")).returncode == 0


def test_a_package_without_its_source_is_not_published():
    with tempfile.TemporaryDirectory() as w:
        release(os.path.join(w, "out"), source=False)
        r = run("--out", os.path.join(w, "out"), "--dest", os.path.join(w, "d"), "--only", "commanderkeen")
        assert r.returncode != 0 and "source" in r.stderr


def test_source_base_follows_ab_source_base():
    with tempfile.TemporaryDirectory() as w:
        release(os.path.join(w, "out"))
        env = dict(os.environ, AB_SOURCE_BASE="http://x/source/")
        r = run("--out", os.path.join(w, "out"), "--dest", os.path.join(w, "d"), "--only", "commanderkeen", env=env)
        assert r.returncode == 0, r.stderr
        with open(os.path.join(w, "d", "commanderkeen.item.json"), encoding="utf-8") as f:
            assert json.load(f)["source_url"].startswith("http://x/source/commanderkeen/")


@pytest.mark.skipif(not shutil.which("bash") or not os.path.isfile(os.path.join(SITE_TOOLS, "repo_publish.sh")),
                    reason="needs bash and autobleem-repo's tools")
def test_release_publish_into_a_temp_site_tree():
    """the site job's two steps with --local: the source archives, then the store items; the index run lists them"""
    ports = tuple(p for p in ALL_PORTS if not is_data_port(p))  # the data ports' package items: test_packages.py
    with tempfile.TemporaryDirectory() as w, tempfile.TemporaryDirectory() as site:
        out = os.path.join(w, "out")
        release(out, ports=ports)
        dest = os.path.join(w, "store-out")
        assert run("--out", out, "--dest", dest, "--only", *ports).returncode == 0
        env = dict(os.environ, REPO_DIR=site, AB_REPO_URL="https://site")
        publish = [shutil.which("bash"), os.path.join(SITE_TOOLS, "repo_publish.sh"), "--local"]
        for pid in ports:
            archive = [os.path.join(out, f) for f in os.listdir(out)
                       if f.startswith(pid + "-") and f.endswith("-source.tar.gz")]
            r = subprocess.run(publish + ["pe-source", pid, *archive], env=env, capture_output=True, text=True)
            assert r.returncode == 0, r.stderr
        files = [os.path.join(dest, f) for f in sorted(os.listdir(dest))]
        r = subprocess.run(publish + ["store", "psc", *files], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        with open(os.path.join(site, "store", "psc", "catalog.json"), encoding="utf-8") as f:
            catalog = json.load(f)
        assert sorted(i["id"] for i in catalog["items"]) == ["pe/" + p for p in sorted(ports)]
        for i in catalog["items"]:
            assert i["category"] == expected_category(i["id"][3:])
            assert i["kind"] == "pe" and i["files"][0]["name"].endswith(".mod") and i["files"][0]["sha256"]
            assert i["source_url"].startswith("https://autobleem.retromenele.pl/source/")
            # the address the package names is where pe-source put the archive
            assert os.path.isfile(os.path.join(site, "source", i["source_url"].split("/source/", 1)[1]))
        with open(os.path.join(site, "store", "index.html"), encoding="utf-8") as f:
            page = f.read()
        assert "PE Apps</h2>" in page and page.count("Source code") == len(ports)


def test_the_store_image_is_the_ports_own_icon_file():
    """DOSBox's drawn floppy (port.ini icon_file) is the Store image, not the generated text icon; a port without one
    keeps the generated icon."""
    with tempfile.TemporaryDirectory() as w:
        out, dest = os.path.join(w, "out"), os.path.join(w, "dest")
        release(out, ports=("dosbox", "commanderkeen"))
        r = run("--out", out, "--dest", dest, "--only", "dosbox", "commanderkeen")
        assert r.returncode == 0, r.stderr
        with open(os.path.join(ROOT, "ports", "dosbox", "files", "icon.png"), "rb") as f:
            drawn = f.read()
        with open(os.path.join(dest, "dosbox.png"), "rb") as f:
            assert f.read() == drawn
        with open(os.path.join(dest, "commanderkeen.png"), "rb") as f:
            png = f.read()
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and png != drawn
