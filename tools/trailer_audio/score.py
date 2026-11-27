"""Cake-Pop Demon Hunters: the score and the sound design (BAD-857).

Everything is synthesized in code: no samples, nothing downloaded, no
copyrighted music. The tune is an original K-pop-style hook ("Sugar Rush",
A minor, 120 bpm) played as an epic orchestral cover: strings, brass, choir,
taiko, timpani, plus BRAAAM hits, drones, rain, fire and the foley.

  ~/.venvs/claude/bin/python tools/trailer_audio/score.py [out.wav]

Writes a 48 kHz stereo wav of the whole teaser (without the voices; mix.py
lays them on top), cues taken from tools/trailer/timeline.py.
"""

import math
import os
import sys

import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "trailer"))
import timeline as T  # noqa: E402

SR = 48000
RNG = np.random.default_rng(1927)
TOTAL = T.TOTAL + 1.0
N = int(TOTAL * SR)


def S(name):
    return T.START[name]


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


class Bus:
    def __init__(self):
        self.l = np.zeros(N, dtype=np.float32)
        self.r = np.zeros(N, dtype=np.float32)

    def add(self, x, t0, gain=1.0, pan=0.0):
        i = int(t0 * SR)
        if i >= N or i + len(x) <= 0:
            return
        a = max(0, -i)
        x = x[a:]
        i = max(i, 0)
        n = min(len(x), N - i)
        gl = gain * math.cos((pan + 1) * math.pi / 4)
        gr = gain * math.sin((pan + 1) * math.pi / 4)
        self.l[i:i + n] += (x[:n] * gl).astype(np.float32)
        self.r[i:i + n] += (x[:n] * gr).astype(np.float32)


MUSIC, SFX, AMB, HITS = Bus(), Bus(), Bus(), Bus()


# ------------------------------------------------------------ dsp bits

def tt(dur):
    return np.arange(int(dur * SR)) / SR


def env(n, a=0.01, d=0.1, s=0.7, r=0.1, curve=2.0):
    e = np.ones(n)
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    na = min(na, n)
    if na:
        e[:na] = np.linspace(0, 1, na) ** 1.0
    nd = min(nd, n - na)
    if nd > 0:
        e[na:na + nd] = np.linspace(1, s, nd)
    e[na + nd:] = s
    if nr and nr < n:
        e[-nr:] *= np.linspace(1, 0, nr) ** curve
    return e


def lp(x, fc, order=2):
    fc = min(fc, SR * 0.45)
    return signal.sosfilt(signal.butter(order, fc, "low", fs=SR, output="sos"), x)


def hp(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, "high", fs=SR, output="sos"), x)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(signal.butter(order, [lo, min(hi, SR * 0.45)], "band", fs=SR, output="sos"), x)


def sweep_lp(x, f0, f1, steps=8):
    """Low-pass whose cutoff glides f0 -> f1 across x (blend of fixed filters)."""
    fs = np.geomspace(f0, f1, steps)
    outs = [lp(x, f) for f in fs]
    pos = np.linspace(0, steps - 1, len(x))
    i = np.clip(pos.astype(int), 0, steps - 2)
    fr = pos - i
    res = np.zeros_like(x)
    for k in range(steps - 1):
        m = i == k
        res[m] = outs[k][m] * (1 - fr[m]) + outs[k + 1][m] * fr[m]
    return res


def saw(f, dur, nh=24, vib=0.0, vib_hz=5.5, phase=0.0):
    t = tt(dur)
    fi = f * (1 + vib * np.sin(2 * np.pi * vib_hz * t)) if vib else f * np.ones_like(t)
    ph = 2 * np.pi * np.cumsum(fi) / SR + phase
    k = int(max(1, min(nh, SR * 0.45 / np.max(fi))))
    out = np.zeros_like(t)
    for h in range(1, k + 1):
        out += np.sin(h * ph) / h
    return out * (2 / np.pi)


def sq(f, dur, nh=12):
    t = tt(dur)
    ph = 2 * np.pi * f * t
    out = np.zeros_like(t)
    for h in range(1, nh * 2, 2):
        if f * h > SR * 0.45:
            break
        out += np.sin(h * ph) / h
    return out * (4 / np.pi) * 0.5


def noise(dur):
    return RNG.standard_normal(int(dur * SR))


def norm(x, peak=1.0):
    m = np.max(np.abs(x)) or 1.0
    return x * (peak / m)


