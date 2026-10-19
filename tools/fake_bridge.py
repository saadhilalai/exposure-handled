"""A fake FX2 that speaks the bridge's language, so the runner can be tried with no camera.

Same socket protocol as bridge/src/camera_bridge.cpp (ping, status, settings, get, frame,
lvstats, set, lock, quit) and the same checks before a change: read-only, kill switch,
allow-list (ISO 800-12800; with --allow-exposure also f/2.8-f/11, 1/48-1/100 and WB Auto /
Color Temp 2800-7500K, like the real bridge), recording, value offered.
White balance: the light has a color temperature (--light-k, default 3200K). On Auto WB the
picture is neutral; on Color Temp it gets the cast a real camera would show (warmer when the
WB setting is above the light).
The picture is a recorded frame (or a made-up test scene) made brighter or darker by
the exposure change, using the measured S-Log3 calibration (20.63 levels/stop, clip 221).
Like the real FX2 (Step 3), a change is confirmed after ~0.15 s and shows in the picture
~0.3 s after it's sent. Nothing here talks to a real camera.

Usage:
  python tools/fake_bridge.py                         # made-up scene at ISO 800, 1/160, f/2.8
  python tools/fake_bridge.py --frame clean.jpg --iso 1600 --shutter 50 --fnumber 5.6
         [--light 20:-1 40:0.7]   from 20 s the room is 1 stop darker, from 40 s 0.7 stop brighter
         [--record 30:40]         the camera records from 30 s to 40 s
         [--read-only | --allow-iso-while-recording | --allow-exposure] [--light-k 3200]
         [--socket run/fake_bridge.sock] [--log-dir DIR]
"""
import argparse
import copy
import json
import math
import socketserver
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.tone import ToneModel, load_calibration  # noqa: E402

SETTINGS_FILE = Path(__file__).resolve().parent / "fake_camera_settings.json"
DEFAULT_SOCKET = ROOT / "run" / "fake_bridge.sock"
# Same as the real bridge's compiled-in list: (min, max, needs --allow-exposure)
ALLOW_LIST = {"IsoSensitivity": (800, 12800, False), "FNumber": (280, 1100, True), "ShutterSpeed": (48, 100, True),
              "Colortemp": (2800, 7500, True), "WhiteBalance": (0x0000, 0x0100, True)}
EXPOSURE = ("IsoSensitivity", "FNumber", "ShutterSpeed")
AWB, COLOR_TEMP = 0x0000, 0x0100
REMEMBERED_K = 5600                              # the Kelvin the fake "remembers" for Color Temp mode
RECORDING = 1                                    # CrMovie_Recording_State_Recording
CONFIRM_S, SHOW_S = 0.15, 0.3                    # measured on the FX2: 119-172 ms / 272-325 ms
CLIPPED_EXTRA_STOPS = 1.0                        # clipped areas of a recorded frame: assumed 1 stop over clip


def exposure_ev(values):
    """Exposure in stops (bigger = brighter picture) from raw ISO / FNumber / ShutterSpeed."""
    shutter = values["ShutterSpeed"]
    return (math.log2(values["IsoSensitivity"] & 0xFFFFFF) - 2 * math.log2(values["FNumber"] / 100)
            + math.log2((shutter >> 16) / (shutter & 0xFFFF)))


def rule_allows(name, raw):
    """The real bridge's rule_allows(), value by value."""
    lo, hi, _ = ALLOW_LIST[name]
    if name == "IsoSensitivity":
        return not raw >> 24 and lo <= (raw & 0xFFFFFF) <= hi
    if name == "ShutterSpeed":
        num, den = (raw >> 16) & 0xFFFF, raw & 0xFFFF
        return not raw >> 32 and num >= 1 and num * lo <= den <= num * hi
    if name == "WhiteBalance":
        return raw in (lo, hi)
    return lo <= raw <= hi


def camera_offers(prop, raw):
    values = prop["set_values"] or prop["values"]
    if prop["type"].endswith("Range") and len(values) == 3:
        lo, hi, step = values
        return lo <= raw <= hi and (step <= 0 or (raw - lo) % step == 0)
    return raw in values


