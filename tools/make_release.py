#!/usr/bin/env python3
"""Creates release zips: one per theme (dark / light) and a full one. Usage: make_release.py [outdir] [version]"""
import os, sys, zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "dist")
VER = sys.argv[2] if len(sys.argv) > 2 else "v1.0.0"
COMMON = ["click-animations", "preview", "README.md", "LICENSE"]


def add(z, rel, prefix):
    p = os.path.join(ROOT, rel)
    if os.path.isfile(p):
        z.write(p, prefix + "/" + rel)
        return
    for d, _, fs in os.walk(p):
        for f in sorted(fs):
            if f == "settings.ini" or "__pycache__" in d:
                continue
            fp = os.path.join(d, f)
            z.write(fp, prefix + "/" + os.path.relpath(fp, ROOT).replace(os.sep, "/"))


def make(name, parts):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "%s-%s.zip" % (name, VER))
    prefix = name
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for r in parts:
            add(z, r, prefix)
    assert zipfile.ZipFile(path).testzip() is None
    print("%-44s %6.1f MB" % (path, os.path.getsize(path) / 1e6))


make("Dark-Blur-Cursor-dark", ["dark"] + COMMON)
make("Dark-Blur-Cursor-light", ["light"] + COMMON)
make("Dark-Blur-Cursor-full", ["dark", "light", "tools"] + COMMON + [".gitignore"])
