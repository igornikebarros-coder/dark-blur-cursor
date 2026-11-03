"""Vector designs (32x32 grid) for every Dark Blur cursor role."""
import math
import numpy as np
from cursorlib import Canvas

ARROW = [(3.3, 2.3), (3.3, 23.2), (8.4, 18.4), (12.0, 26.2), (15.4, 24.7), (11.8, 17.0), (18.6, 17.0)]
TIP = (3.3, 2.3)


def band_light(t):
    """Diagonal shimmer sweep; t in [0,1] sweeps, None = rest."""
    if t is None:
        return None
    c = -8.0 + t * 46.0
    return lambda X, Y: 0.55 * np.exp(-(((X + Y) * 0.5 - c) / 2.6) ** 2)


def comet_light(cx, cy, head):
    """Bright rotating head with fading tail (clockwise)."""
    def f(X, Y):
        phi = np.arctan2(Y - cy, X - cx)
        d = np.mod(head - phi, 2 * np.pi)
        return np.clip(1 - d / (1.3 * np.pi), 0, 1) ** 1.8
    return f


ARROW_SCALE = 0.75          # stock Aero arrow: ~12x19 px on the 32 px canvas
ARROW_AT = (2.2, 2.2)       # where the arrow tip vertex lands


def arrow(c, scale=ARROW_SCALE, light=None):
    c.begin()
    c.push(TIP[0], TIP[1], scale, 0, ARROW_AT[0] - TIP[0], ARROW_AT[1] - TIP[1])
    c.poly(ARROW, round=0.9)
    c.reset()
    c.cur.light = light
    c.hotspot = (2.0, 2.0)


def badge(c, cx=23.0, cy=23.0, r=5.8):
    c.begin(); c.circle(cx, cy, r)


# glyphs (light, drawn on the badge)
def g_question(c, cx, cy):
    c.begin(glyph=True)
    c.arc(cx, cy - 1.3, 2.0, 165, -75, 1.5)
    c.line([(cx + 0.55, cy + 0.65), (cx, cy + 1.3)], 1.5)
    c.circle(cx, cy + 3.6, 0.85)


def g_plus(c, cx, cy):
    c.begin(glyph=True)
    c.line([(cx - 2.7, cy), (cx + 2.7, cy)], 1.6)
    c.line([(cx, cy - 2.7), (cx, cy + 2.7)], 1.6)


def g_minus(c, cx, cy):
    c.begin(glyph=True)
    c.line([(cx - 2.7, cy), (cx + 2.7, cy)], 1.6)


def g_alias(c, cx, cy):
    c.begin(glyph=True)
    c.line([(cx - 2.4, cy + 2.4), (cx + 2.2, cy - 2.2)], 1.5)
    c.line([(cx - 0.6, cy - 2.6), (cx + 2.6, cy - 2.6), (cx + 2.6, cy + 0.6)], 1.5)


def g_person(c, cx, cy):
    c.begin(glyph=True)
    c.circle(cx, cy - 2.0, 1.9)
    pts = [(cx + 3.7 * math.cos(math.radians(a)), cy + 4.4 - 3.4 * math.sin(math.radians(a))) for a in range(0, 181, 10)]
    c.poly(pts)


def dbl_arrow(c, ang, R=13.8, hl=7.0, hw=5.6, sw=3.0, cx=16, cy=16, both=True):
    """Double-headed arrow through (cx,cy) rotated by ang (0 = vertical)."""
    c.push(cx, cy, 1.0, ang)
    heads = [-1, 1] if both else [-1]
    c.rect(cx - sw / 2, cy - R + hl - 0.4, cx + sw / 2, cy + R - hl + 0.4)
    for s in heads:
        tipy = cy + s * R
        basey = cy + s * (R - hl)
        c.poly([(cx, tipy), (cx - hw, basey), (cx + hw, basey)], round=0.9)
    c.reset()


def spinner(c, cx, cy, r, w, head):
    c.begin()
    c.ring(cx, cy, r, w)
    c.cur.light = comet_light(cx, cy, head)


# ------------------------------------------------------------------ roles
def normal(c, t=None):
    arrow(c, ARROW_SCALE, band_light(t))


