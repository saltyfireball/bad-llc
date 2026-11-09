#!/usr/bin/env python3
"""Bad Omen studio ident sting (SLRM-1922).

Synthesizes tools/ident/out/sting.wav: 48 kHz, 24-bit stereo, exactly 9.0 s,
from code only (numpy + scipy). No samples, no downloaded audio. Fixed seeds,
so every run writes the same file.

    uv run --with numpy --with scipy python tools/ident/sting.py [--review]

--review also writes tools/ident/out/review/: sting-cues.txt (cue, frame,
seconds, measured onset), sting-cuemap.png (cue timing chart), and, through
ffmpeg, sting-spectrogram.png and sting-waveform.png.

Timing follows tools/ident/BEATS.md: 24 fps, frame f (1-based) starts at
(f - 1) / 24 s. To retime a sound, change its frame in CUES below.
"""

import argparse
import os
import struct
import subprocess
import sys
import zlib

import numpy as np
from scipy import ndimage, signal

# ---------------------------------------------------------------------------
# Cue table. One row per sound:
#   (frame, until_frame or None, function name, pan, gain dB, reverb send)
# frame       : 1-based frame where the sound's main transient lands.
# until_frame : for sounds with a length set by the picture (salt stream,
#               crackle, whoosh, swell), the frame the sound should be done by.
# pan         : -1 left .. +1 right; a (start, end) pair pans across the cue.
# gain dB     : level of the cue's peak before mastering.
# send        : reverb send, 0..1.
# Stage left to right: ladder -0.35, table -0.05, mirror +0.35. The raven
# walks in from the left; the cat crosses right to left in the foreground.
# ---------------------------------------------------------------------------
CUES = [
    (6, None, "bulb_tick", 0.10, -21.0, 0.20),
    *[(16 + 6 * i, None, "raven_step", -0.85 + 0.075 * i, -19.0, 0.22) for i in range(8)],
    (60, None, "tail_flick", -0.30, -24.0, 0.25),
    (64, 82, "ladder_creak", (-0.38, -0.12), -15.0, 0.25),
    (82, None, "wood_clunk", -0.08, -6.5, 0.28),
    (84, None, "shaker_clink", -0.03, -14.0, 0.28),
    (86, 111, "salt_hiss", 0.02, -21.0, 0.22),
    (100, None, "mirror_wobble_thud", 0.35, -11.0, 0.28),
    (118, None, "mirror_slam", 0.35, -8.0, 0.30),
    (120, None, "glass_crack", 0.35, -9.0, 0.30),
    (122, 150, "crackle_tail", 0.35, -15.0, 0.35),
    (128, 140, "cat_whoosh", (0.90, -0.90), -13.0, 0.18),
    (134, None, "cat_mrrp", 0.00, -20.0, 0.30),
    (162, None, "umbrella_pop", 0.55, -11.0, 0.25),
    (168, 217, "low_swell", 0.00, -6.5, 0.35),
]

SR = 48000
FPS = 24
DUR = 9.0
N = int(SR * DUR)
TARGET_LUFS = -16.0
CEILING_DBTP = -1.0
ROOM_TONE_DBFS = -64.0
SEED = 1922

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "out")
REVIEW_DIR = os.path.join(OUT_DIR, "review")
WAV_PATH = os.path.join(OUT_DIR, "sting.wav")


def frame_start(f):
    return (f - 1) / FPS


def frame_sample(f):
    return int(round(frame_start(f) * SR))


# ---------------------------------------------------------------------------
# DSP helpers
# ---------------------------------------------------------------------------
def ns(sec):
    return max(1, int(round(sec * SR)))


def tvec(n):
    return np.arange(n) / SR


def norm(x):
    p = np.max(np.abs(x))
    return x / p if p > 0 else x


def add(dst, src, at):
    if at < 0:
        src = src[-at:]
        at = 0
    end = min(len(dst), at + len(src))
    if end > at:
        dst[at:end] += src[: end - at]


def lowpass(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, "low", fs=SR, output="sos"), x)


def highpass(x, fc, order=2):
    return signal.sosfilt(signal.butter(order, fc, "high", fs=SR, output="sos"), x)


def bandpass(x, lo, hi, order=2):
    hi = min(hi, SR * 0.45)
    return signal.sosfilt(signal.butter(order, [lo, hi], "band", fs=SR, output="sos"), x)


def env_exp(n, tau, attack=0.0005):
    t = tvec(n)
    e = np.exp(-t / tau)
    if attack > 0:
        e *= np.minimum(1.0, t / attack)
    return e


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def modes(freqs, decays, amps, dur, rng=None, detune=0.0):
    """Sum of exponentially decaying sines: the ring of a struck object."""
    n = ns(dur)
    t = tvec(n)
    out = np.zeros(n)
    for f, d, a in zip(freqs, decays, amps):
        if rng is not None and detune:
            f *= 1 + rng.uniform(-detune, detune)
        if f < SR * 0.45:
            out += a * np.sin(2 * np.pi * f * t) * np.exp(-t / d)
    return out


