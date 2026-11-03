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


# ------------------------------------------------------- monochrome whitish frosted style
THEMES = {
    # dark theme: whitish frosted body, soft white glow, thin darker edge
    "dark": dict(body_top=(238, 241, 249), body_bot=(168, 176, 196), body_dim=(98, 104, 122), body_a=0.92,
                 edge=(54, 59, 76), edge_hw=0.62, glow=(255, 255, 255), glow_a=0.60, tint_a=0.0,
                 shimmer=(255, 255, 255), glyph=(30, 34, 50), glyph_shadow=(255, 255, 255),
                 shadow=(0, 0, 0), shadow_a=0.38),
    # light theme: whitish body too, slightly stronger gray edge + soft gray shadow so it reads on light backgrounds
    "light": dict(body_top=(252, 253, 255), body_bot=(196, 203, 220), body_dim=(130, 137, 156), body_a=0.96,
                  edge=(78, 85, 106), edge_hw=0.85, glow=(44, 50, 70), glow_a=0.42, tint_a=0.0,
                  shimmer=(255, 255, 255), glyph=(30, 34, 50), glyph_shadow=(255, 255, 255),
                  shadow=(28, 34, 60), shadow_a=0.50),
}


def render_layers(cv, theme="dark", phase=None, pulse=1.0):
    """Monochrome whitish-frosted render of Canvas layers -> NxN straight-alpha uint8 RGBA.

    phase: None = static; 0..1 = position of the white shimmer sweeping across the shape.
    pulse: brightness of the outer glow (~1)."""
    T = THEMES[theme]
    M, u, N, ss = cv.M, cv.u, cv.N, cv.ss
    HW = T["edge_hw"]
    yy, xx = np.mgrid[0:M, 0:M].astype(np.float32)
    X, Y = (xx + 0.5) / u, (yy + 0.5) / u
    out = np.zeros((M, M, 4), np.float32)
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
        ys, xs = np.nonzero(inside)
        x0, x1, y0, y1 = xs.min() / u, xs.max() / u, ys.min() / u, ys.max() / u
        spat = np.clip(((X - x0) + (Y - y0)) / max((x1 - x0) + (y1 - y0), 1e-3), 0, 1)

        din = cv2.distanceTransform(inside, cv2.DIST_L2, 5).astype(np.float32) / u
        dout = cv2.distanceTransform(1 - inside, cv2.DIST_L2, 5).astype(np.float32) / u
        sd = np.where(inside > 0, -din, dout)                              # signed distance (+ outside)

        # emphasis map e: white shimmer band sweeping across, or the spinner's bright head
        e = np.zeros((M, M), np.float32)
        spinner = L.light is not None
        if spinner:
            e = np.clip(L.light(X, Y), 0, 1).astype(np.float32)
        elif phase is not None:
            c = -0.30 + 1.60 * phase
            e = np.exp(-((spat - c) / 0.17) ** 2).astype(np.float32)

        # soft shadow (gray, stronger in the light theme)
        if L.shadow:
            s1 = _blur(np.roll(m, (int(0.9 * u), int(0.6 * u)), (0, 1)), 1.1 * u) * T["shadow_a"]
            _over(out, T["shadow"], np.clip(s1, 0, 1) * (1 - m))

        # soft neutral outer glow, pulsing; brighter where the shimmer passes
        if L.shadow:
            o = np.maximum(sd - HW, 0)
            g1 = np.exp(-o / 0.9) * np.clip(1.0 - o / 3.5, 0, 1)
            g2 = np.exp(-o / 2.2) * np.clip(1.0 - o / 6.0, 0, 1)
            gk = pulse * (0.55 + 0.6 * e) if not spinner else pulse * (0.20 + 0.80 * e)
            _over(out, T["glow"], np.clip((g1 * 0.8 + g2 * 0.4) * T["glow_a"] * gk, 0, 1) * (1 - m))

        # whitish frosted body: vertical gradient, soft top-left sheen
        g = np.clip((Y - y0) / max(y1 - y0, 1e-3), 0, 1)[..., None]
        body = f3("body_top") * (1 - g) + f3("body_bot") * g
        if spinner:                                                        # tail is gray, head is white
            body = f3("body_dim") * (1 - e[..., None]) + f3("body_top") * e[..., None]
        _over(out, body, m * T["body_a"] * L.alpha)
        _over(out, (255, 255, 255), m * np.clip(1 - spat * 1.6, 0, 1) ** 1.5 * 0.30)
        if not spinner:                                                    # the white shimmer
            _over(out, T["shimmer"], m * e * 0.95)

        # thin darker edge for definition, plus a bright inner rim (frost)
        band = np.clip((HW - np.abs(sd)) * u + 0.5, 0, 1)
        _over(out, T["edge"], band * 0.96)
        rim = np.clip((0.28 - np.abs(sd + HW + 0.30)) * u + 0.5, 0, 1) * (sd < 0)
        _over(out, (255, 255, 255), rim * 0.70)

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
    info = b"INFO" + _chunk(b"INAM", title.encode("latin1", "replace") + b"\0") + _chunk(b"IART", author.encode("latin1") + b"\0")
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
