#!/usr/bin/env python3
"""Builds preview/*.png and *.gif by decoding the REAL .cur/.ani/.bgra files of the pack."""
import os, io, sys, struct, glob
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
sys.path.insert(0, os.path.dirname(__file__))
from cursorlib import parse_cur, parse_ani, decode_cur
import designs as D

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PREV = os.path.join(ROOT, "preview")
os.makedirs(PREV, exist_ok=True)
FONT = "/workspace/fonts/roboto.ttf"
if not os.path.exists(FONT):
    FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(sz, bold=False):
    f = ImageFont.truetype(FONT, sz)
    try:
        f.set_variation_by_axes([700 if bold else 400])
    except Exception:
        pass
    return f


def cur_image(data, size):
    """Decode one size of a .cur (true straight-alpha) -> RGBA PIL image, hotspot."""
    px, hot = decode_cur(data, size)
    return Image.fromarray(px, "RGBA"), hot


def ani_frames(path, size):
    data = open(path, "rb").read()
    info = parse_ani(data)
    off = data.find(b"fram") + 4
    out = []
    while off < len(data):
        sz = struct.unpack("<I", data[off + 4:off + 8])[0]
        out.append(cur_image(data[off + 8:off + 8 + sz], size)[0])
        off += 8 + sz + (sz & 1)
    return out, info["rate"]


