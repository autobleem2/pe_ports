"""Game data as packages (packages spec, APPS-12): freedoomdata and openarenadata are .mods that proc_pe turns into
Packages/pe-<name>/ (launcher_package="1" + package.ini in the launcher folder, no launch.sh), and the engines say
which data they run (uses=). The engines' start scripts take the picked game from AB_PKG_* and keep the old search
when there is none. No network: the staged files are made here."""
import configparser
import gzip
import io
import lzma
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import mkmod  # noqa: E402

MKMOD = os.path.join(ROOT, "tools", "mkmod.py")
LAUNCHERS = "media/project_eris/etc/project_eris/SUP/launchers/"

# the content kinds of the launcher's shipped table (rc/packages.ini): the data and the engines use these words
KINDS = {"freedoomdata": "doom-iwad", "openarenadata": "q3-openarena"}
USES = {"lzdoom": "doom-iwad", "ioquake3": "q3-openarena", "dosbox": "dos-game"}
STAGED = {  # the files each data port's build.sh lays in the stage, with the licence files of its [port] licence_files
    "freedoomdata": ["freedoom1.wad", "freedoom2.wad"],
    "openarenadata": ["baseoa/pak0.pk3", "baseoa/pak1-maps.pk3"],
}


def load(pid):
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    cfg.read(os.path.join(ROOT, "ports", pid, "port.ini"), encoding="utf-8")
    return cfg


def build_mod(pid, work):
    """ports/<pid> through the real mkmod.py over made-up game files; returns the unpacked launcher folder's files"""
    cfg = load(pid)
    stage, src, out = (os.path.join(work, n) for n in ("stage", "src", "out"))
    os.makedirs(src)
    for rel in STAGED[pid]:
        path = os.path.join(stage, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"IWAD " + rel.encode() + bytes(range(200)))
    for lic in cfg["port"]["licence_files"].split():
        os.makedirs(os.path.dirname(os.path.join(src, lic)), exist_ok=True)
        with open(os.path.join(src, lic), "w") as f:
            f.write("licence")
    env = dict(os.environ, SOURCE_DATE_EPOCH="1700000000", AB_ALLOW_NO_DIGEST="1")
    r = subprocess.run([sys.executable, MKMOD, pid, "--stage", stage, "--src", src, "--out", out],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    ver = cfg["port"]["version"]
    with open(os.path.join(out, "%s-%s.mod" % (pid, ver)), "rb") as f:
        ar = f.read()
    return unpack(ar, cfg["launcher"]["filename"])


def unpack(ar, filename):
    """{relative path: bytes} of the launcher folder in the .mod's data.tar.xz, and the control file as "control" """
    assert ar.startswith(b"!<arch>\n")
    pos, members = 8, {}
    while pos + 60 <= len(ar):
        name = ar[pos:pos + 16].decode().strip().rstrip("/")
        size = int(ar[pos + 48:pos + 58].decode())
        members[name] = ar[pos + 60:pos + 60 + size]
        pos += 60 + size + (size & 1)
    files = {}
    with tarfile.open(fileobj=io.BytesIO(lzma.decompress(members["data.tar.xz"]))) as t:
        for m in t.getmembers():
            name = m.name[2:] if m.name.startswith("./") else m.name
            prefix = LAUNCHERS + filename + "/"
            if m.isfile() and name.startswith(prefix):
                files[name[len(prefix):]] = t.extractfile(m).read()
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(members["control.tar.gz"]))) as t:
        files["control"] = t.extractfile("./control").read()
    return files


def read_ini(text):
    """package.ini as core's reader sees it: flat keys, case-insensitive, a # comment anywhere"""
    out = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line and not line.startswith("["):
            k, v = line.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out


