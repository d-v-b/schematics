"""The holder is one bent strip, extruded along the rail. Across devices,
strip thicknesses, drops, leans and lengths (a 1 mm coupon slice or a real
part) it builds one valid solid of the expected extents; its inner-leaf
contact, pocket floor, seat, lip contact and leaning hanger sit where the
parameters put them; the pad touches the rail face at pad_y and blends into
the hanger without touching its device-side face; it clears the mattress
and stays under the creep ceiling; and a label engraves it where it fits:
the top face of a thin slice, the hanger's rail-side face of a real part.

The pocket is checked in its own frame (HolderParams.world): u across the
slot away from the hanger, v up the hanger, from the J's centre.

One test covers the combinations; the rest each cover one validation error.
"""

import math

import pytest
from build123d import Vector

from holder import HolderParams, holder, pad_outline

TOL = 1e-3


@pytest.mark.parametrize("length", [1.0, 10.0])
@pytest.mark.parametrize("device_t,t,drop,lean", [
    (11.5, 3.0, 200.0, 7.0),   # the laptop, as specified
    (9.3, 3.0, 200.0, 7.0),    # the phone
    (11.5, 2.5, 160.0, 5.0),   # thinner strip, shallowest pocket, less lean
    (9.3, 2.5, 180.0, 9.0),    # more lean
])
def test_holder(length, device_t, t, drop, lean):
    p = HolderParams(device_t=device_t, t=t, drop=drop, lean=lean, length=length)
    p.validate()
    body = holder(p)
    assert body.is_valid() and len(body.solids()) == 1

    bb = body.bounding_box()
    assert (bb.min.Z, bb.max.Z) == pytest.approx((0, p.length), abs=TOL)
    assert (bb.min.Y, bb.max.Y) == pytest.approx((-drop - p.gap / 2 - t, p.top_y), abs=TOL)

    z = p.length / 2

    def inside(q):
        return body.is_inside(Vector(q[0], q[1], z))

    # relaxed, the inner leaf reaches inner_pre into the rail at one point
    x, y = p.inner_contact
    assert x == pytest.approx(-p.rail_t + p.inner_pre, abs=1e-6)
    assert inside((x - 0.05, y)) and not inside((x + 0.05, y))
    assert p.protrusion <= p.mattress_clear
    assert p.inner_stress <= p.creep_limit
    back = -p.gap / 2  # the hanger's device-side face, in u
    # the J's centre, where the device seats, is drop below the rail top
    assert p.world(0, 0)[1] == pytest.approx(-drop, abs=1e-9)
    # the hanger leans: 30 up it, its device-side face is still at u = back
    assert inside(p.world(back - 0.05, 30)) and not inside(p.world(back + 0.05, 30))
    # the J's inside bottom is gap/2 below the seat
    assert inside(p.world(0, -p.gap / 2 - 0.05)) and not inside(p.world(0, -p.gap / 2 + 0.05))
    # the seat: just above it at the hanger face is open slot, and 1 mm
    # below it the J wall has already curved in under the device's rear corner
    assert not inside(p.world(back + 0.05, 0.05)) and inside(p.world(back + 0.05, -1.0))
    # relaxed, the lip reaches lip_pre into the device at one point
    u, v = p.local(p.lip_contact)
    assert u == pytest.approx(back + device_t - p.lip_pre, abs=1e-6)
    assert inside(p.world(u + 0.05, v)) and not inside(p.world(u - 0.05, v))
    assert p.lip_stress <= p.creep_limit
    # the pad's round nose touches the rail face at pad_y, and only there
    assert inside((0.05, -p.pad_y)) and not inside((-0.05, -p.pad_y))
    assert not inside((0.05, -p.pad_y + p.pad_r + 0.5)) and not inside((0.05, -p.pad_y - p.pad_r - 0.5))
    # the pad stays on the rail side: the hanger's device-side face is flat
    # across the pad's whole blend
    up, dn = (p.local(q)[1] for q in p.pad_blend)
    for v in (up, (up + dn) / 2, dn):
        assert inside(p.world(back - 0.05, v)) and not inside(p.world(back + 0.05, v))
    # and it blends in smoothly: fillet, nose and fillet meet each other and
    # the hanger's rail-side face without a corner
    fillet_up, nose, fillet_dn = pad_outline(p)
    down = Vector(*p.hanger_dir, 0)
    for a_, b_ in ((down, fillet_up.tangent_at(0)), (fillet_up.tangent_at(1), nose.tangent_at(0)),
                   (nose.tangent_at(1), fillet_dn.tangent_at(0)), (fillet_dn.tangent_at(1), down)):
        assert a_.cross(b_).length == pytest.approx(0, abs=1e-6) and a_.dot(b_) > 0

    labelled = holder(HolderParams(device_t=device_t, t=t, drop=drop, lean=lean, length=length,
                                   label="ip1.0 lp0.75 t3"))
    assert labelled.is_valid() and labelled.volume < body.volume
    cut = body - labelled
    if length < p.label_size + 1:
        # a thin slice carries its ID in its top face, within the hanger's width
        assert cut.bounding_box().min.Z == pytest.approx(length - p.label_depth, abs=TOL)
        (fx, fy), (nx, ny) = p.hanger_start, p.hanger_n
        assert max(abs((v.X - fx) * nx + (v.Y - fy) * ny) for v in cut.vertices()) < t / 2
    else:
        # a real part carries it in the hanger's rail-side face, hidden in use
        (fx, fy), (nx, ny) = p.hanger_start, p.hanger_n
        depth = [(v.X - fx) * nx + (v.Y - fy) * ny + t / 2 for v in cut.vertices()]
        assert min(depth) == pytest.approx(0, abs=TOL) and max(depth) == pytest.approx(p.label_depth, abs=TOL)