def planckian_xy(k):
    """Kim et al. (2002) cubic fit of the Planckian locus, 1667-25000K."""
    t = float(k)
    if t <= 4000:
        x = -0.2661239e9 / t ** 3 - 0.2343589e6 / t ** 2 + 0.8776956e3 / t + 0.179910
    else:
        x = -3.0258469e9 / t ** 3 + 2.1070379e6 / t ** 2 + 0.2226347e3 / t + 0.240390
    if t <= 2222:
        y = -1.1063814 * x ** 3 - 1.34811020 * x ** 2 + 2.18555832 * x - 0.20219683
    elif t <= 4000:
        y = -0.9549476 * x ** 3 - 1.37418593 * x ** 2 + 2.09137015 * x - 0.16748867
    else:
        y = 3.0817580 * x ** 3 - 5.87338670 * x ** 2 + 3.75112997 * x - 0.37001483
    return x, y


def cast_stops(light_k, wb_k):
    """Per-channel (B, G, R) brightness offsets, in stops, of a neutral surface lit by `light_k` and shot at
    WB `wb_k` (None = Auto WB: neutral). The cast is the light's color moved by the WB error, in mireds."""
    from agent.eyes import D65, PRIMARIES, rgb_to_xyz_matrix
    if wb_k is None:
        return np.zeros(3, np.float32)
    mired = 1e6 / 6504.0 + (1e6 / light_k - 1e6 / wb_k)
    x, y = planckian_xy(1e6 / max(mired, 1e6 / 25000))
    xyz = np.array([x / y, 1.0, (1 - x - y) / y])
    rgb = np.linalg.solve(rgb_to_xyz_matrix(PRIMARIES["slog3"], D65), xyz)
    x6, y6 = planckian_xy(6504.0)
    rgb6 = np.linalg.solve(rgb_to_xyz_matrix(PRIMARIES["slog3"], D65), np.array([x6 / y6, 1.0, (1 - x6 - y6) / y6]))
    gains = np.maximum(rgb / rgb6, 1e-3)                  # relative to how the Planckian 6504K renders
    gains /= gains[1]
    return np.log2(gains[::-1]).astype(np.float32)        # RGB -> BGR


