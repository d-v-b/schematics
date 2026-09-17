"""The spacer is a disk of the asked-for radius and thickness with a through
bore down its axis, and it prints flat.

One test covers combinations of radius, bore and thickness; the rest each
cover one validation error.
"""

import math

import pytest

from conftest import assert_printable
from spacer import SpacerParams, profile, spacer

TOL = 1e-3


@pytest.mark.parametrize("outer_r,hole_d,thickness", [
    (20.0, 6.0, 3.0),    # the default: R20 x 3 with a 6 mm bore
    (20.0, 6.0, 10.0),   # a deeper standoff
    (10.0, 3.2, 2.0),    # small, for a lighter screw
    (25.0, 6.6, 1.2),    # thin and wide
])
@pytest.mark.parametrize("label", ["", "R20 d6"])
def test_fit(outer_r, hole_d, thickness, label):
    p = SpacerParams(outer_r=outer_r, hole_d=hole_d, thickness=thickness, label=label)
    assert p.wall == pytest.approx(outer_r - hole_d / 2)
    body = spacer(p)
    assert body.is_valid() and len(body.solids()) == 1

    # a disk of the asked-for size, centred on the origin, sitting on z = 0
    bb = body.bounding_box()
    assert bb.size.X == pytest.approx(2 * outer_r, abs=TOL)
    assert bb.size.Y == pytest.approx(2 * outer_r, abs=TOL)
    assert bb.size.Z == pytest.approx(thickness, abs=TOL)
    assert bb.center().X == pytest.approx(0, abs=TOL)
    assert bb.center().Y == pytest.approx(0, abs=TOL)
    assert bb.min.Z == pytest.approx(0, abs=TOL)

    # the plan is an annulus: one face, one hole, both circles on the axis
    plan = profile(p)
    assert len(plan.faces()) == 1
    face = plan.faces()[0]
    assert face.outer_wire().length == pytest.approx(2 * math.pi * outer_r, abs=TOL)
    inner = face.inner_wires()
    assert len(inner) == 1
    assert inner[0].length == pytest.approx(math.pi * hole_d, abs=TOL)
    ib = inner[0].bounding_box()
    assert ib.center().X == pytest.approx(0, abs=TOL)
    assert ib.center().Y == pytest.approx(0, abs=TOL)
    assert ib.size.X == pytest.approx(hole_d, abs=TOL)

    # the bore goes right through: it is the same size at both faces
    top = next(f for f in body.faces() if abs(f.center().Z - thickness) < TOL and f.normal_at().Z > 0.99)
    bottom = next(f for f in body.faces() if abs(f.center().Z) < TOL and f.normal_at().Z < -0.99)
    # (the label's letters are inner wires of the top face too, off the axis)
    on_axis = [w for w in top.inner_wires()
               if math.hypot(w.bounding_box().center().X, w.bounding_box().center().Y) < hole_d / 2]
    assert len(on_axis) == 1
    assert len(bottom.inner_wires()) == 1
    for w in (on_axis[0], bottom.inner_wires()[0]):
        wb = w.bounding_box()
        assert wb.center().X == pytest.approx(0, abs=TOL)
        assert wb.center().Y == pytest.approx(0, abs=TOL)
        assert wb.size.X == pytest.approx(hole_d, abs=TOL)
        assert wb.size.Y == pytest.approx(hole_d, abs=TOL)

    # volume: the annulus, less whatever the lettering engraves away. Bound
    # the lettering generously rather than computing the glyphs.
    annulus = math.pi * (outer_r**2 - (hole_d / 2) ** 2) * thickness
    if label:
        ink = 0.5 * p.label_size**2 * len(label) * p.label_depth
        assert annulus - ink < body.volume < annulus
    else:
        assert body.volume == pytest.approx(annulus, rel=1e-6)

    assert_printable(body)


def test_rejects_non_positive_thickness():
    with pytest.raises(ValueError, match="outer_r and thickness must be positive"):
        profile(SpacerParams(thickness=0.0))


def test_rejects_non_positive_outer_r():
    with pytest.raises(ValueError, match="outer_r and thickness must be positive"):
        profile(SpacerParams(outer_r=-1.0))


def test_rejects_non_positive_hole():
    with pytest.raises(ValueError, match="hole_d must be positive"):
        profile(SpacerParams(hole_d=0.0))


def test_rejects_hole_wider_than_disk():
    with pytest.raises(ValueError, match="hole_d must be less than the disk"):
        profile(SpacerParams(outer_r=3.0, hole_d=6.0))


def test_rejects_label_through_spacer():
    with pytest.raises(ValueError, match="label_depth must be less than thickness"):
        profile(SpacerParams(label="x", label_depth=3.0))