def help_(c, t=None):
    arrow(c); badge(c); g_question(c, 23, 23)
    c.hotspot = (2.0, 2.0)


def working(c, t=0.62):
    arrow(c)
    spinner(c, 22.8, 22.8, 4.6, 2.7, 2 * math.pi * t)
    c.hotspot = (2.0, 2.0)


def busy(c, t=0.62):
    spinner(c, 16, 16, 10.2, 4.0, 2 * math.pi * t)
    c.hotspot = (16, 16)


def precision(c, t=None):
    c.base = (16,16,.85)
    c.begin()
    c.ring(16, 16, 3.9, 2.0)
    for a in (0, 90, 180, 270):
        c.push(16, 16, 1.0, a)
        c.rrect(14.8, 2.4, 17.2, 11.0, 1.0)
        c.reset()
    c.hotspot = (16, 16)


def text(c, t=None):
    c.base = (16,16,.85)
    c.begin()
    c.rrect(14.2, 5.2, 17.8, 26.8, 1.2)
    c.rrect(10.6, 4.4, 21.4, 7.6, 1.4)
    c.rrect(10.6, 24.4, 21.4, 27.6, 1.4)
    c.hotspot = (16, 16)


def vtext(c, t=None):
    c.base = (16, 16, .85)
    c.begin()
    c.push(16, 16, 1.0, 90)
    c.rrect(14.2, 5.2, 17.8, 26.8, 1.2)
    c.rrect(10.6, 4.4, 21.4, 7.6, 1.4)
    c.rrect(10.6, 24.4, 21.4, 27.6, 1.4)
    c.reset()
    c.hotspot = (16, 16)


def handwriting(c, t=None):
    c.begin()
    T = (3.4, 28.6)
    d = (math.sqrt(.5), -math.sqrt(.5)); n = (math.sqrt(.5), math.sqrt(.5))
    def Q(u, v):
        return (T[0] + u * d[0] + v * n[0], T[1] + u * d[1] + v * n[1])
    c.poly([Q(0, 0), Q(5.4, -2.5), Q(5.4, 2.5)], round=0.9)
    c.poly([Q(5.0, -2.6), Q(21.5, -2.6), Q(21.5, 2.6), Q(5.0, 2.6)], round=0.6)
    e = Q(21.5, 0); c.circle(e[0], e[1], 2.6)
    c.poly([Q(5.1, -3.0), Q(5.9, -3.0), Q(5.9, 3.0), Q(5.1, 3.0)], sub=True)
    c.hotspot = (3.0, 29.0)


def unavailable(c, t=None):
    arrow(c)
    c.begin()
    cx, cy = 22.8, 22.8
    c.ring(cx, cy, 5.0, 2.6)
    c.line([(cx - 3.5, cy + 3.5), (cx + 3.5, cy - 3.5)], 2.6)
    c.hotspot = (2.0, 2.0)


def vertical(c, t=None):
    c.base = (16,16,.82)
    c.begin(); dbl_arrow(c, 0); c.hotspot = (16, 16)


def horizontal(c, t=None):
    c.base = (16,16,.82)
    c.begin(); dbl_arrow(c, 90); c.hotspot = (16, 16)


def diagonal1(c, t=None):   # NW-SE
    c.base = (16,16,.82)
    c.begin(); dbl_arrow(c, -45, R=14.0, hl=7.2, hw=5.6); c.hotspot = (16, 16)


def diagonal2(c, t=None):   # NE-SW
    c.base = (16,16,.82)
    c.begin(); dbl_arrow(c, 45, R=14.0, hl=7.2, hw=5.6); c.hotspot = (16, 16)


def move(c, t=None):
    c.base = (16,16,.84)
    c.begin()
    dbl_arrow(c, 0, R=14.0, hl=6.6, hw=5.2, sw=2.8)
    dbl_arrow(c, 90, R=14.0, hl=6.6, hw=5.2, sw=2.8)
    c.hotspot = (16, 16)


