"""The base is a floor and a wall round a pocket slack wider than the pot,
whose crest waves between trough_h and peak_h over lobes periods, and it
prints as modeled.

One test covers combinations of pot size, slack, wave and rounding; the
rest each cover one validation error.
"""

import math

import pytest
from build123d import Axis

from base import BaseParams, base
from conftest import assert_printable

TOL = 1e-3


def _top_z(body, r: float, theta: float) -> float:
    """The highest point of the body straight above (r, theta)."""
    x, y = r * math.cos(theta), r * math.sin(theta)
    hits = body.find_intersection_points(Axis((x, y, -1), (0, 0, 1)))
    return max(pt.Z for pt, *_ in hits)


@pytest.mark.parametrize("pot_d,slack,peak_h,trough_h,lobes,crest_r,foot_chamfer", [
    (70.0, 5.0, 10.0, 6.0, 6, 1.0, 0.5),   # the default
    (70.0, 5.0, 10.0, 10.0, 6, 1.0, 0.5),  # no wave: a level rim
    (70.0, 3.0, 14.0, 5.0, 9, 0.8, 0.0),   # a deep wave, more lobes, no chamfer
    (120.0, 8.0, 20.0, 12.0, 3, 0.0, 0.4), # a big pot, three lobes, sharp crest
])
def test_fit(pot_d, slack, peak_h, trough_h, lobes, crest_r, foot_chamfer):
    p = BaseParams(pot_d=pot_d, slack=slack, peak_h=peak_h, trough_h=trough_h, lobes=lobes,
                   crest_r=crest_r, foot_chamfer=foot_chamfer)
    assert p.pocket_d == pytest.approx(pot_d + slack)
    assert p.outer_d == pytest.approx(pot_d + slack + 2 * p.wall)
    assert p.crest_z(0) == pytest.approx(peak_h)
    assert p.crest_z(math.pi / lobes) == pytest.approx(trough_h)

    body = base(p)
    assert body.is_valid() and len(body.solids()) == 1

    # sits on the bed, centered on the axis, reaching peak_h at the crests
    bb = body.bounding_box()
    assert bb.min.Z == pytest.approx(0, abs=TOL)
    assert bb.max.Z == pytest.approx(peak_h, abs=0.01)
    assert bb.size.X == pytest.approx(p.outer_d, abs=0.01)
    assert bb.size.Y == pytest.approx(p.outer_d, abs=0.01)

    # mid-wall, the crest follows the wave exactly: peaks and troughs lobes
    # times round, and in between
    mid = (p.pocket_d + p.outer_d) / 4
    for k in range(lobes):
        assert _top_z(body, mid, 2 * math.pi * k / lobes) == pytest.approx(peak_h, abs=0.01)
        assert _top_z(body, mid, math.pi * (2 * k + 1) / lobes) == pytest.approx(trough_h, abs=0.01)
    assert _top_z(body, mid, 0.37) == pytest.approx(p.crest_z(0.37), abs=0.01)

    # the crest's corners are rounded outward, to crest_r, on both sides
    r_in, r_out = p.pocket_d / 2, p.outer_d / 2
    d = 0.2
    shoulder = peak_h - crest_r + math.sqrt(crest_r**2 - (crest_r - d) ** 2) if crest_r > d else peak_h
    assert _top_z(body, r_in + d, 0) == pytest.approx(shoulder, abs=0.01)
    assert _top_z(body, r_out - d, 0) == pytest.approx(shoulder, abs=0.01)

    # the volume adds up: the floor inside the pocket, plus a wall whose
    # mean height is midway between peak and trough, less the rounding and
    # the chamfer
    wall = (math.pi * (r_out**2 - r_in**2) * (peak_h + trough_h) / 2
            - 2 * (1 - math.pi / 4) * crest_r**2 * 2 * math.pi * (r_in + r_out) / 2
            - foot_chamfer**2 / 2 * 2 * math.pi * r_out)
    assert body.volume == pytest.approx(math.pi * r_in**2 * p.floor + wall, rel=2e-3)

    # the pocket is clear to its full diameter down to the floor
    assert _top_z(body, 0, 0) == pytest.approx(p.floor, abs=TOL)
    assert _top_z(body, p.pocket_d / 2 - 0.01, 1.0) == pytest.approx(p.floor, abs=TOL)

    assert_printable(body)


def test_rejects_non_positive_size():
    with pytest.raises(ValueError, match="pot_d, wall and floor must be positive"):
        base(BaseParams(wall=0.0))


def test_rejects_negative_slack():
    with pytest.raises(ValueError, match="slack must not be negative"):
        base(BaseParams(slack=-1.0))


def test_rejects_no_lobes():
    with pytest.raises(ValueError, match="lobes must be at least 1"):
        base(BaseParams(lobes=0))


def test_rejects_peak_below_trough():
    with pytest.raises(ValueError, match="peak_h must not be below trough_h"):
        base(BaseParams(peak_h=5.0, trough_h=6.0))


def test_rejects_trough_too_low_for_rounding():
    with pytest.raises(ValueError, match="above the floor at its troughs"):
        base(BaseParams(trough_h=3.0))


def test_rejects_crest_rounding_over_half_the_wall():
    with pytest.raises(ValueError, match="crest_r must be at least 0 and under half the wall"):
        base(BaseParams(crest_r=1.2))


def test_rejects_foot_chamfer_too_big():
    with pytest.raises(ValueError, match="foot_chamfer"):
        base(BaseParams(foot_chamfer=2.0))


def test_rejects_too_big_for_the_bed():
    with pytest.raises(ValueError, match="over the 256 bed"):
        base(BaseParams(pot_d=260.0))
