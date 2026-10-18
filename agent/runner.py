"""The agent loop: eyes → brain → safety gate → bridge, one live-view frame at a time.

Dry run (the default) never sends a change: proposals are shown and logged as "would
change". Live mode hands each proposal to SafetyGate.change_setting(), the only way the
agent changes the camera, and only for settings the director approved
(config/safe_ranges.json "change_allowed": today ISO only). The brain still plans the
other levers and shows them as advice ("Would change, not approved yet: ...").

Kill switch: kill() locks the bridge over its own connection, so it gets through even
while a change is in flight, and stops the loop. A change already sent finishes
(~0.15 s); nothing after it is sent, and the bridge refuses every change until it's
restarted. A lock from another terminal (tools/kill_switch.py) stops the runner too.
Runaway guard: more than MAX_CHANGES_PER_MIN changes in a minute trips the kill switch.
Any other refused or unconfirmed change pauses the agent until the operator resumes.
"""
import json
import re
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from agent.brain import Brain, cam_state_from_settings, observation_from_report
from agent.bridge_client import BridgeClient
from agent.eyes import Eyes, context_from_settings
from agent.looks import LOOKS
from agent.safety import SafetyGate, load_ranges
from agent.sony_values import describe_value, load_enums

WATCHED = ("IsoSensitivity", "FNumber", "ShutterSpeed", "WhiteBalance", "Colortemp", "RecordingState",
           "MovieShootingMode", "Movie_Recording_FrameRateSetting", "PictureProfile", "PictureProfile_Gamma")
SUMMARY = ("IsoSensitivity", "ShutterSpeed", "FNumber", "WhiteBalance", "Colortemp")
SETTINGS_EVERY_S = 0.25      # re-read the camera's settings (catches recording and hand changes)
STATUS_EVERY_S = 1.0         # re-read the bridge status (catches a lock from another terminal)
MAX_CHANGES_PER_MIN = 20     # runaway guard: a smooth agent needs far fewer
ADVICE_REPEAT_S = 10.0       # show the same advice again only after this long
WOULD_REPEAT_S = 10.0


class RunnerError(Exception):
    pass


def approved_settings(ranges):
    """Settings the director approved for live changes."""
    return {name for name, rule in ranges.items() if rule.get("change_allowed")}


