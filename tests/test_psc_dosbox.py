"""ports/dosbox/files/psc-dosbox.sh, the DOSBox start script: what it makes from the launcher's AB_PKG_* variables (or a
folder given as an argument) in a temporary folder. The program itself (dosbox) is not run here: the script only builds
the run's conf and mapper file and, with two or more start programs, asks (the answer is DB_CHOICE here)."""
import os
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FILES = os.path.join(ROOT, "ports", "dosbox", "files")
SHELLS = [s for s in ("sh", "dash", "bash") if shutil.which(s)]
pytestmark = pytest.mark.skipif(not SHELLS, reason="needs a POSIX shell")


def posix(path):
    return path.replace("\\", "/")


class Run:
    def __init__(self, w, shell, **env):
        self.w = posix(w)
        self.shell = shell
        self.pkg = self.w + "/pkg"
        self.run_dir = self.w + "/run"
        self.log = self.w + "/log"
        os.makedirs(self.pkg + "/GAME", exist_ok=True)
        os.makedirs(self.log, exist_ok=True)
        self.env = {"PATH": os.environ["PATH"], "DB_RUN": self.run_dir, "RUNTIME_LOG_PATH": self.log, "DB_APP": posix(FILES)}
        self.env.update(env)

    def source(self, pkg=None):
        """what launch.sh does: source the script, then use DB_CONF"""
        cmd = '. "%s/psc-dosbox.sh"; echo "CONF=$DB_CONF"' % posix(FILES)
        if pkg is not None:
            cmd = 'set -- "%s"; ' % pkg + cmd
        return subprocess.run([self.shell, "-c", cmd], capture_output=True, text=True, env=self.env, cwd=posix(FILES))

    def conf(self):
        with open(self.run_dir + "/dosbox.conf", encoding="utf-8") as f:
            return f.read()

    def autoexec(self):
        return self.conf().split("[autoexec]\n", 1)[1].splitlines()


@pytest.fixture(params=SHELLS)
def shell(request):
    return request.param


def test_the_script_is_posix_sh(shell):
    for name in ("psc-dosbox.sh",):
        assert subprocess.run([shell, "-n", posix(os.path.join(FILES, name))]).returncode == 0


def test_one_start_runs_at_once_and_c_is_the_package(shell):
    with tempfile.TemporaryDirectory() as w:
        r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg/", AB_PKG_FILE=posix(w) + "/pkg/GAME/GAME.EXE", AB_PKG_TITLE="Game")
        p = r.source()
        assert p.returncode == 0, p.stderr
        assert "CONF=" + r.run_dir + "/dosbox.conf" in p.stdout
        assert r.autoexec() == ['mount c "%s"' % r.pkg, "c:", "cd \\GAME", "GAME.EXE", "exit"]


def test_the_base_settings_come_first_then_the_games(shell):
    with tempfile.TemporaryDirectory() as w:
        r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg", AB_PKG_STARTS="GAME.EXE|Play", AB_PKG_SET_CYCLES="max",
                AB_PKG_SET_MEMSIZE="16", AB_PKG_SET_SOUND="none")
        assert r.source().returncode == 0
        text = r.conf()
        with open(os.path.join(FILES, "dosbox.conf"), encoding="utf-8") as f:
            assert text.startswith(f.read())  # the base file is copied as it is, the game's lines are appended
        tail = text.split("# --- this game ---", 1)[1]
        assert "[cpu]\ncycles=max\n" in tail and "[dosbox]\nmemsize=16\n" in tail
        assert "nosound=true" in tail and "sbtype=none" in tail
        assert "mapperfile=%s/mapper.txt" % r.run_dir in tail  # absolute: a relative one resolves under /tmp
        assert r.autoexec() == ['mount c "%s"' % r.pkg, "c:", "GAME.EXE", "exit"]


def test_settings_dosbox_would_choke_on_are_left_out(shell):
    with tempfile.TemporaryDirectory() as w:
        r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg", AB_PKG_STARTS="GAME.EXE|Play", AB_PKG_SET_CYCLES="max;rm -rf /",
                AB_PKG_SET_MEMSIZE="640", AB_PKG_SET_SOUND="gus")
        assert r.source().returncode == 0
        tail = r.conf().split("# --- this game ---", 1)[1]
        assert "cycles=" not in tail and "memsize=" not in tail and "sbtype" not in tail
        assert tail.count("ignored") == 3


