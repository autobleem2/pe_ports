"""BlastEm on the console: the sound device takes only 16-bit samples, so the defaults patch must make BlastEm ask
for s16 (it quits at start-up when the sound device refuses its format). The patches apply to the vendored upstream."""
import os
import shutil
import subprocess
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = os.path.join(ROOT, "ports", "blastem")


def patched(files, patches):
    tmp = tempfile.mkdtemp()
    try:
        for name in files:
            shutil.copy(os.path.join(PORT, "upstream", name), os.path.join(tmp, name))
        for patch in patches:
            r = subprocess.run(["git", "apply", os.path.join(PORT, "patches", patch)], cwd=tmp,
                               capture_output=True, text=True)
            assert r.returncode == 0, patch + ": " + r.stderr
        return {n: open(os.path.join(tmp, n), encoding="utf-8").read() for n in files}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_defaults_ask_for_16_bit_sound():
    cfg = patched(["default.cfg"], ["0002-psc-defaults.patch"])["default.cfg"]
    audio = cfg.split("audio {")[1].split("}")[0]
    lines = [ln.split() for ln in audio.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    assert ["format", "s16"] in lines
    assert ["format", "f32"] not in lines


def test_pad_mapping_patch_applies_and_its_comment_is_right():
    src = patched(["render_sdl.c"], ["0001-psc-pad-mapping.patch"])["render_sdl.c"]
    assert "SDL's\n//database knows nothing of it" not in src
    assert "has a mapping for it too" in src
