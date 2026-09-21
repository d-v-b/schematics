"""The bracket is an L of the asked-for legs, thickness and width, rounded
like a thick stroke, with a gusset in the inside corner on one side and a
bolt hole through each leg; it prints on its side.

One test covers combinations of the dimensions; the rest each cover one
validation error.
"""

import math

import pytest
from build123d import GeomType

from bracket import BracketParams, bracket, profile
from conftest import assert_printable

TOL = 1e-3


def _hole_faces(body, hole_d):
    return [f for f in body.faces()
            if f.geom_type == GeomType.CYLINDER and abs(f.radius - hole_d / 2) < TOL]


@pytest.mark.parametrize("leg,thickness,width,rib_t,rib_l,hole_d", [
    (40.0, 6.0, 30.0, 5.0, 25.0, 8.6),   # the default: M8, 40 mm legs
    (50.0, 5.0, 30.0, 4.0, 30.0, 8.6),   # longer, thinner legs
    (40.0, 8.0, 36.0, 8.0, 20.0, 8.6),   # heavy
    (30.0, 4.0, 20.0, 3.0, 15.0, 5.5),   # M5 size
])
@pytest.mark.parametrize("label", ["", "M8 t6"])
def test_fit(leg, thickness, width, rib_t, rib_l, hole_d, label):
    washer_d = 16.0 if hole_d > 8 else 10.0
    p = BracketParams(leg=leg, thickness=thickness, width=width, rib_t=rib_t, rib_l=rib_l,
                      hole_d=hole_d, washer_d=washer_d, label=label)
    t, r = thickness, p.fillet_r
    body = bracket(p)
    assert body.is_valid() and len(body.solids()) == 1

    # outer faces on the axes, legs reaching leg, width up z
    bb = body.bounding_box()
    assert (bb.min.X, bb.min.Y, bb.min.Z) == pytest.approx((0, 0, 0), abs=TOL)
    assert (bb.size.X, bb.size.Y, bb.size.Z) == pytest.approx((leg, leg, width), abs=TOL)

    # the profile is the L's centreline dilated by t / 2: every point of its
    # outline away from the inside corner is t / 2 from that centreline
    face = profile(p).faces()[0]
    def centreline_dist(x, y):
        c = t / 2
        da = math.hypot(max(x - (leg - c), 0, c - x), y - c)  # leg along x
        db = math.hypot(x - c, max(y - (leg - c), 0, c - y))  # leg along y
        return min(da, db)
    for e in face.outer_wire().edges():
        for pt in e.positions([i / 10 for i in range(11)]):
            if math.hypot(pt.X - t, pt.Y - t) > r + TOL:  # clear of the inside fillet
                assert centreline_dist(pt.X, pt.Y) == pytest.approx(t / 2, abs=TOL)

    # one hole through each leg, hole_d across, axis square to the leg,
    # hole_at out from the corner and centred on the width
    holes = _hole_faces(body, hole_d)
    assert len(holes) == 2
    # a bore runs thickness through its leg and is hole_d across the other two ways
    by_axis = {}
    for f in holes:
        b = f.bounding_box()
        axis = "y" if b.size.Y == pytest.approx(t, abs=TOL) else "x"
        by_axis[axis] = b
        through = b.size.Y if axis == "y" else b.size.X
        across = b.size.X if axis == "y" else b.size.Y
        assert through == pytest.approx(t, abs=TOL)
        assert across == pytest.approx(hole_d, abs=TOL)
        assert b.size.Z == pytest.approx(hole_d, abs=TOL)
    assert sorted(by_axis) == ["x", "y"]  # one through each leg
    assert p.hole_at == pytest.approx(t + (leg - t) / 2)  # midway along the free length
    for axis, b in by_axis.items():
        c = b.center()
        assert c.Z == pytest.approx(width / 2, abs=TOL)
        along, square = (c.X, c.Y) if axis == "y" else (c.Y, c.X)
        assert along == pytest.approx(p.hole_at, abs=TOL)
        assert square == pytest.approx(t / 2, abs=TOL)  # through the leg's thickness

    # volume: the stroked L (two stadiums less their overlap at the corner)
    # plus the inside fillet, the gusset over its rib_t, less the two holes
    # (less a sliver of lettering)
    stadium = (leg - t) * t + math.pi * t**2 / 4
    overlap = 3 * math.pi * t**2 / 16 + t**2 / 4
    fillet = r**2 * (1 - math.pi / 4)
    l_area = 2 * stadium - overlap + fillet
    gusset = rib_l**2 / 2 - fillet
    expect = l_area * width + gusset * rib_t - 2 * math.pi * (hole_d / 2) ** 2 * t
    if label:
        ink = 0.5 * p.label_size**2 * len(label) * p.label_depth
        assert expect - ink < body.volume < expect
    else:
        assert body.volume == pytest.approx(expect, rel=1e-6)

    # nothing overhangs but the short bridges over the two holes
    assert_printable(body, ignore=lambda f: f in holes)


def test_rejects_non_positive_dimension():
    with pytest.raises(ValueError, match="must be positive"):
        profile(BracketParams(thickness=0.0))


def test_rejects_leg_too_short():
    with pytest.raises(ValueError, match="leg must be longer than twice the thickness"):
        profile(BracketParams(leg=10.0, thickness=6.0))


def test_rejects_hole_wider_than_bracket():
    with pytest.raises(ValueError, match="hole_d must be less than width"):
        profile(BracketParams(width=8.0, hole_d=8.6, rib_t=1.0))


def test_rejects_washer_against_other_leg():
    with pytest.raises(ValueError, match="washer would foul the other leg"):
        profile(BracketParams(hole_x=12.0))


def test_rejects_washer_off_end_of_leg():
    with pytest.raises(ValueError, match="washer would overhang the end of the leg"):
        profile(BracketParams(hole_x=35.0))


def test_rejects_washer_against_rib():
    with pytest.raises(ValueError, match="washer would foul the rib"):
        profile(BracketParams(width=24.0))


def test_rejects_rib_past_leg():
    with pytest.raises(ValueError, match="rib_l must end before the leg's rounded end"):
        profile(BracketParams(rib_l=33.0))


def test_rejects_rib_through_width():
    with pytest.raises(ValueError, match="rib_t must be less than width"):
        profile(BracketParams(rib_t=30.0))


def test_rejects_label_through_leg():
    with pytest.raises(ValueError, match="label_depth must be less than width"):
        profile(BracketParams(label="x", label_depth=30.0))
