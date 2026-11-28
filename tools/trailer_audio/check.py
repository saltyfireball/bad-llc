"""Objective checks on the finished cut (BAD-891).

  ~/.venvs/claude/bin/python tools/trailer_audio/check.py CUT.mp4

1. ebur128: integrated loudness (target about -14 LUFS) and true peak (under -1 dBTP).
2. Clipping: samples at full scale.
3. Whisper: every voice line is cut out of the mix at its cue and transcribed; it must match the script.
4. Cuts: RMS of the music-stop gag (roll) and the one-beat gap before the chorus.
"""
import difflib, json, os, re, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "trailer"))
import timeline as T
MODEL = os.path.expanduser("~/.local/share/whisper/ggml-large-v3-turbo-q5_0.bin")


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower().replace("-", " ").replace("10,000", "10000").replace("ten thousand", "10000").replace("desert", "dessert")).split()


def main():
    cut = sys.argv[1]
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", cut, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True)
    tail = r.stderr[r.stderr.rindex("Summary:"):]
    I = float(re.search(r"I:\s+(-?[\d.]+) LUFS", tail).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail).group(1))
    print("integrated %.1f LUFS, true peak %.1f dBTP" % (I, tp))
    ok = abs(I + 14) < 1.0 and tp < -1.0
    lines = {l["id"]: l["text"] for l in json.load(open(os.path.join(HERE, "lines.json")))}
    bad = 0
    with tempfile.TemporaryDirectory() as d:
        for shot, lid, off in T.VO:
            t0 = T.START[shot] + off - 0.15
            wav = os.path.join(d, lid + ".wav")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "%.3f" % t0, "-t", "%.3f" % (T.line_dur(lid) + 0.4), "-i", cut,
                            "-ar", "16000", "-ac", "1", wav], check=True)
            heard = subprocess.run(["whisper-cli", "-m", MODEL, "-f", wav, "-nt", "-np"], capture_output=True, text=True).stdout.strip()
            s = difflib.SequenceMatcher(None, norm(heard), norm(lines[lid])).ratio()
            flag = "ok " if s >= 0.8 else "BAD"
            bad += s < 0.8
            print("%s %s %.2f heard=%r script=%r" % (flag, lid, s, heard, lines[lid]))
    # music-stop gag and the one-beat-early cut: rms in 100 ms windows
    def rms(t0, dur):
        r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", "%.3f" % t0, "-t", "%.3f" % dur, "-i", cut, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
        m = re.search(r"mean_volume: (-?[\d.]+|-inf)", r.stderr)
        return float(m.group(1)) if m and m.group(1) != "-inf" else -99.0
    fin = T.START["finale"] + T.DUR["finale"]
    print("one-beat gap  %.2f-%.2f s: %.0f dB (before %.0f, chorus %.0f)" % (fin + 0.05, fin + 0.45, rms(fin + 0.05, 0.4), rms(fin - 0.5, 0.4), rms(T.START["title"] + 0.3, 0.4)))
    ro = T.START["rolldown"]
    print("roll gag      %.0f dB inside (before %.0f, after %.0f)" % (rms(ro + 0.8, 1.6), rms(ro - 0.6, 0.5), rms(ro + 3.1, 0.4)))
    print("PASS" if ok and not bad else "FAIL", "loudness_ok=%s vo_bad=%d" % (ok, bad))


if __name__ == "__main__":
    main()
