"""Checks the site in Microsoft Edge (Playwright): desktop and phone, dark and light. Fails on console errors,
failed requests, horizontal overflow, images without alt text, a missing download detection, a hero loop that
doesn't play, and accessibility violations (axe-core, with the production headers from staticwebapp.config.json
applied when checking a local server).

usage: python tools/validate.py [url] [--shots]
  url      default http://127.0.0.1:8781/; serve site/ first:
           python -m http.server 8781 --bind 127.0.0.1 --directory site
  --shots  save each view's first screen and full page to tools/.out/shots/
setup:     pip install -r tools/requirements.txt (uses the installed Microsoft Edge)
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from axe_playwright_python.sync_playwright import Axe
from playwright.sync_api import TimeoutError, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = next((a for a in sys.argv[1:] if not a.startswith("--")), "http://127.0.0.1:8781/")
ORIGIN = "{0.scheme}://{0.netloc}".format(urlparse(URL))
LOCAL = urlparse(URL).hostname in ("127.0.0.1", "localhost") or URL.startswith("http://")
SHOTS = ROOT / "tools" / ".out" / "shots" if "--shots" in sys.argv else None
HEADERS = json.loads((ROOT / "site" / "staticwebapp.config.json").read_text(encoding="utf-8"))["globalHeaders"]
ANDROID = ("Mozilla/5.0 (Linux; Android 15; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/131.0.0.0 Mobile Safari/537.36")
VIEWS = [
    ("desktop-dark", dict(viewport={"width": 1440, "height": 900}, color_scheme="dark")),
    ("desktop-light", dict(viewport={"width": 1440, "height": 900}, color_scheme="light")),
    ("phone-dark", dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, color_scheme="dark",
                        is_mobile=True, has_touch=True, user_agent=ANDROID)),
    ("phone-light", dict(viewport={"width": 390, "height": 844}, device_scale_factor=2, color_scheme="light",
                         is_mobile=True, has_touch=True, user_agent=ANDROID)),
]
REVEAL_ALL = "document.querySelectorAll('.reveal').forEach(e => e.classList.add('is-in'))"


def with_production_headers(route):
    response = route.fetch()
    route.fulfill(response=response, headers={**response.headers, **HEADERS})


problems = []
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge", headless=True)
    for name, options in VIEWS:
        ctx = browser.new_context(**options)
        page = ctx.new_page()
        log = []
        page.on("console", lambda m, log=log: log.append(f"console {m.type}: {m.text}") if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e, log=log: log.append(f"page error: {e}"))
        page.on("requestfailed", lambda r, log=log: log.append(f"request failed: {r.url} {r.failure}"))
        page.on("response", lambda r, log=log: log.append(f"HTTP {r.status}: {r.url}") if r.status >= 400 else None)
        if LOCAL:
            page.route(f"{ORIGIN}/**", with_production_headers)
        page.goto(URL, wait_until="networkidle")
        if SHOTS:
            SHOTS.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(SHOTS / f"{name}-fold.png"))
        label = page.locator("[data-download-label]").first.inner_text()
        overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
        no_alt = page.evaluate("[...document.images].filter(i => !i.hasAttribute('alt')).map(i => i.src)")
        page.locator("[data-hero-loop]").scroll_into_view_if_needed()
        try:
            # Selector waits work under the production CSP without unsafe-eval.
            page.locator("[data-hero-loop].is-playing").wait_for(state="visible", timeout=8000)
            playing = page.evaluate("(() => { const v = document.querySelector('[data-hero-loop] video'); return !!v && !v.paused; })()")
        except TimeoutError:
            playing = False
        if SHOTS:
            page.evaluate(REVEAL_ALL)
            page.wait_for_timeout(500)
            page.screenshot(path=str(SHOTS / f"{name}-full.png"), full_page=True)
        issues = list(log)
        if overflow:
            issues.append("the page scrolls sideways")
        if no_alt:
            issues.append(f"images without alt: {no_alt}")
        if label.strip() == "Download Lumi":
            issues.append("the download button didn't detect the platform")
        if not playing:
            issues.append("the hero loop didn't play")
        print(f"{name}: download '{label.strip()}' | hero loop {'playing' if playing else 'NOT playing'} | "
              f"{'OK' if not issues else str(len(issues)) + ' problem(s)'}")
        problems += [f"{name}: {i}" for i in issues]
        ctx.close()

    axe = Axe()
    for scheme, (w, h) in (("dark", (1440, 900)), ("light", (1440, 900)), ("dark", (390, 844))):
        ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=scheme, reduced_motion="reduce")
        page = ctx.new_page()
        if LOCAL:
            page.route(f"{ORIGIN}/**", with_production_headers)
        page.goto(URL, wait_until="networkidle")
        # Audit final colours, not mid-reveal opacity, with every answer open.
        page.evaluate(REVEAL_ALL)
        page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
        page.wait_for_timeout(800)
        violations = axe.run(page).response["violations"]
        print(f"axe {scheme} {w}px: {len(violations)} violation(s)")
        for v in violations:
            nodes = "; ".join(str(n["target"]) for n in v["nodes"][:4])
            problems.append(f"axe {scheme} {w}px [{v['impact']}] {v['id']}: {v['help']} -> {nodes}")
        ctx.close()
    browser.close()

print(f"\n{len(problems)} problem(s)" if problems else "\nall checks passed")
for item in problems:
    print("  " + item)
sys.exit(1 if problems else 0)
