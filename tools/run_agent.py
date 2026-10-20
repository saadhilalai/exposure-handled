"""Run the camera agent: eyes → brain → safety gate → bridge, with a keyboard kill switch.

Dry run is the default: the agent watches and says what it WOULD change; nothing is sent.
--live sends approved changes (ISO only, 800-12800) through the safety gate; with --allow-exposure
also aperture f/2.8-f/11, shutter 1/48-1/100 and WB 2800-7500K (bridge started with the same flag).

Keys:  SPACE   kill switch: stop now, lock the bridge, the camera is yours
       p       Auto on / off (off = the agent only suggests)
       l       Lock: hold every setting now / unlock
       m       mark a scene event (e.g. the moment a light changes; used by the Step 7 test)
       x       log a problem right now (flicker, slow, wrong call, confusing screen): saved to problems.jsonl
       1-5     look: 1 Cinematic, 2 Run and gun, 3 Interview, 4 Low light, 5 Photo portrait
       q       quit (offers to put your starting ISO back)
       Ctrl-C  kill switch + quit
From any other terminal:  python tools/kill_switch.py
--dashboard also serves the dashboard at http://127.0.0.1:8765/ (same controls, plus the
"this face looks right" button). A live session with the dashboard starts with Auto OFF.
--take S1_R3_A_agent names the Step 7 take (session folder + logs). --allow-iso-while-recording
is the Step 7 recording switch: agent takes only, needs --live, a take name ending in _agent,
and a bridge started with the same flag. Off unless given.

Usage:
  python tools/run_agent.py --fake                     # fake camera, made-up scene: no camera at all
  python tools/run_agent.py --fake --live --frame F.jpg --iso 1600 --shutter 50 --fnumber 5.6 --light 20:-1
  python tools/run_agent.py                            # dry run on the real bridge (run/bridge.sock)
  python tools/run_agent.py --live                     # live on the real camera: you type LIVE first
  python tools/run_agent.py --fake --dashboard          # the dashboard on the fake camera
"""
import argparse
import os
import re
import select
import shutil
import signal
import subprocess
import sys
import termios
import threading
import time
import tty
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent.bridge_client import DEFAULT_SOCKET, BridgeClient, BridgeError  # noqa: E402
from agent.looks import LOOKS  # noqa: E402
from agent.runner import AgentRunner, RunnerError  # noqa: E402

FAKE_SOCKET = ROOT / "run" / "fake_bridge.sock"
LOOK_KEYS = dict(zip("12345", LOOKS))
KEYS_HELP = "SPACE kill switch · p Auto on/off · l Lock · m mark · x problem · 1-5 look · q quit · h help"
LABELS = {"start": ("START", "1"), "change": ("CHANGE", "32"), "would_change": ("WOULD", "36"),
          "advice": ("ADVICE", "33"), "kill": ("KILL", "1;31"), "error": ("ERROR", "1;31"),
          "pause": ("PAUSE", "35"), "refused": ("REFUSED", "35"), "look": ("LOOK", "1"),
          "end": ("END", "1"), "restore": ("RESTORE", "32"), "help": ("KEYS", "2"), "status": ("status", "2"),
          "face": ("FACE", "1"), "dashboard": ("WEB", "1"), "mark": ("MARK", "1;36"), "problem": ("PROBLEM", "1;33")}


