"""Bad Omen site check (SLRM-1881).

usage: ~/.venvs/claude/bin/python tools/sitecheck.py URL OUTDIR

For one URL it runs:
- Lighthouse (mobile and desktop presets) in Google Chrome: performance, accessibility,
  best-practices and SEO scores.
- Chromium and WebKit (Safari's engine; real Safari automation is not enabled on this Mac)
  at 390x844 (phone) and 1440x900 (laptop), each with JS on, JS off and reduced motion.
  Per run: a full-page screenshot, horizontal overflow, console errors, failed requests,
  third-party requests, whether the page text is visible, and the running CSS animations.

Writes OUTDIR/report.json, OUTDIR/report.md and the screenshots. Exit 1 when a hard check fails.
"""
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

SIZES = {"phone": (390, 844), "laptop": (1440, 900)}
MODES = ("js", "nojs", "reduced")


def lighthouse(url, out, preset):
    path = out / f"lighthouse-{preset}.json"
    cmd = ["npx", "--yes", "lighthouse@12", url, "--quiet", "--output=json", f"--output-path={path}",
           "--chrome-flags=--headless=new", "--only-categories=performance,accessibility,best-practices,seo"]
    if preset == "desktop":
        cmd.append("--preset=desktop")
    subprocess.run(cmd, check=False, capture_output=True, timeout=300)
    if not path.exists():
        return {"error": "lighthouse produced no report"}
    data = json.loads(path.read_text())
    scores = {k: round((v.get("score") or 0) * 100) for k, v in data["categories"].items()}
    audits = data["audits"]
    scores["LCP_ms"] = round(audits["largest-contentful-paint"]["numericValue"])
    scores["CLS"] = round(audits["cumulative-layout-shift"]["numericValue"], 3)
    scores["TBT_ms"] = round(audits["total-blocking-time"]["numericValue"])
    scores["bytes"] = round(audits["total-byte-weight"]["numericValue"])
    return scores


def browser_run(pw, engine, url, size, mode, out):
    host = urlparse(url).hostname
    browser = getattr(pw, engine).launch()
    ctx = browser.new_context(viewport={"width": size[0], "height": size[1]},
                              java_script_enabled=(mode != "nojs"),
                              reduced_motion="reduce" if mode == "reduced" else "no-preference")
    page = ctx.new_page()
    errors, failed, third = [], [], set()
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("requestfailed", lambda r: failed.append(r.url))
    page.on("request", lambda r: (urlparse(r.url).hostname not in (host, None)
                                  and not r.url.startswith("data:") and third.add(r.url)))
    page.goto(url, wait_until="load", timeout=30000)
    page.wait_for_timeout(1500)
    info = page.evaluate("""() => ({
      overflow: document.documentElement.scrollWidth - window.innerWidth,
      textChars: document.body.innerText.trim().length,
      h1: (document.querySelector('h1')||{}).innerText || null,
      footer: /A Bad Omen project/i.test(document.body.textContent),
      animations: document.getAnimations ? document.getAnimations()
        .filter(a => a.playState === 'running').length : null,
    })""") if mode != "nojs" else None
    if info is None:
        # JS is off for the page, but Playwright's evaluate still runs in an isolated world.
        info = {"overflow": page.evaluate("document.documentElement.scrollWidth - window.innerWidth"),
                "textChars": len(page.inner_text("body").strip()),
                "h1": page.inner_text("h1") if page.query_selector("h1") else None,
                "footer": "a bad omen project" in page.text_content("body").lower(),
                "animations": None}
    # Copy the findings before the screenshot: Playwright's screenshot injects a style tag,
    # which a strict CSP rightly refuses, and WebKit logs that as a console error.
    seen = {"errors": list(errors), "failed": list(failed), "thirdParty": sorted(third)}
    shot = out / f"{engine}-{'x'.join(map(str, size))}-{mode}.png"
    page.screenshot(path=str(shot), full_page=True)
    browser.close()
    return {**info, **seen, "shot": shot.name}


def main():
    url, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    report = {"url": url, "lighthouse": {p: lighthouse(url, out, p) for p in ("mobile", "desktop")}, "runs": {}}
    with sync_playwright() as pw:
        for engine in ("chromium", "webkit"):
            for sname, size in SIZES.items():
                for mode in MODES:
                    key = f"{engine}/{sname}/{mode}"
                    try:
                        report["runs"][key] = browser_run(pw, engine, url, size, mode, out)
                    except Exception as e:  # report it, keep going
                        report["runs"][key] = {"crash": str(e)}
    problems = []
    # Pages serves every non-production URL with x-robots-tag: noindex, which fails Lighthouse's
    # is-crawlable audit. Score SEO without that audit off production so a preview is judged fairly.
    for preset, s in report["lighthouse"].items():
        path = out / f"lighthouse-{preset}.json"
        if "error" in s or not path.exists():
            continue
        data = json.loads(path.read_text())
        if data["audits"]["is-crawlable"]["score"] == 0 and ".pages.dev" in url:
            refs = [r for r in data["categories"]["seo"]["auditRefs"] if r["weight"] and r["id"] != "is-crawlable"]
            got = sum(r["weight"] * (data["audits"][r["id"]]["score"] or 0) for r in refs)
            s["seo"] = round(100 * got / sum(r["weight"] for r in refs))
            s["seo_note"] = "preview noindex excluded"
    for key, r in report["runs"].items():
        if "crash" in r:
            problems.append(f"{key}: crashed: {r['crash']}")
            continue
        if r["overflow"] > 0:
            problems.append(f"{key}: horizontal overflow {r['overflow']}px")
        if r["textChars"] < 200:
            problems.append(f"{key}: page text missing ({r['textChars']} chars)")
        if not r["footer"]:
            problems.append(f"{key}: no Bad Omen footer")
        if r["errors"]:
            problems.append(f"{key}: console errors {r['errors'][:3]}")
        if r["failed"]:
            problems.append(f"{key}: failed requests {r['failed'][:3]}")
        if r["thirdParty"]:
            problems.append(f"{key}: third-party requests {r['thirdParty'][:3]}")
        if key.endswith("/reduced") and r["animations"]:
            problems.append(f"{key}: {r['animations']} animations still running under reduced motion")
    for preset, s in report["lighthouse"].items():
        if "error" in s:
            problems.append(f"lighthouse {preset}: {s['error']}")
            continue
        for cat in ("performance", "accessibility", "best-practices", "seo"):
            if s.get(cat, 0) < 90:
                problems.append(f"lighthouse {preset}: {cat} {s.get(cat)}")
    report["problems"] = problems
    (out / "report.json").write_text(json.dumps(report, indent=2))
    lines = [f"# Site check: {url}", "", "## Lighthouse", ""]
    for preset, s in report["lighthouse"].items():
        lines.append(f"- {preset}: " + ", ".join(f"{k} {v}" for k, v in s.items()))
    lines += ["", "## Browsers (overflow px / text chars / footer / errors / 3rd party / running animations)", ""]
    for key, r in report["runs"].items():
        lines.append(f"- {key}: " + ("CRASH " + r["crash"] if "crash" in r else
                     f"{r['overflow']} / {r['textChars']} / {r['footer']} / {len(r['errors'])} / "
                     f"{len(r['thirdParty'])} / {r['animations']}"))
    lines += ["", "## Problems", ""] + ([f"- {p}" for p in problems] or ["- none"])
    (out / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
