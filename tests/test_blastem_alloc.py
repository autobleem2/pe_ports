"""BlastEm's aligned_calloc / aligned_free (util.c): the pointer given back to free() must be the one calloc made.
Upstream stores the alignment instead of the real shift, which only shows where calloc returns 8-aligned memory
(32-bit ARM glibc, the console) - on a PC it always returns 16-aligned memory and the shift is always 16. The test
compiles the two functions with the host cc against a fake calloc that returns pointers 8 mod 16 (and 0 mod 16)."""
import os
import shutil
import subprocess
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = os.path.join(ROOT, "ports", "blastem")
CC = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

HARNESS = r"""
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

static size_t fake_mod;       /* what the fake calloc's result is modulo 16: 8 or 0 */
static void *fake_ptr;        /* the pointer the fake calloc gave */
static void *fake_raw;
static void *freed;           /* the pointer aligned_free handed to free() */

static void *fake_calloc(size_t n, size_t size)
{
	size_t total = n * size;
	fake_raw = calloc(1, total + 64);
	uint8_t *base = (uint8_t *)(((uintptr_t)fake_raw + 15) & ~(uintptr_t)15);
	fake_ptr = base + fake_mod;
	return fake_ptr;
}

static void fake_free(void *p)
{
	freed = p;
}

#define calloc fake_calloc
#define free fake_free
""" + "\n/*CUT*/\n" + r"""
#undef calloc
#undef free

int main(void)
{
	size_t mods[2] = {8, 0};
	size_t sizes[3] = {1, 512 * 1024, 1024 * 1024};
	int bad = 0;
	for (int m = 0; m < 2; m++) {
		for (int s = 0; s < 3; s++) {
			fake_mod = mods[m];
			void *p = aligned_calloc(1, sizes[s], 16);
			if (((uintptr_t)p) & 15) {
				printf("not 16-aligned: mod %zu size %zu\n", mods[m], sizes[s]);
				bad = 1;
			}
			freed = NULL;
			aligned_free(p);
			if (freed != fake_ptr) {
				printf("free() got %p, calloc gave %p: mod %zu size %zu\n", freed, fake_ptr, mods[m], sizes[s]);
				bad = 1;
			}
			free(fake_raw);
		}
	}
	fake_mod = 8;
	freed = (void *)1;
	aligned_free(NULL);
	if (freed != (void *)1) {
		printf("aligned_free(NULL) reached free()\n");
		bad = 1;
	}
	return bad;
}
"""


def util_c(patches):
    """upstream/util.c with the given patches applied (a copy; the vendored source stays as it is)"""
    tmp = tempfile.mkdtemp()
    try:
        dst = os.path.join(tmp, "util.c")
        shutil.copy(os.path.join(PORT, "upstream", "util.c"), dst)
        for patch in patches:
            if patch.startswith("0004"):
                r = subprocess.run(["git", "apply", os.path.join(PORT, "patches", patch)], cwd=tmp,
                                   capture_output=True, text=True)
                assert r.returncode == 0, patch + ": " + r.stderr
        with open(dst, encoding="utf-8") as f:
            return f.read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_harness(src):
    start = src.index("void *aligned_calloc")
    end = src.index("char * alloc_concat")
    code = HARNESS.replace("/*CUT*/", src[start:end])
    tmp = tempfile.mkdtemp()
    try:
        c = os.path.join(tmp, "h.c")
        exe = os.path.join(tmp, "h.exe" if os.name == "nt" else "h")
        with open(c, "w", encoding="utf-8", newline="\n") as f:
            f.write(code)
        r = subprocess.run([CC, "-O0", "-o", exe, c], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        return subprocess.run([exe], capture_output=True, text=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


needs_cc = pytest.mark.skipif(CC is None, reason="needs a host C compiler")


@needs_cc
def test_patched_aligned_free_gives_free_the_pointer_calloc_made():
    r = run_harness(util_c(["0004-aligned-calloc-offset.patch"]))
    assert r.returncode == 0, r.stdout


@needs_cc
def test_the_unpatched_upstream_fails_the_same_test():
    """so the test above cannot pass vacuously: upstream hands free() a pointer 8 bytes early when calloc's is 8 mod 16"""
    r = run_harness(util_c([]))
    assert r.returncode != 0
    assert "free() got" in r.stdout


def test_the_port_carries_the_fix_in_its_version_and_changes():
    with open(os.path.join(PORT, "port.ini"), encoding="utf-8") as f:
        ini = f.read()
    assert "version=1.0.0-3" in ini
    assert "0004-aligned-calloc-offset.patch" in ini
