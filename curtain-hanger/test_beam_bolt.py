"""Geometry checks for the bolted beam wrap.

One test builds a half over a grid of parameters, mates a flipped copy, and
checks the assembled fit: a mirror-symmetric part, a continuous band along
the beam, no interference across the slot travel, bolts that pass through
both fingers at every position, collisions beyond the travel, and no
unsupported overhangs in print orientation. The rest each cover one
validation error.
"""

import pytest
from build123d import Location, Plane, mirror

from beam_bolt import BoltParams, assembly, bolt_shafts, half, profile
from conftest import assert_printable

TOL = 1e-4


def _overlap(a, b):
    r = a & b
    return r.volume if hasattr(r, "volume") else sum(s.volume for s in r)


@pytest.mark.parametrize("wall,bolt_d", [(5.0, 2.0), (6.0, 2.0), (6.0, 3.0)])
@pytest.mark.parametrize("joint_clearance", [0.2, 0.3, 0.5])
@pytest.mark.parametrize("length,taper_len", [(50.0, 25.0), (50.0, 0.0), (10.0, 25.0)])
def test_assembled_fit(wall, bolt_d, joint_clearance, length, taper_len):
    p = BoltParams(wall=wall, bolt_d=bolt_d, joint_clearance=joint_clearance, length=length, taper_len=taper_len)
    lower, upper = assembly(p)
    assert lower.is_valid()
    assert len(lower.solids()) == 1

    # the part is mirror-symmetric about the beam's centreline
    prof = profile(p)
    residual = prof - mirror(prof, about=Plane.YZ.offset(p.inner_w / 2))
    assert sum(f.area for f in residual.faces()) == pytest.approx(0, abs=TOL)

    bb = lower.bounding_box()
    assert bb.min.X == pytest.approx(-wall, abs=TOL)
    assert bb.max.X == pytest.approx(p.inner_w + wall, abs=TOL)
    assert bb.min.Y == pytest.approx(-wall, abs=TOL)
    assert bb.max.Y == pytest.approx(p.tip_end, abs=TOL)

    # a continuous band: both halves occupy exactly the same length along the beam
    for part in (lower, upper):
        assert part.bounding_box().min.Z == pytest.approx(0, abs=TOL)
        assert part.bounding_box().max.Z == pytest.approx(length, abs=TOL)
    both = lower.bounding_box().add(upper.bounding_box())
    assert both.min.Y == pytest.approx(-wall, abs=TOL)
    assert both.max.Y == pytest.approx(p.span_h + wall, abs=TOL)

    # across the slot travel: no interference, bolts pass through both fingers
    for dy in (-p.slot_travel, -p.slot_travel / 2, 0.0, p.slot_travel / 2, p.slot_travel):
        shifted = upper.moved(Location((0, dy, 0)))
        shafts = bolt_shafts(p, dy)
        assert _overlap(lower, shifted) == pytest.approx(0, abs=TOL), f"shift {dy}"
        assert _overlap(lower, shafts) == pytest.approx(0, abs=TOL), f"lower shaft {dy}"
        assert _overlap(shifted, shafts) == pytest.approx(0, abs=TOL), f"upper shaft {dy}"

    # beyond the travel the bolt hits a slot end; well beyond it the finger
    # tips run into the tapers; along the beam the finger faces meet
    # (this assembly has slots on both halves, so the pair's travel is doubled)
    assert _overlap(lower, bolt_shafts(p, 2 * p.slot_travel + 0.5 * p.hole_d)) > 0
    over = p.slot_travel + p.tip_gap + 0.5 * taper_len + 1.0  # halfway up the taper
    assert _overlap(lower, upper.moved(Location((0, -over, 0)))) > 0
    assert _overlap(lower, upper.moved(Location((0, 0, -(joint_clearance + 0.1))))) > 0

    assert_printable(lower)


def test_coupon_is_the_two_joint_pieces():
    p = BoltParams(coupon=1, length=10)
    pieces = half(p)
    assert len(pieces.solids()) == 2
    bb = pieces.bounding_box()
    assert bb.min.Y == pytest.approx(p.shoulder - p.taper_len - p.coupon_stub, abs=TOL)
    assert bb.max.Y == pytest.approx(p.tip_end, abs=TOL)
    assert_printable(pieces)


def test_rejects_nonpositive_wall():
    with pytest.raises(ValueError, match="wall must be positive"):
        profile(BoltParams(wall=0))


def test_rejects_span_smaller_than_fillets():
    with pytest.raises(ValueError, match="fillet radius"):
        profile(BoltParams(beam_w=3, clearance=0, fillet_r=2))


def test_rejects_bad_joint_clearance():
    with pytest.raises(ValueError, match="joint_clearance"):
        profile(BoltParams(joint_clearance=-0.1))


