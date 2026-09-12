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
@pytest.mark.parametrize("tooth_h", [1.5, 2.0])
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

    # (with full-length rows the joint may allow more travel than the
    # designed cinch and slack; that is fine, so no collision is asserted
    # beyond them)

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
    assert 0.25 * slab < _overlap(lower, upper) < slab
    assert p.flex().deflection == pytest.approx(p.tooth_h + 0.3)


def test_taper_blends_the_wall_into_the_lap():
    # the arm thins linearly from the wall to the slab over taper_len below
    # the lap: the profile loses half a (wall - slab) x taper_len triangle per
    # arm compared with a square step, and the mating tips still clear it at
    # the cinched position
    p = FlexParams(joint_clearance=0.2, length=10)
    stepped = profile(FlexParams(joint_clearance=0.2, length=10, taper_len=0))
    tapered = profile(p)
    assert stepped.area - tapered.area == pytest.approx((p.wall - p.slab) * p.taper_len / 2 * 2, rel=1e-3)
    lower, upper = assembly(p)
    cinched = upper.moved(Location((0, -p.cinch_travel, 0)))
    assert _overlap(lower, cinched) == pytest.approx(0, abs=TOL)


def test_rejects_taper_into_the_elbow():
    with pytest.raises(ValueError, match="taper_len"):
        profile(FlexParams(taper_len=200))


def test_coupon_is_the_two_joint_pieces():
    p = FlexParams(coupon=1, length=10, joint_clearance=0.2)
    pieces = half(p)
    assert len(pieces.solids()) == 2
    bb = pieces.bounding_box()
    assert bb.min.Y == pytest.approx(min(p.lap_y0, p.inner_step) - p.taper_len - p.coupon_stub, abs=TOL)
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


def test_rejects_teeth_too_tall_for_the_lap():
    with pytest.raises(ValueError, match="lap slab"):
        profile(FlexParams(wall=3, tooth_h=1.6))


def test_rejects_teeth_swallowed_by_clearance():
    with pytest.raises(ValueError, match="never engage"):
        profile(FlexParams(tooth_h=0.2, joint_clearance=0.3))


def test_rejects_nonpositive_pitch():
    with pytest.raises(ValueError, match="tooth_pitch"):
        profile(FlexParams(tooth_pitch=0))


def test_rejects_negative_cinch():
    with pytest.raises(ValueError, match="cinch_teeth"):
        profile(FlexParams(cinch_teeth=-1))


def test_rejects_bad_slack():
    with pytest.raises(ValueError, match="slack_teeth"):
        profile(FlexParams(slack_teeth=0))


def test_rows_run_the_full_lap_with_no_empty_runs():
    p = FlexParams(joint_clearance=0.2)
    # the arm's toothed span is whole teeth, both rows are long, and the two
    # laps are the same thickness: slab plus teeth on each side
    assert p.recess_y1 - p.recess_y0 == pytest.approx(p.n_arm * p.tooth_pitch)
    assert p.n_tab >= 3 and p.n_arm >= 5
    assert 2 * (p.slab + p.tooth_h / 2) == pytest.approx(p.wall - p.joint_clearance)


def test_rejects_teeth_in_the_tip_round():
    with pytest.raises(ValueError, match="teeth_from_tip"):
        profile(FlexParams(teeth_from_tip=0.5))


def test_rejects_lap_too_short_on_tab_side():
    with pytest.raises(ValueError, match="tooth row on the tab"):
        profile(FlexParams(lap_len=12, cinch_teeth=0))



def test_rejects_label_deeper_than_wall():
    with pytest.raises(ValueError, match="label_depth"):
        profile(FlexParams(label="x", label_depth=5, wall=5))


def test_base_dovetail_groove_stays_inside_the_base():
    from assembly import interference

    p = FlexParams(wall=5, dovetail_w=42, length=10)
    lower, upper = assembly(p)
    # the groove is cut into the base: the halves' envelope is unchanged
    assert lower.bounding_box().min.Y == pytest.approx(-p.wall, abs=1e-4)
    assert upper.bounding_box().max.Y == pytest.approx(p.span_h + p.wall, abs=1e-4)
    assert lower.volume < assembly(FlexParams(wall=5, length=10))[0].volume
    assert_printable(lower)
    both = interference("flex", p)
    assert all(v == pytest.approx(0, abs=1e-3) for k, v in both.items() if k not in ("lower", "upper"))


def test_coupon_id_is_engraved_on_the_top_face():
    plain = half(FlexParams(coupon=1, length=10, joint_clearance=0.2))
    tagged = half(FlexParams(coupon=1, length=10, joint_clearance=0.2, label="jc0.2 th0.8"))
    assert tagged.volume < plain.volume
    for a in "XYZ":
        assert getattr(tagged.bounding_box().size, a) == pytest.approx(getattr(plain.bounding_box().size, a), abs=1e-4)
