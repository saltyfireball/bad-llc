// Run from the repo root: node --test tests/
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const zlib = require("node:zlib");
const Core = require("../public/kit/v1/portrait-core.js");
const { cassandra, carrie } = require("./fixtures.js");

const DT = 1 / 30;
const KIT = path.join(__dirname, "..", "public", "kit", "v1");

// A small seeded random, so a run is the same every time.
function seeded(seed) {
  let s = seed;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

// Drives a player on a fake clock and plays the part of the page: when the core says play a clip,
// the "video" ends after the manifest duration. Records every clip start and blink.
function rig(manifest, rand) {
  const core = Core.create(manifest, { rand: rand || seeded(7) });
  const r = { core, t: 0, f: null, clips: [], blinks: [], cells: [], early: 0, id: 0, endAt: 0 };
  let prevKind = null;
  r.run = (secs) => {
    const end = r.t + secs;
    while (r.t < end) {
      r.f = core.tick(r.t);
      if (r.f.kind === "clip" && r.f.id !== r.id) {
        if (prevKind === "clip" && r.t < r.endAt) r.early++; // a clip cut short
        r.id = r.f.id;
        r.endAt = r.t + manifest.clips[r.f.name].duration;
        r.clips.push({ name: r.f.name, t: r.t, from: prevKind });
      }
      if (r.f.kind === "clip" && r.t >= r.endAt) core.ended();
      if (r.f.kind === "blink" && prevKind !== "blink") r.blinks.push({ t: r.t, from: prevKind });
      if (r.f.kind === "grid") r.cells.push([r.f.cx, r.f.cy, r.t]);
      prevKind = r.f.kind;
      r.t += DT;
    }
    return r;
  };
  return r;
}

// Run until the test is true (a bounded wait, so a bug fails instead of hanging).
function until(r, pred, max) {
  const end = r.t + (max || 60);
  while (!pred(r)) { if (r.t > end) assert.fail("timed out waiting"); r.run(DT); }
  return r;
}
// Keep the pointer moving at (u, v) for secs, as a real cursor reports every frame.
function follow(r, u, v, secs) {
  const end = r.t + secs;
  while (r.t < end) { r.core.pointer(u, v); r.run(DT); }
  return r;
}
// An idle pass that has just started.
const freshIdle = (r) => until(r, (x) => x.f.name === "idle" && x.t - x.clips[x.clips.length - 1].t < 2 * DT);

const actions = (r, m) => r.clips.filter((c) => m.behaviour.idles.includes(c.name));

test("the intro plays first, then the idle loop", () => {
  const r = rig(cassandra()).run(0.1);
  assert.equal(r.f.kind, "clip");
  assert.equal(r.f.name, "wave");
  r.run(3.5);
  assert.equal(r.f.name, "idle");
  assert.deepEqual(r.clips.map((c) => c.name).slice(0, 2), ["wave", "idle"]);
});

test("no intro in the manifest means the idle clip from the start", () => {
  const r = rig(carrie()).run(0.1);
  assert.equal(r.f.name, "idle");
});

test("the idle loop restarts under a new id at each pass", () => {
  const r = rig(carrie(), () => 0).run(0.1);
  const first = r.f.id;
  r.run(4.5);
  assert.equal(r.f.name, "idle");
  assert.notEqual(r.f.id, first);
});

test("idles are never the same twice in a row, and come within every [lo, hi]", () => {
  const m = cassandra();
  for (const seed of [1, 2, 3, 4, 5]) {
    const r = rig(m, seeded(seed)).run(900);
    const idles = actions(r, m);
    assert.ok(idles.length > 20, "enough idles in fifteen minutes");
    for (let i = 1; i < idles.length; i++) {
      assert.notEqual(idles[i].name, idles[i - 1].name);
      const gap = idles[i].t - idles[i - 1].t;
      assert.ok(gap >= m.behaviour.every[0] - DT, "not sooner than lo: " + gap);
      // up to hi, plus the wait for the seam (one idle pass) and a blink in front of it
      assert.ok(gap <= m.behaviour.every[1] + m.clips.idle.duration + 1, "not later than hi: " + gap);
    }
  }
});

test("idles and blinks start only at the idle seam", () => {
  const m = cassandra();
  const r = rig(m, seeded(3)).run(300);
  assert.ok(r.blinks.length > 20);
  assert.equal(r.early, 0, "no clip is ever cut short by the next one");
  for (const c of actions(r, m)) assert.ok(["clip", "blink"].includes(c.from), "an idle follows a clip end or a blink: " + c.from);
  for (const b of r.blinks) assert.ok(["clip", "blink"].includes(b.from), "a blink follows a clip end: " + b.from);
});

test("blinks come within blinkEvery of each other, in the idle loop", () => {
  const m = cassandra();
  m.behaviour.idles = [];
  m.behaviour.intro = null;
  const r = rig(m, seeded(5)).run(300);
  assert.ok(r.blinks.length > 30);
  for (let i = 1; i < r.blinks.length; i++) {
    const gap = r.blinks[i].t - r.blinks[i - 1].t;
    assert.ok(gap >= m.behaviour.blinkEvery[0] - DT, "not sooner than lo: " + gap);
    assert.ok(gap <= m.behaviour.blinkEvery[1] + m.clips.idle.duration + 1, "not later than hi + a pass: " + gap);
  }
});

test("a blink draws the blink atlas frames in order, then ends", () => {
  const r = rig(cassandra(), () => 0);
  const seen = [];
  until(r, (x) => { x.run(DT); if (x.f.kind === "blink" && !seen.includes(x.f.key)) seen.push(x.f.key); return seen.length && x.f.kind !== "blink"; });
  assert.ok(seen.length >= 3 && seen[0] === "blink0", seen.join());
  assert.deepEqual(seen, seen.slice().sort(), "frames in order");
  assert.equal(r.f.kind, "clip");
});

test("a poke plays the poke clip, and the cooldown ignores the next one", () => {
  const r = rig(cassandra(), () => 0.99).run(6); // intro done
  r.clips.length = 0;
  assert.equal(r.core.poke(), true);
  assert.equal(r.core.poke(), false, "inside the cooldown");
  r.run(8);
  assert.equal(r.clips.filter((s) => s.name === "wave").length, 1);
  r.run(2);
  assert.equal(r.core.poke(), true, "after the cooldown");
});

test("a poke waits for the end of the idle pass", () => {
  const r = freshIdle(rig(cassandra(), () => 0.99).run(0.1));
  r.run(0.5);
  const id = r.f.id;
  r.core.poke();
  r.run(1);
  assert.equal(r.f.id, id, "the idle pass is not cut short");
  r.run(4);
  assert.equal(r.f.name, "wave");
});

test("Carrie never plays a wave, her poke is the glance", () => {
  const r = rig(carrie(), seeded(9));
  for (let i = 0; i < 40; i++) { r.core.poke(); r.run(15); }
  assert.ok(r.clips.length > 10);
  assert.equal(r.clips.filter((s) => s.name === "wave").length, 0);
  assert.ok(r.clips.some((s) => s.name === "glance"));
});

test("the grid steps one cell at a time toward the pointer, at a few cells a second", () => {
  const r = rig(cassandra(), () => 0.5).run(8); // past the intro, mid idle
  follow(r, 0.6, -0.6, 12); // far right and up: the corner cell
  assert.equal(r.f.kind, "grid");
  assert.deepEqual([r.f.cx, r.f.cy], [4, 0]);
  const cells = r.cells;
  for (let i = 1; i < cells.length; i++) {
    assert.ok(Math.abs(cells[i][0] - cells[i - 1][0]) <= 1 && Math.abs(cells[i][1] - cells[i - 1][1]) <= 1);
  }
  const steps = cells.filter((c, i) => i && (c[0] !== cells[i - 1][0] || c[1] !== cells[i - 1][1]));
  assert.ok(steps.length >= 2);
  assert.ok(steps[1][2] - steps[0][2] > 0.1, "not one cell per frame");
  assert.ok(steps[1][2] - steps[0][2] < 0.25, "about six cells a second");
});

test("following holds at the seam: the idle pass finishes, then the grid runs", () => {
  const r = freshIdle(rig(cassandra(), () => 0.5).run(0.1));
  r.run(0.5);
  const id = r.f.id;
  follow(r, -0.6, 0, 1);
  assert.equal(r.f.id, id, "still the same idle pass");
  assert.equal(r.f.kind, "clip");
  follow(r, -0.6, 0, 4);
  assert.equal(r.f.kind, "grid");
});

test("with no movement she recentres, then the idle clip resumes", () => {
  const r = rig(cassandra(), () => 0.5).run(8);
  follow(r, -0.6, 0, 14);
  assert.equal(r.f.kind, "grid");
  assert.equal(r.f.cx, 0);
  until(r, (x) => x.f.kind !== "grid", 10);
  assert.equal(r.f.kind, "clip", "back to the idle loop (or a due clip)");
  const [lx, ly] = r.cells[r.cells.length - 1];
  assert.ok(Math.abs(lx - 2) <= 1 && Math.abs(ly - 1) <= 1, "left from beside the centre cell");
});

test("she recentres before a clip plays", () => {
  const r = rig(cassandra(), () => 0.5).run(8);
  follow(r, 0.6, 0.6, 14);
  assert.deepEqual([r.f.cx, r.f.cy], [4, 2]);
  r.core.poke();
  const seen = [];
  const t0 = r.t;
  while (r.f.kind !== "clip" && r.t < t0 + 5) { r.run(DT); if (r.f.kind === "grid") seen.push([r.f.cx, r.f.cy]); }
  assert.equal(r.f.name, "wave");
  const [lx, ly] = seen[seen.length - 1];
  assert.ok(Math.abs(lx - 2) <= 1 && Math.abs(ly - 1) <= 1, "the clip starts from beside the centre cell");
  for (let i = 1; i < seen.length; i++) {
    assert.ok(Math.abs(seen[i][0] - seen[i - 1][0]) <= 1 && Math.abs(seen[i][1] - seen[i - 1][1]) <= 1);
  }
});

test("while following, a blink shows the closed cell", () => {
  const r = rig(cassandra(), () => 0).run(3);
  let closed = 0, open = 0;
  for (let i = 0; i < 900; i++) { r.core.pointer(0.6, 0); r.run(DT); if (r.f.kind === "grid") r.f.closed ? closed++ : open++; }
  assert.ok(closed > 0 && open > closed);
});

test("a touch tap looks gently toward the tap, then returns", () => {
  const r = rig(cassandra(), () => 0.5).run(0.1);
  r.core.poke(); // the poke after the intro; its cooldown then covers the tap
  until(r, (x) => x.clips.length >= 3 && x.f.name === "idle");
  assert.ok(r.t < 6);
  r.core.tap(0.6, -0.6);
  until(r, (x) => x.f.kind === "grid", 10);
  r.run(0.8);
  assert.equal(r.f.kind, "grid");
  assert.deepEqual([r.f.cx, r.f.cy], [3, 0], "only one cell off centre");
  r.run(6);
  assert.notEqual(r.f.kind, "grid");
});

test("a failed clip drops clips: the still, with blinks and the grid", () => {
  const r = rig(cassandra(), () => 0).run(0.1);
  assert.equal(r.f.name, "wave");
  r.core.drop();
  r.clips.length = 0;
  r.run(60);
  assert.equal(r.clips.length, 0, "no clip ever starts again");
  assert.ok(r.blinks.length >= 8, "blinks go on");
  assert.equal(r.core.poke(), false, "a poke has no clip to play");
  assert.equal(r.f.kind === "rest" || r.f.kind === "blink", true);
  r.core.pointer(0.6, 0);
  r.run(2);
  assert.equal(r.f.kind, "grid");
  r.run(8);
  assert.equal(r.f.kind === "rest" || r.f.kind === "blink", true);
});

test("a clip that never ends is given up on after its duration plus a margin", () => {
  const core = Core.create(cassandra(), { rand: () => 0 });
  let f;
  for (let t = 0; t < 30; t += DT) f = core.tick(t); // nobody calls ended()
  assert.notEqual(f.id, 1);
});

test("pause and resume leave no time jump", () => {
  const a = rig(cassandra(), () => 0.5).run(3);
  const b = rig(cassandra(), () => 0.5).run(3);
  a.core.pause();
  assert.equal(a.core.tick(a.t + 50).key, a.f.key, "paused: the frame holds");
  a.core.resume(10000);
  a.t = 10000 + DT;
  a.id = 0; // the page replays nothing: only compare what the core says
  a.run(2);
  b.run(2);
  assert.equal(a.f.key, b.f.key, "same state as the player that never paused");
});

test("a long gap between ticks is clamped", () => {
  const r = rig(cassandra(), () => 0.5).run(3);
  const before = r.f;
  const after = r.core.tick(r.t + 3600);
  assert.equal(after.key, before.key);
});

// ---- the page part, with a fake DOM: reduced motion and no-JS paths touch nothing ----

async function page(reduced) {
  const calls = { fetch: 0 };
  const fig = {
    getAttribute: () => "portrait/manifest.json",
    querySelector: () => ({ alt: "x" }),
  };
  const win = {
    BOPortraitCore: Core, fetch: () => { calls.fetch++; return Promise.reject(new Error("no")); },
    matchMedia: () => ({ matches: reduced, addEventListener() {} }),
    requestIdleCallback: (f) => f(), cancelAnimationFrame() {}, addEventListener() {}, devicePixelRatio: 1,
  };
  const doc = { readyState: "complete", baseURI: "http://localhost/", querySelectorAll: () => [fig] };
  vm.runInNewContext(fs.readFileSync(path.join(KIT, "portrait.js"), "utf8"), { window: win, document: doc, fetch: win.fetch, cancelAnimationFrame() {}, URL, Array, Promise, Image: function () {} });
  await new Promise((ok) => setImmediate(ok));
  return calls;
}

test("reduced motion fetches nothing and leaves the still", async () => {
  assert.equal((await page(true)).fetch, 0);
});

test("without reduced motion the page part starts by fetching the manifest", async () => {
  assert.equal((await page(false)).fetch, 1);
});

// ---- manifest validation ----

test("a good manifest validates", () => {
  assert.equal(Core.validate(cassandra()), null);
  assert.equal(Core.validate(carrie()), null);
});

test("bad manifests are refused, so the still stays", () => {
  const cases = {
    "not an object": () => null,
    "version 2": (m) => { m.version = 2; },
    "no version": (m) => { delete m.version; },
    "no width": (m) => { delete m.width; },
    "no still": (m) => { delete m.still; },
    "still without 2x": (m) => { delete m.still[2]; },
    "no clips": (m) => { delete m.clips; },
    "no idle clip": (m) => { delete m.clips.idle; },
    "clip without src": (m) => { delete m.clips.wave.src; },
    "clip with no duration": (m) => { m.clips.wave.duration = 0; },
    "no blink atlas": (m) => { delete m.atlases.blink; },
    "no grid atlas": (m) => { delete m.atlases.grid; },
    "atlas without 2x": (m) => { delete m.atlases.blink.files[2]; },
    "atlas without size": (m) => { delete m.atlases.grid.width; },
    "no blink": (m) => { delete m.blink; },
    "blink fps zero": (m) => { m.blink.fps = 0; },
    "blink without frames": (m) => { m.blink.frames = []; },
    "blink names a missing atlas": (m) => { m.blink.atlas = "nope"; },
    "no grid": (m) => { delete m.grid; },
    "no behaviour": (m) => { delete m.behaviour; },
    "bad every": (m) => { m.behaviour.every = [20, 8]; },
    "bad blinkEvery": (m) => { m.behaviour.blinkEvery = [1]; },
    "intro names a missing clip": (m) => { m.behaviour.intro = "nope"; },
    "poke names a missing clip": (m) => { m.behaviour.poke = "nope"; },
    "idle names a missing clip": (m) => { m.behaviour.idles.push("nope"); },
    "idles is not a list": (m) => { m.behaviour.idles = "glance"; },
    "blink rect outside the atlas": (m) => { m.blink.frames[1] = [190, 0, 20, 8, 10, 10]; },
    "blink rect outside the portrait": (m) => { m.blink.frames[1] = [0, 0, 8, 8, 95, 10]; },
    "rect with a negative origin": (m) => { m.grid.frames[3] = [-1, 0, 8, 8, 10, 10]; },
    "rect of the wrong length": (m) => { m.grid.frames[3] = [0, 0, 8, 8, 10]; },
    "rect with no area": (m) => { m.grid.frames[3] = [0, 0, 0, 8, 10, 10]; },
    "rect is not numbers": (m) => { m.grid.frames[3] = ["0", 0, 8, 8, 10, 10]; },
    "grid with the wrong cell count": (m) => { m.grid.frames.pop(); },
    "closed with the wrong cell count": (m) => { m.grid.closed.pop(); },
    "no closed cells": (m) => { delete m.grid.closed; },
    "grid without yaw": (m) => { m.grid.yaw = []; },
  };
  for (const [what, edit] of Object.entries(cases)) {
    const m = cassandra();
    const r = edit(m);
    assert.notEqual(Core.validate(r === null ? null : m), null, what);
  }
});

test("unsafe file names are refused everywhere", () => {
  const bad = ["../x.mp4", "a/../b.mp4", "/etc/passwd", "https://elsewhere.example/a.mp4", "//host/a.mp4", "a/b.mp4", "..", "x..y.mp4", "", "data:video/mp4;base64,AAAA", "a\\b.mp4"];
  const spots = {
    "still 1x": (m, s) => { m.still[1] = s; },
    "still 2x": (m, s) => { m.still[2] = s; },
    "clip src": (m, s) => { m.clips.idle.src = s; },
    "blink atlas": (m, s) => { m.atlases.blink.files[1] = s; },
    "grid atlas 2x": (m, s) => { m.atlases.grid.files[2] = s; },
  };
  for (const [where, put] of Object.entries(spots)) {
    for (const s of bad) {
      const m = cassandra();
      put(m, s);
      assert.notEqual(Core.validate(m), null, where + ": " + JSON.stringify(s));
    }
  }
});

// ---- the demo bake stays valid ----

test("the demo manifest validates and every file it names exists", () => {
  const dir = path.join(KIT, "portrait-demo", "portrait");
  const m = JSON.parse(fs.readFileSync(path.join(dir, "manifest.json"), "utf8"));
  assert.equal(Core.validate(m), null);
  const names = [...Object.values(m.still), ...Object.values(m.clips).map((c) => c.src)];
  for (const a of Object.values(m.atlases)) names.push(...Object.values(a.files));
  for (const n of names) assert.ok(fs.existsSync(path.join(dir, n)), n);
  const total = fs.readdirSync(path.join(KIT, "portrait-demo"), { recursive: true })
    .reduce((s, f) => { const p = path.join(KIT, "portrait-demo", f); return s + (fs.statSync(p).isFile() ? fs.statSync(p).size : 0); }, 0);
  assert.ok(total < 150 * 1024, "demo folder is " + total + " bytes");
});

// ---- size budget ----

test("the player stays under 6 KB gzipped, core and page part together", () => {
  const code = ["portrait-core.js", "portrait.js"].map((f) => fs.readFileSync(path.join(KIT, f)));
  const size = zlib.gzipSync(Buffer.concat(code), { level: 9 }).length;
  assert.ok(size < 6 * 1024, "gzipped " + size + " bytes");
});

test("every kit player file is ASCII", () => {
  for (const f of ["portrait-core.js", "portrait.js", "portrait.css"]) {
    assert.ok(!/[^\x00-\x7f]/.test(fs.readFileSync(path.join(KIT, f), "utf8")), f);
  }
});
