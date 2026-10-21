"""The Raspberry Pi 64-bit target: `--target rpi64` of ci/build.sh and tools/mkmod.py.

Same package format as the other targets with its own Platform line and file name; one source archive; the `.rpi.patch`
files and the `rpi` keys of port.ini never reach it. No compiler and no network: ci/build.sh runs here over a made-up
port in a copy of the tree, tools/mkmod.py over made-up staged files."""
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(__file__))
import test_rpi_target as base  # noqa: E402

mkmod = base.mkmod
ROOT = base.ROOT
PORTS64 = ("blastem", "commanderkeen", "dosbox", "ioquake3", "lzdoom", "openjazz", "openlara", "tyrquake")


# ---- tools/mkmod.py ------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("pid", PORTS64)
def test_the_rpi64_package_names_its_machine(pid):
    with tempfile.TemporaryDirectory() as w:
        mod, _ = base.build(pid, "rpi64", w)
        ver = base.load(pid)["port"]["version"]
        assert os.path.basename(mod) == "%s-%s-rpi64.mod" % (pid, ver)
        control, files = base.unpack(mod)
        assert " Platform: RPI arm64\n" in control and "SONYPSC" not in control and "armhf" not in control
        assert "Architecture: arm64\n" in control and "Package: %s\n" % pid in control
        launch = files["launch.sh"].decode()
        assert 'echo -n 2 > "/data/power/disable" 2>/dev/null\n' in launch
        source = files["SOURCE.txt"].decode()
        assert "built for the Raspberry Pi 64-bit" in source and "--target rpi64" in source


def test_mod_filename_per_target():
    assert mkmod.mod_filename("x", "1.0", "psc") == "x-1.0.mod"
    assert mkmod.mod_filename("x", "1.0", "rpi") == "x-1.0-rpi.mod"
    assert mkmod.mod_filename("x", "1.0", "rpi64") == "x-1.0-rpi64.mod"


def test_the_other_packages_keep_their_control_lines():
    for target, platform in (("psc", "SONYPSC armhf"), ("rpi", "RPI armhf")):
        with tempfile.TemporaryDirectory() as w:
            control, _ = base.unpack(base.build("openjazz", target, w)[0])
            assert " Platform: %s\n" % platform in control and "Architecture: armhf\n" in control


def test_one_source_archive_serves_rpi64_too():
    with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
        _, src_psc = base.build("tyrquake", "psc", a)
        _, src_64 = base.build("tyrquake", "rpi64", b)
        with open(src_psc, "rb") as f1, open(src_64, "rb") as f2:
            assert f1.read() == f2.read()
        with tarfile.open(src_64) as t:
            names = t.getnames()
            info = t.extractfile([n for n in names if n.endswith("BUILD-INFO.txt")][0]).read().decode()
        assert any(n.endswith("/ci/rpi64.cmake") for n in names)
        assert "toolchain (rpi64):" in info and "[--target psc|rpi|rpi64|pcusb]" in info


def test_rpi64_launcher_keys_do_not_fall_back_to_rpi():
    cfg = base.load("openlara")
    cfg["launcher"].pop("env.rpi64", None)  # a port with env.rpi but no env.rpi64
    assert mkmod.launcher_value(cfg, "env", "rpi") == "HOME=/var/volatile/launchtmp"
    assert mkmod.launcher_value(cfg, "env", "rpi64") == ""
    assert mkmod.launcher_value(cfg, "binary", "rpi64") == "OpenLara"  # the common key
    cfg["launcher"]["args.rpi64"] = "-x"
    assert mkmod.launcher_value(cfg, "args", "rpi64") == "-x"


def test_rpi64_changes_come_from_changes_rpi64_only():
    cfg = base.load("blastem")
    text = mkmod.source_txt(cfg, "http://x/s.tar.gz", "0" * 64, "sha256:0", "img", "rpi64")
    assert "0006-builtin-font.rpi64.patch" in text and "0006-builtin-font.rpi.patch" not in text
    text = mkmod.source_txt(cfg, "http://x/s.tar.gz", "0" * 64, "sha256:0", "img", "rpi")
    assert "0006-builtin-font.rpi.patch" in text and "rpi64" not in text.replace("--target rpi64", "")


