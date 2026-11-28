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


LINE_GAIN = {"d04": 1.2}   # the last line sits under the sting; needs the push to keep its s


def main():
    score_p, out_p = sys.argv[1], sys.argv[2]
    ident_p = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "..", "..", "public", "kit", "v1", "ident", "ident.mp4")
    sc = read(score_p)
    n = len(sc)
    vo = np.zeros(n, dtype=np.float32)
    for shot, lid, off in T.VO:
        x = read(os.path.join(HERE, "vo", lid + ".wav"))[:, 0] * LINE_GAIN.get(lid, 1.0)
        i = int((T.START[shot] + off) * SR)
        vo[i:i + len(x)] += x[: n - i]
    env = np.abs(vo)
    env = signal.sosfilt(signal.butter(2, 14.0, "low", fs=SR, output="sos"), env)
    env = np.clip(env / 0.03, 0, 1)
    # hold the duck a little after each word so it does not pump between syllables
    k = int(0.25 * SR)
    env = signal.sosfilt(signal.butter(1, 3.0, "low", fs=SR, output="sos"), np.maximum.accumulate(env[::-1])[::-1] * 0 + env) if False else env
    hold = np.convolve(env, np.ones(k) / k, mode="same")
    env = np.maximum(env, hold * 1.0)
    duck = (1.0 - 0.86 * env).astype(np.float32)
    out = sc * duck[:, None] * 0.8
    # voices, centred, a touch of room
    ir = np.exp(-np.arange(int(0.35 * SR)) / (0.08 * SR)) * np.random.default_rng(3).standard_normal(int(0.35 * SR)) * 0.02
    wet = signal.fftconvolve(vo, ir)[:n]
    vo_m = (np.tanh(vo * 1.8) * 0.9 + wet * 0.35).astype(np.float32)
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
    pre = out_p + ".pre.wav"
    pcm = (out * 32767).astype("<i2")
    with wave.open(pre, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    # two-pass loudnorm: about -14 LUFS integrated, true peak under -1.5 dBTP
    import json, re
    f = "loudnorm=I=-14:TP=-1.5:LRA=11"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", pre, "-af", f + ":print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    m = json.loads(re.search(r"\{[^{}]*\}", r.stderr[r.stderr.rindex("{"):]).group(0))
    f2 = f + ":measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true" % (m["input_i"], m["input_tp"], m["input_lra"], m["input_thresh"], m["target_offset"])
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", pre, "-af", f2, "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le", out_p], check=True)
    os.remove(pre)
    print("mixed", out_p, round(n / SR, 1), "s; measured", m["input_i"], "LUFS, tp", m["input_tp"])


if __name__ == "__main__":
    main()