class Console:
    """Event lines scroll. On a terminal the status line redraws in place; otherwise status changes print."""

    def __init__(self):
        self.tty = sys.stdout.isatty()
        self.t0 = time.monotonic()
        self.runner = None
        self.lock = threading.Lock()
        self.last_quiet = None
        self.last_draw = 0.0

    def event(self, kind, text):
        with self.lock:
            if kind == "status_line":
                return self._status(text)
            label, color = LABELS.get(kind, (kind.upper(), "0"))
            line = "%6.1fs  %-7s %s" % (time.monotonic() - self.t0, label, text)
            if self.tty:
                sys.stdout.write("\r\033[K\033[%sm%s\033[0m\n" % (color, line))
                self.last_draw = 0.0
            else:
                sys.stdout.write(line + "\n")
            sys.stdout.flush()

    def _status(self, text):
        r = self.runner
        if not self.tty:
            quiet = re.sub(r"waiting [0-9.]+ s", "waiting", text)
            if quiet != self.last_quiet:
                self.last_quiet = quiet
                sys.stdout.write("%6.1fs  status  %s\n" % (time.monotonic() - self.t0, quiet))
                sys.stdout.flush()
            return
        now = time.monotonic()
        if r is None or r.report is None or now - self.last_draw < 0.1:     # redraw at most 10x a second
            return
        self.last_draw = now
        mode = "KILLED" if r.killed else "LOCKED" if r.held else "AUTO OFF" if r.live and r.paused else \
            "LIVE" if r.live else "DRY RUN"
        rep = r.report
        face = " · face %+.1f" % rep.faces[0]["stops"] if rep.faces else ""
        line = "[%s · %s] %s │ key %+.1f%s · headroom %.1f │ %s fps │ %s" % (
            mode, r.brain.look.name.split(" (")[0], r.summary(), rep.key_stops, face, rep.headroom_stops,
            r.fps if r.fps is not None else "…", text)
        sys.stdout.write("\r\033[K" + line[:shutil.get_terminal_size().columns - 1])
        sys.stdout.flush()


class Keyboard:
    """Single key presses, read on a background thread (the terminal goes back to normal on close)."""

    def __init__(self, on_key):
        self.fd = sys.stdin.fileno()
        self.saved = termios.tcgetattr(self.fd)
        tty.setcbreak(self.fd)                    # keys arrive one at a time; Ctrl-C still works
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._loop, args=(on_key,), daemon=True)
        self.thread.start()

    def _loop(self, on_key):
        while not self.done.is_set():
            if select.select([self.fd], [], [], 0.1)[0]:
                on_key(os.read(self.fd, 1).decode(errors="ignore"))

    def close(self):
        self.done.set()
        self.thread.join(timeout=1)
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.saved)


def start_fake(args, socket_path, session):
    """Start tools/fake_bridge.py in its own process and wait until it answers."""
    cmd = [sys.executable, str(ROOT / "tools" / "fake_bridge.py"), "--socket", str(socket_path), "--log-dir", str(session)]
    for flag in ("frame", "iso", "shutter", "fnumber"):
        if getattr(args, flag) is not None:
            cmd += ["--" + flag, str(getattr(args, flag))]
    for flag in ("light", "record"):
        if getattr(args, flag):
            cmd += ["--" + flag] + getattr(args, flag)
    if args.fake_read_only:
        cmd.append("--read-only")
    if args.allow_iso_while_recording:
        cmd.append("--allow-iso-while-recording")
    if args.allow_exposure_while_recording:
        cmd.append("--allow-exposure-while-recording")
    elif args.allow_exposure:
        cmd.append("--allow-exposure")
    # Own process group, so Ctrl-C reaches only the runner (which then stops the fake itself).
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=(session / "fake_bridge_errors.log").open("w"),
                            start_new_session=True)
    for _ in range(100):
        try:
            BridgeClient(socket_path, timeout=2).command("ping")
            return proc
        except OSError:
            if proc.poll() is not None:
                sys.exit("The fake camera didn't start: see %s" % (session / "fake_bridge_errors.log"))
            time.sleep(0.1)
    proc.terminate()
    sys.exit("The fake camera didn't answer within 10 s")


