/* Bad Omen ident (kit v1). Plays once a visit, muted, when it scrolls into
   view, and holds its last frame.
   Later visits and reduced motion get the poster and a button. No JS: the
   poster and native controls. If the video cannot play, .bo-ident-fallback
   shows instead. A click or key elsewhere on the page leaves it alone. */
(function () {
  var d = document, seen = false,
    calm = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  try { seen = !!sessionStorage.getItem("bo-ident"); } catch (e) {}
  function mark() { try { sessionStorage.setItem("bo-ident", "1"); } catch (e) {} }

  function button(cls) {
    var b = d.createElement("button");
    b.type = "button";
    b.className = "bo-ident-btn " + cls;
    return b;
  }

  [].forEach.call(d.querySelectorAll(".bo-ident"), function (f) {
    var v = f.querySelector("video");
    if (!v) return;
    var src = v.querySelectorAll("source"), started = false,
      bar = d.createElement("div"), snd = button("bo-ident-sound"), act = button("bo-ident-act");

    function fail() { f.classList.add("is-failed"); v.pause(); }
    if (!v.canPlayType || ![].some.call(src, function (s) { return v.canPlayType(s.type); })) return fail();
    if (src.length) src[src.length - 1].addEventListener("error", fail);
    v.addEventListener("error", fail);

    function label() {
      snd.textContent = v.muted ? "Sound: off" : "Sound: on";
      act.textContent = !v.paused ? "Skip" : started || seen ? "Replay" : "Play";
    }
    function run() {
      try { v.currentTime = 0; } catch (e) {}
      var p = v.play();
      if (p && p.catch) p.catch(label);
    }

    v.removeAttribute("controls");
    v.removeAttribute("autoplay");
    v.loop = false;
    v.muted = true;
    v.addEventListener("play", function () { started = true; label(); });
    v.addEventListener("pause", label);
    v.addEventListener("ended", label);
    v.addEventListener("volumechange", label);

    snd.addEventListener("click", function () {
      if (v.muted) { v.muted = false; run(); } else v.muted = true;
    });
    act.addEventListener("click", function () {
      if (v.paused) return run();
      v.pause();
      if (isFinite(v.duration)) v.currentTime = v.duration;
    });

    bar.className = "bo-ident-bar";
    bar.append(snd, act);
    f.appendChild(bar);
    f.classList.add("is-js");
    label();
    if (seen || calm) return;
    // Autoplay waits until most of it is on screen, so an ident lower on the
    // page is not over before anyone scrolls to it. The visit counts once it starts.
    if (!window.IntersectionObserver) { mark(); return run(); }
    var io = new IntersectionObserver(function (es) {
      if (!es[0].isIntersecting || started) return;
      io.disconnect();
      mark();
      run();
    }, { threshold: 0.6 });
    io.observe(f);
  });
})();
