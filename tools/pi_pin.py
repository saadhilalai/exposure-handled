"""Make the dashboard's PIN for the Pi. It asks for a 6-digit PIN twice (nothing shows as you type) and prints the
line to put in /etc/camera-agent/config.toml, under [dashboard]. Only a salted hash is printed, never the PIN.

Usage: python tools/pi_pin.py
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.pin import hash_pin  # noqa: E402


def main():
    pin = getpass.getpass("New 6-digit PIN: ")
    if getpass.getpass("Same PIN again: ") != pin:
        sys.exit("The two PINs don't match. Nothing changed.")
    try:
        line = 'pin_hash = "%s"' % hash_pin(pin)
    except ValueError as e:
        sys.exit("%s. Nothing changed." % e)
    print("\nPut this line under [dashboard] in /etc/camera-agent/config.toml, then restart the agent:\n")
    print(line)


if __name__ == "__main__":
    main()
