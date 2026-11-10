"""Keying helpers for the Bad Omen ident characters (SLRM-1922).

Import from scene.py (Blender's Python), after the characters are appended:

    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import rigs
    roots = rigs.append_characters()          # {'raven': obj, 'cat': obj}
    raven, cat = roots['raven'], roots['cat']

The rig internals are documented in characters.py. Every helper takes the
character's root Empty (RAVEN_ROOT or CAT_ROOT, or whatever name it got on
append) and finds the rest by the custom property "bo_role" on each object,
so a renamed copy (RAVEN_ROOT.001) still works.

All helpers key every frame they touch (dense keys, no fcurve handles to
fight), so they are deterministic and can be called in any order. Channels:

    key_raven_walk     root location + rotation_euler.z, body loc/rot,
                       head location, foot_ik.L/.R location + rotation
    key_head_turn      head rotation_euler only
    key_tail_flick     tail rotation_euler only
    key_umbrella_open  RAVEN_ROOT["umbrella_open"] only
    key_umbrella_visible  hide_render/hide_viewport of the umbrella parts
    key_cat_bound      cat root location + rotation_euler.z + ["bound"]

Signatures:

    append_characters(path=None, scene=None) -> {'raven': obj, 'cat': obj}
    raven_rig(root) -> armature object
    key_raven_walk(root, start_frame, end_frame, start_xy, end_xy,
                   step_frames=6, first_step=None, ground_z=None,
                   lift=0.022, bob=0.006, head_bob=True) -> list of contact frames
    key_raven_pose_neutral(root, frame)
    yaw_to_face(root, frame, target_xyz) -> degrees for key_head_turn
    key_head_turn(root, start_frame, end_frame, yaw_deg, pitch_deg=0.0,
                  roll_deg=0.0, from_deg=(0.0, 0.0, 0.0))
    key_tail_flick(root, frame, angle_deg=35.0, axis='yaw', frames=8)
    key_umbrella_open(root, frame, frames=5)
    key_umbrella_visible(root, frame, visible)
    key_cat_bound(root, start_frame, end_frame, start_xy, end_xy,
                  stride_frames=6, ground_z=None, bob=0.035)
"""

import math
import os

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BLEND = os.path.join(HERE, "characters.blend")


# ---------------------------------------------------------------- lookup

def _children(root):
    return list(root.children_recursive)


def _by_role(root, role):
    for ob in [root] + _children(root):
        if ob.get("bo_role") == role:
            return ob
    raise KeyError("no object with bo_role=%r under %s" % (role, root.name))


def _all_by_role_prefix(root, prefix):
    return [ob for ob in [root] + _children(root)
            if str(ob.get("bo_role", "")).startswith(prefix)]


def raven_rig(root):
    return _by_role(root, "raven_rig")


def append_characters(path=None, scene=None):
    """Append the RAVEN and CAT collections from characters.blend and link
    them into the scene. Returns {'raven': RAVEN_ROOT, 'cat': CAT_ROOT}."""
    path = path or DEFAULT_BLEND
    scene = scene or bpy.context.scene
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.collections = [c for c in src.collections if c in ("RAVEN", "CAT")]
    out = {}
    for coll in dst.collections:
        scene.collection.children.link(coll)
        for ob in coll.all_objects:
            if ob.get("bo_role") == "raven_root":
                out["raven"] = ob
            elif ob.get("bo_role") == "cat_root":
                out["cat"] = ob
    return out


# ---------------------------------------------------------------- math

def _smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def _key(target, path, value, frame, index=-1):
    """Set and key a property (vector or scalar)."""
    if index >= 0:
        getattr(target, path)[index] = value
        target.keyframe_insert(path, index=index, frame=frame)
    else:
        setattr(target, path, value)
        target.keyframe_insert(path, frame=frame)


def _key_prop(ob, prop, value, frame):
    ob[prop] = value
    ob.keyframe_insert('["%s"]' % prop, frame=frame)


def _heading(start_xy, end_xy):
    """Root rotation_euler.z that points the rest forward (-X) along travel."""
    dx = end_xy[0] - start_xy[0]
    dy = end_xy[1] - start_xy[1]
    return math.atan2(-dy, -dx)


# ---------------------------------------------------------------- raven

def key_raven_pose_neutral(root, frame):
    """Key every raven control bone at rest on one frame."""
    rig = raven_rig(root)
    for name in ("body", "head", "tail", "foot_ik.L", "foot_ik.R",
                 "wing.L", "wing.R", "umbrella"):
        pb = rig.pose.bones[name]
        _key(pb, "location", (0.0, 0.0, 0.0), frame)
        _key(pb, "rotation_euler", (0.0, 0.0, 0.0), frame)


