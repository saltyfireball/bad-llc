"""Trailer render entry (BAD-857). Runs inside Blender, normally on kif:

  kif-render --dir tools/trailer tools/trailer/trailer.blend tools/trailer/render.py -- SHOT [preview] [f=A-B] [list=1,50] [stills]

SHOT is a shot id from shots.py (or a comma list); `preview` renders half
size at low samples; `f=A-B` renders only those frames; `list=` renders those
frames only. Frames land in $BLENDER_JOB_OUT/<shot>/frame_NNNN.png.
"""

import os
import sys
import time

import bpy

HERE = os.path.dirname(bpy.data.filepath) or os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import shots  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ids = argv[0].split(",") if argv else []
    preview = "preview" in argv
    fr = [a for a in argv if a.startswith("f=")]
    lst = [a for a in argv if a.startswith("list=")]
    out = os.environ.get("BLENDER_JOB_OUT", os.path.join(HERE, "out"))
    for sid in ids:
        sc, frames = shots.build(sid, preview)
        d = os.path.join(out, sid)
        os.makedirs(d, exist_ok=True)
        a, b = frames
        todo = list(range(a, b + 1))
        if fr:
            lo, hi = fr[0][2:].split("-")
            todo = list(range(int(lo), int(hi) + 1))
        if lst:
            todo = [int(x) for x in lst[0][5:].split(",")]
        t0 = time.time()
        for f in todo:
            sc.frame_set(f)
            sc.render.filepath = os.path.join(d, "frame_%04d.png" % f)
            t = time.time()
            bpy.ops.render.render(write_still=True)
            print("[trailer] %s frame %d %.2fs" % (sid, f, time.time() - t), flush=True)
        print("[trailer] %s done: %d frames in %.0fs" % (sid, len(todo), time.time() - t0), flush=True)


main()
