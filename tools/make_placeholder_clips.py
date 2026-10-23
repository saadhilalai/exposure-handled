"""Placeholder clips for the project website (site/), until real FX2 footage exists.

Every clip is a made-up scene, not camera footage, and the site labels each one PLACEHOLDER.
They're made the way the camera would see them: the scene is built in linear light (0.18 = grey),
encoded with Sony's published S-Log3 curve (the same one as agent/tone.py), and the graded
version goes through the blind test's LUT (luts/, Sony's file, never in the repo).

Scenes (each loops seamlessly):
  night    out-of-focus city lights, tungsten and LED, drifting   -> night.mp4 + night-log.mp4
  lamp     a warm lamp on a textured wall, a plant's shadow swaying -> lamp.mp4
  sunbeam  late sun through a window onto a wall, dust in the beam -> sunbeam.mp4

Encoding uses the Mac's hardware H.264 encoder (VideoToolbox), so the CPU stays light.

Usage: python tools/make_placeholder_clips.py [--seconds 10] [--only night]
"""
import argparse
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "media" / "placeholder"
LUT = ROOT / "luts" / "2_SGamut3CineSLog3_To_LC-709TypeA.cube"
FPS = 24
W, H = 1600, 900
GREY = 0.18
TITLE = "PLACEHOLDER: made-up scene, not footage from the Sony cinema camera (camera-agent site)"

# Light colours (linear RGB, roughly white-balanced for 5600K)
TUNGSTEN = np.array([1.0, 0.62, 0.32], np.float32)
SODIUM = np.array([1.0, 0.48, 0.12], np.float32)
COOL = np.array([0.72, 0.84, 1.0], np.float32)
LED = np.array([0.42, 0.58, 1.0], np.float32)
RED = np.array([1.0, 0.16, 0.1], np.float32)
SUN = np.array([1.0, 0.74, 0.46], np.float32)


def stops(s):
    return GREY * 2.0 ** s


def slog3(x):
    """Linear reflectance -> S-Log3 code value as 0..1 of 10-bit full range (420/1023 = grey)."""
    x = np.maximum(x, 0.0)
    code = np.where(x >= 0.01125, 420.0 + 261.5 * np.log10((x + 0.01) / 0.19),
                    95.0 + x * (171.2102946929 - 95.0) / 0.01125)
    return np.clip(code / 1023.0, 0.0, 1.0)


def tileable_noise(h, w, sigma, rng):
    """Smooth random field that wraps at the edges (so it can be scrolled forever), 0..1."""
    fy, fx = np.fft.fftfreq(h)[:, None], np.fft.fftfreq(w)[None, :]
    blur = np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))      # a Gaussian blur, done in the FFT
    n = np.fft.ifft2(np.fft.fft2(rng.random((h, w))) * blur).real.astype(np.float32)   # so it wraps
    return (n - n.min()) / (n.max() - n.min())


def vignette(strength=0.35):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((x - W / 2) / (W / 2), (y - H / 2) / (H / 2)) / np.sqrt(2)
    return (1 - strength * r ** 2)[..., None]