def strike(rng, freqs, decays, amps, dur, exc_ms=1.0, exc_lp=None, detune=0.02):
    """Short noise excitation through a modal body: tactile foley hit."""
    m = max(8, ns(exc_ms / 1000.0))
    exc = rng.standard_normal(m) * np.hanning(m)
    if exc_lp:
        exc = lowpass(exc, exc_lp)
    ir = modes(freqs, decays, amps, dur, rng, detune)
    return norm(signal.fftconvolve(exc, ir)[: len(ir)])


def noise_burst(rng, dur, lo, hi, tau, attack=0.0005):
    n = ns(dur)
    return norm(bandpass(rng.standard_normal(n), lo, hi) * env_exp(n, tau, attack))


def pitched_thump(n, f_end, f_start, f_tau, amp_tau, attack=0.001):
    t = tvec(n)
    f = f_end + (f_start - f_end) * np.exp(-t / f_tau)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * env_exp(n, amp_tau, attack)


def stick_slip(rng, rate, jitter_ms=1.2):
    """Impulse train from a time-varying rate: the friction of a creak."""
    n = len(rate)
    ph = np.cumsum(rate) / SR
    idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0] + 1
    j = int(jitter_ms * SR / 1000)
    idx = np.clip(idx + rng.integers(-j, j + 1, len(idx)), 0, n - 1)
    imp = np.zeros(n)
    np.add.at(imp, idx, rng.uniform(0.35, 1.0, len(idx)))
    return imp


def resonate(x, freqs, qs, gains):
    y = np.zeros_like(x)
    for f, q, g in zip(freqs, qs, gains):
        b, a = signal.iirpeak(f, q, fs=SR)
        y += g * signal.lfilter(b, a, x)
    return y


def svf_bandpass(x, fc, q):
    """Chamberlin state-variable band-pass with a per-sample cutoff."""
    y = np.empty_like(x)
    low = band = 0.0
    fcoef = 2 * np.sin(np.pi * np.minimum(fc, SR / 6) / SR)
    dq = 1.0 / q
    for i in range(len(x)):
        f = fcoef[i]
        high = x[i] - low - dq * band
        band += f * high
        low += f * band
        y[i] = band
    return y


def formant(x, freq, bw):
    """Two-pole resonator with per-sample centre frequency (formant filter)."""
    y = np.empty_like(x)
    y1 = y2 = 0.0
    r = np.exp(-np.pi * bw / SR)
    c = 2 * r * np.cos(2 * np.pi * freq / SR)
    r2 = r * r
    g = 1 - r
    for i in range(len(x)):
        v = g * x[i] + c[i] * y1 - r2 * y2
        y2 = y1
        y1 = v
        y[i] = v
    return y


def pan_gains(p):
    th = (np.clip(p, -1, 1) + 1) * np.pi / 4
    return np.cos(th), np.sin(th)


# ---------------------------------------------------------------------------
# Cues. Each takes (rng, n) where n is the sample length the picture allows
# (None when the cue sets its own length) and returns mono or (n, 2) stereo,
# or (audio, pre) where pre is a lead-in in samples before the cue frame.
# ---------------------------------------------------------------------------
def bulb_tick(rng, n):
    """Filament tick, a dim re-strike tick, and a short mains buzz flicker."""
    n = ns(0.9)
    t = tvec(n)
    out = np.zeros(n)
    tick = 0.85 * strike(rng, [2400, 3900, 6100, 8300], [0.012, 0.009, 0.006, 0.004],
                         [1, 0.7, 0.5, 0.3], 0.05, exc_ms=0.4)
    add(tick, 0.5 * noise_burst(rng, 0.01, 1500, 14000, 0.0015), 0)
    add(out, tick, 0)
    retick = strike(rng, [2450, 3950, 6200], [0.01, 0.007, 0.005], [1, 0.6, 0.4], 0.04, exc_ms=0.3)
    add(out, 0.35 * retick, ns(0.125))
    phases = rng.uniform(0, 2 * np.pi, 40)
    buzz = sum(np.sin(2 * np.pi * 60 * k * t + phases[k]) / k for k in range(2, 40))
    buzz = bandpass(buzz, 180, 5000)
    gate = np.zeros(n)
    for a, b, lvl in [(0.0, 0.045, 1.0), (0.085, 0.12, 0.45), (0.125, 0.9, 1.0)]:
        gate[ns(a):ns(b)] = lvl
    steady = np.ones(n)
    k0 = ns(0.125)
    steady[k0:] = 0.08 + 0.92 * np.exp(-(t[k0:] - t[k0]) / 0.12)
    gate *= steady
    gate *= 1 - smoothstep((t - 0.6) / 0.3)
    gate = np.convolve(gate, np.hanning(ns(0.003)) / np.hanning(ns(0.003)).sum(), "same")
    out += 0.3 * norm(buzz) * gate
    return norm(out)


def raven_step(rng, n):
    """Two talon taps and a soft pad on a wooden floor."""
    out = np.zeros(ns(0.16))
    taps = [(0.0, 1.0), (rng.uniform(0.012, 0.02), rng.uniform(0.5, 0.75)),
            (rng.uniform(0.03, 0.04), rng.uniform(0.15, 0.3))]
    for dt, a in taps:
        tap = strike(rng, [230, 510, 890, 1420, 2250, 3500, 5200],
                     [0.035, 0.028, 0.022, 0.016, 0.011, 0.007, 0.004],
                     [0.5, 0.7, 0.8, 0.9, 0.8, 0.6, 0.4], 0.12, exc_ms=0.5, detune=0.04)
        claw = noise_burst(rng, 0.006, 2500, 14000, 0.0008)
        add(out, a * 0.8 * tap, ns(dt))
        add(out, a * 0.45 * claw, ns(dt))
    add(out, 0.35 * noise_burst(rng, 0.04, 60, 500, 0.012, attack=0.002), 0)
    return norm(out)