def test_game_data_is_not_built_for_rpi64():
    r = subprocess.run([sys.executable, base.MKMOD, "freedoomdata", "--target", "rpi64", "--stage", ROOT, "--src", ROOT,
                        "--out", ROOT], capture_output=True, text=True, env=dict(os.environ, AB_ALLOW_NO_DIGEST="1"))
    assert r.returncode != 0 and "game data" in r.stderr + r.stdout


# ---- ci/build.sh over a made-up port ---------------------------------------------------------------------------------
FAKE_BUILD = '''port_build() {
    { echo "TARGET=$TARGET"; echo "CC=$CC"; echo "STRIP=$STRIP"; echo "ARM_FLAGS=$ARM_FLAGS"
      echo "PKG_CONFIG_LIBDIR=$PKG_CONFIG_LIBDIR"; echo "ZLIB_A=$ZLIB_A"; echo "ZLIB_INC=$ZLIB_INC"
      echo "TOOLCHAIN_CMAKE=$TOOLCHAIN_CMAKE"; echo "SHIM=$(cat "$ROOT/build/shim/sdl2-config" 2>/dev/null | tail -1)"
      echo "SRC_FILES=$(cd "$SRC" && echo *)"; } > "$STAGE/report.txt"
}
'''


@pytest.fixture()
def fake_tree():
    with tempfile.TemporaryDirectory() as w:
        for d in ("ci", "tools"):
            os.makedirs(os.path.join(w, d))
        shutil.copy(os.path.join(ROOT, "ci", "build.sh"), os.path.join(w, "ci", "build.sh"))
        with open(os.path.join(w, "tools", "mkmod.py"), "w") as f:  # stands in for the packer: shows what it was asked for
            f.write("import shutil, sys\nprint('MKMOD', *sys.argv[1:])\n"
                    "stage = sys.argv[sys.argv.index('--stage') + 1]\n"
                    "print(open(stage + '/report.txt').read())\n")
        port = os.path.join(w, "ports", "fake")
        os.makedirs(os.path.join(port, "upstream"))
        os.makedirs(os.path.join(port, "patches"))
        with open(os.path.join(port, "upstream", "main.c"), "w") as f:
            f.write("base\n")
        # kind=data skips check_binary (there is no cross readelf here)
        with open(os.path.join(port, "port.ini"), "w") as f:
            f.write("[port]\nid=fake\nkind=data\n")
        with open(os.path.join(port, "build.sh"), "w") as f:
            f.write(FAKE_BUILD)
        for name in ("0001-all.patch", "0002-psc-only.psc.patch", "0003-rpi-only.rpi.patch", "0004-rpi64-only.rpi64.patch"):
            tag = name.split("-", 1)[1].split(".")[0]
            with open(os.path.join(port, "patches", name), "w") as f:
                f.write("--- a/%s.txt\n+++ b/%s.txt\n@@ -0,0 +1 @@\n+%s\n" % (tag, tag, tag))
        yield w


def run_fake(w, *args, env=None):
    return subprocess.run(["bash", os.path.join(w, "ci", "build.sh"), *args, "fake"], capture_output=True, text=True, cwd=w,
                          env=dict(os.environ, AB_PE_TARGET="", **(env or {})))


def report(r):
    return dict(l.split("=", 1) for l in r.stdout.splitlines() if re.match(r"^[A-Z_]+=", l))


def test_rpi64_selects_only_the_common_and_its_own_patches(fake_tree):
    r = run_fake(fake_tree, "--target", "rpi64")
    assert r.returncode == 0, r.stdout + r.stderr
    got = report(r)["SRC_FILES"].split()
    assert "all.txt" in got and "rpi64-only.txt" in got
    assert "rpi-only.txt" not in got and "psc-only.txt" not in got, got
    assert "patch: ports/fake/patches/0003-rpi-only.rpi.patch" not in r.stdout


def test_the_other_targets_do_not_get_the_rpi64_patch(fake_tree):
    for target, want in (("psc", "psc-only.txt"), ("rpi", "rpi-only.txt")):
        r = run_fake(fake_tree, "--target", target)
        assert r.returncode == 0, r.stdout + r.stderr
        got = report(r)["SRC_FILES"].split()
        assert "all.txt" in got and want in got and "rpi64-only.txt" not in got, (target, got)


