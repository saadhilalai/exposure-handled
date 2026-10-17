"""Print a camera settings snapshot (from probe_readonly) as readable tables.

Usage: python3 tools/show_settings.py sessions/<folder>
Also writes <folder>/settings_table.md.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.sony_values import describe_choices, describe_property, is_decoded, load_enums  # noqa: E402

KEY_GROUPS = [
    ("Exposure", ["ExposureCtrlType", "ExposureProgramMode", "IrisModeSetting", "FNumber",
                  "ShutterModeSetting", "ShutterMode", "ShutterModeStatus", "ShutterSpeed", "ShutterAngle",
                  "ExtendedShutterSpeed", "GainControlSetting", "IsoSensitivity", "IsoCurrentSensitivity",
                  "GainBaseIsoSensitivity", "BaseISOSwitchEI", "ExposureIndex"]),
    ("Color", ["WhiteBalance", "Colortemp", "AWBL"]),
    ("Look / log (read-only for us)", ["PictureProfile", "PictureProfile_Gamma", "PictureProfile_ColorMode",
                                       "MovieShootingMode", "MovieShootingModeColorGamut", "LogShootingMode",
                                       "BaseLookValue", "CreativeLook", "MonitorLUTSetting", "GammaDisplayAssist"]),
    ("Focus", ["FocusMode", "FocusArea", "SubjectRecognitionAF", "FocusIndication", "NearFar",
               "FocusPositionCurrentValue"]),
    ("Recording (read-only for us)", ["RecordingState", "Movie_Recording_FrameRateSetting",
                                      "Movie_Recording_Setting", "Movie_File_Format", "Movie_RecordingMedia"]),
    ("Live view / camera", ["LiveViewStatus", "LiveView_Image_Quality", "LiveViewDisplayEffect",
                            "PriorityKeySettings", "BatteryLevel", "TotalBatteryLevel", "LensModelName",
                            "SoftwareVersion"]),
]

# Identifies the individual camera body; kept out of printed tables.
PRIVATE = {"BodySerialNumber"}


def changeable(prop):
    if prop["can_set_now"]:
        return "yes"
    return {"DisplayOnly": "no (display only)", "False": "no (not now)",
            "NotSupported": "no (not supported)"}.get(prop["enable"], "no")


def table(rows, headers):
    widths = [max(len(str(r[i])) for r in rows + [headers]) for i in range(len(headers))]
    widths = [min(w, 70) for w in widths]
    line = lambda r: "  ".join(str(c)[:widths[i]].ljust(widths[i]) for i, c in enumerate(r))
    return "\n".join([line(headers), line(["-" * w for w in widths])] + [line(r) for r in rows])


def md_table(rows, headers):
    esc = lambda s: str(s).replace("|", "\\|")
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def main():
    folder = Path(sys.argv[1])
    snapshot = json.loads((folder / "settings_start.json").read_text())
    result_path = folder / "probe_result.json"
    result = json.loads(result_path.read_text()) if result_path.exists() else {}
    enums = load_enums()
    props = {p["name"]: p for p in snapshot["properties"]}

    text_out, md_out = [], []
    cam = snapshot["camera"]
    header = "Camera: %s via %s   SDK version: %s   Read at: %s   Settings reported: %d" % (
        cam["model"], cam["connection"], snapshot["sdk_version"], snapshot["captured_at"],
        snapshot["property_count"])
    text_out.append(header)
    md_out.append("# FX2 settings snapshot\n\n" + header + "\n")

    headers = ["Setting", "Current", "Changeable now", "Allowed values"]
    for group, names in KEY_GROUPS:
        rows = []
        for name in names:
            if name in props:
                p = props[name]
                rows.append([name, describe_property(p, enums), changeable(p), describe_choices(p, enums)])
            else:
                rows.append([name, "(not reported)", "", ""])
        text_out.append("\n== %s ==\n%s" % (group, table(rows, headers)))
        md_out.append("\n## %s\n\n%s\n" % (group, md_table(rows, headers)))

    shown = {n for _, names in KEY_GROUPS for n in names}
    rest = []
    for name in sorted(props):
        if name in shown or name in PRIVATE:
            continue
        p = props[name]
        current = describe_property(p, enums) if (is_decoded(name, enums) or p["type"] == "STR") else p["current"]
        rest.append([name, current, p["type"], changeable(p)])
    rest_headers = ["Setting", "Current (raw unless decoded)", "Type", "Changeable now"]
    text_out.append("\n== All other settings (%d) ==\n%s" % (len(rest), table(rest, rest_headers)))
    md_out.append("\n## All other settings (%d)\n\n%s\n" % (len(rest), md_table(rest, rest_headers)))

    if result:
        lv = result.get("liveview")
        changed = result.get("changed_between_reads", [])
        summary = ["", "== Probe result =="]
        summary.append("Live view frame: %s" % (json.dumps(lv) if lv else "NOT captured"))
        summary.append("Settings that differed between the first and second read: %d" % len(changed))
        for c in changed:
            summary.append("  %s: %s -> %s" % (c["name"], c["start"], c["end"]))
        text_out += summary
        md_out.append("\n## Probe result\n\n" + "\n".join("- " + s for s in summary[2:]) + "\n")

    print("\n".join(text_out))
    (folder / "settings_table.md").write_text("\n".join(md_out))
    print("\nSaved table -> %s" % (folder / "settings_table.md"))


if __name__ == "__main__":
    main()