@pytest.mark.parametrize("value,expect", [("auto", "auto"), ("fixed 8000", "fixed 8000"), ("max 90%", "max 90%"), ("3000", "3000")])
def test_cycles_values(shell, value, expect):
    with tempfile.TemporaryDirectory() as w:
        r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg", AB_PKG_STARTS="GAME.EXE|Play", AB_PKG_SET_CYCLES=value)
        assert r.source().returncode == 0
        assert "[cpu]\ncycles=%s\n" % expect in r.conf().split("# --- this game ---", 1)[1]


def test_sound_choices(shell):
    for value, must in (("sb16", "sbtype=sb16"), ("sbpro2", "sbtype=sbpro2"), ("speaker", "pcspeaker=true")):
        with tempfile.TemporaryDirectory() as w:
            r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg", AB_PKG_STARTS="GAME.EXE|Play", AB_PKG_SET_SOUND=value)
            assert r.source().returncode == 0
            assert must in r.conf().split("# --- this game ---", 1)[1]


def test_two_starts_take_the_answer(shell):
    with tempfile.TemporaryDirectory() as w:
        starts = "GAME/GAME.EXE|Play;GAME/SETUP.EXE|Setup"
        for choice, program in (("1", "GAME.EXE"), ("2", "SETUP.EXE")):
            r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg", AB_PKG_STARTS=starts, DB_CHOICE=choice)
            assert r.source().returncode == 0
            assert r.autoexec()[2:] == ["cd \\GAME", program, "exit"]


def test_the_choice_screen_has_the_labels_in_its_text(shell):
    """the PE dialog has no button captions: Cross/Circle/Square/Triangle and the titles go in the question's text"""
    with tempfile.TemporaryDirectory() as w:
        bindir = os.path.join(w, "bin")
        os.makedirs(bindir)
        tool = os.path.join(bindir, "sdl_input_text_display")
        with open(tool, "w", newline="\n") as f:
            f.write('#!/bin/sh\nprintf "%s|" "$@" > "' + posix(w) + '/dialog.args"\nexit 101\n')
        os.chmod(tool, 0o755)
        r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg", AB_PKG_TITLE="My Game", PROJECT_ERIS_PATH=posix(w),
                AB_PKG_STARTS="GAME/GAME.EXE|Play;GAME/SETUP.EXE|Setup;GAME/X.EXE|Third")
        os.makedirs(posix(w) + "/bin", exist_ok=True)
        p = r.source()
        assert p.returncode == 0, p.stderr
        with open(w + "/dialog.args") as f:
            args = f.read().split("|")
        assert args[0] == "My Game\\n \\nCross - Play\\nCircle - Setup\\nSquare - Third"  # \n are the dialog's line breaks
        assert args[-2] == "XOS"  # only the buttons that have a program
        assert r.autoexec()[2:] == ["cd \\GAME", "SETUP.EXE", "exit"]  # 101 = Circle = the second


def test_no_answer_means_the_first_program(shell):
    with tempfile.TemporaryDirectory() as w:
        bindir = os.path.join(w, "bin")
        os.makedirs(bindir)
        tool = os.path.join(bindir, "sdl_input_text_display")
        with open(tool, "w", newline="\n") as f:
            f.write("#!/bin/sh\nexit 1\n")
        os.chmod(tool, 0o755)
        r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg", PROJECT_ERIS_PATH=posix(w), AB_PKG_STARTS="A.EXE|Play;B.EXE|Setup")
        assert r.source().returncode == 0
        assert r.autoexec()[2:] == ["A.EXE", "exit"]


def test_four_starts_at_most(shell):
    with tempfile.TemporaryDirectory() as w:
        r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg", AB_PKG_STARTS="A.EXE|1;B.EXE|2;C.EXE|3;D.EXE|4;E.EXE|5", DB_CHOICE="5")
        assert r.source().returncode == 0
        assert r.autoexec()[2:] == ["A.EXE", "exit"]  # a fifth start does not exist: the first


