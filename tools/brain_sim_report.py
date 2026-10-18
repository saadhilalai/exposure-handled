"""Run every fake scene through the brain + simulated camera and print what it did and why.

Usage: python tools/brain_sim_report.py [scene_name ...] [--json out.json]
No camera involved.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agent.brain import Brain  # noqa: E402
from agent.looks import LOOKS  # noqa: E402
from agent.scenes import SCENES  # noqa: E402
from agent.sim import SimCamera, simulate  # noqa: E402


def summarize(spec, run, cam):
    look = LOOKS[spec.look]
    dt = 1 / 24
    last_obs = run.log[-1][2]
    settle = None
    if spec.event_t is not None:
        after = [t for t, _ in run.exposure_changes() if t >= spec.event_t]
        settle = round(after[-1] - spec.event_t, 2) if after else 0.0
    return {
        "scene": spec.name, "look": look.name, "expect": spec.expect,
        "changes": len(run.changes), "reversals": run.reversals(),
        "seconds_clipping": round(run.seconds_clipping(look.max_clip_pct, dt), 2),
        "settle_s": settle,
        "end": "ISO %d  f/%g  1/%d  ND %.2f  WB %sK" % (cam.iso, cam.fnumber, round(1 / cam.shutter_s), cam.nd, cam.wb_kelvin),
        "end_face": None if last_obs.face is None else round(last_obs.face, 2),
        "end_key": round(last_obs.key, 2),
        "decisions": [(round(t, 2), p.reason) for t, p in run.changes],
        "advice": [(round(t, 2), a) for t, a in run.advice],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--json")
    args = ap.parse_args()
    results = []
    for spec in SCENES:
        if args.names and spec.name not in args.names:
            continue
        cam = SimCamera(**spec.camera)
        run = simulate(spec.scene, cam, Brain(spec.look), spec.seconds,
                       recording=spec.recording, operator_nd_delay=spec.operator_nd_delay)
        s = summarize(spec, run, cam)
        results.append(s)
        print("\n=== %s  [%s]" % (s["scene"], s["look"]))
        print("    expect: %s" % s["expect"])
        print("    changes %d, reversals %d, clipping %.1f s%s" % (
            s["changes"], s["reversals"], s["seconds_clipping"],
            ", settled %.1f s after the change" % s["settle_s"] if s["settle_s"] is not None else ""))
        for t, why in s["decisions"]:
            print("    %6.2f s  CHANGE  %s" % (t, why))
        for t, a in s["advice"]:
            print("    %6.2f s  ADVICE  %s" % (t, a))
        print("    end: %s | face %s, scene %+.1f st" % (s["end"], s["end_face"], s["end_key"]))
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
