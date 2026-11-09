/* Bad Omen kit v1: living portrait, the state machine. Plain JS, no DOM, no dependencies.
   It reads a bake manifest (docs: "Bake format (manifest v1)") and says what to show: a clip
   to play, or a canvas crop (blink, pose grid). portrait.js draws it; tests/ drive it with a
   fake clock and a fake random. ASCII only. */
(function (root, make) {
  var api = make();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.BOPortraitCore = api;
})(this, function () {
  var STEP = 1 / 6,      // the pose grid moves one cell every 1/6 s
    HOME = 2,            // seconds without pointer movement before she looks back at you
    TAP = 1.2,           // how long a touch tap holds her gaze
    COOL = 6,            // seconds between pokes
    SHUT = 0.15,         // a blink while following: the closed cell for this long
    LATE = 8;            // a clip with no end this long after its duration is treated as over

  // ---- manifest check: any complaint means the player keeps the still ----
  function need(ok, what) { if (!ok) throw new Error(what); }
  function num(v) { return typeof v === "number" && isFinite(v); }
  function file(s) { return typeof s === "string" && /^[\w@][\w@.-]*$/.test(s) && s.indexOf("..") < 0; }
  function pair(p) { return Array.isArray(p) && num(p[0]) && num(p[1]) && p[0] >= 0 && p[0] <= p[1]; }
  function files(f, what) {
    need(f && file(f[1]) && file(f[2]), what + ": files");
  }

  // A frame is null (same as rest) or [sx, sy, w, h, dx, dy] inside the atlas and the portrait.
  function frames(m, list, atlas, what) {
    var a = m.atlases[atlas];
    need(a, what + ": no atlas");
    need(Array.isArray(list) && list.length, what + ": no frames");
    list.forEach(function (r) {
      if (r == null) return;
      need(Array.isArray(r) && r.length === 6 && r.every(num) &&
        r[0] >= 0 && r[1] >= 0 && r[4] >= 0 && r[5] >= 0 && r[2] > 0 && r[3] > 0 &&
        r[0] + r[2] <= a.width && r[1] + r[3] <= a.height &&
        r[4] + r[2] <= m.width && r[5] + r[3] <= m.height, what + ": rect outside");
    });
  }

  function check(m) {
    need(m && m.version === 1, "version");
    need(num(m.width) && num(m.height) && m.width > 0 && m.height > 0, "size");
    var C = m.clips, A = m.atlases, B = m.behaviour, G = m.grid, K = m.blink, n;
    files(m.still, "still");
    need(C && typeof C === "object" && C.idle, "no idle clip");
    Object.keys(C).forEach(function (k) {
      need(file(C[k].src) && num(C[k].duration) && C[k].duration > 0, k + ": clip");
    });
    need(A && A.blink && A.grid, "atlases");
    Object.keys(A).forEach(function (k) {
      need(num(A[k].width) && num(A[k].height) && A[k].width > 0 && A[k].height > 0, "atlas " + k);
      files(A[k].files, "atlas " + k);
    });
    need(K && num(K.fps) && K.fps > 0, "blink: fps");
    frames(m, K.frames, K.atlas, "blink");
    need(G && Array.isArray(G.yaw) && Array.isArray(G.pitch) && G.yaw.length && G.pitch.length, "grid");
    n = G.yaw.length * G.pitch.length;
    frames(m, G.frames, G.atlas, "grid");
    frames(m, G.closed, G.atlas, "grid closed");
    need(G.frames.length === n, "grid: cell count");
    need(G.closed.length === n, "grid: closed count");
    need(B && pair(B.every) && pair(B.blinkEvery) && Array.isArray(B.idles), "behaviour");
    B.idles.concat(B.intro || [], B.poke || []).forEach(function (k) { need(C[k], "no clip " + k); });
  }

  function validate(m) {
    try { check(m); return null; } catch (e) { return e.message; }
  }

  // ---- the player ----
  // tick(seconds) says what to show: {kind, key, ...}
  //   clip: play clip `name` (`id` is new per start); the page calls ended() when it is over.
  //   blink, grid: draw `frame` ([sx,sy,w,h,dx,dy] or null) from `atlas`. rest: the still alone.
  // o.rand: () => [0,1).
  function create(m, o) {
    var rnd = (o && o.rand) || Math.random, b = m.behaviour, G = m.grid, K = m.blink,
      cx0 = (G.yaw.length - 1) >> 1, cy0 = (G.pitch.length - 1) >> 1, cx = cx0, cy = cy0, tx = cx0, ty = cy0;
    var clock = 0, last = null, paused = false, cur = null, mode = "rest", // rest, clip, blink or grid
      clips = true, act = null, ids = 0, bt = 0, introQ = !!b.intro, pokeQ = false, pokeOK = 0,
      lastIdle = null, nextIdle = b.idles.length ? span(b.every) : Infinity, nextBlink = span(b.blinkEvery),
      acc = 0, moved = -HOME, shut = 0, seamAt = 0;

    function span(r) { return r[0] + (r[1] - r[0]) * rnd(); }
    function sign(v) { return v > 0 ? 1 : v < 0 ? -1 : 0; }
    function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
    function play(n) { mode = "clip"; act = { n: n, t: 0, id: ++ids, over: false }; }

    // The next clip: intro, then a poke, then an idle that is not the last one.
    function take() {
      var n = null, pool;
      if (!clips) return n;
      if (introQ) { introQ = false; n = b.intro; }
      else if (pokeQ) { pokeQ = false; n = b.poke; }
      else if (clock >= nextIdle) {
        pool = b.idles.filter(function (i) { return i !== lastIdle; });
        if (!pool.length) pool = b.idles;
        n = lastIdle = pool[Math.floor(rnd() * pool.length)];
        nextIdle = clock + span(b.every);
      }
      return n;
    }

    // The seam: the portrait is on rest and nothing is playing. Everything starts here, in order:
    // follow the cursor, then a due clip, then a blink, else the idle loop again. A pointer that
    // moved since the last seam is looked at for at least TAP seconds, even if it has gone still.
    function seam() {
      var x;
      if (moved >= seamAt) moved = Math.max(moved, clock - HOME + TAP);
      seamAt = clock;
      if (clock - moved < HOME && (tx !== cx0 || ty !== cy0)) { mode = "grid"; cx = cx0; cy = cy0; acc = 0; shut = 0; }
      else if ((x = take())) play(x);
      else if (clock >= nextBlink) { mode = "blink"; bt = 0; nextBlink = clock + span(b.blinkEvery); }
      else if (clips) play("idle");
      else mode = "rest";
    }

    // Pointer offset from the portrait centre, in portrait sizes (u across, v down), to a cell.
    function aim(u, v, gentle) {
      var x = Math.round(cx0 + clamp(u / 0.6, -1, 1) * cx0), y = Math.round(cy0 + clamp(v / 0.6, -1, 1) * cy0);
      if (gentle) { x = clamp(x, cx0 - 1, cx0 + 1); y = clamp(y, cy0 - 1, cy0 + 1); }
      tx = x; ty = y;
    }

    function stepGrid(dt) {
      var d = clips && (introQ || pokeQ); // a poke or intro ends the follow; a due idle waits for it
      if (clock - moved > HOME || d) { tx = cx0; ty = cy0; }
      acc = Math.min(acc + dt, STEP);
      if (acc >= STEP && (cx !== tx || cy !== ty)) { acc -= STEP; cx += sign(tx - cx); cy += sign(ty - cy); }
      if (cx === cx0 && cy === cy0 && (d || clock - moved > HOME)) return seam();
      if (!d && clock >= nextBlink) { shut = clock + SHUT; nextBlink = clock + span(b.blinkEvery); }
    }

    function out() {
      var i, k, list;
      if (mode === "clip") return { kind: "clip", key: "clip" + act.id, name: act.n, id: act.id };
      if (mode === "blink") {
        i = Math.min(Math.floor(bt * K.fps), K.frames.length - 1);
        return { kind: "blink", key: "blink" + i, atlas: K.atlas, frame: K.frames[i] };
      }
      if (mode === "grid") {
        k = clock < shut;
        i = cy * G.yaw.length + cx;
        list = k ? G.closed : G.frames;
        return { kind: "grid", key: "grid" + (k ? "c" : "") + i, cx: cx, cy: cy, closed: k, atlas: G.atlas, frame: list[i] };
      }
      return { kind: "rest", key: "rest", frame: null };
    }

    return {
      tick: function (t) {
        var dt = last == null ? 0 : clamp(t - last, 0, 0.25); // a long gap is never a jump
        last = t;
        if (paused && cur) return cur;
        clock += dt;
        if (mode === "clip") {
          act.t += dt;
          if (act.over || act.t > m.clips[act.n].duration + LATE) seam();
        } else if (mode === "blink") {
          bt += dt;
          if (bt * K.fps >= K.frames.length) seam();
        } else if (mode === "grid") stepGrid(dt);
        else seam();
        return (cur = out());
      },
      // The page says the clip has finished.
      ended: function () { if (act) act.over = true; },
      // A clip failed: no more clips; the still, grid and blinks stay.
      drop: function () {
        clips = false; introQ = pokeQ = false; nextIdle = Infinity;
        if (mode === "clip") mode = "rest";
      },
      pause: function () { paused = true; },
      // The pointer left the page or the portrait went off screen: the follow ends.
      leave: function () { moved = -HOME - clock; },
      resume: function (t) { paused = false; last = t; }, // the next tick sees no gap
      // Pointer moved over the page: u, v are its offset from the portrait centre in portrait sizes.
      pointer: function (u, v) { moved = clock; aim(u, v); },
      // pointerenter or a click. False when the cooldown (or the persona) says no.
      poke: function () {
        if (!clips || !b.poke || clock < pokeOK) return false;
        pokeQ = true; pokeOK = clock + COOL;
        return true;
      },
      // A touch tap pokes when it can, else looks gently toward the tap, then returns.
      tap: function (u, v) {
        if (this.poke()) return;
        moved = clock; aim(u, v, true);
      }
    };
  }

  return { validate: validate, create: create };
});