def tail_flick(rng, n):
    """Feather swish ending in a light tap on the ladder leg."""
    n = ns(0.25)
    t = tvec(n)
    tp = 0.03
    e = (t / tp) ** 2 * np.exp(2 * (1 - t / tp))
    swish = norm(bandpass(rng.standard_normal(n), 1800, 7500) * e)
    out = 0.7 * swish
    tap = strike(rng, [640, 1480, 2650, 4100], [0.03, 0.02, 0.012, 0.007],
                 [1, 0.8, 0.5, 0.3], 0.1, exc_ms=0.4)
    add(out, 0.55 * tap, ns(0.035))
    return norm(out)


def ladder_creak(rng, n):
    """Stick-slip creak as the ladder wobbles, a lower groan as it tips, air as it falls."""
    t = tvec(n)
    out = np.zeros(n)
    # creak 1: wobble
    n1 = ns(0.32)
    u = tvec(n1) / 0.32
    wander = lowpass(rng.standard_normal(n1), 8) * 60
    rate = 22 + 42 * np.sin(np.pi * np.clip(u * 1.2, 0, 1)) + 14 * u + wander
    c1 = resonate(stick_slip(rng, np.maximum(rate, 6)), [330, 590, 1050, 1690, 2480, 3600],
                  [14, 18, 22, 22, 20, 16], [0.6, 1.0, 0.9, 0.7, 0.5, 0.3])
    c1 = norm(c1) * np.sin(np.pi * u) ** 0.6 * (0.8 + 0.2 * np.sin(2 * np.pi * 7 * tvec(n1)))
    add(out, c1, 0)
    # creak 2: groan as it commits to the fall
    n2 = ns(0.3)
    u2 = tvec(n2) / 0.3
    rate2 = 14 + 26 * u2 + lowpass(rng.standard_normal(n2), 6) * 40
    c2 = resonate(stick_slip(rng, np.maximum(rate2, 5)), [260, 470, 840, 1350, 2000],
                  [12, 16, 20, 20, 18], [0.8, 1.0, 0.8, 0.5, 0.3])
    c2 = norm(c2) * np.sin(np.pi * u2) ** 0.8 * 0.85
    add(out, c2, ns(0.36))
    # friction noise riding both
    fr = bandpass(rng.standard_normal(n), 900, 4000) * 0.06
    out += fr * (np.abs(out) > 0.05).astype(float)
    # air as it swings down into the table
    k = ns(0.5)
    air = lowpass(bandpass(rng.standard_normal(n - k), 120, 900), 700)
    air = norm(air) * smoothstep((t[k:] - t[k]) / (t[-1] - t[k])) ** 2 * 0.22
    out[k:] += air
    return norm(out)


def wood_clunk(rng, n):
    """Ladder hits the side table: heavy wood body, low thump, two small bounces."""
    n = ns(0.9)
    out = np.zeros(n)
    fr = [88, 141, 226, 353, 532, 781, 1160, 1690, 2450]
    dc = [0.28, 0.22, 0.17, 0.12, 0.08, 0.055, 0.035, 0.022, 0.012]
    am = [1, 0.9, 0.85, 0.8, 0.7, 0.55, 0.45, 0.3, 0.2]
    out += 0.8 * strike(rng, fr, dc, am, 0.9, exc_ms=2.5, exc_lp=4000, detune=0.01)
    out += 0.7 * pitched_thump(n, 45, 68, 0.04, 0.12)
    add(out, 0.35 * noise_burst(rng, 0.02, 800, 9000, 0.003), 0)
    add(out, 0.32 * strike(rng, fr[2:], dc[2:], am[2:], 0.4, exc_ms=1.5, detune=0.03), ns(0.06))
    add(out, 0.14 * strike(rng, fr[3:], dc[3:], am[3:], 0.3, exc_ms=1.0, detune=0.03), ns(0.13))
    return norm(out)


def shaker_clink(rng, n):
    """Glass shaker topples (clink), its metal cap taps, then it rolls."""
    n = ns(0.6)
    t = tvec(n)
    out = np.zeros(n)

    def glass():
        return strike(rng, [2280, 3810, 5390, 7720, 10150], [0.16, 0.11, 0.08, 0.05, 0.03],
                      [1, 0.8, 0.6, 0.45, 0.3], 0.4, exc_ms=0.3, detune=0.02)

    def cap():
        return strike(rng, [4380, 6620, 9110], [0.05, 0.035, 0.02], [1, 0.7, 0.4], 0.15,
                      exc_ms=0.2, detune=0.02)

    add(out, glass(), 0)
    add(out, 0.5 * cap(), ns(0.012))
    add(out, 0.55 * glass(), ns(0.085))
    add(out, 0.3 * cap(), ns(0.09))
    k = ns(0.12)
    tr = t[k:] - t[k]
    roll = bandpass(rng.standard_normal(n - k), 180, 1400)
    roll_env = (0.5 + 0.5 * np.sin(2 * np.pi * 7.5 * tr)) ** 2
    roll_env *= np.minimum(1, tr / 0.02) * np.exp(-tr / 0.18)
    out[k:] += 0.2 * norm(roll) * roll_env
    for i in range(4):
        add(out, 0.12 * np.exp(-i / 2.0) * glass(), k + ns(i / 7.5 + 0.03))
    return norm(out)


