"""The Linux targets (APPS-13): `--target rpi` (Raspberry Pi 32-bit), `rpi64` (Raspberry Pi 64-bit) and `pcusb` (the PC stick,
i386) of ci/build.sh, tools/mkmod.py and tools/store_item.py.

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
# target -> (Platform line, Architecture, how SOURCE.txt names the machine)
LINUX = {
    "rpi": ("RPI armhf", "armhf", "the Raspberry Pi 32-bit"),
    "rpi64": ("RPI64 arm64", "arm64", "the Raspberry Pi 64-bit"),
    "pcusb": ("PCUSB i386", "i386", "the PC stick"),
}


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
    with open(os.path.join(stage, mkmod.launcher_value(cfg, "binary", target or "psc")), "wb") as f:
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


@pytest.mark.parametrize("target", sorted(LINUX))
@pytest.mark.parametrize("pid", ENGINES)
def test_the_package_names_its_machine(pid, target):
    platform, arch, machine = LINUX[target]
    with tempfile.TemporaryDirectory() as w:
        mod, _ = build(pid, target, w)
        ver = load(pid)["port"]["version"]
        assert os.path.basename(mod) == "%s-%s-%s.mod" % (pid, ver, target)
        control, files = unpack(mod)
        assert " Platform: %s\n" % platform in control and "SONYPSC" not in control
        assert "Architecture: %s\n" % arch in control and "Package: %s\n" % pid in control
        launch = files["launch.sh"].decode()
        # the console's power flag does not exist on the Pi: no error text from the redirections
        assert 'echo -n 2 > "/data/power/disable" 2>/dev/null\n' in launch
        assert 'echo -n 1 > "/data/power/disable" 2>/dev/null\n' in launch
        source = files["SOURCE.txt"].decode()
        assert "built for %s" % machine in source and "--target %s" % target in source
        assert files["launcher.cfg"].decode().startswith('launcher_filename="%s"' % load(pid)["launcher"]["filename"])


def test_one_source_archive_serves_both_targets():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        _, src_psc = build("tyrquake", "psc", a)
        _, src_rpi = build("tyrquake", "rpi", b)
        with tempfile.TemporaryDirectory() as c, tempfile.TemporaryDirectory() as d:
            _, src_rpi64 = build("tyrquake", "rpi64", c)
            _, src_pcusb = build("tyrquake", "pcusb", d)
            with open(src_psc, "rb") as f1, open(src_rpi, "rb") as f2, open(src_rpi64, "rb") as f3, open(src_pcusb, "rb") as f4:
                assert f1.read() == f2.read() == f3.read() == f4.read(), \
                    "the archive is the same file whichever target packed it (never replaced with other bytes)"
        with tarfile.open(src_rpi) as t:
            names = t.getnames()
            info = t.extractfile([n for n in names if n.endswith("BUILD-INFO.txt")][0]).read().decode()
        for cmake in ("rpi", "rpi64", "pcusb"):
            assert any(n.endswith("/ci/%s.cmake" % cmake) for n in names), "the toolchain file of %s is part of the source" % cmake
        for key in ("psc", "rpi", "rpi64", "pcusb"):
            assert "toolchain (%s):" % key in info
        assert "[--target psc|rpi|rpi64|pcusb]" in info


def test_a_launcher_value_can_differ_per_target():
    cfg = load("openlara")
    assert mkmod.launcher_value(cfg, "env", "psc") == ""
    for target in LINUX:  # env.linux: the key of every target but the console
        assert mkmod.launcher_value(cfg, "env", target) == "HOME=/var/volatile/launchtmp"
    assert mkmod.launcher_value(cfg, "binary", "rpi") == "OpenLara"  # no key of its own: the common one
    for target in LINUX:
        with tempfile.TemporaryDirectory() as w:
            _, files = unpack(build("openlara", target, w)[0])
            assert "HOME=/var/volatile/launchtmp ./OpenLara" in files["launch.sh"].decode()
            assert "src/platform/sdl2" in files["SOURCE.txt"].decode()
    with tempfile.TemporaryDirectory() as w:
        _, files = unpack(build("openlara", "psc", w)[0])
        assert "HOME=" not in files["launch.sh"].decode()


def test_the_engine_program_is_named_per_target():
    """ioquake3's program is named after the engine's ARCH: one name per machine, the console's and the 32-bit Pi's kept"""
    cfg = load("ioquake3")
    names = {t: mkmod.launcher_value(cfg, "binary", t) for t in ("psc", "rpi", "rpi64", "pcusb")}
    assert names == {"psc": "ioquake3.armv7l", "rpi": "ioquake3.armv7l", "rpi64": "ioquake3.aarch64", "pcusb": "ioquake3.x86"}
    with tempfile.TemporaryDirectory() as w:
        _, files = unpack(build("ioquake3", "pcusb", w)[0])
        launch = files["launch.sh"].decode()
        assert "./ioquake3.x86 " in launch and "armv7l" not in launch


@pytest.mark.parametrize("target", sorted(LINUX))
def test_game_data_is_not_built_for_the_linux_targets(target):
    for pid in ("freedoomdata", "openarenadata"):
        r = subprocess.run([sys.executable, MKMOD, pid, "--target", target, "--stage", ROOT, "--src", ROOT, "--out", ROOT],
                           capture_output=True, text=True, env=dict(os.environ, AB_ALLOW_NO_DIGEST="1"))
        assert r.returncode != 0 and "game data" in r.stderr + r.stdout


def test_an_unknown_target_is_refused():
    r = subprocess.run([sys.executable, MKMOD, "openjazz", "--target", "pi5", "--stage", ROOT, "--out", ROOT],
                       capture_output=True, text=True)
    assert r.returncode == 2 and "invalid choice" in r.stderr


# ---- ci/build.sh (what runs without the image) --------------------------------------------------------------------
def ci(*args):
    return subprocess.run(["bash", os.path.join(ROOT, "ci", "build.sh"), *args], capture_output=True, text=True, cwd=ROOT)


@pytest.mark.parametrize("target", sorted(LINUX))
def test_ci_builds_no_game_data_for_the_linux_targets(target):
    r = ci("--target", target, "freedoomdata", "openarenadata", "liero", "xargon")
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("shared with the psc build") == 4 and "freedoomdata (%s)" % target in r.stdout


def test_ci_target_can_come_after_the_port_and_must_be_known():
    assert ci("freedoomdata", "--target=rpi").returncode == 0
    r = ci("--target", "pi5", "openjazz")
    assert r.returncode == 2 and "unknown target" in r.stderr


def test_the_ports_name_no_console_flag_any_more():
    """PSC_FLAGS became ARM_FLAGS and then CPU_FLAGS (every target has its own): nothing may still read the old names"""
    for pid in os.listdir(os.path.join(ROOT, "ports")):
        path = os.path.join(ROOT, "ports", pid, "build.sh")
        with open(path, encoding="utf-8") as f:
            text = f.read()
            assert "PSC_FLAGS" not in text and "ARM_FLAGS" not in text, path


def test_patches_for_one_target_say_so_in_their_name():
    name_re = re.compile(r"^\d{4}-[a-z0-9-]+(\.psc|\.linux|\.rpi|\.rpi64|\.pcusb)?\.patch$")
    seen = {}
    for pid in os.listdir(os.path.join(ROOT, "ports")):
        folder = os.path.join(ROOT, "ports", pid, "patches")
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else ():
            assert name_re.match(name), (pid, name)
            seen[(pid, name)] = True
    assert ("tyrquake", "0001-psc-video-1280x720-abgr.psc.patch") in seen, "the console's ABGR/720p window is the console's only"
    assert ("tyrquake", "0002-sdl-gamecontroller.patch") in seen
    assert ("blastem", "0006-builtin-font.linux.patch") in seen, "Nuklear's built-in font on every Linux machine (DejaVu aborts its baker)"


def test_the_linux_patches_apply_to_every_target_but_the_console():
    """ci/build.sh's own filter: .linux.patch is applied for rpi, rpi64 and pcusb, never for psc"""
    with open(os.path.join(ROOT, "ci", "build.sh"), encoding="utf-8") as f:
        text = f.read()
    assert '*.linux.patch) [ "$TARGET" != psc ] || continue' in text
    for target in ("rpi", "rpi64", "pcusb"):
        assert '*.%s.patch) [ "$TARGET" = %s ] || continue' % (target, target) in text


