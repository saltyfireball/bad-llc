"""Duet checks (SLRM-1921): size budget, manifest files, the page wiring, no model files in public/.

Run: python3 -m unittest discover tests
"""
import json
import unittest
from pathlib import Path

PUBLIC = Path(__file__).resolve().parent.parent / "public"
DUET = PUBLIC / "duet"
BUDGET = 2_621_440  # 2.5 MB for everything in public/duet/, both sides together (SLRM-1951)
PRIVATE = {".vrm", ".glb", ".gltf", ".fbx", ".blend", ".bvh"}


def manifest_paths(node):
    """Every string in the manifest that names a file (has an extension)."""
    if isinstance(node, dict):
        for value in node.values():
            yield from manifest_paths(value)
    elif isinstance(node, list):
        for value in node:
            yield from manifest_paths(value)
    elif isinstance(node, str) and "." in node and "/" not in node.lstrip("./") and not node.startswith("#"):
        if node.rsplit(".", 1)[-1].isalnum() and not node.replace(".", "").isdigit():
            yield node


class DuetTest(unittest.TestCase):
    def setUp(self):
        self.duet = json.loads((DUET / "duet.json").read_text())
        self.sides = {s: json.loads((DUET / self.duet[s]).read_text()) for s in ("left", "right")}

    def test_budget(self):
        total = sum(f.stat().st_size for f in DUET.rglob("*") if f.is_file())
        self.assertLessEqual(total, BUDGET, f"public/duet is {total} bytes")

    def test_manifest_files_exist(self):
        for side, manifest in self.sides.items():
            folder = (DUET / self.duet[side]).parent
            names = set(manifest_paths(manifest))
            self.assertTrue(names, f"{side} manifest names no files")
            for name in sorted(names):
                self.assertTrue((folder / name).is_file(), f"{side} manifest names missing file {name}")

    def test_bits_pair_clips_of_equal_length(self):
        self.assertTrue(self.duet["bits"])
        for bit in self.duet["bits"]:
            for side in ("left", "right"):
                clip = self.sides[side]["clips"].get(bit[side])
                self.assertIsNotNone(clip, f"{bit['name']}: no {side} clip {bit[side]}")
                self.assertEqual(clip["duration"], bit["duration"], f"{bit['name']} {side}")

    def test_stills_on_the_page(self):
        html = (PUBLIC / "index.html").read_text()
        for side in ("left", "right"):
            folder = self.duet[side].split("/")[0]
            for name in ("rest.webp", "rest@2x.webp"):
                self.assertTrue((DUET / folder / name).is_file(), f"{folder}/{name}")
                self.assertIn(f"duet/{folder}/{name}", html)
        self.assertIn('data-duet="duet/duet.json"', html)

    def test_csp_allows_self_media_only(self):
        csp = (PUBLIC / "_headers").read_text()
        self.assertIn("media-src 'self'", csp)
        self.assertIn("script-src 'self';", csp)
        self.assertIn("no-transform", csp)

    def test_no_model_files(self):
        found = [str(f.relative_to(PUBLIC)) for f in PUBLIC.rglob("*") if f.suffix.lower() in PRIVATE]
        self.assertEqual(found, [], "model or mocap files must never be public")


if __name__ == "__main__":
    unittest.main()
