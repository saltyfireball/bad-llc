"""Phone layout checks (SLRM-1952): no sideways scroll, and the personnel file stacks.

Loads public/ in headless Chromium and WebKit at phone and tablet widths. Skips when
Playwright or its browsers are not installed.

Run: ~/.venvs/claude/bin/python -m unittest tests.test_mobile_layout
"""
import functools
import http.server
import threading
import unittest
from pathlib import Path

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

PUBLIC = Path(__file__).resolve().parent.parent / "public"
WIDTHS = (320, 375, 390, 430, 768)
ENGINES = ("chromium", "webkit")

# Everything that sticks out past the viewport, and each staff entry's box against its list.
MEASURE = """
() => {
  const vw = document.documentElement.clientWidth;
  const wide = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('svg') && el.tagName.toLowerCase() !== 'svg') continue;
    if (el.classList.contains('skip')) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.right > vw + 0.5 || r.left < -0.5)
      wide.push(`${el.tagName.toLowerCase()}.${el.className} ${Math.round(r.left)}..${Math.round(r.right)}`);
  }
  const list = document.querySelector('#personnel dl');
  const box = list.getBoundingClientRect();
  const rows = [...list.querySelectorAll('.staff-row')].map(row => {
    const r = row.getBoundingClientRect();
    const dd = row.querySelector('dd');
    const ch = parseFloat(getComputedStyle(dd).fontSize) * 0.5;
    return {name: row.querySelector('dt').textContent.trim(), left: r.left, right: r.right, top: r.top,
            bottom: r.bottom, ddChars: dd.getBoundingClientRect().width / ch};
  });
  return {scrollWidth: document.documentElement.scrollWidth, clientWidth: vw, wide,
          list: {left: box.left, right: box.right}, rows};
}
"""


def serve(folder):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    handler.log_message = lambda *args: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@unittest.skipIf(sync_playwright is None, "playwright is not installed")
class MobileLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = serve(PUBLIC)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/index.html"
        cls.pw = sync_playwright().start()
        cls.browsers = {}
        for engine in ENGINES:
            try:
                cls.browsers[engine] = getattr(cls.pw, engine).launch()
            except PlaywrightError:
                pass
        if not cls.browsers:
            cls.tearDownClass()
            raise unittest.SkipTest("no Playwright browser is installed")

    @classmethod
    def tearDownClass(cls):
        for browser in cls.browsers.values():
            browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def measure(self, engine, width):
        page = self.browsers[engine].new_page(viewport={"width": width, "height": 900}, reduced_motion="reduce")
        try:
            page.goto(self.url, wait_until="load")
            page.evaluate("document.fonts.ready")
            return page.evaluate(MEASURE)
        finally:
            page.close()

    def test_phone_widths(self):
        for engine in self.browsers:
            for width in WIDTHS:
                with self.subTest(engine=engine, width=width):
                    m = self.measure(engine, width)
                    self.assertLessEqual(m["scrollWidth"], m["clientWidth"], "the page scrolls sideways")
                    self.assertEqual(m["wide"], [], "elements stick out past the viewport")
                    self.assertEqual(len(m["rows"]), 5)
                    for row in m["rows"]:
                        # Each entry spans the whole list, inside it: none clipped, none side by side.
                        self.assertGreaterEqual(row["left"], m["list"]["left"] - 0.5, row["name"])
                        self.assertLessEqual(row["right"], m["list"]["right"] + 0.5, row["name"])
                        self.assertGreaterEqual(row["right"] - row["left"], 0.95 * (m["list"]["right"] - m["list"]["left"]), row["name"])
                        self.assertGreaterEqual(row["ddChars"], 12, f"{row['name']} text column is too narrow")
                    for above, below in zip(m["rows"], m["rows"][1:]):
                        self.assertLessEqual(above["bottom"], below["top"] + 0.5, f"{below['name']} is not under {above['name']}")


if __name__ == "__main__":
    unittest.main()
