"""Read which LUT the FX2's Display LUT uses, read-only, for the Step 7 blind test.

The plan says every blind-test clip gets the same LUT as the camera's Display LUT, named in
the plan before any clip is graded. This reads it from the camera:
  MonitorLUTSetting   Display LUT on or off
  BaseLookValue       the selected Base Look: kind (preset / user / scene file / temporary) + index
  Base Look names     the camera's own names for each Base Look (Sony "display strings")
and saves them to <out_dir>/display_lut.json. It refuses to run unless the bridge was
started with --read-only, so it cannot change anything.

Usage: python tools/read_display_lut.py <out_dir> [--socket run/bridge.sock]
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.bridge_client import DEFAULT_SOCKET, BridgeClient  # noqa: E402
from agent.sony_values import describe_value, load_enums  # noqa: E402

KINDS = {0x00: "Preset", 0x01: "User", 0x02: "Scene file"}   # Sony's CrBaseLookValue kinds
TEMPORARY = 0x8000
NAMES, INPUTS, OUTPUTS = 3, 2, 4     # CrDisplayStringType_BaseLook_Name / _Input / _Output_Display


def decode_base_look(value):
    """BaseLookValue -> (kind, index). Sony: upper 8 bits kind, lower 8 bits index; 0x8000 = temporary."""
    if value & TEMPORARY:
        return "Temporary copy of %s" % KINDS.get((value >> 8) & 0x0F, "?"), value & 0xFF
    return KINDS.get(value >> 8, "kind 0x%02x" % (value >> 8)), value & 0xFF


def lookup(items, value):
    return next((i["text"] for i in items if i.get("value") == value), None)


def summarize(props, names, inputs, outputs, enums):
    """What the camera says, as a dict with a one-line answer for the plan."""
    out = {"read_on": date.today().isoformat()}
    if "MonitorLUTSetting" in props:
        out["display_lut"] = describe_value("MonitorLUTSetting", props["MonitorLUTSetting"]["current"], enums)
    if "BaseLookValue" not in props:
        out["answer"] = "The camera didn't report a Base Look: check Display LUT / Base Look in the camera menu by hand."
        return out
    value = props["BaseLookValue"]["current"]
    kind, index = decode_base_look(value)
    out.update(base_look_value=value, kind=kind, index=index, name=lookup(names, value),
               input=lookup(inputs, value), output=lookup(outputs, value),
               all_names=[{"value": i["value"], "text": i["text"]} for i in names])
    if "EmbedLUTFile" in props:
        out["embed_lut_file"] = describe_value("EmbedLUTFile", props["EmbedLUTFile"]["current"], enums)
    label = out["name"] or "%s #%d (name not reported)" % (kind, index)
    out["answer"] = "Base Look: %s (%s, value 0x%04x), Display LUT: %s, read on %s" % (
        label, kind, value, out.get("display_lut", "?"), out["read_on"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--socket", default=str(DEFAULT_SOCKET))
    args = ap.parse_args()
    client = BridgeClient(args.socket)
    if not client.status().get("read_only"):
        sys.exit("Refusing: start the bridge with --read-only for this.")
    props = client.get("MonitorLUTSetting", "BaseLookValue", "EmbedLUTFile")
    lists = {}
    for type_id in (NAMES, INPUTS, OUTPUTS):
        reply = client.display_strings(type_id)
        lists[type_id] = reply.get("items", []) if reply.get("ok") else []
    client.close()
    result = summarize(props, lists[NAMES], lists[INPUTS], lists[OUTPUTS], load_enums())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "display_lut.json").write_text(json.dumps(result, indent=1))
    print(result["answer"])
    if result.get("all_names"):
        print("Base Looks the camera offers:", ", ".join("%s (0x%04x)" % (i["text"], i["value"]) for i in result["all_names"]))
    print("Next: find that LUT's .cube file, then write its exact file name into docs/step7-test-plan.md.")


if __name__ == "__main__":
    main()