def salt_hiss(rng, n):
    """Granular salt stream off the table edge, landing on the floor."""
    t = tvec(n)
    dur = t[-1]
    shape = smoothstep(t / 0.08) * np.where(t < 0.62, 1.0, np.exp(-(t - 0.62) / 0.12))
    shape *= 1 - smoothstep((t - (dur - 0.08)) / 0.08)
    dens = 5500 * shape

    def grains(lo, hi, delay):
        mask = rng.random(n) < dens / SR
        g = np.where(mask, rng.exponential(1.0, n) * rng.choice([-1.0, 1.0], n), 0.0)
        g = bandpass(g, lo, hi)
        return np.concatenate([np.zeros(ns(delay)), g])[:n]

    fine = grains(3000, 12000, 0.0)
    floor = grains(1200, 5000, 0.025)
    sheen = bandpass(rng.standard_normal(n), 4000, 10000) * shape
    out = norm(fine) + 0.5 * norm(floor) + 0.12 * norm(sheen)
    return norm(out)


def mirror_wobble_thud(rng, n):
    """Mirror tips forward and catches on its stand: dull thud, glass flex, rocking knocks."""
    n = ns(0.8)
    out = np.zeros(n)
    out += strike(rng, [68, 115, 187, 296, 462, 700], [0.3, 0.24, 0.18, 0.12, 0.07, 0.04],
                  [1, 0.9, 0.8, 0.6, 0.45, 0.3], 0.8, exc_ms=5, exc_lp=1500, detune=0.01)
    out += 0.4 * pitched_thump(n, 55, 75, 0.03, 0.09, attack=0.002)
    add(out, 0.07 * strike(rng, [1190, 1870, 2760, 3940], [0.35, 0.28, 0.2, 0.12],
                           [1, 0.7, 0.5, 0.3], 0.7, exc_ms=1.0), ns(0.004))
    knock = [410, 980, 1720]
    add(out, 0.35 * strike(rng, knock, [0.03, 0.02, 0.012], [1, 0.7, 0.4], 0.1, exc_ms=0.8), ns(0.018))
    add(out, 0.22 * strike(rng, knock, [0.03, 0.02, 0.012], [1, 0.7, 0.4], 0.1, exc_ms=0.8), ns(0.16))
    add(out, 0.1 * strike(rng, knock, [0.03, 0.02, 0.012], [1, 0.7, 0.4], 0.1, exc_ms=0.8), ns(0.27))
    return norm(out)


def mirror_slam(rng, n):
    """Pivot creak lead-in, then the mirror slams back upright on its frame."""
    pre = ns(0.35)
    n = pre + ns(1.0)
    out = np.zeros(n)
    u = tvec(pre) / 0.35
    rate = 28 + 45 * u
    cr = resonate(stick_slip(rng, rate), [420, 780, 1300, 2100], [14, 18, 20, 18], [0.8, 1.0, 0.7, 0.4])
    out[:pre] += 0.12 * norm(cr) * u ** 2
    m = n - pre
    hit = np.zeros(m)
    hit += strike(rng, [58, 97, 160, 248, 385, 598, 930, 1420],
                  [0.4, 0.32, 0.25, 0.18, 0.12, 0.08, 0.05, 0.03],
                  [1, 0.95, 0.85, 0.75, 0.6, 0.45, 0.35, 0.25], 1.0, exc_ms=4, exc_lp=3000, detune=0.01)
    hit += 0.8 * pitched_thump(m, 37, 52, 0.05, 0.2)
    add(hit, 0.45 * noise_burst(rng, 0.02, 600, 10000, 0.004), 0)
    k = ns(0.12)
    rat = bandpass(rng.standard_normal(k), 1200, 4500)
    rat *= np.sin(2 * np.pi * 38 * tvec(k)) ** 2 * np.exp(-tvec(k) / 0.05)
    add(hit, 0.2 * norm(rat), ns(0.003))
    add(hit, 0.08 * modes([1800, 2650, 3900, 5200], [0.15, 0.12, 0.09, 0.06], [1, 0.8, 0.6, 0.4], 0.5), 0)
    out[pre:] += norm(hit)
    return norm(out), pre


