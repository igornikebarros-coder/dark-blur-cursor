"""Dark Blur Cursor - rendering + file-format helpers.

Cursors are described on a 32x32 design grid with a tiny vector DSL (Canvas),
rasterised at a supersampled resolution, then turned into dark frosted-glass
by `render_layers` (shadow, smoky translucent fill, inner glow, sheen,
dark outer line, light rim) and box-downsampled to the target size.
"""
import math, struct, io
import numpy as np
import cv2
from PIL import Image, ImageDraw

GRID = 32.0


# ----------------------------------------------------------------- canvas DSL
class Layer:
    def __init__(self, img, glyph=False, alpha=1.0, shadow=True):
        self.img = img            # PIL 'L' supersampled mask
        self.glyph = glyph        # solid light glyph (no glass)
        self.alpha = alpha        # multiplier on the glass fill alpha
        self.shadow = shadow
        self.light = None         # callable(X, Y)->0..1 in design units (shimmer / comet)


class Canvas:
    def __init__(self, N):
        self.N = N
        self.ss = 8 if N <= 32 else (6 if N <= 48 else 4)
        self.M = N * self.ss
        self.u = self.M / GRID                      # supersampled px per design unit
        self.layers = []
        self.cur = None
        self.tf = (0.0, 0.0, 1.0, 0.0, 0.0, 0.0)    # cx, cy, scale, rot(deg), tx, ty
        self.base = (16.0, 16.0, 1.0)               # global fit: cx, cy, scale
        self._hot = (0.0, 0.0)

    # layers
    def begin(self, glyph=False, alpha=1.0, shadow=True):
        self.cur = Layer(Image.new("L", (self.M, self.M), 0), glyph, alpha, shadow)
        self.layers.append(self.cur)
        self._d = ImageDraw.Draw(self.cur.img)
        return self.cur

    # transform: p' = c + s*R(p-c) + t
    def push(self, cx=16.0, cy=16.0, scale=1.0, rot=0.0, tx=0.0, ty=0.0):
        self.tf = (cx, cy, scale, rot, tx, ty)

    def reset(self):
        self.tf = (0.0, 0.0, 1.0, 0.0, 0.0, 0.0)

    def _b(self, X, Y):
        bx, by, bs = self.base
        return bx + bs * (X - bx), by + bs * (Y - by)

    def P(self, p):
        cx, cy, s, rot, tx, ty = self.tf
        x, y = p[0] - cx, p[1] - cy
        a = math.radians(rot)
        c, sn = math.cos(a), math.sin(a)
        xr, yr = x * c - y * sn, x * sn + y * c
        X, Y = self._b(cx + s * xr + tx, cy + s * yr + ty)
        return (X * self.u, Y * self.u)

    def S(self, v):
        return v * self.tf[2] * self.base[2] * self.u

    @property
    def hotspot(self):
        return self._hot

    @hotspot.setter
    def hotspot(self, h):
        self._hot = self._b(h[0], h[1])

    def smooth(self, sigma=0.6):
        """Round convex AND concave corners of the current layer (organic shapes)."""
        sg = sigma * self.u
        a = np.asarray(self.cur.img, np.float32) / 255.0
        b = cv2.GaussianBlur(a, (0, 0), sg)
        v = np.clip((b - 0.5) * 2.5 * sg + 0.5, 0, 1)
        self.cur.img = Image.fromarray((v * 255 + 0.5).astype(np.uint8), "L")
        self._d = ImageDraw.Draw(self.cur.img)

    def _fill(self, sub):
        return 0 if sub else 255

    # primitives -------------------------------------------------------------
    def poly(self, pts, round=0.0, sub=False):
        f = self._fill(sub)
        q = [self.P(p) for p in pts]
        self._d.polygon(q, fill=f)
        if round > 0:
            r = self.S(round) / 2
            for i in range(len(q)):
                a, b = q[i], q[(i + 1) % len(q)]
                self._d.line([a, b], fill=f, width=int(max(1, 2 * r)))
                self._d.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r], fill=f)

    def circle(self, cx, cy, r, sub=False):
        x, y = self.P((cx, cy)); rr = self.S(r)
        self._d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=self._fill(sub))

    def ring(self, cx, cy, r, w, sub=False):
        self.circle(cx, cy, r + w / 2, sub)
        self.circle(cx, cy, r - w / 2, not sub)

    def line(self, pts, w, cap=True, sub=False):
        f = self._fill(sub)
        q = [self.P(p) for p in pts]
        r = self.S(w) / 2
        self._d.line(q, fill=f, width=int(round(2 * r)), joint="curve")
        if cap:
            for a in (q[0], q[-1]):
                self._d.ellipse([a[0] - r, a[1] - r, a[0] + r, a[1] + r], fill=f)

    def rrect(self, x0, y0, x1, y1, r, sub=False):
        """Rounded rect, rotation-safe (built from polygon + corner circles)."""
        r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
        f = self._fill(sub)
        pts = [(x0 + r, y0), (x1 - r, y0), (x1, y0 + r), (x1, y1 - r),
               (x1 - r, y1), (x0 + r, y1), (x0, y1 - r), (x0, y0 + r)]
        self._d.polygon([self.P(p) for p in pts], fill=f)
        for (cx, cy) in [(x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)]:
            self.circle(cx, cy, r, sub)

    def rect(self, x0, y0, x1, y1, sub=False):
        self._d.polygon([self.P(p) for p in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]], fill=self._fill(sub))

    def arc(self, cx, cy, r, a0, a1, w, sub=False, n=40):
        pts = []
        for i in range(n + 1):
            a = math.radians(a0 + (a1 - a0) * i / n)
            pts.append((cx + r * math.cos(a), cy - r * math.sin(a)))
        self.line(pts, w, sub=sub)

    def done(self):
        return self.layers


