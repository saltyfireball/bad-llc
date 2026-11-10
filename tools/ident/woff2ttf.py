"""Convert a woff2 font to ttf so Blender can load it.

Run with fontTools available:
  uv run --with fonttools --with brotli python tools/ident/woff2ttf.py IN.woff2 OUT.ttf
"""
import sys

from fontTools.ttLib import TTFont


def main():
    src, dst = sys.argv[1], sys.argv[2]
    font = TTFont(src)
    font.flavor = None
    font.save(dst)


if __name__ == "__main__":
    main()