class Night:
    """Out-of-focus city lights drifting left, near ones faster: a pan past a street at night."""

    def __init__(self, T, rng):
        self.T, self.w, self.h = T, W // 2, H // 2
        self.lights = []
        for layer, n, rmin, rmax in ((0, 46, 9, 20), (1, 22, 24, 52)):
            for _ in range(n):
                self.lights.append(dict(
                    layer=layer, x=rng.random(), y=float(np.clip(rng.normal(0.52, 0.17 + 0.08 * layer), 0.08, 0.95)),
                    r=rng.uniform(rmin, rmax), bob=rng.uniform(0, 2 * np.pi),
                    colour=[TUNGSTEN, SODIUM, COOL, LED, RED, TUNGSTEN, SODIUM, COOL][rng.integers(8)],
                    level=stops(rng.uniform(-1.2, 3.6) - layer * 1.0)))
        y = np.linspace(0, 1, self.h, dtype=np.float32)[:, None, None]
        self.base = (stops(-6.5) * (0.6 + 0.8 * y) * np.array([0.7, 0.8, 1.0], np.float32)
                     + stops(-5.5) * np.exp(-((y - 0.8) / 0.2) ** 2) * SODIUM)
        self.vig = cv2.resize(vignette(0.5), (self.w, self.h))[..., None]

    def frame(self, t):
        img = np.broadcast_to(self.base, (self.h, self.w, 3)).copy()
        p = t / self.T
        for L in self.lights:
            span = self.w + 4 * L["r"]
            x = (L["x"] * span - p * span * (1 + L["layer"])) % span - 2 * L["r"]
            y = L["y"] * self.h + 3 * np.sin(2 * np.pi * p + L["bob"])
            r = L["r"] * (1 + 0.04 * np.sin(2 * np.pi * p + L["bob"]))     # a little focus breathing
            x0, x1 = int(max(x - r - 3, 0)), int(min(x + r + 4, self.w))
            y0, y1 = int(max(y - r - 3, 0)), int(min(y + r + 4, self.h))
            if x1 <= x0 or y1 <= y0:
                continue
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            d = np.hypot(xx - x, yy - y) / r
            disc = np.clip((1 - d) * r / 1.6, 0, 1) * (0.8 + 0.35 * d ** 6)  # soft edge, brighter rim
            img[y0:y1, x0:x1] += disc[..., None] * L["level"] * L["colour"]
        img = cv2.GaussianBlur(img, (0, 0), 1.2) + 0.12 * cv2.GaussianBlur(img, (0, 0), 30)  # glow
        return cv2.resize(img * self.vig, (W, H), interpolation=cv2.INTER_LINEAR)


class Lamp:
    """A warm practical lamp on a textured wall, cool window fill, a plant's shadow swaying."""

    def __init__(self, T, rng):
        self.T = T
        h, w = H // 2, W // 2
        self.h, self.w = h, w
        albedo = 0.62 + 0.08 * tileable_noise(h, w, 40, rng) + 0.03 * tileable_noise(h, w, 1.5, rng)
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        pool = np.exp(-(((x - 0.78 * w) / (0.42 * w)) ** 2 + ((y - 0.18 * h) / (0.55 * h)) ** 2))
        hot = np.exp(-(((x - 0.84 * w) / (0.12 * w)) ** 2 + ((y - 0.1 * h) / (0.2 * h)) ** 2))
        self.light = (stops(1.2) * pool[..., None] * TUNGSTEN + stops(2.4) * hot[..., None] * TUNGSTEN
                      + stops(-2.6) * (1 - x / w)[..., None] * COOL) * albedo[..., None]
        self.leaves = tileable_noise(h * 2, w * 2, 18, rng)
        self.vig = cv2.resize(vignette(0.45), (w, h))[..., None]

    def frame(self, t):
        a = 2 * np.pi * t / self.T
        dx, dy = int(14 * np.sin(a)), int(6 * np.sin(2 * a))
        leaf = np.roll(self.leaves, (dy, dx), axis=(0, 1))[:self.h, int(0.35 * self.w):int(0.35 * self.w) + self.w]
        shadow = 1 - 0.5 * cv2.GaussianBlur(np.clip((leaf - 0.62) * 8, 0, 1), (0, 0), 5)
        breathe = 2 ** (0.08 * np.sin(a))
        img = self.light * (shadow[..., None] * 0.85 + 0.15) * breathe
        return cv2.resize(img * self.vig, (W, H), interpolation=cv2.INTER_LINEAR)