# --------------------------------------------------------------- glass render
def _blur(a, sigma):
    if sigma < 0.3:
        return a
    return cv2.GaussianBlur(a, (0, 0), sigma)


def _over(dst, src_rgb, src_a):
    """premultiplied dst (M,M,4) <- src (straight rgb 3 floats/array, alpha array) over dst."""
    a = src_a[..., None]
    dst[..., :3] = dst[..., :3] * (1 - a) + np.asarray(src_rgb, np.float32) * a
    dst[..., 3:4] = dst[..., 3:4] * (1 - a) + a


_NOISE_CACHE = {}


def _noise(M, u):
    key = (M,)
    if key not in _NOISE_CACHE:
        rng = np.random.RandomState(7)
        n = rng.rand(M, M).astype(np.float32)
        n = _blur(n, 2.2 * u)
        n = (n - n.mean()) / (n.std() + 1e-6)
        _NOISE_CACHE[key] = n
    return _NOISE_CACHE[key]


THEMES = {
    "dark": dict(
        fill_top=(52, 58, 76), fill_bot=(10, 12, 19), fa0=0.76, fa1=0.14, noise=4.0,
        glyph=(240, 246, 255), glyph_shadow=(0, 0, 0), inner=(150, 185, 255), inner_gain=0.34,
        sheen=(255, 255, 255), sheen_a=0.15, rim=(232, 240, 255), rim_lo=0.50, rim_hi=0.45,
        rim2=None, outer=(6, 8, 14), outer_a=0.55, shadow=(0, 0, 0), shadow_a=1.0,
        halo_a=(80, 135, 255), halo_b=(155, 105, 255), halo_gain=0.62, tint=(150, 195, 255)),
    "light": dict(
        fill_top=(250, 252, 255), fill_bot=(188, 200, 226), fa0=0.80, fa1=-0.06, noise=-3.0,
        glyph=(30, 38, 62), glyph_shadow=(255, 255, 255), inner=(255, 255, 255), inner_gain=0.55,
        sheen=(255, 255, 255), sheen_a=0.40, rim=(44, 58, 98), rim_lo=0.88, rim_hi=0.12,
        rim2=(255, 255, 255), outer=(255, 255, 255), outer_a=0.65, shadow=(24, 32, 70), shadow_a=0.85,
        halo_a=(90, 135, 255), halo_b=(165, 115, 255), halo_gain=0.38, tint=(70, 120, 245)),
}