def glass_crack(rng, n):
    """Sharp snap, a run of micro-cracks across the pane, and the glass ringing."""
    n = ns(0.7)
    out = np.zeros(n)
    add(out, noise_burst(rng, 0.01, 2500, 16000, 0.0012), 0)
    add(out, 0.5 * strike(rng, [3140, 4730, 6920, 9480, 12300], [0.32, 0.22, 0.15, 0.09, 0.05],
                          [1, 0.8, 0.6, 0.4, 0.25], 0.7, exc_ms=0.2, detune=0.01), 0)
    k = 28
    gaps = rng.exponential(1.0, k) * np.linspace(0.0015, 0.008, k)
    times = np.cumsum(gaps)
    imp = np.zeros(n)
    for i, tt in enumerate(times):
        imp[min(n - 1, ns(tt))] += 0.9 * np.exp(-i / 12) * rng.uniform(0.4, 1.0) * rng.choice([-1, 1])
    tick_ir = modes([5100, 7300, 9800], [0.006, 0.004, 0.003], [1, 0.7, 0.5], 0.03)
    run = signal.fftconvolve(bandpass(imp, 1800, 15000), tick_ir)[:n]
    out += 0.6 * norm(run)
    add(out, 0.35 * noise_burst(rng, 0.04, 300, 1800, 0.008), 0)
    return norm(out)


def crackle_tail(rng, n):
    """Thinning glass ticks as the cracks run out and settle into the wordmark (stereo)."""
    t = tvec(n)
    out = np.zeros((n, 2))
    rate = 70 * np.exp(-t / 0.3) + 3
    events = np.nonzero(rng.random(n) < rate / SR)[0]
    for e in events:
        te = e / SR
        amp = (0.25 + 0.75 * rng.random()) * np.exp(-te / 0.6)
        for _ in range(1 if rng.random() < 0.7 else rng.integers(2, 5)):
            f1 = rng.uniform(2800, 9000)
            d = rng.uniform(0.004, 0.02)
            tick = modes([f1, f1 * 1.47, f1 * 2.09], [d, d * 0.7, d * 0.5], [1, 0.5, 0.3], d * 5)
            tick[:ns(0.0003)] += rng.standard_normal(ns(0.0003)) * 0.5
            gl, gr = pan_gains(rng.uniform(-0.3, 0.3))
            at = e + rng.integers(0, ns(0.005))
            a = amp * rng.uniform(0.5, 1.0)
            add(out[:, 0], a * gl * tick, at)
            add(out[:, 1], a * gr * tick, at)
    fade = 1 - smoothstep((t - (t[-1] - 0.15)) / 0.15)
    out *= fade[:, None]
    return out / np.max(np.abs(out))


def cat_whoosh(rng, n):
    """Air of a cat bolting past the lens: band-passed noise sweeping up and down."""
    n = n + ns(0.06)
    t = tvec(n)
    u = t / t[-1]
    amp = np.where(u < 0.45, smoothstep(u / 0.45) ** 1.5, np.exp(-((u - 0.45) / 0.22) ** 2))
    fc = 700 + 2200 * np.exp(-((u - 0.45) / 0.18) ** 2)
    x = rng.standard_normal(n)
    body = svf_bandpass(x, fc, 1.2)
    low = lowpass(rng.standard_normal(n), 350)
    out = norm(body) * amp + 0.35 * norm(low) * amp
    return norm(out)


def cat_mrrp(rng, n):
    """Short soft cat trill: formant-filtered glottal source, rolled 'rr', lip close."""
    dur = 0.26
    n = ns(dur)
    t = tvec(n)
    u = t / dur
    f0 = 240 + 140 * smoothstep(u / 0.8) + 50 * smoothstep((u - 0.8) / 0.2)
    f0 *= 1 + 0.008 * np.sin(2 * np.pi * 6 * t)
    ph = 2 * np.pi * np.cumsum(f0) / SR
    src = sum(np.sin(k * ph) / k ** 1.3 for k in range(1, 15))
    depth = 0.65 * (1 - smoothstep((u - 0.55) / 0.2))
    trill = 1 - depth * (0.5 + 0.5 * np.cos(2 * np.pi * 27 * t))
    f1 = 350 + 400 * smoothstep((u - 0.12) / 0.25) - 120 * smoothstep((u - 0.7) / 0.3)
    f2 = 1300 + 500 * smoothstep((u - 0.15) / 0.35)
    f3 = np.full(n, 2900.0)
    f4 = np.full(n, 4200.0)
    voice = (formant(src, f1, 90) + 0.5 * formant(src, f2, 120)
             + 0.25 * formant(src, f3, 180) + 0.12 * formant(src, f4, 250))
    voice = norm(voice)
    murmur = norm(lowpass(src, 450))
    xf = smoothstep(u / 0.18)
    sig = murmur * (1 - xf) * 0.8 + voice * xf
    env = smoothstep(t / 0.02) * (1 - smoothstep((u - 0.9) / 0.1))
    breath = norm(bandpass(rng.standard_normal(n), 1500, 6000)) * 0.03
    out = (sig * trill + breath) * env
    puff = noise_burst(rng, 0.012, 500, 3000, 0.003)
    out = np.concatenate([out, np.zeros(ns(0.02))])
    add(out, 0.06 * puff, n + ns(0.004))
    return norm(out)


