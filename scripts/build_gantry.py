"""Build the simplified planar gantry in the open Blender scene.

Units: 1 Blender unit = 1 inch.
Envelope: X [-24, 24], Y [-3, 3], Z [0, 72].
"""

import math
import bpy
import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

# --- locked geometry (inches) ------------------------------------------------

H_LO, H_HI = 8.39, 69.78
# Pancake tilt motor (23 mm) is the left-side limit. The right rail
# is still set by the camera swing.
X_LO, X_HI = -15.82, 15.16

VB_R = 1.3125 / 2
VB_X = 20.35
VB_Y = -0.40

HB_R = 1.125 / 2
# Beam centers are set once the payload motor size is known.

AXLE_R = 0.125
# Far enough forward that the bore stays inside the front beam, and far
# enough back that the belt can wrap the far side of the pinion.
AXLE_Y = -1.80
BAR_R = 0.125

GT2 = 2.0 / 25.4

def pitch_radius(teeth):
    return teeth * GT2 / (2 * math.pi)

PR20 = pitch_radius(20)

# Inner wheels stack above and below on axles that sit on the beams.
# Each outer wheel hangs from the L-bracket at that end of the front beam.
VR_RC, VR_RF = 0.45, 0.52
VR_HW_IN, VR_HW_OUT = 0.36, 0.30
VR_GAP = 0.012
VR_D = VR_RC + VB_R + VR_GAP
VR_AXLE_DZ = HB_R + BAR_R
# Both beams stop just past the inner-wheel pillow block. The U-bracket
# fills the gap from that end out to the L-bracket.
HB_X1_F = VB_X - VR_D + 0.46
HB_X0 = -HB_X1_F
HB_X1_R = HB_X1_F
HB_X0_R = -HB_X1_R

# Horizontal carriage rollers. Larger crown so the truck wheels read clearly.
HR_RC, HR_RF, HR_HW = 0.36, 0.46, 0.28
HR_GAP = 0.012
HR_D = HR_RC + HB_R + HR_GAP
HR_X = 1.35

# Horizontal belt hangs between the upper inner wheel axles.
# Teeth face the beam; the smooth back faces the gap, where the idlers ride.
HBELT_Y = -1.12
# Just above the upper truck axles: axle radius, belt half-width, then a small gap.
HBELT_DZ = HR_D + 0.10 + 0.10 + 0.04
HP_Y = -0.15
HM_LEN, HM_SQ = 1.89, 1.665
# Inner faces of the two beams clear the motor by this much.
BEAM_CLEAR = 0.10
HB_Y_F = HP_Y - HM_SQ / 2 - BEAM_CLEAR - HB_R
HB_Y_R = HP_Y + HM_SQ / 2 + BEAM_CLEAR + HB_R
# Shaft points up. Body bottom rests on the truck plate.
HM_TOP = 0.41

# Vertical motor fastens to the right L-bracket. Shaft face, body toward +X.
VM_FACE_X = 21.22

HOME_H = H_LO
HOME_X = X_LO


# --- scene --------------------------------------------------------------------

def purge():
    if bpy.context.mode != "OBJECT":
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except RuntimeError:
            pass
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for datablocks in (
        bpy.data.meshes, bpy.data.materials, bpy.data.curves,
        bpy.data.cameras, bpy.data.lights, bpy.data.actions,
    ):
        for block in list(datablocks):
            datablocks.remove(block)


def setup_scene():
    scene = bpy.context.scene
    purge()
    us = scene.unit_settings
    us.system = "IMPERIAL"
    us.length_unit = "INCHES"
    us.scale_length = 0.0254
    scene.render.fps = 24
    scene.frame_start = 0
    scene.frame_end = 290
    scene.frame_current = 0
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.filepath = r"C:\_o\_dev\anaker_planar2\renders\gantry_still.png"
    eevee = getattr(scene, "eevee", None)
    if eevee and hasattr(eevee, "taa_render_samples"):
        eevee.taa_render_samples = 64
    world = scene.world or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs["Color"].default_value = (0.80, 0.81, 0.83, 1.0)
        bg.inputs["Strength"].default_value = 0.45
    return scene


def make_collection(name):
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    return coll


def make_mat(name, color, metallic, roughness):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    mat.diffuse_color = (*color, 1.0)
    return mat


# --- mesh helpers -------------------------------------------------------------

def new_object(name, mesh, coll, mat, smooth=True):
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    for poly in mesh.polygons:
        poly.use_smooth = smooth
    mesh.update()
    return obj


def orient(mesh, axis):
    if axis == "X":
        mesh.transform(Matrix.Rotation(math.pi / 2, 4, "Y"))
    elif axis == "Y":
        mesh.transform(Matrix.Rotation(-math.pi / 2, 4, "X"))
    mesh.update()


def cylinder(name, radius, length, center, axis, coll, mat, verts=48, smooth=True):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, cap_tris=False, segments=verts,
        radius1=radius, radius2=radius, depth=length,
    )
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    orient(me, axis)
    obj = new_object(name, me, coll, mat, smooth=smooth)
    obj.location = center
    return obj


def box(name, size, center, coll, mat, smooth=False):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    sx, sy, sz = size
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z *= sz
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = new_object(name, me, coll, mat, smooth=smooth)
    obj.location = center
    return obj


def lathe(name, profile, steps, axis, coll, mat, smooth=True):
    bm = bmesh.new()
    verts = [bm.verts.new((r, 0.0, z)) for r, z in profile]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(
        bm, geom=verts + edges, angle=math.tau, steps=steps,
        axis=(0.0, 0.0, 1.0), cent=(0.0, 0.0, 0.0),
    )
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    orient(me, axis)
    return new_object(name, me, coll, mat, smooth=smooth)


def groove_radius(y, rc, rb):
    y = min(abs(y), rb * 0.999)
    return (rc + rb) - math.sqrt(rb * rb - y * y)


def roller(name, rc, rf, rb, half_w, axis, coll, mat, gap=0.012, bore=0.09):
    """Crowned roller. Axis ends up along `axis`. Groove clears a perpendicular beam."""
    D = rc + rb + gap
    limit = rb + gap

    def max_r(y):
        ay = abs(y)
        if ay >= limit - 1e-4:
            return rf
        return D - math.sqrt(max(limit * limit - ay * ay, 0.0))

    n = 28
    pts = [(bore, -half_w)]
    for i in range(n + 1):
        y = -half_w + (2 * half_w) * i / n
        ay = min(abs(y), rb * 0.999)
        rg = groove_radius(ay, rc, rb)
        pts.append((max(bore + 0.02, min(rf, rg, max_r(y))), y))
    pts.append((bore, half_w))
    return lathe(name, pts, 48, axis, coll, mat, smooth=True)


def flanged_pulley(name, tip_r, flange_r, width, hole_r, steps, axis, coll, mat):
    ft = 0.04
    hw = width / 2
    profile = [
        (hole_r, -hw),
        (flange_r, -hw),
        (flange_r, -hw + ft),
        (tip_r, -hw + ft),
        (tip_r, hw - ft),
        (flange_r, hw - ft),
        (flange_r, hw),
        (hole_r, hw),
        (hole_r, -hw),
    ]
    return lathe(name, profile, steps, axis, coll, mat, smooth=False)


def belt_tooth(name, along, teeth, coll, mat, width=0.22):
    """One GT2 pitch. `teeth` is '-Y' (vertical belts) or '+Y' (horizontal belt)."""
    pitch = GT2
    back = 0.020
    tooth = 0.026
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm2 = bmesh.new()
    bmesh.ops.create_cube(bm2, size=1.0)
    if along == "Z":
        # Teeth point +Y, toward the rail. The smooth back faces the pinion side.
        for v in bm.verts:
            v.co.x *= width
            v.co.y = -back * (v.co.y + 0.5)
            v.co.z = pitch * (v.co.z + 0.5)
        for v in bm2.verts:
            v.co.x *= width * 0.72
            v.co.y = tooth * (v.co.y + 0.5)
            v.co.z = pitch * (0.22 + 0.56 * (v.co.z + 0.5))
    else:
        # Along X. Teeth point -Y, toward the beam. The smooth back faces the gap.
        for v in bm.verts:
            v.co.x = pitch * (v.co.x + 0.5)
            v.co.y = back * (v.co.y + 0.5)
            v.co.z *= width
        for v in bm2.verts:
            v.co.x = pitch * (0.22 + 0.56 * (v.co.x + 0.5))
            v.co.y = -(tooth * (v.co.y + 0.5))
            v.co.z *= width * 0.72
    me_tmp = bpy.data.meshes.new(name + "_t")
    bm2.to_mesh(me_tmp)
    bm2.free()
    bm.from_mesh(me_tmp)
    bpy.data.meshes.remove(me_tmp)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return new_object(name, me, coll, mat, smooth=False)


