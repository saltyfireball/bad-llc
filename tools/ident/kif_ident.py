"""Render the bad.llc ident frames on kif at native 1080p (BAD-891).

  kif-render --dir STAGE STAGE/tools/ident/stage.blend STAGE/tools/ident/kif_ident.py -- 1-192

STAGE holds tools/ident/*.py + characters.blend, public/img/wordmark.svg and
the converted Spectral ttf in tools/ident/out/fonts. The job's input folder is
read-only, so the wrapper copies it into $BLENDER_JOB_OUT/work and runs scene.py there.
"""
import os, shutil, subprocess, sys
import bpy

here = os.path.dirname(bpy.data.filepath)
out = os.environ["BLENDER_JOB_OUT"]
stage = os.path.dirname(os.path.dirname(here))
work = os.path.join(out, "work")
shutil.copytree(stage, work, ignore=shutil.ignore_patterns("kif-render", "_kif_render"))
rng = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "1-192"
r = subprocess.run([bpy.app.binary_path, "-b", "--factory-startup", "-P", os.path.join(work, "tools", "ident", "scene.py"),
                    "--", "--render", "--frames", rng, "--out", os.path.join(out, "ident")])
shutil.rmtree(work, ignore_errors=True)
sys.exit(r.returncode)