def umbrella_pop(rng, n):
    """Runner slides up, the latch clicks, the canopy snaps taut with a small whump."""
    pre = ns(0.14)
    n = pre + ns(0.5)
    out = np.zeros(n)
    u = tvec(pre) / 0.14
    slide = norm(bandpass(rng.standard_normal(pre), 1500, 6500)) * u ** 1.5 * 0.16
    out[:pre] += slide
    add(out, 0.08 * strike(rng, [3260, 4890], [0.02, 0.015], [1, 0.6], 0.05, exc_ms=0.2), 0)
    m = n - pre
    pop = np.zeros(m)
    add(pop, 0.6 * strike(rng, [3260, 4890, 7350, 9900], [0.035, 0.025, 0.015, 0.01],
                          [1, 0.7, 0.5, 0.3], 0.12, exc_ms=0.2), 0)
    add(pop, 0.9 * noise_burst(rng, 0.12, 250, 4500, 0.028, attack=0.001), 0)
    add(pop, 0.3 * noise_burst(rng, 0.1, 400, 3500, 0.03, attack=0.004), ns(0.03))
    wh = lowpass(rng.standard_normal(m), 220) * env_exp(m, 0.05, 0.003)
    pop += 0.7 * norm(wh) + 0.3 * pitched_thump(m, 70, 95, 0.03, 0.06, attack=0.003)
    for i in range(5):
        add(pop, 0.12 * strike(rng, [5200, 7900], [0.008, 0.005], [1, 0.6], 0.03, exc_ms=0.2),
            ns(rng.uniform(0.01, 0.06)))
    out[pre:] += pop
    return norm(out), pre


def low_swell(rng, n):
    """The logo hit: sub drop, punch, a low struck body, then a dark D-minor drone swell
    that blooms and decays to nothing by the last frame (stereo)."""
    t = tvec(n)
    T = t[-1]
    hit = 1.0 * pitched_thump(n, 40, 70, 0.09, 0.55, attack=0.002)
    add(hit, 0.35 * noise_burst(rng, 0.2, 40, 1800, 0.03, attack=0.001), 0)
    body = strike(rng, [73.4, 110.3, 147, 196, 262, 330], [0.55, 0.45, 0.35, 0.25, 0.18, 0.12],
                  [1, 0.6, 0.5, 0.35, 0.25, 0.15], T, exc_ms=4, exc_lp=1200, detune=0.003)
    hit[: len(body)] += 0.5 * body
    hit = np.tanh(1.8 * hit) / np.tanh(1.8)  # gentle saturation: weight without a spiky peak
    e = (1 - np.exp(-t / 0.25)) ** 2 * np.exp(-np.maximum(t - 0.35, 0) / 0.32)
    b = e / e.max()
    notes = [36.71, 55.0, 73.42, 87.31, 110.0]
    namps = [1.0, 0.7, 0.6, 0.35, 0.3]
    out = np.zeros((n, 2))
    for ch in range(2):
        drone = np.zeros(n)
        for f, a in zip(notes, namps):
            for det in (1.0, 1.0021, 0.9983):
                fv = f * det * (1 + rng.uniform(-0.0006, 0.0006))
                kmax = int(1500 / fv)
                for k in range(1, kmax + 1):
                    drone += a / k * np.sin(2 * np.pi * k * fv * t + rng.uniform(0, 2 * np.pi))
        dark = lowpass(drone, 220)
        bright = lowpass(drone, 900)
        drone = norm(dark + (bright - dark) * b)
        shimmer = np.zeros(n)
        for f in (587.33, 880.0, 1174.66):
            for det in (0.997, 1.003):
                shimmer += np.sin(2 * np.pi * f * det * t + rng.uniform(0, 2 * np.pi))
        es = smoothstep(t / 0.8) * np.exp(-np.maximum(t - 0.6, 0) / 0.45)
        out[:, ch] = hit + 0.55 * drone * e + 0.03 * norm(shimmer) * es
    fade = 1 - smoothstep((t - (T - 0.25)) / 0.25)
    out *= fade[:, None]
    return out / np.max(np.abs(out))


# ---------------------------------------------------------------------------
# Room, loudness, limiter
# ---------------------------------------------------------------------------
def room_ir(rng, dur=1.3, rt=(0.85, 0.65, 0.35), predelay=0.011):
    n = ns(dur)
    t = tvec(n)
    nz = rng.standard_normal(n)
    k = 6.91
    tail = (lowpass(nz, 300) * np.exp(-k * t / rt[0])
            + bandpass(nz, 300, 3000) * np.exp(-k * t / rt[1])
            + highpass(nz, 3000) * np.exp(-k * t / rt[2]))
    tail *= np.minimum(1, t / 0.02) * 0.6
    for _ in range(10):
        tap = rng.uniform(0.005, 0.045)
        tail[ns(tap)] += 0.6 * np.exp(-tap / 0.03) * rng.choice([-1, 1]) * 8
    ir = np.concatenate([np.zeros(ns(predelay)), tail])
    return ir / np.sqrt(np.sum(ir ** 2))


def lufs(x):
    """ITU-R BS.1770-4 integrated loudness (48 kHz), stereo."""
    b1 = [1.53512485958697, -2.69169618940638, 1.19839281085285]
    a1 = [1.0, -1.69065929318241, 0.73248077421585]
    b2 = [1.0, -2.0, 1.0]
    a2 = [1.0, -1.99004745483398, 0.99007225036621]
    y = signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=0), axis=0)
    blk, hop = ns(0.4), ns(0.1)
    zs = np.array([np.mean(y[i:i + blk] ** 2, axis=0).sum()
                   for i in range(0, len(y) - blk + 1, hop)])
    lk = -0.691 + 10 * np.log10(zs + 1e-20)
    zs = zs[lk > -70]
    if len(zs) == 0:
        return -70.0
    rel = -0.691 + 10 * np.log10(zs.mean()) - 10
    zs = zs[(-0.691 + 10 * np.log10(zs)) > rel]
    return -0.691 + 10 * np.log10(zs.mean())


