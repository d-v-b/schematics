"""The holder is one bent strip, extruded along the rail. Across devices,
sections, strip thicknesses and drops it builds one valid solid of the
expected extents; its pocket floor, inner-leaf contact and lip contact sit
where the parameters put them; it clears the mattress and stays under the
creep ceiling; and a label engraves it.

One test covers the combinations; the rest each cover one validation error.
"""

import pytest
from build123d import Vector

from holder import HolderParams, holder

TOL = 1e-3


@pytest.mark.parametrize("section", ["full", "clamp", "pocket"])
@pytest.mark.parametrize("device_t,t,drop", [
    (11.5, 3.0, 200.0),   # the laptop, as specified
    (9.3, 3.0, 200.0),    # the phone
    (11.5, 2.5, 160.0),   # thinner strip, shallowest pocket
    (9.3, 2.5, 180.0),
])
def test_holder(section, device_t, t, drop):
    p = HolderParams(device_t=device_t, t=t, drop=drop, section=section, length=10)
    p.validate()
    body = holder(p)
    assert body.is_valid() and len(body.solids()) == 1

    bb = body.bounding_box()
    assert (bb.min.Z, bb.max.Z) == pytest.approx((0, p.length), abs=TOL)
    top = p.top_y if section != "pocket" else p.j_y + p.stub + t / 2
    bottom = -drop - p.gap / 2 - t if section != "clamp" else -p.stub - t / 2
    assert (bb.min.Y, bb.max.Y) == pytest.approx((bottom, top), abs=TOL)

    z = p.length / 2
    if section != "pocket":
        # relaxed, the inner leaf reaches inner_pre into the rail at one point
        x, y = p.inner_contact
        assert x == pytest.approx(-p.rail_t + p.inner_pre, abs=1e-6)
        assert body.is_inside(Vector(x - 0.05, y, z)) and not body.is_inside(Vector(x + 0.05, y, z))
        assert p.protrusion <= p.mattress_clear
        assert p.inner_stress <= p.creep_limit
    if section != "clamp":
        # the J's inside bottom is gap/2 below the seat
        mid = p.back_x + device_t / 2
        assert body.is_inside(Vector(mid, -drop - p.gap / 2 - 0.05, z))
        assert not body.is_inside(Vector(mid, -drop - p.gap / 2 + 0.05, z))
        # the seat: just above it at the hanger face is open slot, and 1 mm
        # below it the J wall has already curved in under the device's rear corner
        assert not body.is_inside(Vector(p.back_x + 0.05, -drop + 0.05, z))
        assert body.is_inside(Vector(p.back_x + 0.05, -drop - 1.0, z))
        # relaxed, the lip reaches lip_pre into the device at one point
        x, y = p.lip_contact
        assert x == pytest.approx(p.back_x + device_t - p.lip_pre, abs=1e-6)
        assert body.is_inside(Vector(x + 0.05, y, z)) and not body.is_inside(Vector(x - 0.05, y, z))
        assert p.lip_stress <= p.creep_limit

    labelled = holder(HolderParams(device_t=device_t, t=t, drop=drop, section=section, length=10, label="ip1.0 t3"))
    assert labelled.is_valid() and labelled.volume < body.volume


def test_non_positive():
    with pytest.raises(ValueError, match="must be positive: t, bend_ri"):
        HolderParams(t=0, bend_ri=-1).validate()


def test_section():
    with pytest.raises(ValueError, match="section must be one of"):
        HolderParams(section="middle").validate()


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