def alternate(c, t=None):
    c.base = (16,16,.9)
    c.begin()
    c.rect(13.7, 11.5, 18.3, 27.8)
    c.rrect(13.7, 24.0, 18.3, 27.8, 1.4)
    c.poly([(16, 2.6), (8.2, 13.4), (23.8, 13.4)], round=0.9)
    c.hotspot = (16, 2.0)


def link(c, t=None):
    hand(c, band_light(t))


def hand(c, light=None):
    """Pointing hand: index finger up, three curled fingers, thumb on the left, short wrist."""
    c.base = (11.7, 2.4, 0.88)           # keep the fingertip fixed, fit to ~19x23 px like the stock hand
    c.begin()
    c.rrect(9.6, 2.4, 14.0, 17.0, 2.2)       # index finger (fully rounded tip)
    c.rrect(14.0, 10.6, 18.4, 19.0, 2.1)     # middle knuckle
    c.rrect(18.4, 11.6, 22.6, 19.4, 2.0)     # ring knuckle
    c.rrect(22.6, 13.4, 26.2, 20.0, 1.8)     # pinky knuckle
    c.rrect(9.6, 13.0, 26.2, 24.6, 4.2)      # palm
    c.poly([(11.0, 22.0), (24.6, 22.0), (23.0, 28.6), (12.6, 28.6)], round=1.6)   # wrist
    c.line([(10.8, 21.4), (5.6, 16.4)], 4.2)   # thumb
    c.smooth(0.55)
    for x, y0 in ((14.0, 10.0), (18.4, 10.8), (22.6, 12.0)):   # finger grooves (open at the top)
        c.line([(x, y0), (x, 17.8)], 0.5, sub=True)
    c.cur.light = light
    c.hotspot = (11.7, 2.4)


def location(c, t=None):
    c.base = (16,16,.9)
    c.begin()
    cx, cy, r, tip = 16.0, 11.4, 8.5, 28.4
    d = tip - cy
    phi = math.acos(r / d)
    tl = (cx - r * math.sin(phi), cy + r * math.cos(phi))
    tr = (cx + r * math.sin(phi), cy + r * math.cos(phi))
    c.circle(cx, cy, r)
    c.poly([(cx, tip), tr, tl], round=0.9)
    c.circle(cx, cy, 3.2, sub=True)
    c.hotspot = (16, 28.0)


def person(c, t=None):
    arrow(c); badge(c); g_person(c, 23, 23)
    c.hotspot = (2.0, 2.0)


# ---- extras (Windhawk Cursor Override)
def copy_(c, t=None):
    arrow(c); badge(c); g_plus(c, 23, 23); c.hotspot = (2.0, 2.0)


def alias(c, t=None):
    arrow(c); badge(c); g_alias(c, 23, 23); c.hotspot = (2.0, 2.0)


def cell(c, t=None):
    c.base = (16,16,.8)
    c.begin()
    c.rrect(3.6, 12.3, 28.4, 19.7, 1.6)
    c.rrect(12.3, 3.6, 19.7, 28.4, 1.6)
    c.hotspot = (16, 16)


def col_resize(c, t=None):
    c.base = (16,16,.85)
    c.begin()
    c.rrect(12.6, 5.0, 15.0, 27.0, 1.2)
    c.rrect(17.0, 5.0, 19.4, 27.0, 1.2)
    for s in (-1, 1):
        x = 16 + s * 1.0
        c.rect(min(x, 16 + s * 8.4), 14.6, max(x, 16 + s * 8.4), 17.4)
        c.poly([(16 + s * 13.6, 16), (16 + s * 7.0, 10.2), (16 + s * 7.0, 21.8)], round=0.9)
    c.hotspot = (16, 16)


def row_resize(c, t=None):
    c.base = (16,16,.85)
    c.begin()
    c.push(16, 16, 1.0, 90)
    c.rrect(12.6, 5.0, 15.0, 27.0, 1.2)
    c.rrect(17.0, 5.0, 19.4, 27.0, 1.2)
    for s in (-1, 1):
        x = 16 + s * 1.0
        c.rect(min(x, 16 + s * 8.4), 14.6, max(x, 16 + s * 8.4), 17.4)
        c.poly([(16 + s * 13.6, 16), (16 + s * 7.0, 10.2), (16 + s * 7.0, 21.8)], round=0.9)
    c.reset()
    c.hotspot = (16, 16)


