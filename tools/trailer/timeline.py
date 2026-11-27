"""The cut: shot order, durations and where each voice line starts (BAD-857).

Seconds at 24 fps. Starts are chained from the durations. Shared by the
Blender shot builders (lip flaps, camera cuts) and edit.py.
"""

FPS = 24

SEQ = [
    ("ident", 8.0), ("city", 6.0), ("horns", 5.0), ("bakery", 6.0), ("eyes", 3.0),
    ("card_summer", 2.0), ("vanilla", 5.0), ("velvet", 8.6), ("funfetti", 5.0), ("stage", 5.4),
    ("crumb", 7.4), ("card_evil", 2.0), ("demon", 10.4), ("card_feed", 2.0),
    ("walk", 3.5), ("sword", 2.5), ("fly", 2.5), ("headbutt", 2.5), ("rolldown", 3.5), ("roof", 8.0),
    ("finale", 6.0), ("gap1", 0.5), ("title", 7.5), ("stinger", 9.5), ("card_rating", 2.0),
]

# (shot, line id, offset into the shot in seconds)
VO = [
    ("city", "n01", 1.0), ("horns", "n02", 0.6), ("bakery", "n03", 0.6),
    ("vanilla", "v01", 2.4),
    ("velvet", "r01", 0.5), ("velvet", "v02", 4.5), ("velvet", "r02", 6.8),
    ("funfetti", "f01", 2.2), ("stage", "n04", 1.0), ("crumb", "c01", 2.2),
    ("demon", "d01", 1.2), ("demon", "d02", 5.2), ("demon", "v03", 6.8), ("demon", "d03", 9.0),
    ("roof", "r03", 1.3), ("roof", "v04", 4.2), ("finale", "v05", 1.8),
    ("title", "n05", 2.0), ("stinger", "d04", 6.3),
]

START = {}
DUR = {}
_t = 0.0
for _n, _d in SEQ:
    START[_n] = _t
    DUR[_n] = _d
    _t += _d
TOTAL = _t


def frames(name):
    return int(round(DUR[name] * FPS))


def lines(name):
    """[(line id, offset seconds)] for a shot."""
    return [(i, o) for s, i, o in VO if s == name]


# seconds of each processed VO line (tools/trailer_audio/vo/index.json)
LINE_DUR = {"n01": 1.239, "n02": 1.544, "n03": 1.842, "v01": 2.013, "r01": 3.295, "v02": 1.976, "r02": 1.609, "f01": 1.604, "n04": 3.874, "c01": 3.209, "d01": 2.702, "d02": 1.16, "v03": 2.078, "d03": 1.322, "r03": 1.463, "v04": 3.443, "v05": 1.153, "n05": 3.977, "d04": 1.478}


def line_dur(i):
    return LINE_DUR[i]
