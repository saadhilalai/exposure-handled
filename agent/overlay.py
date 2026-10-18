"""Draw what the eyes see on top of the live view: zebras, false color, face boxes, numbers.

False color uses stops vs 18% grey, so it reads the same in log and normal modes.
"""
import cv2
import numpy as np

from agent.eyes import GRID_COLS, GRID_ROWS, LUMA_WEIGHTS

# (name, low stops, high stops, BGR color). "clip" bands are relative to the clip point.
FALSE_COLOR_BANDS = [
    ("crushed", None, -6.0, (128, 0, 128)),        # purple
    ("deep shadow", -6.0, -3.0, (120, 40, 0)),     # dark blue
    ("18% grey", -0.25, 0.25, (60, 200, 60)),      # green
    ("skin (light)", 0.5, 1.5, (180, 120, 255)),   # pink
    ("90% white", 2.0, 2.6, (230, 220, 60)),       # cyan
]
NEAR_CLIP = (0, 220, 255)   # yellow
CLIPPED = (0, 0, 255)       # red
FONT = cv2.FONT_HERSHEY_SIMPLEX


def _luma(bgr):
    out = cv2.transform(bgr, LUMA_WEIGHTS.reshape(1, 3))
    return out[..., 0] if out.ndim == 3 else out


def false_color(bgr, tm):
    luma = _luma(bgr)
    stops = tm.to_stops(luma)
    grey = (luma.astype(np.float32) * 0.8).astype(np.uint8)
    out = cv2.cvtColor(grey, cv2.COLOR_GRAY2BGR)
    for _, lo, hi, color in FALSE_COLOR_BANDS:
        mask = np.ones_like(luma, dtype=bool)
        if lo is not None:
            mask &= stops >= lo
        if hi is not None:
            mask &= stops < hi
        out[mask] = color
    near = luma >= tm.level_for_stops(tm.clip_stops - 0.5)
    out[near] = NEAR_CLIP
    out[luma >= tm.clip_level - 1] = CLIPPED
    return out


def zebras(bgr, tm, stripe=6):
    """Diagonal stripes: red/white where clipped, yellow where within half a stop of clipping."""
    out = bgr.copy()
    luma = _luma(bgr)
    h, w = luma.shape
    yy, xx = np.mgrid[0:h, 0:w]
    stripes = ((xx + yy) // stripe) % 2 == 0
    clipped = luma >= tm.clip_level - 1
    near = (luma >= tm.level_for_stops(tm.clip_stops - 0.5)) & ~clipped
    out[near & stripes] = NEAR_CLIP
    out[clipped & stripes] = CLIPPED
    out[clipped & ~stripes] = (255, 255, 255)
    return out


def draw_faces(img, report):
    for i, f in enumerate(report.faces, 1):
        x, y, w, h = f["box"]
        cv2.rectangle(img, (x, y), (x + w, y + h), (60, 220, 60), 2)
        label = "Face %d  %+.1f st" % (i, f["stops"])
        cv2.rectangle(img, (x, y - 22), (x + 9 * len(label), y), (60, 220, 60), -1)
        cv2.putText(img, label, (x + 4, y - 6), FONT, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    return img


def draw_regions(img, report):
    """Outline regions the eyes treat specially: light sources (orange), changed/moving (cyan)."""
    h, w = img.shape[:2]
    cw, ch = w / GRID_COLS, h / GRID_ROWS
    for c in range(1, GRID_COLS):
        cv2.line(img, (int(c * cw), 0), (int(c * cw), h), (90, 90, 90), 1)
    for r in range(1, GRID_ROWS):
        cv2.line(img, (0, int(r * ch)), (w, int(r * ch)), (90, 90, 90), 1)

    def box(rc, color, tag):
        r, c = rc
        p0, p1 = (int(c * cw) + 2, int(r * ch) + 2), (int((c + 1) * cw) - 2, int((r + 1) * ch) - 2)
        cv2.rectangle(img, p0, p1, color, 2)
        cv2.putText(img, tag, (p0[0] + 4, p0[1] + 16), FONT, 0.45, color, 1, cv2.LINE_AA)

    for rc in report.light_source_regions:
        box(rc, (0, 160, 255), "light")
    for rc in (report.change or {}).get("changed_regions", []):
        box(rc, (255, 220, 0), "changed")
    return img


def draw_panel(img, report, ctx, extra_lines=()):
    tone = "S-LOG3" if report.tone == "slog3" else "NORMAL (Rec.709-like)"
    faces = ", ".join("%+.1f st" % f["stops"] for f in report.faces) or "none"
    color = report.color
    if color.get("light_estimate_k"):
        light = "light ~%dK (%s)" % (color["light_estimate_k"], color.get("confidence"))
    elif "warm_cool" in color:
        light = "cast: %s / %s (%s conf.)" % (color["warm_cool"], color["green_magenta"], color.get("confidence"))
    else:
        light = "color: n/a"
    lines = [
        tone + "   " + report.tone_source,
        "ISO %s   %s   %s   WB %s   %s" % (ctx.iso.replace("ISO ", ""), ctx.shutter, ctx.fnumber, ctx.wb, ctx.frame_rate),
        "Key %+.1f st   Faces: %s" % (report.key_stops, faces),
        "Clipped %.1f%%   Near clip %.1f%%   Crushed %.1f%%" % (report.clipped_pct, report.near_clip_pct, report.crushed_pct),
        light,
    ]
    if report.motion is not None:
        lines.append("Motion %.0f%%   Exposure shift %+.2f st" % (report.motion["moving_pct"], report.change["exposure_shift_stops"]))
    lines += list(extra_lines)
    width = max(cv2.getTextSize(s, FONT, 0.5, 1)[0][0] for s in lines) + 20
    overlay = img.copy()
    cv2.rectangle(overlay, (8, 8), (8 + width, 16 + 20 * len(lines)), (0, 0, 0), -1)
    img[:] = cv2.addWeighted(overlay, 0.6, img, 0.4, 0)
    for i, s in enumerate(lines):
        cv2.putText(img, s, (18, 28 + 20 * i), FONT, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def draw_legend(img):
    h, w = img.shape[:2]
    items = [(n, c) for n, _, _, c in FALSE_COLOR_BANDS] + [("near clip", NEAR_CLIP), ("clipped", CLIPPED)]
    x = 10
    cv2.rectangle(img, (0, h - 30), (w, h), (0, 0, 0), -1)
    for name, color in items:
        cv2.rectangle(img, (x, h - 22), (x + 14, h - 8), color, -1)
        cv2.putText(img, name, (x + 20, h - 10), FONT, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
        x += 30 + cv2.getTextSize(name, FONT, 0.45, 1)[0][0]
    return img


def render(bgr, report, ctx, tm, mode="assist", extra_lines=()):
    """mode: clean | zebras | false_color | faces | regions | assist (zebras + faces + regions + numbers)."""
    if mode == "clean":
        return bgr.copy()
    if mode == "zebras":
        return draw_panel(zebras(bgr, tm), report, ctx, extra_lines)
    if mode == "false_color":
        return draw_legend(draw_panel(false_color(bgr, tm), report, ctx, extra_lines))
    if mode == "faces":
        return draw_panel(draw_faces(bgr.copy(), report), report, ctx, extra_lines)
    if mode == "regions":
        return draw_panel(draw_regions(bgr.copy(), report), report, ctx, extra_lines)
    img = zebras(bgr, tm)
    draw_regions(img, report)
    draw_faces(img, report)
    return draw_panel(img, report, ctx, extra_lines)