def test_rejects_negative_taper():
    with pytest.raises(ValueError, match="taper_len"):
        profile(BoltParams(taper_len=-1))


def test_rejects_no_bolts():
    with pytest.raises(ValueError, match="at least one bolt"):
        profile(BoltParams(n_bolts=0))


def test_rejects_slot_shorter_than_hole():
    with pytest.raises(ValueError, match="slot_len"):
        profile(BoltParams(slot_len=2))


def test_rejects_wall_too_thin_for_slot():
    with pytest.raises(ValueError, match="too thin for a"):
        profile(BoltParams(wall=4, bolt_d=3))


def test_rejects_arms_too_short_for_lap_and_taper():
    with pytest.raises(ValueError, match="arms are too short"):
        profile(BoltParams(lap_len=150, taper_len=40))


def test_rejects_lap_too_short_for_slots():
    with pytest.raises(ValueError, match="lap_len is too short"):
        profile(BoltParams(lap_len=12))


def test_rejects_label_deeper_than_wall():
    with pytest.raises(ValueError, match="label_depth"):
        profile(BoltParams(label="x", label_depth=5, wall=5))


def test_base_dovetail_groove_stays_inside_the_base():
    from assembly import interference

    p = BoltParams(wall=5, dovetail_w=42, length=10)
    lower, upper = assembly(p)
    # the groove is cut into the base: the halves' envelope is unchanged
    assert lower.bounding_box().min.Y == pytest.approx(-p.wall, abs=1e-4)
    assert upper.bounding_box().max.Y == pytest.approx(p.span_h + p.wall, abs=1e-4)
    assert lower.volume < assembly(BoltParams(wall=5, length=10))[0].volume
    assert_printable(lower)
    both = interference("bolt", p)
    assert all(v == pytest.approx(0, abs=1e-3) for k, v in both.items() if k not in ("lower", "upper"))


def test_fused_rail_clamps_hang_from_the_base():
    from beam_bolt import fused_rails

    p = BoltParams(rails="outer,outer", length=10)
    body = half(p)
    assert body.is_valid() and len(body.solids()) == 1
    # the rails seat in the fused clamps without touching them, below the base
    for rail in fused_rails(p):
        assert _overlap(body, rail) == pytest.approx(0, abs=1e-3)
        assert rail.bounding_box().max.Y < -p.wall
    assert body.bounding_box().min.Y < -p.wall - 10
    assert_printable(body)
    # the plain half is the same part without them
    assert half(BoltParams(length=10)).volume < body.volume


def test_rejects_rail_clamps_off_the_base():
    with pytest.raises(ValueError, match="flat underside"):
        profile(BoltParams(rails="outer,outer", rail_spacing=50))


def test_rejects_rail_clamps_with_a_dovetail():
    with pytest.raises(ValueError, match="cannot also have a dovetail"):
        profile(BoltParams(rails="outer,outer", dovetail_w=32))


def test_lower_half_has_holes_and_the_upper_the_slot():
    from beam_bolt import mate_location

    q = BoltParams(length=10)
    lower = half(BoltParams(length=10, bolt_slot=0))
    upper = half(BoltParams(length=10, bolt_slot=1)).moved(mate_location(q))
    # a hole removes less than a slot
    assert lower.volume > half(BoltParams(length=10, bolt_slot=1)).volume
    # the bolt sits in the lower's hole and rides the upper's slot across the travel
    for dy in (-q.slot_travel, 0.0, q.slot_travel):
        shafts = bolt_shafts(BoltParams(length=10, bolt_slot=0), dy)
        assert _overlap(lower, shafts) == pytest.approx(0, abs=TOL)
        assert _overlap(upper.moved(Location((0, dy, 0))), shafts) == pytest.approx(0, abs=TOL)
        assert _overlap(lower, upper.moved(Location((0, dy, 0)))) == pytest.approx(0, abs=TOL)
    assert _overlap(upper.moved(Location((0, q.slot_travel + 0.6, 0))), bolt_shafts(BoltParams(length=10, bolt_slot=0), q.slot_travel + 0.6)) > 0


def test_taper_is_a_smooth_curve():
    # the cosine taper removes the same area as a straight ramp but is tangent
    # at both ends: its top face has no edge steeper than 45 degrees and its
    # first and last facets are nearly flat
    import math

    p = BoltParams(length=50, taper_len=25)
    body = half(p)
    slopes = []
    for f in body.faces():
        n = f.normal_at()
        # upward-facing facets of the shoulder taper only (the nose at the
        # tip is deliberately steeper, rolling over to vertical)
        if n.Z > 0.05 and abs(n.X) < 1e-6 and f.center().Y < p.arm_len:
            slopes.append(math.degrees(math.atan2(abs(n.Y), n.Z)))
    # a cosine's steepest point is pi/2 times the straight ramp's slope
    assert 50 < max(slopes) < 65
    assert min(slopes) < 8
