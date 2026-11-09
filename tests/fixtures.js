// Synthetic manifests for the portrait tests. Made-up numbers, no art.
"use strict";

function rects(n, layers) {
  var out = [];
  for (var i = 0; i < n; i++) {
    var f = {};
    layers.forEach(function (l) { f[l] = i === 0 ? null : [i * 4, 0, 8, 8, 10 + i, 10]; });
    out.push(f);
  }
  return out;
}

function files(name, layers) {
  var f = {};
  layers.forEach(function (l) { f[l] = { 1: name + "." + l + ".webp", 2: name + "." + l + "@2x.webp" }; });
  return f;
}

// Cassandra: intro and poke wave, three idles, a 5x3 grid with closed eyes.
function cassandra() {
  var L = ["base", "shirt"], names = ["idle", "blink", "wave", "glance", "tilt", "look"], m = {
    version: 1, persona: "cassandra", width: 100, height: 120, densities: [1, 2], background: null,
    still: { 1: "rest.webp", 2: "rest@2x.webp" }, layers: L, atlases: {}, actions: {},
    grid: {
      atlas: "grid", yaw: [-14, -7, 0, 7, 14], pitch: [-6, 0, 6],
      frames: rects(15, L), closed: rects(15, L)
    },
    behaviour: { intro: "wave", poke: "wave", idles: ["glance", "tilt", "look"], every: [8, 20], blinkEvery: [2, 6], grid: true }
  };
  names.concat("grid").forEach(function (n) { m.atlases[n] = { width: 200, height: 200, files: files(n, L) }; });
  names.forEach(function (n) {
    m.actions[n] = { atlas: n, fps: n === "idle" ? 8 : n === "blink" ? 24 : 12, frames: rects(n === "idle" ? 16 : 6, L) };
  });
  m.actions.idle.loop = true;
  return m;
}

// Carrie: no intro, no wave, her poke is the glance.
function carrie() {
  var m = cassandra();
  delete m.actions.wave;
  delete m.atlases.wave;
  m.persona = "carrie";
  m.background = "#000000";
  m.behaviour = { intro: null, poke: "glance", idles: ["glance", "tilt", "look"], every: [8, 20], blinkEvery: [2, 6], grid: true };
  return m;
}

module.exports = { cassandra: cassandra, carrie: carrie };
