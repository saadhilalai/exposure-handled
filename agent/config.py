"""Settings for an install on the Pi: one file instead of paths written into the code.

Read from $CAMERA_AGENT_CONFIG, else /etc/camera-agent/config.toml. With no file, every value is this repo's own
default, so nothing changes on the Mac. A misspelled name or a wrong kind of value is refused, never silently
replaced by a default. Example with every setting: config/pi.example.toml.

On purpose, two things are NOT settings:
  - the start-up mode: the bridge always starts read-only (director's decision); only arming from the phone
    (PIN + LIVE) switches it to its normal mode;
  - anything the phone could turn on. allow_exposure (aperture, shutter, WB) lives only in this file, which only
    an admin on the Pi can edit.
"""
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYSTEM_FILE = Path("/etc/camera-agent/config.toml")

# section -> name -> (kind, default). Paths may be relative to the repo.
SCHEMA = {
    "paths": {"sdk_dir": (Path, ROOT / "sdk"), "data_dir": (Path, ROOT), "run_dir": (Path, ROOT / "run")},
    "bridge": {"binary": (Path, ROOT / "build" / "bridge" / "camera_bridge"), "allow_exposure": (bool, False)},
    "dashboard": {"host": (str, "127.0.0.1"), "port": (int, 8770), "names": (list, []), "pin_hash": (str, "")},
    "hotspot": {"ssid": (str, "camera-pi"), "band": (str, "bg")},
    "agent": {"look": (str, "cinematic"), "phone_timeout_s": (float, 5.0)},
}
LOOK_KEYS = ("cinematic", "run_and_gun", "interview", "low_light", "photo_portrait")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    sdk_dir: Path
    data_dir: Path
    run_dir: Path
    binary: Path
    allow_exposure: bool
    host: str
    port: int
    names: list = field(default_factory=list)
    pin_hash: str = ""
    ssid: str = "camera-pi"
    band: str = "bg"
    look: str = "cinematic"
    phone_timeout_s: float = 5.0
    source: str = "defaults"

    # Everything the Pi writes lives under data_dir, the card's writable partition.
    @property
    def sessions_dir(self):
        return self.data_dir / "sessions"

    @property
    def state_dir(self):
        return self.data_dir / "state"

    @property
    def lock_file(self):
        return self.state_dir / "locked"

    @property
    def paired_file(self):
        return self.state_dir / "paired.json"

    @property
    def logs_dir(self):
        return self.data_dir / "logs"

    @property
    def socket_path(self):
        return self.run_dir / "bridge.sock"


def _value(section, name, kind, raw):
    where = "[%s] %s" % (section, name)
    if kind is Path:
        if not isinstance(raw, str) or not raw:
            raise ConfigError("%s must be a path in quotes" % where)
        p = Path(raw).expanduser()
        return p if p.is_absolute() else ROOT / p
    if kind is float and isinstance(raw, int) and not isinstance(raw, bool):
        raw = float(raw)
    if kind is list:
        if not isinstance(raw, list) or not all(isinstance(x, str) and x for x in raw):
            raise ConfigError("%s must be a list of names in quotes" % where)
        return list(raw)
    if not isinstance(raw, kind) or (kind is int and isinstance(raw, bool)):
        raise ConfigError("%s must be %s" % (where, {bool: "true or false", int: "a whole number",
                                                     float: "a number", str: "text in quotes"}[kind]))
    return raw


def parse(text, source="(text)"):
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError("%s: %s" % (source, e)) from None
    values = {}
    for section, items in data.items():
        if section not in SCHEMA or not isinstance(items, dict):
            raise ConfigError("%s: unknown section [%s]" % (source, section))
        for name, raw in items.items():
            if name not in SCHEMA[section]:
                raise ConfigError("%s: unknown setting [%s] %s" % (source, section, name))
            values[name] = _value(section, name, SCHEMA[section][name][0], raw)
    for section in SCHEMA.values():
        for name, (_, default) in section.items():
            values.setdefault(name, list(default) if isinstance(default, list) else default)
    if not 1 <= values["port"] <= 65535:
        raise ConfigError("%s: [dashboard] port must be 1-65535" % source)
    if values["look"] not in LOOK_KEYS:
        raise ConfigError("%s: [agent] look must be one of %s" % (source, ", ".join(LOOK_KEYS)))
    if values["band"] not in ("bg", "a"):
        raise ConfigError("%s: [hotspot] band must be \"bg\" (2.4 GHz) or \"a\" (5 GHz)" % source)
    if not 1.0 <= values["phone_timeout_s"] <= 60.0:
        raise ConfigError("%s: [agent] phone_timeout_s must be 1-60 seconds" % source)
    return Config(source=source, **values)


def load(path=None):
    """The settings: from `path`, else $CAMERA_AGENT_CONFIG, else the system file, else the defaults."""
    path = path or os.environ.get("CAMERA_AGENT_CONFIG") or (SYSTEM_FILE if SYSTEM_FILE.exists() else None)
    if not path:
        return parse("", "defaults")
    path = Path(path)
    if not path.is_file():
        raise ConfigError("settings file not found: %s" % path)
    return parse(path.read_text(encoding="utf-8"), str(path))


def bridge_argv(cfg, armed):
    """The bridge's command line on the Pi. Read-only unless armed; ISO only unless the file allows exposure.
    The lock file is always on, so a kill outlives every restart."""
    argv = [str(cfg.binary), str(cfg.socket_path), str(cfg.logs_dir)]
    if not armed:
        argv.append("--read-only")
    elif cfg.allow_exposure:
        argv.append("--allow-exposure")
    return argv + ["--lock-file=%s" % cfg.lock_file]
