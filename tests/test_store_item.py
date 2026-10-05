"""tools/store_item.py: the Store's pe items from port.ini and a release's out/ folder; and, when autobleem-repo's
tools are around (PE_SITE_TOOLS, default the sibling pe-site worktree), the whole publish into a temp site tree."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "tools", "store_item.py")
SITE_TOOLS = os.environ.get("PE_SITE_TOOLS") or os.path.abspath(os.path.join(ROOT, "..", "pe-site", "tools"))
SOURCE = "https://autobleem.retromenele.pl/source/commanderkeen/commanderkeen-2.4.0-1-source.tar.gz"


def release(out, ports=("commanderkeen",), source=True):
    os.makedirs(out, exist_ok=True)
    for pid in ports:
        with open(os.path.join(ROOT, "ports", pid, "port.ini"), encoding="utf-8") as f:
            ver = [ln.split("=", 1)[1] for ln in f.read().splitlines() if ln.startswith("version=")][0].strip()
        with open(os.path.join(out, "%s-%s.mod" % (pid, ver)), "wb") as f:
            f.write(b"mod " + pid.encode())
        if source:
            with open(os.path.join(out, "%s-%s-source.tar.gz" % (pid, ver)), "wb") as f:
                f.write(b"src " + pid.encode())


def run(*args, env=None):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env)


def test_descriptor_from_port_ini():
    with tempfile.TemporaryDirectory() as w:
        release(os.path.join(w, "out"))
        r = run("--out", os.path.join(w, "out"), "--dest", os.path.join(w, "d"), "--only", "commanderkeen")
        assert r.returncode == 0, r.stderr
        with open(os.path.join(w, "d", "commanderkeen.item.json"), encoding="utf-8") as f:
            d = json.load(f)
        assert d["id"] == "pe/commanderkeen" and d["kind"] == "pe"
        assert d["title"] == "Commander Genius (Keen 1)" and d["version"] == "2.4.0-1" and d["licence"] == "GPL-2.0"
        assert d["source_url"] == SOURCE
        assert d["files"] == [{"name": "commanderkeen-2.4.0-1.mod"}]  # the source archive is never a file
        assert d["image"] == "commanderkeen.png"
        with open(os.path.join(w, "d", "commanderkeen.png"), "rb") as f:
            assert f.read(8) == b"\x89PNG\r\n\x1a\n"
        assert os.path.isfile(os.path.join(w, "d", "commanderkeen-2.4.0-1.mod"))


def test_a_missing_package_stops_the_release():
    with tempfile.TemporaryDirectory() as w:
        release(os.path.join(w, "out"), ports=("commanderkeen", "openjazz", "openlara"))
        r = run("--out", os.path.join(w, "out"), "--dest", os.path.join(w, "d"))
        assert r.returncode != 0 and "tyrquake" in r.stderr and "incomplete" in r.stderr
        release(os.path.join(w, "out"), ports=("tyrquake",))
        assert run("--out", os.path.join(w, "out"), "--dest", os.path.join(w, "d2")).returncode == 0


def test_a_package_without_its_source_is_not_published():
    with tempfile.TemporaryDirectory() as w:
        release(os.path.join(w, "out"), source=False)
        r = run("--out", os.path.join(w, "out"), "--dest", os.path.join(w, "d"), "--only", "commanderkeen")
        assert r.returncode != 0 and "source" in r.stderr


def test_source_base_follows_ab_source_base():
    with tempfile.TemporaryDirectory() as w:
        release(os.path.join(w, "out"))
        env = dict(os.environ, AB_SOURCE_BASE="http://x/source/")
        r = run("--out", os.path.join(w, "out"), "--dest", os.path.join(w, "d"), "--only", "commanderkeen", env=env)
        assert r.returncode == 0, r.stderr
        with open(os.path.join(w, "d", "commanderkeen.item.json"), encoding="utf-8") as f:
            assert json.load(f)["source_url"].startswith("http://x/source/commanderkeen/")


@pytest.mark.skipif(not shutil.which("bash") or not os.path.isfile(os.path.join(SITE_TOOLS, "repo_publish.sh")),
                    reason="needs bash and autobleem-repo's tools")
def test_release_publish_into_a_temp_site_tree():
    """the site job's two steps with --local: the source archives, then the store items; the index run lists them"""
    ports = ("commanderkeen", "openjazz", "openlara", "tyrquake")
    with tempfile.TemporaryDirectory() as w, tempfile.TemporaryDirectory() as site:
        out = os.path.join(w, "out")
        release(out, ports=ports)
        dest = os.path.join(w, "store-out")
        assert run("--out", out, "--dest", dest).returncode == 0
        env = dict(os.environ, REPO_DIR=site, AB_REPO_URL="https://site")
        publish = [shutil.which("bash"), os.path.join(SITE_TOOLS, "repo_publish.sh"), "--local"]
        for pid in ports:
            archive = [os.path.join(out, f) for f in os.listdir(out)
                       if f.startswith(pid + "-") and f.endswith("-source.tar.gz")]
            r = subprocess.run(publish + ["pe-source", pid, *archive], env=env, capture_output=True, text=True)
            assert r.returncode == 0, r.stderr
        files = [os.path.join(dest, f) for f in sorted(os.listdir(dest))]
        r = subprocess.run(publish + ["store", "psc", *files], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        with open(os.path.join(site, "store", "psc", "catalog.json"), encoding="utf-8") as f:
            catalog = json.load(f)
        assert sorted(i["id"] for i in catalog["items"]) == ["pe/" + p for p in sorted(ports)]
        for i in catalog["items"]:
            assert i["kind"] == "pe" and i["files"][0]["name"].endswith(".mod") and i["files"][0]["sha256"]
            assert i["source_url"].startswith("https://autobleem.retromenele.pl/source/")
            # the address the package names is where pe-source put the archive
            assert os.path.isfile(os.path.join(site, "source", i["source_url"].split("/source/", 1)[1]))
        with open(os.path.join(site, "store", "index.html"), encoding="utf-8") as f:
            page = f.read()
        assert "PE Apps</h2>" in page and page.count("Source code") == 4
