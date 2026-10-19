"""Step 7: the printable run sheet, made from the frozen take order (tools/make_test_order.py).

One row per take, in shooting order, with the exact command and boxes to tick. People are
Person A / Person B: write their names on the paper, never in the repo. Which takes go to the
blind test is NOT on the sheet, on purpose, so nobody shoots those takes differently.

Usage: python tools/make_run_sheet.py            -> docs/step7-run-sheet.html and .pdf
"""
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.make_test_order import build_order  # noqa: E402

OUT = ROOT / "docs" / "step7-run-sheet"
METHOD_KEY = {"Agent": "agent", "FX2 auto": "fx2auto", "Manual": "manual"}
SCENES = {   # number: (title, look key, f-stop, the event, session)
    "S1": ("Window-backlit face", "interview", "f/4", "At 15 s open the blind fully, press m. Hold 35 s.", 1),
    "S3": ("Indoor tungsten", "cinematic", "f/2.8", "At 15 s one lamp off, press m. At 35 s back on, press m.", 1),
    "S4": ("Low light", "low_light", "f/2.8", "At 15 s dim about 1 stop, press m.", 1),
    "S6": ("Static control", "cinematic", "f/2.8", "Nothing changes. 60 s. No mark.", 1),
    "S2": ("Shade → sun walk", "run_and_gun", "f/5.6", "At ~15 s walk into the sun on the marked line, press m. Stand there.", 2),
    "S5": ("Sunset", "cinematic", "f/2.8", "The light falls on its own. Start ~25 min before sunset. Press m at each block start.", 2),
}
BONUS = {"S1": ["A", "B"], "S4": ["A", "B"], "S2": ["A"], "S3": ["B"]}


def command(take, look, method):
    if method == "agent":
        return "run_agent.py --live --dashboard --look %s --take %s --allow-iso-while-recording" % (look, take)
    return "run_agent.py --look %s --take %s" % (look, take)


def checks(method, bonus=False):
    first = {"agent": ["Auto on (press twice)"], "fx2auto": ["Camera Auto ISO on (800–12800)"],
             "manual": ["Dashboard not visible to you"]}[method]
    if bonus:
        first.append("Follow its advice")
    last = ["Camera Auto ISO back off"] if method == "fx2auto" else []
    return first + ["Rec started", "m at event", "Rec stopped", "q"] + last


def takes(order):
    """Every take in shooting order, grouped by scene: {scene: [(take, who, method, bonus)]}."""
    by_scene = {}
    for scene, who, rounds in order["rows"]:
        num = scene.split()[0]
        person = who.split()[-1] if who.startswith("Person") else None
        for n, methods in rounds:
            for m in methods:
                key = METHOD_KEY[m]
                name = "%s_R%d_%s%s" % (num, n, person + "_" if person else "", key)
                by_scene.setdefault(num, []).append((n, name, who, m, key, False))
    for num in by_scene:
        by_scene[num].sort(key=lambda t: t[0])         # S1/S4: rounds interleave A, B, A, B...
        for p in BONUS.get(num, []):
            by_scene[num].append((99, "%s_BONUS_%s_agent" % (num, p), "Person " + p, "Agent", "agent", True))
    by_scene["S5"] = [(i + 1, "S5_R%d_%s" % (i + 1, METHOD_KEY[m]), "one person", m, METHOD_KEY[m], False)
                      for i, block in enumerate(order["sunset"]) for m in block]          # 2-minute blocks
    return by_scene


def esc(s):
    return html.escape(str(s))


