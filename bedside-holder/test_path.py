"""The turtle walks lines and tangent arcs; its segments know their ends,
midpoints and offset faces."""

import math

import pytest

from path import Turtle, sample


def test_turtle():
    # a stadium: up 10, a half-turn left of radius 2, down 10, a half-turn
    # left again; it closes on itself
    tw = Turtle((0.0, 0.0), math.pi / 2)
    tw.line(10).arc(2, math.pi).line(10).arc(2, math.pi)
    up, top, down, bottom = tw.segs
    assert up.end == pytest.approx((0, 10))
    assert top.centre == pytest.approx((-2, 10))
    assert top.mid == pytest.approx((-2, 12))
    assert top.end == pytest.approx((-4, 10))
    assert down.end == pytest.approx((-4, 0))
    assert bottom.end == pytest.approx((0, 0), abs=1e-12)
    assert tw.heading == pytest.approx(2 * math.pi + math.pi / 2)

    # the left face lies inside a left-turning stadium, 0.5 in from the
    # centreline everywhere; on the top arc it is at radius 1.5
    for x, y in top.sample(0.5):
        assert math.hypot(x + 2, y - 10) == pytest.approx(1.5)
    assert min(x for x, _ in sample(tw.segs, 0.5)) == pytest.approx(-3.5)
    assert max(x for x, _ in sample(tw.segs, -0.5)) == pytest.approx(0.5)

    # a right turn puts its centre on the right
    right = Turtle((0.0, 0.0), 0.0).arc(3, -math.pi / 2).segs[0]
    assert right.centre == pytest.approx((0, -3))
    assert right.end == pytest.approx((3, -3))

    # walking segments back retraces them to the start
    back = Turtle(tw.segs[2].end, tw.segs[2].h1 + math.pi).replay_reversed(tw.segs[:3])
    assert back.pos == pytest.approx((0, 0), abs=1e-12)
