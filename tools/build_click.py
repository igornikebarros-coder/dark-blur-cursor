#!/usr/bin/env python3
"""Pre-renders the click effects to click-animations/<effect>-<dark|light>.bgra.

Format (same idea as Galaxy Cursor): 48 frames of 128x128 pixels, 32bpp, top-down,
byte order B,G,R,A with PREMULTIPLIED alpha, ready for UpdateLayeredWindow (AC_SRC_ALPHA).
"""
import os, math, sys
import numpy as np
import cv2

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "click-animations")
FRAMES, SIZE, SS = 48, 128, 3
M = SIZE * SS
yy, xx = np.mgrid[0:M, 0:M].astype(np.float32)
CX = CY = (M - 1) / 2.0
R_ = np.sqrt((xx - CX) ** 2 + (yy - CY) ** 2)
AA = 0.9 * SS          # edge softness in hi-res px


def ease_out(t):  return 1 - (1 - t) ** 3
def ease_in_out(t): return t * t * (3 - 2 * t)
def clamp01(x): return min(1.0, max(0.0, x))


def over(dst, rgb, a):
    a = a[..., None]
    dst[..., :3] = dst[..., :3] * (1 - a) + np.asarray(rgb, np.float32) * a
    dst[..., 3:4] = dst[..., 3:4] * (1 - a) + a


PAL = {
    "dark": dict(top=(46, 52, 70), bot=(12, 14, 22), fillk=1.0, inner=None, shadow=(0, 0, 0), shadow_k=0.32,
                 outer=(6, 8, 14), outer_a=0.5, rim=(232, 240, 255), rim_lo=0.55, rim_hi=0.40, rim2=None,
                 halo_a=(80, 135, 255), halo_b=(155, 105, 255), halo_k=0.55, spec=(255, 255, 255)),
    "light": dict(top=(250, 252, 255), bot=(186, 198, 226), fillk=0.95, inner=(255, 255, 255), shadow=(24, 32, 70), shadow_k=0.26,
                  outer=(255, 255, 255), outer_a=0.6, rim=(44, 58, 98), rim_lo=0.85, rim_hi=0.15, rim2=(255, 255, 255),
                  halo_a=(90, 135, 255), halo_b=(165, 115, 255), halo_k=0.40, spec=(255, 255, 255)),
}
THEME = "dark"


def glass(dst, sdf, k=1.0, fill=0.58, glow=0.30, glow_w=7.0, rim_w=1.3, tint=(150, 190, 255), light=None):
    """Frosted-glass shape from a signed distance field (negative = inside, in output px)."""
    P = PAL[THEME]
    s = sdf * SS
    body = np.clip(0.5 - s / AA, 0, 1)
    # soft shadow, knocked out under the glass
    sh = cv2.GaussianBlur(np.roll(body, (2 * SS, SS), (0, 1)), (0, 0), 2.2 * SS) * P["shadow_k"] * k
    over(dst, P["shadow"], sh * (1 - body))
    # cool blue -> violet edge light just outside the shape
    outd = np.maximum(sdf, 0)
    g = np.clip((xx + yy) / (1.2 * M), 0, 1)[..., None]
    hc = np.array(P["halo_a"], np.float32) * (1 - g) + np.array(P["halo_b"], np.float32) * g
    h = np.exp(-np.maximum(outd - 0.3, 0) / 1.1) * np.clip(1.2 - outd / 4.0, 0, 1) * (1 - body)
    over(dst, hc, np.clip(h * P["halo_k"] * k, 0, 1))
    # smoky / frosted fill: lighter towards the top-left
    g1 = np.clip((xx + yy) / (2.0 * M), 0, 1)[..., None]
    col = np.array(P["top"], np.float32) * (1 - g1) + np.array(P["bot"], np.float32) * g1
    over(dst, col, body * fill * P["fillk"] * k)
    # inner glow
    ig = np.exp(s / (glow_w * SS)) * body
    over(dst, P["inner"] or tint, np.clip(ig * glow * k, 0, 1))
    # outer hairline, then rim
    ow = 0.7 * SS
    over(dst, P["outer"], np.clip(0.5 + (ow - s) / AA, 0, 1) * np.clip(0.5 + s / AA, 0, 1) * P["outer_a"] * k)
    rim = body * np.clip(0.5 + (rim_w * SS + s) / AA, 0, 1)
    ra = P["rim_lo"] + P["rim_hi"] * (1 - g1[..., 0])
    over(dst, P["rim"], rim * ra * k)
    if P["rim2"] is not None:
        r2 = body * np.clip(0.5 + ((rim_w + 0.9) * SS + s) / AA, 0, 1) * np.clip(0.5 - (rim_w * SS + s) / AA, 0, 1)
        over(dst, P["rim2"], r2 * 0.5 * k)
    if light is not None:
        over(dst, P["spec"], body * light)


