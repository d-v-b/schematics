"""The bar has the asked-for section, a row of through slots on the pitch,
ends that stay inside the pivot circle, and prints flat.

One test covers combinations of length, pitch, slot size and count; the
rest each cover one validation error.
"""

import math

import pytest
from build123d import CenterOf

from bolt_bar import BarParams, bar, outline, profile
from conftest import assert_printable

TOL = 1e-3


@pytest.mark.parametrize("length,pitch,end_margin,slots,expect_n", [
    (200.0, 40.0, 20.0, 0, 5),   # default: 20-60-100-140-180
    (200.0, 40.0, 30.0, 0, 4),   # 40-80-120-160: the end slots are centred on the pivots
    (100.0, 40.0, 20.0, 0, 2),   # 60 mm span fits two at 40 (20 and 60), centred at 30 and 70
    (80.0, 40.0, 40.0, 0, 1),    # one slot, in the middle; R40 end arcs centred there too
    (120.0, 35.0, 10.0, 3, 3),   # fixed count
])
@pytest.mark.parametrize("end_r", [20.0, 40.0, 0.0])
@pytest.mark.parametrize("slot_w,slot_l,width,thickness", [
    (6.6, 30.0, 40.0, 4.0),
    (6.4, 20.0, 40.0, 4.0),
    (5.0, 5.0, 30.0, 3.0),       # round holes
])
@pytest.mark.parametrize("label", ["", "p40 s30"])
def test_fit(length, pitch, end_margin, slots, expect_n, end_r, slot_w, slot_l, width, thickness, label):
    p = BarParams(length=length, width=width, thickness=thickness, slot_w=slot_w, slot_l=slot_l,
                  pitch=pitch, end_margin=end_margin, slots=slots, end_r=end_r, label=label)
    assert p.n_slots == expect_n
    body = bar(p)
    assert body.is_valid() and len(body.solids()) == 1

    # section and length as asked
    bb = body.bounding_box()
    assert bb.size.X == pytest.approx(length, abs=TOL)
    assert bb.size.Y == pytest.approx(width, abs=TOL)
    assert bb.size.Z == pytest.approx(thickness, abs=TOL)

    # slots are through, on the centreline, on the pitch, centred on the bar,
    # and each is slot_l long by slot_w wide
    xs = p.slot_xs
    assert len(xs) == expect_n
    assert all(b - a == pytest.approx(pitch) for a, b in zip(xs, xs[1:]))
    assert sum(xs) == pytest.approx(0, abs=1e-9)
    assert length / 2 - xs[-1] >= end_margin - 1e-9
    plan = profile(p)
    assert len(plan.faces()) == 1
    inner = [w for w in plan.wires() if not w.is_same(plan.faces()[0].outer_wire())]
    assert len(inner) == expect_n
    for w, x in zip(sorted(inner, key=lambda w: w.center(CenterOf.MASS).X), xs):
        wb = w.bounding_box()
        assert wb.center().X == pytest.approx(x, abs=TOL)
        assert wb.center().Y == pytest.approx(0, abs=TOL)
        assert wb.size.X == pytest.approx(slot_l, abs=TOL)
        assert wb.size.Y == pytest.approx(slot_w, abs=TOL)
        assert w.length == pytest.approx(2 * (slot_l - slot_w) + math.pi * slot_w, abs=TOL)

    # each end stays within end_r of its pivot (end_r in from the tip): no
    # point of the outline beyond the pivot is farther than end_r from it
    plan_outline = outline(p)
    if end_r > 0:
        piv = length / 2 - end_r
        for e in plan_outline.edges():
            for pt in e.positions([i / 20 for i in range(21)]):
                if pt.X >= piv - TOL:
                    assert math.hypot(pt.X - piv, pt.Y) <= end_r + TOL
        # and the tip is where the arc says: end_sagitta proud of the corners
        assert plan_outline.bounding_box().max.X == pytest.approx(length / 2, abs=TOL)
        assert p.end_sagitta == pytest.approx(end_r - math.sqrt(end_r**2 - (width / 2) ** 2))
        # and the whole outline is symmetric about both axes
        assert plan_outline.bounding_box().center().X == pytest.approx(0, abs=TOL)

    # volume: bar minus the end caps minus the corner rounds minus the slots
    # (minus a sliver of lettering). With arc ends the corner rounds are not
    # right angles, so bound them instead of computing them.
    slot_area = (slot_l - slot_w) * slot_w + math.pi * (slot_w / 2) ** 2
    solid = length * width - expect_n * slot_area
    if end_r > 0:
        theta = 2 * math.asin(width / 2 / end_r)
        segment = end_r**2 / 2 * (theta - math.sin(theta))
        solid -= 2 * (p.end_sagitta * width - segment)
        fillet_lo, fillet_hi = (0.0, 0.0) if p.end_is_semicircle else (4 * p.corner_r**2, 0.0)
    else:
        fillet_lo = fillet_hi = 4 * p.corner_r**2 * (1 - math.pi / 4)
    label_area = 0.5 * p.label_depth / thickness * width * pitch if label else 0.0
    lo = (solid - fillet_lo - label_area) * thickness
    hi = (solid - fillet_hi) * thickness
    assert lo - 1e-6 < body.volume <= hi + 1e-6
    if not label and (end_r == 0 or p.end_is_semicircle):
        assert body.volume == pytest.approx(hi, rel=1e-6)

    assert_printable(body)


