"""The PC stick target: `--target pcusb` of ci/build.sh and tools/mkmod.py (32-bit x86, i386, no SSE2).

Same package format as the other targets with its own Platform line and file name; one source archive; the patches and
port.ini keys of the other targets never reach it. No compiler and no network: ci/build.sh runs here over a made-up port
in a copy of the tree, tools/mkmod.py over made-up staged files."""
import os
import sys
import tarfile
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import test_rpi_target as base  # noqa: E402
import test_rpi64_target as r64  # noqa: E402
from test_rpi64_target import fake_tree, run_fake, report  # noqa: E402,F401

mkmod = base.mkmod
ROOT = base.ROOT
PORTS_PCUSB = ("blastem", "commanderkeen", "ioquake3", "openlara")


# ---- tools/mkmod.py ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("pid", PORTS_PCUSB)
def test_the_pcusb_package_names_its_machine(pid):
    with tempfile.TemporaryDirectory() as w:
        mod, _ = base.build(pid, "pcusb", w)
        ver = base.load(pid)["port"]["version"]
        assert os.path.basename(mod) == "%s-%s-pcusb.mod" % (pid, ver)
        control, files = base.unpack(mod)
        assert " Platform: PCUSB i386\n" in control and "SONYPSC" not in control and "armhf" not in control
        assert "Architecture: i386\n" in control and "Package: %s\n" % pid in control
        source = files["SOURCE.txt"].decode()
        assert "built for the PC stick" in source and "--target pcusb" in source and "Raspberry" not in source


def test_mod_filename_per_target():
    assert mkmod.mod_filename("x", "1.0", "pcusb") == "x-1.0-pcusb.mod"
    assert mkmod.TARGETS["pcusb"] == ("PCUSB i386", "-pcusb") and mkmod.ARCH["pcusb"] == "i386"


def test_the_other_packages_keep_their_control_lines():
    for target, platform, arch in (("psc", "SONYPSC armhf", "armhf"), ("rpi", "RPI armhf", "armhf"),
                                   ("rpi64", "RPI arm64", "arm64")):
        with tempfile.TemporaryDirectory() as w:
            control, _ = base.unpack(base.build("openjazz", target, w)[0])
            assert " Platform: %s\n" % platform in control and "Architecture: %s\n" % arch in control


def test_one_source_archive_serves_pcusb_too():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        _, src_psc = base.build("tyrquake", "psc", a)
        _, src_pc = base.build("tyrquake", "pcusb", b)
        with open(src_psc, "rb") as f1, open(src_pc, "rb") as f2:
            assert f1.read() == f2.read()
        with tarfile.open(src_pc) as t:
            names = t.getnames()
            info = t.extractfile([n for n in names if n.endswith("BUILD-INFO.txt")][0]).read().decode()
        assert any(n.endswith("/ci/pcusb.cmake") for n in names)
        assert "toolchain (pcusb):" in info and "-mno-sse2" in info


def test_pcusb_launcher_keys_do_not_fall_back_to_the_other_machines():
    cfg = base.load("ioquake3")
    assert mkmod.launcher_value(cfg, "binary", "pcusb") == "ioquake3.x86"
    assert mkmod.launcher_value(cfg, "binary", "rpi64") == "ioquake3.aarch64"
    assert mkmod.launcher_value(cfg, "binary", "psc") == "ioquake3.armv7l"
    cfg = base.load("openlara")
    assert mkmod.launcher_value(cfg, "env", "pcusb") == "HOME=/var/volatile/launchtmp"
    assert mkmod.launcher_value(cfg, "pre", "pcusb") == mkmod.launcher_value(cfg, "pre", "rpi")
    assert mkmod.launcher_value(cfg, "pre", "psc") == ""


def test_pcusb_changes_come_from_changes_pcusb_only():
    cfg = base.load("blastem")
    text = mkmod.source_txt(cfg, "http://x/s.tar.gz", "0" * 64, "sha256:0", "img", "pcusb")
    assert "0006-builtin-font.pcusb.patch" in text and "0006-builtin-font.rpi" not in text
    for target in ("rpi", "rpi64"):
        other = mkmod.source_txt(cfg, "http://x/s.tar.gz", "0" * 64, "sha256:0", "img", target)
        assert "pcusb" not in other.replace("--target pcusb", "")


def test_game_data_is_not_built_for_pcusb():
    import subprocess
    r = subprocess.run([sys.executable, base.MKMOD, "freedoomdata", "--target", "pcusb", "--stage", ROOT, "--src", ROOT,
                        "--out", ROOT], capture_output=True, text=True, env=dict(os.environ, AB_ALLOW_NO_DIGEST="1"))
    assert r.returncode != 0 and "game data" in r.stderr + r.stdout