def test_a_start_that_leaves_the_package_is_refused(shell):
    for bad in ("../x.exe|Hack", "/etc/passwd|Hack", "a/../../b.exe|Hack", "a\\b.exe|Hack"):
        with tempfile.TemporaryDirectory() as w:
            r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg", AB_PKG_STARTS=bad)
            p = r.source()
            assert p.returncode == 1 and "not a path inside the package" in p.stderr, bad


def test_the_game_file_is_the_start_when_there_are_no_starts(shell):
    with tempfile.TemporaryDirectory() as w:
        r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg", AB_PKG_FILE=posix(w) + "/pkg/GAME/PLAY.BAT")
        assert r.source().returncode == 0
        assert r.autoexec()[2:] == ["cd \\GAME", "PLAY.BAT", "exit"]


def test_a_folder_name_with_blanks_is_one_argument_of_mount(shell):
    with tempfile.TemporaryDirectory() as w:
        r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg", AB_PKG_STARTS="GAME.EXE|Play")
        with_blank = posix(w) + "/my games"
        os.makedirs(with_blank)
        r.env["AB_PKG_DIR"] = with_blank
        assert r.source().returncode == 0
        assert r.autoexec()[0] == 'mount c "%s"' % with_blank


def test_the_game_s_mapper_is_copied_and_the_default_is_the_fallback(shell):
    with tempfile.TemporaryDirectory() as w:
        mine = posix(w) + "/pkg/mapper.txt"
        r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg", AB_PKG_STARTS="GAME.EXE|Play", AB_PKG_MAPPER=mine)
        with open(mine, "w") as f:
            f.write('key_a "stick_0 button 0"\n')
        assert r.source().returncode == 0
        with open(r.run_dir + "/mapper.txt") as f:
            assert f.read() == 'key_a "stick_0 button 0"\n'
        # DOSBox may save into its mapper file: the package's own copy is never the one it writes to
        assert os.path.realpath(r.run_dir + "/mapper.txt") != os.path.realpath(mine)
        os.remove(mine)  # a mapper the package lost: the App's default, and a line in the log
        assert r.source().returncode == 0
        with open(r.run_dir + "/mapper.txt") as f, open(os.path.join(FILES, "mapper.txt")) as d:
            assert f.read() == d.read()
        with open(r.log + "/dosbox-start.log") as f:
            assert "not readable" in f.read()


def test_without_a_package_the_script_stops_and_gives_the_power_setting_back(shell):
    with tempfile.TemporaryDirectory() as w:
        r = Run(w, shell)
        p = r.source()
        assert p.returncode == 1 and "AB_PKG_DIR is not set" in p.stderr
        r.env["AB_PKG_DIR"] = posix(w) + "/gone"
        p = r.source()
        assert p.returncode == 1 and "is gone" in p.stderr


def test_the_folder_may_be_an_argument_when_the_launcher_set_nothing(shell):
    with tempfile.TemporaryDirectory() as w:
        r = Run(w, shell, AB_PKG_STARTS="GAME.EXE|Play")
        p = r.source(pkg=r.pkg)
        assert p.returncode == 0, p.stderr
        assert r.autoexec()[0] == 'mount c "%s"' % r.pkg
        # run directly it only reports
        p = subprocess.run([shell, posix(os.path.join(FILES, "psc-dosbox.sh")), r.pkg], capture_output=True, text=True,
                           env={k: v for k, v in r.env.items() if k != "DB_APP"})
        assert p.returncode == 0, p.stderr
        assert "start: GAME.EXE" in p.stdout and "conf: " + r.run_dir + "/dosbox.conf" in p.stdout


def test_a_start_inside_a_deeper_folder(shell):
    with tempfile.TemporaryDirectory() as w:
        r = Run(w, shell, AB_PKG_DIR=posix(w) + "/pkg", AB_PKG_STARTS="A/B/C.EXE|Play")
        assert r.source().returncode == 0
        assert r.autoexec()[2:] == ["cd \\A\\B", "C.EXE", "exit"]


