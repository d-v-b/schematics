"""The strip is a stadium of the asked-for length and width with a hole
through its centre, and it prints flat.

One test covers combinations of length, width, hole and thickness; the rest
each cover one validation error.
"""

import math

import pytest

from conftest import assert_printable
from strip import StripParams, profile, strip

TOL = 1e-3


@pytest.mark.parametrize("length,half_width,hole_d,thickness", [
    (40.0, 9.0, 6.0, 3.0),    # the default: 40 x 18, 6 mm hole
    (60.0, 9.0, 6.0, 3.0),    # longer
    (30.0, 6.0, 3.2, 2.0),    # smaller all round
    (18.0, 9.0, 6.0, 3.0),    # length = width: the stadium closes up to a disk
])
def test_fit(length, half_width, hole_d, thickness):
    p = StripParams(length=length, half_width=half_width, hole_d=hole_d, thickness=thickness)
    assert p.wall == pytest.approx(half_width - hole_d / 2)
    body = strip(p)
    assert body.is_valid() and len(body.solids()) == 1

    # length along X, width along Y, centred on the origin, sitting on z = 0
    bb = body.bounding_box()
    assert bb.size.X == pytest.approx(length, abs=TOL)
    assert bb.size.Y == pytest.approx(2 * half_width, abs=TOL)
    assert bb.size.Z == pytest.approx(thickness, abs=TOL)
    assert bb.center().X == pytest.approx(0, abs=TOL)
    assert bb.center().Y == pytest.approx(0, abs=TOL)
    assert bb.min.Z == pytest.approx(0, abs=TOL)

    # one face, one hole, the hole on the origin and hole_d across
    plan = profile(p)
    assert len(plan.faces()) == 1
    face = plan.faces()[0]
    inner = face.inner_wires()
    assert len(inner) == 1
    assert inner[0].length == pytest.approx(math.pi * hole_d, abs=TOL)
    ib = inner[0].bounding_box()
    assert ib.center().X == pytest.approx(0, abs=TOL)
    assert ib.center().Y == pytest.approx(0, abs=TOL)

    # the outline is a stadium: every point on it is half_width from the
    # straight centreline segment between the arc centres
    c = length / 2 - half_width
    for e in face.outer_wire().edges():
        for pt in e.positions([i / 20 for i in range(21)]):
            dx = max(abs(pt.X) - c, 0.0)
            assert math.hypot(dx, pt.Y) == pytest.approx(half_width, abs=TOL)

    # volume: the stadium less the hole
    stadium = (length - 2 * half_width) * 2 * half_width + math.pi * half_width**2
    hole = math.pi * (hole_d / 2) ** 2
    assert body.volume == pytest.approx((stadium - hole) * thickness, rel=1e-6)

    assert_printable(body)


def test_rejects_non_positive_dimension():
    with pytest.raises(ValueError, match="must be positive"):
        profile(StripParams(thickness=0.0))


def test_rejects_hole_wider_than_strip():
    with pytest.raises(ValueError, match="hole_d must be less than the strip's width"):
        profile(StripParams(half_width=3.0, hole_d=6.0))


def test_rejects_length_shorter_than_width():
    with pytest.raises(ValueError, match="length must be at least 2 \\* half_width"):
        profile(StripParams(length=16.0, half_width=9.0))
