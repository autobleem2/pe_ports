"""Data ports (packages spec 2.3): ports/liero and ports/xargon become a package zip with package.ini and a `package`
Store item; the engine port dosbox carries `uses=` into launcher.cfg and its item. No network: the game archives are
replaced by files made here, the checks are of the generator and of the descriptors it writes."""
import configparser
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import mkmod  # noqa: E402

MKMOD = os.path.join(ROOT, "tools", "mkmod.py")
STORE_ITEM = os.path.join(ROOT, "tools", "store_item.py")
DATA_PORTS = ("liero", "xargon")


def load(pid, text=None):
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    if text is None:
        cfg.read(os.path.join(ROOT, "ports", pid, "port.ini"), encoding="utf-8")
    else:
        cfg.read_string(text)
    return cfg


def fake_stage(cfg, stage, extra=()):
    """The package root as the port's build.sh lays it, with made-up bytes: every file the port.ini names, a licence
    text, and the port's own mapper file."""
    pid = cfg["port"]["id"]
    _kinds, games = mkmod.package_entries(cfg)
    names = {g["file"] for g in games} | {s[0] for g in games for s in g["starts"]} | set(extra)
    for rel in sorted(names):
        path = os.path.join(stage, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"game file " + rel.encode() + bytes(range(256)))
    os.makedirs(os.path.join(stage, "licences"), exist_ok=True)
    with open(os.path.join(stage, "licences", "licence.txt"), "w") as f:
        f.write("a licence")
    mapper = os.path.join(ROOT, "ports", pid, "files", "mapper.txt")
    if os.path.isfile(mapper):
        shutil.copyfile(mapper, os.path.join(stage, "mapper.txt"))


def build(pid, work):
    cfg = load(pid)
    stage = os.path.join(work, "stage-" + pid)
    fake_stage(cfg, stage)
    out = os.path.join(work, "out")
    env = dict(os.environ, SOURCE_DATE_EPOCH="1700000000")
    r = subprocess.run([sys.executable, MKMOD, pid, "--stage", stage, "--out", out], capture_output=True, text=True, env=env)
    return r, out, stage


def zopen(path):
    """the zip read into memory (a file left open cannot be removed on Windows)"""
    with open(path, "rb") as f:
        return zipfile.ZipFile(io.BytesIO(f.read()))


def read_ini(text):
    """package.ini as core's reader sees it: flat keys, case-insensitive, no sections"""
    out = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line and not line.startswith("["):
            k, v = line.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out


@pytest.mark.parametrize("pid", DATA_PORTS)
def test_the_zip_holds_package_ini_and_the_games_files_unchanged(pid):
    with tempfile.TemporaryDirectory() as w:
        r, out, stage = build(pid, w)
        assert r.returncode == 0, r.stderr
        ver = load(pid)["port"]["version"]
        z = zopen(os.path.join(out, "%s-%s.zip" % (pid, ver)))
        names = z.namelist()
        assert names[0] == "package.ini"
        assert not any(n.startswith("/") or ".." in n.split("/") for n in names)
        ini = read_ini(z.read("package.ini").decode("utf-8"))
        assert ini["kind"] == "dos-game" and ini["id"] == pid and ini["version"] == ver
        assert ini["title"] and ini["licence"] and ini["author"] and len(ini["description"]) <= 200
        assert ini["image"] in names and "SOURCE.txt" in names and any(n.startswith("licences/") for n in names)
        # every file the descriptor names is in the zip, byte for byte what the build laid (the game's files are never touched)
        n = 1
        while "game%d.title" % n in ini:
            assert ini["game%d.file" % n] in names
            for key in [k for k in ini if k.startswith("game%d.start" % n) and k.endswith(".file")]:
                assert ini[key] in names
            assert ini["game%d.mapper" % n] in names
            n += 1
        assert n > 1
        for name in names:
            if name.endswith("/") or name in ("package.ini", "SOURCE.txt") or name == pid + ".png":
                continue
            with open(os.path.join(stage, *name.split("/")), "rb") as f:
                assert z.read(name) == f.read(), name