def reverb_ir(rt60=2.8, pre=0.02, bright=0.5):
    n = int((rt60 + pre) * SR)
    t = np.arange(n) / SR
    out = []
    for _ in range(2):
        x = RNG.standard_normal(n) * np.exp(-6.9 * np.maximum(t - pre, 0) / rt60)
        x[: int(pre * SR)] = 0
        x = lp(x, 1500 + 7000 * bright)
        out.append(x)
    return np.stack(out) * 0.04


def reverb(bus, rt60, wet, bright=0.5):
    ir = reverb_ir(rt60, bright=bright)
    wl = signal.fftconvolve(bus.l, ir[0])[:N]
    wr = signal.fftconvolve(bus.r, ir[1])[:N]
    bus.l = (bus.l * (1.0 - wet * 0.3) + wet * wl).astype(np.float32)
    bus.r = (bus.r * (1.0 - wet * 0.3) + wet * wr).astype(np.float32)


# ------------------------------------------------------------ instruments

def strings(midi, dur, vel=0.5, bright=0.5, vib=0.004, slow=0.18):
    f = mtof(midi)
    x = np.zeros(int(dur * SR))
    for d in (-0.12, -0.04, 0.05, 0.13):
        x += saw(f * 2 ** (d / 12), dur, 18, vib, 5.0 + 0.3 * d) / 4
    x = lp(x, 900 + 5000 * bright)
    return x * env(len(x), slow, 0.05, 0.85, 0.35) * vel


def pluck_str(midi, dur=0.18, vel=0.5):
    """Staccato string ostinato."""
    f = mtof(midi)
    x = (saw(f, dur, 14) + saw(f * 1.004, dur, 14)) * 0.5
    x = lp(x, 3200)
    return x * env(len(x), 0.004, 0.05, 0.3, 0.06) * vel


def brass(midi, dur, vel=0.5, bright=0.7, att=0.07):
    f = mtof(midi)
    x = (saw(f, dur, 20, 0.002) + saw(f * 1.003, dur, 20)) * 0.5
    x = sweep_lp(x, 500 + 800 * bright, 1500 + 3200 * bright, 5)
    x = np.tanh(x * 1.6)
    return x * env(len(x), att, 0.08, 0.85, 0.15) * vel


def choir(midi, dur, vel=0.5, vowel="ah"):
    f = mtof(midi)
    x = np.zeros(int(dur * SR))
    for d in (-0.1, 0.0, 0.11):
        x += saw(f * 2 ** (d / 12), dur, 30, 0.006, 5.0 + d * 3) / 3
    forms = {"ah": (800, 1150, 2900), "oh": (500, 900, 2800), "oo": (330, 800, 2600)}[vowel]
    y = sum(bp(x, fc * 0.85, fc * 1.15, 2) * g for fc, g in zip(forms, (1.0, 0.6, 0.25)))
    return y * env(len(y), 0.25, 0.1, 0.9, 0.4) * vel * 2.2


def bell(midi, dur=2.5, vel=0.4):
    """Celesta / music-box: the cute side of the tune."""
    f = mtof(midi)
    t = tt(dur)
    x = np.zeros_like(t)
    for k, (m, a) in enumerate(((1, 1.0), (2.76, 0.4), (5.4, 0.2), (8.9, 0.08))):
        x += a * np.sin(2 * np.pi * f * m * t) * np.exp(-t * (2.2 + k * 1.5))
    return x * vel * 0.7


def piano(midi, dur=2.0, vel=0.4):
    f = mtof(midi)
    t = tt(dur)
    x = np.zeros_like(t)
    for h in range(1, 9):
        x += np.sin(2 * np.pi * f * h * t * (1 + 0.0004 * h * h)) / h ** 1.2 * np.exp(-t * (1.5 + h * 0.9))
    x *= 1 - np.exp(-t * 400)
    return lp(x, 4500) * vel * 1.2


def taiko(vel=1.0, pitch=58.0):
    t = tt(1.6)
    f = pitch * (1 + 1.4 * np.exp(-t * 18))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.2)
    x += lp(noise(1.6), 900) * np.exp(-t * 40) * 0.6
    x += 0.3 * np.sin(2 * np.pi * pitch * 2.1 * t) * np.exp(-t * 9)
    return np.tanh(x * 2.0) * vel


def timp(freq, vel=0.8, dur=1.4):
    t = tt(dur)
    f = freq * (1 + 0.25 * np.exp(-t * 14))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.0)
    x += lp(noise(dur), 600) * np.exp(-t * 60) * 0.5
    return x * vel