def test_the_shipped_pad_maps_name_only_events_dosbox_has():
    """every event of a mapper file is one DOSBox's mapper knows (key_<name>), every bind a console pad's button or axis"""
    import re
    events = {"up", "down", "left", "right", "enter", "esc", "rshift", "lshift", "lctrl", "lalt", "space", "p", "s", "l",
              "b", "y", "r", "f", "d", "g"}
    for path in [os.path.join(FILES, "mapper.txt"), os.path.join(ROOT, "ports", "liero", "files", "mapper.txt"),
                 os.path.join(ROOT, "ports", "xargon", "files", "mapper.txt")]:
        with open(path, encoding="utf-8") as f:
            for line in f.read().splitlines():
                name, binds = line.split(" ", 1)
                assert name.startswith("key_") and name[4:] in events, line
                for b in re.findall(r'"([^"]*)"', binds):
                    assert re.fullmatch(r"stick_0 (button [0-9]|axis [01] [01])", b), b


def test_a_mapper_binding_buttons_above_3_needs_buttonwrap_off():
    """with buttonwrap=true the mapper creates binds only for the emulated stick's 4 buttons (sdl_mapper.cpp,
    CreateButtonBind) and silently drops `stick_0 button 4..9`: Start, Select and the shoulders were dead"""
    import re
    with open(os.path.join(FILES, "dosbox.conf"), encoding="utf-8") as f:
        wrap = re.findall(r"^buttonwrap=(\w+)", f.read(), re.M)
    assert len(wrap) == 1
    high = []
    for path in [os.path.join(FILES, "mapper.txt"), os.path.join(ROOT, "ports", "liero", "files", "mapper.txt"),
                 os.path.join(ROOT, "ports", "xargon", "files", "mapper.txt")]:
        with open(path, encoding="utf-8") as f:
            high += [b for b in re.findall(r"stick_0 button ([0-9]+)", f.read()) if int(b) >= 4]
    assert high, "the shipped mappers are expected to use the shoulder, Select and Start buttons"
    assert wrap[0] == "false", "a mapper binds button %s but buttonwrap is %s" % (high[0], wrap[0])


def test_dosbox_ships_the_drawn_icon_as_its_app_image():
    import struct
    import sys
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import configparser
    import mkmod
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(os.path.join(ROOT, "ports", "dosbox", "port.ini"), encoding="utf-8")
    png = mkmod.port_icon(cfg["port"])
    assert png == open(os.path.join(FILES, "icon.png"), "rb").read()
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", png[16:24]) == (256, 219)  # the size of the App icons (app_*/resources/icon.png)
    # a port without icon_file keeps the generated one
    assert mkmod.port_icon({"id": "x", "icon_text": "X"})[:8] == b"\x89PNG\r\n\x1a\n"


def test_xargon_ships_its_saved_setup_so_it_never_asks_keyboard_or_joystick():
    """the files the game wrote itself (digital sound, music, Keyboard) for its three episodes, laid by build.sh"""
    xargon = os.path.join(ROOT, "ports", "xargon")
    sets = []
    for n in (1, 2, 3):
        with open(os.path.join(xargon, "files", "CONFIG.XR%d" % n), "rb") as f:
            sets.append(f.read())
    assert len(sets[0]) == 232 and sets[0] == sets[1] == sets[2]
    assert sets[0][-8:] == b"\0\0\0\0\x01\0\x01\0"  # the answers the game saved
    with open(os.path.join(xargon, "build.sh"), encoding="utf-8") as f:
        assert 'CONFIG.XR$n" "$STAGE/XARGON/CONFIG.XR$n"' in f.read()


def test_xargon_pad_cross_fires_circle_jumps_triangle_stays_enter():
    """the PSC pad is SDL buttons 0 Triangle, 1 Circle, 2 Cross, 3 Square: Cross and Square fire (Space, Shift), Circle
    jumps (Alt), Triangle stays Enter - the key the shipped CONFIG.XR1-3 confirm screen is answered with"""
    binds = {}
    with open(os.path.join(ROOT, "ports", "xargon", "files", "mapper.txt"), encoding="utf-8") as f:
        for line in f.read().splitlines():
            name, bind = line.split(" ", 1)
            binds[bind.strip('"')] = name
    assert binds["stick_0 button 2"] == "key_space"
    assert binds["stick_0 button 3"] == "key_lshift"
    assert binds["stick_0 button 1"] == "key_lalt"
    assert binds["stick_0 button 0"] == "key_enter"
