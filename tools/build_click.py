#!/usr/bin/env python3
"""Pre-renders the monochrome whitish frosted click effects to click-animations/<effect>-<dark|light>.bgra.

Format: 40 frames of 160x160 pixels, 32bpp, top-down, byte order B,G,R,A with PREMULTIPLIED alpha,
ready for UpdateLayeredWindow (AC_SRC_ALPHA). Frame step in the AHK script is 16 ms.
"""
import os, math, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "click-animations")
FRAMES, SIZE, SS = 40, 160, 3
M = SIZE * SS
yy, xx = np.mgrid[0:M, 0:M].astype(np.float32)
CX = CY = (M - 1) / 2.0
R_ = np.sqrt((xx - CX) ** 2 + (yy - CY) ** 2) / SS          # radius in output px
ANG = (np.arctan2(yy - CY, xx - CX) / (2 * np.pi)).astype(np.float32)   # -0.5..0.5
AA = 0.9 * SS
THEME = "dark"
BODY = {"dark": ((240, 243, 250), (176, 184, 204), 0.86), "light": ((252, 253, 255), (200, 207, 224), 0.90)}


def ease_out(t):  return 1 - (1 - t) ** 3
def ease_in_out(t): return t * t * (3 - 2 * t)
def clamp01(x): return min(1.0, max(0.0, x))


def over(dst, rgb, a):
    a = a[..., None]
    dst[..., :3] = dst[..., :3] * (1 - a) + np.asarray(rgb, np.float32) * a
    dst[..., 3:4] = dst[..., 3:4] * (1 - a) + a


PAL = {
    "dark": dict(edge=(58, 64, 82), glow=(255, 255, 255), glow_k=1.0, hw=0.8),
    "light": dict(edge=(82, 90, 112), glow=(36, 42, 64), glow_k=0.65, hw=1.0),
}


def neon(dst, sdf, col=None, k=1.0, body=1.0, hw=1.25, glow=1.0, glow_w=1.0, tint=0.35):
    """Whitish frosted shape with a thin darker edge and soft glow, from a signed distance field
    (output px, + = outside). `col` is ignored (kept for call compatibility): everything is monochrome."""
    P = PAL[THEME]
    ehw = hw * 0.7 * P["hw"] / 0.8                    # edge half width (px)
    s = sdf * SS
    b_in = np.clip(0.5 - s / AA, 0, 1)
    o = np.maximum(sdf - ehw, 0)
    g = (np.exp(-o / (1.3 * glow_w)) * 0.75 + np.exp(-o / (4.5 * glow_w)) * 0.38) * np.clip(1 - o / (14 * glow_w), 0, 1)
    over(dst, P["glow"], np.clip(g * glow * P["glow_k"] * k, 0, 1) * (1 - b_in))
    top, bot, ba = BODY[THEME]
    gy = np.clip(yy / M, 0, 1)[..., None]
    over(dst, np.array(top, np.float32) * (1 - gy) + np.array(bot, np.float32) * gy, b_in * ba * body * k)
    band = np.clip((ehw * SS - np.abs(s)) / AA + 0.5, 0, 1)
    over(dst, P["edge"], band * np.clip(0.96 * k, 0, 1))
    rim = np.clip((0.35 * SS - np.abs(s + (ehw + 0.45) * SS)) / AA + 0.5, 0, 1) * (sdf < 0)
    over(dst, (255, 255, 255), rim * np.clip(0.7 * k, 0, 1))


def finish(dst):
    d = dst.reshape(SIZE, SS, SIZE, SS, 4).mean(axis=(1, 3))
    a = np.clip(d[..., 3], 0, 1)
    bgra = np.empty((SIZE, SIZE, 4), np.uint8)
    for i, c in enumerate((2, 1, 0)):
        bgra[..., i] = np.clip(d[..., c] + 0.5, 0, 255).astype(np.uint8)
    bgra[..., 3] = np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)
    for c in range(3):
        bgra[..., c] = np.minimum(bgra[..., c], bgra[..., 3])      # premultiplied invariant
    return bgra


def new():
    return np.zeros((M, M, 4), np.float32)


MONO = {"dark": np.array((236, 240, 248), np.float32), "light": np.array((60, 66, 90), np.float32)}


def ring_col(hue=0.0):
    return MONO[THEME]


def mono_const(hue=0.0):
    return MONO[THEME]