@pytest.mark.parametrize("pid", DATA_PORTS)
def test_the_zip_is_the_same_every_time(pid):
    shas = []
    for _ in range(2):
        with tempfile.TemporaryDirectory() as w:
            r, out, _stage = build(pid, w)
            assert r.returncode == 0, r.stderr
            shas.append(hashlib.sha256(open(os.path.join(out, os.listdir(out)[0]), "rb").read()).hexdigest())
    assert shas[0] == shas[1]


def test_liero_and_xargon_descriptors():
    with tempfile.TemporaryDirectory() as w:
        for pid in DATA_PORTS:
            r, out, _ = build(pid, w)
            assert r.returncode == 0, r.stderr
        z = zopen(os.path.join(w, "out", "liero-%s.zip" % load("liero")["port"]["version"]))
        ini = read_ini(z.read("package.ini").decode())
        assert ini["game1.file"] == "LIERO/LIERO.EXE" and ini["game1.start1.title"] == "Play"
        assert ini["game1.start2.file"] == "LIERO/LEVEDIT.EXE"
        assert ini["game1.dosbox.cycles"] == "max" and ini["game1.dosbox.memsize"] == "16" and ini["game1.dosbox.sound"] == "sb16"
        assert ini["game1.mapper"] == "mapper.txt"
        z = zopen(os.path.join(w, "out", "xargon-%s.zip" % load("xargon")["port"]["version"]))
        ini = read_ini(z.read("package.ini").decode())
        assert ini["game1.file"] == "XARGON/XARGON.BAT" and ini["game1.start2.file"] == "XARGON/HELPME.EXE"


def test_a_package_without_licences_is_refused():
    with tempfile.TemporaryDirectory() as w:
        cfg = load("liero")
        stage = os.path.join(w, "s")
        fake_stage(cfg, stage)
        shutil.rmtree(os.path.join(stage, "licences"))
        with pytest.raises(SystemExit) as e:
            mkmod.make_package(cfg, stage, w, 0)
        assert "licences/" in str(e.value)


def test_a_file_the_descriptor_names_must_be_in_the_stage():
    with tempfile.TemporaryDirectory() as w:
        cfg = load("liero")
        stage = os.path.join(w, "s")
        fake_stage(cfg, stage)
        os.remove(os.path.join(stage, "LIERO", "LEVEDIT.EXE"))
        with pytest.raises(SystemExit) as e:
            mkmod.package_ini(cfg, stage, "liero.png")
        assert "LEVEDIT.EXE" in str(e.value)


GOOD = """[port]
id=demo
name=Demo
version=1.0-1
description=A demo.
licence=Freeware
publisher=Someone
year=1990
icon_text=DEMO
[package]
content_kind=dos-game
games=demo|Demo Game|DEMO/GAME.EXE
"""


@pytest.mark.parametrize("change,message", [
    ("content_kind=dos-game", "content_kind=Dos_Game"),          # the kind grammar
    ("games=demo|Demo Game|DEMO/GAME.EXE", "games=demo|Demo Game|../GAME.EXE"),
    ("games=demo|Demo Game|DEMO/GAME.EXE", "games=demo|Demo Game|/abs/GAME.EXE"),
    ("games=demo|Demo Game|DEMO/GAME.EXE", "games=demo|Demo Game"),
    ("games=demo|Demo Game|DEMO/GAME.EXE", "games=Demo|Demo Game|DEMO/GAME.EXE"),  # the game id grammar
    ("games=demo|Demo Game|DEMO/GAME.EXE", "games=a|A|A.EXE;a|B|B.EXE"),            # one id twice
    ("description=A demo.", "description=A demo # not a comment"),
    ("content_kind=dos-game", "content_kind=doom-iwad\nmapper=mapper.txt"),         # mapper belongs to dos-game
    ("content_kind=dos-game", "content_kind=dos-game\ndosbox.Cycles=max"),          # setting names are lower case
])
def test_a_bad_package_section_is_refused(change, message):
    cfg = load(None, GOOD.replace(change, message))
    with tempfile.TemporaryDirectory() as w:
        stage = os.path.join(w, "s")
        os.makedirs(os.path.join(stage, "DEMO"))
        open(os.path.join(stage, "DEMO", "GAME.EXE"), "wb").close()  # the file is there: only the section is wrong
        with pytest.raises(SystemExit):
            mkmod.package_ini(cfg, stage, "demo.png")