# ---- ci/build.sh over a made-up port ---------------------------------------------------------------------------------
def test_pcusb_selects_only_the_common_and_its_own_patches(fake_tree):
    import subprocess  # noqa: F401
    pdir = os.path.join(fake_tree, "ports", "fake", "patches")
    with open(os.path.join(pdir, "0005-pcusb-only.pcusb.patch"), "w") as f:
        f.write("--- a/pcusb-only.txt\n+++ b/pcusb-only.txt\n@@ -0,0 +1 @@\n+pcusb-only\n")
    r = run_fake(fake_tree, "--target", "pcusb")
    assert r.returncode == 0, r.stdout + r.stderr
    got = report(r)["SRC_FILES"].split()
    assert "all.txt" in got and "pcusb-only.txt" in got, got
    assert not {"psc-only.txt", "rpi-only.txt", "rpi64-only.txt"} & set(got), got
    for target, other in (("psc", "psc-only.txt"), ("rpi", "rpi-only.txt"), ("rpi64", "rpi64-only.txt")):
        got = report(run_fake(fake_tree, "--target", target))["SRC_FILES"].split()
        assert other in got and "pcusb-only.txt" not in got, (target, got)


def test_pcusb_build_environment(fake_tree):
    r = run_fake(fake_tree, "--target", "pcusb")
    rep = report(r)
    assert rep["CC"] == "i386-gcc"
    assert "-m32" in rep["ARM_FLAGS"] and "-march=i686" in rep["ARM_FLAGS"]
    assert "-mno-sse2" in rep["ARM_FLAGS"] and "-mno-sse " in rep["ARM_FLAGS"] + " " and "mfpu" not in rep["ARM_FLAGS"]
    assert rep["PKG_CONFIG_LIBDIR"].startswith("/usr/lib/i386-linux-gnu/pkgconfig")
    assert rep["ZLIB_A"] == "/usr/lib/i386-linux-gnu/libz.a" and rep["ZLIB_INC"] == "/usr/include"
    assert rep["TOOLCHAIN_CMAKE"].endswith("/ci/pcusb.cmake")
    assert rep["SHIM"] == 'exec pkg-config sdl2 "$@"'
    assert "MKMOD fake --target pcusb " in r.stdout
    shim = os.path.join(fake_tree, "build", "shim")
    with open(os.path.join(shim, "i386-gcc")) as f:
        text = f.read()
        assert "exec gcc -m32 " in text or "exec i686-linux-gnu-gcc " in text
    with open(os.path.join(shim, "i386-g++")) as f:
        text = f.read()
        assert "exec g++ -m32 " in text or "exec i686-linux-gnu-g++ " in text


def test_env_variable_selects_pcusb(fake_tree):
    import subprocess
    r = subprocess.run(["bash", os.path.join(fake_tree, "ci", "build.sh"), "fake"], capture_output=True, text=True,
                       cwd=fake_tree, env=dict(os.environ, AB_PE_TARGET="pcusb"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "MKMOD fake --target pcusb " in r.stdout


def test_the_other_environments_are_unchanged(fake_tree):
    rep = report(run_fake(fake_tree, "--target", "rpi64"))
    assert rep["CC"] == "aarch64-linux-gnu-gcc" and rep["ARM_FLAGS"] == "-march=armv8-a"
    rep = report(run_fake(fake_tree, "--target", "rpi"))
    assert rep["CC"] == "arm-linux-gnueabihf-gcc" and rep["ARM_FLAGS"] == "-mfloat-abi=hard -march=armv7-a -mfpu=neon-vfpv4"


def test_an_unknown_target_is_refused_and_names_pcusb(fake_tree):
    r = run_fake(fake_tree, "--target", "amiga")
    assert r.returncode == 2 and "pcusb" in r.stderr


def test_ci_builds_no_game_data_for_pcusb():
    r = base.ci("--target", "pcusb", "freedoomdata", "liero")
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("shared with the psc build") == 2 and "freedoomdata (pcusb)" in r.stdout


def _text(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def test_check_binary_knows_i386_and_refuses_sse():
    text = _text("ci", "build.sh")
    assert "ELF 32-bit LSB.*Intel 80386" in text and "objdump -d" in text and "xmm" in text
    assert "needs a glibc newer than 2.36" in text


def test_pcusb_toolchain_file_is_i386_without_sse():
    text = _text("ci", "pcusb.cmake")
    assert "i386-gcc" in text and "i386-g++" in text and "i386-linux-gnu" in text
    assert "-m32" in text and "-mno-sse2" in text and "aarch64" not in text and "gnueabihf" not in text


def test_pcusb_patch_files_are_copies_of_the_pi_ones():
    for port, name in (("blastem", "0006-builtin-font"), ("openlara", "0002-sdl2-log-errors")):
        folder = os.path.join(ROOT, "ports", port, "patches")
        pi = name + (".rpi64.patch" if port == "blastem" else ".rpi.patch")
        with open(os.path.join(folder, pi), "rb") as a, open(os.path.join(folder, name + ".pcusb.patch"), "rb") as b:
            assert a.read() == b.read()


def test_ports_pick_the_x86_build_on_pcusb():
    assert 'if [ "$TARGET" = pcusb ]; then arch=x86 isa=; fi' in _text("ports", "ioquake3", "build.sh")
    assert "cpu=i386 isa=" in _text("ports", "blastem", "build.sh")
    assert '[ "$TARGET" = pcusb ]' in _text("ports", "openlara", "build.sh")
    assert "pcusb" not in _text("ports", "lzdoom", "build.sh")


def test_the_workflow_does_not_publish_pcusb_yet():
    assert "pcusb" not in _text(".github", "workflows", "build.yml")
