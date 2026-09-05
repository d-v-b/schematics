"""Geometry checks for the compliant (flex) beam wrap.

One test builds a half over a grid of parameters with a positive clearance,
mates a rotated copy, and checks the ratchet: no interference at any allowed
position, ramps that collide between positions, flat faces that block
separation, a flush outer profile, and no unsupported overhangs. A second
test checks that a negative clearance produces exactly the intended
interference. The rest each cover one validation error.
"""

import pytest
from build123d import Location

from beam_flex import FlexParams, assembly, half, profile
from conftest import assert_printable

TOL = 1e-4


def _overlap(a, b):
    r = a & b
    return r.volume if hasattr(r, "volume") else sum(s.volume for s in r)


@pytest.mark.parametrize("wall", [5.0, 6.0])
@pytest.mark.parametrize("joint_clearance", [0.1, 0.2, 0.4])
@pytest.mark.parametrize("tooth_h", [0.6, 0.8])
@pytest.mark.parametrize("length", [10.0, 50.0])
def test_assembled_fit(wall, joint_clearance, tooth_h, length):
    p = FlexParams(wall=wall, joint_clearance=joint_clearance, tooth_h=tooth_h, length=length)
    lower, upper = assembly(p)
    assert lower.is_valid()

    # flush outside: nothing sticks out beyond the walls on either half
    bb = lower.bounding_box()
    assert bb.min.X == pytest.approx(-wall, abs=TOL)
    assert bb.max.X == pytest.approx(p.inner_w + wall, abs=TOL)
    assert bb.min.Y == pytest.approx(-wall, abs=TOL)
    assert bb.max.Y == pytest.approx(p.outer_arm_len, abs=TOL)
    both = lower.bounding_box().add(upper.bounding_box())
    assert both.min.X == pytest.approx(-wall, abs=TOL)
    assert both.max.X == pytest.approx(p.inner_w + wall, abs=TOL)
    assert both.max.Y == pytest.approx(p.span_h + wall, abs=TOL)

    pitch = p.tooth_pitch
    positions = range(-p.cinch_teeth, p.slack_teeth + 1)
    for k in positions:
        shifted = upper.moved(Location((0, k * pitch, 0)))
        assert _overlap(lower, shifted) == pytest.approx(0, abs=TOL), f"position {k}"

    engaged = tooth_h - joint_clearance
    click = 0.5 * pitch * (1 - joint_clearance / tooth_h)
    for k in positions:
        assert _overlap(lower, upper.moved(Location((0, k * pitch + click, 0)))) > 0, f"click from {k}"
        assert _overlap(lower, upper.moved(Location((0, k * pitch + 0.3 * engaged, 0)))) > 0, f"pull from {k}"

    assert _overlap(lower, upper.moved(Location((0, -(p.cinch_teeth + 1) * pitch, 0)))) > 0
    assert _overlap(lower, upper.moved(Location((0, (p.slack_teeth + 1) * pitch, 0)))) > 0

    assert_printable(lower)


def test_negative_clearance_is_the_intended_interference():
    p = FlexParams(joint_clearance=-0.3, length=10)
    lower, upper = assembly(p)
    # the as-printed laps overlap by exactly the interference, on both sides,
    # and nowhere else
    r = lower & upper
    solids = list(r.solids())
    assert solids
    for s in solids:
        bb = s.bounding_box()
        assert bb.min.X < 0 or bb.max.X > p.inner_w  # inside a wall, not the cavity
        assert p.lap_y0 - 1e-6 <= bb.min.Y and bb.max.Y <= p.span_h - p.lap_y0 + 1e-6
    # the overlap is a 0.3 mm slab over the nested laps (both sides), thinned
    # where the recess and teeth are; the tooth ramps add only thin slivers
    slab = 0.3 * p.lap_len * p.length * 2
    assert 0.4 * slab < _overlap(lower, upper) < slab
    assert p.flex().deflection == pytest.approx(p.tooth_h + 0.3)


def test_shoulder_fillets_add_material_without_touching_the_tips():
    plain = profile(FlexParams(shoulder_r=0, joint_clearance=0.2))
    rounded = profile(FlexParams(joint_clearance=0.2))
    # two fillets, each a square minus a quarter circle
    r = 1.0
    assert rounded.area - plain.area == pytest.approx(2 * (r * r - 3.14159265 * r * r / 4), rel=1e-3)
    # and the assembled fit is unchanged at the cinched position, where the
    # mating tips come closest to the shoulders
    p = FlexParams(joint_clearance=0.2, length=10)
    lower, upper = assembly(p)
    cinched = upper.moved(Location((0, -p.cinch_travel, 0)))
    assert _overlap(lower, cinched) == pytest.approx(0, abs=TOL)


def test_rejects_shoulder_fillet_larger_than_tip_round():
    with pytest.raises(ValueError, match="shoulder_r"):
        profile(FlexParams(shoulder_r=2.0))


def test_coupon_is_the_two_joint_pieces():
    p = FlexParams(coupon=1, length=10, joint_clearance=0.2)
    pieces = half(p)
    assert len(pieces.solids()) == 2
    bb = pieces.bounding_box()
    assert bb.min.Y == pytest.approx(min(p.lap_y0, p.inner_step) - p.coupon_stub, abs=TOL)
    assert bb.max.Y == pytest.approx(p.outer_arm_len, abs=TOL)
    assert_printable(pieces)


def test_rejects_nonpositive_wall():
    with pytest.raises(ValueError, match="wall must be positive"):
        profile(FlexParams(wall=0))


def test_rejects_span_smaller_than_fillets():
    with pytest.raises(ValueError, match="fillet radius"):
        profile(FlexParams(beam_w=3, clearance=0, fillet_r=2))


def test_rejects_unknown_material():
    with pytest.raises(ValueError, match="material"):
        profile(FlexParams(material="steel"))


def test_rejects_teeth_too_tall_for_half_wall():
    with pytest.raises(ValueError, match="half wall"):
        profile(FlexParams(wall=3, tooth_h=1.2))


def test_rejects_teeth_swallowed_by_clearance():
    with pytest.raises(ValueError, match="never engage"):
        profile(FlexParams(tooth_h=0.2, joint_clearance=0.3))


def test_rejects_no_teeth():
    with pytest.raises(ValueError, match="at least one tooth"):
        profile(FlexParams(n_teeth=0))


def test_rejects_negative_cinch():
    with pytest.raises(ValueError, match="cinch_teeth"):
        profile(FlexParams(cinch_teeth=-1))


def test_rejects_bad_slack():
    with pytest.raises(ValueError, match="slack_teeth"):
        profile(FlexParams(slack_teeth=0))


def test_rejects_teeth_in_the_tip_round():
    with pytest.raises(ValueError, match="teeth_from_tip"):
        profile(FlexParams(teeth_from_tip=0.5))


def test_rejects_lap_too_short_on_tab_side():
    with pytest.raises(ValueError, match="tab side"):
        profile(FlexParams(lap_len=8, cinch_teeth=0))


def test_rejects_lap_too_short_on_arm_side():
    with pytest.raises(ValueError, match="arm side"):
        profile(FlexParams(lap_len=16))


def test_rejects_label_deeper_than_wall():
    with pytest.raises(ValueError, match="label_depth"):
        profile(FlexParams(label="x", label_depth=5, wall=5))