def test_rpi64_build_environment(fake_tree):
    r = run_fake(fake_tree, "--target", "rpi64")
    rep = report(r)
    assert rep["CC"] == "aarch64-linux-gnu-gcc" and rep["STRIP"] == "aarch64-linux-gnu-strip"
    assert "mfloat-abi" not in rep["ARM_FLAGS"] and "mfpu" not in rep["ARM_FLAGS"] and "neon" not in rep["ARM_FLAGS"]
    assert rep["PKG_CONFIG_LIBDIR"].startswith("/usr/lib/aarch64-linux-gnu/pkgconfig")
    assert rep["ZLIB_A"] == "/usr/lib/aarch64-linux-gnu/libz.a" and rep["ZLIB_INC"] == "/usr/include"
    assert rep["TOOLCHAIN_CMAKE"].endswith("/ci/rpi64.cmake")
    assert rep["SHIM"] == 'exec pkg-config sdl2 "$@"'
    assert "MKMOD fake --target rpi64 " in r.stdout


def test_env_variable_selects_rpi64(fake_tree):
    r = subprocess.run(["bash", os.path.join(fake_tree, "ci", "build.sh"), "fake"], capture_output=True, text=True,
                       cwd=fake_tree, env=dict(os.environ, AB_PE_TARGET="rpi64"))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "MKMOD fake --target rpi64 " in r.stdout


def test_rpi_environment_is_unchanged(fake_tree):
    rep = report(run_fake(fake_tree, "--target", "rpi"))
    assert rep["CC"] == "arm-linux-gnueabihf-gcc"
    assert rep["ARM_FLAGS"] == "-mfloat-abi=hard -march=armv7-a -mfpu=neon-vfpv4"
    assert rep["PKG_CONFIG_LIBDIR"] == "/usr/lib/arm-linux-gnueabihf/pkgconfig:/usr/share/pkgconfig"
    assert rep["ZLIB_A"] == "/usr/lib/arm-linux-gnueabihf/libz.a"
    assert rep["TOOLCHAIN_CMAKE"].endswith("/ci/rpi.cmake")


def test_ci_builds_no_game_data_for_rpi64():
    r = base.ci("--target", "rpi64", "freedoomdata", "liero")
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("shared with the psc build") == 2 and "freedoomdata (rpi64)" in r.stdout


def test_check_binary_knows_aarch64():
    with open(os.path.join(ROOT, "ci", "build.sh"), encoding="utf-8") as f:
        text = f.read()
    assert "ELF 64-bit LSB.*ARM aarch64" in text and "ELF 32-bit LSB.*ARM" in text
    assert "$PE_TRIPLE-readelf" in text and "GLIBC_2" in text


def test_rpi64_toolchain_file_is_aarch64():
    with open(os.path.join(ROOT, "ci", "rpi64.cmake"), encoding="utf-8") as f:
        text = f.read()
    assert "aarch64-linux-gnu-gcc" in text and "aarch64-linux-gnu-g++" in text
    assert "mfpu" not in text.replace("no float-ABI or FPU switch", "") and "gnueabihf" not in text


def test_blastem_build_has_no_32bit_switch_on_rpi64():
    with open(os.path.join(ROOT, "ports", "blastem", "build.sh"), encoding="utf-8") as f:
        text = f.read()
    assert 'if [ "$TARGET" = rpi64 ]; then cpu=aarch64 isa=; elif [ "$TARGET" = pcusb ]; then cpu=i386 isa=; else cpu=armv7 isa=-marm; fi' in text


def test_rpi64_patch_files_are_named_for_one_target():
    folder = os.path.join(ROOT, "ports", "blastem", "patches")
    with open(os.path.join(folder, "0006-builtin-font.rpi.patch"), "rb") as a, \
            open(os.path.join(folder, "0006-builtin-font.rpi64.patch"), "rb") as b:
        assert a.read() == b.read()


def test_the_workflow_does_not_publish_rpi64_yet():
    with open(os.path.join(ROOT, ".github", "workflows", "build.yml"), encoding="utf-8") as f:
        assert "rpi64" not in f.read()