def array_along(obj, length, offset):
    mod = obj.modifiers.new("Array", "ARRAY")
    mod.fit_type = "FIT_LENGTH"
    mod.fit_length = length
    mod.use_relative_offset = True
    mod.relative_offset_displace = offset
    return mod


def nema_body(name, axis, coll, mat_body, length=None):
    """1.665 square body. Shaft boss on the +axis face. Default length is 1.89."""
    length = HM_LEN if length is None else length
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= HM_SQ
        v.co.y *= HM_SQ
        v.co.z *= length
    bm3 = bmesh.new()
    bmesh.ops.create_cone(
        bm3, cap_ends=True, cap_tris=False, segments=32,
        radius1=0.433, radius2=0.433, depth=0.08,
    )
    for v in bm3.verts:
        v.co.z += length / 2 + 0.04
    me_boss = bpy.data.meshes.new(name + "_boss")
    bm3.to_mesh(me_boss)
    bm3.free()
    bm.from_mesh(me_boss)
    bpy.data.meshes.remove(me_boss)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    orient(me, axis)
    return new_object(name, me, coll, mat_body, smooth=False)


def subtract(target, cutter):
    bpy.context.view_layer.update()
    mod = target.modifiers.new("Bool", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter
    mod.solver = "FLOAT"
    with bpy.context.temp_override(
        object=target, active_object=target,
        selected_objects=[target], selected_editable_objects=[target],
    ):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def parent_keep(child, parent):
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy()
    child.parent = parent
    bpy.context.view_layer.update()
    child.matrix_world = mw


def empty(name, loc, coll):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.4
    obj.hide_render = True
    obj.location = loc
    coll.objects.link(obj)
    return obj


def tag_spin(obj, axis, gain, source):
    obj["spin_axis"] = axis
    obj["spin_gain"] = gain
    obj["spin_src"] = source


def world_pts(obj):
    mw = obj.matrix_world
    return [mw @ v.co for v in obj.data.vertices]


def min_radial_z(obj, x, y):
    best = 1e9
    for p in world_pts(obj):
        best = min(best, math.hypot(p.x - x, p.y - y))
    return best


def min_radial_x(obj, y, z):
    best = 1e9
    for p in world_pts(obj):
        best = min(best, math.hypot(p.y - y, p.z - z))
    return best


# --- animation ----------------------------------------------------------------

def fcurves_of(act, slot):
    found = []
    if act is None:
        return found
    for layer in act.layers:
        for strip in layer.strips:
            bag = strip.channelbag(slot)
            if bag:
                found.extend(bag.fcurves)
    return found


def activate(obj, act, slots):
    ad = obj.animation_data_create()
    key = (act.name, obj.name)
    if key not in slots:
        slots[key] = act.slots.new(id_type="OBJECT", name=obj.name)
    ad.action = act
    ad.action_slot = slots[key]
    return slots[key]


def _unit2(x, y):
    L = math.hypot(x, y) or 1.0
    return x / L, y / L


def belt_mesh(name, pts, width_axis, tooth_sign, coll, mat):
    """One belt along a 3D centerline. `width_axis` is the belt width direction.
    Teeth lie on the `tooth_sign` side of (tangent cross width_axis)."""
    back = 0.020
    tooth_h = 0.024
    half_w = 0.10
    waxis = Vector(width_axis).normalized()
    bm = bmesh.new()

    def frame(i):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        if t.length < 1e-8:
            t = Vector((0.0, 0.0, 1.0))
        t.normalize()
        n = t.cross(waxis)
        if n.length < 1e-8:
            n = Vector((0.0, 1.0, 0.0))
        n.normalize()
        return t, n

    rings = []
    normals = []
    for i, p in enumerate(pts):
        t, n = frame(i)
        tooth_n = n * tooth_sign
        normals.append(tooth_n)
        # Pitch at the centerline. Smooth back is opposite the teeth.
        ring = []
        for su in (-half_w, half_w):
            for st in (0.0, back):
                ring.append(bm.verts.new(p + waxis * su - tooth_n * st))
        rings.append(ring)
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for j in range(4):
            j2 = (j + 1) % 4
            bm.faces.new((a[j], b[j], b[j2], a[j2]))
    if len(rings) >= 2:
        bm.faces.new(rings[0])
        bm.faces.new(list(reversed(rings[-1])))

    # Teeth at each GT2 of arc length, sitting on the pitch face.
    dist = 0.0
    next_tooth = GT2 * 0.5
    for i in range(len(pts) - 1):
        seg = pts[i + 1] - pts[i]
        seglen = seg.length
        if seglen < 1e-8:
            continue
        while next_tooth <= dist + seglen:
            f = (next_tooth - dist) / seglen
            p = pts[i] + seg * f
            t, n = frame(i)
            tooth_n = n * tooth_sign
            bw = half_w * 0.72
            th = tooth_h
            tl = GT2 * 0.28
            corners = []
            for su in (-bw, bw):
                for ss in (-tl, tl):
                    for st in (0.0, th):
                        corners.append(bm.verts.new(
                            p + waxis * su + t * ss + tooth_n * st
                        ))
            # corners: su, ss, st with su fastest? nested su, ss, st
            # index: su*4 + ss*2 + st
            def cid(su, ss, st):
                return su * 4 + ss * 2 + st
            faces = (
                (0, 1, 3, 2), (4, 6, 7, 5),
                (0, 4, 5, 1), (2, 3, 7, 6),
                (0, 2, 6, 4), (1, 5, 7, 3),
            )
            for fidx in faces:
                bm.faces.new(tuple(corners[k] for k in fidx))
            next_tooth += GT2
        dist += seglen

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return new_object(name, me, coll, mat, smooth=True)


def crossed_tangents(c1, r1, c2, r2):
    """Internal tangents. The two centers lie on opposite sides of the belt."""
    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
    dist = math.hypot(dx, dy)
    if dist <= r1 + r2 + 1e-6:
        return []
    angle = math.atan2(dy, dx)
    theta = math.acos(max(-1.0, min(1.0, (r1 + r2) / dist)))
    out = []
    for s in (-1.0, 1.0):
        a = angle + s * theta
        p1 = (c1[0] + r1 * math.cos(a), c1[1] + r1 * math.sin(a))
        p2 = (c2[0] - r2 * math.cos(a), c2[1] - r2 * math.sin(a))
        out.append((p1, p2, a))
    return out


def _arc(center, radius, a0, a1, n):
    pts = []
    for i in range(n + 1):
        th = a0 + (a1 - a0) * i / n
        pts.append((center[0] + radius * math.cos(th), center[1] + radius * math.sin(th)))
    return pts


def _short(a0, a1):
    delta = a1 - a0
    while delta <= -math.pi:
        delta += math.tau
    while delta > math.pi:
        delta -= math.tau
    return delta


def vertical_wrap_pts(x, z0):
    """Belt around the far side of one vertical pinion.

    Teeth face the pinion. Idlers sit on the smooth back, between the
    rail belt and the pinion. Returns the centerline, the lower kiss Z
    relative to z0, and the idler Y.
    """
    rp = PR20 - 0.004
    ri = 0.12
    yb = VB_Y - VB_R - 0.032
    py = AXLE_Y
    iy = yb - ri
    iz = 0.72
    tang = crossed_tangents((0.0, py), rp, (iz, iy), ri)

    def pin_ang(item):
        p1 = item[0]
        return math.atan2(p1[1] - py, p1[0])

    # Far side of the pinion is -Y, angle -pi/2.
    near = min(tang, key=lambda item: abs(((pin_ang(item) + math.pi / 2 + math.pi) % math.tau) - math.pi))
    p_pin, p_idl, _ = near
    a_pin = math.atan2(p_pin[1] - py, p_pin[0])
    a_idl = math.atan2(p_idl[1] - iy, p_idl[0] - iz)
    a_pin_lo = math.pi - a_pin
    a_idl_lo = math.pi - a_idl
    kiss = math.pi / 2
    lo = _arc((-iz, iy), ri, kiss, kiss + _short(kiss, a_idl_lo), 8)
    d_pin = _short(a_pin_lo, a_pin)
    mid = a_pin_lo + d_pin / 2
    if abs(((mid + math.pi / 2 + math.pi) % math.tau) - math.pi) > 0.6:
        d_pin = d_pin - math.tau if d_pin > 0 else d_pin + math.tau
    parc = _arc((0.0, py), rp, a_pin_lo, a_pin_lo + d_pin, 24)
    hi = _arc((iz, iy), ri, a_idl, a_idl + _short(a_idl, kiss), 8)
    yz = lo + parc + hi
    pts = [Vector((x, y, z0 + z)) for z, y in yz]
    return pts, -iz, iy


def horizontal_wrap_pts(cx, z):
    """Belt over the far side of the payload pinion.

    Teeth face the beam. Idlers ride the smooth back, on the gap side.
    Returns the centerline, the left kiss X relative to the carriage, and idler Y.
    """
    rp = PR20 - 0.004
    ri = 0.13
    yb = HBELT_Y
    py = HP_Y
    iy = yb + ri
    ix = -0.75
    tang = crossed_tangents((0.0, py), rp, (ix, iy), ri)

    def pin_ang(item):
        p1 = item[0]
        return math.atan2(p1[1] - py, p1[0])

    candidates = [item for item in tang if 0.4 < pin_ang(item) < math.pi - 0.05]
    near = max(candidates, key=lambda item: pin_ang(item))
    p_pin, p_idl, _ = near
    a_pin = math.atan2(p_pin[1] - py, p_pin[0])
    a_idl = math.atan2(p_idl[1] - iy, p_idl[0] - ix)
    kiss = -math.pi / 2
    left = _arc((ix, iy), ri, kiss, kiss + _short(kiss, a_idl), 8)
    a_right = math.pi - a_pin
    d_pin = _short(a_pin, a_right)
    mid = a_pin + d_pin / 2
    if abs(((mid - math.pi / 2 + math.pi) % math.tau) - math.pi) > 0.7:
        d_pin = d_pin - math.tau if d_pin > 0 else d_pin + math.tau
    parc = _arc((0.0, py), rp, a_pin, a_pin + d_pin, 24)
    a_idl_r = math.pi - a_idl
    right = _arc((-ix, iy), ri, a_idl_r, a_idl_r + _short(a_idl_r, kiss), 8)
    xy = left + parc + right
    return pts_xy(cx, z, xy), ix, iy


def pts_xy(cx, z, xy):
    return [Vector((cx + x, y, z)) for x, y in xy]


# --- build --------------------------------------------------------------------

def build():
    scene = setup_scene()
    frame = make_collection("Frame")
    gantry_c = make_collection("Gantry")
    carriage_c = make_collection("Carriage")
    drives = make_collection("Drives")
    render_c = make_collection("Render")
    cuts = make_collection("Cutters")

    aluminum = make_mat("Aluminum", (0.74, 0.75, 0.77), 1.0, 0.32)
    steel = make_mat("Steel", (0.50, 0.52, 0.55), 1.0, 0.22)
    roller_mat = make_mat("Roller", (0.015, 0.015, 0.016), 0.0, 0.48)
    motor_mat = make_mat("Motor", (0.012, 0.012, 0.014), 0.2, 0.38)
    belt_mat = make_mat("Belt", (0.015, 0.015, 0.016), 0.0, 0.72)
    cube_mat = make_mat("Payload", (0.86, 0.30, 0.04), 0.0, 0.38)
    floor_mat = make_mat("Floor", (0.62, 0.63, 0.65), 0.0, 0.85)
    dark_metal = make_mat("DarkMetal", (0.10, 0.10, 0.11), 0.85, 0.32)
    brass = make_mat("Brass", (0.55, 0.42, 0.18), 1.0, 0.28)

    h = HOME_H
    cx = HOME_X

    gantry = empty("Gantry", (0.0, 0.0, h), gantry_c)
    carriage = empty("Carriage", (cx, 0.0, h), carriage_c)

    box("R_Floor", (160, 100, 0.02), (0, 0, -0.02), render_c, floor_mat)

    # --- frame: plates, vertical beams, fixed front belts ---
    box("F_Plate_bottom", (48, 6, 0.5), (0, 0, 0.25), frame, aluminum)
    box("F_Plate_top", (48, 6, 0.5), (0, 0, 71.75), frame, aluminum)
    for sign, side in ((1, "R"), (-1, "L")):
        cylinder(
            f"F_VBeam_{side}", VB_R, 71.04,
            (sign * VB_X, VB_Y, 36.0), "Z", frame, steel, verts=64,
        )

    # Rail belt pitch line, just in front of the beam. Split into the run
    # below the gantry and the run above it; the wrap between them moves with H.
    yb = VB_Y - VB_R - 0.032
    _, kiss_z, v_iy = vertical_wrap_pts(VB_X, 0.0)
    v_low = {}
    v_high = {}
    for sign, side in ((1, "R"), (-1, "L")):
        low = belt_tooth(f"F_VBelt_{side}_low", "Z", "+Y", frame, belt_mat)
        low.location = (sign * VB_X, yb, 0.70)
        array_along(low, max(GT2, (h + kiss_z) - 0.70), (0, 0, 1))
        v_low[side] = low
        high = belt_tooth(f"F_VBelt_{side}_high", "Z", "+Y", frame, belt_mat)
        high.location = (sign * VB_X, yb, h - kiss_z)
        array_along(high, max(GT2, 71.15 - (h - kiss_z)), (0, 0, 1))
        v_high[side] = high
        for zend, tag in ((0.62, "bot"), (71.28, "top")):
            box(
                f"F_Clamp_{side}_{tag}",
                (0.36, 0.10, 0.22),
                (sign * VB_X, yb - 0.04, zend),
                frame, aluminum,
            )

    # --- beams. Front beam ends at the L-brackets. Rear beam ends at the inner axles. ---
    front_len = HB_X1_F - HB_X0
    front_cx = (HB_X0 + HB_X1_F) / 2
    front = cylinder(
        "G_Beam_front", HB_R, front_len,
        (front_cx, HB_Y_F, h), "X", gantry_c, steel, verts=64,
    )
    rear_len = HB_X1_R - HB_X0_R
    rear_cx = (HB_X0_R + HB_X1_R) / 2
    rear = cylinder(
        "G_Beam_rear", HB_R, rear_len,
        (rear_cx, HB_Y_R, h), "X", gantry_c, steel, verts=64,
    )

    bore = cylinder(
        "cut_bore", 0.175, front_len + 1.0,
        (front_cx, AXLE_Y, h), "X", cuts, steel, verts=32,
    )
    subtract(front, bore)

    # Inner wheels stack on the rail side. Both share the rail's Y so the
    # groove seats, and their axles rest on the top and bottom of both beams.
    x_in = VB_X - VR_D
    z_hi = h + VR_AXLE_DZ
    z_lo = h - VR_AXLE_DZ
    axle_y0, axle_y1 = HB_Y_F - 0.22, HB_Y_R + 0.22
    axle_len = axle_y1 - axle_y0
    axle_yc = (axle_y0 + axle_y1) / 2
    for sign, side in ((1, "R"), (-1, "L")):
        for zc, tag in ((z_hi, "hi"), (z_lo, "lo")):
            cylinder(
                f"G_Axle_{side}_{tag}", BAR_R, axle_len,
                (sign * x_in, axle_yc, zc), "Y", gantry_c, aluminum, verts=20,
            )
            rol = roller(
                f"G_VRoll_{side}_{tag}",
                VR_RC, VR_RF, VB_R, VR_HW_IN, "Y",
                gantry_c, roller_mat, VR_GAP, bore=0.145,
            )
            rol.location = (sign * x_in, VB_Y, zc)
            gain = (1.0 if sign > 0 else -1.0) / VR_RC
            tag_spin(rol, 1, gain, "H")
            for beam_y, btag in ((HB_Y_F, "F"), (HB_Y_R, "R")):
                blk = box(
                    f"G_AxleBlock_{side}_{tag}_{btag}",
                    (0.70, 0.58, 0.42),
                    (sign * x_in, beam_y, zc),
                    gantry_c, aluminum,
                )
                bore = cylinder(
                    f"cut_blk_{side}_{tag}_{btag}", 0.145, 0.80,
                    (sign * x_in, beam_y, zc), "Y", cuts, steel, verts=16,
                )
                subtract(blk, bore)
                bolt_z = zc - 0.20 if tag == "hi" else zc + 0.20
                for dx, didx in ((-0.22, "a"), (0.22, "b")):
                    cylinder(
                        f"G_AxleBolt_{side}_{tag}_{btag}_{didx}",
                        0.05, 0.40,
                        (sign * x_in + dx, beam_y, bolt_z),
                        "Z", gantry_c, steel, verts=12,
                    )

    # Outer wheel hangs on the L-bracket. The axle stops just past the wheel.
    x_out = VB_X + VR_D
    out_y0, out_y1 = -0.88, 0.00
    out_len = out_y1 - out_y0
    out_yc = (out_y0 + out_y1) / 2
    for sign, side in ((1, "R"), (-1, "L")):
        cylinder(
            f"G_Axle_{side}_out", BAR_R, out_len,
            (sign * x_out, out_yc, h), "Y", gantry_c, aluminum, verts=20,
        )
        rol = roller(
            f"G_VRoll_{side}_out",
            VR_RC, VR_RF, VB_R, VR_HW_OUT, "Y",
            gantry_c, roller_mat, VR_GAP, bore=0.145,
        )
        rol.location = (sign * x_out, VB_Y, h)
        gain = (-1.0 if sign > 0 else 1.0) / VR_RC
        tag_spin(rol, 1, gain, "H")

    # --- drives ---
    axle = cylinder(
        "G_Axle", AXLE_R, 41.56,
        (0.0, AXLE_Y, h), "X", drives, steel, verts=24,
    )
    tag_spin(axle, 0, 1.0 / PR20, "H")

    tip = PR20 - 0.004
    pinions = []
    for sign, side in ((1, "R"), (-1, "L")):
        pin = flanged_pulley(
            f"G_VPinion_{side}", tip, 0.27, 0.32, AXLE_R + 0.015,
            20, "X", drives, dark_metal,
        )
        pin.location = (sign * VB_X, AXLE_Y, h)
        pinions.append(pin)
        pts, _, _ = vertical_wrap_pts(sign * VB_X, h)
        belt_mesh(f"G_VWrap_{side}", pts, (1, 0, 0), 1.0, drives, belt_mat)
        for zc, tag in ((h + kiss_z, "lo"), (h - kiss_z, "hi")):
            idler = flanged_pulley(
                f"G_VIdler_{side}_{tag}", 0.12, 0.14, 0.28, 0.05,
                16, "X", drives, dark_metal,
            )
            idler.location = (sign * VB_X, v_iy, zc)
            tag_spin(idler, 0, -1.0 / 0.12, "H")

    # One bracket per end: a U of one thickness and height, open toward
    # the rail, with the outer-wheel leg on the motor plate. The drive
    # axle passes through the inner end. Both ends carry the NEMA 17
    # pattern so the motor can mount on either side.
    T = 0.16
    ZH = 0.96
    y_closed = AXLE_Y - HM_SQ / 2 - 0.12
    y_open = -1.12
    y_motor = AXLE_Y + HM_SQ / 2 + 0.12
    nema = 31.0 / 25.4 / 2
    for sign, side in ((1, "R"), (-1, "L")):
        beam_end = x_in + 0.46
        in_c = sign * (beam_end + T / 2 - 0.02)
        out_c = sign * (VM_FACE_X - 0.02 - T / 2)
        inner = box(
            f"G_Bracket_{side}_in",
            (T, y_open - y_closed, ZH * 2),
            (in_c, (y_closed + y_open) / 2, h),
            gantry_c, aluminum,
        )
        subtract(inner, cylinder(
            f"cut_bin_{side}", 0.18, T + 0.2,
            (in_c, AXLE_Y, h), "X", cuts, steel, verts=16,
        ))
        outer = box(
            f"G_Bracket_{side}",
            (T, y_motor - y_closed, ZH * 2),
            (out_c, (y_closed + y_motor) / 2, h),
            gantry_c, aluminum,
        )
        subtract(outer, cylinder(
            f"cut_bout_{side}", 0.46, T + 0.2,
            (out_c, AXLE_Y, h), "X", cuts, steel, verts=16,
        ))
        for iy, iz, tag in (
            (-nema, -nema, "a"), (nema, -nema, "b"),
            (-nema, nema, "c"), (nema, nema, "d"),
        ):
            subtract(outer, cylinder(
                f"cut_nema_{side}_{tag}", 0.067, T + 0.2,
                (out_c, AXLE_Y + iy, h + iz), "X", cuts, steel, verts=12,
            ))
            cylinder(
                f"G_BracketScrew_{side}_{tag}", 0.10, 0.06,
                (out_c - sign * (T / 2 + 0.03), AXLE_Y + iy, h + iz),
                "X", gantry_c, steel, verts=12,
            )
        box(
            f"G_Bracket_{side}_back",
            (abs(out_c - in_c) + T, T, ZH * 2),
            ((in_c + out_c) / 2, y_closed + T / 2, h),
            gantry_c, aluminum,
        )
        foot = box(
            f"G_BracketFoot_{side}",
            (0.64, T, ZH * 2),
            (sign * 21.32, -0.84, h),
            gantry_c, aluminum,
        )
        subtract(foot, cylinder(
            f"cut_foot_{side}", 0.15, T + 0.2,
            (sign * x_out, -0.84, h), "Y", cuts, steel, verts=16,
        ))
        x0 = in_c - sign * (T / 2)
        x1 = out_c + sign * (T / 2)
        for zc, tag in ((h + kiss_z, "lo"), (h - kiss_z, "hi")):
            subtract(inner, cylinder(
                f"cut_idl_{side}_{tag}_i", 0.055, T + 0.2,
                (in_c, v_iy, zc), "X", cuts, steel, verts=12,
            ))
            subtract(outer, cylinder(
                f"cut_idl_{side}_{tag}_o", 0.055, T + 0.2,
                (out_c, v_iy, zc), "X", cuts, steel, verts=12,
            ))
            cylinder(
                f"G_VIdlerAxle_{side}_{tag}", 0.04, abs(x1 - x0),
                ((x0 + x1) / 2, v_iy, zc), "X", gantry_c, steel, verts=12,
            )

    coupler = cylinder(
        "G_Coupler", 0.26, 0.26,
        (20.69, AXLE_Y, h), "X", drives, brass, verts=24,
    )
    vm = nema_body("G_VMotor", "X", drives, motor_mat)
    vm.location = (VM_FACE_X + HM_LEN / 2, AXLE_Y, h)
    vm.rotation_euler[2] = math.pi  # shaft points inboard, toward -X
    vshaft = cylinder(
        "G_VShaft", 0.098, 0.55,
        (21.05, AXLE_Y, h), "X", drives, steel, verts=16,
    )

    # Horizontal belt hangs between the upper inner wheel axles.
    # Teeth face the beam; idlers ride the smooth back.
    hz_belt = h + HBELT_DZ
    # The vertical drive shaft sits just outside the left top-wheel axle
    # and the inner idler sits just inside it.
    axle_min = 20.0 / 25.4
    gear_r = 0.28
    # Belt shaft just outside the left top axle, inner idler just inside it.
    # The pan motor uses that same offset outside the right top axle.
    idler_dx = 0.75
    shaft_r, idler_r = 0.098, 0.16
    belt_dx = -HR_X - (shaft_r + (idler_dx - idler_r)) / 2
    pan_off = -belt_dx
    h_pts, h_ix, h_iy = horizontal_wrap_pts(cx + belt_dx, hz_belt)
    belt_mesh("C_HWrap", h_pts, (0, 0, 1), 1.0, carriage_c, belt_mat)
    hb_left = belt_tooth("G_HBelt_L", "X", "-Y", drives, belt_mat, width=0.16)
    hb_left.location = (-x_in, HBELT_Y, hz_belt)
    array_along(hb_left, max(GT2, (cx + belt_dx + h_ix) - (-x_in)), (1, 0, 0))
    hb_right = belt_tooth("G_HBelt_R", "X", "-Y", drives, belt_mat, width=0.16)
    hb_right.location = (cx + belt_dx - h_ix, HBELT_Y, hz_belt)
    array_along(hb_right, max(GT2, x_in - (cx + belt_dx - h_ix)), (1, 0, 0))
    for sign, side in ((1, "R"), (-1, "L")):
        box(
            f"G_BeltClamp_{side}",
            (0.22, 0.16, 0.64),
            (sign * x_in, HBELT_Y, h + 0.93),
            gantry_c, aluminum,
        )

    # U truck with a top. Cheeks sit just outside the beams.
    y_cheek_f = HB_Y_F - HB_R - 0.21
    y_cheek_r = HB_Y_R + HB_R + 0.21
    axle_y0c, axle_y1c = y_cheek_f - 0.06, y_cheek_r + 0.06
    cax_len = axle_y1c - axle_y0c
    cax_yc = (axle_y0c + axle_y1c) / 2
    for xoff, tag in ((-HR_X, "hi_a"), (HR_X, "hi_b")):
        cylinder(
            f"C_Axle_{tag}", 0.10, cax_len,
            (cx + xoff, cax_yc, h + HR_D), "Y", carriage_c, steel, verts=16,
        )
        for beam_y, btag in ((HB_Y_F, "F"), (HB_Y_R, "R")):
            rol = roller(
                f"C_HRoll_{btag}_{tag}",
                HR_RC, HR_RF, HB_R, HR_HW, "Y",
                carriage_c, roller_mat, HR_GAP, bore=0.11,
            )
            rol.location = (cx + xoff, beam_y, h + HR_D)
            tag_spin(rol, 1, 1.0 / HR_RC, "X")

    # Lower wheels sit on the carriage centerline, one on each beam.
    # Each axle runs in from the outside cheek and stops short of the pan gear.
    z_lo = h - HR_D
    my0, my1 = HP_Y - HM_SQ / 2, HP_Y + HM_SQ / 2
    for y0, y1, tag in (
        (axle_y0c, my0 - 0.02, "lo_F"),
        (my1 + 0.02, axle_y1c, "lo_R"),
    ):
        cylinder(
            f"C_Axle_{tag}", 0.10, y1 - y0,
            (cx, (y0 + y1) / 2, z_lo), "Y", carriage_c, steel, verts=16,
        )
    for beam_y, btag in ((HB_Y_F, "F"), (HB_Y_R, "R")):
        rol = roller(
            f"C_HRoll_{btag}_lo",
            HR_RC, HR_RF, HB_R, HR_HW, "Y",
            carriage_c, roller_mat, HR_GAP, bore=0.11,
        )
        rol.location = (cx, beam_y, z_lo)
        tag_spin(rol, 1, -1.0 / HR_RC, "X")

    # U truck. Bottom plate, cheeks, and a top that carries the payload idlers.
    plate_y0, plate_y1 = y_cheek_f - 0.05, y_cheek_r + 0.05
    plate_yc = (plate_y0 + plate_y1) / 2
    plate_ys = plate_y1 - plate_y0
    top_bot = HR_D + HR_RF + 0.08
    cheek_bot, cheek_top = -1.52, top_bot + 0.08
    cheek_h = cheek_top - cheek_bot
    cheek_zc = (cheek_bot + cheek_top) / 2
    truck_x = 2.0 * (pan_off + HM_LEN / 2 + 0.16)
    box(
        "C_Cheek_F", (truck_x, 0.10, cheek_h),
        (cx, y_cheek_f, h + cheek_zc), carriage_c, aluminum,
    )
    box(
        "C_Cheek_R", (truck_x, 0.10, cheek_h),
        (cx, y_cheek_r, h + cheek_zc), carriage_c, aluminum,
    )
    box(
        "C_Plate", (truck_x, plate_ys, 0.10),
        (cx, plate_yc, h - 1.55), carriage_c, aluminum,
    )
    box(
        "C_Top", (truck_x, plate_ys, 0.10),
        (cx, plate_yc, h + top_bot + 0.05), carriage_c, aluminum,
    )
    # End plates. Holes clear the beams and the belt by a small margin.
    end_t = 0.10
    beam_hole = HB_R + 0.04
    belt_hole = 0.12
    for sign, tag in ((-1, "L"), (1, "R")):
        end = box(
            f"C_End_{tag}", (end_t, plate_ys, cheek_h),
            (cx + sign * (truck_x / 2 - end_t / 2), plate_yc, h + cheek_zc),
            carriage_c, aluminum,
        )
        for beam_y in (HB_Y_F, HB_Y_R):
            subtract(end, cylinder(
                f"cut_end_{tag}_{beam_y:.2f}", beam_hole, end_t + 0.3,
                (end.location.x, beam_y, h), "X", cuts, steel, verts=24,
            ))
        subtract(end, cylinder(
            f"cut_end_{tag}_belt", belt_hole, end_t + 0.3,
            (end.location.x, HBELT_Y, hz_belt), "X", cuts, steel, verts=20,
        ))
    subtract(bpy.data.objects["C_Plate"], cylinder(
        "cut_pan", 0.16, 0.40,
        (cx, HP_Y, h - 1.55), "Z", cuts, steel, verts=16,
    ))

    # Payload motor stands on the plate, shaft up. The belt is raised to clear it.
    hm = nema_body("C_HMotor", "Z", carriage_c, motor_mat)
    hm.location = (cx + belt_dx, HP_Y, h + HM_TOP - HM_LEN / 2)
    hm.rotation_euler[2] = math.pi / 2
    hp = flanged_pulley(
        "C_HPinion", tip, tip + 0.04, 0.28, 0.11,
        20, "Z", carriage_c, dark_metal,
    )
    hp.location = (cx + belt_dx, HP_Y, hz_belt)
    tag_spin(hp, 2, 1.0 / PR20, "X")
    shaft_lo = h + HM_TOP + 0.02
    shaft_hi = hz_belt - 0.08
    hshaft = cylinder(
        "C_HShaft", 0.098, shaft_hi - shaft_lo,
        (cx + belt_dx, HP_Y, (shaft_lo + shaft_hi) / 2),
        "Z", carriage_c, steel, verts=16,
    )
    for xoff, tag in ((h_ix, "a"), (-h_ix, "b")):
        idler = flanged_pulley(
            f"C_HIdler_{tag}", 0.13, 0.16, 0.24, 0.05,
            16, "Z", carriage_c, dark_metal,
        )
        ix, iy, iz = cx + belt_dx + xoff, h_iy, hz_belt
        idler.location = (ix, iy, iz)
        tag_spin(idler, 2, -1.0 / 0.13, "X")
        # Hung from the truck top. The pin drops out of a boss into the pulley bore.
        box(
            f"C_IdlerBoss_{tag}",
            (0.28, 0.28, 0.08),
            (ix, iy, h + top_bot - 0.02),
            carriage_c, aluminum,
        )
        pin_hi = h + top_bot + 0.04
        pin_lo = iz + 0.02
        cylinder(
            f"C_IdlerPin_{tag}", 0.04, pin_hi - pin_lo,
            (ix, iy, (pin_hi + pin_lo) / 2),
            "Z", carriage_c, steel, verts=12,
        )

    # --- parenting ---
    bpy.context.view_layer.update()
    parent_keep(carriage, gantry)

    def meshes(coll):
        return [o for o in coll.objects if o.type == "MESH"]

    for obj in meshes(gantry_c) + meshes(drives):
        if obj.name.startswith("C_"):
            parent_keep(obj, carriage)
        else:
            parent_keep(obj, gantry)
    for obj in meshes(carriage_c):
        parent_keep(obj, carriage)

    bpy.context.view_layer.update()
    for pin in pinions:
        parent_keep(pin, axle)
    parent_keep(coupler, axle)
    parent_keep(vshaft, axle)
    parent_keep(hshaft, hp)

    # Pan motor on its side, shaft toward the center. The exposed axle is
    # at least 20 mm before the 1:1 miter.
    pan_x = cx
    pan_z = h + HM_TOP - HM_LEN / 2
    pan_motor = nema_body("C_PanMotor", "X", carriage_c, motor_mat)
    pan_motor.location = (cx + pan_off, HP_Y, pan_z)
    pan_motor.rotation_euler[2] = math.pi
    boss_in = pan_off - HM_LEN / 2 - 0.08
    shaft_len = boss_in - gear_r * 0.35
    cylinder(
        "C_PanShaft", 0.098, shaft_len,
        (cx + gear_r * 0.35 + shaft_len / 2, HP_Y, pan_z),
        "X", carriage_c, steel, verts=16,
    )

    def miter_gear(name, radius, teeth=20, phase=0.0, lay_on_x=False):
        """1:1 miter. Cone axis is +Z, heel at z=0. Teeth are tapered wedges."""
        bm = bmesh.new()
        bmesh.ops.create_cone(
            bm, cap_ends=True, cap_tris=False, segments=32,
            radius1=radius * 0.62, radius2=0.045, depth=radius * 0.92,
        )
        for v in bm.verts:
            v.co.z += radius * 0.46
        pitch = math.tau / teeth
        heel_z, toe_z = 0.08 * radius, 0.92 * radius

        def station(z, ang, radial):
            return (
                radial * math.cos(ang),
                radial * math.sin(ang),
                z,
            )

        for i in range(teeth):
            a = phase + i * pitch
            # Heel is the wide end. The tooth narrows toward the apex.
            tooth = bmesh.new()
            verts = []
            # Pitch radius equals distance from the apex, so the face is 45 deg.
            for z, width in ((heel_z, 1.0), (toe_z, 0.45)):
                slant = radius - z
                rr, rt = slant * 0.55, slant * 1.0
                wz, wt = pitch * 0.42 * width, pitch * 0.20 * width
                verts.append(station(z, a - wz, rr))
                verts.append(station(z, a - wt, rt))
                verts.append(station(z, a + wt, rt))
                verts.append(station(z, a + wz, rr))
            bm_verts = [tooth.verts.new(c) for c in verts]
            tooth.verts.ensure_lookup_table()
            faces = (
                (0, 1, 2, 3),
                (4, 7, 6, 5),
                (0, 4, 5, 1),
                (1, 5, 6, 2),
                (2, 6, 7, 3),
                (3, 7, 4, 0),
            )
            for f in faces:
                tooth.faces.new([bm_verts[k] for k in f])
            tooth_me = bpy.data.meshes.new(name + "_tt")
            tooth.to_mesh(tooth_me)
            tooth.free()
            bm.from_mesh(tooth_me)
            bpy.data.meshes.remove(tooth_me)
        if lay_on_x:
            for v in bm.verts:
                x, z = v.co.x, v.co.z
                v.co.x = -z
                v.co.z = x
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        return new_object(name, me, carriage_c, dark_metal, smooth=False)

    gear_h = miter_gear("C_PanGearH", gear_r, phase=math.pi / 20, lay_on_x=True)
    gear_h.location = (cx + gear_r - 0.10, HP_Y, pan_z - 0.06)
    parent_keep(pan_motor, carriage)
    parent_keep(bpy.data.objects["C_PanShaft"], carriage)
    parent_keep(gear_h, carriage)
    gear_v = miter_gear("C_PanGearV", gear_r)
    gear_v.location = (cx, HP_Y, pan_z - gear_r)
    gear_v.rotation_euler[2] = 0.0

    # Both yokes use the same square stock and the same overall width.
    # Tilt spins about the camera box center. The inverted body hangs from
    # the lower yoke by the tripod peg. The lower yoke sits far enough
    # below the upper one that a 45 deg lens swing clears the carriage.
    stock = 0.16
    depth = stock * 3
    cam_hx, cam_hz = 4.26 / 2, 2.64 / 2
    arm_in = cam_hx + 0.20 + stock / 2
    arm_out = arm_in + stock + 0.04
    cam_z = h - 4.40
    upper_bar_z = h - 1.85
    peg = 0.20
    lower_bar_z = cam_z + cam_hz + peg + stock / 2
    bx, by, bz = pan_x, HP_Y, cam_z

    pan = empty("C_Pan", (pan_x, HP_Y, upper_bar_z), carriage_c)
    parent_keep(pan, carriage)
    parent_keep(gear_v, pan)
    axle_top = pan_z - gear_r + 0.16
    axle_bot = upper_bar_z
    cylinder(
        "C_PanAxle", 0.12, axle_top - axle_bot,
        (pan_x, HP_Y, (axle_top + axle_bot) / 2),
        "Z", carriage_c, steel, verts=16,
    )
    parent_keep(bpy.data.objects["C_PanAxle"], pan)
    box(
        "C_PanBar", (arm_out * 2 + stock, depth, stock),
        (pan_x, HP_Y, upper_bar_z), carriage_c, aluminum,
    )
    parent_keep(bpy.data.objects["C_PanBar"], pan)
    upper_arm_h = upper_bar_z - bz
    for sx, tag in ((-1, "L"), (1, "R")):
        box(
            f"C_PanArm_{tag}", (stock, depth, upper_arm_h),
            (pan_x + sx * arm_out, HP_Y, (upper_bar_z + bz) / 2),
            carriage_c, aluminum,
        )
        parent_keep(bpy.data.objects[f"C_PanArm_{tag}"], pan)

    tilt = empty("C_Tilt", (bx, by, bz), carriage_c)
    parent_keep(tilt, pan)
    box(
        "C_TiltBar", (arm_in * 2 + stock, depth, stock),
        (bx, by, lower_bar_z), carriage_c, aluminum,
    )
    parent_keep(bpy.data.objects["C_TiltBar"], tilt)
    lower_arm_h = lower_bar_z - bz
    for sx, tag in ((-1, "L"), (1, "R")):
        box(
            f"C_TiltArm_{tag}", (stock, depth, lower_arm_h),
            (bx + sx * arm_in, by, (lower_bar_z + bz) / 2),
            carriage_c, aluminum,
        )
        parent_keep(bpy.data.objects[f"C_TiltArm_{tag}"], tilt)
        # Pin only bridges the two arms. It stops outside the camera.
        cylinder(
            f"C_TiltPin_{tag}", 0.08, stock * 2 + 0.08,
            (bx + sx * (arm_in + arm_out) / 2, by, bz),
            "X", carriage_c, steel, verts=12,
        )
        parent_keep(bpy.data.objects[f"C_TiltPin_{tag}"], tilt)

    nema = 31.0 / 25.4 / 2
    plate_x = -(arm_out + stock)
    plate = box(
        "C_TiltPlate", (stock, HM_SQ, HM_SQ),
        (bx + plate_x, by, bz), carriage_c, aluminum,
    )
    subtract(plate, cylinder(
        "cut_tilt_shaft", 0.14, stock + 0.2,
        (bx + plate_x, by, bz), "X", cuts, steel, verts=16,
    ))
    for sy, sz, tag in (
        (-nema, -nema, "a"), (nema, -nema, "b"),
        (nema, nema, "c"), (-nema, nema, "d"),
    ):
        subtract(plate, cylinder(
            f"cut_tilt_{tag}", 0.067, stock + 0.2,
            (bx + plate_x, by + sy, bz + sz), "X", cuts, steel, verts=12,
        ))
        screw = cylinder(
            f"C_TiltScrew_{tag}", 0.10, 0.06,
            (bx + plate_x + stock / 2 + 0.03, by + sy, bz + sz),
            "X", carriage_c, steel, verts=12,
        )
        parent_keep(screw, pan)
    parent_keep(plate, pan)
    face_x = bx + plate_x - stock / 2
    pancake = 23.0 / 25.4
    tilt_motor = nema_body("C_TiltMotor", "X", carriage_c, motor_mat, length=pancake)
    tilt_motor.location = (face_x - pancake / 2, by, bz)
    parent_keep(tilt_motor, pan)
    shaft_x0 = face_x - 0.08
    shaft_x1 = bx - arm_out - stock / 2
    cylinder(
        "C_TiltShaft", 0.098, abs(shaft_x1 - shaft_x0),
        ((shaft_x0 + shaft_x1) / 2, by, bz),
        "X", carriage_c, steel, verts=16,
    )
    parent_keep(bpy.data.objects["C_TiltShaft"], tilt)

    # EOS M100, upside down: tripod face up, lens toward the front.
    cam_black = make_mat("CamBody", (0.012, 0.012, 0.014), 0.15, 0.45)
    cam_lens = make_mat("CamLens", (0.02, 0.02, 0.022), 0.4, 0.25)
    cam_glass = make_mat("CamGlass", (0.03, 0.05, 0.08), 0.9, 0.05)
    cam_silver = make_mat("CamSilver", (0.55, 0.55, 0.52), 0.7, 0.3)
    body = box("C_CamBody", (4.26, 1.39, 2.64), (bx, by, bz), carriage_c, cam_black)
    parent_keep(body, tilt)
    cylinder(
        "C_CamPeg", 0.10, peg,
        (bx, by, bz + cam_hz + peg / 2),
        "Z", carriage_c, cam_silver, verts=16,
    )
    parent_keep(bpy.data.objects["C_CamPeg"], tilt)
    grip = box("C_CamGrip", (1.15, 1.55, 2.40), (bx + 1.45, by + 0.05, bz - 0.05), carriage_c, cam_black)
    parent_keep(grip, tilt)
    lens = cylinder("C_CamLens", 0.72, 1.70, (bx, by - 1.45, bz), "Y", carriage_c, cam_lens, verts=32)
    parent_keep(lens, tilt)
    ring = cylinder("C_CamRing", 0.78, 0.12, (bx, by - 2.25, bz), "Y", carriage_c, cam_silver, verts=32)
    parent_keep(ring, tilt)
    glass = cylinder("C_CamGlass", 0.48, 0.04, (bx, by - 2.32, bz), "Y", carriage_c, cam_glass, verts=24)
    parent_keep(glass, tilt)
    dial = cylinder("C_CamDial", 0.28, 0.18, (bx + 1.35, by - 0.15, bz - 1.22), "Z", carriage_c, cam_silver, verts=16)
    parent_keep(dial, tilt)
    shutter = cylinder("C_CamShutter", 0.14, 0.12, (bx + 1.70, by - 0.55, bz - 1.15), "Z", carriage_c, cam_silver, verts=12)
    parent_keep(shutter, tilt)
    screen = box("C_CamScreen", (2.6, 0.06, 1.7), (bx - 0.15, by + 0.72, bz + 0.05), carriage_c, cam_glass)
    parent_keep(screen, tilt)
    flash = box("C_CamFlash", (1.3, 0.35, 0.28), (bx - 1.1, by - 0.55, bz - 1.25), carriage_c, cam_black)
    parent_keep(flash, tilt)

    # Drop the empty cutter collection.
    bpy.data.collections.remove(cuts)

    # --- one loop around the travel box: BL, TL, TR, BR ----------------
    # Travel the box, and at each corner hold still while pan and tilt
    # each run through their full ±45 deg range.
    corners = [
        (X_LO, H_LO),
        (X_LO, H_HI),
        (X_HI, H_HI),
        (X_HI, H_LO),
    ]
    sweep = [(-45, -45), (45, -45), (45, 45), (-45, 45), (-45, -45)]
    keys = []
    frame = 0
    for i, (x, hz) in enumerate(corners):
        for pd, td in sweep:
            keys.append((frame, x, hz, pd, td))
            frame += 10
        frame = keys[-1][0] + 30
    keys.append((frame, X_LO, H_LO, -45, -45))
    scene.frame_end = keys[-1][0]
    loops = {"Loop_Box": keys}
    actions = {name: bpy.data.actions.new(name) for name in loops}
    slots = {}
    spinners = [
        o for o in bpy.data.objects
        if "spin_gain" in o.keys() and o.parent not in (axle, hp)
    ]

    for name, keys in loops.items():
        act = actions[name]
        for frame_i, x, hz, pan_deg, tilt_deg in keys:
            gantry.location.z = hz
            carriage.location.x = x
            pan_ang = math.radians(pan_deg)
            tilt_ang = math.radians(tilt_deg)
            activate(gantry, act, slots)
            gantry.keyframe_insert("location", index=2, frame=frame_i)
            activate(carriage, act, slots)
            carriage.keyframe_insert("location", index=0, frame=frame_i)
            activate(pan, act, slots)
            pan.rotation_euler[2] = pan_ang
            pan.keyframe_insert("rotation_euler", index=2, frame=frame_i)
            activate(tilt, act, slots)
            tilt.rotation_euler[0] = tilt_ang
            tilt.keyframe_insert("rotation_euler", index=0, frame=frame_i)
            activate(gear_h, act, slots)
            gear_h.rotation_euler[0] = pan_ang
            gear_h.keyframe_insert("rotation_euler", index=0, frame=frame_i)
            for obj in spinners:
                activate(obj, act, slots)
                delta = (hz - H_LO) if obj["spin_src"] == "H" else (x - X_LO)
                axis = int(obj["spin_axis"])
                obj.rotation_euler[axis] = obj["spin_gain"] * delta
                obj.keyframe_insert("rotation_euler", index=axis, frame=frame_i)
            for side, low in v_low.items():
                activate(low, act, slots)
                low.modifiers["Array"].fit_length = max(GT2, (hz + kiss_z) - 0.70)
                low.keyframe_insert('modifiers["Array"].fit_length', frame=frame_i)
                high = v_high[side]
                activate(high, act, slots)
                high.location.z = hz - kiss_z
                high.modifiers["Array"].fit_length = max(GT2, 71.15 - (hz - kiss_z))
                high.keyframe_insert("location", index=2, frame=frame_i)
                high.keyframe_insert('modifiers["Array"].fit_length', frame=frame_i)
            activate(hb_left, act, slots)
            hb_left.modifiers["Array"].fit_length = max(GT2, (x + belt_dx + h_ix) + x_in)
            hb_left.keyframe_insert('modifiers["Array"].fit_length', frame=frame_i)
            activate(hb_right, act, slots)
            hb_right.location.x = x + belt_dx - h_ix
            hb_right.modifiers["Array"].fit_length = max(GT2, x_in - (x + belt_dx - h_ix))
            hb_right.keyframe_insert("location", index=0, frame=frame_i)
            hb_right.keyframe_insert('modifiers["Array"].fit_length', frame=frame_i)

    for (act_name, obj_name), slot in slots.items():
        act = actions[act_name]
        for fc in fcurves_of(act, slot):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
            mod = fc.modifiers.new("CYCLES")
            mod.mode_before = "REPEAT"
            mod.mode_after = "REPEAT"

    strip_starts = (("Loop_Box", 0),)
    belt_movers = [
        *v_low.values(), *v_high.values(), hb_left, hb_right,
    ]
    animated = [gantry, carriage, pan, tilt, gear_h, *spinners, *belt_movers]
    for obj in animated:
        ad = obj.animation_data
        track = ad.nla_tracks.new()
        track.name = "Loops"
        for name, start in strip_starts:
            strip = track.strips.new(name, start, actions[name])
            strip.action_slot = slots[(name, obj.name)]
            strip.extrapolation = "HOLD"
        ad.action = None

    gantry.location.z = H_LO
    carriage.location.x = X_LO
    scene.frame_set(0)

    # --- camera and lights ---
    cam_data = bpy.data.cameras.new("Camera")
    cam_data.lens = 50
    cam_data.clip_start = 0.1
    cam_data.clip_end = 2000
    cam = bpy.data.objects.new("Camera", cam_data)
    cam.location = (100, -148, 56)
    render_c.objects.link(cam)
    target = empty("R_Look", (0.0, 0.0, 36.0), render_c)
    target.hide_viewport = True
    con = cam.constraints.new("TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    scene.camera = cam

    sun_data = bpy.data.lights.new("Key", "SUN")
    sun_data.energy = 3.2
    sun_data.angle = math.radians(6)
    sun = bpy.data.objects.new("Key", sun_data)
    sun.rotation_euler = (math.radians(48), math.radians(8), math.radians(35))
    render_c.objects.link(sun)

    fill_data = bpy.data.lights.new("Fill", "AREA")
    fill_data.energy = 400
    fill_data.size = 80
    fill = bpy.data.objects.new("Fill", fill_data)
    fill.location = (-40, -30, 60)
    render_c.objects.link(fill)
    con = fill.constraints.new("TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

    rim_data = bpy.data.lights.new("Rim", "AREA")
    rim_data.energy = 180
    rim_data.size = 40
    rim = bpy.data.objects.new("Rim", rim_data)
    rim.location = (20, 40, 55)
    render_c.objects.link(rim)
    con = rim.constraints.new("TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"

    for area in bpy.context.screen.areas:
        if area.type == "VIEW_3D":
            space = area.spaces.active
            space.clip_end = 2000
            space.shading.type = "MATERIAL"
            space.overlay.show_extras = False
            space.overlay.show_relationship_lines = False
            space.overlay.show_cursor = False
            space.overlay.show_floor = False
            space.overlay.show_axis_x = False
            space.overlay.show_axis_y = False
            space.overlay.show_axis_z = False
            space.region_3d.view_perspective = "CAMERA"

    bpy.context.view_layer.update()
    for obj in (gantry, carriage, target):
        obj.hide_viewport = True

    # --- clearance at the travel extremes ------------------------------------
    def set_pose(x, z):
        gantry.location.z = z
        carriage.location.x = x
        bpy.context.view_layer.update()

    def bounds(obj):
        pts = world_pts(obj)
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        zs = [p.z for p in pts]
        return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))

    def mesh_bvh(obj):
        deps = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(deps)
        me = ev.to_mesh()
        bm = bmesh.new()
        bm.from_mesh(me)
        bm.transform(ev.matrix_world)
        tree = BVHTree.FromBMesh(bm)
        bm.free()
        ev.to_mesh_clear()
        return tree

    report = []
    poses = [
        ("BL", X_LO, H_LO),
        ("TL", X_LO, H_HI),
        ("TR", X_HI, H_HI),
        ("BR", X_HI, H_LO),
    ]
    # Wheel and roller seating does not change with pose. Measure once.
    set_pose(0.0, 40.0)
    for sign, side in ((1, "R"), (-1, "L")):
        for tag in ("hi", "lo", "out"):
            rol = bpy.data.objects[f"G_VRoll_{side}_{tag}"]
            gap = min_radial_z(rol, sign * VB_X, VB_Y) - VB_R
            report.append(f"wheel {rol.name} rail_gap {gap:.4f}")
        for btag in ("F", "R"):
            beam_y = HB_Y_F if btag == "F" else HB_Y_R
            for xtag in ("hi_a", "hi_b", "lo"):
                rol = bpy.data.objects[f"C_HRoll_{btag}_{xtag}"]
                gap = min_radial_x(rol, beam_y, 40.0) - HB_R
                report.append(f"roll {rol.name} beam_gap {gap:.4f}")
    for name, y0, r in (
        ("G_Beam_front", HB_Y_F, HB_R),
        ("G_Beam_rear", HB_Y_R, HB_R),
    ):
        # Nearest approach of each horizontal beam to each vertical rail.
        obj = bpy.data.objects[name]
        for sign in (1, -1):
            gap = min_radial_z(obj, sign * VB_X, VB_Y) - VB_R
            report.append(f"{name} vs rail{sign:+d} {gap:.4f}")

    env_hit = []
    for tag, x, z in poses:
        set_pose(x, z)
        for obj in bpy.data.objects:
            if obj.type != "MESH" or obj.name.startswith("R_"):
                continue
            if obj.name.startswith(("C_Cam", "C_Tilt", "C_Pan")):
                continue
            x0, x1, y0, y1, z0, z1 = bounds(obj)
            if x0 < -24.02 or x1 > 24.02 or y0 < -3.02 or y1 > 3.02 or z0 < -0.02 or z1 > 72.02:
                env_hit.append(f"{tag} {obj.name} ({x0:.2f},{x1:.2f}) ({y0:.2f},{y1:.2f}) ({z0:.2f},{z1:.2f})")
        cam = bpy.data.objects["C_CamBody"]
        c0, c1, _, _, cz0, cz1 = bounds(cam)
        plate = bpy.data.objects["F_Plate_bottom"]
        _, _, _, _, _, pz1 = bounds(plate)
        report.append(f"{tag} cam_z {cz0:.3f} plate_top {pz1:.3f} gap {cz0 - pz1:.3f} cam_x {c0:.2f},{c1:.2f}")

    def overlaps(a, b):
        if a is None or b is None:
            return 0
        return len(mesh_bvh(a).overlap(mesh_bvh(b)))

    pairs = [
        ("G_VPinion_R", "G_Beam_front"),
        ("G_VPinion_R", "F_VBeam_R"),
        ("G_Axle", "G_Beam_front"),
        ("G_Coupler", "G_Beam_front"),
        ("G_Coupler", "G_VMotor"),
        ("G_VMotor", "G_VRoll_R_out"),
        ("G_VMotor", "F_Plate_bottom"),
        ("G_VMotor", "G_Axle_R_out"),
        ("G_VMotor", "G_Bracket_R"),
        ("G_BracketFoot_R", "G_VRoll_R_out"),
        ("G_BracketFoot_R", "G_VMotor"),
        ("G_Bracket_R", "G_VRoll_R_out"),
        ("G_Bracket_R", "G_VMotor"),
        ("G_VShaft", "G_Bracket_R"),
        ("C_HPinion", "G_Beam_front"),
        ("C_HMotor", "G_Beam_front"),
        ("C_HMotor", "G_Beam_rear"),
        ("C_HMotor", "C_Axle_hi_a"),
        ("C_HMotor", "C_Axle_hi_b"),
        ("C_HMotor", "C_Axle_lo_F"),
        ("C_HMotor", "C_Axle_lo_R"),
        ("C_HMotor", "C_HRoll_F_lo"),
        ("C_HMotor", "C_Plate"),
        ("C_HMotor", "C_Cheek_F"),
        ("C_CamBody", "F_Plate_bottom"),
        ("C_CamBody", "C_Plate"),
        ("C_CamLens", "F_VBeam_R"),
        ("C_PanMotor", "C_HMotor"),
        ("C_TiltMotor", "C_CamBody"),
        ("C_Plate", "C_HRoll_F_lo"),
        ("C_End_L", "G_Beam_front"),
        ("C_End_L", "G_Beam_rear"),
        ("C_End_R", "G_Beam_front"),
        ("C_End_R", "G_Beam_rear"),
        ("C_End_L", "G_HBelt_L"),
        ("C_End_R", "G_HBelt_R"),
        ("C_End_R", "C_PanMotor"),
        ("C_End_L", "C_HMotor"),
        ("C_Cheek_R", "G_Beam_rear"),
        ("G_VRoll_R_hi", "G_Beam_front"),
        ("G_VRoll_R_hi", "G_Beam_rear"),
        ("G_VRoll_R_lo", "G_Beam_front"),
        ("G_Axle_R_hi", "F_VBeam_R"),
        ("G_Axle_R_out", "G_Beam_front"),
        ("G_VIdler_R_lo", "G_VPinion_R"),
        ("C_HIdler_a", "C_HPinion"),
        ("G_HBelt_R", "C_Axle_hi_a"),
        ("G_HBelt_R", "C_Axle_hi_b"),
        ("C_HWrap", "C_Axle_hi_a"),
        ("C_HIdler_a", "C_Axle_hi_a"),
        ("G_Bracket_R_in", "G_VIdler_R_hi"),
        ("G_Bracket_R_back", "G_VPinion_R"),
        ("G_BracketScrew_R_a", "G_VMotor"),
        ("G_VPinion_R", "G_Beam_front"),
        ("G_VRoll_R_out", "G_BracketFoot_R"),
        ("C_IdlerBoss_a", "C_HIdler_a"),
        ("C_HRoll_F_hi_b", "G_AxleBlock_R_hi_F"),
        ("C_HRoll_F_hi_b", "G_AxleBlock_R_lo_F"),
        ("C_HRoll_R_hi_b", "G_AxleBlock_R_hi_R"),
        ("C_HRoll_R_hi_b", "G_AxleBlock_R_lo_R"),
        ("C_Top", "C_HRoll_F_hi_a"),
        ("C_Top", "C_HPinion"),
        ("C_Top", "F_Plate_top"),
        ("C_Top", "F_VBeam_R"),
        ("C_Plate", "F_VBeam_R"),
        ("C_CamBody", "F_VBeam_R"),
        ("C_CamLens", "C_Plate"),
        ("C_CamBody", "C_PanBar"),
        ("C_CamLens", "C_PanBar"),
    ]
    angles = {"BL": (-45, -45), "TL": (-45, 45), "TR": (45, 45), "BR": (45, -45)}
    names = {o.name: o for o in bpy.data.objects}
    hit_n = 0
    for tag, x, z in poses:
        set_pose(x, z)
        pan.rotation_euler[2] = math.radians(angles[tag][0])
        tilt.rotation_euler[0] = math.radians(angles[tag][1])
        bpy.context.view_layer.update()
        for a, b in pairs:
            n = overlaps(names.get(a), names.get(b))
            if n:
                hit_n += 1
                report.append(f"HIT {tag} {a} vs {b} tris {n}")
    report.append(f"pair_hits {hit_n}")

    # At each corner, sweep the full pan and tilt range and test the
    # tilt motor against both vertical beams.
    motor_names = ("C_TiltMotor", "C_TiltPlate", "C_TiltShaft")
    beam_names = ("F_VBeam_L", "F_VBeam_R")
    snag = 0
    for tag, x, z in poses:
        set_pose(x, z)
        for pd in (-45, -15, 0, 15, 45):
            for td in (-45, 0, 45):
                pan.rotation_euler[2] = math.radians(pd)
                tilt.rotation_euler[0] = math.radians(td)
                bpy.context.view_layer.update()
                for mn in motor_names:
                    for bn in beam_names:
                        n = overlaps(names.get(mn), names.get(bn))
                        if n:
                            snag += 1
                            report.append(f"SNAG {tag} pan {pd} tilt {td} {mn} vs {bn} tris {n}")
    report.append(f"motor_snags {snag}")

    pan.rotation_euler[2] = math.radians(-45)
    tilt.rotation_euler[0] = math.radians(-45)
    gear_h.rotation_euler[0] = math.radians(-45)
    set_pose(X_LO, H_LO)
    scene.frame_set(0)
    path = r"C:\_o\_dev\anaker_planar2\planar_stage.blend"
    bpy.ops.wm.save_as_mainfile(filepath=path)

    print("X_IN", round(x_in, 4), "X_OUT", round(x_out, 4))
    print("AXLE_Y", round(AXLE_Y, 4), "PR20", round(PR20, 4))
    print("CARRIAGE_LOCAL", tuple(round(v, 4) for v in carriage.location))
    print("NLA", [
        (s.name, round(s.frame_start, 1), round(s.frame_end, 1))
        for s in gantry.animation_data.nla_tracks[0].strips
    ])
    print("REPORT")
    for line in report:
        print(line)
    print("ENV")
    for line in env_hit:
        print(line)
    print("OBJECTS", len(bpy.data.objects))
    print("SAVED", path)
    return path


if __name__ == "__main__" or True:
    build()
