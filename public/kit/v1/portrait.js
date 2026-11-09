/* Bad Omen kit v1: living portrait, the part that touches the page. Needs portrait-core.js first.
   Mark a figure: <figure data-portrait="portrait/manifest.json"><img ...></figure>.
   Near the viewport and after first paint it fetches the manifest and the blink and grid
   atlases, then lays a video (clips) and a canvas (blink and grid crops) over the still. Any
   problem leaves the still showing. No inline script or style (CSP: script-src, connect-src,
   img-src and media-src 'self'). ASCII only. */
(function (win, doc) {
  var Core = win.BOPortraitCore;
  if (!Core || !win.fetch) return;

  var still = win.matchMedia("(prefers-reduced-motion: reduce)"), OFF = "bo-portrait-off";

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
      var canvas, video, raf, io, off = [], shown = true, onscreen = true, gone = false;

      function undo() {
        gone = true;
        cancelAnimationFrame(raf);
        if (io) io.disconnect();
        off.forEach(function (f) { f(); });
        [canvas, video].forEach(function (e) { if (e && e.parentNode) e.parentNode.removeChild(e); });
        if (video) { video.removeAttribute("src"); video.load(); }
      }

      var base = new URL(src, doc.baseURI);
      fetch(base, { credentials: "same-origin" }).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.json();
      }).then(function (m) {
        var bad = Core.validate(m), d = win.devicePixelRatio > 1 ? 2 : 1, jobs = {};
        if (bad) throw new Error(bad);
        if (gone || id !== run) return;
        Object.keys(m.atlases).forEach(function (k) {
          jobs[k] = load(new URL(m.atlases[k].files[d], base));
        });
        return Promise.all([jobs.blink, jobs.grid]).then(function (a) { start(m, d, { blink: a[0], grid: a[1] }); });
      }).catch(undo);

      function start(m, d, atlas) {
        if (gone || id !== run) return;
        var core = Core.create(m), W = m.width * d, H = m.height * d, ctx, rect, lastKey, tok = 0, clips = true, live = false;
        canvas = doc.createElement("canvas");
        canvas.width = W;
        canvas.height = H;
        canvas.className = "bo-portrait-canvas";
        canvas.setAttribute("aria-hidden", "true");
        ctx = canvas.getContext("2d");
        if (!ctx) throw new Error("no canvas");
        video = doc.createElement("video");
        video.className = "bo-portrait-video " + OFF;
        video.muted = true;
        video.setAttribute("muted", "");
        video.setAttribute("playsinline", "");
        video.setAttribute("disablepictureinpicture", "");
        video.setAttribute("aria-hidden", "true");
        video.setAttribute("preload", "none");

        // The video shows once the clip's first frame is up and hides when it ends (its last
        // frame is rest, like the still). A clip that fails drops clips for good.
        function noClips() {
          if (!clips) return;
          clips = false;
          tok++;
          live = false;
          core.drop();
          video.classList.add(OFF);
          video.removeAttribute("src");
          video.load();
        }
        function playing(name) {
          var u = new URL(m.clips[name].src, base).href, n = ++tok, p;
          live = true;
          video.classList.add(OFF);
          video.setAttribute("preload", "auto");
          if (video.src === u) video.currentTime = 0;
          else video.src = u;
          p = video.play();
          if (p && p.catch) p.catch(noClips);
          function show() { if (n === tok && clips) video.classList.remove(OFF); }
          if (video.requestVideoFrameCallback) video.requestVideoFrameCallback(show);
          else video.addEventListener("playing", show, { once: true });
        }
        function hush() { tok++; live = false; video.classList.add(OFF); }
        video.addEventListener("ended", function () { hush(); core.ended(); });
        video.addEventListener("error", noClips);

        function draw(f) {
          var r = f.frame;
          ctx.clearRect(0, 0, W, H);
          if (r) ctx.drawImage(atlas[f.atlas], r[0] * d, r[1] * d, r[2] * d, r[3] * d, r[4] * d, r[5] * d, r[2] * d, r[3] * d);
        }

        function frame(t) {
          raf = 0;
          try {
            var f = core.tick(t / 1000);
            if (f.key !== lastKey) {
              lastKey = f.key;
              if (f.kind === "clip") { draw({}); playing(f.name); }
              else { if (live) { hush(); video.pause(); } draw(f); }
            }
            raf = requestAnimationFrame(frame);
          } catch (e) { undo(); }
        }
        // Running means: tab shown, portrait on screen.
        function sync() {
          if (gone) return;
          if (shown && onscreen) {
            if (raf) return;
            core.resume(performance.now() / 1000);
            raf = requestAnimationFrame(frame);
            if (live) { var p = video.play(); if (p && p.catch) p.catch(noClips); }
          } else {
            cancelAnimationFrame(raf);
            raf = 0;
            core.leave();
            core.pause();
            video.pause();
          }
        }
        function on(t, e, f, o) { t.addEventListener(e, f, o); off.push(function () { t.removeEventListener(e, f, o); }); }
        function at(e) {
          rect = fig.getBoundingClientRect();
          return [(e.clientX - rect.left) / rect.width - 0.5, (e.clientY - rect.top) / rect.height - 0.5];
        }

        fig.insertBefore(video, img.nextSibling);
        fig.insertBefore(canvas, video.nextSibling);

        on(doc, "visibilitychange", function () { shown = !doc.hidden; sync(); });
        if (win.IntersectionObserver) {
          io = new IntersectionObserver(function (e) { onscreen = e[e.length - 1].isIntersecting; sync(); });
          io.observe(fig);
        }
        on(doc.documentElement, "mouseleave", function () { core.leave(); });
        on(doc, "pointermove", function (e) {
          if (onscreen && e.pointerType !== "touch") core.pointer.apply(core, at(e));
        }, { passive: true });
        on(fig, "pointerenter", function (e) { if (e.pointerType !== "touch") core.poke(); });
        on(fig, "pointerdown", function (e) {
          if (e.pointerType === "touch") core.tap.apply(core, at(e));
          else core.poke();
        });
        shown = !doc.hidden;
        sync();
      }

      return undo;
    }

    // Reduced motion: the still only. Else wait for first paint and the viewport, then idle time.
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
    // Reduced motion can change while the page is open.
    still.addEventListener("change", function () { stop(); stop = function () {}; begin(); });
  }

  Array.prototype.forEach.call(doc.querySelectorAll("[data-portrait]"), portrait);
})(window, document);