def made_up_scene(w, h, tm):
    """A neutral test scene in stops vs grey: a gradient from -1.5 to +0.5 st and one small clipped lamp."""
    stops = np.linspace(-1.5, 0.5, w, dtype=np.float32)[None, :] + np.linspace(-0.3, 0.3, h, dtype=np.float32)[:, None]
    stops[h // 24: h // 8, int(w * 0.77): int(w * 0.85)] = tm.clip_stops + 3     # inside one grid region
    return np.repeat(stops[..., None], 3, axis=2)


class FakeCamera:
    def __init__(self, frame=None, size=(1024, 576), iso=None, shutter=None, fnumber=None, light=(), record=(),
                 read_only=False, realtime=True, fps=24.0, log_dir=None, scene_offset=0.0, iso_while_recording=False,
                 allow_exposure=False, light_k=3200):
        self.props = copy.deepcopy(json.loads(SETTINGS_FILE.read_text())["properties"])
        for name, raw in (("IsoSensitivity", iso), ("FNumber", fnumber and int(round(fnumber * 100))),
                          ("ShutterSpeed", shutter and (1 << 16) | int(shutter))):
            if raw is not None:
                if raw not in self.props[name]["set_values"]:
                    raise ValueError("the FX2 doesn't offer %s %s" % (name, raw))
                self.props[name]["current"] = raw
        self.tm = ToneModel("slog3", load_calibration())
        if frame is not None:
            bgr = cv2.imread(str(frame))
            if bgr is None:
                raise ValueError("can't read %s" % frame)
            scene = self.tm.to_stops(bgr) + np.where(bgr >= self.tm.clip_level, CLIPPED_EXTRA_STOPS, 0.0)
        else:
            scene = made_up_scene(size[0], size[1], self.tm)
        self.scene = scene.astype(np.float32) + scene_offset
        self.light_k = light_k
        self.remembered_k = REMEMBERED_K
        self.start = {n: self.props[n]["current"] for n in EXPOSURE}   # the frame was recorded at these
        self.start.update(WhiteBalance=self.props["WhiteBalance"]["current"], Colortemp=self.props["Colortemp"]["current"])
        self.visible = dict(self.start)                                 # what the picture shows right now
        self.pending = []                                               # [(t_visible, name, raw)]
        self.light = sorted(light)
        self.record = list(record)
        self.recording = False                                          # tests can flip this directly
        self.read_only, self.realtime, self.fps = read_only, realtime, fps
        self.iso_while_recording = iso_while_recording and not read_only
        self.allow_exposure = allow_exposure and not read_only and not iso_while_recording
        self.locked = False
        self.sets = []                                                  # every set command received
        self.frame_no = 0
        self.t0 = time.monotonic()
        self.cache = {}
        self.mutex = threading.Lock()
        self.log_path = Path(log_dir) / "bridge_log.jsonl" if log_dir else None

    # ------------------------------------------------------------ the scene
    def clock(self):
        return time.monotonic() - self.t0 if self.realtime else self.frame_no / self.fps

    def light_stops(self, t):
        return ([s for at, s in self.light if at <= t] or [0.0])[-1]

    def is_recording(self, t):
        return self.recording or any(a <= t < b for a, b in self.record)

    def render(self, ev, wb_k=None):
        key = (round(ev, 3), wb_k)
        if key not in self.cache:
            levels = np.searchsorted(self.tm.stops_lut, self.scene + ev + cast_stops(self.light_k, wb_k))
            img = np.clip(levels, self.tm.floor_level, self.tm.clip_level).astype(np.uint8)
            self.cache[key] = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()
        return self.cache[key]

    def frame(self, after, timeout_ms):
        if self.realtime:
            deadline = time.monotonic() + timeout_ms / 1000
            while int(self.clock() * self.fps) <= after and time.monotonic() < deadline:
                time.sleep(0.005)
            n = int(self.clock() * self.fps)
            if n <= after:
                return {"ok": False, "error": "no new frame within timeout"}, None
            self.frame_no = n
        else:
            self.frame_no += 1
        t = self.clock()
        with self.mutex:
            for item in [p for p in self.pending if p[0] <= t]:
                self.visible[item[1]] = item[2]
                self.pending.remove(item)
            ev = exposure_ev(self.visible) - exposure_ev(self.start) + self.light_stops(t)
            wb_k = self.visible["Colortemp"] if self.visible["WhiteBalance"] == COLOR_TEMP else None
        jpeg = self.render(ev, wb_k)
        return {"ok": True, "frame_no": self.frame_no, "age_ms": 0.0, "bytes": len(jpeg)}, jpeg

    # -------------------------------------------------------------- settings
    def properties(self, names=None):
        self.props["RecordingState"]["current"] = RECORDING if self.is_recording(self.clock()) else 0
        return [p for n, p in self.props.items() if names is None or n in names]

    def _refusal(self, name, raw):
        if self.read_only:
            return "bridge was started read-only"
        if self.locked:
            return "kill switch is on (bridge locked)"
        if name not in ALLOW_LIST:
            return "not on the allow-list"
        if ALLOW_LIST[name][2] and not self.allow_exposure:
            return "only ISO may change (bridge started without --allow-exposure)"
        if not rule_allows(name, raw):
            return "outside the approved range"
        if self.is_recording(self.clock()) and not (self.iso_while_recording and name == "IsoSensitivity"):
            return "camera is recording"
        if not self.props[name]["can_set_now"]:
            return "camera says this setting can't be changed right now"
        if not camera_offers(self.props[name], raw):
            return "camera doesn't offer this value right now"
        return None

    def set(self, name, raw):
        with self.mutex:
            t_call = self.clock()
            self.sets.append((t_call, name, raw))
            why = self._refusal(name, raw)
            if why:
                self._log({"event": "set_refused", "name": name, "value": raw, "reason": why})
                return {"ok": False, "refused": True, "error": why}
            old = self.props[name]["current"]
            if old == raw:
                return {"ok": True, "changed": False, "old": old, "new": raw}
        if self.realtime:
            time.sleep(CONFIRM_S)
        with self.mutex:
            self.props[name]["current"] = raw
            self.pending.append((t_call + SHOW_S, name, raw))
            if name == "Colortemp":
                self.remembered_k = raw
            if name == "WhiteBalance":                    # like the FX2: Kelvin only exists in Color Temp mode
                kt = self.props["Colortemp"]
                kt["current"] = self.remembered_k if raw == COLOR_TEMP else 0
                kt["can_set_now"] = raw == COLOR_TEMP
                kt["enable"] = "True" if raw == COLOR_TEMP else "False"
                self.pending.append((t_call + SHOW_S, "Colortemp", kt["current"]))
        fields = {"name": name, "old": old, "new": raw, "confirmed": True, "camera_reports": raw,
                  "ms_sdk_return": 2.0, "ms_first_callback": CONFIRM_S * 1000 - 20, "ms_confirmed": CONFIRM_S * 1000,
                  "while_recording": self.is_recording(t_call)}
        self._log({"event": "set", **fields})
        return {"ok": True, "changed": True, **fields}

    def _log(self, entry):
        if self.log_path:
            with self.log_path.open("a") as f:
                f.write(json.dumps({"time": datetime.now().isoformat(timespec="milliseconds"), **entry}) + "\n")

    # -------------------------------------------------------------- protocol
    def command(self, args):
        """One command line (split) -> (JSON reply, raw bytes to send after it or None)."""
        cmd = args[0]
        if cmd == "ping":
            return {"ok": True, "pong": True}, None
        if cmd == "status":
            return {"ok": True, "model": "FAKE camera (no real camera)", "fake": True, "connected": True,
                    "locked": self.locked, "read_only": self.read_only, "iso_while_recording": self.iso_while_recording,
                    "allow_exposure": self.allow_exposure,
                    "allow_list": [{"name": n, "min": lo, "max": hi} for n, (lo, hi, sw) in ALLOW_LIST.items()
                                   if self.allow_exposure or not sw]}, None
        if cmd == "settings":
            return {"ok": True, "time": datetime.now().isoformat(), "properties": self.properties()}, None
        if cmd == "get" and len(args) > 1:
            return {"ok": True, "time": datetime.now().isoformat(), "properties": self.properties(args[1:])}, None
        if cmd == "frame" and len(args) == 3:
            return self.frame(int(args[1]), int(args[2]))
        if cmd == "lvstats":
            return {"ok": True, "fps": self.fps, "last_frame_no": self.frame_no}, None
        if cmd == "display_strings":
            return {"ok": False, "error": "the fake camera has no display strings"}, None
        if cmd == "set" and len(args) == 3:
            return self.set(args[1], int(args[2], 0)), None
        if cmd == "lock":
            self.locked = True
            self._log({"event": "locked"})
            return {"ok": True, "locked": True}, None
        if cmd == "quit":
            return {"ok": True, "quitting": True}, None
        return {"ok": False, "error": "unknown or malformed command"}, None


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        for line in self.rfile:
            args = line.decode().split()
            if not args:
                continue
            reply, payload = self.server.camera.command(args)
            self.wfile.write((json.dumps(reply) + "\n").encode())
            if payload:
                self.wfile.write(payload)
            self.wfile.flush()
            if args[0] == "quit":
                self.server.quitting.set()
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return


def serve(camera, socket_path=DEFAULT_SOCKET):
    """Start the fake bridge in a background thread. Returns the server (call .shutdown() to stop)."""
    socket_path = Path(socket_path)
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    socket_path.unlink(missing_ok=True)
    server = socketserver.ThreadingUnixStreamServer(str(socket_path), _Handler)
    server.daemon_threads = True
    server.camera = camera
    server.quitting = threading.Event()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def parse_pairs(items):
    return [tuple(float(x) for x in item.split(":")) for item in items or []]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--socket", default=str(DEFAULT_SOCKET))
    ap.add_argument("--frame", help="a recorded live-view JPEG (S-Log3); default: a made-up test scene")
    ap.add_argument("--iso", type=int, help="the ISO the frame was recorded at")
    ap.add_argument("--shutter", type=int, help="shutter denominator the frame was recorded at (50 = 1/50)")
    ap.add_argument("--fnumber", type=float, help="aperture the frame was recorded at")
    ap.add_argument("--light", nargs="*", metavar="T:STOPS", help="from T seconds on, the light is STOPS brighter")
    ap.add_argument("--record", nargs="*", metavar="T0:T1", help="the camera records from T0 to T1 seconds")
    ap.add_argument("--read-only", action="store_true")
    ap.add_argument("--allow-iso-while-recording", action="store_true", help="Step 7 agent takes only")
    ap.add_argument("--allow-exposure", action="store_true", help="aperture, shutter and WB may change too")
    ap.add_argument("--light-k", type=int, default=3200, help="the light's color temperature")
    ap.add_argument("--log-dir")
    args = ap.parse_args()
    if sum((args.read_only, args.allow_iso_while_recording, args.allow_exposure)) > 1:
        sys.exit("--read-only, --allow-iso-while-recording and --allow-exposure can't be combined (same as the real bridge)")

    camera = FakeCamera(frame=args.frame, iso=args.iso, shutter=args.shutter, fnumber=args.fnumber,
                        light=parse_pairs(args.light), record=parse_pairs(args.record),
                        read_only=args.read_only, log_dir=args.log_dir,
                        iso_while_recording=args.allow_iso_while_recording, allow_exposure=args.allow_exposure,
                        light_k=args.light_k)
    server = serve(camera, args.socket)
    print("Fake camera ready on %s (no real camera). Ctrl-C or 'quit' stops it." % args.socket, flush=True)
    try:
        while not server.quitting.wait(0.5):
            pass
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        Path(args.socket).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