def finish(dst):
    d = dst.reshape(SIZE, SS, SIZE, SS, 4).mean(axis=(1, 3))
    # premultiplied colour = straight colour * alpha ; dst colours are already premultiplied
    a = np.clip(d[..., 3], 0, 1)
    bgra = np.empty((SIZE, SIZE, 4), np.uint8)
    bgra[..., 0] = np.clip(d[..., 2] + 0.5, 0, 255).astype(np.uint8)
    bgra[..., 1] = np.clip(d[..., 1] + 0.5, 0, 255).astype(np.uint8)
    bgra[..., 2] = np.clip(d[..., 0] + 0.5, 0, 255).astype(np.uint8)
    bgra[..., 3] = np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)
    # guarantee premultiplied invariant (colour <= alpha)
    for c in range(3):
        bgra[..., c] = np.minimum(bgra[..., c], bgra[..., 3])
    return bgra


def new():
    return np.zeros((M, M, 4), np.float32)


# ------------------------------------------------------------------ effects
def fx_ripple(f):
    t = f / (FRAMES - 1)
    d = new()
    for delay, k in ((0.0, 1.0), (0.22, 0.75)):
        tt = clamp01((t - delay) / (1 - delay))
        if tt <= 0:
            continue
        r = 5 + 54 * ease_out(tt)
        w = 2.2 + 6.5 * (1 - tt)
        fade = (1 - tt) ** 1.3 * min(1, tt * 14)
        glass(d, np.abs(R_ / SS - r) - w / 2, k=k * fade, fill=0.62, glow=0.45, glow_w=2.2)
    # tiny press flash
    if t < 0.25:
        a = 1 - t / 0.25
        glass(d, R_ / SS - 4.5 * (1 + t * 2), k=a, fill=0.5, glow=0.6, glow_w=3.0)
    return d


def fx_glow(f):
    t = f / (FRAMES - 1)
    d = new()
    r = 8 + 40 * ease_out(t)
    fade = (1 - t) ** 1.1 * min(1, t * 12)
    glass(d, R_ / SS - r, k=fade, fill=0.42, glow=0.9, glow_w=9.0 + 8 * t, rim_w=1.2)
    # bright, quickly fading core
    c = clamp01(1 - t * 3.2)
    if c > 0:
        core = np.exp(-(R_ / SS) ** 2 / (2 * (7 + 6 * (1 - c)) ** 2))
        over(d, (200, 225, 255), core * 0.55 * c)
    return d


def fx_particles(f):
    t = f / (FRAMES - 1)
    d = new()
    rng = np.random.RandomState(11)
    n = 16
    sdf = np.full((M, M), 1e3, np.float32)
    for i in range(n):
        ang = (i / n) * 2 * math.pi + rng.uniform(-0.18, 0.18)
        dist = rng.uniform(32, 58)
        r0 = rng.uniform(2.6, 5.2)
        delay = rng.uniform(0, 0.12)
        tt = clamp01((t - delay) / (1 - delay))
        p = ease_out(tt)
        r = r0 * (1 - 0.55 * tt) + 0.6
        x, y = dist * p * math.cos(ang), dist * p * math.sin(ang) + 6 * tt * tt  # slight gravity
        s = np.sqrt((xx - CX - x * SS) ** 2 + (yy - CY - y * SS) ** 2) / SS - r
        sdf = np.minimum(sdf, s)
    fade = (1 - t) ** 0.8 * min(1, t * 16)
    glass(d, sdf, k=fade, fill=0.7, glow=0.55, glow_w=1.8, rim_w=1.0)
    # soft central bloom
    over(d, (170, 205, 255), np.exp(-(R_ / SS) ** 2 / (2 * 9 ** 2)) * 0.25 * clamp01(1 - t * 4))
    return d


def fx_orbit(f):
    t = f / (FRAMES - 1)
    d = new()
    fade = min(1, t * 12) * (1 - t) ** 0.9
    r = 46 * (1 - ease_in_out(t) * 0.78) + 4
    sdf = np.full((M, M), 1e3, np.float32)
    for i in range(3):
        ang = i * 2 * math.pi / 3 + t * 2 * math.pi * 1.25
        x, y = r * math.cos(ang), r * math.sin(ang)
        rad = 5.2 - 2.4 * t
        sdf = np.minimum(sdf, np.sqrt((xx - CX - x * SS) ** 2 + (yy - CY - y * SS) ** 2) / SS - rad)
    glass(d, sdf, k=fade, fill=0.72, glow=0.6, glow_w=2.0, rim_w=1.1)
    # faint guide ring
    glass(d, np.abs(R_ / SS - r) - 0.8, k=fade * 0.45, fill=0.4, glow=0.2, glow_w=1.5, rim_w=0.7)
    return d


EFFECTS = {"ripple": fx_ripple, "glow": fx_glow, "particle": fx_particles, "orbit": fx_orbit}


def render(name, theme="dark"):
    global THEME
    THEME = theme
    return np.stack([finish(EFFECTS[name](f)) for f in range(FRAMES)])


def main():
    os.makedirs(OUT, exist_ok=True)
    for old in os.listdir(OUT):
        if old.endswith(".bgra"):
            os.remove(os.path.join(OUT, old))
    for theme in ("dark", "light"):
        for name in EFFECTS:
            fr = render(name, theme)
            assert fr.shape == (FRAMES, SIZE, SIZE, 4)
            with open(os.path.join(OUT, "%s-%s.bgra" % (name, theme)), "wb") as f:
                f.write(fr.tobytes())
            print(name, theme, fr.nbytes, "alpha max", fr[..., 3].max())


if __name__ == "__main__":
    main()