@pytest.mark.parametrize("pid", sorted(KINDS))
def test_a_data_mod_is_a_package_not_an_app(pid):
    with tempfile.TemporaryDirectory() as w:
        files = build_mod(pid, w)
        cfg = load(pid)
        launcher_cfg = files["launcher.cfg"].decode()
        assert 'launcher_package="1"' in launcher_cfg.splitlines()
        assert "launch.sh" not in files and not any(n.endswith(".sh") for n in files), "a package has nothing to start"
        ini = read_ini(files["package.ini"].decode("utf-8"))
        assert ini["title"] == cfg["port"]["name"] and ini["kind"] == KINDS[pid]
        assert ini["version"] == cfg["port"]["version"] and ini["id"] == pid
        assert ini["licence"] and ini["author"] and len(ini["description"]) <= 200
        assert ini["image"] == cfg["launcher"]["filename"] + ".png" and ini["image"] in files
        assert "source" not in ini and "pesource" not in ini, "proc_pe stamps these, the mod does not"
        n = 1
        while "game%d.title" % n in ini:
            assert ini["game%d.file" % n] in files, "every game file is in the folder"
            assert files[ini["game%d.file" % n]].startswith(b"IWAD ") or ini["game%d.file" % n].endswith(".pk3")
            n += 1
        assert n > 1
        assert "SOURCE.txt" in files and any(name.startswith("licences/") for name in files)
        assert b"Version: " + cfg["port"]["version"].encode() in files["control"]


def test_the_data_kinds_and_games():
    with tempfile.TemporaryDirectory() as w:
        free = read_ini(build_mod("freedoomdata", w)["package.ini"].decode())
    assert [free["game1.id"], free["game1.file"]] == ["freedoom1", "freedoom1.wad"]
    assert [free["game2.id"], free["game2.file"]] == ["freedoom2", "freedoom2.wad"]
    with tempfile.TemporaryDirectory() as w:
        arena = read_ini(build_mod("openarenadata", w)["package.ini"].decode())
    assert [arena["game1.id"], arena["game1.file"]] == ["openarena", "baseoa/pak0.pk3"]


@pytest.mark.parametrize("pid,old", [("freedoomdata", "0.13.0-1"), ("openarenadata", "0.8.8-1")])
def test_the_data_mods_have_a_newer_revision_than_the_app_making_one(pid, old):
    """the new revision replaces/follows the old one (proc_pe compares Debian versions), so it must be higher"""
    new = load(pid)["port"]["version"]
    assert new != old and int(new.split("-")[-1]) > int(old.split("-")[-1])


@pytest.mark.parametrize("pid", sorted(USES))
def test_the_engines_say_which_data_they_run(pid):
    cfg = load(pid)
    assert cfg["port"]["uses"] == USES[pid]
    assert 'launcher_uses="%s"' % USES[pid] in mkmod.launcher_cfg(cfg).splitlines()
    assert 'launcher_package="1"' not in mkmod.launcher_cfg(cfg), "an engine is an App"


def test_lzdoom_names_its_own_wad_folder():
    assert 'launcher_package_dir="WAD"' in mkmod.launcher_cfg(load("lzdoom")).splitlines()


def test_a_data_mod_is_not_a_zip_port():
    """[datapackage] (a .mod that proc_pe turns into a package) is not [package] (a zip for the Store)"""
    for pid in KINDS:
        cfg = load(pid)
        assert mkmod.is_data_mod(cfg) and not mkmod.is_package_port(cfg)
    assert not mkmod.is_data_mod(load("lzdoom"))


# ---- the engines' start scripts: the picked game from AB_PKG_*, the old search without a pick ------------------
SH = shutil.which("sh")
pytestmark_sh = pytest.mark.skipif(not SH, reason="needs sh")