def render_layers(cv, theme="dark", halo=True):
    """Render Canvas layers to an NxN straight-alpha uint8 RGBA array."""
    T = THEMES[theme]
    M, u, N, ss = cv.M, cv.u, cv.N, cv.ss
    yy, xx = np.mgrid[0:M, 0:M].astype(np.float32)
    X, Y = (xx + 0.5) / u, (yy + 0.5) / u               # design units
    diag = np.clip((X + Y) / 64.0, 0, 1)                # 0 top-left .. 1 bottom-right
    out = np.zeros((M, M, 4), np.float32)
    noise = _noise(M, u)
    f3 = lambda k: np.array(T[k], np.float32)

    for L in cv.layers:
        m = np.asarray(L.img, np.float32) / 255.0
        if m.max() <= 0:
            continue
        inside = (m > 0.5).astype(np.uint8)
        if L.glyph:
            sh = _blur(np.roll(m, (int(0.5 * u), int(0.3 * u)), (0, 1)), 0.6 * u) * 0.35
            _over(out, T["glyph_shadow"], sh * (1 - m))
            _over(out, T["glyph"], m * 0.96)
            continue
        light = None
        if L.light is not None:
            light = np.clip(L.light(X, Y), 0, 1).astype(np.float32)

        din = cv2.distanceTransform(inside, cv2.DIST_L2, 5).astype(np.float32) / u
        dout = cv2.distanceTransform(1 - inside, cv2.DIST_L2, 5).astype(np.float32) / u

        # soft shadow (knocked out under the translucent glass)
        if L.shadow:
            s1 = _blur(np.roll(m, (int(1.1 * u), int(0.5 * u)), (0, 1)), 1.15 * u) * 0.42
            s2 = _blur(np.roll(m, (int(0.35 * u), int(0.15 * u)), (0, 1)), 0.4 * u) * 0.30
            sh = np.clip(s1 + s2, 0, 0.6) * T["shadow_a"]
            _over(out, T["shadow"], np.clip(sh, 0, 1) * (1 - m))

        # cool blue -> violet edge light just outside the shape (kept tight so it stays crisp at 32 px)
        if halo and L.shadow:
            hw = 0.95
            h = np.exp(-np.maximum(dout - 0.35, 0) / hw) * np.clip(1.2 - dout / 3.4, 0, 1) * (1 - m)
            g = np.clip(diag * 1.6, 0, 1)[..., None]
            hc = f3("halo_a") * (1 - g) + f3("halo_b") * g
            ha = np.clip(h * T["halo_gain"], 0, 1)
            if light is not None:
                ha = np.clip(ha + h * light * 0.25, 0, 1)
            _over(out, hc, ha)

        # smoky / frosted fill gradient
        col = np.empty((M, M, 3), np.float32)
        top, bot = f3("fill_top"), f3("fill_bot")
        t = np.clip(diag * 1.3, 0, 1)[..., None]
        col[:] = top * (1 - t) + bot * t
        col += (noise[..., None] * T["noise"])
        fa = (T["fa0"] + T["fa1"] * diag + noise * 0.03) * L.alpha
        if light is not None:
            tint = f3("tint")
            col = col * (1 - light[..., None] * 0.9) + tint * (light[..., None] * 0.9)
            fa = fa * (1 - light * 0.5) + 0.44 * light
        fa = np.clip(fa, 0, 1) * m
        _over(out, np.clip(col, 0, 255), fa)

        # inner glow
        g = np.exp(-din / 1.5) * m
        dirw = 0.75 + 0.5 * (1 - diag)
        _over(out, T["inner"], np.clip(g * T["inner_gain"] * dirw, 0, 1))

        # sheen (top-left specular)
        sheen = np.clip(1 - diag * 1.9, 0, 1) ** 1.5 * T["sheen_a"] * m
        _over(out, T["sheen"], sheen)

        # outer hairline
        ow = 0.65
        oa = np.clip((ow * u - dout * u) / 1.0 + 0.5, 0, 1) * (1 - m) * T["outer_a"]
        _over(out, T["outer"], oa)

        # rim (+ optional bright inner line for the light theme)
        rw = 0.95
        ra = np.clip((rw - din) * u + 0.5, 0, 1) * m
        rim_a = T["rim_lo"] + T["rim_hi"] * (1 - np.clip(diag * 1.4, 0, 1))
        if light is not None:
            rim_a = np.clip(rim_a + light * 0.5, 0, 1)
        _over(out, T["rim"], ra * rim_a)
        if T["rim2"] is not None:
            r2 = np.clip((rw + 0.75 - din) * u + 0.5, 0, 1) * np.clip((din - rw) * u + 0.5, 0, 1) * m
            _over(out, T["rim2"], r2 * 0.55)

    # box downsample in premultiplied space
    out = out.reshape(N, ss, N, ss, 4).mean(axis=(1, 3))
    a = out[..., 3:4]
    rgb = np.where(a > 1e-4, out[..., :3] / np.maximum(a, 1e-4), 0)
    res = np.concatenate([np.clip(rgb, 0, 255), np.clip(a, 0, 1) * 255], axis=-1)
    return np.clip(res + 0.5, 0, 255).astype(np.uint8)


def hot_px(h, N):
    return (min(N - 1, max(0, int(math.floor(h[0] * N / GRID + 0.5)))),
            min(N - 1, max(0, int(math.floor(h[1] * N / GRID + 0.5)))))


