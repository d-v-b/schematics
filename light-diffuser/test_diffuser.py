"""The diffuser is a tube open at both ends, whose outer face
follows r(theta, z), whose wall is wall thick level across it, and which
prints as modeled.

One test covers combinations of size, ripple and sway; the rest each cover
one validation error.
"""

import math

import numpy as np
import pytest
from build123d import Axis, GeomType

from conftest import volume
from diffuser import DiffuserParams, diffuser

TOL = 0.01


def _area(x, y) -> float:
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def _radial_hits(body, theta: float, z: float) -> list[float]:
    """Radii at which a level ray out from the axis at (theta, z) crosses the body."""
    c, s = math.cos(theta), math.sin(theta)
    hits = body.find_intersection_points(Axis((0, 0, z), (c, s, 0)))
    return sorted(q.X * c + q.Y * s for q, *_ in hits if q.X * c + q.Y * s > 0)


def _normals_z(face, nu: int = 1200, nv: int = 60) -> list[float]:
    """Z of the face's outward normal on an nu x nv grid over its whole
    (u, v) range."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepLProp import BRepLProp_SLProps
    from OCP.BRepTools import BRepTools
    from OCP.TopAbs import TopAbs_REVERSED

    u0, u1, v0, v1 = BRepTools.UVBounds_s(face.wrapped)
    props = BRepLProp_SLProps(BRepAdaptor_Surface(face.wrapped), 1, 1e-9)
    sign = -1 if face.wrapped.Orientation() == TopAbs_REVERSED else 1
    out = []
    for u in np.linspace(u0, u1, nu):
        for v in np.linspace(v0, v1, nv):
            props.SetParameters(u, v)
            out.append(sign * props.Normal().Z())
    return out


@pytest.mark.parametrize("d,h,wall,lobes,ripple_a,sway,sway_periods,sway_turns", [
    (170.0, 150.0, 1.0, 24, 4.5, 16.0, 1.0, 1),   # the default
    (170.0, 150.0, 1.0, 24, 4.5, 0.0, 1.0, 1),    # straight flutes
    (160.0, 120.0, 1.2, 12, 3.0, 12.0, 1.5, 0),   # fewer flutes swaying together
    (100.0, 60.0, 1.6, 24, 0.0, 16.0, 1.0, 1),    # no ripple: a plain tube
])
def test_shape(d, h, wall, lobes, ripple_a, sway, sway_periods, sway_turns):
    p = DiffuserParams(d=d, h=h, wall=wall, lobes=lobes, ripple_a=ripple_a, sway=sway,
                       sway_periods=sway_periods, sway_turns=sway_turns)
    body = diffuser(p)
    assert body.is_valid() and len(body.solids()) == 1

    # stands on the bed, centered on the axis, h tall, d + 2 ripple_a across
    bb = body.bounding_box()
    assert bb.min.Z == pytest.approx(0, abs=TOL)
    assert bb.max.Z == pytest.approx(h, abs=TOL)
    for lo, hi in ((bb.min.X, bb.max.X), (bb.min.Y, bb.max.Y)):
        assert -lo == pytest.approx(d / 2 + ripple_a, abs=TOL)
        assert hi == pytest.approx(d / 2 + ripple_a, abs=TOL)

    # through the wall, the outer face follows r(theta, z) and the inner
    # face lies wall from the outer face's section, measured level
    rng = np.random.default_rng(0)
    fine = np.linspace(0, 2 * np.pi, 40000, endpoint=False)
    # including just above the bottom rim and just below the top one
    zs = np.concatenate([rng.uniform(0.5, h - 0.5, 10), [0.1, 1.5, h - 0.1, h - 1.5]])
    for theta, z in zip(rng.uniform(0, 2 * np.pi, 14), zs):
        r_in, r_out = _radial_hits(body, theta, z)
        assert r_out == pytest.approx(float(p.r(theta, z)), abs=TOL)
        ox, oy = p.outer_xy(fine, z)
        gap = np.hypot(ox - r_in * math.cos(theta), oy - r_in * math.sin(theta)).min()
        assert gap == pytest.approx(wall, abs=TOL)

    # the tube is clear and open from end to end
    for x, y in [(0.0, 0.0), (0.3 * d, 0.1 * d)]:
        assert not body.find_intersection_points(Axis((x, y, -1), (0, 0, 1)))

    # the volume adds up: the area between the outer and inner sections,
    # all the way up. With this many flutes both are the same at every height
    th = np.linspace(0, 2 * np.pi, 40000, endpoint=False)
    expected = (_area(*p.outer_xy(th, 0.0)) - _area(*p.inner_xy(th, 0.0))) * h
    assert volume(body) == pytest.approx(expected, rel=1e-4)

    # nothing leans more than 45 degrees from vertical: the rims lie
    # level, and the walls' normals are sampled over their whole parameter range
    limit = -math.sin(math.radians(45)) - 1e-6
    for f in body.faces():
        if f.geom_type == GeomType.PLANE:
            assert abs(f.normal_at().Z) == pytest.approx(1)
        else:
            assert min(_normals_z(f)) >= limit
    assert p.steepest() <= 45


def test_rejects_non_positive_size():
    with pytest.raises(ValueError, match="d, h and wall must be positive"):
        diffuser(DiffuserParams(wall=0.0))


def test_rejects_fractional_counts():
    with pytest.raises(ValueError, match="must be whole numbers"):
        diffuser(DiffuserParams(sway_turns=0.5))


def test_rejects_no_lobes():
    with pytest.raises(ValueError, match="lobes must be at least 1"):
        diffuser(DiffuserParams(lobes=0))


def test_rejects_negative_ripple():
    with pytest.raises(ValueError, match="must not be negative"):
        diffuser(DiffuserParams(sway=-1.0))


def test_rejects_ripple_over_the_spread():
    with pytest.raises(ValueError, match="over the 20 allowed"):
        diffuser(DiffuserParams(ripple_a=5.5))


def test_rejects_no_room_inside():
    with pytest.raises(ValueError, match="leave room inside"):
        diffuser(DiffuserParams(d=10.0, ripple_a=4.5))


def test_rejects_sway_too_short_for_the_sections():
    with pytest.raises(ValueError, match="sway fewer times"):
        diffuser(DiffuserParams(sway_periods=40.0, sway=0.8))


def test_rejects_steep_overhang():
    with pytest.raises(ValueError, match="over 45"):
        diffuser(DiffuserParams(sway=40.0))


def test_rejects_crests_too_tight_for_the_wall():
    with pytest.raises(ValueError, match="too tight for the 1 wall"):
        diffuser(DiffuserParams(lobes=60, sway=0.0))


def test_rejects_too_big_for_the_bed():
    with pytest.raises(ValueError, match="over the 256 bed"):
        diffuser(DiffuserParams(d=250.0))