def snare(vel=0.7):
    t = tt(0.5)
    x = hp(noise(0.5), 1500) * np.exp(-t * 14) + 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 28)
    return x * vel


def hat(vel=0.3):
    t = tt(0.08)
    return hp(noise(0.08), 7000) * np.exp(-t * 60) * vel


def braam(dur=3.6, root=43.65, vel=1.0):
    """The trailer horn: detuned saw stack, a fifth, an octave, sub, distortion, filter close."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    g = 1 + 0.035 * np.exp(-t * 1.3)
    x = np.zeros(n)
    for ratio, amp in ((1.0, 1.0), (2.0, 0.8), (1.5, 0.55), (3.0, 0.35), (4.0, 0.25)):
        for d in (-0.14, -0.05, 0.0, 0.06, 0.15):
            fi = root * ratio * 2 ** (d / 12) * g
            ph = 2 * np.pi * np.cumsum(fi) / SR
            w = np.zeros(n)
            for h in range(1, 14):
                w += np.sin(h * ph) / h
            x += w * amp / 5
    x = np.tanh(x * 2.6)
    x = sweep_lp(x, 4200, 260, 7)
    sub = np.sin(2 * np.pi * np.cumsum(root * 0.5 * (1 + 0.08 * np.exp(-t * 3))) / SR) * 0.9
    e = (1 - np.exp(-t * 90)) * np.exp(-t / (dur * 0.38)) * (0.25 + 0.75 * np.exp(-t * 2.5))
    imp = lp(noise(dur), 700) * np.exp(-t * 14) * 0.9
    y = (x * 0.8 + sub) * e + imp
    return np.tanh(y * 1.3) * vel


def hit_small(vel=0.6):
    """A shorter low hit for the cards."""
    t = tt(1.8)
    f = 52 * (1 + 0.6 * np.exp(-t * 10))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.4)
    x += lp(noise(1.8), 500) * np.exp(-t * 24) * 0.7
    x += 0.35 * lp(saw(65.4, 1.8, 20), 700) * np.exp(-t * 2.2)
    return np.tanh(x * 1.8) * vel


def riser(dur, vel=0.5, f0=200, f1=9000):
    n = int(dur * SR)
    x = noise(dur)
    x = sweep_lp(x, f0, f1, 9)
    t = np.linspace(0, 1, n)
    sw = np.sin(2 * np.pi * np.cumsum(120 * (2 ** (t * 3.6))) / SR) * 0.3
    return (x * 0.6 + sw) * (t ** 2.2) * vel


def drone(f, dur, vel=0.5, motion=0.15):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for d in (-0.1, 0.0, 0.08):
        x += saw(f * 2 ** (d / 12), dur, 10, 0.001, 0.2) / 3
    x += 0.7 * np.sin(2 * np.pi * f * 0.5 * t)
    x = sweep_lp(x, 300, 700, 4)
    return x * (0.7 + motion * np.sin(2 * np.pi * 0.09 * t)) * vel


def boom_sfx(dur=2.4, vel=0.9, deep=38.0):
    t = tt(dur)
    f = deep * (1 + 1.6 * np.exp(-t * 7))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.0)
    x += lp(noise(dur), 1800) * np.exp(-t * 5) * 0.9
    x += hp(lp(noise(dur), 5000), 300) * np.exp(-t * 18) * 0.5
    return np.tanh(x * 1.7) * vel


def whoosh(dur=0.8, vel=0.4, up=True):
    n = int(dur * SR)
    x = bp(noise(dur), 300, 6000)
    t = np.linspace(0, 1, n)
    e = np.sin(np.pi * t) ** 2 if up else (1 - t) ** 2
    return x * e * vel


def tick(vel=0.3, f=1800):
    t = tt(0.05)
    return np.sin(2 * np.pi * f * t) * np.exp(-t * 90) * vel


def clang(vel=0.6):
    t = tt(2.2)
    x = np.zeros_like(t)
    for m, a in ((1, 1.0), (2.32, 0.7), (4.1, 0.5), (6.8, 0.3), (9.7, 0.2)):
        x += a * np.sin(2 * np.pi * 620 * m * t) * np.exp(-t * (3 + m))
    x += hp(noise(2.2), 3000) * np.exp(-t * 50) * 0.5
    return x * vel * 0.5


def thud(vel=0.7, f=70):
    t = tt(0.7)
    x = np.sin(2 * np.pi * f * (1 + 0.8 * np.exp(-t * 25)) * t) * np.exp(-t * 9) + lp(noise(0.7), 600) * np.exp(-t * 30) * 0.7
    return np.tanh(x * 1.5) * vel


def twang(vel=0.4):
    t = tt(1.4)
    f = 340 * (1 + 0.12 * np.sin(2 * np.pi * 14 * t) * np.exp(-t * 3))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 3.5)
    return x * vel


def boing(vel=0.25):
    t = tt(0.22)
    f = 300 + 500 * np.sin(np.pi * np.clip(t / 0.22, 0, 1))
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14) * vel


def pitter(dur=1.2, vel=0.25, n=26):
    out = np.zeros(int(dur * SR))
    for _ in range(n):
        i = RNG.integers(0, len(out) - 800)
        t = tt(0.016)
        click = np.sin(2 * np.pi * RNG.uniform(3500, 7500) * t) * np.exp(-t * 300)
        out[i:i + len(click)] += click * RNG.uniform(0.3, 1.0)
    return out * vel


def crunch(vel=0.7):
    t = tt(0.22)
    x = hp(noise(0.22), 700) * np.exp(-t * 28)
    for _ in range(5):
        i = RNG.integers(0, int(0.15 * SR))
        x[i:i + 300] += RNG.standard_normal(300) * np.exp(-np.arange(300) / 60) * 0.8
    return lp(x, 6000) * vel


def sniff(vel=0.5):
    n = int(0.7 * SR)
    t = np.linspace(0, 1, n)
    x = bp(noise(0.7), 700, 4200) * (np.sin(np.pi * t) ** 3)
    return x * vel


def wind(dur, vel=0.4):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = bp(noise(dur), 200, 1800)
    g = 0.5 + 0.5 * np.sin(2 * np.pi * 0.23 * t + 1) * np.sin(2 * np.pi * 0.07 * t)
    return x * g * vel


def rainloop(dur, vel=0.3):
    x = hp(noise(dur), 1500)
    x = lp(x, 9000)
    drops = np.zeros(int(dur * SR))
    for _ in range(int(dur * 40)):
        i = RNG.integers(0, len(drops) - 400)
        drops[i:i + 120] += RNG.standard_normal(120) * np.exp(-np.arange(120) / 25) * 0.8
    return (x * 0.5 + hp(drops, 800)) * vel


def fire(dur, vel=0.3):
    out = lp(noise(dur), 220) * 0.7
    for _ in range(int(dur * 22)):
        i = RNG.integers(0, len(out) - 500)
        k = int(RNG.integers(80, 400))
        out[i:i + k] += RNG.standard_normal(k) * np.exp(-np.arange(k) / (k / 4)) * RNG.uniform(0.2, 1.0)
    return hp(out, 80) * vel


def keyclack(vel=0.4):
    t = tt(0.04)
    return hp(noise(0.04), 1200) * np.exp(-t * 120) * vel


def candle(dur, vel=0.12):
    out = lp(noise(dur), 400) * 0.1
    for _ in range(int(dur * 4)):
        i = RNG.integers(0, len(out) - 300)
        out[i:i + 120] += RNG.standard_normal(120) * np.exp(-np.arange(120) / 30) * 0.4
    return out * vel * 3


# ------------------------------------------------------------ the tune: "Sugar Rush"

SIX = 0.125   # one sixteenth at 120 bpm
HOOK = [  # (start in 16ths, length in 16ths, midi) : four bars
    (0, 2, 76), (2, 2, 76), (4, 2, 79), (6, 2, 81), (8, 4, 79), (12, 2, 76), (14, 2, 74),
    (16, 2, 72), (18, 2, 72), (20, 2, 76), (22, 2, 79), (24, 6, 76), (30, 2, 74),
    (32, 2, 76), (34, 2, 76), (36, 2, 79), (38, 2, 81), (40, 4, 84), (44, 2, 81), (46, 2, 79),
    (48, 4, 76), (52, 2, 74), (54, 2, 72), (56, 8, 69),
]
CHORDS = [(45, (57, 60, 64)), (41, (53, 57, 60)), (48, (55, 60, 64)), (43, (55, 59, 62))]  # Am F C G: bass, triad


def hook(t0, bars=4, power=1.0, perc=True, choir_on=True, solo=None):
    """The hook, orchestrated. power 0..1.2 sets how many layers are in; solo='bell'|'piano' plays it small."""
    for bar in range(bars):
        tb = t0 + bar * 2.0
        bass, tri = CHORDS[bar % 4]
        if solo is None:
            for m in tri:
                MUSIC.add(strings(m - 12, 2.0, 0.17 * power, 0.45), tb, 1.0, -0.3 if m % 2 else 0.3)
            MUSIC.add(strings(bass - 12, 2.0, 0.34 * power, 0.35), tb, 1.0, 0)
            if power > 0.5:
                for k in range(8):
                    MUSIC.add(pluck_str(bass + (0, 12, 7, 12, 0, 12, 7, 12)[k], 0.2, 0.3 * power), tb + k * 0.25, 1.0, -0.2 + 0.05 * k)
            if perc:
                MUSIC.add(taiko(1.0 * min(power, 1.0)), tb, 1.0, -0.1)
                MUSIC.add(taiko(0.8 * min(power, 1.0), 52), tb + 1.0, 1.0, 0.1)
                if power > 0.7:
                    MUSIC.add(snare(0.7), tb + 0.5, 1.0, 0.1)
                    MUSIC.add(snare(0.8), tb + 1.5, 1.0, -0.1)
                    for k in range(8):
                        MUSIC.add(hat(0.18), tb + k * 0.25 + 0.125, 1.0, 0.3)
                if bar == bars - 1 and power > 0.7:
                    for k in range(8):
                        MUSIC.add(snare(0.3 + 0.06 * k), tb + 1.5 + k * 0.0625, 1.0, 0)
    for st, ln, m in HOOK:
        if st >= bars * 16:
            continue
        tn = t0 + st * SIX
        dur = ln * SIX + 0.1
        if solo == "bell":
            MUSIC.add(bell(m + 12, 1.8, 0.35), tn, 1.0, 0.2)
        elif solo == "piano":
            MUSIC.add(piano(m, 1.6, 0.4), tn, 1.0, 0.15)
            MUSIC.add(piano(m - 12, 1.6, 0.25), tn, 1.0, -0.1)
        else:
            MUSIC.add(strings(m, dur, 0.34 * power, 0.7), tn, 1.0, 0.25)
            MUSIC.add(strings(m - 12, dur, 0.3 * power, 0.5), tn, 1.0, -0.25)
            if power > 0.55:
                MUSIC.add(brass(m - 12, dur, 0.34 * power, 0.7), tn, 1.0, 0.0)
            if power > 0.85:
                MUSIC.add(brass(m, dur, 0.22 * power, 0.9), tn, 1.0, 0.1)
            if choir_on and ln >= 4 and power > 0.8:
                MUSIC.add(choir(m, dur + 0.2, 0.3 * power, "ah"), tn, 1.0, 0.0)


# ------------------------------------------------------------ the cue sheet

def build():
    s = S
    # --- 0:08 cold open --------------------------------------------------
    t0 = s("city")
    AMB.add(drone(55.0, 20.0, 0.5), t0 - 0.5, 1.0)
    AMB.add(fire(6.5, 0.4), t0, 1.0, -0.2)
    AMB.add(wind(6.0, 0.25), t0, 1.0, 0.2)
    for k in range(10):   # a slow heartbeat under the fire
        SFX.add(thud(0.35 + 0.05 * k, 50), t0 + 1.0 + k * 1.4, 1.0, 0)
    t1 = s("horns")
    AMB.add(fire(5.0, 0.3), t1, 1.0, 0.2)
    for k, m in enumerate((33, 33, 36)):  # low brass swell: the shape in the smoke
        MUSIC.add(brass(m, 2.8, 0.34, 0.2, 0.9), t1 + 0.4 + k * 1.2, 1.0, 0)
    HITS.add(boom_sfx(2.8, 0.55, 34), t1 + 3.3, 1.0)
    t2 = s("bakery")
    AMB.add(rainloop(8.2, 0.33), t2 - 0.5, 1.0)
    for k, (st, ln, m) in enumerate(HOOK[:12]):   # the tune as a music box, slow and wrong
        MUSIC.add(bell(m + 12 - (1 if st in (6, 16) else 0), 2.6, 0.28), t2 + 0.6 + st * 0.2, 1.0, 0.3)
    MUSIC.add(drone(55.0, 6.5, 0.35), t2, 1.0)
    # silence at 25.0, then the eyes
    t3 = s("eyes")
    AMB.add(rainloop(1.8, 0.07), t3, 1.0)
    SFX.add(tick(0.2, 900), t3 + 1.35, 1.0)
    HITS.add(braam(3.8, 43.65, 1.0), t3 + 1.9, 1.0)
    # --- 0:28 the team ----------------------------------------------------
    t = s("card_summer")
    HITS.add(hit_small(0.8), t + 0.1, 1.0)
    MUSIC.add(drone(55.0, 2.0, 0.3), t, 1.0)
    t = s("vanilla")
    AMB.add(wind(5.0, 0.55), t, 1.0)
    MUSIC.add(drone(55.0, 5.2, 0.4), t, 1.0)
    for k in range(10):
        MUSIC.add(pluck_str(33 + (0, 7, 0, 7, 12)[k % 5], 0.3, 0.32), t + k * 0.5 + 0.05, 1.0, -0.2)
    for m in (45, 52, 57):
        MUSIC.add(strings(m, 5.0, 0.18, 0.4, slow=1.5), t, 1.0, 0.0)
    HITS.add(riser(1.0, 0.2, 500, 6000), t + 4.0, 1.0)
    t = s("velvet")
    for k in range(int(T.DUR["velvet"] / 0.25)):  # clock ticks + arpeggio pulse
        SFX.add(tick(0.12 + 0.12 * (k % 4 == 0), 2400), t + k * 0.25, 1.0, 0.4)
        MUSIC.add(pluck_str((45, 52, 57, 60, 64, 60, 57, 52)[k % 8] + (0, 0, -4, -4)[(k // 8) % 4], 0.14, 0.26 + 0.08 * (k / 34)), t + k * 0.25, 1.0, -0.3)
    for m in (45, 48, 52):
        MUSIC.add(strings(m, T.DUR["velvet"], 0.2, 0.4, slow=2.5), t, 1.0, 0)
    for k, tm in enumerate((1.3, 3.3, 6.4)):
        SFX.add(tick(0.35, 3200), t + tm, 1.0, 0.8)
    for b in range(4):
        MUSIC.add(taiko(0.35 + 0.15 * b, 55), t + 4.0 + b * 1.0, 1.0)
    t = s("funfetti")
    MUSIC.add(drone(55.0, 5.0, 0.3), t, 1.0)
    HITS.add(boom_sfx(3.0, 1.0, 36), t + 0.9, 1.0)
    HITS.add(riser(0.9, 0.3, 300, 5000), t + 0.0, 1.0)
    SFX.add(pitter(2.0, 0.22, 40), t + 1.6, 1.0, 0.2)
    for k in range(3):
        SFX.add(boing(0.18), t + 1.4 + 0.75 * k + 0.45, 1.0)
        SFX.add(thud(0.22, 90), t + 1.4 + 0.75 * k + 0.8, 1.0)
    for k, m in enumerate((45, 48, 52, 57)):
        MUSIC.add(strings(m, 3.0, 0.22, 0.6, slow=1.0), t + 2.0, 1.0)
    t = s("stage")   # the day job: the tune, played straight and big
    hook(t - 0.2, 3, 0.95, True, True)
    for k in range(40):
        AMB.add(hp(noise(0.2), 2500) * np.exp(-tt(0.2) * 12) * 0.05, t + k * 0.13, 1.0, RNG.uniform(-1, 1))   # crowd fizz
    # hard cut at the end of the stage: nothing rings out
    # --- 0:55 the stakes ---------------------------------------------------
    t = s("crumb")
    AMB.add(candle(T.DUR["crumb"] + 0.5, 0.25), t - 0.2, 1.0, 0.5)
    AMB.add(drone(41.2, T.DUR["crumb"] + 1.0, 0.3, 0.3), t - 0.2, 1.0)
    MUSIC.add(strings(45, 6.0, 0.14, 0.2, slow=2.5), t + 1.0, 1.0)
    SFX.add(thud(0.1, 120), t + 5.65, 1.0)
    SFX.add(pitter(0.8, 0.12, 8), t + 5.7, 1.0)
    t = s("card_evil")
    HITS.add(braam(3.4, 38.9, 0.95), t, 1.0)
    t = s("demon")
    AMB.add(fire(T.DUR["demon"], 0.3), t, 1.0, -0.2)
    AMB.add(wind(T.DUR["demon"], 0.2), t, 1.0, 0.3)
    MUSIC.add(drone(36.7, T.DUR["demon"] + 0.5, 0.6, 0.3), t, 1.0)
    for k in range(10):
        MUSIC.add(brass(33 if k % 3 else 36, 1.4, 0.3, 0.25, 0.4), t + 0.3 + k * 1.0, 1.0)
        HITS.add(taiko(0.9, 45), t + 0.3 + k * 1.0, 1.0, 0)
    for k in range(4):    # his footsteps / breath
        HITS.add(boom_sfx(2.0, 0.5, 33), t + 0.15 + k * 2.4, 1.0)
    SFX.add(whoosh(1.2, 0.35, True), t + 4.4, 1.0)
    for m in (33, 40, 45):
        MUSIC.add(choir(m + 12, 4.0, 0.2, "oo"), t + 6.5, 1.0)
    t = s("card_feed")
    HITS.add(braam(4.0, 36.7, 1.0), t, 1.0)
    # --- 1:14 the montage: the tune at full power -----------------------------
    t = s("walk")
    hook(t, 4, 1.15, True, True)   # 8 s: walk, sword, fly, headbutt
    for k in range(3):
        SFX.add(boing(0.25), t + 0.6 + k * 1.14, 1.0)
        SFX.add(thud(0.4, 80), t + 1.2 + k * 1.14, 1.0)
    SFX.add(clang(0.6), t + s("sword") - t + 1.45, 1.0, 0.1)
    SFX.add(whoosh(0.5, 0.3, True), t + s("sword") - t + 0.8, 1.0)
    tf = s("fly")
    HITS.add(boom_sfx(2.4, 1.0, 40), tf + 0.35, 1.0)
    HITS.add(boom_sfx(1.8, 0.6, 46), tf + 0.55, 1.0)
    SFX.add(whoosh(1.0, 0.4, True), tf + 0.1, 1.0)
    SFX.add(thud(0.6, 60), tf + 1.58, 1.0)
    SFX.add(twang(0.5), tf + 1.6, 1.0)
    th = s("headbutt")
    for i in range(5):
        for q in range(5):
            SFX.add(keyclack(0.5), th + 0.35 + 0.4 * i + q * 0.012, 1.0, 0.2)
        SFX.add(thud(0.3, 140), th + 0.4 + 0.4 * i, 1.0)
    SFX.add(tick(0.5, 2600), th + 2.1, 1.0)
    SFX.add(tick(0.5, 3400), th + 2.2, 1.0)
    tr = s("rolldown")
    # music cuts out at the start of the roll and comes back as she stops
    SFX.add(lp(noise(2.0), 400) * np.linspace(0.05, 0.4, int(2 * SR)) * 0.3, tr + 0.3, 1.0)
    SFX.add(pitter(2.5, 0.16, 50), tr + 0.2, 1.0)
    # --- 1:30 the rooftop -----------------------------------------------------
    t = s("roof")
    AMB.add(rainloop(T.DUR["roof"] + 1.0, 0.36), t - 0.5, 1.0)
    AMB.add(fire(T.DUR["roof"], 0.1), t, 1.0, 0.5)
    hook(t + 0.4, 4, 0.35, False, False, solo="piano")
    for m in (45, 52, 57, 60):
        MUSIC.add(strings(m, 7.0, 0.14, 0.3, slow=2.2), t + 0.5, 1.0)
    # --- 1:36 the finale: the build ----------------------------------------------
    t = s("finale")
    AMB.add(fire(6.0, 0.35), t, 1.0, -0.3)
    AMB.add(drone(55.0, 6.0, 0.5), t, 1.0)
    HITS.add(riser(4.0, 0.6, 300, 10000), t + 2.0, 1.0)
    cut = t + T.DUR["finale"]
    # a four-on-the-floor build: kick every beat from 3.0 s, snare roll in the last second
    for b in range(int(2.8 / 0.5)):
        MUSIC.add(taiko(0.5 + 0.08 * b, 58), t + 3.2 + b * 0.5, 1.0)
    for k in range(10):
        MUSIC.add(snare(0.25 + 0.06 * k), t + 4.6 + k * 0.125, 1.0, -0.1 + 0.02 * k)
    for k, m in enumerate((57, 60, 64, 69)):
        MUSIC.add(strings(m, 2.8, 0.2 + 0.05 * k, 0.6, slow=1.8), t + 3.0, 1.0)
        MUSIC.add(choir(m, 2.6, 0.2, "ah"), t + 3.1, 1.0)
    # --- 1:42 the title: the chorus drops (one beat after the cut) ----------------
    t = s("title")
    HITS.add(braam(4.2, 43.65, 1.0), t, 1.0)
    hook(t, 4, 1.25, True, True)
    SFX.add(pitter(3.0, 0.3, 120), t + 0.3, 1.0, 0.3)
    MUSIC.add(choir(69, 6.0, 0.28, "ah"), t + 4.0, 1.0)
    MUSIC.add(brass(45, 3.0, 0.5, 0.8, 0.05), t + 5.5, 1.0)
    # --- 1:50 the stinger ---------------------------------------------------------------
    t = s("stinger")
    AMB.add(fire(T.DUR["stinger"], 0.3), t, 1.0, -0.3)
    AMB.add(drone(36.7, T.DUR["stinger"] + 0.5, 0.5), t, 1.0)
    SFX.add(whoosh(1.1, 0.5, True), t + 0.9, 1.0)
    SFX.add(thud(0.5, 50), t + 2.1, 1.0)
    SFX.add(sniff(0.6), t + 3.4, 1.0, -0.2)
    SFX.add(sniff(0.5), t + 3.9, 1.0, 0.2)
    SFX.add(whoosh(0.5, 0.4, False), t + 4.35, 1.0)
    for k in range(4):
        SFX.add(crunch(0.9), t + 5.05 + k * 0.45, 1.0, 0)
        SFX.add(thud(0.18, 100), t + 5.05 + k * 0.45, 1.0)
    HITS.add(braam(3.0, 43.65, 1.0), t + 8.2, 1.0)
    t = s("card_rating")
    SFX.add(boing(0.2), t + 0.5, 1.0)


def vo_track():
    import wave
    out = np.zeros(N, dtype=np.float32)
    for shot, lid, off in T.VO:
        p = os.path.join(HERE, "vo", lid + ".wav")
        with wave.open(p, "rb") as w:
            x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
        i = int((T.START[shot] + off) * SR)
        out[i:i + len(x)] += x[: N - i]
    return out


def cuts(bus):
    """Where the music stops dead: the end of the stage, the roll, the finale."""
    def gate(t_from, t_to, fade=0.04):
        i, j = int(t_from * SR), int(t_to * SR)
        g = np.ones(N, dtype=np.float32)
        g[i:j] = 0
        k = int(fade * SR)
        if i - k >= 0:
            g[i - k:i] = np.linspace(1, 0, k)
        if j + k < N:
            g[j:j + k] = np.linspace(0, 1, k)
        bus.l *= g
        bus.r *= g
    gate(S("stage") + T.DUR["stage"], S("crumb") + 7.0)          # hard cut after 'By night...'
    gate(S("rolldown") + 0.5, S("rolldown") + 2.9, 0.03)           # she keeps rolling, music stops
    gate(S("finale") + T.DUR["finale"], S("title") - 0.0 + 0.0, 0.01)   # one beat of nothing before the drop
    gate(S("eyes") - 0.0, S("eyes") + 1.8, 0.02)   # the silence before BRAAAM (music bus only)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "score.wav")
    build()
    reverb(MUSIC, 3.0, 0.45)
    reverb(HITS, 3.8, 0.45, 0.3)
    reverb(SFX, 1.2, 0.25)
    reverb(AMB, 2.0, 0.2)
    cuts(MUSIC)
    cuts(HITS)
    # tame the sub: the drones and booms carry more bass than tune
    for bus, k in ((MUSIC, 0.7), (AMB, 0.6), (HITS, 0.4), (SFX, 0.3)):
        bus.l = (bus.l - k * lp(bus.l, 140, 2)).astype(np.float32)
        bus.r = (bus.r - k * lp(bus.r, 140, 2)).astype(np.float32)
    # the ident keeps its own sound; nothing of ours until 0:08
    mix_l = MUSIC.l * 0.55 + HITS.l * 0.8 + SFX.l * 0.8 + AMB.l * 0.7
    mix_r = MUSIC.r * 0.55 + HITS.r * 0.8 + SFX.r * 0.8 + AMB.r * 0.7
    g = np.ones(N, dtype=np.float32)
    g[: int(T.START["city"] * SR) - int(0.5 * SR)] = 0.0
    mix_l *= g
    mix_r *= g
    st = np.stack([mix_l, mix_r], 1)
    st = np.tanh(st * 1.1) / np.tanh(1.1)
    st *= 0.9 / max(np.max(np.abs(st)), 1e-6)
    import wave
    pcm = (st * 32767).astype("<i2")
    with wave.open(out, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("wrote", out, round(N / SR, 1), "s")


if __name__ == "__main__":
    main()
