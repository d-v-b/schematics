"""The mechanics model is in equilibrium, matches hand calculations where
there are some, scales with the load as it should, and its rated load
really is the load at which the weakest mode reaches the safety factor.

One test covers combinations of the anchor and the loading; the rest each
cover one error.
"""

import math

import pytest

from anchor import AnchorParams
from mechanics import (
    G,
    Loading,
    axle_loads,
    beam,
    bearing_sets,
    cam_forces,
    capacity_kg,
    check,
    modes,
    rated_kg,
    stations,
    trigger_pull,
)


@pytest.mark.parametrize("kw,n", [
    ({}, 1),                                                # the default, worst case
    ({}, 2),                                                # all four cams bearing
    ({"alpha": 12.0, "reach_min": 33.0, "reach_max": 46.0}, 1),
    ({"cam_t": 8.0, "plate_t": 5.0, "drop": 110.0}, 2),
])
def test_mechanics(kw, n):
    p, ld = AnchorParams(**kw), Loading(cams_per_wall=n)
    W, k = ld.W, p.k

    # each wall carries half the load as friction; the reaction runs through the axle at alpha
    F, N, R = cam_forces(p, W, n)
    assert 2 * n * F == pytest.approx(W)
    assert F / N == pytest.approx(k)
    assert math.hypot(F, N) == pytest.approx(R)

    # the axle: every choice of n cams per wall, in equilibrium, the
    # horizontal pushes cancelling and the vertical ones summing to W
    sets = bearing_sets(n)
    assert len(sets) == (4 if n == 1 else 1)
    for b in sets:
        loads = axle_loads(p, W, b)
        assert sum(l[1] for l in loads) == pytest.approx(0, abs=1e-9)
        assert sum(l[2] for l in loads) == pytest.approx(W)

    # the beam: a single central load P gives P L / 4 and P / 2 each end,
    # and all four cams bearing matches the hand calculation at mid-span
    # (which, by symmetry, is where the peak is)
    ys, span = stations(p)
    m, ra, rb = beam([(span / 2, 0.0, 100.0)], span)
    assert (m, ra, rb) == pytest.approx((100 * span / 4, 50, 50), rel=1e-3)
    F4, N4, _ = cam_forces(p, W, 2)
    mz = W / 2 * span / 2 - F4 * ((span / 2 - ys[0]) + (span / 2 - ys[1]))
    mx = N4 * (ys[1] - ys[0])
    m4, ra4, rb4 = beam(axle_loads(p, W, (0, 1, 2, 3)), span)
    assert m4 == pytest.approx(math.hypot(mx, mz), rel=1e-3)
    assert ra4 == pytest.approx(W / 2) and rb4 == pytest.approx(W / 2)

    # every load-bearing mode's demand rises with the load, all but the
    # wall indent in proportion; slip's doesn't change at all
    at1, at2 = modes(p, ld, W), modes(p, ld, 2 * W)
    for a, b in zip(at1, at2):
        if not a.scales:
            assert b.demand == a.demand
        elif a.name == "wall indent":
            assert b.demand > a.demand
        else:
            assert b.demand == pytest.approx(2 * a.demand)

    # each mode's capacity is where its safety factor reaches 1, and the
    # rated load is where the weakest reaches ld.sf
    for mode in at1:
        if mode.scales:
            cap = capacity_kg(p, ld, mode.name)
            at_cap = next(x for x in modes(p, ld, cap * G) if x.name == mode.name)
            assert at_cap.sf == pytest.approx(1, rel=1e-6)
    rated = rated_kg(p, ld)
    assert min(x.sf for x in modes(p, ld, rated * G) if x.scales) == pytest.approx(ld.sf, rel=1e-6)
    check(p, Loading(load_kg=0.99 * rated, cams_per_wall=n))

    # the trigger always has to pull against the bands, but not hard
    assert 0 < trigger_pull(p, ld) < 50


def test_overload():
    with pytest.raises(ValueError, match="exceeds the rated"):
        check(AnchorParams(), Loading(load_kg=50.0))


def test_cams_per_wall():
    with pytest.raises(ValueError, match="cams_per_wall"):
        modes(AnchorParams(), Loading(cams_per_wall=3))


def test_unknown_bolt():
    with pytest.raises(ValueError, match="thread data"):
        modes(AnchorParams(bolt=7, hole=7.4), Loading())
