// Synthetic manifests for the portrait tests. Made-up numbers, no art.
"use strict";

// n frame rects: the first is null (same as rest), the rest are small crops inside a 200x200 atlas.
function rects(n) {
  var out = [];
  for (var i = 0; i < n; i++) out.push(i === 0 ? null : [i * 4, 0, 8, 8, 10 + i, 10]);
  return out;
}

function files(name) {
  return { 1: name + ".webp", 2: name + "@2x.webp" };
}

// Cassandra: intro and poke wave, three idles, a 5x3 grid with closed eyes.
function cassandra() {
  return {
    version: 1, persona: "cassandra", width: 100, height: 120, background: "#17151c",
    still: files("rest"),
    clips: {
      idle: { src: "idle.mp4", duration: 4, loop: true },
      wave: { src: "wave.mp4", duration: 2.8 },
      glance: { src: "glance.mp4", duration: 1.5 },
      tilt: { src: "tilt.mp4", duration: 1.5 },
      look: { src: "look.mp4", duration: 2 }
    },
    atlases: {
      blink: { files: files("blink"), width: 200, height: 200 },
      grid: { files: files("grid"), width: 200, height: 200 }
    },
    blink: { atlas: "blink", fps: 24, frames: rects(4) },
    grid: { atlas: "grid", yaw: [-14, -7, 0, 7, 14], pitch: [-6, 0, 6], frames: rects(15), closed: rects(15) },
    behaviour: { intro: "wave", poke: "wave", idles: ["glance", "tilt", "look"], every: [8, 20], blinkEvery: [2, 6] }
  };
}

// Carrie: no intro, no wave, her poke is the glance.
function carrie() {
  var m = cassandra();
  delete m.clips.wave;
  m.persona = "carrie";
  m.background = "#000000";
  m.behaviour = { intro: null, poke: "glance", idles: ["glance", "tilt", "look"], every: [8, 20], blinkEvery: [2, 6] };
  return m;
}

module.exports = { cassandra: cassandra, carrie: carrie };