def test_every_port_builds_for_every_target_in_its_script():
    """no build script may still name a Pi-only thing: `[ "$TARGET" = rpi ]` is gone (rpi64 and pcusb are Linux targets too)"""
    for pid in os.listdir(os.path.join(ROOT, "ports")):
        with open(os.path.join(ROOT, "ports", pid, "build.sh"), encoding="utf-8") as f:
            assert '"$TARGET" = rpi ]' not in f.read(), pid


# ---- store_item.py -------------------------------------------------------------------------------------------------
def fake_release(out):
    """what every build leaves in out/: the engines of each target, the shared game data and one source archive each"""
    os.makedirs(out)
    for pid in sorted(os.listdir(os.path.join(ROOT, "ports"))):
        cfg = load(pid)
        ver = cfg["port"]["version"]
        if mkmod.is_package_port(cfg):
            open(os.path.join(out, "%s-%s.zip" % (pid, ver)), "wb").write(b"zip " + pid.encode())
            continue
        targets = ("psc",) if mkmod.is_data_mod(cfg) else ("psc", "rpi", "rpi64", "pcusb")
        for t in targets:
            open(os.path.join(out, mkmod.mod_filename(pid, ver, t)), "wb").write(b"mod %s %s" % (pid.encode(), t.encode()))
        open(os.path.join(out, "%s-%s-source.tar.gz" % (pid, ver)), "wb").write(b"src " + pid.encode())


