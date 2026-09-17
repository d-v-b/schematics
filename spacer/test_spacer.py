"""The spacer is the perimeter of a star dilated by a disk: a band of constant
width whose tips reach outer_r, with a clear aperture down the middle for the
screw to pass through, and it prints flat.

One test covers combinations of size, band width, waist and point count; the
rest each cover one validation error.
"""

import math

import pytest
from build123d import GeomType

from conftest import assert_printable
from spacer import SpacerParams, profile, spacer

TOL = 1e-3


def _radii(shape):
    """Distances from the axis to a dense sample of a wire or face boundary."""
    return [math.hypot(pt.X, pt.Y)
            for e in shape.edges()
            for pt in e.positions([i / 60 for i in range(61)])]


@pytest.mark.parametrize("outer_r,band_r,waist,points,thickness", [
    (20.0, 3.0, 0.382, 5, 3.0),   # the default: 5 points, 6 mm band, 7.0 mm aperture
    (20.0, 3.0, 0.5, 5, 3.0),     # fatter waist, 11 mm aperture
    (20.0, 4.0, 0.45, 5, 6.0),    # wider band, thicker spacer
    (15.0, 2.5, 0.5, 6, 3.0),     # six points, smaller
    (25.0, 3.0, 0.382, 7, 2.0),   # seven points, thin
])
def test_fit(outer_r, band_r, waist, points, thickness):
    p = SpacerParams(outer_r=outer_r, band_r=band_r, waist=waist, points=points,
                     thickness=thickness)
    star_r = outer_r - band_r
    assert p.star_r == pytest.approx(star_r)
    assert p.band_w == pytest.approx(2 * band_r)
    # the aperture is the star eroded by the dilation radius
    assert p.aperture == pytest.approx(2 * (star_r * waist - band_r))
    assert p.aperture >= p.min_aperture

    body = spacer(p)
    assert body.is_valid() and len(body.solids()) == 1

    # a flat band sitting on z = 0, centred on the axis
    bb = body.bounding_box()
    assert bb.size.Z == pytest.approx(thickness, abs=TOL)
    assert bb.min.Z == pytest.approx(0, abs=TOL)

    plan = profile(p)
    assert len(plan.faces()) == 1
    face = plan.faces()[0]

    # the tips reach outer_r exactly, and nothing goes beyond it
    outer = face.outer_wire()
    assert max(_radii(outer)) == pytest.approx(outer_r, abs=TOL)

    # exactly one aperture, and it is clear to the full diameter: the nearest
    # material to the axis is aperture / 2 away
    inner = face.inner_wires()
    assert len(inner) == 1
    assert min(_radii(inner[0])) == pytest.approx(p.aperture / 2, abs=TOL)
    assert min(_radii(face)) == pytest.approx(p.aperture / 2, abs=TOL)

    # the dilation rounds every tip to band_r, on centres that sit on the
    # star's circumradius and are evenly spaced round it
    tips = [e for e in outer.edges()
            if e.geom_type == GeomType.CIRCLE and abs(e.radius - band_r) < TOL]
    assert len(tips) == points
    angles = sorted(math.atan2(e.arc_center.Y, e.arc_center.X) for e in tips)
    for e in tips:
        assert math.hypot(e.arc_center.X, e.arc_center.Y) == pytest.approx(star_r, abs=TOL)
    steps = [b - a for a, b in zip(angles, angles[1:])]
    assert steps == pytest.approx([2 * math.pi / points] * (points - 1), abs=1e-6)

    # it is a band, not a disk: well under the solid disk it replaces
    disk = math.pi * outer_r**2
    assert face.area < 0.7 * disk
    assert body.volume == pytest.approx(face.area * thickness, rel=1e-6)

    assert_printable(body)


def test_rejects_non_positive_thickness():
    with pytest.raises(ValueError, match="outer_r and thickness must be positive"):
        profile(SpacerParams(thickness=0.0))


def test_rejects_non_positive_outer_r():
    with pytest.raises(ValueError, match="outer_r and thickness must be positive"):
        profile(SpacerParams(outer_r=-1.0))


def test_rejects_non_positive_band():
    with pytest.raises(ValueError, match="band_r must be positive"):
        profile(SpacerParams(band_r=0.0))


def test_rejects_waist_out_of_range():
    with pytest.raises(ValueError, match="waist must be between 0 and 1"):
        profile(SpacerParams(waist=1.0))


def test_rejects_too_few_points():
    with pytest.raises(ValueError, match="points must be at least 3"):
        profile(SpacerParams(points=2))


def test_rejects_aperture_below_minimum():
    # a fat band on a narrow waist closes the middle up
    with pytest.raises(ValueError, match="clear aperture"):
        profile(SpacerParams(band_r=5.0, waist=0.382))


def test_rejects_aperture_closed_entirely():
    # the erosion eats the whole star: no aperture at all
    with pytest.raises(ValueError, match="clear aperture"):
        profile(SpacerParams(band_r=7.0, waist=0.3))
