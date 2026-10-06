"""PE round 10: lzdoom's menu patch and OpenAL Soft settings, ioquake3's raw-joystick option. The patches are checked
against copies of the pinned upstream files (skipped when the submodule is not checked out); the port.ini lines the
console depends on are checked as text."""
import os
import re
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def port_file(pid, *path):
    return os.path.join(ROOT, "ports", pid, *path)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def ini(pid):
    out = {}
    section = None
    for line in read(port_file(pid, "port.ini")).splitlines():
        m = re.match(r"\[(\w+)\]", line)
        if m:
            section = m.group(1)
        elif "=" in line and not line.startswith(";"):
            k, v = line.split("=", 1)
            out[(section, k)] = v
    return out


def apply_patches(pid, files, patches):
    """Copy the upstream's `files` to a temp dir and `git apply` the patches in order; returns the result dir."""
    upstream = port_file(pid, "upstream")
    if not os.path.exists(os.path.join(upstream, files[0])):
        pytest.skip("the %s upstream submodule is not checked out" % pid)
    tmp = tempfile.mkdtemp()
    try:
        for name in files:
            dest = os.path.join(tmp, name)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(os.path.join(upstream, name), "rb") as f:
                data = f.read().replace(b"\r\n", b"\n")
            with open(dest, "wb") as f:
                f.write(data)
        for patch in patches:
            r = subprocess.run(["git", "apply", os.path.join(
                ROOT, "ports", pid, "patches", patch)], cwd=tmp, capture_output=True, text=True)
            assert r.returncode == 0, patch + ": " + r.stderr
        return tmp, {n: read(os.path.join(tmp, n)) for n in files}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_lzdoom_menu_patch_applies_and_fixes_both_bugs():
    _, src = apply_patches("lzdoom", ["src/menu/menu.cpp", "src/posix/sdl/i_input.cpp"],
                           ["0001-menu-psc-pad.patch", "0002-sdl-joystick-in-menus.patch"])
    menu = src["src/menu/menu.cpp"]
    # axis 1 is X (left/right), axis 2 is Y (up/down)
    for key, mkey in (("KEY_JOYAXIS2MINUS", "MKEY_Up"), ("KEY_JOYAXIS2PLUS", "MKEY_Down"),
                      ("KEY_JOYAXIS1MINUS", "MKEY_Left"), ("KEY_JOYAXIS1PLUS", "MKEY_Right")):
        assert re.search(key + r":\s*case KEY_JOYPOV1_\w+:\s*mkey = " + mkey + ";", menu), key
    # the pad's buttons are no longer dropped while a menu is open
    block = src["src/posix/sdl/i_input.cpp"].split("case SDL_JOYBUTTONUP:")[1].split("break;")[0]
    assert "GUICapture" not in block and "D_PostEvent" in block


def test_lzdoom_openal_is_16_bit_and_found_by_the_engine():
    conf = read(port_file("lzdoom", "files", "alsoft.conf"))
    assert re.search(r"^sample-type\s*=\s*int16$", conf, re.M)
    assert re.search(r"^frequency\s*=\s*44100$", conf, re.M)
    assert 'ALSOFT_CONF="$(pwd)/alsoft.conf"' in ini("lzdoom")[("launcher", "env")]
    assert "alsoft.conf" in read(port_file("lzdoom", "build.sh"))


def test_lzdoom_version_is_bumped():
    assert ini("lzdoom")[("port", "version")] == "3.84-3"


def test_ioquake3_raw_joystick_patch_applies():
    _, src = apply_patches("ioquake3", ["code/sdl/sdl_input.c"], ["0002-joystick-raw-option.patch"])
    c = src["code/sdl/sdl_input.c"]
    assert 'Cvar_Get( "in_joystickGamepad", "1", CVAR_ARCHIVE )' in c
    assert "in_joystickGamepad->integer && SDL_IsGameController(" in c
    assert "in_joystick->integer && in_joystickGamepad->integer" in c


def test_ioquake3_uses_the_raw_joystick_and_does_not_hide_the_pad():
    port = ini("ioquake3")
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in port[("launcher", "env")]
    args = port[("launcher", "args")]
    assert args.index("+set in_joystickGamepad 0") < args.index("+set in_joystick 1")
    assert port[("port", "version")] == "1.36-3"
