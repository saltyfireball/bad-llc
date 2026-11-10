"""The gap between sections stays even and never balloons (SLRM-1953).

Loads public/index.html in headless Chromium and WebKit at phone, tablet and desktop widths and
measures the visible gap between neighbouring sections: from the last thing painted in one (text,
an image, a border or a background) to the first thing painted in the next. Padding does not count.

Needs Playwright with its browsers (skips without it):
    ~/.venvs/claude/bin/python -m unittest tests.test_spacing
SPACING_PUBLIC=/some/public measures another copy of the page (to show an old one fails).
"""
import functools
import http.server
import os
import threading
import unittest
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = Path(os.environ.get("SPACING_PUBLIC", ROOT / "public"))

# The page's sections, in order: the hero, every section in main, the footer.
SECTIONS = "body > header.hero, main > section, body > footer"
WIDTHS = (375, 390, 768, 1280, 1440)
ENGINES = ("chromium", "webkit")

# --bo-section is 3.5rem on a phone and 6rem on a desktop. A few px of slack covers line boxes.
PHONE_MAX = 64      # px, widths under 600
DESKTOP_MAX = 104   # px, everything wider
HERO_EXTRA = 48     # px the hero may add on top: its own bottom padding, on purpose

MEASURE = r"""
(sel) => {
  const alpha = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return c === 'transparent' ? 0 : 1;
    const p = m[1].split(/[ ,\/]+/).filter(Boolean); return p.length > 3 ? parseFloat(p[3]) : 1; };
  const shown = e => {
    for (let n = e; n && n.nodeType === 1; n = n.parentElement) {
      const s = getComputedStyle(n);
      if (s.display === 'none' || s.visibility === 'hidden' || parseFloat(s.opacity) === 0) return false;
      if (s.clipPath && s.clipPath.indexOf('inset(50%') === 0) return false;
    }
    return true;
  };
  const painted = e => {
    const s = getComputedStyle(e);
    if (/^(img|video|canvas|svg|picture)$/i.test(e.tagName)) return true;
    if (alpha(s.backgroundColor) > 0 || s.backgroundImage !== 'none') return true;
    for (const side of ['Top', 'Right', 'Bottom', 'Left'])
      if (parseFloat(s['border' + side + 'Width']) > 0 && s['border' + side + 'Style'] !== 'none'
          && alpha(s['border' + side + 'Color']) > 0) return true;
    return false;
  };
  const box = root => {
    let top = Infinity, bottom = -Infinity;
    const add = r => { if (r.width < 2 || r.height < 2) return; top = Math.min(top, r.top); bottom = Math.max(bottom, r.bottom); };
    const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    for (let n = w.currentNode; n; n = w.nextNode()) {
      if (n.nodeType === 3) {
        if (!n.textContent.trim() || !shown(n.parentElement)) continue;
        const rg = document.createRange(); rg.selectNodeContents(n);
        for (const r of rg.getClientRects()) add(r);
      } else if (shown(n) && painted(n)) add(n.getBoundingClientRect());
    }
    return { top: top + scrollY, bottom: bottom + scrollY };
  };
  return [...document.querySelectorAll(sel)].map(e => ({
    name: e.tagName.toLowerCase() + (e.className ? '.' + String(e.className).split(' ')[0] : '')
      + (e.getAttribute('aria-labelledby') ? '#' + e.getAttribute('aria-labelledby') : ''),
    ...box(e) }));
}
"""


def serve(root):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def measure(url, engines=ENGINES, widths=WIDTHS):
    """{(engine, width): [(from, to, gap_px), ...]} for every neighbouring pair of sections."""
    out = {}
    with sync_playwright() as p:
        for engine in engines:
            browser = getattr(p, engine).launch()
            for width in widths:
                page = browser.new_page(viewport={"width": width, "height": 900}, reduced_motion="reduce")
                page.goto(url, wait_until="load")
                page.evaluate("document.fonts.ready.then(() => true)")
                boxes = page.evaluate(MEASURE, SECTIONS)
                out[(engine, width)] = [(a["name"], b["name"], round(b["top"] - a["bottom"])) for a, b in zip(boxes, boxes[1:])]
                page.close()
            browser.close()
    return out


@unittest.skipIf(sync_playwright is None, "playwright not installed")
class SectionSpacing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        srv = serve(PUBLIC)
        cls.addClassCleanup(srv.server_close)
        cls.addClassCleanup(srv.shutdown)
        cls.gaps = measure(f"http://127.0.0.1:{srv.server_port}/index.html")

    def test_gaps_stay_under_the_limit(self):
        bad = []
        for (engine, width), pairs in self.gaps.items():
            limit = PHONE_MAX if width < 600 else DESKTOP_MAX
            for i, (a, b, gap) in enumerate(pairs):
                allowed = limit + (HERO_EXTRA if i == 0 else 0)
                if gap > allowed:
                    bad.append(f"{engine} {width}px: {a} -> {b} is {gap}px, max {allowed}")
        self.assertEqual(bad, [], "\n" + "\n".join(bad))

    def test_gaps_never_collapse(self):
        bad = [f"{e} {w}px: {a} -> {b} is {g}px" for (e, w), pairs in self.gaps.items() for a, b, g in pairs if g < 32]
        self.assertEqual(bad, [], "\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
