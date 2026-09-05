"""Geometry checks for the beam wrap.

One test builds a half over a grid of parameters, mates a rotated copy, and
checks the assembled fit: no interference at any ratchet position, ramps that
collide between positions, flat faces that block separation, and the expected
envelope. The rest each cover one validation error.
"""

import pytest
from build123d import Location

from beam_wrap import WrapParams, assembly, half, profile
from conftest import assert_printable

TOL = 1e-4


def _overlap(a, b):
    r = a & b
    return r.volume if hasattr(r, "volume") else sum(s.volume for s in r)


@pytest.mark.parametrize("wall", [2.0, 3.0, 4.0])
@pytest.mark.parametrize("joint_clearance", [0.15, 0.25, 0.4])
@pytest.mark.parametrize("tooth_h", [0.8, 1.2])
def test_assembled_fit(wall, joint_clearance, tooth_h):
    p = WrapParams(wall=wall, joint_clearance=joint_clearance, tooth_h=tooth_h, length=10)
    lower, upper = assembly(p)
    assert lower.is_valid()
    assert_printable(lower)

    # envelope of one half: outer tab sticks out on the left, arm reaches the lap top
    bb = lower.bounding_box()
    assert bb.min.X == pytest.approx(-(2 * wall + joint_clearance), abs=TOL)
    assert bb.max.X == pytest.approx(p.inner_w + wall, abs=TOL)
    assert bb.min.Y == pytest.approx(-wall, abs=TOL)
    assert bb.max.Y == pytest.approx(p.outer_arm_len, abs=TOL)

    # assembled: the pair encloses the beam and the halves do not interfere
    both = lower.bounding_box().add(upper.bounding_box())
    assert both.min.Y == pytest.approx(-wall, abs=TOL)
    assert both.max.Y == pytest.approx(p.span_h + wall, abs=TOL)
    assert _overlap(lower, upper) == pytest.approx(0, abs=TOL)

    pitch = p.tooth_pitch
    positions = range(-p.cinch_teeth, p.slack_teeth + 1)
    # every ratchet position is interference-free: cinched by cinch_teeth,
    # nominal, and looser by up to slack_teeth
    for k in positions:
        shifted = upper.moved(Location((0, k * pitch, 0)))
        assert _overlap(lower, shifted) == pytest.approx(0, abs=TOL), f"position {k}"

    # between positions the ramps collide (that is the click), and pulling
    # straight up from any engaged position hits the flat faces. The ramps of
    # the two rows are parallel, so they interfere for shifts up to
    # pitch * (1 - joint_clearance / tooth_h); probe halfway to that.
    engaged = tooth_h - joint_clearance
    click = 0.5 * pitch * (1 - joint_clearance / tooth_h)
    for k in positions:
        half_step = upper.moved(Location((0, k * pitch + click, 0)))
        assert _overlap(lower, half_step) > 0, f"half step from {k}"
        pulled = upper.moved(Location((0, k * pitch + 0.3 * engaged, 0)))
        assert _overlap(lower, pulled) > 0, f"pull from {k}"

    # beyond the designed travel the parts collide rather than fit
    too_tight = upper.moved(Location((0, -(p.cinch_teeth + 1) * pitch, 0)))
    assert _overlap(lower, too_tight) > 0
    too_loose = upper.moved(Location((0, (p.slack_teeth + 1) * pitch, 0)))
    assert _overlap(lower, too_loose) > 0


def test_coupon_is_the_two_joint_pieces():
    p = WrapParams(coupon=1, length=10)
    pieces = half(p)
    assert len(pieces.solids()) == 2
    bb = pieces.bounding_box()
    assert bb.min.Y == pytest.approx(p.lap_y0 - p.jog_height - p.coupon_stub, abs=TOL)
    assert bb.max.Y == pytest.approx(p.outer_arm_len, abs=TOL)


def test_rejects_nonpositive_wall():
    with pytest.raises(ValueError, match="wall must be positive"):
        profile(WrapParams(wall=0))


def test_rejects_span_smaller_than_fillets():
    with pytest.raises(ValueError, match="fillet radius"):
        profile(WrapParams(beam_w=3, clearance=0, fillet_r=2))


def test_rejects_negative_joint_clearance():
    with pytest.raises(ValueError, match="joint_clearance"):
        profile(WrapParams(joint_clearance=-0.1))


def test_rejects_teeth_swallowed_by_clearance():
    with pytest.raises(ValueError, match="never engage"):
        profile(WrapParams(tooth_h=0.2, joint_clearance=0.3))


def test_rejects_teeth_taller_than_wall():
    with pytest.raises(ValueError, match="tooth_h"):
        profile(WrapParams(tooth_h=3, wall=3))


def test_rejects_no_teeth():
    with pytest.raises(ValueError, match="at least one tooth"):
        profile(WrapParams(n_teeth=0))


def test_rejects_negative_cinch():
    with pytest.raises(ValueError, match="cinch_teeth"):
        profile(WrapParams(cinch_teeth=-1))


def test_rejects_slack_beyond_row():
    with pytest.raises(ValueError, match="slack_teeth"):
        profile(WrapParams(slack_teeth=4, n_teeth=4))


def test_rejects_zero_slack():
    with pytest.raises(ValueError, match="slack_teeth"):
        profile(WrapParams(slack_teeth=0))


def test_rejects_teeth_in_the_tip_round():
    with pytest.raises(ValueError, match="teeth_from_tip"):
        profile(WrapParams(teeth_from_tip=0.5, wall=3))


def test_rejects_lap_too_short_on_tab_side():
    with pytest.raises(ValueError, match="tab side"):
        profile(WrapParams(lap_len=8, cinch_teeth=0))


def test_rejects_lap_too_short_on_arm_side():
    with pytest.raises(ValueError, match="arm side"):
        profile(WrapParams(lap_len=16))


def test_rejects_bump_off_the_arm():
    with pytest.raises(ValueError, match="bump does not fit"):
        profile(WrapParams(bump_y=130))


def test_rejects_label_deeper_than_wall():
    with pytest.raises(ValueError, match="label_depth"):
        profile(WrapParams(label="x", label_depth=3, wall=2))
