"""The clip is a flat plate lying flush on the beam's face: a strip of
constant width following straight runs and tangent circular arcs in the
plane of that face, so the loops bulge along the beam, with a lip block at
each end reaching down the beam's sides. Relaxed, the lips are closer
together than the beam is wide, so fitting it stretches the loops. Its
compliance model matches the geometry it builds, it stays under the creep
ceiling, and it prints flat.

One test covers combinations of the loop geometry; the rest each cover one
validation error.
"""

import math

import pytest
from build123d import GeomType, Vector

from clip import ClipParams, centreline, clip, profile, strip
from conftest import assert_printable

TOL = 1e-3


@pytest.mark.parametrize("loops,loop_r,turn,t,plate", [
    (3, 3.25, 125.0, 1.6, 3.0),    # the default: a 3 mm plate
    (3, 3.0, 130.0, 1.6, 3.0),     # longer runs, thinner margin
    (2, 4.0, 120.0, 1.6, 2.0),     # two big loops, thinner plate
    (3, 3.5, 130.0, 1.2, 6.0),     # narrow strip, thicker plate
])
def test_fit(loops, loop_r, turn, t, plate):
    p = ClipParams(loops=loops, loop_r=loop_r, turn=turn, t=t, plate=plate)
    a = math.radians(turn)
    s = p.span / 2
    body = clip(p)
    assert body.is_valid() and len(body.solids()) == 1

    # as printed: the serpentine flat on the bed in XY, the loops bulging
    # along the beam (+y) from the flats' centreline on y = 0, the plate
    # rising plate in z and the lips a further lip above it. Across the beam
    # the lips' outer faces span the gap plus both lips; along the beam the
    # lips cover the whole serpentine
    h = 2 * loop_r * (1 - math.cos(a))
    assert p.loop_h == pytest.approx(h)
    bb = body.bounding_box()
    assert bb.size.X == pytest.approx(p.span + 2 * p.lip_t, abs=TOL)
    assert (bb.min.Y, bb.max.Y) == pytest.approx((-t / 2, h + t / 2), abs=TOL)
    assert (bb.min.Z, bb.max.Z) == pytest.approx((0, plate + p.lip), abs=TOL)

    # the beam sits on the plate's top face at z = plate: all of the strip
    # between the lips is in that plane, so the clip lies flush
    band = strip(p)
    contact = [f for f in body.faces() if abs(f.center().Z - plate) < TOL and f.normal_at().Z > 0.99]
    # (the band less its two half-disc end caps, which the lips swallow)
    assert sum(f.area for f in contact) == pytest.approx(band.area - math.pi * t**2 / 4, rel=1e-4)

    # each lip's inside face is square to the span at +-span / 2, running
    # the lips' full width along the beam and up to the foot of its lead-in
    # chamfer, so the relaxed gap is span
    for side in (-1, 1):
        inner = [f for f in body.faces()
                 if abs(f.center().X - side * s) < TOL and abs(abs(f.normal_at().X) - 1) < 1e-6]
        assert len(inner) == 1
        fb = inner[0].bounding_box()
        assert (fb.min.Y, fb.max.Y) == pytest.approx((-t / 2, h + t / 2), abs=TOL)
        assert (fb.min.Z, fb.max.Z) == pytest.approx((0, plate + p.lip - p.chamfer), abs=TOL)
    assert p.interference == pytest.approx(p.beam_w - p.span)

    # the centreline is flats and three tangent arcs of loop_r per loop, and
    # the strip is exactly t thick along all of it: its area is t times the
    # centreline's length plus the two round end caps, which fails if any
    # part of the strip overlapped another, and every point of its outline
    # is t / 2 from the centreline
    line = centreline(p)
    arcs = [e for e in line.edges() if e.geom_type == GeomType.CIRCLE]
    assert len(arcs) == 3 * loops
    assert all(e.radius == pytest.approx(loop_r, abs=TOL) for e in arcs)
    assert band.area == pytest.approx(t * line.length + math.pi * t**2 / 4, rel=1e-4)
    for e in band.edges():
        for pt in e.positions([i / 8 for i in range(9)]):
            assert line.distance_to(Vector(pt.X, pt.Y, 0)) == pytest.approx(t / 2, abs=TOL)

    # the neck, where a loop's feet pass closest, is clear by at least
    # min_gap, and the flats between loops are not negative
    assert p.neck == pytest.approx(4 * loop_r * math.sin(a) - 2 * loop_r - t)
    assert p.neck >= p.min_gap and p.flat >= 0

    # the compliance model's closed form agrees with the integral of y^2
    # (height above the strip's centreline) along the centreline it built
    y0 = 0.0
    numeric = 0.0
    for e in line.edges():
        n = 4000
        for pt in e.positions([(i + 0.5) / n for i in range(n)]):
            numeric += (pt.Y - y0) ** 2 * e.length / n
    assert p.bend_integral == pytest.approx(numeric, rel=1e-4)

    # stiffness, grip and crown stress follow from it; stress is
    # independent of the plate's thickness and stays under the creep ceiling
    inertia = plate * t**3 / 12
    assert p.stiffness == pytest.approx(p.modulus * inertia / numeric, rel=1e-4)
    assert p.grip == pytest.approx(p.stiffness * p.interference)
    assert p.crown_stress == pytest.approx(p.modulus * p.interference * h * t / (2 * numeric), rel=1e-4)
    assert p.crown_stress <= p.creep_limit

    assert_printable(body)


def test_rejects_non_positive_dimension():
    with pytest.raises(ValueError, match="must be positive"):
        profile(ClipParams(t=0.0))


def test_rejects_span_not_under_beam():
    with pytest.raises(ValueError, match="span must be less than beam_w"):
        profile(ClipParams(span=40.0))


def test_rejects_turn_out_of_range():
    with pytest.raises(ValueError, match="turn must be between 0 and 180"):
        profile(ClipParams(turn=0.0))


def test_rejects_thin_lip():
    with pytest.raises(ValueError, match="lip_t must be at least t"):
        profile(ClipParams(lip_t=1.0))


def test_rejects_loops_not_fitting():
    with pytest.raises(ValueError, match="loops do not fit"):
        profile(ClipParams(loops=4))


def test_rejects_tight_neck():
    with pytest.raises(ValueError, match="neck"):
        profile(ClipParams(turn=140.0))


def test_rejects_over_creep_ceiling():
    with pytest.raises(ValueError, match="creep"):
        profile(ClipParams(creep_limit=5.0))


def test_rejects_chamfer_short_of_interference():
    with pytest.raises(ValueError, match="lead-in"):
        profile(ClipParams(chamfer=0.5))


def test_rejects_chamfer_through_lip():
    with pytest.raises(ValueError, match="chamfer must be less than lip_t and lip"):
        profile(ClipParams(chamfer=3.0))