def run_script(pid, work, env, setup=None):
    """psc-pad.sh of the port, sourced in a temporary App folder; prints the variables it decides"""
    app = os.path.join(work, "apps", pid)
    os.makedirs(app)
    shutil.copyfile(os.path.join(ROOT, "ports", pid, "files", "psc-pad.sh"), os.path.join(app, "psc-pad.sh"))
    shutil.copytree(os.path.join(ROOT, "ports", pid, "files", "psc"), os.path.join(app, "psc"))
    if setup:
        setup(app)
    shown = {"lzdoom": "$LZ_IWAD|$LZ_MODS", "ioquake3": "$OA_DATA"}[pid]
    e = {k: v for k, v in os.environ.items() if not k.startswith("AB_")}
    e.update(RUNTIME_LOG_PATH=work, AB_LOG_DIR=work, AB_APP_PAD_MODE="psc-kernel", **env)
    r = subprocess.run([SH, "-c", ". ./psc-pad.sh; echo \"%s\"" % shown], cwd=app, env=e, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    with open(os.path.join(work, pid + "-pad.log"), encoding="utf-8") as f:
        return r.stdout.strip(), f.read()


@pytestmark_sh
def test_lzdoom_plays_the_picked_game():
    with tempfile.TemporaryDirectory() as w:
        def wad_folder(app):  # the App's own WAD folder has a game too: the pick wins, it is not searched
            os.makedirs(os.path.join(app, "WAD"))
            open(os.path.join(app, "WAD", "doom2.wad"), "w").close()
        out, log = run_script("lzdoom", w, {"AB_PKG_FILE": "/media/Packages/My Games/freedoom1.wad",
                                            "AB_PKG_ID": "pe-freedoomdata/freedoom1"}, wad_folder)
        assert out == "/media/Packages/My Games/freedoom1.wad|"
        assert "game package pe-freedoomdata/freedoom1" in log


@pytestmark_sh
def test_lzdoom_without_a_pick_searches_as_before():
    with tempfile.TemporaryDirectory() as w:
        def wad_folder(app):
            os.makedirs(os.path.join(app, "WAD"))
            os.makedirs(os.path.join(app, "MODS"))
            open(os.path.join(app, "WAD", "doom2.wad"), "w").close()
            open(os.path.join(app, "MODS", "extra.wad"), "w").close()
        out, _ = run_script("lzdoom", w, {}, wad_folder)
        assert out == "WAD/doom2.wad|-file MODS/extra.wad"
    with tempfile.TemporaryDirectory() as w:
        out, log = run_script("lzdoom", w, {})
        assert out.endswith("/pe-freedoomdata/freedoom2.wad|") and "from Freedoom" in log


@pytestmark_sh
def test_ioquake3_uses_the_picked_package_as_its_base_path():
    with tempfile.TemporaryDirectory() as w:
        out, log = run_script("ioquake3", w, {"AB_PKG_DIR": "/media/Packages/pe-openarenadata",
                                               "AB_PKG_FILE": "/media/Packages/pe-openarenadata/baseoa/pak0.pk3",
                                               "AB_PKG_KIND": "q3-openarena", "AB_PKG_ID": "pe-openarenadata/openarena"})
        assert out == "/media/Packages/pe-openarenadata"
        assert "game package pe-openarenadata/openarena" in log
    with tempfile.TemporaryDirectory() as w:
        out, log = run_script("ioquake3", w, {})
        assert out.endswith("/pe-openarenadata") and "the OpenArena data App" in log


@pytestmark_sh
@pytest.mark.parametrize("pid", ["lzdoom", "ioquake3"])
def test_the_start_scripts_parse(pid):
    r = subprocess.run([SH, "-n", os.path.join(ROOT, "ports", pid, "files", "psc-pad.sh")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_the_arguments_quote_the_picked_paths():
    """a path with a blank (Packages/My Games/...) stays one argument"""
    assert '-iwad "${LZ_IWAD}"' in load("lzdoom")["launcher"]["args"]
    assert 'fs_basepath "${OA_DATA}"' in load("ioquake3")["launcher"]["args"]


def test_no_kind_is_invented():
    """the kinds used here are the ones of the launcher's shipped table"""
    table = {"doom-iwad", "heretic-iwad", "hexen-iwad", "strife-iwad", "quake-id1", "q3-openarena", "q3-baseq3",
             "theme-hospital", "dos-game", "duke3d-grp", "sw-grp"}
    assert set(KINDS.values()) | set(USES.values()) <= table
    assert all(re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", k) for k in table)
