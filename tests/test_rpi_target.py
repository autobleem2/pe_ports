"""The Raspberry Pi 32-bit target (APPS-13): `--target rpi` of ci/build.sh, tools/mkmod.py and tools/store_item.py.

The package keeps the .mod format with a Platform line of its own (proc_pe lists an App only on the machine its Platform
names); the console's package stays what it was (name, control file, launch.sh); one source archive serves both; game
data is shared. No network and no compiler: the staged files are made here."""
import configparser
import gzip
import io
import json
import lzma
import os
import re
import subprocess
import sys
import tarfile
import tempfile

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import mkmod  # noqa: E402

MKMOD = os.path.join(ROOT, "tools", "mkmod.py")
STORE_ITEM = os.path.join(ROOT, "tools", "store_item.py")
LAUNCHERS = "media/project_eris/etc/project_eris/SUP/launchers/"
ENGINES = ("blastem", "commanderkeen", "dosbox", "ioquake3", "lzdoom", "openjazz", "openlara", "tyrquake")


def load(pid):
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    cfg.read(os.path.join(ROOT, "ports", pid, "port.ini"), encoding="utf-8")
    return cfg


def build(pid, target, work):
    """mkmod.py over made-up files for the engine `pid`; returns (mod path, source archive path)"""
    cfg = load(pid)
    stage, src, out = (os.path.join(work, n) for n in ("stage", "src", "out"))
    os.makedirs(src, exist_ok=True)
    os.makedirs(stage, exist_ok=True)
    with open(os.path.join(stage, cfg["launcher"]["binary"]), "wb") as f:
        f.write(b"\x7fELF" + bytes(range(100)))
    for lic in cfg["port"]["licence_files"].split():
        os.makedirs(os.path.dirname(os.path.join(src, lic)), exist_ok=True)
        with open(os.path.join(src, lic), "w") as f:
            f.write("licence")
    env = dict(os.environ, SOURCE_DATE_EPOCH="1700000000", AB_ALLOW_NO_DIGEST="1")
    args = [sys.executable, MKMOD, pid, "--stage", stage, "--src", src, "--out", out]
    if target:
        args += ["--target", target]
    r = subprocess.run(args, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    ver = cfg["port"]["version"]
    mod = os.path.join(out, mkmod.mod_filename(pid, ver, target or "psc"))
    return mod, os.path.join(out, "%s-%s-source.tar.gz" % (pid, ver))


def unpack(path):
    """(control text, {file name inside the launcher folder: bytes}) of a .mod"""
    with open(path, "rb") as f:
        ar = f.read()
    pos, members = 8, {}
    while pos + 60 <= len(ar):
        name = ar[pos:pos + 16].decode().strip().rstrip("/")
        size = int(ar[pos + 48:pos + 58].decode())
        members[name] = ar[pos + 60:pos + 60 + size]
        pos += 60 + size + (size & 1)
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(members["control.tar.gz"]))) as t:
        control = t.extractfile("./control").read().decode()
    files = {}
    with tarfile.open(fileobj=io.BytesIO(lzma.decompress(members["data.tar.xz"]))) as t:
        for m in t.getmembers():
            name = m.name[2:] if m.name.startswith("./") else m.name
            if m.isfile() and name.startswith(LAUNCHERS):
                files[name.split("/", 7)[-1]] = t.extractfile(m).read()
    return control, files


def test_the_console_package_is_what_it_was():
    with tempfile.TemporaryDirectory() as w:
        mod, _ = build("openjazz", None, w)
        assert os.path.basename(mod) == "openjazz-%s.mod" % load("openjazz")["port"]["version"]
        control, files = unpack(mod)
        assert " Platform: SONYPSC armhf\n" in control and "RPI" not in control
        launch = files["launch.sh"].decode()
        assert 'echo -n 2 > "/data/power/disable"\n' in launch and "2>/dev/null" not in launch
        assert "built for the Raspberry Pi" not in files["SOURCE.txt"].decode()


