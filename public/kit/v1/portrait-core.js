/* Bad Omen kit v1: living portrait, the state machine. Plain JS, no DOM, no dependencies.
   It reads a bake manifest (docs: "Bake format (manifest v1)") and says which frame to show.
   portrait.js draws it; tests/ drive it with a fake clock and a fake random. ASCII only. */
(function (root, make) {
  var api = make();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.BOPortraitCore = api;
})(this, function () {
  var STEP = 1 / 6,      // the pose grid moves one cell every 1/6 s
    HOME = 2,            // seconds without pointer movement before she looks back at you
    TAP = 1.2,           // how long a touch tap holds her gaze
    COOL = 6,            // seconds between pokes
    SHUT = 0.15;         // a blink while following: the closed cell for this long

  // ---- manifest check: any complaint means the player keeps the still ----
  function need(ok, what) { if (!ok) throw new Error(what); }
  function num(v) { return typeof v === "number" && isFinite(v); }
  function file(s) { return typeof s === "string" && /^[\w@][\w@.-]*$/.test(s); }
  function pair(p) { return Array.isArray(p) && num(p[0]) && num(p[1]) && p[0] >= 0 && p[0] <= p[1]; }

  function frames(m, list, atlas, what) {
    var a = m.atlases[atlas];
    need(a, what + ": no atlas");
    need(Array.isArray(list) && list.length, what + ": no frames");
    list.forEach(function (f) {
      need(f && typeof f === "object", what + ": bad frame");
      m.layers.forEach(function (l) {
        var r = f[l];
        if (r == null) return; // same as rest
        need(Array.isArray(r) && r.length === 6 && r.every(num) &&
          r[0] >= 0 && r[1] >= 0 && r[4] >= 0 && r[5] >= 0 && r[2] > 0 && r[3] > 0 &&
          r[0] + r[2] <= a.width && r[1] + r[3] <= a.height &&
          r[4] + r[2] <= m.width && r[5] + r[3] <= m.height, what + ": rect outside");
      });
    });
  }

  function check(m) {
    need(m && m.version === 1, "version");
    need(num(m.width) && num(m.height) && m.width > 0 && m.height > 0, "size");
    var D = m.densities, L = m.layers, A = m.atlases, B = m.behaviour, G = m.grid;
    need(Array.isArray(D) && D.indexOf(1) >= 0, "densities");
    need(Array.isArray(L) && L.length && L.every(file), "layers");
    need(m.still && D.every(function (d) { return file(m.still[d]); }), "still");
    need(A && typeof A === "object", "atlases");
    Object.keys(A).forEach(function (k) {
      need(num(A[k].width) && num(A[k].height) && A[k].files, "atlas " + k);
      L.forEach(function (l) {
        D.forEach(function (d) { need(A[k].files[l] && file(A[k].files[l][d]), "atlas " + k + " file"); });
      });
    });
    need(m.actions && m.actions.idle, "no idle");
    Object.keys(m.actions).forEach(function (k) {
      var a = m.actions[k];
      need(num(a.fps) && a.fps > 0, k + ": fps");
      frames(m, a.frames, a.atlas, k);
    });
    need(B && pair(B.every) && pair(B.blinkEvery) && Array.isArray(B.idles), "behaviour");
    B.idles.concat(B.intro || [], B.poke || []).forEach(function (n) { need(m.actions[n], "no action " + n); });
    if (B.grid) {
      need(G && Array.isArray(G.yaw) && Array.isArray(G.pitch) && G.yaw.length && G.pitch.length, "grid");
      var n = G.yaw.length * G.pitch.length;
      frames(m, G.frames, G.atlas, "grid");
      need(G.frames.length === n, "grid: cell count");
      if (G.closed) { frames(m, G.closed, G.atlas, "grid closed"); need(G.closed.length === n, "grid: closed count"); }
    }
  }

  function validate(m) {
    try { check(m); return null; } catch (e) { return e.message; }
  }

  // ---- the player: tick(seconds) in, a frame out ----
  // o.rand: () => [0,1). The clock is whatever you pass to tick/resume, in seconds.
  function create(m, o) {
    var rnd = (o && o.rand) || Math.random, b = m.behaviour, A = m.actions,
      G = b.grid && m.grid, cx0, cy0;
    var clock = 0, last = null, paused = false, cur = null, mode = "loop", // loop, act or grid
      loopT = 0, seam = true, act = null, introQ = !!b.intro, pokeQ = false, pokeOK = 0,
      lastIdle = null, nextIdle = span(b.every), nextBlink = span(b.blinkEvery),
      cx, cy, tx, ty, acc = 0, moved = -HOME, shut = 0;
    if (G) { cx0 = (G.yaw.length - 1) >> 1; cy0 = (G.pitch.length - 1) >> 1; cx = tx = cx0; cy = ty = cy0; }
    if (!b.idles.length) nextIdle = Infinity;

    function span(r) { return r[0] + (r[1] - r[0]) * rnd(); }
    function sign(v) { return v > 0 ? 1 : v < 0 ? -1 : 0; }
    function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
    function due() { return introQ || pokeQ || clock >= nextIdle; }
    function play(n) { mode = "act"; act = { n: n, t: 0 }; }

    // The next action to play, or null. Intro first, then a poke, then an idle that is never
    // the one we just played.
    function take() {
      var n = null, ids;
      if (introQ) { introQ = false; n = b.intro; }
      else if (pokeQ) { pokeQ = false; n = b.poke; }
      else if (clock >= nextIdle) {
        ids = b.idles.filter(function (i) { return i !== lastIdle; });
        if (!ids.length) ids = b.idles;
        n = lastIdle = ids[Math.floor(rnd() * ids.length)];
        nextIdle = clock + span(b.every);
      }
      return n;
    }

    // Pointer offset from the portrait centre, in portrait sizes (u across, v down), to a cell.
    function aim(u, v, gentle) {
      var x = Math.round(cx0 + clamp(u / 0.6, -1, 1) * cx0), y = Math.round(cy0 + clamp(v / 0.6, -1, 1) * cy0);
      if (gentle) { x = clamp(x, cx0 - 1, cx0 + 1); y = clamp(y, cy0 - 1, cy0 + 1); }
      tx = x; ty = y;
      if (mode === "loop" && (x !== cx0 || y !== cy0)) enter();
    }
    function enter() { mode = "grid"; cx = cx0; cy = cy0; acc = 0; shut = 0; }

    function stepGrid(dt) {
      var d = due();
      if (clock - moved > HOME || d) { tx = cx0; ty = cy0; }
      acc = Math.min(acc + dt, STEP);
      if (acc >= STEP && (cx !== tx || cy !== ty)) { acc -= STEP; cx += sign(tx - cx); cy += sign(ty - cy); }
      if (cx === cx0 && cy === cy0) {
        if (d) return play(take());
        if (clock - moved > HOME) { mode = "loop"; loopT = 0; seam = true; return; }
      }
      if (!d && G.closed && clock >= nextBlink) { shut = clock + SHUT; nextBlink = clock + span(b.blinkEvery); }
    }

    // The idle loop. Anything that is due waits for the seam, where every action joins.
    function stepLoop(dt) {
      var a = A.idle, x;
      loopT += dt;
      if (loopT * a.fps >= a.frames.length) { loopT -= a.frames.length / a.fps; seam = true; }
      if (!seam) return;
      seam = false;
      if ((x = take())) play(x);
      else if (A.blink && clock >= nextBlink) { play("blink"); nextBlink = clock + span(b.blinkEvery); }
    }

    function out() {
      var a, i, list, k;
      if (mode === "act") {
        a = A[act.n];
        i = Math.min(Math.floor(act.t * a.fps), a.frames.length - 1);
        return { key: act.n + ":" + i, name: act.n, i: i, atlas: a.atlas, frame: a.frames[i] };
      }
      if (mode === "grid") {
        k = clock < shut;
        i = cy * G.yaw.length + cx;
        list = k ? G.closed : G.frames;
        return { key: "grid" + (k ? "c" : "") + i, name: "grid", i: i, cx: cx, cy: cy, closed: k, atlas: G.atlas, frame: list[i] };
      }
      a = A.idle;
      i = Math.min(Math.floor(loopT * a.fps), a.frames.length - 1);
      return { key: "idle:" + i, name: "idle", i: i, atlas: a.atlas, frame: a.frames[i] };
    }

    return {
      tick: function (t) {
        var dt = last == null ? 0 : clamp(t - last, 0, 0.25); // a long gap is never a jump
        last = t;
        if (paused && cur) return cur;
        clock += dt;
        if (mode === "act") {
          act.t += dt;
          if (act.t * A[act.n].fps >= A[act.n].frames.length) {
            act = null; seam = true; loopT = 0; mode = "loop";
            if (G && clock - moved < HOME && (tx !== cx0 || ty !== cy0)) enter();
          }
        }
        if (mode === "grid") stepGrid(dt);
        if (mode === "loop") stepLoop(dt);
        return (cur = out());
      },
      pause: function () { paused = true; },
      resume: function (t) { paused = false; last = t; }, // the next tick sees no gap
      // Pointer moved over the page: u, v are its offset from the portrait centre in portrait sizes.
      pointer: function (u, v) { if (G) { moved = clock; aim(u, v); } },
      // pointerenter or a click. False when the cooldown (or the persona) says no.
      poke: function () {
        if (!b.poke || clock < pokeOK) return false;
        pokeQ = true; pokeOK = clock + COOL;
        return true;
      },
      // A touch tap pokes when it can, else looks gently toward the tap, then returns.
      tap: function (u, v) {
        if (this.poke() || !G) return;
        moved = clock - HOME + TAP; aim(u, v, true);
      }
    };
  }

  return { validate: validate, create: create };
});