def _zoom(c, glyph):
    c.base = (15.4, 15.4, .85)
    c.begin(alpha=0.45, shadow=False); c.circle(13.0, 13.0, 8.6)
    c.begin()
    c.ring(13.0, 13.0, 9.2, 2.8)
    c.line([(19.8, 19.8), (27.0, 27.0)], 4.4)
    glyph(c, 13.0, 13.0)
    c.hotspot = (13.0, 13.0)


def zoom_in(c, t=None):
    _zoom(c, g_plus)


def zoom_out(c, t=None):
    _zoom(c, g_minus)


def grab(c, t=None):
    c.base = (16, 16, .9)
    c.begin()
    c.rrect(7.8, 6.6, 12.4, 17.0, 2.2)
    c.rrect(12.4, 4.0, 17.0, 17.0, 2.3)
    c.rrect(17.0, 5.2, 21.4, 17.0, 2.2)
    c.rrect(21.4, 8.4, 25.2, 17.0, 1.9)
    c.rrect(7.8, 13.0, 25.2, 25.4, 4.6)
    c.poly([(10.0, 23.0), (22.8, 23.0), (21.4, 29.0), (11.6, 29.0)], round=1.6)
    c.line([(9.6, 20.6), (3.8, 14.0)], 4.2)
    c.smooth(0.55)
    for x, y0 in ((12.4, 5.5), (17.0, 4.5), (21.4, 6.5)):
        c.line([(x, y0), (x, 14.4)], 0.5, sub=True)
    c.hotspot = (16, 16)


def grabbing(c, t=None):
    c.base = (16, 16, .9)
    c.begin()
    c.rrect(7.8, 12.0, 25.2, 24.6, 4.8)
    for x in (10.0, 14.2, 18.4, 22.6):
        c.circle(x, 13.4, 2.4)
    c.poly([(10.0, 22.0), (23.0, 22.0), (21.6, 28.0), (11.4, 28.0)], round=1.6)
    c.line([(9.0, 21.0), (4.4, 17.6)], 4.0)
    c.smooth(0.55)
    for x in (12.1, 16.3, 20.5):
        c.line([(x, 10.6), (x, 14.6)], 0.5, sub=True)
    c.hotspot = (16, 16.5)


ROLES = [  # (file stem, label, fn, scheme-registry key or None)
    ("normal", "Normal", normal, "Arrow"),
    ("help", "Ajuda", help_, "Help"),
    ("working", "Segundo plano", working, "AppStarting"),
    ("busy", "Ocupado", busy, "Wait"),
    ("precision", "Precisão", precision, "Crosshair"),
    ("text", "Texto", text, "IBeam"),
    ("handwriting", "Caneta", handwriting, "NWPen"),
    ("unavailable", "Indisponível", unavailable, "No"),
    ("vertical", "Vertical", vertical, "SizeNS"),
    ("horizontal", "Horizontal", horizontal, "SizeWE"),
    ("diagonal1", "Diagonal 1", diagonal1, "SizeNWSE"),
    ("diagonal2", "Diagonal 2", diagonal2, "SizeNESW"),
    ("move", "Mover", move, "SizeAll"),
    ("alternate", "Alternativo", alternate, "UpArrow"),
    ("link", "Link", link, "Hand"),
    ("location", "Local", location, "Pin"),
    ("person", "Pessoa", person, "Person"),
]
EXTRAS = [
    ("alias", "Atalho", alias, None),
    ("copy", "Copiar", copy_, None),
    ("cell", "Célula", cell, None),
    ("col-resize", "Col. resize", col_resize, None),
    ("row-resize", "Linha resize", row_resize, None),
    ("zoom-in", "Zoom +", zoom_in, None),
    ("zoom-out", "Zoom −", zoom_out, None),
    ("grab", "Mão aberta", grab, None),
    ("grabbing", "Mão fechada", grabbing, None),
    ("vertical-text", "Texto vert.", vtext, None),
]
ALL = ROLES + EXTRAS
