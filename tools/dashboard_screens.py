"""Screenshots of the dashboard, driven like a person would use it (needs a running dashboard).

Clicks Auto twice, waits for the agent to work, hovers the chart, switches to false color,
locks, takes a phone-size view, then presses the kill switch. Uses the installed Google
Chrome through Playwright (a test-only tool: `uv pip install playwright`).

Usage: python tools/dashboard_screens.py <out_dir> [--url http://127.0.0.1:8765/] [--work 12]
"""
import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--url", default="http://127.0.0.1:8765/")
    ap.add_argument("--work", type=float, default=12, help="seconds to let the agent work after Auto on")
    ap.add_argument("--no-kill", action="store_true")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    shot = lambda page, name: (page.screenshot(path=str(out / (name + ".png"))), print("saved", out / (name + ".png")))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(args.url)
        page.wait_for_function("document.getElementById('live').naturalWidth > 0", timeout=15000)
        page.wait_for_timeout(2500)
        shot(page, "01_desktop_suggesting")

        if page.is_enabled("#btn-auto"):
            page.click("#btn-auto")
            page.wait_for_timeout(300)
            shot(page, "02_auto_armed")
            page.click("#btn-auto")
        page.wait_for_timeout(args.work * 1000)
        shot(page, "03_desktop_auto")

        page.locator(".insights").scroll_into_view_if_needed()
        box = page.locator("#chart-svg").bounding_box()
        page.mouse.move(box["x"] + box["width"] * 0.62, box["y"] + box["height"] * 0.5)
        page.wait_for_timeout(400)
        page.locator(".insights").screenshot(path=str(out / "04_chart_hover.png"))
        print("saved", out / "04_chart_hover.png")
        page.mouse.move(5, 5)
        page.evaluate("window.scrollTo(0, 0)")

        page.click("[data-mode=false_color]")
        page.click("#t-regions")
        page.wait_for_timeout(1500)
        shot(page, "05_false_color_regions")
        page.click("[data-mode=zebras]")
        page.wait_for_timeout(1200)
        page.locator(".frame").screenshot(path=str(out / "06_zebras.png"))
        print("saved", out / "06_zebras.png")
        page.click("[data-mode=clean]")
        page.click("#t-regions")

        page.click("#btn-lock")
        page.wait_for_timeout(1200)
        shot(page, "07_locked")
        page.click("#btn-lock")

        phone = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True,
                                 has_touch=True)
        phone.goto(args.url)
        phone.wait_for_function("document.getElementById('live').naturalWidth > 0", timeout=15000)
        phone.wait_for_timeout(2000)
        phone.screenshot(path=str(out / "08_phone_top.png"))
        phone.screenshot(path=str(out / "09_phone_full.png"), full_page=True)
        print("saved phone views")

        if not args.no_kill:
            page.click("#btn-kill")
            page.wait_for_timeout(1500)
            shot(page, "10_killed")
        if errors:
            print("BROWSER ERRORS:", *errors, sep="\n  ")
            sys.exit(1)
        print("no browser errors")
        browser.close()


if __name__ == "__main__":
    main()