@pytest.mark.parametrize("pid", ENGINES)
def test_the_pi_package_names_its_machine(pid):
    with tempfile.TemporaryDirectory() as w:
        mod, _ = build(pid, "rpi", w)
        ver = load(pid)["port"]["version"]
        assert os.path.basename(mod) == "%s-%s-rpi.mod" % (pid, ver)
        control, files = unpack(mod)
        assert " Platform: RPI armhf\n" in control and "SONYPSC" not in control
        assert "Architecture: armhf\n" in control and "Package: %s\n" % pid in control
        launch = files["launch.sh"].decode()
        # the console's power flag does not exist on the Pi: no error text from the redirections
        assert 'echo -n 2 > "/data/power/disable" 2>/dev/null\n' in launch
        assert 'echo -n 1 > "/data/power/disable" 2>/dev/null\n' in launch
        source = files["SOURCE.txt"].decode()
        assert "built for the Raspberry Pi 32-bit" in source and "--target rpi" in source
        assert files["launcher.cfg"].decode().startswith('launcher_filename="%s"' % load(pid)["launcher"]["filename"])


def test_one_source_archive_serves_both_targets():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        _, src_psc = build("tyrquake", "psc", a)
        _, src_rpi = build("tyrquake", "rpi", b)
        with open(src_psc, "rb") as f1, open(src_rpi, "rb") as f2:
            assert f1.read() == f2.read(), "the archive is the same file whichever target packed it (never replaced with other bytes)"
        with tarfile.open(src_rpi) as t:
            names = t.getnames()
            info = t.extractfile([n for n in names if n.endswith("BUILD-INFO.txt")][0]).read().decode()
        assert any(n.endswith("/ci/rpi.cmake") for n in names), "the Pi's toolchain file is part of the source"
        assert "toolchain (psc):" in info and "toolchain (rpi):" in info and "[--target psc|rpi]" in info


def test_a_launcher_value_can_differ_per_target():
    cfg = load("openlara")
    assert mkmod.launcher_value(cfg, "env", "psc") == ""
    assert mkmod.launcher_value(cfg, "env", "rpi") == "HOME=/var/volatile/launchtmp"
    assert mkmod.launcher_value(cfg, "binary", "rpi") == "OpenLara"  # no key of its own: the common one
    with tempfile.TemporaryDirectory() as w:
        _, files = unpack(build("openlara", "rpi", w)[0])
        assert "HOME=/var/volatile/launchtmp ./OpenLara" in files["launch.sh"].decode()
        assert "src/platform/sdl2" in files["SOURCE.txt"].decode()
    with tempfile.TemporaryDirectory() as w:
        _, files = unpack(build("openlara", "psc", w)[0])
        assert "HOME=" not in files["launch.sh"].decode()


def test_game_data_is_not_built_for_the_pi():
    for pid in ("freedoomdata", "openarenadata"):
        r = subprocess.run([sys.executable, MKMOD, pid, "--target", "rpi", "--stage", ROOT, "--src", ROOT, "--out", ROOT],
                           capture_output=True, text=True, env=dict(os.environ, AB_ALLOW_NO_DIGEST="1"))
        assert r.returncode != 0 and "game data" in r.stderr + r.stdout


def test_an_unknown_target_is_refused():
    r = subprocess.run([sys.executable, MKMOD, "openjazz", "--target", "pi5", "--stage", ROOT, "--out", ROOT],
                       capture_output=True, text=True)
    assert r.returncode == 2 and "invalid choice" in r.stderr


# ---- ci/build.sh (what runs without the image) --------------------------------------------------------------------
def ci(*args):
    return subprocess.run(["bash", os.path.join(ROOT, "ci", "build.sh"), *args], capture_output=True, text=True, cwd=ROOT)


def test_ci_builds_no_game_data_for_the_pi():
    r = ci("--target", "rpi", "freedoomdata", "openarenadata", "liero", "xargon")
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("shared with the psc build") == 4 and "freedoomdata (rpi)" in r.stdout


def test_ci_target_can_come_after_the_port_and_must_be_known():
    assert ci("freedoomdata", "--target=rpi").returncode == 0
    r = ci("--target", "pi5", "openjazz")
    assert r.returncode == 2 and "unknown target" in r.stderr


