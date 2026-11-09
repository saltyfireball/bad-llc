// Run from the repo root: node --test tests/
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const zlib = require("node:zlib");
const Core = require("../public/kit/v1/portrait-core.js");
const { cassandra, carrie } = require("./fixtures.js");

const DT = 1 / 30;

// A small seeded random, so a run is the same every time.
function seeded(seed) {
  let s = seed;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

// Drives a player on a fake clock. Records every action that starts.
function rig(manifest, rand) {
  const core = Core.create(manifest, { rand: rand || seeded(7) });
  const r = { core, t: 0, f: null, starts: [], cells: [] };
  let prev = null;
  r.run = (secs) => {
    const end = r.t + secs;
    while (r.t < end) {
      r.f = core.tick(r.t);
      if (r.f.name !== "idle" && r.f.name !== "grid" && (!prev || prev.name !== r.f.name || r.f.i < prev.i)) {
        r.starts.push({ name: r.f.name, t: r.t });
      }
      if (r.f.name === "grid") r.cells.push([r.f.cx, r.f.cy, r.t]);
      prev = r.f;
      r.t += DT;
    }
    return r;
  };
  return r;
}

test("intro plays first, then the idle loop", () => {
  const r = rig(cassandra()).run(0.1);
  assert.equal(r.f.name, "wave");
  r.run(1.5);
  assert.equal(r.f.name, "idle");
});

test("no intro in the manifest means the idle loop from the start", () => {
  const r = rig(carrie()).run(0.1);
  assert.equal(r.f.name, "idle");
});

test("an idle is never the same twice in a row, and the timing window holds", () => {
  const m = cassandra();
  for (const seed of [1, 2, 3, 4, 5]) {
    const r = rig(m, seeded(seed)).run(600);
    const idles = r.starts.filter((s) => m.behaviour.idles.includes(s.name));
    assert.ok(idles.length > 20, "enough idles in ten minutes");
    const loop = m.actions.idle.frames.length / m.actions.idle.fps;
    for (let i = 1; i < idles.length; i++) {
      assert.notEqual(idles[i].name, idles[i - 1].name);
      const gap = idles[i].t - idles[i - 1].t;
      assert.ok(gap >= m.behaviour.every[0] - DT, "not sooner than min: " + gap);
      // up to max, plus the wait for the seam and a blink or the action in front of it
      assert.ok(gap <= m.behaviour.every[1] + loop + 1, "not later than max: " + gap);
    }
  }
});

test("blinks play only at the loop seam", () => {
  const m = cassandra();
  const r = rig(m, seeded(3)).run(120);
  const blinks = r.starts.filter((s) => s.name === "blink");
  assert.ok(blinks.length > 5);
  // The loop restarts at the end of every action, so a blink may only start on a seam:
  // check every frame instead. A blink's first frame follows an idle frame 0 or an action end.
  const core = Core.create(m, { rand: seeded(3) });
  let prev = null, bad = 0;
  for (let t = 0; t < 120; t += DT) {
    const f = core.tick(t);
    if (f.name === "blink" && f.i === 0 && prev && prev.name === "idle") {
      const last = m.actions.idle.frames.length - 1;
      // the previous idle frame was the final one (the loop wrapped) or the loop had just started
      if (!(prev.i >= last - 1 || prev.i <= 1)) bad++;
    }
    prev = f;
  }
  assert.equal(bad, 0);
});

test("a poke plays the wave, and the cooldown ignores the next one", () => {
  const r = rig(cassandra(), () => 0.99).run(5); // intro done
  r.starts.length = 0;
  assert.equal(r.core.poke(), true);
  assert.equal(r.core.poke(), false, "inside the cooldown");
  r.run(4);
  assert.equal(r.starts.filter((s) => s.name === "wave").length, 1);
  r.run(4);
  assert.equal(r.core.poke(), true, "after the cooldown");
});

test("Carrie never plays a wave", () => {
  const r = rig(carrie(), seeded(9));
  for (let i = 0; i < 40; i++) { r.core.poke(); r.run(15); }
  assert.ok(r.starts.length > 10);
  assert.equal(r.starts.filter((s) => s.name === "wave").length, 0);
  assert.ok(r.starts.some((s) => s.name === "glance"), "her poke is the glance");
});

test("the grid steps one cell at a time toward the pointer, and keeps its eyes on it", () => {
  const r = rig(cassandra(), () => 0.5).run(3); // past the intro, mid loop
  r.core.pointer(0.6, -0.6); // far right and up: the corner cell
  r.run(1.5);
  assert.equal(r.f.name, "grid");
  assert.deepEqual([r.f.cx, r.f.cy], [4, 0]);
  const cells = r.cells;
  for (let i = 1; i < cells.length; i++) {
    assert.ok(Math.abs(cells[i][0] - cells[i - 1][0]) <= 1 && Math.abs(cells[i][1] - cells[i - 1][1]) <= 1);
  }
  const steps = cells.filter((c, i) => i && (c[0] !== cells[i - 1][0] || c[1] !== cells[i - 1][1]));
  assert.ok(steps.length >= 2);
  assert.ok(steps[1][2] - steps[0][2] > 0.1, "a few cells per second, not one per frame");
});

test("with no movement she goes back to the centre and the idle loop", () => {
  const r = rig(cassandra(), () => 0.5).run(3);
  r.core.pointer(-0.6, 0);
  r.run(1);
  assert.equal(r.f.name, "grid");
  r.run(4);
  assert.equal(r.f.name, "idle");
});

test("she recentres before an action plays", () => {
  const r = rig(cassandra(), () => 0.5).run(3);
  r.core.pointer(0.6, 0.6);
  r.run(1.5);
  assert.deepEqual([r.f.cx, r.f.cy], [4, 2]);
  r.core.poke();
  let seen = [];
  const t0 = r.t;
  while (r.f.name !== "wave" && r.t < t0 + 3) { r.run(DT); if (r.f.name === "grid") seen.push([r.f.cx, r.f.cy]); }
  assert.equal(r.f.name, "wave");
  // The wave's first frame is the rest pose, the centre cell, so the centre never shows twice.
  const lastSeen = seen[seen.length - 1];
  assert.ok(Math.abs(lastSeen[0] - 2) <= 1 && Math.abs(lastSeen[1] - 1) <= 1, "one cell from the centre");
  for (let i = 1; i < seen.length; i++) {
    assert.ok(Math.abs(seen[i][0] - seen[i - 1][0]) <= 1 && Math.abs(seen[i][1] - seen[i - 1][1]) <= 1);
  }
});

test("while following, a blink shows the closed cell", () => {
  const r = rig(cassandra(), () => 0).run(3); // blinkEvery min = 2 s
  r.core.pointer(0.6, 0);
  let closed = 0, open = 0;
  for (let i = 0; i < 90; i++) { r.core.pointer(0.6, 0); r.run(DT); if (r.f.name === "grid") r.f.closed ? closed++ : open++; }
  assert.ok(closed > 0 && open > closed);
});

test("a touch tap looks gently toward the tap, then returns", () => {
  const r = rig(cassandra(), () => 0.5).run(3);
  r.core.poke(); r.run(5); // spend the poke so the tap has to look
  r.core.tap(0.6, -0.6);
  r.run(0.8);
  assert.equal(r.f.name, "grid");
  assert.deepEqual([r.f.cx, r.f.cy], [3, 0], "only one cell off centre");
  r.run(3);
  assert.equal(r.f.name, "idle");
});

test("pause and resume leave no time jump", () => {
  const a = rig(cassandra(), () => 0.5).run(3);
  const b = rig(cassandra(), () => 0.5).run(3);
  a.core.pause();
  assert.equal(a.core.tick(a.t + 50).key, a.f.key, "paused: the frame holds");
  a.core.resume(10000); // hours later by the clock
  const t = a.t;
  a.t = 10000 + DT;
  a.run(2);
  b.run(2);
  assert.equal(a.f.key, b.f.key, "same frame as the player that never paused");
  assert.ok(t > 0);
});

test("a long gap between ticks is clamped", () => {
  const r = rig(cassandra(), () => 0.5).run(3);
  const before = r.f;
  const after = r.core.tick(r.t + 3600);
  assert.ok(after.name === before.name || after.name === "idle" || after.name === "wave");
  assert.ok(after.i <= before.i + 8, "moved a few frames, not an hour");
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
    "no layers": (m) => { delete m.layers; },
    "no idle action": (m) => { delete m.actions.idle; },
    "no behaviour": (m) => { delete m.behaviour; },
    "bad every": (m) => { m.behaviour.every = [20, 8]; },
    "intro names a missing action": (m) => { m.behaviour.intro = "nope"; },
    "idle names a missing action": (m) => { m.behaviour.idles.push("nope"); },
    "zero fps": (m) => { m.actions.idle.fps = 0; },
    "no frames": (m) => { m.actions.idle.frames = []; },
    "action atlas missing": (m) => { m.actions.idle.atlas = "nope"; },
    "atlas file missing": (m) => { delete m.atlases.idle.files.shirt; },
    "atlas file with a path": (m) => { m.atlases.idle.files.base[1] = "../x.webp"; },
    "atlas file is a url": (m) => { m.atlases.idle.files.base[1] = "https://elsewhere.example/a.webp"; },
    "rect outside the atlas": (m) => { m.actions.idle.frames[3].base = [190, 0, 20, 8, 10, 10]; },
    "rect outside the portrait": (m) => { m.actions.idle.frames[3].base = [0, 0, 8, 8, 95, 10]; },
    "rect with a negative origin": (m) => { m.actions.idle.frames[3].base = [-1, 0, 8, 8, 10, 10]; },
    "rect of the wrong length": (m) => { m.actions.idle.frames[3].base = [0, 0, 8, 8, 10]; },
    "grid with the wrong cell count": (m) => { m.grid.frames.pop(); },
    "closed with the wrong cell count": (m) => { m.grid.closed.pop(); },
    "grid wanted but missing": (m) => { delete m.grid; },
  };
  for (const [what, edit] of Object.entries(cases)) {
    const m = cassandra();
    const r = edit(m);
    assert.notEqual(Core.validate(r === null ? null : m), null, what);
  }
});

// ---- size budget ----

test("the player stays under 6 KB gzipped, core and page part together", () => {
  const dir = path.join(__dirname, "..", "public", "kit", "v1");
  const code = ["portrait-core.js", "portrait.js"].map((f) => fs.readFileSync(path.join(dir, f)));
  const size = zlib.gzipSync(Buffer.concat(code), { level: 9 }).length;
  assert.ok(size < 6 * 1024, "gzipped " + size + " bytes");
});

test("every kit file is ASCII", () => {
  const dir = path.join(__dirname, "..", "public", "kit", "v1");
  for (const f of ["portrait-core.js", "portrait.js", "portrait.css"]) {
    assert.ok(!/[^\x00-\x7f]/.test(fs.readFileSync(path.join(dir, f), "utf8")), f);
  }
});