def test_non_positive():
    with pytest.raises(ValueError, match="must be positive: t, bend_ri"):
        HolderParams(t=0, bend_ri=-1).validate()


def test_arc_too_tight():
    with pytest.raises(ValueError, match="radius must exceed t / 2"):
        HolderParams(lip_flare_r=1.4).validate()


def test_label_too_deep():
    with pytest.raises(ValueError, match="label_depth 3 must be less than t 3"):
        HolderParams(label_depth=3.0).validate()


def test_inner_leaf_cannot_lean():
    with pytest.raises(ValueError, match="inner leaf cannot lean in"):
        HolderParams(inner_len=2.0, inner_flare_r=2.0, inner_pre=4.0).validate()


def test_lip_cannot_reach():
    with pytest.raises(ValueError, match="lip reaches the device before it stops leaning"):
        HolderParams(lip_r=200.0, lip_lean=20.0).validate()


def test_lip_flare_too_small():
    with pytest.raises(ValueError, match="lip_flare_deg must exceed lip_lean"):
        HolderParams(lip_flare_deg=4.0).validate()


def test_mattress_clearance():
    with pytest.raises(ValueError, match="more than the 3 mattress clearance"):
        HolderParams(mattress_clear=3.0).validate()


def test_too_big_for_the_bed():
    with pytest.raises(ValueError, match="over the 250 bed limit"):
        HolderParams(drop=250.0).validate()


def test_inner_leaf_creep():
    with pytest.raises(ValueError, match="inner leaf would sit at"):
        HolderParams(inner_pre=1.5).validate()


def test_lip_creep():
    with pytest.raises(ValueError, match="lip would sit at"):
        HolderParams(lip_base=4.0).validate()


def test_pad_off_the_rail():
    with pytest.raises(ValueError, match="pad hangs off the bottom of the rail"):
        HolderParams(pad_y=156.0).validate()


def test_pad_off_the_hanger():
    with pytest.raises(ValueError, match="pad must meet the hanger between the rail top and the pocket"):
        HolderParams(drop=140.0).validate()


def test_pad_fillet_too_small():
    with pytest.raises(ValueError, match="pad_fillet 2 is too small to reach the hanger"):
        HolderParams(pad_fillet=2.0).validate()


def test_lean_too_small():
    with pytest.raises(ValueError, match="lean 1 is too small"):
        HolderParams(lean=1.0).validate()
