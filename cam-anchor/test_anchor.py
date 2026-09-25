"""The anchor's cams reach across the gap from a log spiral whose contact
point is always their outermost point, its trigger retracts and its band
expands them over the whole working range, and every part is a flat
extrusion that prints with its holes along Z.

One test covers combinations of the geometry; the rest each cover one
validation error.
"""

import math

import pytest
from build123d import GeomType

from anchor import (
    AnchorParams,
    cam,
    cam_outline,
    cam_sketch,
    coupon,
    finger_pull,
    plate,
    sleeve,
    tooth_tips,
    torque,
)
from conftest import assert_printable

TOL = 0.05


@pytest.mark.parametrize("kw", [
    {},                                                    # the default
    {"alpha": 12.0, "reach_min": 33.0, "reach_max": 46.0},  # flatter cam, wider range
    {"gap": 70.0, "reach_min": 30.0, "reach_max": 40.0, "plate_w": 20.0},
    {"drop": 110.0, "cam_t": 8.0, "tooth_d": 0.5},
])
def test_anchor(kw):
    p = AnchorParams(**kw)
    p.validate()
    a = math.radians(p.alpha)

    # the reach model: reach_min retracted, reach_max at rho_max, the gap in between
    assert p.reach(0) == pytest.approx(p.reach_min)
    assert p.reach(p.rho_max) == pytest.approx(p.reach_max)
    assert 0 < p.rho_gap < p.rho_max < p.rho_rest
    assert 2 * p.reach(p.rho_gap) == pytest.approx(p.gap)

    # the tooth tips lie on the spiral; the valleys lie tooth_d inside it
    pts = cam_outline(p)[1:]
    for i, (x, z) in enumerate(pts):
        psi = -math.atan2(z, x)
        depth = 0 if i % 2 == 0 else p.tooth_d
        assert math.hypot(x, z) == pytest.approx(p.r(psi) - depth, abs=1e-9)
    assert len(pts) == 2 * len(tooth_tips(p)) - 1

    # the contact point, alpha below the axle's horizontal, is the cam's
    # outermost point in x wherever the cam is, and its mirror's on -x
    for rho in (0.0, p.rho_gap, p.rho_max):
        bb = cam_sketch(p, rho).bounding_box()
        assert bb.max.X == pytest.approx(p.reach(rho), abs=TOL)
        assert cam_sketch(p, rho, mirror=True).bounding_box().min.X == pytest.approx(-p.reach(rho), abs=TOL)
        # (and the wall's reaction then runs through the axle at alpha)
        cx, cz = p.reach(rho), -p.reach(rho) * math.tan(a)
        assert math.atan2(-cz, cx) == pytest.approx(a)

    # over the whole working range, the trigger cord retracts the cam
    # (clockwise) and the band expands it (counter-clockwise), until the
    # band parks it at rho_rest with no leverage left
    steps = [p.rho_rest * i / 40 for i in range(41)]
    assert all(torque(p.trigger_hole(r), p.pull_hole) < 0 for r in steps)
    assert all(torque(p.spring_hole(r), p.sleeve) > 0 for r in steps[:-1])
    assert torque(p.spring_hole(p.rho_rest), p.sleeve) == pytest.approx(0, abs=1e-9)

    # the trigger hole keeps a wall round it inside the valleys of the
    # spiral, and its cord, running down the cam's face, passes the sleeve
    wall = p.r(p.rho_rest / 2) - p.tooth_d - p.trigger_r - p.cord_hole / 2
    assert wall >= p.trigger_in - p.cord_hole / 2 > 3
    for rho in (0.0, p.rho_gap, p.rho_max):
        (hx, hz), (fx, fz) = p.trigger_hole(rho), p.pull_hole
        cord = [(hx + (fx - hx) * i / 200, hz + (fz - hz) * i / 200) for i in range(201)]
        assert all(math.dist(c, p.sleeve) > p.sleeve_od / 2 for c in cord)

    # the lobes clear the sleeve, and the whole cam fits between the walls retracted
    assert p.r_max + p.sleeve_od / 2 < p.drop
    bb = cam_sketch(p).bounding_box()
    assert max(-bb.min.X, bb.max.X) <= p.reach_min + TOL

    # every part: one valid solid, flat on the bed, every bore along Z
    for part, t in ((cam(p), p.cam_t), (plate(p), p.plate_t), (sleeve(p), p.stack),
                    (finger_pull(p), p.pull_t), (coupon(p), 4.0)):
        assert part.is_valid() and len(part.solids()) == 1
        bb = part.bounding_box()
        assert (bb.min.Z, bb.max.Z) == pytest.approx((0, t), abs=1e-6)
        assert max(bb.size.X, bb.size.Y) < 256
        assert_printable(part)
        for f in part.faces().filter_by(GeomType.CYLINDER):
            assert abs(f.normal_at().Z) < 1e-6


def test_gap_outside_reach():
    with pytest.raises(ValueError, match="must include"):
        AnchorParams(gap=95.0).validate()


def test_cam_too_steep():
    with pytest.raises(ValueError, match="slip"):
        AnchorParams(alpha=22.0).validate()


def test_plate_too_wide():
    with pytest.raises(ValueError, match="narrower"):
        AnchorParams(plate_w=70.0).validate()


def test_lobe_hits_sleeve():
    with pytest.raises(ValueError, match="sleeve"):
        AnchorParams(drop=50.0).validate()
