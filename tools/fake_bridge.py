"""A fake FX2 that speaks the bridge's language, so the runner can be tried with no camera.

Same socket protocol as bridge/src/camera_bridge.cpp (ping, status, settings, get, frame,
lvstats, set, lock, quit) and the same checks before a change: read-only, kill switch,
allow-list (ISO 800-12800 only, like the real bridge), recording, value offered.
The picture is a recorded frame (or a made-up test scene) made brighter or darker by
the exposure change, using the measured S-Log3 calibration (20.63 levels/stop, clip 221).
Like the real FX2 (Step 3), a change is confirmed after ~0.15 s and shows in the picture
~0.3 s after it's sent. Nothing here talks to a real camera.

Usage:
  python tools/fake_bridge.py                         # made-up scene at ISO 800, 1/160, f/2.8
  python tools/fake_bridge.py --frame clean.jpg --iso 1600 --shutter 50 --fnumber 5.6
         [--light 20:-1 40:0.7]   from 20 s the room is 1 stop darker, from 40 s 0.7 stop brighter
         [--record 30:40]         the camera records from 30 s to 40 s
         [--read-only | --allow-iso-while-recording] [--socket run/fake_bridge.sock] [--log-dir DIR]
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
ALLOW_LIST = {"IsoSensitivity": (800, 12800)}   # same as the real bridge's compiled-in list
EXPOSURE = ("IsoSensitivity", "FNumber", "ShutterSpeed")
RECORDING = 1                                    # CrMovie_Recording_State_Recording
CONFIRM_S, SHOW_S = 0.15, 0.3                    # measured on the FX2: 119-172 ms / 272-325 ms
CLIPPED_EXTRA_STOPS = 1.0                        # clipped areas of a recorded frame: assumed 1 stop over clip


def exposure_ev(values):
    """Exposure in stops (bigger = brighter picture) from raw ISO / FNumber / ShutterSpeed."""
    shutter = values["ShutterSpeed"]
    return (math.log2(values["IsoSensitivity"] & 0xFFFFFF) - 2 * math.log2(values["FNumber"] / 100)
            + math.log2((shutter >> 16) / (shutter & 0xFFFF)))


def made_up_scene(w, h, tm):
    """A neutral test scene in stops vs grey: a gradient from -1.5 to +0.5 st and one small clipped lamp."""
    stops = np.linspace(-1.5, 0.5, w, dtype=np.float32)[None, :] + np.linspace(-0.3, 0.3, h, dtype=np.float32)[:, None]
    stops[h // 24: h // 8, int(w * 0.77): int(w * 0.85)] = tm.clip_stops + 3     # inside one grid region
    return np.repeat(stops[..., None], 3, axis=2)


class FakeCamera:
    def __init__(self, frame=None, size=(1024, 576), iso=None, shutter=None, fnumber=None, light=(), record=(),
                 read_only=False, realtime=True, fps=24.0, log_dir=None, scene_offset=0.0, iso_while_recording=False):
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
        self.start = {n: self.props[n]["current"] for n in EXPOSURE}   # the frame was recorded at these
        self.visible = dict(self.start)                                 # what the picture shows right now
        self.pending = []                                               # [(t_visible, name, raw)]
        self.light = sorted(light)
        self.record = list(record)
        self.recording = False                                          # tests can flip this directly
        self.read_only, self.realtime, self.fps = read_only, realtime, fps
        self.iso_while_recording = iso_while_recording and not read_only
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

    def render(self, ev):
        key = round(ev, 3)
        if key not in self.cache:
            levels = np.searchsorted(self.tm.stops_lut, self.scene + ev)
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
        jpeg = self.render(ev)
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
        lo, hi = ALLOW_LIST[name]
        if raw >> 24 or not lo <= (raw & 0xFFFFFF) <= hi:
            return "outside the approved range"
        if self.is_recording(self.clock()) and not (self.iso_while_recording and name == "IsoSensitivity"):
            return "camera is recording"
        if not self.props[name]["can_set_now"]:
            return "camera says this setting can't be changed right now"
        if raw not in self.props[name]["set_values"]:
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
                    "allow_list": [{"name": n, "min": lo, "max": hi} for n, (lo, hi) in ALLOW_LIST.items()]}, None
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
    ap.add_argument("--log-dir")
    args = ap.parse_args()
    if args.read_only and args.allow_iso_while_recording:
        sys.exit("--read-only and --allow-iso-while-recording can't be combined (same as the real bridge)")

    camera = FakeCamera(frame=args.frame, iso=args.iso, shutter=args.shutter, fnumber=args.fnumber,
                        light=parse_pairs(args.light), record=parse_pairs(args.record),
                        read_only=args.read_only, log_dir=args.log_dir,
                        iso_while_recording=args.allow_iso_while_recording)
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