def background(w, h, dark, seed=3):
    """Soft gradient with colour blobs so the glass translucency is visible."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    if dark:
        base = np.array([20, 23, 33], np.float32); blobs = [(0.15, 0.2, (60, 90, 170)), (0.8, 0.75, (110, 70, 160)), (0.6, 0.15, (40, 120, 140))]
    else:
        base = np.array([226, 230, 240], np.float32); blobs = [(0.15, 0.2, (150, 190, 255)), (0.8, 0.75, (255, 190, 210)), (0.6, 0.15, (190, 235, 215))]
    img = np.tile(base, (h, w, 1))
    for bx, by, col in blobs:
        d2 = ((xx / w - bx) ** 2 * (w / max(w, h)) ** -2 * 0 + ((xx - bx * w) ** 2 + (yy - by * h) ** 2) / (0.45 * max(w, h)) ** 2)
        k = np.exp(-d2)[..., None] * (0.55 if dark else 0.7)
        img = img * (1 - k) + np.array(col, np.float32) * k
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


def paste_cursor(canvas, im, cx, cy):
    canvas.paste(im, (int(cx - im.width / 2), int(cy - im.height / 2)), im)


THEME_TITLE = {"dark": "Dark Blur", "light": "Light Blur"}
MAIN_STEMS = [r[0] for r in D.ROLES]


def cur_path(theme, stem, kind="cursor-classic", ext=".cur"):
    return os.path.join(ROOT, theme, kind, stem + ext)


def tile(img, x, y, w, h, dark):
    t = Image.new("L", (w, h), 0)
    ImageDraw.Draw(t).rounded_rectangle([0, 0, w - 1, h - 1], 14, fill=int(255 * (18 if dark else 70) / 255))
    img.paste(Image.new("RGB", (w, h), (255, 255, 255)), (x, y), t)


def panel_static(theme, dark_bg, size=96, stems=None, cols=9, cw=132, ch=132, title=True, strip=True, cursor_size=None):
    items = [x for x in D.ALL if stems is None or x[0] in stems]
    rows = (len(items) + cols - 1) // cols
    top = 56 if title else 34
    W, H = cols * cw + 40, top + rows * ch + (120 if strip else 10)
    img = background(W, H, dark_bg)
    dr = ImageDraw.Draw(img)
    fg = (236, 240, 250) if dark_bg else (30, 34, 46)
    sub = (150, 160, 185) if dark_bg else (100, 108, 128)
    name = THEME_TITLE[theme]
    if title:
        dr.text((24, 14), name, font=font(24, True), fill=fg)
    else:
        dr.text((24, 8), name, font=font(16, True), fill=fg)
    dr.text((W - 24, 16 if title else 12), "fundo escuro" if dark_bg else "fundo claro", font=font(14), fill=sub, anchor="ra")
    extra = [e[0] for e in D.EXTRAS]
    for i, (stem, label, fn, key) in enumerate(items):
        cim, hot = cur_image(open(cur_path(theme, stem), "rb").read(), cursor_size or size)
        x, y = 20 + (i % cols) * cw, top + (i // cols) * ch
        tile(img, x + 6, y + 2, cw - 12, ch - 8, dark_bg)
        paste_cursor(img, cim, x + cw / 2, y + ch * 0.4)
        dr.text((x + cw / 2, y + ch - 24), label, font=font(12), fill=sub if stem in extra else fg, anchor="mm")
    if strip:
        y0 = top + rows * ch + 14
        dr.text((24, y0), "Tamanho real (32 px)", font=font(12), fill=sub)
        for i, (stem, label, fn, key) in enumerate(D.ROLES):
            cim, hot = cur_image(open(cur_path(theme, stem), "rb").read(), 32)
            paste_cursor(img, cim, 40 + i * 62, y0 + 56)
    return img


def stack(imgs, path, gap=0):
    W = max(i.width for i in imgs)
    H = sum(i.height for i in imgs) + gap * (len(imgs) - 1)
    sheet = Image.new("RGB", (W, H), (0, 0, 0))
    y = 0
    for i in imgs:
        sheet.paste(i, (0, y)); y += i.height + gap
    sheet.save(path, optimize=True)
    print(os.path.basename(path), sheet.size)


def make_static_sheets():
    # combined showcase: both themes, light + dark backgrounds, the 17 scheme cursors
    p = []
    for th in ("dark", "light"):
        for dk in (False, True):
            p.append(panel_static(th, dk, stems=MAIN_STEMS, cols=9, cw=108, ch=104, title=False, strip=False, cursor_size=64))
    head = background(p[0].width, 70, True)
    d = ImageDraw.Draw(head)
    d.text((24, 12), "Dark Blur Cursor", font=font(28, True), fill=(240, 244, 255))
    d.text((24, 46), "Vidro fosco escuro e claro  \u2022  cursores clássicos + animados  \u2022  animações de clique", font=font(13), fill=(160, 172, 200))
    stack([head] + p, os.path.join(PREV, "showcase.png"))
    # every cursor of each theme on both backgrounds
    for th in ("dark", "light"):
        stack([panel_static(th, False), panel_static(th, True)], os.path.join(PREV, "%s-theme.png" % th))


def to_gif(frames, durations, path):
    pal = [f.convert("P", palette=Image.ADAPTIVE, colors=255, dither=Image.FLOYDSTEINBERG) for f in frames]
    pal[0].save(path, save_all=True, append_images=pal[1:], duration=durations, loop=0, optimize=False, disposal=1)
    print(os.path.basename(path), "%.1f MB" % (os.path.getsize(path) / 1e6), len(frames), "frames")


COMBOS = [("dark", False), ("dark", True), ("light", False), ("light", True)]


def make_animated_gif():
    cells = [("busy", "Ocupado"), ("working", "Segundo plano"), ("normal", "Normal (brilho)"), ("link", "Link (brilho)")]
    data = {}
    for th in ("dark", "light"):
        for stem, label in cells:
            fr, rate = ani_frames(cur_path(th, stem, "cursor-animated", ".ani"), 128)
            data[(th, stem)] = (fr, np.cumsum(rate) * (1000 / 60.0))
    cw, ch = 150, 150
    W, H = cw * len(cells), ch * 4 + 34
    base = Image.new("RGB", (W, H), (18, 20, 28))
    for r, (th, dk) in enumerate(COMBOS):
        base.paste(background(W, ch, dk), (0, r * ch))
        ImageDraw.Draw(base).text((10, r * ch + 8), THEME_TITLE[th] + " Animated", font=font(12, True), fill=(236, 240, 250) if dk else (40, 44, 58))
    ImageDraw.Draw(base).text((W // 2, 4 * ch + 17), "Dark Blur Cursor - cursores animados", font=font(14, True), fill=(220, 228, 245), anchor="mm")
    step, period = 60, 2400
    frames, durs = [], []
    for k in range(period // step):
        t = k * step
        img = base.copy(); dr = ImageDraw.Draw(img)
        for r, (th, dk) in enumerate(COMBOS):
            for ci, (stem, label) in enumerate(cells):
                fr, cum = data[(th, stem)]
                idx = int(np.searchsorted(cum, t % cum[-1], side="right")) % len(fr)
                im = fr[idx].resize((96, 96), Image.LANCZOS)
                paste_cursor(img, im, ci * cw + cw / 2, r * ch + 66)
                dr.text((ci * cw + cw / 2, r * ch + 134), label, font=font(11), fill=(236, 240, 250) if dk else (40, 44, 58), anchor="mm")
        frames.append(img); durs.append(step)
    to_gif(frames, durs, os.path.join(PREV, "dark-blur-cursor-animated.gif"))


def make_click_gif():
    names = [("ripple", "Ondulação"), ("glow", "Brilho"), ("particle", "Partículas"), ("orbit", "Órbita")]
    fx = {(n, th): np.fromfile(os.path.join(ROOT, "click-animations", "%s-%s.bgra" % (n, th)), np.uint8).reshape(48, 128, 128, 4)
          for n, _ in names for th in ("dark", "light")}
    arrows = {th: cur_image(open(cur_path(th, "normal"), "rb").read(), 32) for th in ("dark", "light")}
    cw, ch = 150, 150
    W, H = cw * 4, ch * 4 + 34
    base = Image.new("RGB", (W, H), (18, 20, 28))
    for r, (th, dk) in enumerate(COMBOS):
        base.paste(background(W, ch, dk), (0, r * ch))
        ImageDraw.Draw(base).text((10, r * ch + 8), "Efeito " + ("escuro" if th == "dark" else "claro"), font=font(12, True), fill=(236, 240, 250) if dk else (40, 44, 58))
    ImageDraw.Draw(base).text((W // 2, 4 * ch + 17), "Dark Blur Cursor - animações de clique", font=font(14, True), fill=(220, 228, 245), anchor="mm")
    frames, durs = [], []
    seq = list(range(0, 48, 2)) + [None] * 8
    for k in seq:
        img = base.copy(); dr = ImageDraw.Draw(img)
        for r, (th, dk) in enumerate(COMBOS):
            arrow, hot = arrows[th]
            for ci, (n, label) in enumerate(names):
                cx, cy = ci * cw + cw // 2, r * ch + 70
                if k is not None:
                    f = fx[(n, th)][k].astype(np.float32)
                    a = f[..., 3:4] / 255.0
                    box = (cx - 64, cy - 64, cx + 64, cy + 64)
                    reg = np.array(img.crop(box), np.float32)
                    comp = f[..., [2, 1, 0]] + reg * (1 - a)       # premultiplied "over"
                    img.paste(Image.fromarray(np.clip(comp, 0, 255).astype(np.uint8)), box[:2])
                img.paste(arrow, (cx - hot[0], cy - hot[1]), arrow)
                dr.text((cx, r * ch + 138), label, font=font(11), fill=(236, 240, 250) if dk else (40, 44, 58), anchor="mm")
        frames.append(img); durs.append(30 if k is not None else 60)
    to_gif(frames, durs, os.path.join(PREV, "dark-blur-cursor-click-animations.gif"))


if __name__ == "__main__":
    for old in glob.glob(os.path.join(PREV, "*")):
        os.remove(old)
    make_static_sheets(); make_animated_gif(); make_click_gif()
