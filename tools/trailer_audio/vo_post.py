"""Pick the best Orpheus take of each line (whisper checks the words) and
dress each voice: gravel narrator, huge demon, old Crumb, bright heroes.

~/.venvs/claude/bin/python tools/trailer_audio/vo_post.py
Reads raw/<id>_<take>.wav, writes vo/<id>.wav (48 kHz mono) and vo/index.json
(id -> duration in seconds).
"""
import difflib, json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.expanduser("~/.local/share/whisper/ggml-large-v3-turbo-q5_0.bin")

# pitch factor, tempo after, extra filters
PROFILES = {
    "narr": (0.80, 0.96, "equalizer=f=110:t=h:w=120:g=7,equalizer=f=2800:t=q:w=1:g=3,"
                         "asoftclip=type=tanh:threshold=0.45,"
                         "acompressor=threshold=0.05:ratio=6:attack=5:release=90:makeup=4,"
                         "aecho=0.8:0.6:70|140:0.22|0.1"),
    "demon": (0.58, 0.9, "equalizer=f=70:t=h:w=100:g=9,asoftclip=type=tanh:threshold=0.35,"
                         "acompressor=threshold=0.05:ratio=8:attack=5:release=120:makeup=5,"
                         "aecho=0.8:0.7:90|210|350:0.35|0.22|0.12"),
    "crumb": (0.9, 0.9, "tremolo=f=5.5:d=0.18,lowpass=f=5200,highpass=f=120,"
                        "acompressor=threshold=0.05:ratio=4:makeup=3,aecho=0.8:0.5:50:0.2"),
    "vanilla": (1.0, 1.0, "highpass=f=90,acompressor=threshold=0.05:ratio=4:makeup=3,aecho=0.8:0.5:45:0.15"),
    "velvet": (0.97, 1.0, "highpass=f=90,acompressor=threshold=0.05:ratio=4:makeup=3,aecho=0.8:0.5:45:0.15"),
    "funfetti": (0.97, 1.0, "highpass=f=90,acompressor=threshold=0.05:ratio=4:makeup=3,aecho=0.8:0.5:45:0.15"),
}
WHISPER_LINES = {"v05": "volume=0.55,lowpass=f=4500,aecho=0.8:0.6:60|120:0.3|0.15"}


def norm(s):
    return re.sub(r"[^a-z ]", "", s.lower().replace("-", " ")).split()


def transcribe(path):
    with tempfile.TemporaryDirectory() as d:
        wav = os.path.join(d, "a.wav")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", path, "-ar", "16000", "-ac", "1", wav], check=True)
        r = subprocess.run(["whisper-cli", "-m", MODEL, "-f", wav, "-nt", "-np"], capture_output=True, text=True)
        return r.stdout.strip()


def main():
    lines = json.load(open(os.path.join(HERE, "lines.json")))
    os.makedirs(os.path.join(HERE, "vo"), exist_ok=True)
    index = {}
    for ln in lines:
        best, score = None, -1
        for t in range(3):
            p = os.path.join(HERE, "raw", "%s_%d.wav" % (ln["id"], t))
            if not os.path.exists(p):
                continue
            heard = transcribe(p)
            s = difflib.SequenceMatcher(None, norm(heard), norm(ln["text"])).ratio()
            print(ln["id"], t, round(s, 2), repr(heard), flush=True)
            if s > score:
                best, score = p, s
        pitch, tempo, extra = PROFILES[ln["who"]]
        extra = WHISPER_LINES.get(ln["id"], extra)
        out = os.path.join(HERE, "vo", ln["id"] + ".wav")
        chain = ("silenceremove=start_periods=1:start_threshold=-45dB,"
                 "asetrate=%d,aresample=48000,atempo=%.4f,%s,alimiter=limit=0.9"
                 % (int(24000 * pitch), tempo / pitch, extra))
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", best, "-af", chain, "-ar", "48000", "-ac", "1", out], check=True)
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out],
                                 capture_output=True, text=True).stdout)
        index[ln["id"]] = round(d, 3)
    json.dump(index, open(os.path.join(HERE, "vo", "index.json"), "w"), indent=1)
    print(index)


if __name__ == "__main__":
    main()
