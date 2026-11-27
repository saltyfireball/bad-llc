"""Lay the voices on the score, with the ident's own sound up front (BAD-857).

  ~/.venvs/claude/bin/python tools/trailer_audio/mix.py SCORE.wav OUT.wav [IDENT.mp4]

The score ducks under each voice line; the ident plays straight for 8 s.
"""
import os, subprocess, sys, tempfile, wave
import numpy as np
from scipy import signal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "trailer"))
import timeline as T  # noqa: E402

SR = 48000


def read(path):
    with wave.open(path, "rb") as w:
        ch = w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    return x.reshape(-1, ch)


def main():
    score_p, out_p = sys.argv[1], sys.argv[2]
    ident_p = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "..", "..", "public", "kit", "v1", "ident", "ident.mp4")
    sc = read(score_p)
    n = len(sc)
    vo = np.zeros(n, dtype=np.float32)
    for shot, lid, off in T.VO:
        x = read(os.path.join(HERE, "vo", lid + ".wav"))[:, 0]
        i = int((T.START[shot] + off) * SR)
        vo[i:i + len(x)] += x[: n - i]
    env = np.abs(vo)
    sos = signal.butter(2, 6.0, "low", fs=SR, output="sos")
    env = signal.sosfilt(sos, env)
    env = np.clip(env / 0.12, 0, 1)
    duck = (1.0 - 0.45 * env).astype(np.float32)
    out = sc * duck[:, None] * 0.85
    # voices, centred, a touch of room
    ir = np.exp(-np.arange(int(0.35 * SR)) / (0.08 * SR)) * np.random.default_rng(3).standard_normal(int(0.35 * SR)) * 0.02
    wet = signal.fftconvolve(vo, ir)[:n]
    vo_m = (vo * 1.0 + wet * 0.5).astype(np.float32)
    out[:, 0] += vo_m
    out[:, 1] += vo_m
    # the ident, straight: first 8 s of its own sound, faded over the last half second
    with tempfile.TemporaryDirectory() as d:
        wv = os.path.join(d, "ident.wav")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", ident_p, "-t", "8", "-ar", str(SR), "-ac", "2", wv], check=True)
        idt = read(wv)
    m = min(len(idt), n)
    f = np.ones(m, dtype=np.float32)
    k = int(0.5 * SR)
    f[int(8.0 * SR) - k: int(8.0 * SR)] = np.linspace(1, 0, k) if m >= int(8.0 * SR) else 1
    out[:m] += idt[:m] * f[:, None] * 1.0
    pk = np.max(np.abs(out))
    out = np.tanh(out * 0.9) / np.tanh(0.9)
    out *= 0.89 / max(np.max(np.abs(out)), 1e-6)
    pcm = (out * 32767).astype("<i2")
    with wave.open(out_p, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("mixed", out_p, round(n / SR, 1), "s, pre-limit peak", round(float(pk), 2))


if __name__ == "__main__":
    main()
