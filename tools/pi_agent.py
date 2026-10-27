"""The agent on the Raspberry Pi, run by the camera-agent service at power-up (see docs/step8-pi-build.md).

It reads /etc/camera-agent/config.toml (or $CAMERA_AGENT_CONFIG), puts the bridge in read-only, and serves the
dashboard to the phone on the Pi's own Wi-Fi. Arming (PIN + LIVE on the phone) is the only way to let it change
anything. It refuses to start without a PIN, because the dashboard is on a network.

Usage: python tools/pi_agent.py [--config FILE]
"""
import argparse
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.config import ConfigError, load  # noqa: E402
from agent.dashboard import Dashboard  # noqa: E402
from agent.pi_controller import PiController, SystemdBridge  # noqa: E402
from agent.pin import PinGuard  # noqa: E402


def open_dashboard(cfg, guard, controller, retry_s=2.0):
    """The hotspot's address may not be up yet at power-up: keep trying until it is."""
    while not controller.stop_event.is_set():
        try:
            return Dashboard(None, host=cfg.host, port=cfg.port, guard=guard, names=cfg.names).start()
        except OSError as e:
            print("Dashboard can't open %s:%d yet (%s): retrying" % (cfg.host, cfg.port, e), flush=True)
            time.sleep(retry_s)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", help="settings file (default: $CAMERA_AGENT_CONFIG or /etc/camera-agent/config.toml)")
    args = ap.parse_args()
    try:
        cfg = load(args.config)
    except ConfigError as e:
        sys.exit("Settings: %s" % e)
    if not cfg.pin_hash:
        sys.exit("No PIN yet: run  python tools/pi_pin.py  and put its line under [dashboard] in %s" % cfg.source)
    guard = PinGuard(cfg.pin_hash, cfg.paired_file)
    controller = PiController(cfg, SystemdBridge(), guard)
    signal.signal(signal.SIGTERM, lambda *_: controller.stop_event.set())     # systemd's stop
    dash = open_dashboard(cfg, guard, controller)
    if dash is None:
        return
    controller.attach(dash)
    print("Dashboard on %s (settings: %s). The bridge starts read-only." % (dash.url, cfg.source), flush=True)
    try:
        controller.run()
    except KeyboardInterrupt:
        controller.close()
    finally:
        dash.stop()


if __name__ == "__main__":
    main()
