"""Assemble the teaser from the rendered frames, the cards and the mix (BAD-857).

  ~/.venvs/claude/bin/python tools/trailer/edit.py MIX.wav OUT.mp4 [--frames DIR] [--only shot,shot]

Frames come from tools/trailer/kr.sh (DIR/<shot>/frame_NNNN.png). Needs ffmpeg and Pillow.
The bad.llc ident plays straight for 8 s (the web copy in public/kit/v1/ident,
scaled up) and one sprinkle drops through its last frame.
"""
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import timeline as T  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
IDENT = os.path.join(REPO, "public", "kit", "v1", "ident", "ident.mp4")
FONT = "/System/Library/Fonts/Supplemental/Copperplate.ttc"
BONE = (232, 226, 214)
W, H = 1920, 1080
FPS = 24
ENC = ["-c:v", "libx264", "-crf", "15", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "24", "-g", "48"]
FINISH = "vignette=PI/6,noise=alls=3:allf=t"

CARDS = {
    "card_summer": ["THIS SUMMER"],
    "card_evil": ["AN ANCIENT EVIL"],
    "card_feed": ["HAS RETURNED TO FEED"],
    "card_rating": ["Rated PG-13 for intense sugar", "and brief crumbling."],
}
NAMES = {  # shot -> (name, role, start s, end s)
    "vanilla": ("VANILLA", "THE LEADER", 0.5, 2.3),
    "velvet": ("RED VELVET", "THE BRAINS", 0.4, 2.2),
    "funfetti": ("FUNFETTI", "THE LOOSE CANNON", 0.5, 2.1),
}


def font(size):
    return ImageFont.truetype(FONT, size)


def spaced(draw, xy, text, fnt, fill, track):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + track


def text_width(draw, text, fnt, track):
    return sum(draw.textlength(c, font=fnt) + track for c in text) - track


def card_png(path, lines, size=92, track=14):
    im = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(im)
    fnt = font(size if len(lines) == 1 else 54)
    th = len(lines) * (fnt.size * 1.45)
    y = (H - th) / 2
    for ln in lines:
        w = text_width(d, ln, fnt, track if len(lines) == 1 else 6)
        spaced(d, ((W - w) / 2, y), ln, fnt, BONE, track if len(lines) == 1 else 6)
        y += fnt.size * 1.45
    im.save(path)


def name_png(path, name, role):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    f1, f2 = font(120), font(40)
    spaced(d, (150, H - 360), name, f1, BONE + (255,), 18)
    spaced(d, (156, H - 215), role, f2, (200, 160, 90, 255), 16)
    im.save(path)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("ffmpeg failed:\n" + " ".join(cmd) + "\n" + r.stderr[-1500:])


def frames_in(frames, shot, n):
    d = os.path.join(frames, shot)
    have = len([f for f in os.listdir(d) if f.startswith("frame_")]) if os.path.isdir(d) else 0
    if have < n:
        raise SystemExit("%s: %d of %d frames in %s" % (shot, have, n, d))
    return os.path.join(d, "frame_%04d.png")


def main():
    args = sys.argv[1:]
    mix, out = args[0], args[1]
    frames = os.path.expanduser(args[args.index("--frames") + 1]) if "--frames" in args else os.path.expanduser("~/.local/share/cpdh-trailer/frames")
    only = args[args.index("--only") + 1].split(",") if "--only" in args else None
    work = os.path.expanduser("~/.local/share/cpdh-trailer/edit")
    os.makedirs(work, exist_ok=True)
    segs = []
    for name, dur in T.SEQ:
        if only and name not in only:
            continue
        n = int(round(dur * FPS))
        seg = os.path.join(work, name + ".mp4")
        if name == "ident":
            spr = frames_in(frames, "sprinkle", 20) if os.path.isdir(os.path.join(frames, "sprinkle")) else None
            if spr:
                run(["ffmpeg", "-loglevel", "error", "-y", "-i", IDENT, "-framerate", "24", "-start_number", "1", "-i", spr,
                     "-filter_complex", "[0:v]scale=1920:1080:flags=lanczos,fps=24[a];[1:v]format=rgba,setpts=PTS+6.7/TB[b];[a][b]overlay=eof_action=pass:format=auto[v]",
                     "-map", "[v]", "-frames:v", str(n), "-an"] + ENC + [seg])
            else:
                run(["ffmpeg", "-loglevel", "error", "-y", "-i", IDENT, "-vf", "scale=1920:1080:flags=lanczos,fps=24", "-frames:v", str(n), "-an"] + ENC + [seg])
        elif name in CARDS:
            png = os.path.join(work, name + ".png")
            card_png(png, CARDS[name])
            fo = dur - 0.35
            run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "24", "-i", png, "-frames:v", str(n),
                 "-vf", "fade=t=in:st=0.1:d=0.3,fade=t=out:st=%.2f:d=0.3" % fo, "-an"] + ENC + [seg])
        elif name == "gap1":
            run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=24", "-frames:v", str(n), "-an"] + ENC + [seg])
        else:
            pat = frames_in(frames, name, n if name != "stinger" else int(8.2 * FPS))
            vf = FINISH
            inp = ["-framerate", "24", "-start_number", "1", "-i", pat]
            if name == "city":
                vf += ",fade=t=in:st=0:d=1.2"
            elif name == "eyes":
                vf += ",fade=t=out:st=%.2f:d=0.4" % (dur - 0.45)
            elif name == "crumb":
                vf += ",fade=t=in:st=0:d=0.4"
            elif name == "stinger":
                cut = int(round(8.2 * FPS))
                vf += ",tpad=stop_mode=add:stop_duration=%.3f:color=black" % (dur - 8.2)
                inp += ["-frames:v", str(cut)]
            if name in NAMES:
                nm, role, a, b = NAMES[name]
                png = os.path.join(work, name + "_name.png")
                name_png(png, nm, role)
                run(["ffmpeg", "-loglevel", "error", "-y"] + inp + ["-loop", "1", "-framerate", "24", "-i", png,
                     "-filter_complex", "[0:v]%s[a];[1:v]format=rgba,fade=t=in:st=%.2f:d=0.25:alpha=1,fade=t=out:st=%.2f:d=0.25:alpha=1[b];[a][b]overlay=shortest=0[v]" % (vf, a, b - 0.25),
                     "-map", "[v]", "-frames:v", str(n), "-an"] + ENC + [seg])
            else:
                if name != "stinger":
                    inp += ["-frames:v", str(n)]
                run(["ffmpeg", "-loglevel", "error", "-y"] + inp + ["-vf", vf, "-frames:v", str(n), "-an"] + ENC + [seg])
        segs.append(seg)
        print("segment", name, n, "frames", flush=True)
    lst = os.path.join(work, "concat.txt")
    with open(lst, "w") as f:
        for s in segs:
            f.write("file '%s'\n" % s)
    silent = os.path.join(work, "video.mp4")
    run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])
    run(["ffmpeg", "-loglevel", "error", "-y", "-i", silent, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "21", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-af", "loudnorm=I=-14:TP=-1.5:LRA=14", "-ar", "48000", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", out])
    print("wrote", out)


if __name__ == "__main__":
    main()