def test_the_ports_name_no_console_flag_any_more():
    """PSC_FLAGS became ARM_FLAGS (the Pi has its own): nothing may still read the old name"""
    for pid in os.listdir(os.path.join(ROOT, "ports")):
        path = os.path.join(ROOT, "ports", pid, "build.sh")
        with open(path, encoding="utf-8") as f:
            assert "PSC_FLAGS" not in f.read(), path


def test_patches_for_one_target_say_so_in_their_name():
    name_re = re.compile(r"^\d{4}-[a-z0-9-]+(\.psc|\.rpi)?\.patch$")
    seen = {}
    for pid in os.listdir(os.path.join(ROOT, "ports")):
        folder = os.path.join(ROOT, "ports", pid, "patches")
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else ():
            assert name_re.match(name), (pid, name)
            seen[(pid, name)] = True
    assert ("tyrquake", "0001-psc-video-1280x720-abgr.psc.patch") in seen, "the console's ABGR/720p window is the console's only"
    assert ("tyrquake", "0002-sdl-gamecontroller.patch") in seen


# ---- store_item.py -------------------------------------------------------------------------------------------------
def fake_release(out):
    """what both builds leave in out/: the console's engines, the Pi's, the shared game data and one source archive each"""
    os.makedirs(out)
    for pid in sorted(os.listdir(os.path.join(ROOT, "ports"))):
        cfg = load(pid)
        ver = cfg["port"]["version"]
        if mkmod.is_package_port(cfg):
            open(os.path.join(out, "%s-%s.zip" % (pid, ver)), "wb").write(b"zip " + pid.encode())
            continue
        targets = ("psc",) if mkmod.is_data_mod(cfg) else ("psc", "rpi")
        for t in targets:
            open(os.path.join(out, mkmod.mod_filename(pid, ver, t)), "wb").write(b"mod %s %s" % (pid.encode(), t.encode()))
        open(os.path.join(out, "%s-%s-source.tar.gz" % (pid, ver)), "wb").write(b"src " + pid.encode())


def store(out, dest, *args):
    return subprocess.run([sys.executable, STORE_ITEM, "--out", out, "--dest", dest, *args], capture_output=True, text=True)


def test_the_pi_catalog_has_the_pi_engines_and_the_shared_data():
    with tempfile.TemporaryDirectory() as w:
        out = os.path.join(w, "out")
        fake_release(out)
        psc, rpi = os.path.join(w, "psc"), os.path.join(w, "rpi")
        assert store(out, psc).returncode == 0
        r = store(out, rpi, "--target", "rpi")
        assert r.returncode == 0, r.stderr
        for pid in ENGINES:
            ver = load(pid)["port"]["version"]
            with open(os.path.join(rpi, pid + ".item.json"), encoding="utf-8") as f:
                item = json.load(f)
            assert item["id"] == "pe/" + pid and item["files"] == [{"name": "%s-%s-rpi.mod" % (pid, ver)}]
            assert item["source_url"].endswith("/%s/%s-%s-source.tar.gz" % (pid, pid, ver)), "the one source archive"
            with open(os.path.join(rpi, "%s-%s-rpi.mod" % (pid, ver)), "rb") as f:
                assert f.read() == b"mod %s rpi" % pid.encode()
            with open(os.path.join(psc, pid + ".item.json"), encoding="utf-8") as f:
                assert json.load(f)["files"] == [{"name": "%s-%s.mod" % (pid, ver)}], "the console's catalog is unchanged"
        # game data: the very same package in both catalogs
        for pid in ("freedoomdata", "openarenadata"):
            ver = load(pid)["port"]["version"]
            for d in (psc, rpi):
                with open(os.path.join(d, pid + ".item.json"), encoding="utf-8") as f:
                    assert json.load(f)["files"] == [{"name": "%s-%s.mod" % (pid, ver)}]
        for pid in ("liero", "xargon"):
            ver = load(pid)["port"]["version"]
            assert os.path.isfile(os.path.join(rpi, "%s-%s.zip" % (pid, ver)))


def test_a_missing_pi_package_stops_the_pi_release():
    with tempfile.TemporaryDirectory() as w:
        out = os.path.join(w, "out")
        fake_release(out)
        ver = load("blastem")["port"]["version"]
        os.remove(os.path.join(out, "blastem-%s-rpi.mod" % ver))
        r = store(out, os.path.join(w, "rpi"), "--target", "rpi")
        assert r.returncode != 0 and "blastem-%s-rpi.mod is not in" % ver in r.stderr
        assert store(out, os.path.join(w, "psc")).returncode == 0, "the console's release does not need the Pi's files"