class Sunbeam:
    """Late sun through a window: the panes land on the wall, leaves outside move, dust in the beam."""

    def __init__(self, T, rng):
        self.T = T
        h, w = H // 2, W // 2
        self.h, self.w = h, w
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        self.x, self.y = x, y
        self.room = stops(-3.4) * (0.55 + 0.45 * y / h)[..., None] * np.array([0.92, 0.74, 0.6], np.float32)
        u = (x * 0.62 - y * 0.78) / w                                 # across the shaft of light in the air
        self.haze = np.exp(-(u / 0.12) ** 2) * (1 - y / h) ** 0.5
        self.leaves = tileable_noise(h * 2, w * 2, 16, rng)
        self.dust = [dict(x=rng.random(), y=rng.random(), s=rng.uniform(0.6, 1.8), ph=rng.uniform(0, 6.3),
                          k=int(rng.integers(1, 3))) for _ in range(160)]
        self.vig = cv2.resize(vignette(0.5), (w, h))[..., None]

    def panes(self, drift):
        """The window's 2 x 3 panes thrown onto the wall, sheared by the low sun."""
        x0, y0, pw, ph, shear = 0.40 * self.w + drift, 0.16 * self.h, 0.36 * self.w, 0.78 * self.h, 0.42
        u = (self.x - x0 - shear * (self.y - y0)) / pw
        v = (self.y - y0) / ph
        inside = (u > 0) & (u < 1) & (v > 0) & (v < 1)
        bar = 0.035
        mull = (np.abs((u * 2 + 0.5) % 1 - 0.5) < bar * 2) | (np.abs((v * 3 + 0.5) % 1 - 0.5) < bar * 3)
        return cv2.GaussianBlur((inside & ~mull).astype(np.float32), (0, 0), 3.5)

    def frame(self, t):
        a = 2 * np.pi * t / self.T
        leaf = np.roll(self.leaves, (int(8 * np.sin(a)), int(14 * np.cos(a))), axis=(0, 1))[:self.h, :self.w]
        dapple = 0.55 + 0.45 * cv2.GaussianBlur(np.clip((leaf - 0.3) * 2.5, 0, 1), (0, 0), 2)
        light = self.panes(6 * np.sin(a)) * dapple
        img = self.room + stops(2.9) * light[..., None] * SUN + stops(-0.6) * (self.haze * dapple)[..., None] * SUN
        motes = np.zeros((self.h, self.w), np.float32)
        for d in self.dust:
            x = ((d["x"] + 0.03 * np.sin(a * d["k"] + d["ph"])) % 1) * self.w
            y = ((d["y"] - t / self.T * d["k"] * 0.25) % 1) * self.h
            cv2.circle(motes, (int(x * 4), int(y * 4)), int(d["s"] * 4), 1.0, -1, cv2.LINE_AA, shift=2)
        motes = cv2.GaussianBlur(motes, (0, 0), 0.8) * self.haze
        img += stops(2.2) * motes[..., None] * SUN
        return cv2.resize(img * self.vig, (W, H), interpolation=cv2.INTER_LINEAR)


def encode(name, scene, seconds, with_log, rng):
    graded = OUT / ("%s.mp4" % name)
    common = ["-c:v", "h264_videotoolbox", "-b:v", "3.2M", "-pix_fmt", "yuv420p", "-tag:v", "avc1",
              "-movflags", "+faststart", "-color_primaries", "bt709", "-color_trc", "bt709",
              "-colorspace", "bt709", "-metadata", "title=" + TITLE]
    cmd = ["nice", "-n", "15", "ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb48le",
           "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-"]
    if with_log:
        cmd += ["-filter_complex", "[0:v]split=2[log][in];[in]lut3d=file='%s':interp=tetrahedral[out]" % LUT,
                "-map", "[out]", *common, str(graded), "-map", "[log]", *common, str(OUT / ("%s-log.mp4" % name))]
    else:
        cmd += ["-vf", "lut3d=file='%s':interp=tetrahedral" % LUT, *common, str(graded)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(seconds * FPS)
    for k in range(n):
        code = slog3(scene.frame(k / FPS))
        code = code + rng.normal(0, 0.0025, code.shape).astype(np.float32)        # a little sensor noise
        ff.stdin.write((np.clip(code, 0, 1) * 65535).astype("<u2").tobytes())
    ff.stdin.close()
    if ff.wait():
        sys.exit("ffmpeg failed on %s" % name)
    for clip in [graded] + ([OUT / ("%s-log.mp4" % name)] if with_log else []):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", str(clip), "-frames:v", "1", "-q:v", "4",
                        str(clip.with_suffix(".jpg"))], check=True)
    print("made", graded.relative_to(ROOT), "(+ log)" if with_log else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=float, default=10)
    ap.add_argument("--only", choices=["night", "lamp", "sunbeam"])
    args = ap.parse_args()
    if not LUT.exists():
        sys.exit("Needs the blind test's LUT at %s (see luts/README.md)." % LUT.relative_to(ROOT))
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261019)
    for name, cls, with_log in (("night", Night, True), ("lamp", Lamp, False), ("sunbeam", Sunbeam, False)):
        if args.only in (None, name):
            encode(name, cls(args.seconds, rng), args.seconds, with_log, rng)


if __name__ == "__main__":
    main()
