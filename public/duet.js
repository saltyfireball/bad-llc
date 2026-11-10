/* bad.llc duet (SLRM-1921): Cassie and Carrie in one frame, playing paired bits.
   Needs kit/v1/portrait-core.js first. Mark the frame:
     <figure data-duet="duet/duet.json"> ... <div data-side="left"><img></div> <div data-side="right"><img></div>
   Each side gets the kit's state machine (BOPortraitCore) for blinks and cursor-following eyes, with its own
   clips switched off (drop()). This file owns the clips: every few seconds (duet.json "every"), or on hover or
   tap, it picks a bit, waits until both sides are on rest, then starts both halves together. Never two at once.
   Between bits each side follows the pointer on her own clock (SLRM-1948): every time the pointer starts moving,
   one of them looks first and the other answers late, only half turns, or ignores it.
   No JS, reduced motion or any error: the two stills only. No inline script or style. ASCII only. */
(function (win, doc) {
  var Core = win.BOPortraitCore, fig = doc.querySelector("[data-duet]");
  if (!Core || !win.fetch || !fig) return;

  var still = win.matchMedia("(prefers-reduced-motion: reduce)"), OFF = "bo-portrait-off", SIDES = ["left", "right"],
    WAIT = 3, LOAD = 10, LATE = 4,   // seconds: to reach rest, to load both clips, past a clip's end
    QUIET = 1.2,                     // seconds of a still pointer before its next move is a new look
    FIRST = [0.02, 0.1], LAG = [0.3, 0.7],   // seconds behind the pointer: the one who looks, the other
    HALF = 0.25, DEAF = 0.2,         // chances the other only half turns (one cell), or does not look at all
    run = 0, stop = function () {};

  function num(v) { return typeof v === "number" && isFinite(v); }
  function need(ok, what) { if (!ok) throw new Error(what); }
  function check(d) {
    need(d && d.version === 1 && typeof d.left === "string" && typeof d.right === "string", "duet");
    need(Array.isArray(d.every) && num(d.every[0]) && d.every[0] > 0 && d.every[0] <= d.every[1], "every");
    need(Array.isArray(d.bits) && d.bits.length, "bits");
    d.bits.forEach(function (b) { need(b.left && b.right && num(b.duration) && b.duration > 0, "bit"); });
  }
  function json(url) {
    return fetch(url, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
  }
  function image(url) {
    return new Promise(function (ok, no) {
      var i = new Image();
      i.onload = function () { ok(i); };
      i.onerror = no;
      i.src = url;
    });
  }

  function go(id) {
    var raf = 0, io, off = [], els = [], gone = false, shown = true, onscreen = true, sides = {}, D;

    function undo() {
      gone = true;
      cancelAnimationFrame(raf);
      if (io) io.disconnect();
      off.forEach(function (f) { f(); });
      els.forEach(function (e) {
        if (e.parentNode) e.parentNode.removeChild(e);
        if (e.tagName === "VIDEO") { e.removeAttribute("src"); e.load(); }
      });
    }

    var base = new URL(fig.getAttribute("data-duet"), doc.baseURI), d = win.devicePixelRatio > 1 ? 2 : 1;
    json(base).then(function (duet) {
      check(duet);
      D = duet;
      return Promise.all(SIDES.map(function (s) {
        var url = new URL(duet[s], base);
        return json(url).then(function (m) {
          var bad = Core.validate(m);
          if (bad) throw new Error(bad);
          duet.bits.forEach(function (b) {
            need(m.clips[b[s]] && m.clips[b[s]].duration === b.duration, "clip " + b[s]);
          });
          return Promise.all([image(new URL(m.atlases.blink.files[d], url)), image(new URL(m.atlases.grid.files[d], url))])
            .then(function (a) { sides[s] = { m: m, url: url, atlas: { blink: a[0], grid: a[1] } }; });
        });
      }));
    }).then(function () { if (!gone && id === run) start(); }).catch(undo);

    function start() {
      var clock = 0, last = null, bit = null, lastBit = null, poked = false, coolUntil = 0, clips = true,
        next = span(D.every), moved = -Infinity;

      function span(r) { return r[0] + (r[1] - r[0]) * Math.random(); }

      SIDES.forEach(function (s) {
        var S = sides[s], box = fig.querySelector('[data-side="' + s + '"]'), m = S.m, canvas, video;
        need(box && box.querySelector("img"), "side " + s);
        S.box = box;
        S.core = Core.create(m);
        S.core.drop();                       // the duet plays the clips, the core only blinks and looks
        S.q = [];                            // pointer moves not yet passed on: [time, method, u, v]
        S.lag = 0;
        S.how = "pointer";                   // or "tap" (one cell at most), or null (not looking)
        canvas = doc.createElement("canvas");
        canvas.width = m.width * d;
        canvas.height = m.height * d;
        canvas.className = "bo-portrait-canvas";
        canvas.setAttribute("aria-hidden", "true");
        S.ctx = canvas.getContext("2d");
        need(S.ctx, "canvas");
        video = doc.createElement("video");
        video.className = "bo-portrait-video " + OFF;
        video.muted = true;
        video.setAttribute("muted", "");
        video.setAttribute("playsinline", "");
        video.setAttribute("disablepictureinpicture", "");
        video.setAttribute("aria-hidden", "true");
        video.setAttribute("preload", "none");
        S.video = video;
        S.canvas = canvas;
        box.appendChild(video);
        box.appendChild(canvas);
        els.push(video, canvas);
        on(video, "ended", function () { video.classList.add(OFF); if (bit) bit.ended[s] = true; });
        on(video, "error", noClips);
      });

      function draw(S, f) {
        var r = f && f.frame, k = f ? f.key : "none", W = S.canvas.width, H = S.canvas.height;
        if (k === S.key) return;
        S.key = k;
        S.ctx.clearRect(0, 0, W, H);
        if (r) S.ctx.drawImage(S.atlas[f.atlas], r[0] * d, r[1] * d, r[2] * d, r[3] * d, r[4] * d, r[5] * d, r[2] * d, r[3] * d);
      }

      // A clip failed (iOS Low Power Mode refuses autoplay, a 404): no more bits, the stills, blinks and eyes stay.
      function noClips() {
        if (!clips) return;
        clips = false;
        end();
        SIDES.forEach(function (s) {
          var v = sides[s].video;
          v.classList.add(OFF);
          v.removeAttribute("src");
          v.load();
        });
      }

      function pick() {
        var pool = D.bits.filter(function (b) { return b !== lastBit; });
        if (!pool.length) pool = D.bits;
        return (lastBit = pool[Math.floor(Math.random() * pool.length)]);
      }

      // A sync barrier: both halves start playing hidden and pause on their first decoded frame (rest, like the
      // stills). Once both are there, both are shown and played in the same frame. play() also makes iOS load them.
      function load(b) {
        var n = bit.n;
        SIDES.forEach(function (s) {
          var v = sides[s].video, u = new URL(sides[s].m.clips[b[s]].src, sides[s].url).href, p;
          v.setAttribute("preload", "auto");
          if (v.src === u) v.currentTime = 0;
          else v.src = u;
          p = v.play();
          if (p && p.catch) p.catch(failed);
          function first() { if (bit && bit.n === n) { v.pause(); bit.ready[s] = true; } }
          if (v.requestVideoFrameCallback) v.requestVideoFrameCallback(first);
          else v.addEventListener("playing", first, { once: true });
        });
      }
      function play() {
        SIDES.forEach(function (s) {
          var v = sides[s].video, p = v.play();
          v.classList.remove(OFF);
          if (p && p.catch) p.catch(failed);
        });
      }
      // pause() right after play() rejects that play() with AbortError: that one is expected.
      function failed(e) { if (!e || e.name !== "AbortError") noClips(); }
      function end() {
        bit = null;
        next = clock + span(D.every);
        coolUntil = clock + (D.cooldown || 0);
        SIDES.forEach(function (s) { sides[s].core.resume(performance.now() / 1000); });
      }

      // Phases: wait (both sides heading home to rest), load (both clips buffering), play.
      function stepBit(dt) {
        bit.t += dt;
        if (bit.phase === "wait") {
          var home = SIDES.every(function (s) { return sides[s].f.kind === "rest"; });
          if (home || bit.t > WAIT) {
            SIDES.forEach(function (s) { sides[s].core.pause(); draw(sides[s], null); });
            bit.phase = "load";
            bit.t = 0;
            load(bit.b);
          }
        } else if (bit.phase === "load") {
          if (bit.ready.left && bit.ready.right) {
            bit.phase = "play";
            bit.t = 0;
            play();
          } else if (bit.t > LOAD) {
            SIDES.forEach(function (s) { sides[s].video.pause(); sides[s].video.classList.add(OFF); });
            end();
          }
        } else if ((bit.ended.left && bit.ended.right) || bit.t > bit.b.duration + LATE) {
          SIDES.forEach(function (s) { sides[s].video.classList.add(OFF); });
          end();
        }
      }

      function frame(t) {
        raf = 0;
        try {
          var now = t / 1000, dt = last == null ? 0 : Math.min(Math.max(now - last, 0), 0.25);
          last = now;
          clock += dt;
          if (!bit && clips && (poked || clock >= next)) {
            poked = false;
            bit = { b: pick(), phase: "wait", t: 0, n: Math.random(), ended: { left: false, right: false }, ready: {} };
            SIDES.forEach(function (s) { sides[s].q.length = 0; sides[s].core.leave(); });
          }
          if (!bit || bit.phase === "wait") {
            SIDES.forEach(function (s) {
              var S = sides[s];
              pass(S);
              S.f = S.core.tick(now);
              draw(S, S.f);
            });
          }
          if (bit) stepBit(dt);
          raf = requestAnimationFrame(frame);
        } catch (e) { undo(); }
      }

      // Running means: tab shown, frame on screen.
      function sync() {
        if (gone) return;
        if (shown && onscreen) {
          if (raf) return;
          last = null;
          if (!bit || bit.phase === "wait") SIDES.forEach(function (s) { sides[s].core.resume(performance.now() / 1000); });
          raf = requestAnimationFrame(frame);
          if (bit && bit.phase === "play") {
            sides.right.video.currentTime = sides.left.video.currentTime;
            SIDES.forEach(function (s) { var p = sides[s].video.play(); if (p && p.catch) p.catch(failed); });
          }
        } else {
          cancelAnimationFrame(raf);
          raf = 0;
          SIDES.forEach(function (s) { sides[s].core.leave(); sides[s].core.pause(); sides[s].video.pause(); });
        }
      }
      function on(t, e, f, o) { t.addEventListener(e, f, o); off.push(function () { t.removeEventListener(e, f, o); }); }
      // A move after a quiet spell is a new look: one side (either) follows at once, the other late, by half
      // or not at all. Each side's moves wait in its queue for its lag, so the two never step their eyes,
      // blink-shut or come home on the same frame.
      function aim(e, method) {
        if (bit) return;
        if (clock - moved > QUIET) {
          var lead = Math.random() < 0.5 ? 0 : 1, r = Math.random();
          SIDES.forEach(function (s, i) {
            var S = sides[s];
            S.lag = span(i === lead ? FIRST : LAG);
            S.how = i === lead ? method : r < DEAF ? null : r < DEAF + HALF ? "tap" : method;
          });
        }
        moved = clock;
        SIDES.forEach(function (s) {
          var S = sides[s], b = S.box.getBoundingClientRect();
          if (S.how) S.q.push([clock, S.how, (e.clientX - b.left) / b.width - 0.5, (e.clientY - b.top) / b.height - 0.5]);
          if (S.q.length > 240) S.q.shift();
        });
      }
      // Hand a side the moves that have waited out its lag ("leave" too, so she also looks home late).
      function pass(S) {
        while (S.q.length && S.q[0][0] <= clock - S.lag) {
          var a = S.q.shift();
          if (a[1] === "leave") S.core.leave();
          else S.core[a[1]](a[2], a[3]);
        }
      }
      function poke() { if (!bit && clips && clock >= coolUntil) poked = true; }

      on(doc, "visibilitychange", function () { shown = !doc.hidden; sync(); });
      if (win.IntersectionObserver) {
        io = new IntersectionObserver(function (e) { onscreen = e[e.length - 1].isIntersecting; sync(); });
        io.observe(fig);
      }
      on(doc.documentElement, "mouseleave", function () { SIDES.forEach(function (s) { sides[s].q.push([clock, "leave"]); }); });
      on(doc, "pointermove", function (e) { if (onscreen && e.pointerType !== "touch") aim(e, "pointer"); }, { passive: true });
      on(fig, "pointerenter", function (e) { if (e.pointerType !== "touch") poke(); });
      on(fig, "pointerdown", function (e) {
        if (e.pointerType === "touch" && (bit || !clips || clock < coolUntil)) aim(e, "tap");
        else poke();
      });
      shown = !doc.hidden;
      sync();
    }

    return undo;
  }

  // Reduced motion: the stills only. Else wait for first paint and the viewport, then idle time.
  function begin() {
    var id = ++run, ready = 0, watch;
    if (still.matches) return;
    function later() {
      if (id !== run || ++ready < 2) return;
      if (watch) watch.disconnect();
      (win.requestIdleCallback || function (f) { setTimeout(f, 200); })(function () {
        if (id === run) stop = go(id);
      }, { timeout: 2000 });
    }
    if (win.IntersectionObserver) {
      watch = new IntersectionObserver(function (e) { if (e[e.length - 1].isIntersecting) { watch.disconnect(); later(); } }, { rootMargin: "300px" });
      watch.observe(fig);
    } else ready++;
    if (doc.readyState === "complete") later();
    else win.addEventListener("load", later, { once: true });
    stop = function () { run++; if (watch) watch.disconnect(); };
  }

  begin();
  still.addEventListener("change", function () { stop(); stop = function () {}; begin(); });
})(window, document);
