"""The deploy's duet stamping (SLRM-1925): every clip, still and atlas goes up under a content-hashed name.

Run: python3 -m unittest discover tests
"""
import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import stamp_duet  # noqa: E402

PUBLIC = ROOT / "public"
KIT_FILE = re.compile(r"^[\w@][\w@.-]*$")


def strings(node):
    return list(stamp_duet.strings(node))


class StampTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.stage = self.tmp / "stage"
        shutil.copytree(PUBLIC, self.stage)
        self.duet = json.loads((self.stage / "duet" / "duet.json").read_text())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def sides(self):
        for side in ("left", "right"):
            path = self.stage / "duet" / self.duet[side]
            yield path.parent, json.loads(path.read_text())

    def test_every_media_file_is_named_by_its_content(self):
        stamp_duet.stamp(self.stage)
        for folder, manifest in self.sides():
            media = [f for f in folder.iterdir() if f.suffix in stamp_duet.MEDIA]
            self.assertTrue(media)
            named = set(strings(manifest))
            for f in media:
                stem, digest = f.stem.rsplit(".", 1)
                self.assertEqual(digest, hashlib.sha256(f.read_bytes()).hexdigest()[:12], f.name)
                self.assertIn(f.name, named, f"{folder.name}/{f.name} is not in its manifest")
                self.assertRegex(f.name, KIT_FILE)
            for name in named:
                if Path(name).suffix in stamp_duet.MEDIA:
                    self.assertTrue((folder / name).is_file(), f"{folder.name} manifest names missing {name}")

    def test_pages_point_at_the_stamped_stills(self):
        moved = stamp_duet.stamp(self.stage)
        html = (self.stage / "index.html").read_text()
        for old, new in moved.items():
            if "/rest" in old:
                self.assertIn(new, html)
        self.assertEqual(re.findall(r"duet/\w+/rest(?:@2x)?\.webp", html), [], "an unstamped still is left on the page")

    def test_changed_content_changes_the_url(self):
        # The SLRM-1925 bug: a new bake under the same URL. A changed clip must get a new name.
        before = stamp_duet.stamp(self.stage)
        other = self.tmp / "other"
        shutil.copytree(PUBLIC, other)
        clip = other / "duet" / "carrie" / "glare.mp4"
        clip.write_bytes(clip.read_bytes() + b"\0")
        after = stamp_duet.stamp(other)
        self.assertNotEqual(before["duet/carrie/glare.mp4"], after["duet/carrie/glare.mp4"])
        self.assertEqual(before["duet/carrie/roll.mp4"], after["duet/carrie/roll.mp4"])

    def test_deploy_stamps_the_stage(self):
        deploy = (ROOT / "deploy.sh").read_text()
        self.assertIn('python3 tools/stamp_duet.py "$stage"', deploy)
        self.assertLess(deploy.index("stamp_duet.py"), deploy.index("pages deploy"))

    def test_unnamed_media_is_refused(self):
        (self.stage / "duet" / "carrie" / "stray.webp").write_bytes(b"x")
        with self.assertRaises(stamp_duet.StampError):
            stamp_duet.stamp(self.stage)


if __name__ == "__main__":
    unittest.main()