def true_peak_track(x):
    """Per-sample peak of the 4x oversampled signal (max over channels)."""
    up = signal.resample_poly(x, 4, 1, axis=0)
    return np.abs(up).max(axis=1)[: len(x) * 4].reshape(len(x), 4).max(axis=1)


def limit(x, ceiling_db, look_ms=1.5, release_ms=120.0):
    c = 10 ** (ceiling_db / 20)
    det = true_peak_track(x)
    g = np.minimum(1.0, c / np.maximum(det, 1e-12))
    w = ns(look_ms / 1000)
    g = ndimage.minimum_filter1d(g, 2 * w + 1)
    g = ndimage.uniform_filter1d(g, w)
    g = np.minimum(g, np.minimum(1.0, c / np.maximum(det, 1e-12)))
    a = np.exp(-1 / (release_ms / 1000 * SR))
    out = np.empty_like(g)
    prev = 1.0
    for i in range(len(g)):
        v = g[i]
        prev = v if v < prev else v + a * (prev - v)
        out[i] = prev
    return x * out[:, None], out


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------
def render():
    dry = np.zeros((N, 2))
    send = np.zeros((N, 2))
    stems = []
    for idx, (frame, until, name, pan, gain_db, rev) in enumerate(CUES):
        fn = globals()[name]
        rng = np.random.default_rng(SEED * 1000 + idx)
        at = frame_sample(frame)
        n = frame_sample(until) - at if until else None
        res = fn(rng, n)
        x, pre = res if isinstance(res, tuple) else (res, 0)
        x = x * 10 ** (gain_db / 20)
        if x.ndim == 1:
            p = np.linspace(pan[0], pan[1], len(x)) if isinstance(pan, tuple) else np.full(len(x), pan)
            gl, gr = pan_gains(p)
            st = np.stack([x * gl, x * gr], axis=1)
        else:
            gl, gr = pan_gains(pan)
            st = x * np.array([gl, gr]) * np.sqrt(2)
        stem = np.zeros((N, 2))
        add(stem[:, 0], st[:, 0], at - pre)
        add(stem[:, 1], st[:, 1], at - pre)
        dry += stem
        send += stem * rev
        stems.append((frame, until, name, at, pre, stem))
    rr = np.random.default_rng(SEED)
    irl, irr = room_ir(rr), room_ir(rr)
    send = np.stack([highpass(send[:, c], 160) for c in range(2)], axis=1)  # keep the low end dry
    wet = np.stack([signal.fftconvolve(send[:, 0], irl)[:N],
                    signal.fftconvolve(send[:, 1], irr)[:N]], axis=1)
    mix = dry + wet
    t = tvec(N)
    rt = np.random.default_rng(SEED + 7)
    room = np.stack([highpass(lowpass(rt.standard_normal(N), 500, 1), 40) for _ in range(2)], axis=1)
    room /= np.sqrt(np.mean(room ** 2))
    room *= 10 ** (ROOM_TONE_DBFS / 20)
    room *= (smoothstep(t / 0.8) * (1 - smoothstep((t - (DUR - 0.12)) / 0.12)))[:, None]
    master_fade = (1 - smoothstep((t - (DUR - 0.03)) / 0.03))[:, None]

    g = 10 ** ((TARGET_LUFS - lufs(mix)) / 20)
    for _ in range(6):
        y, gr = limit(mix * g + room, CEILING_DBTP)
        y *= master_fade
        L = lufs(y)
        if abs(L - TARGET_LUFS) < 0.05:
            break
        g *= 10 ** ((TARGET_LUFS - L) / 20)
    # final safety: hard ceiling on true peak
    tp = true_peak_track(y).max()
    c = 10 ** (CEILING_DBTP / 20)
    if tp > c:
        y *= c / tp
    return y, g, gr, stems, lufs(y)


def write_wav24(path, x):
    x = np.clip(x, -1.0, 1.0 - 2 ** -23)
    q = np.round(x * 2 ** 23).astype(np.int32)
    b = q.astype("<i4").view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    data_len = len(b)
    hdr = b"RIFF" + struct.pack("<I", 36 + data_len) + b"WAVE"
    hdr += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 2, SR, SR * 6, 6, 24)
    hdr += b"data" + struct.pack("<I", data_len)
    with open(path, "wb") as fh:
        fh.write(hdr + b)


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------
def stem_onset(stem, at, pre):
    """Sample where the stem first reaches -12 dB of its own peak after its lead-in."""
    mono = np.abs(stem).max(axis=1)
    pk = mono.max()
    start = max(0, at - pre)
    if pre:
        start = at - ns(0.01)
    hits = np.nonzero(mono[start:] >= pk * 10 ** (-12 / 20))[0]
    return start + hits[0] if len(hits) else at


