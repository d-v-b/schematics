"""The bar has the asked-for section, a row of through holes on the pitch,
and prints flat.

One test covers combinations of length, pitch, hole size and count; the
rest each cover one validation error.
"""

import math

import pytest
from build123d import CenterOf

from bolt_bar import BarParams, bar, profile
from conftest import assert_printable

TOL = 1e-3


@pytest.mark.parametrize("length,pitch,end_margin,holes,expect_n", [
    (200.0, 40.0, 20.0, 0, 5),   # default: 20-60-100-140-180
    (100.0, 40.0, 20.0, 0, 2),   # 60 mm span fits two at 40 (20 and 60), centred at 30 and 70
    (40.0, 40.0, 20.0, 0, 1),    # one hole, in the middle
    (120.0, 25.0, 10.0, 3, 3),   # fixed count
])
@pytest.mark.parametrize("hole_d,width,thickness", [(6.6, 40.0, 4.0), (6.4, 40.0, 4.0), (5.0, 30.0, 3.0)])
@pytest.mark.parametrize("label", ["", "p40 d6.6"])
def test_fit(length, pitch, end_margin, holes, expect_n, hole_d, width, thickness, label):
    p = BarParams(length=length, width=width, thickness=thickness, hole_d=hole_d, pitch=pitch,
                  end_margin=end_margin, holes=holes, label=label)
    assert p.n_holes == expect_n
    body = bar(p)
    assert body.is_valid() and len(body.solids()) == 1

    # section and length as asked
    bb = body.bounding_box()
    assert bb.size.X == pytest.approx(length, abs=TOL)
    assert bb.size.Y == pytest.approx(width, abs=TOL)
    assert bb.size.Z == pytest.approx(thickness, abs=TOL)

    # holes are through, round, on the centreline, on the pitch, centred on the bar
    xs = p.hole_xs
    assert len(xs) == expect_n
    assert all(b - a == pytest.approx(pitch) for a, b in zip(xs, xs[1:]))
    assert sum(xs) == pytest.approx(0, abs=1e-9)
    assert length / 2 - xs[-1] >= end_margin - 1e-9
    plan = profile(p)
    assert len(plan.faces()) == 1
    inner = [w for w in plan.wires() if not w.is_same(plan.faces()[0].outer_wire())]
    assert len(inner) == expect_n
    for w, x in zip(sorted(inner, key=lambda w: w.center(CenterOf.MASS).X), xs):
        (edge,) = w.edges()  # one full circle
        assert edge.arc_center.X == pytest.approx(x, abs=TOL)
        assert edge.arc_center.Y == pytest.approx(0, abs=TOL)
        assert edge.radius == pytest.approx(hole_d / 2, abs=TOL)

    # volume: bar minus the corner rounds minus the holes (minus a sliver of lettering)
    solid = length * width - 4 * p.corner_r**2 * (1 - math.pi / 4) - expect_n * math.pi * (hole_d / 2) ** 2
    expect = solid * thickness
    if label:
        assert expect - 0.5 * p.label_depth * width * pitch < body.volume < expect
    else:
        assert body.volume == pytest.approx(expect, rel=1e-6)

    assert_printable(body)


def test_rejects_merging_holes():
    with pytest.raises(ValueError, match="pitch must exceed hole_d"):
        profile(BarParams(pitch=6.0, hole_d=6.6))


def test_rejects_hole_wider_than_bar():
    with pytest.raises(ValueError, match="hole_d must be less than width"):
        profile(BarParams(width=6.0, hole_d=6.6))


def test_rejects_no_hole_fitting():
    with pytest.raises(ValueError, match="no hole fits"):
        profile(BarParams(length=30.0, end_margin=20.0))


def test_rejects_end_hole_breaking_out():
    with pytest.raises(ValueError, match="break out"):
        profile(BarParams(length=80.0, pitch=40.0, holes=3))


def test_rejects_non_positive_section():
    with pytest.raises(ValueError, match="must be positive"):
        profile(BarParams(thickness=0.0))


def test_rejects_corner_too_big():
    with pytest.raises(ValueError, match="corner_r"):
        profile(BarParams(corner_r=25.0))


def test_rejects_label_through_bar():
    with pytest.raises(ValueError, match="label_depth"):
        profile(BarParams(label="x", label_depth=4.0))