def test_a_good_minimal_package_section():
    cfg = load(None, GOOD)
    with tempfile.TemporaryDirectory() as w:
        stage = os.path.join(w, "s")
        os.makedirs(os.path.join(stage, "DEMO"))
        open(os.path.join(stage, "DEMO", "GAME.EXE"), "wb").close()
        ini = mkmod.package_ini(cfg, stage, "demo.png")
        assert "Game1.File=DEMO/GAME.EXE" in ini and "Kind=dos-game" in ini and "Publisher" not in ini


def test_package_items_in_the_store():
    with tempfile.TemporaryDirectory() as w:
        out, dest = os.path.join(w, "out"), os.path.join(w, "dest")
        os.makedirs(out)
        for pid in DATA_PORTS:
            ver = load(pid)["port"]["version"]
            with open(os.path.join(out, "%s-%s.zip" % (pid, ver)), "wb") as f:
                f.write(b"zip")
        r = subprocess.run([sys.executable, STORE_ITEM, "--out", out, "--dest", dest, "--only", *DATA_PORTS],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        for pid in DATA_PORTS:
            with open(os.path.join(dest, pid + ".item.json"), encoding="utf-8") as f:
                item = json.load(f)
            ver = load(pid)["port"]["version"]
            assert item["id"] == "pkg/" + pid and item["kind"] == "package" and item["category"] == "packages"
            assert item["provides"] == ["dos-game"]
            assert item["files"] == [{"name": "%s-%s.zip" % (pid, ver)}]
            assert "source_url" not in item and "requires" not in item
            assert os.path.isfile(os.path.join(dest, "%s-%s.zip" % (pid, ver))) and os.path.isfile(os.path.join(dest, pid + ".png"))


def test_a_missing_package_zip_stops_the_release():
    with tempfile.TemporaryDirectory() as w:
        out = os.path.join(w, "out")
        os.makedirs(out)
        r = subprocess.run([sys.executable, STORE_ITEM, "--out", out, "--dest", os.path.join(w, "d"), "--only", "liero"],
                           capture_output=True, text=True)
        assert r.returncode != 0 and "incomplete" in r.stderr


def test_the_engine_says_what_it_runs():
    cfg = load("dosbox")
    assert mkmod.launcher_cfg(cfg).splitlines()[-1] == 'launcher_uses="dos-game"'
    with tempfile.TemporaryDirectory() as w:
        out, dest = os.path.join(w, "out"), os.path.join(w, "dest")
        os.makedirs(out)
        for suffix in (".mod", "-source.tar.gz"):
            with open(os.path.join(out, "dosbox-%s%s" % (cfg["port"]["version"], suffix)), "wb") as f:
                f.write(b"x")
        r = subprocess.run([sys.executable, STORE_ITEM, "--out", out, "--dest", dest, "--only", "dosbox"], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        with open(os.path.join(dest, "dosbox.item.json"), encoding="utf-8") as f:
            item = json.load(f)
        assert item["id"] == "pe/dosbox" and item["uses"] == ["dos-game"]


def test_a_bad_uses_value_is_refused():
    cfg = load(None, GOOD.replace("[package]", "uses=Dos Game\n[launcher]\nfilename=demo\n[package]"))
    with pytest.raises(SystemExit):
        mkmod.launcher_cfg(cfg)


def test_the_game_archives_are_pinned():
    """a download is checked against the sha256 in port.ini (build.sh reads it from there): 64 hex digits, the official address"""
    for pid, host in (("liero", "https://www.liero.be/"), ("xargon", "https://classicdosgames.com/")):
        d = load(pid)["data"]
        assert re.fullmatch(r"[0-9a-f]{64}", d["archive_sha256"])
        assert d["source_url"].startswith(host) and d["source_url"].endswith(d["archive_file"])
        with open(os.path.join(ROOT, "ports", pid, "build.sh"), encoding="utf-8") as f:
            text = f.read()
        assert "fetch " in text and "archive_sha256" in text