def stem_end(stem):
    mono = np.abs(stem).max(axis=1)
    idx = np.nonzero(mono >= mono.max() * 10 ** (-40 / 20))[0]
    return idx[-1] if len(idx) else 0


def mix_onsets(y):
    """Spectral-flux onsets of the final mix, in seconds."""
    mono = y.mean(axis=1)
    f, tt, Z = signal.stft(mono, fs=SR, nperseg=1024, noverlap=1024 - 240)
    mag = np.log1p(np.abs(Z) * 1000)
    flux = np.maximum(np.diff(mag, axis=1), 0).sum(axis=0)
    flux = flux / flux.max()
    thr = ndimage.uniform_filter1d(flux, 41) * 1.6 + 0.04
    peaks, _ = signal.find_peaks(flux, height=thr, distance=8)
    return tt[1:][peaks]


def write_png(path, rgb):
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[r].tobytes() for r in range(h))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


def cue_map_png(path, y, stems):
    """Top: mix envelope in dB. Below: one row per cue (table order), bar = stem
    extent, white tick = cue frame. Grid: 1 s lines, light 6-frame ticks."""
    W, top_h, row_h = 1800, 260, 22
    H = top_h + row_h * len(stems) + 10
    img = np.full((H, W, 3), 18, np.uint8)
    px = lambda s: min(W - 1, int(s / N * W))
    for f in range(1, 218, 6):
        img[:, px(frame_sample(f)), :] = 34
    for s in range(10):
        img[:, px(s * SR), :] = 70
    mono = np.abs(y).max(axis=1)
    cols = np.array_split(mono, W)
    for x, c in enumerate(cols):
        db = 20 * np.log10(c.max() + 1e-9)
        hgt = int(np.clip((db + 60) / 60, 0, 1) * (top_h - 10))
        img[top_h - hgt:top_h, x] = (200, 190, 170)
    palette = [(230, 120, 80), (120, 180, 230), (150, 220, 120), (230, 200, 90), (200, 130, 220)]
    for r, (frame, until, name, at, pre, stem) in enumerate(stems):
        y0 = top_h + 5 + r * row_h
        a, b = px(max(0, at - pre)), px(stem_end(stem))
        col = palette[r % len(palette)]
        img[y0 + 5:y0 + row_h - 5, a:b + 1] = col
        cx = px(at)
        img[y0:y0 + row_h, max(0, cx - 1):cx + 2] = 255
        img[:top_h, cx] = np.maximum(img[:top_h, cx], np.array(col, np.uint8) // 2)
    write_png(path, img)


def review(y, stems, gain, gr, measured):
    os.makedirs(REVIEW_DIR, exist_ok=True)
    onsets = mix_onsets(y)
    lines = ["Bad Omen ident sting cue list (24 fps, frame f starts at (f-1)/24 s)",
             "row  cue                 frame  until  seconds  stem_onset_ms  mix_onset_ms",
             "(stem_onset_ms: where the cue's own stem first reaches -12 dB of its peak,",
             " relative to the frame time; mix_onset_ms: nearest spectral-flux onset in",
             " the final mix within +-60 ms, '-' if masked or a soft swell)"]
    for r, (frame, until, name, at, pre, stem) in enumerate(stems):
        so = (stem_onset(stem, at, pre) - at) / SR * 1000
        sec = frame_start(frame)
        d = onsets - sec
        near = d[np.abs(d) <= 0.06]
        mo = "%+6.1f" % (near[np.argmin(np.abs(near))] * 1000) if len(near) else "     -"
        lines.append("%3d  %-18s  %5d  %5s  %7.3f  %+13.1f  %s" % (
            r + 1, name, frame, until if until else "-", sec, so, mo))
    lines.append("")
    lines.append("master gain %.2f dB, max limiter reduction %.2f dB, integrated %.2f LUFS (internal BS.1770)"
                 % (20 * np.log10(gain), abs(20 * np.log10(gr.min())), measured))
    with open(os.path.join(REVIEW_DIR, "sting-cues.txt"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    cue_map_png(os.path.join(REVIEW_DIR, "sting-cuemap.png"), y, stems)
    ff = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", WAV_PATH]
    subprocess.run(ff + ["-lavfi", "showspectrumpic=s=1800x700:mode=combined:legend=1:"
                         "fscale=log:scale=log:color=intensity:start=20:stop=20000",
                         os.path.join(REVIEW_DIR, "sting-spectrogram.png")], check=True)
    subprocess.run(ff + ["-lavfi", "showwavespic=s=1800x500:split_channels=1:scale=sqrt",
                         os.path.join(REVIEW_DIR, "sting-waveform.png")], check=True)
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--review", action="store_true", help="also write review images and cue list")
    args = ap.parse_args()
    y, gain, gr, stems, measured = render()
    assert y.shape == (N, 2)
    os.makedirs(OUT_DIR, exist_ok=True)
    write_wav24(WAV_PATH, y)
    print("wrote %s  (%d samples, %.3f s, %.2f LUFS internal, true peak %.2f dBTP)" % (
        WAV_PATH, len(y), len(y) / SR, measured, 20 * np.log10(true_peak_track(y).max())))
    if args.review:
        review(y, stems, gain, gr, measured)
    return 0


if __name__ == "__main__":
    sys.exit(main())