def render(order):
    by_scene = takes(order)
    total = sum(1 for rows in by_scene.values() for r in rows)
    parts = ["""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Step 7 run sheet | Camera Agent</title>
<style>
@font-face { font-family: "D-DIN"; src: url("../dashboard/fonts/D-DIN.woff2") format("woff2"); font-weight: 400; }
@font-face { font-family: "D-DIN"; src: url("../dashboard/fonts/D-DIN-Bold.woff2") format("woff2"); font-weight: 700; }
@font-face { font-family: "D-DIN Exp"; src: url("../dashboard/fonts/D-DINExp-Bold.woff2") format("woff2"); font-weight: 700; }
@page { size: Letter landscape; margin: 12mm; }
* { box-sizing: border-box; }
body { font-family: "D-DIN", "Helvetica Neue", Arial, sans-serif; color: #000; background: #fff; font-size: 10.5pt; margin: 0; }
.wide { font-family: "D-DIN Exp", "D-DIN", Arial, sans-serif; font-weight: 700; letter-spacing: .2em; text-transform: uppercase; }
header { display: flex; align-items: center; gap: 12px; border-bottom: 1.5px solid #000; padding-bottom: 8px; margin-bottom: 10px; }
header img { width: 30px; height: 30px; background: #000; border-radius: 3px; }
header h1 { font-size: 13pt; margin: 0; }
header .meta { margin-left: auto; font-size: 9pt; color: #444; text-align: right; }
h2 { font-size: 11pt; margin: 14px 0 4px; }
h2 small { font-family: "D-DIN", Arial, sans-serif; letter-spacing: 0; text-transform: none; font-weight: 400; color: #444; font-size: 10pt; margin-left: 8px; }
.event { margin: 0 0 6px; }
.fields { margin: 0 0 6px; color: #222; }
.fields span { display: inline-block; margin-right: 22px; }
table { width: 100%; border-collapse: collapse; page-break-inside: auto; }
tr { page-break-inside: avoid; }
th { text-align: left; font-size: 8pt; letter-spacing: .14em; text-transform: uppercase; border-bottom: 1px solid #000; padding: 3px 4px; }
td { border-bottom: 1px solid #bbb; padding: 5px 4px; vertical-align: top; }
td.take { font-weight: 700; white-space: nowrap; }
td.who { white-space: nowrap; }
td.cmd { font-family: Menlo, monospace; font-size: 7.5pt; color: #333; max-width: 300px; }
.box { display: inline-block; white-space: nowrap; margin: 0 10px 2px 0; font-size: 8.5pt; }
.box::before { content: ""; display: inline-block; width: 9px; height: 9px; border: 1px solid #000; margin-right: 4px; vertical-align: -1px; }
td.blank { width: 120px; }
tr.agent td.take::after { content: " ●"; font-size: 7pt; }
tr.bonus { background: #f2f2f2; }
.grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 28px; }
.grid p { margin: 2px 0; }
.session { page-break-before: always; }
.note { color: #444; font-size: 9pt; }
footer { margin-top: 14px; font-size: 8.5pt; color: #444; }
</style></head><body>"""]
    parts.append("""<header><img src="../dashboard/brand/s4d.png" alt="S4D"><h1 class="wide">Camera Agent · Step 7 run sheet</h1>
<div class="meta">Plan: FINAL, frozen at tag step7-plan-final<br>%d takes and blocks · ● = agent take (recording switch on)</div></header>""" % total)
    parts.append("""<div class="grid">
<div><h2 class="wide">People (names on paper only)</h2>
<p>Person A: ______________________ &nbsp; Person B: ______________________</p>
<p><span class="box">A agrees to be filmed</span><span class="box">A agrees to clips shown privately to raters</span></p>
<p><span class="box">B agrees to be filmed</span><span class="box">B agrees to clips shown privately to raters</span></p>
<p>Face memory: A <span class="box">yes, set once</span><span class="box">declined (scored vs +0.5)</span>
&nbsp; B <span class="box">yes, set once</span><span class="box">declined</span></p>
<p class="note">README or demo video use needs a separate OK from each person.</p></div>
<div><h2 class="wide">Before each session</h2>
<p><span class="box">23.98p, S-Log3 (Flexible ISO)</span><span class="box">USB Remote Shoot/Trn., airplane mode</span></p>
<p><span class="box">Bridge started with --allow-iso-while-recording (Step 7 sessions only)</span></p>
<p><span class="box">Restart the bridge WITHOUT that flag after the session</span></p>
<p><span class="box">Kill switch reachable: SPACE / dashboard / USB cable</span></p>
<p>Date ____________ Place ________________________ Sunset (session 2) ________</p></div>
</div>
<p class="note">Every take: reset the scene; set by hand the start ISO, 1/48 shutter, the look's f-stop, WB Kelvin and ND start;
take is 50 s (S6: 60 s); after agent takes, let the runner put ISO back. Which takes go to the blind test is deliberately not on this sheet.</p>""")
    current_session = None
    for num, (title, look, fstop, event, session) in SCENES.items():
        if session != current_session:
            current_session = session
            label = {1: "Session 1 · daytime, indoors (S1 needs daylight in the window)",
                     2: "Session 2 · a clear day: shade → sun around midday, then the sunset"}[session]
            parts.append('<h2 class="wide%s">%s</h2>' % (" session" if session == 2 else "", esc(label)))
        parts.append('<h2 class="wide">%s · %s<small>look %s, %s, shutter 1/48</small></h2>' % (num, esc(title), look, fstop))
        parts.append('<p class="event"><b>Event:</b> %s</p>' % esc(event))
        parts.append('<p class="fields"><span>Start ISO ______</span><span>WB ______ K</span><span>ND start ______</span>'
                     '<span>Focal length ______ mm</span><span>Framing marked <span class="box"></span></span></p>')
        parts.append("<table><tr><th>#</th><th>Take</th><th>Who</th><th>Method</th><th>Command</th><th>Checks</th>"
                     "<th>Session folder / notes</th></tr>")
        for i, (_, name, who, method, key, bonus) in enumerate(by_scene[num], 1):
            cls = " ".join(c for c in ("agent" if key == "agent" else "", "bonus" if bonus else "") if c)
            parts.append('<tr class="%s"><td>%d</td><td class="take">%s</td><td class="who">%s</td><td>%s%s</td><td class="cmd">%s</td>'
                         '<td>%s</td><td class="blank"></td></tr>' % (
                             cls, i, esc(name), esc(who), esc(method), " (bonus)" if bonus else "",
                             esc(command(name, look, key)), "".join('<span class="box">%s</span>' % esc(c)
                                                                    for c in checks(key, bonus))))
        parts.append("</table>")
    parts.append('<footer>Built by Saad Hilal · S4D · generated by tools/make_run_sheet.py from the frozen order '
                 '(seed 20261018)</footer></body></html>')
    return "\n".join(parts)


def main():
    page = render(build_order())
    OUT.with_suffix(".html").write_text(page)
    print("wrote", OUT.with_suffix(".html"))
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed: open the .html and print it (landscape).")
        return
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        tab = browser.new_page()
        tab.goto(OUT.with_suffix(".html").as_uri())
        tab.wait_for_timeout(500)
        tab.pdf(path=str(OUT.with_suffix(".pdf")), format="Letter", landscape=True, print_background=True,
                margin={"top": "12mm", "bottom": "12mm", "left": "12mm", "right": "12mm"})
        browser.close()
    print("wrote", OUT.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
