/* Bad Omen kit v1: living portrait, the part that touches the page. Needs portrait-core.js first.
   Mark a figure: <figure data-portrait="portrait/manifest.json"><img ...></figure>.
   After first paint it fetches the manifest and atlases and draws over the still. Any
   problem leaves the still showing. No inline script or style, so a strict CSP holds
   (script-src 'self' for the code, connect-src 'self' for the manifest, img-src 'self'
   for the atlases). ASCII only. */
(function (win, doc) {
  var Core = win.BOPortraitCore;
  if (!Core || !win.fetch) return;

  var still = win.matchMedia("(prefers-reduced-motion: reduce)");

  function load(url) {
    return new Promise(function (ok, no) {
      var i = new Image();
      i.onload = function () { ok(i); };
      i.onerror = no;
      i.src = url;
    });
  }

  function portrait(fig) {
    var img = fig.querySelector("img"), src = fig.getAttribute("data-portrait"),
      run = 0, stop = function () {};
    if (!img || !src) return;

    // Fetch and validate, then draw. Returns a function that undoes it all.
    function go(id) {
      var canvas, raf, io, off = [], shown = true, onscreen = true, gone = false;

      function fail() { undo(); }
      function undo() {
        gone = true;
        cancelAnimationFrame(raf);
        if (io) io.disconnect();
        off.forEach(function (f) { f(); });
        if (canvas && canvas.parentNode) canvas.parentNode.removeChild(canvas);
        img.classList.remove("bo-portrait-hide");
      }

      var base = new URL(src, doc.baseURI);
      fetch(base, { credentials: "same-origin" }).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      }).then(function (m) {
        var bad = Core.validate(m);
        if (bad) throw new Error(bad);
        if (gone || id !== run) return;
        var d = win.devicePixelRatio > 1 && m.densities.indexOf(2) >= 0 ? 2 : 1,
          B = m.behaviour, names = [B.intro, B.poke, "idle", "blink"].concat(B.idles),
          atlas = {}, jobs = [];
        if (B.grid) names.push("grid");
        // Only the atlases the behaviour can reach. Still first, then every layer of each.
        names.forEach(function (n) {
          var a = n === "grid" ? m.grid.atlas : m.actions[n] && m.actions[n].atlas;
          if (a) atlas[a] = {};
        });
        jobs.push(load(new URL(m.still[d], base)));
        Object.keys(atlas).forEach(function (a) {
          m.layers.forEach(function (l) {
            jobs.push(load(new URL(m.atlases[a].files[l][d], base)).then(function (i) { atlas[a][l] = i; }));
          });
        });
        return Promise.all(jobs).then(function (j) { start(m, d, atlas, j[0]); });
      }).catch(fail);

      function start(m, d, atlas, rest) {
        if (gone || id !== run) return;
        var B = m.behaviour, core = Core.create(m), W = m.width * d, H = m.height * d, bg = m.background,
          ctx, last = [], lastKey, rect;
        canvas = doc.createElement("canvas");
        canvas.width = W;
        canvas.height = H;
        canvas.className = "bo-portrait-canvas";
        canvas.setAttribute("role", "img");
        canvas.setAttribute("aria-label", img.alt);
        ctx = canvas.getContext("2d");
        if (!ctx) throw new Error("no canvas");
        ctx.drawImage(rest, 0, 0, W, H);

        // Put the rest pixels back under the last frame, clear the new rects, draw the layers.
        function draw(f) {
          var now = m.layers.map(function (l) { return f.frame[l]; }).filter(Boolean);
          last.forEach(function (r) { wipe(r); ctx.drawImage(rest, r[4] * d, r[5] * d, r[2] * d, r[3] * d, r[4] * d, r[5] * d, r[2] * d, r[3] * d); });
          now.forEach(wipe);
          m.layers.forEach(function (l) {
            var r = f.frame[l];
            if (r) ctx.drawImage(atlas[f.atlas][l], r[0] * d, r[1] * d, r[2] * d, r[3] * d, r[4] * d, r[5] * d, r[2] * d, r[3] * d);
          });
          last = now;
        }
        function wipe(r) {
          if (bg) { ctx.fillStyle = bg; ctx.fillRect(r[4] * d, r[5] * d, r[2] * d, r[3] * d); }
          else ctx.clearRect(r[4] * d, r[5] * d, r[2] * d, r[3] * d);
        }

        function frame(t) {
          raf = 0;
          try {
            var f = core.tick(t / 1000);
            if (f.key !== lastKey) { lastKey = f.key; draw(f); }
            raf = requestAnimationFrame(frame);
          } catch (e) { fail(); }
        }
        // Running means: tab shown, portrait on screen. Resuming leaves no time jump.
        function sync() {
          if (gone) return;
          if (shown && onscreen) {
            if (raf) return;
            core.resume(performance.now() / 1000);
            raf = requestAnimationFrame(frame);
          } else {
            cancelAnimationFrame(raf);
            raf = 0;
            core.pause();
          }
        }
        function on(t, e, f, o) { t.addEventListener(e, f, o); off.push(function () { t.removeEventListener(e, f, o); }); }

        fig.insertBefore(canvas, img.nextSibling);
        img.classList.add("bo-portrait-hide");

        on(doc, "visibilitychange", function () { shown = !doc.hidden; sync(); });
        if (win.IntersectionObserver) {
          io = new IntersectionObserver(function (e) { onscreen = e[e.length - 1].isIntersecting; sync(); });
          io.observe(fig);
        }
        if (B.grid && m.grid) {
          on(doc, "pointermove", function (e) {
            if (e.pointerType === "touch") return;
            rect = fig.getBoundingClientRect();
            core.pointer((e.clientX - rect.left) / rect.width - 0.5, (e.clientY - rect.top) / rect.height - 0.5);
          }, { passive: true });
        }
        on(fig, "pointerenter", function (e) { if (e.pointerType !== "touch") core.poke(); });
        on(fig, "pointerdown", function (e) {
          rect = fig.getBoundingClientRect();
          if (e.pointerType === "touch") core.tap((e.clientX - rect.left) / rect.width - 0.5, (e.clientY - rect.top) / rect.height - 0.5);
          else core.poke();
        });
        shown = !doc.hidden;
        sync();
      }

      return undo;
    }

    function begin() {
      var id = ++run;
      if (still.matches) return;
      // After first paint: let the page settle, then work when the browser is idle.
      function later() {
        if (id !== run) return;
        (win.requestIdleCallback || function (f) { setTimeout(f, 200); })(function () {
          if (id === run) stop = go(id);
        }, { timeout: 2000 });
      }
      if (doc.readyState === "complete") later();
      else win.addEventListener("load", later, { once: true });
    }

    begin();
    // Reduced motion can change while the page is open.
    still.addEventListener("change", function () { stop(); stop = function () {}; begin(); });
  }

  Array.prototype.forEach.call(doc.querySelectorAll("[data-portrait]"), portrait);
})(window, document);