def key_raven_walk(root, start_frame, end_frame, start_xy, end_xy,
                   step_frames=6, first_step=None, ground_z=None,
                   lift=0.022, bob=0.006, head_bob=True):
    """Walk the raven in a straight line at constant speed.

    The root travels start_xy -> end_xy over [start_frame, end_frame] and is
    turned to face the travel direction. A foot plants every step_frames,
    starting at first_step (default start_frame + step_frames // 3),
    alternating L, R. Planted feet stay fixed on the floor; after end_frame
    the feet settle together under the body. Body bobs (lowest on each
    contact) and waddles; the head does a pigeon-style hold-and-thrust.
    Returns the list of contact frames (for footstep sound sync).
    """
    rig = raven_rig(root)
    pbs = rig.pose.bones
    z = root.location.z if ground_z is None else ground_z
    first = start_frame + step_frames // 3 if first_step is None else first_step
    dist = math.hypot(end_xy[0] - start_xy[0], end_xy[1] - start_xy[1])
    span = max(1, end_frame - start_frame)
    speed = dist / span
    head_z = _heading(start_xy, end_xy)

    def s_root(f):
        return dist * max(0.0, min(1.0, (f - start_frame) / span))

    # Plant events per foot: (land_frame, distance along path).
    half = speed * step_frames * 0.5
    contacts = []
    c = first
    while c <= end_frame:
        contacts.append(c)
        c += step_frames
    events = {"L": [(-10 ** 6, 0.0)], "R": [(-10 ** 6, 0.0)]}
    for i, c in enumerate(contacts):
        side = "L" if i % 2 == 0 else "R"
        events[side].append((c, min(s_root(c) + half, dist + half)))
    # Settle: both feet end level under the stopped body.
    last = contacts[-1] if contacts else end_frame
    order = sorted(("L", "R"), key=lambda k: events[k][-1][0])
    for n, side in enumerate(order):
        land, s = events[side][-1]
        if abs(s - dist) > 1e-4:
            events[side].append((max(land + step_frames, last + step_frames * (n + 1)), dist))
    settle_end = max(events["L"][-1][0], events["R"][-1][0], end_frame)

    def foot_state(side, f):
        ev = events[side]
        for i in range(len(ev) - 1, -1, -1):
            if ev[i][0] <= f:
                cur = i
                break
        land, s = ev[cur]
        if cur + 1 < len(ev):
            nland, ns = ev[cur + 1]
            lift_f = max(land, nland - step_frames)
            if f >= lift_f:
                u = (f - lift_f) / float(nland - lift_f)
                return s + (ns - s) * _smooth(u), lift * math.sin(math.pi * u), u
        return s, 0.0, None

    f0 = min(start_frame, first - step_frames) - 1
    for f in range(f0, settle_end + 1):
        sr = s_root(f)
        # Root.
        t = sr / dist if dist > 0 else 0.0
        x = start_xy[0] + (end_xy[0] - start_xy[0]) * t
        y = start_xy[1] + (end_xy[1] - start_xy[1]) * t
        _key(root, "location", (x, y, z), f)
        _key(root, "rotation_euler", head_z, f, index=2)
        # Feet (armature space: forward is -X, so ahead = negative x).
        for side in ("L", "R"):
            s, h, u = foot_state(side, f)
            pb = pbs["foot_ik." + side]
            _key(pb, "location", (-(s - sr), 0.0, h), f)
            curl = -math.radians(28.0) * math.sin(math.pi * u) if u is not None else 0.0
            _key(pb, "rotation_euler", (0.0, curl, 0.0), f)
        # Envelope so bob and head bob ease in and out.
        env = _smooth((f - start_frame) / float(step_frames)) * \
            _smooth((end_frame - f) / float(step_frames))
        ph = (f - first) / float(step_frames)
        body = pbs["body"]
        _key(body, "location", (0.0, 0.0, -bob * math.cos(2 * math.pi * ph) * env - bob * env), f)
        _key(body, "rotation_euler",
             (math.radians(3.0) * math.sin(math.pi * ph) * env, math.radians(-2.0) * env, 0.0), f)
        if head_bob:
            amp = min(0.25 * speed * step_frames, 0.014) * env
            p = ph - math.floor(ph)
            if p < 0.7:
                hx = -amp + 2 * amp * (p / 0.7)
            else:
                hx = amp - 2 * amp * _smooth((p - 0.7) / 0.3)
            _key(pbs["head"], "location", (hx, 0.0, 0.0), f)
    return contacts


