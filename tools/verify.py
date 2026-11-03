#!/usr/bin/env python3
"""Parses every .cur/.ani in the pack, opens each frame with Pillow, sanity-checks hotspots."""
import os, sys, io, glob
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from cursorlib import parse_cur, parse_ani, decode_cur

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
bad = 0
TIP_ROLES = {"normal", "help", "working", "unavailable", "person", "copy", "alias", "alternate", "link", "handwriting", "location"}


def check_cur(path, data):
    global bad
    ents = parse_cur(data)
    # Pillow reads .ico natively: flip the type field to 1 so it can decode every size
    ico = bytearray(data); ico[2:4] = b"\x01\x00"
    im = Image.open(io.BytesIO(bytes(ico)))
    stem = os.path.basename(path).rsplit(".", 1)[0]
    msgs = []
    for e in ents:
        if not (0 <= e["hx"] < e["w"] and 0 <= e["hy"] < e["h"]):
            msgs.append("hotspot outside %s" % e); bad += 1
        try:
            fr = im.ico.getimage((e["w"], e["h"])).convert("RGBA")
            assert fr.size == (e["w"], e["h"])
        except Exception as ex:
            msgs.append("pillow failed %dx%d: %s" % (e["w"], e["h"], ex)); bad += 1; continue
        mine, _ = decode_cur(data, e["w"])
        a = mine[..., 3]
        if a.max() == 0:
            msgs.append("empty image"); bad += 1; continue
        ys, xs = np.nonzero(a > 40)
        d = np.sqrt((xs - e["hx"]) ** 2 + (ys - e["hy"]) ** 2).min()
        lim = 0.09 * e["w"] + 1.5  # hotspot must sit on / next to visible pixels
        if stem in TIP_ROLES or stem in ("busy",):
            pass
        if stem not in ("busy",) and d > lim:
            msgs.append("hotspot %dx%d (%d,%d) is %.1fpx from visible pixels" % (e["w"], e["h"], e["hx"], e["hy"], d)); bad += 1
    return ents, msgs


for folder in ("dark/cursor-classic", "dark/cursor-animated", "light/cursor-classic", "light/cursor-animated"):
    for p in sorted(glob.glob(os.path.join(ROOT, folder, "*"))):
        data = open(p, "rb").read()
        name = os.path.relpath(p, ROOT)
        if p.endswith(".cur"):
            ents, msgs = check_cur(p, data)
            print("OK  %-34s sizes=%s hotspots=%s" % (name, [e["w"] for e in ents], [(e["hx"], e["hy"]) for e in ents][:1] + ["..."]))
            for m in msgs: print("   !!", m)
        elif p.endswith(".ani"):
            info = parse_ani(data)
            h = info["anih"]
            assert h["nFrames"] == len(info["frames"]), "frame count mismatch"
            assert len(info["rate"]) == h["nSteps"], "rate count mismatch"
            # run each embedded cur through the .cur check
            import re
            # find the icon chunks again for Pillow verification
            off = data.find(b"fram") + 4
            n = 0
            while off < len(data):
                cid = data[off:off + 4]; import struct; sz = struct.unpack("<I", data[off + 4:off + 8])[0]
                assert cid == b"icon"
                ents, msgs = check_cur(p + "#%d" % n, data[off + 8:off + 8 + sz])
                for m in msgs: print("   !!", name, n, m)
                off += 8 + sz + (sz & 1); n += 1
            print("OK  %-34s frames=%d steps=%d rate[0..3]=%s sizes=%s total=%.2fs" % (
                name, h["nFrames"], h["nSteps"], info["rate"][:3], [e["w"] for e in info["frames"][0]], sum(info["rate"]) / 60))
        elif p.endswith(".inf"):
            t = open(p, "rb").read()
            assert b"\r\n" in t and all(b < 128 for b in t)
            print("OK  %-34s (ascii, CRLF)" % name)

# ---- cross-theme hotspot parity, inf scheme names, click frames
import re, struct as _st
for sub in ("cursor-classic", "cursor-animated"):
    for p in sorted(glob.glob(os.path.join(ROOT, "dark", sub, "*.cur"))):
        q = p.replace("/dark/", "/light/")
        a, b = parse_cur(open(p, "rb").read()), parse_cur(open(q, "rb").read())
        if [(e["w"], e["hx"], e["hy"]) for e in a] != [(e["w"], e["hx"], e["hy"]) for e in b]:
            print("!! hotspot/size mismatch dark vs light:", p); bad += 1
for theme, name in (("dark", "Dark Blur"), ("light", "Light Blur")):
    for sub, sch in (("cursor-classic", name), ("cursor-animated", name + " Animated")):
        t = open(os.path.join(ROOT, theme, sub, "install.inf")).read()
        ok = ('SCHEME_NAME = "%s"' % sch) in t and ('CUR_DIR     = "Cursors\\%s"' % sch) in t
        listed = re.findall(r"^([\w\-]+\.(?:cur|ani))\s*$", t, re.M)
        missing = [f for f in listed if not os.path.exists(os.path.join(ROOT, theme, sub, f))]
        print("%s %-24s scheme=%r files=%d missing=%s" % ("OK " if ok and not missing else "!! ", theme + "/" + sub, sch, len(listed), missing))
        bad += (not ok) + len(missing)
for p in sorted(glob.glob(os.path.join(ROOT, "click-animations", "*.bgra"))):
    d = np.fromfile(p, np.uint8).reshape(40, 160, 160, 4)
    prem = bool((d[..., :3] <= d[..., 3:4]).all())
    ok = d.size == 40 * 160 * 160 * 4 and prem and d[..., 3].max() > 150 and d[:, 0, 0, 3].max() == 0
    print("%s %-30s premultiplied=%s corners_clear=%s" % ("OK " if ok else "!! ", os.path.relpath(p, ROOT), prem, d[:, 0, 0, 3].max() == 0))
    bad += (not ok)
print("PROBLEMS:", bad)
sys.exit(1 if bad else 0)

