"""Python side of the camera bridge: talks to camera_bridge over its private socket.

Every command is one text line; every answer is one JSON line. Live-view
frames come as a JSON header line followed by the raw JPEG bytes.
"""
import json
import socket
from pathlib import Path

DEFAULT_SOCKET = Path(__file__).resolve().parent.parent / "run" / "bridge.sock"


class BridgeError(Exception):
    pass


class BridgeClient:
    def __init__(self, socket_path=DEFAULT_SOCKET, timeout=10.0):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect(str(socket_path))
        self.reader = self.sock.makefile("rb")

    def close(self):
        self.reader.close()
        self.sock.close()

    def command(self, line):
        self.sock.sendall((line + "\n").encode())
        raw = self.reader.readline()
        if not raw:
            raise BridgeError("bridge closed the connection")
        return json.loads(raw)

    def status(self):
        return self.command("status")

    def settings(self):
        """Every setting, as {name: property dict}."""
        reply = self.command("settings")
        if not reply["ok"]:
            raise BridgeError(reply["error"])
        return {p["name"]: p for p in reply["properties"]}

    def get(self, *names):
        """Selected settings by Sony name, as {name: property dict}."""
        reply = self.command("get " + " ".join(names))
        if not reply["ok"]:
            raise BridgeError(reply["error"])
        return {p["name"]: p for p in reply["properties"]}

    def frame(self, after=-1, timeout_ms=1000):
        """Next live-view frame newer than `after`. Returns (header, jpeg_bytes) or (header, None)."""
        self.sock.sendall(("frame %d %d\n" % (after, timeout_ms)).encode())
        header = json.loads(self.reader.readline())
        if not header["ok"]:
            return header, None
        return header, self.reader.read(header["bytes"])

    def lvstats(self, reset=False):
        return self.command("lvstats reset" if reset else "lvstats")

    def display_strings(self, type_id):
        return self.command("display_strings %d" % type_id)

    def lock(self):
        """Kill switch: the bridge refuses every change until it is restarted."""
        return self.command("lock")

    def quit(self):
        return self.command("quit")

    def _set_raw(self, name, raw_value):
        """Low level. Use agent.safety.SafetyGate.change_setting() instead, which checks
        ranges, refuses while recording, and logs the reason."""
        return self.command("set %s %d" % (name, raw_value))
