"""The base is a floor, flat or rippled, and a wall round a pocket slack
wider than the pot, whose crest waves between trough_h and peak_h over
lobes periods, and it prints as modeled.

One test covers combinations of pot size, slack, wave and rounding; the
rest each cover one validation error.
"""

import math

import pytest
from build123d import Axis

from base import BaseParams, base
from conftest import assert_printable, volume

TOL = 1e-3


def _top_z(body, r: float, theta: float) -> float:
    """The highest point of the body straight above (r, theta)."""
    return _top_xy(body, r * math.cos(theta), r * math.sin(theta))


def _top_xy(body, x: float, y: float) -> float:
    """The highest point of the body straight above (x, y)."""
    hits = body.find_intersection_points(Axis((x, y, -1), (0, 0, 1)))
    return max(pt.Z for pt, *_ in hits)


def _j1(x: float, n: int = 2000) -> float:
    """Bessel function J1, from its integral form."""
    return sum(math.cos(t - x * math.sin(t))
               for t in ((i + 0.5) * math.pi / n for i in range(n))) / n


@pytest.mark.parametrize("pot_d,slack,peak_h,trough_h,lobes,crest_r,foot_chamfer,ripple_a,ripple_l", [
    (70.0, 5.0, 10.0, 6.0, 6, 1.0, 0.5, 0.0, 40.0),     # the default
    (70.0, 5.0, 10.0, 10.0, 6, 1.0, 0.5, 0.0, 40.0),    # no wave: a level rim
    (70.0, 3.0, 14.0, 5.0, 9, 0.8, 0.0, 0.0, 40.0),     # a deep wave, more lobes, no chamfer
    (120.0, 8.0, 20.0, 12.0, 3, 0.0, 0.4, 0.0, 40.0),   # a big pot, three lobes, sharp crest
    (140.2, 5.0, 25.0, 21.0, 11, 1.0, 0.5, 5.0, 40.0),  # the 15 cm base, rippled floor
    (70.0, 5.0, 12.0, 9.0, 6, 1.0, 0.5, 1.5, 15.0),     # small, fine ripples
])
def test_fit(pot_d, slack, peak_h, trough_h, lobes, crest_r, foot_chamfer, ripple_a, ripple_l):
    p = BaseParams(pot_d=pot_d, slack=slack, peak_h=peak_h, trough_h=trough_h, lobes=lobes,
                   crest_r=crest_r, foot_chamfer=foot_chamfer, ripple_a=ripple_a,
                   ripple_l=ripple_l)
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
    # the chamfer. The ripples add ripple_a on average, plus what is left of
    # cos(kx) cos(ky) = (cos k(x+y) + cos k(x-y)) / 2 over the pocket's disc
    q = 2 * math.pi / ripple_l * math.sqrt(2)
    floor = (math.pi * r_in**2 * (p.floor + ripple_a)
             + ripple_a * 2 * math.pi * r_in * _j1(q * r_in) / q)
    wall = (math.pi * (r_out**2 - r_in**2) * (peak_h + trough_h) / 2
            - 2 * (1 - math.pi / 4) * crest_r**2 * 2 * math.pi * (r_in + r_out) / 2
            - foot_chamfer**2 / 2 * 2 * math.pi * r_out)
    assert volume(body) == pytest.approx(floor + wall, rel=2e-3)

    # the pocket is clear to its full diameter down to the floor, whose top
    # follows the ripples: a peak on the axis, dimples down to floor half a
    # wavelength along, and the cosine everywhere else
    lam = ripple_l
    assert _top_xy(body, 0, 0) == pytest.approx(p.floor_top, abs=0.01)
    assert _top_xy(body, lam / 2, 0) == pytest.approx(p.floor, abs=0.01)
    assert _top_xy(body, lam / 2, lam / 2) == pytest.approx(p.floor_top, abs=0.01)
    assert _top_xy(body, lam / 4, 0.3 * lam) == pytest.approx(p.floor + ripple_a, abs=0.01)
    edge = p.pocket_d / 2 - 0.01
    for x, y in [(13.0, 7.0), (-15.0, 22.0), (edge * math.cos(1.0), edge * math.sin(1.0))]:
        assert _top_xy(body, x, y) == pytest.approx(p.floor_z(x, y), abs=0.01)

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


def test_rejects_bad_ripple():
    with pytest.raises(ValueError, match="ripple_a must not be negative and ripple_l must be positive"):
        base(BaseParams(ripple_l=0.0))


@pytest.mark.parametrize("trough_h,ripple_a", [(3.0, 0.0), (8.0, 2.5)])
def test_rejects_trough_too_low_for_rounding(trough_h, ripple_a):
    # the ripples' peaks count as the floor
    with pytest.raises(ValueError, match="above the floor at its troughs"):
        base(BaseParams(peak_h=10.0, trough_h=trough_h, ripple_a=ripple_a))


def test_rejects_crest_rounding_over_half_the_wall():
    with pytest.raises(ValueError, match="crest_r must be at least 0 and under half the wall"):
        base(BaseParams(crest_r=1.2))


def test_rejects_foot_chamfer_too_big():
    with pytest.raises(ValueError, match="foot_chamfer"):
        base(BaseParams(foot_chamfer=2.0))


def test_rejects_too_big_for_the_bed():
    with pytest.raises(ValueError, match="over the 256 bed"):
        base(BaseParams(pot_d=260.0))