def test_rejects_merging_slots():
    with pytest.raises(ValueError, match="pitch must exceed slot_l"):
        profile(BarParams(pitch=30.0, slot_l=30.0))


def test_rejects_slot_shorter_than_wide():
    with pytest.raises(ValueError, match="slot_l must be at least slot_w"):
        profile(BarParams(slot_w=6.6, slot_l=5.0))


def test_rejects_slot_wider_than_bar():
    with pytest.raises(ValueError, match="slot_w must be less than width"):
        profile(BarParams(width=6.0, slot_w=6.6))


def test_rejects_no_slot_fitting():
    with pytest.raises(ValueError, match="no slot fits"):
        profile(BarParams(length=30.0, end_margin=20.0, end_r=0.0))


def test_rejects_end_slot_breaking_out():
    with pytest.raises(ValueError, match="break out"):
        profile(BarParams(length=100.0, pitch=40.0, slots=3))


def test_rejects_end_arc_narrower_than_bar():
    with pytest.raises(ValueError, match="end_r must be 0 or at least width / 2"):
        profile(BarParams(end_r=15.0))


def test_rejects_end_arcs_crossing():
    with pytest.raises(ValueError, match="length must be at least 2 \\* end_r"):
        profile(BarParams(length=60.0, end_margin=10.0, end_r=40.0))


def test_semicircle_end_matches_slot_pitch():
    # at the defaults the tip is a semicircle whose centre is the first slot's centre
    p = BarParams()
    assert p.end_is_semicircle
    assert p.length / 2 - p.end_r == pytest.approx(p.slot_xs[-1])


def test_pivot_in_slot():
    assert BarParams().pivot_in_slot                           # R20: the pivot is the first slot's centre
    assert not BarParams(end_r=40.0).pivot_in_slot             # slots 5-35 and 45-75 from the tip: 40 is the bridge
    assert BarParams(end_r=40.0, end_margin=30.0).pivot_in_slot  # 4 slots, the end ones centred 40 from the tip
    assert BarParams(length=80.0, end_margin=40.0, end_r=40.0).pivot_in_slot


def test_rejects_non_positive_section():
    with pytest.raises(ValueError, match="must be positive"):
        profile(BarParams(thickness=0.0))


def test_rejects_corner_too_big():
    with pytest.raises(ValueError, match="corner_r"):
        profile(BarParams(corner_r=25.0))


def test_rejects_label_through_bar():
    with pytest.raises(ValueError, match="label_depth"):
        profile(BarParams(label="x", label_depth=4.0))
