"""Make the paper textures for the art films: warm, slightly fibrous, very subtle (1920x1080 PNGs, tileable enough).
    python video/tools/make_paper.py <out_dir>"""
import sys
from pathlib import Path

import cv2
import numpy as np

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(7)
H, W = 1080, 1920


def noise(scale, octaves=4):
    acc = np.zeros((H, W), np.float32)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        s = max(2, int(scale / 2 ** o))
        small = rng.standard_normal((H // s + 2, W // s + 2)).astype(np.float32)
        acc += amp * cv2.resize(small, (W + 2 * s, H + 2 * s), interpolation=cv2.INTER_CUBIC)[s:s + H, s:s + W]
        tot += amp
        amp *= 0.55
    return acc / tot


# grain + soft blotches + a few long fibres; returned as a multiply layer around 1.0
base = 1.0 + 0.035 * noise(220, 3) + 0.025 * noise(6, 2)
fib = np.zeros((H, W), np.float32)
for _ in range(900):
    x, y = rng.uniform(0, W), rng.uniform(0, H)
    a, ln = rng.uniform(0, np.pi), rng.uniform(8, 60)
    x2, y2 = x + np.cos(a) * ln, y + np.sin(a) * ln
    cv2.line(fib, (int(x), int(y)), (int(x2), int(y2)), float(rng.uniform(0.3, 1.0)), 1, cv2.LINE_AA)
fib = cv2.GaussianBlur(fib, (0, 0), 0.6)
tex = np.clip(base - 0.045 * fib, 0.85, 1.08)
# as a grey multiply texture: 255 = no change
g = np.clip(tex / 1.08 * 255, 0, 255).astype(np.uint8)
cv2.imwrite(str(out / "paper.png"), cv2.merge([g, g, g]))
# light flecks for dark fields (screen layer)
fl = np.zeros((H, W), np.float32)
for _ in range(1600):
    cv2.circle(fl, (int(rng.uniform(0, W)), int(rng.uniform(0, H))), int(rng.integers(0, 2)), float(rng.uniform(0.15, 0.6)), -1, cv2.LINE_AA)
fl = cv2.GaussianBlur(fl, (0, 0), 0.7) + 0.06 * np.clip(noise(4, 2), 0, None)
cv2.imwrite(str(out / "flecks.png"), np.clip(fl * 255, 0, 255).astype(np.uint8))
print("paper textures ->", out)
