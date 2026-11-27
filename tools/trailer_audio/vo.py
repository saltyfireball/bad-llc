"""Raw Orpheus takes for the trailer VO (BAD-857).

Orpheus runs on kif (llama-server :8090); SNAC decodes here with mlx-audio.
Run with ~/.venvs/claude/bin/python tools/trailer_audio/vo.py [--takes N]
Writes tools/trailer_audio/raw/<id>_<take>.wav (24 kHz mono).
"""
import json, os, sys, urllib.request, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
KIF = os.environ.get("ORPHEUS_URL", "http://192.168.1.128:8090")
VOICES = {"narr": "leo", "vanilla": "tara", "velvet": "mia", "funfetti": "jess",
          "crumb": "dan", "demon": "leo"}


def tokens(line, speaker, seed):
    body = {"prompt": [128259, 128000, "%s: %s" % (speaker, line), 128009, 128260],
            "n_predict": 2000, "stream": True, "return_tokens": True, "cache_prompt": False,
            "temperature": 0.6, "top_p": 0.8, "top_k": 0, "min_p": 0, "repeat_penalty": 1.3,
            "repeat_last_n": 20, "seed": seed}
    req = urllib.request.Request(KIF + "/completion", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    out = []
    with urllib.request.urlopen(req, timeout=120) as r:
        for raw in r:
            if not raw.startswith(b"data: "):
                continue
            chunk = json.loads(raw[6:])
            out += chunk.get("tokens") or []
            if chunk.get("stop"):
                break
    return out


def decode(toks, snac):
    import mlx.core as mx
    codes = [t - 128266 for t in toks if t >= 128266]
    codes = codes[:len(codes) // 7 * 7]
    c = np.asarray(codes, dtype=np.int64).reshape(-1, 7) - np.arange(7) * 4096
    c = np.clip(c, 0, 4095)
    layers = [mx.array(c[:, cols].reshape(-1))[None, :] for cols in ([0], [1, 4], [2, 3, 5, 6])]
    return np.asarray(snac.decode(layers)).reshape(-1)


def write(path, audio):
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(pcm.tobytes())


def main():
    takes = int(sys.argv[sys.argv.index("--takes") + 1]) if "--takes" in sys.argv else 3
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    from mlx_audio.tts.models.llama.llama import snac_model
    os.makedirs(os.path.join(HERE, "raw"), exist_ok=True)
    for ln in json.load(open(os.path.join(HERE, "lines.json"))):
        if only and ln["id"] not in only:
            continue
        for t in range(takes):
            p = os.path.join(HERE, "raw", "%s_%d.wav" % (ln["id"], t))
            if os.path.exists(p):
                continue
            a = decode(tokens(ln["text"], VOICES[ln["who"]], 1000 * t + hash(ln["id"]) % 997), snac_model)
            write(p, a)
            print(ln["id"], t, round(len(a) / 24000, 2), "s", flush=True)


if __name__ == "__main__":
    main()
