"""LZDoom's pad files (ports/lzdoom/files/psc): the joystick is switched on, and every binding names a key the
engine has (its own key-name table, c_bind.cpp of the pinned upstream when it is checked out) and a layout that is
complete: each of the console pad's ten buttons and four d-pad directions does something."""
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PSC = os.path.join(ROOT, "ports", "lzdoom", "files", "psc")
BIND = os.path.join(ROOT, "ports", "lzdoom", "upstream", "src", "c_bind.cpp")


def read(name):
    with open(os.path.join(PSC, name), encoding="utf-8") as f:
        return f.read()


def binds(name):
    out = {}
    for line in read(name).splitlines():
        m = re.match(r'\s*bind\s+(\S+)\s+"([^"]*)"', line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def test_the_joystick_is_switched_on():
    assert re.search(r"^set use_joystick true$", read("common.cfg"), re.M)


def test_the_console_pad_layout_is_complete():
    b = binds("pad-psc.cfg")
    for key in ["Joy%d" % i for i in range(1, 11)] + ["Axis1Minus", "Axis1Plus", "Axis2Minus", "Axis2Plus"]:
        assert b.get(key), key + " is not bound"
    # Sony's order: Joy3 Cross fires (and is OK in the menus), Joy10 Start opens the menu
    assert b["Joy3"] == "+attack" and b["Joy10"] == "menu_main"
    assert b["Axis2Minus"] == "+forward" and b["Axis2Plus"] == "+back"
    assert b["Axis1Minus"] == "+left" and b["Axis1Plus"] == "+right"
    # the d-pad is bound only through the axes' buttons (psc-pad.sh gives the axes no game axis)


@pytest.mark.skipif(not os.path.exists(BIND), reason="the lzdoom upstream submodule is not checked out")
def test_every_bound_key_exists_in_the_engine():
    with open(BIND, encoding="utf-8", errors="replace") as f:
        src = f.read()
    names = set(re.findall(r'"([A-Za-z0-9_]+)"', src))
    for cfg in ("pad-psc.cfg", "pad-x360-analog.cfg", "pad-x360-dpad.cfg"):
        for key in binds(cfg):
            assert key in names, "%s: %s is not a key name of the engine" % (cfg, key)
