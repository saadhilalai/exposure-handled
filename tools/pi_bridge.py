"""Start the bridge in one of its two Pi modes, with the command line from the settings file. Run by the
camera-bridge services (deploy/pi/): --read-only at power-up, --armed only after the phone armed it.

Usage: python tools/pi_bridge.py --read-only | --armed  [--print]   (--print shows the command, starts nothing)
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.config import ConfigError, bridge_argv, load  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--read-only", action="store_true")
    mode.add_argument("--armed", action="store_true")
    ap.add_argument("--print", action="store_true", help="show the command and stop")
    args = ap.parse_args()
    try:
        cfg = load()
    except ConfigError as e:
        sys.exit("Settings: %s" % e)
    argv = bridge_argv(cfg, armed=args.armed)
    if args.print:
        print(" ".join(argv))
        return
    for folder in (cfg.logs_dir, cfg.state_dir, cfg.run_dir):
        folder.mkdir(parents=True, exist_ok=True)
    if not cfg.binary.is_file():
        sys.exit("The bridge isn't built yet: %s (run deploy/pi/install.sh)" % cfg.binary)
    sys.stdout.flush()
    os.execv(argv[0], argv)                      # the bridge replaces this program: systemd watches it directly


if __name__ == "__main__":
    main()