# ---- the Pi's first round (2026-10-07) ----------------------------------------------------------------------------
def test_openlara_without_game_data_says_so_on_the_pi_and_the_console_is_untouched():
    """OpenLara ends silently when none of the Tomb Raider files is there (Game::init -> Core::quit): on the Pi the
    launch script shows the text dialog first and does not start the engine; the console's script stays as it was"""
    with tempfile.TemporaryDirectory() as w:
        _, files = unpack(build("openlara", "rpi", w)[0])
        launch = files["launch.sh"].decode()
        lines = launch.splitlines()
        check = [l for l in lines if "sdl_text_display" in l]
        assert len(check) == 1, launch
        # every place the engine looks for the data (gameflow.h getGameVersion / getGameLevelFile) is tested
        for path in ("PSXDATA/GYM.PSX", "DATA/GYM.PHD", "GYM.PHD", "DATA/GYM.SAT", "level/1/TITLE.PSX", "level/1/TITLE.PHD"):
            assert "[ ! -e %s ]" % path in check[0], path
        assert "exit 1" in check[0] and "PSXDATA" in check[0]
        # the check comes before the engine, and `sh -n` takes the whole script
        assert lines.index(check[0]) < max(i for i, l in enumerate(lines) if "./OpenLara" in l)
        r = subprocess.run(["sh", "-n"], input=launch, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    with tempfile.TemporaryDirectory() as w:
        _, files = unpack(build("openlara", "psc", w)[0])
        assert "sdl_text_display" not in files["launch.sh"].decode()


def test_openlara_launch_script_runs_the_dialog_only_when_the_data_is_missing():
    with tempfile.TemporaryDirectory() as w:
        _, files = unpack(build("openlara", "rpi", w)[0])
        app = os.path.join(w, "app")
        bindir = os.path.join(w, "bin")
        os.makedirs(os.path.join(app, "PSXDATA"))
        os.makedirs(bindir)
        shown = os.path.join(w, "shown.txt")
        with open(os.path.join(bindir, "sdl_text_display"), "w") as f:
            f.write('#!/bin/sh\necho "$1" > "%s"\n' % shown)
        os.chmod(os.path.join(bindir, "sdl_text_display"), 0o755)
        # the engine: records that it was started
        with open(os.path.join(app, "OpenLara"), "w") as f:
            f.write('#!/bin/sh\necho started > "%s/engine.txt"\n' % w)
        os.chmod(os.path.join(app, "OpenLara"), 0o755)
        script = files["launch.sh"].decode()
        script = script.replace('. "/var/volatile/project_eris.cfg"', 'PROJECT_ERIS_PATH="%s"\nRUNTIME_LOG_PATH="%s"\nPE_RUN_DIR="%s"' % (w, w, w))
        script = script.replace('cd "/var/volatile/launchtmp"', 'cd "%s"' % app).replace("HOME=/var/volatile/launchtmp ", "")
        script = script.replace("sleep 10", "sleep 0").replace("/data/power/disable", os.path.join(w, "power"))
        with open(os.path.join(w, "launch.sh"), "w") as f:
            f.write(script)
        env = dict(os.environ)
        # no data: the dialog, no engine, exit 1
        r = subprocess.run(["sh", os.path.join(w, "launch.sh")], capture_output=True, text=True, env=env)
        assert r.returncode == 1, r.stdout + r.stderr
        assert os.path.exists(shown) and not os.path.exists(os.path.join(w, "engine.txt"))
        assert "Tomb Raider" in open(shown).read()
        # data there: the engine starts, no dialog
        os.remove(shown)
        open(os.path.join(app, "PSXDATA", "GYM.PSX"), "w").close()
        r = subprocess.run(["sh", os.path.join(w, "launch.sh")], capture_output=True, text=True, env=env)
        assert r.returncode == 0, r.stdout + r.stderr
        assert os.path.exists(os.path.join(w, "engine.txt")) and not os.path.exists(shown)