def confirm_live(args, status):
    if status.get("fake"):
        return
    print("\nLIVE on the real camera (%s)." % status.get("model"))
    if args.rehearsal:
        print("  REHEARSAL: everything from this session is labeled rehearsal and kept apart from Step 7.")
    if args.allow_exposure:
        print("  The agent may change: ISO 800-12800, f/2.8-f/11, shutter 1/48-1/100, WB Auto/2800-7500K.")
    if args.allow_exposure_while_recording:
        print("  REHEARSAL RECORDING SWITCH ON: those may change while the camera records, too.")
    else:
        print("  The agent may change: ISO, 800-12800 only. Shutter, aperture and WB are advice only.")
    print("  Kill switch: SPACE (or Ctrl-C, or tools/kill_switch.py from another terminal, or unplug USB).")
    if not sys.stdin.isatty():
        if not args.yes:
            sys.exit("Not a terminal, so there's no keyboard kill switch. Add --yes to run live anyway.")
        print("  --yes given: no keyboard here. Stop it with: python tools/kill_switch.py")
        return
    if input("Type LIVE to start: ").strip() != "LIVE":
        sys.exit("Not started.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="actually change approved settings (default: dry run)")
    ap.add_argument("--look", default="cinematic", choices=list(LOOKS))
    ap.add_argument("--seconds", type=float, help="stop by itself after this long")
    ap.add_argument("--socket", help="bridge socket (default run/bridge.sock, or the fake's)")
    ap.add_argument("--restore", action="store_true", help="at the end, put the starting ISO back without asking")
    ap.add_argument("--yes", action="store_true", help="allow --live without a keyboard (no SPACE kill switch)")
    fake = ap.add_argument_group("fake camera (no real camera)")
    fake.add_argument("--fake", action="store_true", help="start the fake camera and run against it")
    fake.add_argument("--frame", help="recorded live-view JPEG for the fake (default: a made-up scene)")
    fake.add_argument("--iso", type=int)
    fake.add_argument("--shutter", type=int, help="denominator: 50 = 1/50")
    fake.add_argument("--fnumber", type=float)
    fake.add_argument("--light", nargs="*", metavar="T:STOPS", help="from T s on, the light is STOPS brighter")
    fake.add_argument("--record", nargs="*", metavar="T0:T1", help="the fake records from T0 to T1 s")
    fake.add_argument("--fake-read-only", action="store_true")
    web = ap.add_argument_group("dashboard")
    web.add_argument("--dashboard", action="store_true", help="serve the dashboard (http://127.0.0.1:8765/)")
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--host", default="127.0.0.1", help="0.0.0.0 opens it to your network (Pi + phone): no password yet")
    web.add_argument("--face-refs", help="where 'this face looks right' is stored (default config/face_refs.json)")
    step7 = ap.add_argument_group("Step 7")
    step7.add_argument("--take", help="run-sheet name of this take, e.g. S1_R3_A_agent")
    step7.add_argument("--allow-iso-while-recording", action="store_true",
                       help="Step 7 agent takes only: the agent may change ISO while the camera records")
    reh = ap.add_argument_group("rehearsal (never mixed with Step 7)")
    reh.add_argument("--rehearsal", action="store_true",
                     help="label everything 'rehearsal': sessions go to sessions/REHEARSAL/, takes are named REH_...")
    reh.add_argument("--allow-exposure-while-recording", action="store_true",
                     help="rehearsal agent takes only: ISO, aperture, shutter and WB may change while recording "
                          "(turns on --allow-exposure; bridge needs the same flag)")
    ap.add_argument("--allow-exposure", action="store_true",
                    help="aperture, shutter and WB may change too (bridge must be started with --allow-exposure)")
    args = ap.parse_args()
    if args.allow_exposure_while_recording:
        if not args.rehearsal:
            sys.exit("--allow-exposure-while-recording is for rehearsals only: add --rehearsal")
        args.allow_exposure = True
    if args.rehearsal and not args.face_refs:
        args.face_refs = str(ROOT / "sessions" / "REHEARSAL" / "face_refs.json")   # tonight's faces stay with tonight

    socket_path = Path(args.socket) if args.socket else FAKE_SOCKET if args.fake else DEFAULT_SOCKET
    session = ROOT / "sessions" / ("REHEARSAL" if args.rehearsal else "") / ("%s_%s%s" % (datetime.now().strftime("%Y-%m-%d_%H%M%S"),
                                               args.take or "runner-" + ("live" if args.live else "dry"),
                                               "-fake" if args.fake else ""))
    session.mkdir(parents=True)
    if args.rehearsal:
        (session / "LABEL").write_text("rehearsal: not part of the Step 7 test\n")
    fake_proc = start_fake(args, socket_path, session) if args.fake else None
    if not fake_proc and not socket_path.exists():
        sys.exit("No bridge at %s. Start the bridge first (PROGRESS.md, 'How to start things again')." % socket_path)

    console = Console()
    from agent.faces import FaceBook
    runner = AgentRunner(socket_path, session, look=args.look, live=args.live, on_event=console.event,
                         auto=not args.dashboard, faces=FaceBook(args.face_refs) if args.face_refs else None,
                         iso_while_recording=args.allow_iso_while_recording, take=args.take,
                         exposure=args.allow_exposure, exposure_while_recording=args.allow_exposure_while_recording,
                         label="rehearsal" if args.rehearsal else None)
    console.runner = runner
    keyboard = dashboard = None
    try:
        if args.live:
            confirm_live(args, runner.client.status())
        runner.start()
        console.event("help", KEYS_HELP if sys.stdin.isatty() else "no keyboard: stop with tools/kill_switch.py")
        if args.allow_iso_while_recording:
            console.event("pause", "STEP 7 RECORDING SWITCH ON for take %s: the agent may change ISO (only) while "
                                   "the camera records. Kill switch: SPACE." % args.take)
        if args.allow_exposure_while_recording:
            console.event("pause", "REHEARSAL RECORDING SWITCH ON for take %s: ISO, aperture, shutter and WB may change "
                                   "while the camera records. Kill switch: SPACE." % args.take)
        if args.dashboard:
            from agent.dashboard import Dashboard
            dashboard = Dashboard(runner, args.host, args.port).start()
            console.event("dashboard", "Dashboard: %s%s" % (dashboard.url, "  (Auto is OFF: press Auto to let it change ISO)"
                                                              if args.live else ""))

        def on_key(ch):
            if ch == " ":
                runner.kill("Kill switch (SPACE)")
            elif ch in "pP":
                runner.toggle_pause()
            elif ch in "lL":
                runner.hold(not runner.held)
            elif ch in "mM":
                runner.mark()
            elif ch in "xX":
                runner.problem()
            elif ch in LOOK_KEYS:
                runner.set_look(LOOK_KEYS[ch])
            elif ch in "qQ":
                runner.stop()
            elif ch in "hH?":
                console.event("help", KEYS_HELP)

        if sys.stdin.isatty():
            keyboard = Keyboard(on_key)
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        deadline = None if args.seconds is None else time.monotonic() + args.seconds
        try:
            runner.run(seconds=args.seconds)
            if dashboard and runner.killed:
                # Leave the dashboard up so the operator can see it say KILLED.
                console.event("dashboard", "Stopped. The dashboard stays up to show it; q or Ctrl-C closes it.")
                while not runner.stop_requested and (deadline is None or time.monotonic() < deadline):
                    time.sleep(0.2)
        except KeyboardInterrupt:
            runner.kill("Kill switch (Ctrl-C)")
        finally:
            if keyboard:
                keyboard.close()
        if console.tty:
            print()

        runner.finish()
        if runner.restorable:
            what = ", ".join("%s back to %s" % (d["setting"], d["start"]) for d in runner.restorable)
            if args.restore or (sys.stdin.isatty() and input("Put %s? [y/N] " % what).strip().lower().startswith("y")):
                runner.restore()
            else:
                print("Left as is (%s not done)." % what)
        elif runner.killed and runner.changes:
            print("The bridge is locked, so I can't put settings back. Set it by hand: %s." %
                  runner._text("IsoSensitivity", runner.start_props))
        print("%d change(s) made. Session folder: %s" % (len(runner.changes), session))
    except RunnerError as e:
        sys.exit("Not started: %s" % e)
    finally:
        if dashboard:
            dashboard.stop()
        runner.close()
        if fake_proc:
            try:
                BridgeClient(socket_path, timeout=2).quit()
            except (OSError, BridgeError):
                pass
            try:
                fake_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                fake_proc.terminate()


if __name__ == "__main__":
    main()
