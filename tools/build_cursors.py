#!/usr/bin/env python3
"""Builds cursor-classic/ and cursor-animated/ (.cur, .ani, install.inf)."""
import os, sys, math
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
from cursorlib import *
import designs as D

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATIC_SIZES = (32, 48, 64, 96, 128)
ANI_SIZES = (32, 48, 64)
FUNCS = {s: f for s, _, f, _ in D.ALL}


def render_one(args):
    stem, N, kw, theme = args[:4]
    phase, pulse = (args[4], args[5]) if len(args) > 4 else (None, 1.0)
    c = Canvas(N)
    FUNCS[stem](c, **kw)
    return render_layers(c, theme, phase, pulse), hot_px(c.hotspot, N)


def frame_cur(stem, kw, theme, phase, pulse):
    return build_cur([render_one((stem, N, kw, theme, phase, pulse)) for N in ANI_SIZES])


def ani_job(a):
    return frame_cur(*a)


def make_ani(pool, stem, kws, rates, title, theme):
    """kws: per-frame design kwargs; a white shimmer sweeps across once per loop and the outline glow pulses once."""
    n = len(kws)
    jobs = [(stem, kw, theme, i / n, 1.0 + 0.55 * math.sin(2 * math.pi * i / n)) for i, kw in enumerate(kws)]
    return build_ani(pool.map(ani_job, jobs), rates, title=title)


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
    # ---------- animated: EVERY cursor is an .ani with a visible neon colour cycle + brightness pulse
    d = os.path.join(base, "cursor-animated")
    nb = 24
    for stem, label, fn, key in D.ALL:
        if stem in ("busy", "working"):
            kws, rates = [dict(t=i / nb) for i in range(nb)], [2] * nb          # spinner: 0.8 s per turn
        else:
            kws, rates = [{} for _ in range(nb)], [4] * nb                      # 24 x 4/60 s = 1.6 s loop
        title = "%s - %s" % (name, label)
        write(os.path.join(d, stem + ".ani"), make_ani(pool, stem, kws, rates, title, theme))
    files = {k: s + ".ani" for s, _, _, k in D.ROLES}
    allf = [s + ".ani" for s, *_ in D.ROLES] + [s + ".ani" for s, *_ in D.EXTRAS]
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