def store(out, dest, *args):
    return subprocess.run([sys.executable, STORE_ITEM, "--out", out, "--dest", dest, *args], capture_output=True, text=True)


@pytest.mark.parametrize("target", sorted(LINUX))
def test_the_catalog_has_the_targets_engines_and_the_shared_data(target):
    with tempfile.TemporaryDirectory() as w:
        out = os.path.join(w, "out")
        fake_release(out)
        psc, rpi = os.path.join(w, "psc"), os.path.join(w, target)
        assert store(out, psc).returncode == 0
        r = store(out, rpi, "--target", target)
        assert r.returncode == 0, r.stderr
        for pid in ENGINES:
            ver = load(pid)["port"]["version"]
            with open(os.path.join(rpi, pid + ".item.json"), encoding="utf-8") as f:
                item = json.load(f)
            assert item["id"] == "pe/" + pid and item["files"] == [{"name": "%s-%s-%s.mod" % (pid, ver, target)}]
            assert item["source_url"].endswith("/%s/%s-%s-source.tar.gz" % (pid, pid, ver)), "the one source archive"
            with open(os.path.join(rpi, "%s-%s-%s.mod" % (pid, ver, target)), "rb") as f:
                assert f.read() == b"mod %s %s" % (pid.encode(), target.encode())
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


@pytest.mark.parametrize("target", sorted(LINUX))
def test_a_missing_package_stops_that_targets_release(target):
    with tempfile.TemporaryDirectory() as w:
        out = os.path.join(w, "out")
        fake_release(out)
        ver = load("blastem")["port"]["version"]
        os.remove(os.path.join(out, "blastem-%s-%s.mod" % (ver, target)))
        r = store(out, os.path.join(w, target), "--target", target)
        assert r.returncode != 0 and "blastem-%s-%s.mod is not in" % (ver, target) in r.stderr
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