# ------------------------------------------------------------- file writers
def _dib(rgba):
    """32bpp BMP DIB (bottom-up BGRA straight alpha) + 1bpp AND mask."""
    h, w = rgba.shape[:2]
    bgra = rgba[..., [2, 1, 0, 3]][::-1].copy()
    hdr = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0, w * h * 4, 0, 0, 0, 0)
    stride = ((w + 31) // 32) * 4
    mask = bytearray()
    for y in range(h - 1, -1, -1):
        row = np.packbits((rgba[y, :, 3] == 0).astype(np.uint8))
        mask += bytes(row) + b"\x00" * (stride - len(row))
    return hdr + bgra.tobytes() + bytes(mask)


def build_cur(images):
    """images: list of (rgba ndarray NxNx4, (hx, hy)). Returns .cur bytes."""
    images = sorted(images, key=lambda t: t[0].shape[0])
    blobs = [_dib(im) for im, _ in images]
    out = struct.pack("<HHH", 0, 2, len(images))
    off = 6 + 16 * len(images)
    for (im, hs), b in zip(images, blobs):
        n = im.shape[0]
        out += struct.pack("<BBBBHHII", n if n < 256 else 0, n if n < 256 else 0, 0, 0, hs[0], hs[1], len(b), off)
        off += len(b)
    return out + b"".join(blobs)


def _chunk(cid, data):
    d = cid + struct.pack("<I", len(data)) + data
    if len(data) & 1:
        d += b"\x00"
    return d


def build_ani(frames, rates, title="Dark Blur", author="Dark Blur Cursor", seq=None):
    """frames: list of .cur byte strings; rates: jiffies (1/60 s) per step."""
    steps = len(seq) if seq else len(frames)
    flags = 1 | (2 if seq else 0)
    anih = struct.pack("<9I", 36, len(frames), steps, 0, 0, 32, 1, rates[0], flags)
    info = b"INFO" + _chunk(b"INAM", title.encode("latin1") + b"\0") + _chunk(b"IART", author.encode("latin1") + b"\0")
    body = b"ACON" + _chunk(b"LIST", info) + _chunk(b"anih", anih)
    body += _chunk(b"rate", struct.pack("<%dI" % len(rates), *rates))
    if seq:
        body += _chunk(b"seq ", struct.pack("<%dI" % len(seq), *seq))
    body += _chunk(b"LIST", b"fram" + b"".join(_chunk(b"icon", f) for f in frames))
    return b"RIFF" + struct.pack("<I", len(body)) + body


# ----------------------------------------------------------------- parsers
def parse_cur(data):
    r, t, n = struct.unpack("<HHH", data[:6])
    assert r == 0 and t == 2, "not a .cur"
    ents = []
    for i in range(n):
        w, h, cc, rs, hx, hy, sz, off = struct.unpack("<BBBBHHII", data[6 + 16 * i:22 + 16 * i])
        w = w or 256; h = h or 256
        blob = data[off:off + sz]
        assert len(blob) == sz
        bih = struct.unpack("<IiiHHI", blob[:20])
        assert bih[0] == 40 and bih[1] == w and bih[2] == 2 * h and bih[4] == 32, bih
        ents.append(dict(w=w, h=h, hx=hx, hy=hy, size=sz))
    return ents


def parse_ani(data):
    assert data[:4] == b"RIFF" and data[8:12] == b"ACON"
    assert struct.unpack("<I", data[4:8])[0] == len(data) - 8
    info = {"frames": []}
    def walk(o, end):
        while o < end:
            cid = data[o:o + 4]; sz = struct.unpack("<I", data[o + 4:o + 8])[0]
            if cid == b"LIST":
                typ = data[o + 8:o + 12]
                if typ == b"fram":
                    walk(o + 12, o + 8 + sz)
            elif cid == b"anih":
                v = struct.unpack("<9I", data[o + 8:o + 44])
                info["anih"] = dict(nFrames=v[1], nSteps=v[2], jif=v[7], flags=v[8])
            elif cid == b"rate":
                info["rate"] = list(struct.unpack("<%dI" % (sz // 4), data[o + 8:o + 8 + sz]))
            elif cid == b"seq ":
                info["seq"] = list(struct.unpack("<%dI" % (sz // 4), data[o + 8:o + 8 + sz]))
            elif cid == b"icon":
                info["frames"].append(parse_cur(data[o + 8:o + 8 + sz]))
            o += 8 + sz + (sz & 1)
    walk(12, len(data))
    return info


def decode_cur(data, size):
    """Decode one 32bpp image of a .cur by hand (true alpha channel) -> (RGBA ndarray, (hx, hy))."""
    n = struct.unpack("<H", data[4:6])[0]
    for i in range(n):
        w, h, cc, rs, hx, hy, sz, off = struct.unpack("<BBBBHHII", data[6 + 16 * i:22 + 16 * i])
        if (w or 256) == size:
            w = w or 256
            px = np.frombuffer(data, np.uint8, w * w * 4, off + 40).reshape(w, w, 4)[::-1]
            return px[..., [2, 1, 0, 3]].copy(), (hx, hy)
    raise KeyError(size)
