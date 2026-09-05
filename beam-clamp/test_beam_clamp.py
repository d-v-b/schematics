"""Geometry checks for the beam clamp.

One test covers reasonable parameter combinations and checks the dimensions
that matter for fit; the rest each cover one validation error.
"""

import pytest
from build123d import Align, Compound, Location, Rectangle, ShapeList

from beam_clamp import ClampParams, clamp, profile
from conftest import assert_printable


TOL = 1e-4  # OCCT bounding boxes carry a small padding


def _slice_x(sketch, x_lo, x_hi, y):
    """Bounding box of the sketch material inside x in [x_lo, x_hi] on the line y."""
    eps = 1e-3
    band = Rectangle(x_hi - x_lo, 2 * eps, align=(Align.MIN, Align.MIN)).moved(
        Location((x_lo, y - eps))
    )
    res = sketch & band
    if isinstance(res, ShapeList):
        res = Compound(res)
    return res.bounding_box()


@pytest.mark.parametrize("wall", [2.0, 3.0, 4.0])
@pytest.mark.parametrize("clearance", [-0.2, 0.0, 0.3, 0.6])
@pytest.mark.parametrize("length", [10.0, 40.0])
@pytest.mark.parametrize("label", ["", "w3 c0.3"])
def test_dimensions(wall, clearance, length, label):
    p = ClampParams(wall=wall, clearance=clearance, length=length, label=label)
    part = clamp(p)
    assert part.is_valid()
    if not label:
        assert_printable(part)
    bb = part.bounding_box()
    assert bb.min.X == pytest.approx(-wall, abs=TOL)
    assert bb.max.X == pytest.approx(p.inner_w + wall, abs=TOL)
    assert bb.min.Y == pytest.approx(-wall, abs=TOL)
    assert bb.max.Y == pytest.approx(p.arm_len, abs=TOL)
    assert bb.min.Z == pytest.approx(0, abs=TOL)
    assert bb.max.Z == pytest.approx(length, abs=TOL)

    # bumps protrude exactly bump_h into the cavity at the expected height
    prof = profile(p)
    y_b = p.arm_len - p.bump_from_tip
    left = _slice_x(prof, 0, p.inner_w / 2, y_b)
    right = _slice_x(prof, p.inner_w / 2, p.inner_w, y_b)
    assert left.max.X == pytest.approx(p.bump_h, abs=TOL)
    assert right.min.X == pytest.approx(p.inner_w - p.bump_h, abs=TOL)
    # and the arms are plain walls away from the bump
    assert _slice_x(prof, 0, p.inner_w / 2, p.arm_len / 2).size.X == pytest.approx(0, abs=TOL)

    # a label removes material; no label leaves the plain extrusion
    plain = clamp(ClampParams(wall=wall, clearance=clearance, length=length))
    if label:
        assert part.volume < plain.volume
    else:
        assert part.volume == pytest.approx(plain.volume)


def test_rejects_nonpositive_wall():
    with pytest.raises(ValueError, match="wall must be positive"):
        profile(ClampParams(wall=0))


def test_rejects_span_smaller_than_fillets():
    with pytest.raises(ValueError, match="fillet radius"):
        profile(ClampParams(beam_w=3, clearance=0, fillet_r=2))


def test_rejects_arm_too_short_for_tip():
    with pytest.raises(ValueError, match="arm_len"):
        profile(ClampParams(arm_len=3, fillet_r=2, wall=3))


def test_rejects_bump_off_the_arm():
    with pytest.raises(ValueError, match="bump does not fit"):
        profile(ClampParams(bump_from_tip=0.5))


def test_rejects_label_deeper_than_wall():
    with pytest.raises(ValueError, match="label_depth"):
        profile(ClampParams(label="x", label_depth=3, wall=2))
