"""Give every duet media file a content-hashed name in a staged copy of public/ (SLRM-1925).

Cloudflare gives .mp4 and .webp a 4 hour browser cache on bad.llc whatever _headers says,
while the HTML and JSON are never cached. With fixed names, a redeploy left browsers playing
a cached clip from one bake against a cached still from another (Carrie's shirt jumped
mid-bit). So deploy.sh runs this on its staging copy: each clip, still and atlas becomes
NAME.HASH.EXT (12 hex of its sha256), and the manifests and the pages that name them are
rewritten. Changed content is a new URL; unchanged content keeps its URL and its cache.

The new names pass the kit's file check (letters, digits, @ . _ -), so the player is unchanged.

usage: python3 tools/stamp_duet.py STAGE     (STAGE is the copy of public/ about to be uploaded)
"""

import hashlib
import json
import re
import sys
from pathlib import Path

MEDIA = {".mp4", ".webp"}
KIT_FILE = re.compile(r"^[\w@][\w@.-]*$")   # portrait-core.js file(): what a manifest may name


class StampError(RuntimeError):
    pass


def hashed(path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    return "%s.%s%s" % (path.stem, digest, path.suffix)


def rename_in(node, names):
    """The manifest with every string that is a key of names replaced by its value."""
    if isinstance(node, dict):
        return {k: rename_in(v, names) for k, v in node.items()}
    if isinstance(node, list):
        return [rename_in(v, names) for v in node]
    if isinstance(node, str) and node in names:
        return names[node]
    return node


def strings(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from strings(v)
    elif isinstance(node, str):
        yield node


def stamp(stage):
    """Rename the duet media under stage/duet and rewrite the manifests and pages. Returns {old path: new path}."""
    stage = Path(stage)
    duet_dir = stage / "duet"
    duet = json.loads((duet_dir / "duet.json").read_text())
    moved = {}
    for side in ("left", "right"):
        manifest_path = duet_dir / duet[side]
        folder = manifest_path.parent
        manifest = json.loads(manifest_path.read_text())
        named = set(strings(manifest))
        media = sorted(f for f in folder.iterdir() if f.is_file() and f.suffix in MEDIA)
        unnamed = [f.name for f in media if f.name not in named]
        if unnamed:
            raise StampError("%s has media its manifest does not name: %s" % (folder.name, ", ".join(unnamed)))
        names = {}
        for f in media:
            new = hashed(f)
            if not KIT_FILE.match(new):
                raise StampError("%s would fail the kit's file check" % new)
            f.rename(folder / new)
            names[f.name] = new
            moved["duet/%s/%s" % (folder.name, f.name)] = "duet/%s/%s" % (folder.name, new)
        manifest_path.write_text(json.dumps(rename_in(manifest, names), separators=(",", ":")))
    # The pages name the stills directly (src and srcset): rewrite every exact duet/<side>/<file> path.
    pattern = re.compile(r"(?<![\w/.@-])/?(%s)(?![\w.@-])" % "|".join(re.escape(k) for k in sorted(moved, key=len, reverse=True)))
    for page in stage.glob("*.html"):
        text = page.read_text()
        new = pattern.sub(lambda m: m.group(0).replace(m.group(1), moved[m.group(1)]), text)
        if new != text:
            page.write_text(new)
    return moved


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        for old, new in stamp(sys.argv[1]).items():
            print("%s -> %s" % (old, new))
    except (StampError, OSError, KeyError, ValueError) as e:
        sys.exit("stamp_duet: %s" % e)