class AgentRunner:
    def __init__(self, socket_path, session_dir, look="cinematic", live=False, eyes=None, ranges=None,
                 clock=time.monotonic, on_event=None):
        self.socket_path = socket_path
        self.client = BridgeClient(socket_path)
        self.kill_client = BridgeClient(socket_path)          # its own connection, for the kill switch
        self.session = Path(session_dir)
        self.session.mkdir(parents=True, exist_ok=True)
        self.look = look
        self.live = live
        self.eyes = eyes or Eyes()
        self.ranges = ranges if ranges is not None else load_ranges()
        self.allowed = approved_settings(self.ranges)
        self.gate = SafetyGate(self.client, self.session / "changes.jsonl", self.ranges)
        self.enums = load_enums()
        self.clock = clock
        self.on_event = on_event or (lambda kind, text: None)
        self.killed = False
        self.kill_reason = None
        self.paused = False
        self.stop_requested = False
        self.changes = []                       # changes the agent made (and the camera confirmed)
        self.change_times = deque()
        self.shown_advice = {}
        self.last_would = (None, -1e9)
        self.last_status = None
        self.frame_no = -1
        self.frames = 0
        self.eyes_ms = deque(maxlen=48)
        self.report = self.output = self.jpeg = None
        self.restorable = []
        self.fps = None

    # ------------------------------------------------------------ logging
    def _log(self, event, **fields):
        entry = {"time": datetime.now().isoformat(timespec="milliseconds"),
                 "t": round(self.clock() - self.t0, 3) if hasattr(self, "t0") else 0.0, "event": event, **fields}
        with (self.session / "runner_log.jsonl").open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def _event(self, kind, text, **fields):
        self._log(kind, text=text, **fields)
        self.on_event(kind, text)

    def _text(self, name, props=None):
        props = props if props is not None else self.props
        return describe_value(name, props[name]["current"], self.enums) if name in props else "?"

    # -------------------------------------------------------------- start
    def start(self):
        status = self.client.status()
        self.bridge = status
        if not status.get("connected"):
            raise RunnerError("the bridge has no camera connected")
        if status.get("locked"):
            raise RunnerError("the bridge is locked (kill switch was used): restart the bridge first")
        if self.live and status.get("read_only"):
            raise RunnerError("live mode needs a bridge started WITHOUT --read-only")
        self.t0 = self.clock()
        self.start_props = self.client.settings()
        (self.session / "settings_start.json").write_text(json.dumps(self.start_props, indent=1))
        self.props = {n: self.start_props[n] for n in WATCHED if n in self.start_props}
        self._rebuild()
        self.brain = self._new_brain(self.look)
        self.t_settings = self.t_status = self.t_tick = self.clock()
        mode = "LIVE" if self.live else "DRY RUN"
        self._event("start", "%s on %s · look: %s · may change: %s · camera: %s" % (
            mode, status.get("model", "?"), self.brain.look.name, ", ".join(sorted(self.allowed)) or "nothing",
            self.summary()), mode=mode, allowed=sorted(self.allowed), bridge=status,
            settings={n: self._text(n) for n in SUMMARY})

    def _new_brain(self, look):
        return Brain(look, allowed=self.allowed)

    def _rebuild(self):
        self.ctx = context_from_settings(self.props, self.enums)
        self.cam = cam_state_from_settings(self.props, self.enums)

    def summary(self):
        wb = self._text("WhiteBalance")
        if wb == "ColorTemp":
            wb = "%dK" % self.props["Colortemp"]["current"]
        return "ISO %d · %s · f/%g · WB %s%s" % (self.cam.iso, self._text("ShutterSpeed"), self.cam.fnumber, wb,
                                                 " · RECORDING" if self.cam.recording else "")

    # ---------------------------------------------------------------- loop
    def run(self, seconds=None):
        t_end = None if seconds is None else self.clock() + seconds
        while self.step():
            if t_end is not None and self.clock() >= t_end:
                break

    def step(self):
        """One live-view frame through eyes → brain → (safety gate → bridge). False = stop."""
        if self.killed or self.stop_requested:
            return False
        try:
            now = self.clock()
            if now - self.t_status >= STATUS_EVERY_S:
                self.t_status = now
                if self.client.status().get("locked") and not self.killed:
                    self._killed_from_outside()
                    return False
            if now - self.t_settings >= SETTINGS_EVERY_S:
                self.t_settings = now
                self.props.update(self.client.get(*WATCHED))
                self._rebuild()
            header, jpeg = self.client.frame(after=self.frame_no, timeout_ms=1000)
        except Exception as e:                       # bridge gone or camera unplugged
            self._event("error", "Lost the bridge or camera (%s): stopped. Nothing more will be sent." % e)
            return False
        if jpeg is None:
            self._status("No live view: %s" % header.get("error", "?"))
            return True
        self.frame_no = header["frame_no"]
        bgr = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
        if bgr is None:
            return True
        self.jpeg = jpeg
        t = self.clock()
        self.report = self.eyes.analyze(bgr, self.ctx)
        self.frames += 1
        self.eyes_ms.append(self.report.ms)
        out = self.output = self.brain.update(observation_from_report(self.report, t), self.cam)
        self._advice(out.advice, t)
        if out.proposal is not None:
            self._act(out.proposal, t)
        self._status(out.status)
        if t - self.t_tick >= 1.0:
            self._tick(t)
        return not (self.killed or self.stop_requested)

    def _act(self, p, t):
        if self.killed:
            return
        if not self.live or self.paused or p.setting not in self.allowed:
            why = "dry run" if not self.live else "paused" if self.paused else "not approved"
            if (p.setting, p.raw) != self.last_would[0] or t - self.last_would[1] >= WOULD_REPEAT_S:
                self.last_would = ((p.setting, p.raw), t)
                self._event("would_change", "Would change (%s): %s" % (why, p.reason), setting=p.setting,
                            raw=p.raw, reason=p.reason)
            return
        recent = [x for x in self.change_times if t - x < 60]
        if len(recent) >= MAX_CHANGES_PER_MIN:
            self.kill("Runaway guard: %d changes in under a minute" % len(recent))
            return
        reply = self.gate.change_setting(p.setting, p.raw, p.reason)
        if self.killed:
            return
        if reply.get("ok"):
            self.props[p.setting] = dict(self.props[p.setting], current=reply.get("camera_reports", p.raw))
            self._rebuild()
            if reply.get("changed") is False:          # the camera already had it (changed by hand just now)
                self._log("already_set", setting=p.setting, raw=p.raw)
                return
            self.change_times.append(t)
            n = len(self.changes) + 1
            (self.session / "frames").mkdir(exist_ok=True)
            (self.session / "frames" / ("change_%03d.jpg" % n)).write_bytes(self.jpeg)
            self.changes.append({"t": t, "setting": p.setting, "from": p.from_text, "to": p.to_text,
                                 "reason": p.reason, "ms_confirmed": reply.get("ms_confirmed")})
            self._event("change", "%s  (confirmed in %s ms)" % (p.reason, _ms(reply.get("ms_confirmed"))),
                        setting=p.setting, old=p.from_text, new=p.to_text, reason=p.reason)
            return
        error = reply.get("error", "camera didn't confirm the change")
        if "kill switch" in error:
            self._killed_from_outside()
        elif "recording" in error:
            self._event("refused", "Not changed (camera started recording): %s" % p.reason)
        else:
            self.paused = True
            self._event("pause", "PAUSED: %s was refused (%s). Check the camera, then resume." % (p.to_text, error))

    def _advice(self, advice, t):
        for a in advice:
            same = re.sub(r"[-+]?[0-9][0-9.,]*|[⅓⅔]", "#", a)     # "face -0.9" and "face -0.8" are the same advice
            if t - self.shown_advice.get(same, -1e9) >= ADVICE_REPEAT_S:
                self._event("advice", a)
            self.shown_advice[same] = t

    def _status(self, text):
        quiet = re.sub(r"waiting [0-9.]+ s", "waiting", text)
        if quiet != self.last_status:
            self.last_status = quiet
            self._log("status", text=quiet)
        self.on_event("status_line", text)

    def _tick(self, t):
        self.fps = round(self.frames / max(1e-6, t - self.t_tick), 1)
        r = self.report
        self._log("tick", fps=self.fps, eyes_ms=round(float(np.median(self.eyes_ms)), 1), key=r.key_stops,
                  face=r.faces[0]["stops"] if r.faces else None, headroom=r.headroom_stops,
                  clipped_important=r.clipped_important_pct, camera=self.summary(), paused=self.paused)
        self.frames, self.t_tick = 0, t

    # ------------------------------------------------------------ controls
    def kill(self, why="Kill switch"):
        """Stop now: lock the bridge (no more changes until it's restarted) and end the loop."""
        if self.killed:
            return
        self.killed, self.kill_reason = True, why
        reply = self.gate.kill(self.kill_client, why)
        self._event("kill", "%s: stopped, bridge %s. The camera is yours." % (
            why, "locked" if reply.get("locked") else "NOT confirmed locked (%s)" % reply.get("error")))

    def _killed_from_outside(self):
        self.killed, self.kill_reason = True, "bridge locked from outside"
        self.gate.killed = True
        self._event("kill", "The bridge was locked (kill switch from another terminal): stopped. The camera is yours.")

    def toggle_pause(self):
        self.paused = not self.paused
        self._event("pause", "PAUSED: watching only, no changes" if self.paused else "Resumed")

    def set_look(self, key):
        if key in LOOKS and key != self.brain.look.key:
            self.brain = self._new_brain(key)
            self._event("look", "Look: %s" % self.brain.look.name, look=key)

    def stop(self):
        self.stop_requested = True

    # ---------------------------------------------------------------- end
    def finish(self):
        """Session end: snapshot the settings again and list what changed. Returns the differences."""
        try:
            # A fresh connection: if the loop was interrupted mid-answer (Ctrl-C), the old one is out of step.
            self.client.close()
            self.client = self.gate.client = BridgeClient(self.socket_path)
            end = self.client.settings()
        except Exception as e:
            self._event("end", "Couldn't read the camera at the end (%s)" % e)
            return []
        (self.session / "settings_end.json").write_text(json.dumps(end, indent=1))
        by_agent = {c["setting"] for c in self.changes}
        diffs = []
        for name in SUMMARY:
            if name in self.start_props and name in end and self.start_props[name]["current"] != end[name]["current"]:
                diffs.append({"setting": name, "start": self._text(name, self.start_props), "now": self._text(name, end),
                              "start_raw": self.start_props[name]["current"],
                              "by": "agent" if name in by_agent else "by hand"})
        self.restorable = [d for d in diffs if d["setting"] in self.allowed] if not self.killed else []
        self._event("end", "Session end: %d change(s) by the agent; settings different from the start: %s" % (
            len(self.changes), ", ".join("%s %s → %s (%s)" % (d["setting"], d["start"], d["now"], d["by"])
                                         for d in diffs) or "none"), diffs=diffs)
        return diffs

    def restore(self):
        """Put approved settings back to where the session started (through the safety gate)."""
        results = []
        for d in self.restorable:
            reply = self.gate.change_setting(d["setting"], d["start_raw"],
                                             "Session end: restoring your starting %s" % d["start"])
            results.append((d, reply))
            self._event("restore", "%s back to %s: %s" % (d["setting"], d["start"],
                                                          "done" if reply.get("ok") else reply.get("error")))
        return results

    def close(self):
        for c in (self.client, self.kill_client):
            try:
                c.close()
            except Exception:
                pass


def _ms(v):
    return "?" if v is None else "%d" % round(v)
