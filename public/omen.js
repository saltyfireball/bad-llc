/* Bad Omen. The ident plays once a visit; the rest you will have to find. */
(function () {
  var d = document, h = d.documentElement, keys = [],
    seq = "ArrowUp ArrowUp ArrowDown ArrowDown ArrowLeft ArrowRight ArrowLeft ArrowRight b a";

  // Ident: CSS runs it. Seen this visit, or any click or key, jumps to the end.
  function skip() { h.classList.add("ident-off"); }
  try { if (sessionStorage.omen) skip(); sessionStorage.omen = 1; } catch (e) {}
  d.addEventListener("pointerdown", skip, { once: true });

  // DO NOT PRESS
  var eggs = d.querySelector(".eggs");
  if (eggs) {
    var b = d.createElement("button"), m = d.createElement("p"), n = 0;
    b.type = "button";
    b.className = "nope";
    b.textContent = "Do not press";
    m.className = "nope-msg";
    m.setAttribute("aria-live", "polite");
    b.addEventListener("click", function () {
      m.textContent = ["We told you.", "Noted. The raven has been informed.",
        "He\u2019s here now."][n++] || "He\u2019s not leaving.";
      if (n === 3) {
        var r = d.createElement("img");
        r.src = "img/raven.svg";
        r.alt = "";
        r.width = 120;
        r.height = 150;
        r.className = "perch";
        r.setAttribute("aria-hidden", "true");
        d.body.appendChild(r);
      }
    });
    eggs.append(b, m);
  }

  // Up up down down left right left right b a
  d.addEventListener("keydown", function (e) {
    skip();
    keys.push(e.key.length === 1 ? e.key.toLowerCase() : e.key);
    keys = keys.slice(-10);
    if (keys.join(" ") !== seq) return;
    keys = [];
    var v = d.querySelector('.board-v[data-row="prophecy"]');
    if (v) {
      v.textContent = "fulfilled";
      v.parentNode.className = "board-row is-bad";
    }
    h.classList.remove("blink");
    void h.offsetWidth;
    h.classList.add("blink");
  });
})();