def yaw_to_face(root, frame, target_xyz):
    """Head yaw (degrees, for key_head_turn) that points the beak at a world
    point (the camera) at that frame. Positive yaw turns toward the raven's
    left (-Y)."""
    scene = bpy.context.scene
    keep = scene.frame_current
    scene.frame_set(frame)
    rig = raven_rig(root)
    head = rig.pose.bones["head"]
    m = rig.matrix_world @ head.bone.matrix_local
    local = m.inverted() @ __import__("mathutils").Vector(target_xyz)
    scene.frame_set(keep)
    # Rest forward is -X in bone space; yaw about +Z.
    ang = math.degrees(math.atan2(-local.y, -local.x))
    return max(-120.0, min(120.0, ang))


def key_head_turn(root, start_frame, end_frame, yaw_deg, pitch_deg=0.0,
                  roll_deg=0.0, from_deg=(0.0, 0.0, 0.0)):
    """Turn the head from from_deg (yaw, pitch, roll) to the target with an
    ease in/out, keyed on every frame from start_frame to end_frame. Yaw is
    about the vertical (+ = toward the raven's left, -Y), pitch + = look up,
    roll + = tilt the crown toward the raven's right. The head pivots at the
    neck base, so the beak and the umbrella in it swing with it."""
    pb = raven_rig(root).pose.bones["head"]
    a0 = [math.radians(v) for v in from_deg]
    a1 = [math.radians(v) for v in (yaw_deg, pitch_deg, roll_deg)]
    n = max(1, end_frame - start_frame)
    for f in range(start_frame, end_frame + 1):
        u = _smooth((f - start_frame) / float(n))
        yaw, pitch, roll = [a + (b - a) * u for a, b in zip(a0, a1)]
        # Bone axes = raven axes: X back, Y right, Z up.
        _key(pb, "rotation_euler", (-roll, pitch, yaw), f)


def key_tail_flick(root, frame, angle_deg=35.0, axis="yaw", frames=8):
    """Flick the tail: peak at `frame`, rebound, rest after `frames`.
    axis='yaw' swings it sideways (+ toward the raven's right, +Y),
    axis='pitch' flips it up (+ = up)."""
    pb = raven_rig(root).pose.bones["tail"]
    idx = 2 if axis == "yaw" else 1
    # yaw: +Z rotation moves the tail tip (+X) toward +Y (right).
    # pitch: +Y rotation moves the tip down, so flip for + = up.
    sign = 1.0 if axis == "yaw" else -1.0
    a = math.radians(angle_deg) * sign
    lead = max(2, frames // 4)
    keys = [(frame - lead, 0.0), (frame, a), (frame + lead, -0.35 * a),
            (frame + frames - lead, 0.1 * a), (frame + frames, 0.0)]
    for f, v in keys:
        rot = list(pb.rotation_euler)
        rot[idx] = v
        _key(pb, "rotation_euler", rot, f)


def key_umbrella_open(root, frame, frames=5):
    """Pop the umbrella open: closed at `frame`, fully open (with a small
    overshoot and settle) by frame + frames."""
    k = frames / 5.0
    keys = [(0, 0.0), (2 * k, 0.8), (3 * k, 1.08), (4 * k, 0.97), (5 * k, 1.0)]
    for df, v in keys:
        _key_prop(root, "umbrella_open", v, frame + int(round(df)))


def key_umbrella_visible(root, frame, visible):
    """Show or hide the umbrella (all its parts) from `frame` on."""
    for ob in _all_by_role_prefix(root, "umbrella"):
        ob.hide_render = not visible
        ob.hide_viewport = not visible
        ob.keyframe_insert("hide_render", frame=frame)
        ob.keyframe_insert("hide_viewport", frame=frame)


# ---------------------------------------------------------------- cat

def key_cat_bound(root, start_frame, end_frame, start_xy, end_xy,
                  stride_frames=6, ground_z=None, bob=0.035):
    """Gallop the cat in a straight line. ["bound"] loops 0 (gathered) ->
    1 (stretched) -> 0 every stride_frames; the root rises by `bob` in the
    stretched (airborne) phase and pitches a little. Keyed every frame."""
    z = root.location.z if ground_z is None else ground_z
    head_z = _heading(start_xy, end_xy)
    n = max(1, end_frame - start_frame)
    for f in range(start_frame, end_frame + 1):
        t = (f - start_frame) / float(n)
        x = start_xy[0] + (end_xy[0] - start_xy[0]) * t
        y = start_xy[1] + (end_xy[1] - start_xy[1]) * t
        ph = (f - start_frame) / float(stride_frames)
        b = 0.5 - 0.5 * math.cos(2 * math.pi * ph)
        _key(root, "location", (x, y, z + bob * b), f)
        _key(root, "rotation_euler", (0.0, math.radians(4.0) * math.sin(2 * math.pi * ph), head_z), f)
        _key_prop(root, "bound", b, f)
