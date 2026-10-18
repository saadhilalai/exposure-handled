"""Kill switch from any terminal: locks the bridge, so it refuses every change until it's restarted.

Usage: python tools/kill_switch.py [--socket run/bridge.sock]
(The fake camera's socket is run/fake_bridge.sock.)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.bridge_client import DEFAULT_SOCKET, BridgeClient  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--socket", default=str(DEFAULT_SOCKET))
    path = Path(ap.parse_args().socket)
    if not path.exists():
        print("No bridge running at %s: nothing can change the camera." % path)
        return
    try:
        reply = BridgeClient(path, timeout=3).lock()
    except OSError as e:
        sys.exit("Couldn't reach the bridge (%s). If the camera is still plugged in, unplug the USB cable." % e)
    if not reply.get("locked"):
        sys.exit("Lock NOT confirmed (%s). Unplug the USB cable to be sure." % reply)
    print("Bridge LOCKED: it refuses every change until it's restarted. The camera is yours.")


if __name__ == "__main__":
    main()