# ------------------------------------------------------------------ effects
def fx_ripple(f):
    t = f / (FRAMES - 1)
    d = new()
    for i, delay in enumerate((0.0, 0.16, 0.32)):
        tt = clamp01((t - delay) / (1 - delay))
        if tt <= 0:
            continue
        r = 8 + 68 * ease_out(tt)
        w = 3.0 + 7.0 * (1 - tt)
        fade = (1 - tt) ** 1.0 * min(1, tt * 10)
        neon(d, np.abs(R_ - r) - w / 2, ring_col(), k=fade, hw=1.5, glow=1.1)
    if t < 0.3:                                      # press flash
        a = 1 - t / 0.3
        neon(d, R_ - 6 * (1 + t * 2.5), ring_col(t), k=a, hw=1.4)
    return d


def fx_glow(f):
    t = f / (FRAMES - 1)
    d = new()
    r = 12 + 64 * ease_out(t)
    fade = (1 - t) ** 0.9 * min(1, t * 10)
    col = ring_col(t * 0.8)
    neon(d, R_ - r, col, k=fade, body=0.35, hw=1.9, glow=1.3, glow_w=1.6, tint=0.7)
    # saturated radial colour bloom inside
    bloom = (1 - np.clip(R_ / max(r, 1), 0, 1)) ** 1.4
    over(d, MONO[THEME], np.clip(bloom * 0.35 * fade, 0, 1) * np.clip(0.5 - (R_ - r) * SS / AA, 0, 1))
    c = clamp01(1 - t * 3.0)
    if c > 0:
        over(d, (255, 255, 255), np.exp(-R_ ** 2 / (2 * (6 + 6 * (1 - c)) ** 2)) * 0.80 * c)
    return d


def fx_particles(f):
    t = f / (FRAMES - 1)
    d = new()
    rng = np.random.RandomState(11)
    n = 24
    fade = (1 - t) ** 0.75 * min(1, t * 14)
    for i in range(n):
        ang = (i / n) * 2 * math.pi + rng.uniform(-0.12, 0.12)
        dist = rng.uniform(40, 74)
        r0 = rng.uniform(3.2, 6.4)
        delay = rng.uniform(0, 0.1)
        tt = clamp01((t - delay) / (1 - delay))
        p = ease_out(tt)
        r = r0 * (1 - 0.5 * tt) + 0.8
        x, y = dist * p * math.cos(ang), dist * p * math.sin(ang) + 6 * tt * tt
        sdf = np.sqrt((xx - CX - x * SS) ** 2 + (yy - CY - y * SS) ** 2) / SS - r
        hue = (i / n) * 0.8 + t * 0.5
        neon(d, sdf, MONO[THEME],
             k=fade, hw=1.2, glow=0.95, glow_w=0.9)
    over(d, (255, 255, 255), np.exp(-R_ ** 2 / (2 * 10 ** 2)) * 0.55 * clamp01(1 - t * 4))
    return d


def fx_orbit(f):
    t = f / (FRAMES - 1)
    d = new()
    env = min(1, t * 10) * (1 - t) ** 0.8
    turns = 1.35

    def pos(tt, i):
        r = 70 * (1 - ease_in_out(tt) * 0.8) + 6
        a = i * 2 * math.pi / 3 + tt * 2 * math.pi * turns
        return r * math.cos(a), r * math.sin(a)

    for i in range(3):
        for g in range(9, -1, -1):                       # comet trail: older ghosts are smaller and dimmer
            tt = max(0.0, t - g * 0.018)
            x, y = pos(tt, i)
            rad = (6.2 - 2.4 * tt) * (1 - 0.07 * g)
            sdf = np.sqrt((xx - CX - x * SS) ** 2 + (yy - CY - y * SS) ** 2) / SS - rad
            hue = i * 0.27 + t * 0.9 + g * 0.015
            col = MONO[THEME]
            kk = env * (1 - g / 11.0) ** 1.4
            neon(d, sdf, col, k=kk, hw=1.2 if g == 0 else 0.9, glow=1.0 if g == 0 else 0.35, glow_w=0.9)
    return d


EFFECTS = {"ripple": fx_ripple, "glow": fx_glow, "particle": fx_particles, "orbit": fx_orbit}


def render(name, theme="dark"):
    global THEME
    THEME = theme
    return np.stack([finish(EFFECTS[name](f)) for f in range(FRAMES)])


def _job(a):
    return a, render(*a)


def main():
    from multiprocessing import Pool
    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):
        if old.endswith(".bgra"):
            os.remove(os.path.join(OUT, old))
    jobs = [(n, th) for th in ("dark", "light") for n in EFFECTS]
    with Pool() as pool:
        for (name, theme), fr in pool.imap_unordered(_job, jobs):
            assert fr.shape == (FRAMES, SIZE, SIZE, 4)
            with open(os.path.join(OUT, "%s-%s.bgra" % (name, theme)), "wb") as f:
                f.write(fr.tobytes())
            print(name, theme, fr.nbytes, "alpha max", fr[..., 3].max())


if __name__ == "__main__":
    main()
