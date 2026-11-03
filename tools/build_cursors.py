#!/usr/bin/env python3
"""Builds cursor-classic/ and cursor-animated/ (.cur, .ani, install.inf)."""
import os, sys
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from cursorlib import *
import designs as D

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATIC_SIZES = (32, 48, 64, 96, 128)
ANI_SIZES = (32, 48, 64, 128)
FUNCS = {s: f for s, _, f, _ in D.ALL}


def render_one(args):
    stem, N, kw, theme = args
    c = Canvas(N)
    FUNCS[stem](c, **kw)
    return render_layers(c, theme), hot_px(c.hotspot, N)


def frame_cur(stem, kw, theme):
    return build_cur([render_one((stem, N, kw, theme)) for N in ANI_SIZES])


def ani_job(a):
    return frame_cur(*a)


def make_ani(pool, stem, kws, rates, title, theme):
    frames = pool.map(ani_job, [(stem, kw, theme) for kw in kws])
    return build_ani(frames, rates, title=title)


def write(path, data, mode="wb"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode) as f:
        f.write(data)


def make_inf(scheme, curdir, files_by_key, all_files, anim):
    order = ["Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam", "NWPen", "No",
             "SizeNS", "SizeWE", "SizeNWSE", "SizeNESW", "SizeAll", "UpArrow", "Hand", "Pin", "Person"]
    key_stem = {k: s for s, _, _, k in D.ROLES}
    L = []
    A = L.append
    A("; Dark Blur Cursor - %s" % scheme)
    A("; Botao direito neste arquivo > Instalar. Depois: Configuracoes > Mouse > Ponteiro (ou main.cpl) e escolha o esquema.")
    A("[Version]")
    A('signature="$CHICAGO$"')
    A("")
    A("[DefaultInstall]")
    A("CopyFiles = Scheme.Cur")
    A("AddReg    = Scheme.Reg")
    A("")
    A("[DestinationDirs]")
    A('Scheme.Cur = 10,"%CUR_DIR%"')
    A("")
    A("[Scheme.Reg]")
    vals = ",".join("%%10%%\\%%CUR_DIR%%\\%s" % files_by_key[k] for k in order)
    A('HKCU,"Control Panel\\Cursors\\Schemes","%SCHEME_NAME%",,"' + vals + '"')
    A("")
    A("[Scheme.Cur]")
    for f in all_files:
        A(f)
    A("")
    A("[SourceDisksNames]")
    A("1 = %DISK_NAME%,,,")
    A("")
    A("[SourceDisksFiles]")
    for f in all_files:
        A("%s = 1" % f)
    A("")
    A("[Strings]")
    A('CUR_DIR     = "Cursors\\%s"' % scheme)
    A('SCHEME_NAME = "%s"' % scheme)
    A('DISK_NAME   = "Dark Blur Cursor"')
    return "\r\n".join(L) + "\r\n"


NAMES = {"dark": "Dark Blur", "light": "Light Blur"}


def build_theme(pool, theme):
    name = NAMES[theme]
    base = os.path.join(ROOT, theme)
    statics = {}
    for stem, _, _, _ in D.ALL:
        statics[stem] = build_cur(pool.map(render_one, [(stem, N, {}, theme) for N in STATIC_SIZES]))
    # ---------- classic
    d = os.path.join(base, "cursor-classic")
    for stem, data in statics.items():
        write(os.path.join(d, stem + ".cur"), data)
    files = {k: s + ".cur" for s, _, _, k in D.ROLES if k}
    allf = [s + ".cur" for s, *_ in D.ROLES] + [s + ".cur" for s, *_ in D.EXTRAS]
    with open(os.path.join(d, "install.inf"), "w", newline="", encoding="ascii") as f:
        f.write(make_inf(name, d, files, allf, False))
    # ---------- animated
    d = os.path.join(base, "cursor-animated")
    for stem, data in statics.items():
        write(os.path.join(d, stem + ".cur"), data)
    nb = 24
    anis = {
        "busy": make_ani(pool, "busy", [dict(t=i / nb) for i in range(nb)], [2] * nb, name + " - Busy", theme),
        "working": make_ani(pool, "working", [dict(t=i / nb) for i in range(nb)], [2] * nb, name + " - Working", theme),
    }
    ns = 16  # 1 rest frame (held) + 15 sweep frames
    for stem, title in (("normal", "Normal"), ("link", "Link")):
        kws = [dict(t=None)] + [dict(t=(i + 0.5) / (ns - 1)) for i in range(ns - 1)]
        anis[stem] = make_ani(pool, stem, kws, [100] + [3] * (ns - 1), "%s - %s" % (name, title), theme)
    for stem, data in anis.items():
        write(os.path.join(d, stem + ".ani"), data)
        os.remove(os.path.join(d, stem + ".cur"))
    files = {k: s + (".ani" if s in anis else ".cur") for s, _, _, k in D.ROLES}
    order = [x[0] for x in D.ROLES]
    allf = sorted(files.values(), key=lambda f: order.index(f.rsplit(".", 1)[0])) + [s + ".cur" for s, *_ in D.EXTRAS]
    with open(os.path.join(d, "install.inf"), "w", newline="", encoding="ascii") as f:
        f.write(make_inf(name + " Animated", d, files, allf, True))
    print("built", theme)


def main():
    themes = sys.argv[1:] or ["dark", "light"]
    with Pool() as pool:
        for th in themes:
            build_theme(pool, th)


if __name__ == "__main__":
    main()
