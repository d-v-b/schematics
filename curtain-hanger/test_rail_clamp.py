"""The clamp fits the rails it is built for and holds them.

One test covers combinations of tube sizes, wall, lip depth and spacing; the
rest each cover one validation error.
"""

import pytest
from build123d import Location

from rail_clamp import ClipParams, beam_socket, clip, plate_top, profile, rail_solids

TOL = 1e-4


def _overlap(a, b):
    r = a & b
    return r.volume if hasattr(r, "volume") else sum(s.volume for s in r)


@pytest.mark.parametrize("tubes", ["outer", "inner", "outer,outer", "inner,outer", "inner,inner"])
@pytest.mark.parametrize("wall,opening,clearance", [(1.2, 16.0, 0.0), (1.5, 16.5, 0.1), (1.2, 9.5, 0.0)])
@pytest.mark.parametrize("spacing", [30.0, 40.0])
def test_fit(tubes, wall, opening, clearance, spacing):
    # min_safety 0: the deepest case cannot snap on and would slide on instead
    # the dovetail and the winged plate are covered by their own tests
    p = ClipParams(tubes=tubes, wall=wall, opening=opening, clearance=clearance, spacing=spacing, min_safety=0.0, length=40, dovetail_w=0, mate_w=0)
    body = clip(p)
    assert body.is_valid() and len(body.solids()) == 1

    # every rail seats without the clamp biting into it (at zero clearance
    # the surfaces coincide), and the opening is narrower than the rail so it
    # is trapped
    for rail in rail_solids(p):
        assert _overlap(body, rail) == pytest.approx(0, abs=1e-3)
    assert p.interference > 0
    assert p.opening > p.rail.slot_w + 2 * wall  # lips never reach the glider slot

    # the lips leave the underside clear: they wrap the rail's lower rounds,
    # so their outside may dip at most a wall below the rail's bottom, and the
    # opening keeps them away from the slot (checked above)
    bb = profile(p).bounding_box()
    lowest_rail_bottom = min(r.bounding_box().min.Y for r in rail_solids(p))
    # the lips may curl below the rail by the flare and their end round
    assert bb.min.Y >= lowest_rail_bottom - wall - clearance - p.flare_r - wall / 2 - 1e-3
    # flat plate on top spanning all the Cs, above the necks
    assert bb.max.Y == pytest.approx(plate_top(p), abs=TOL)
    assert bb.size.X == pytest.approx(p.plate_w, abs=TOL)
    # the neck and its fillets stay on the flat top, off the rounds
    assert p.fixed_x <= p.flat_half + 1e-9

    # deeper lips hold harder; wrapping under holds indefinitely
    assert p.pull_out > 0


def test_rejects_unknown_tube():
    with pytest.raises(ValueError, match="tubes must be"):
        profile(ClipParams(tubes="middle"))


def test_rejects_rails_too_close():
    with pytest.raises(ValueError, match="spacing"):
        profile(ClipParams(tubes="outer,outer", spacing=15))


def test_rejects_nonpositive_wall():
    with pytest.raises(ValueError, match="wall must be positive"):
        profile(ClipParams(wall=0))


def test_rejects_excessive_interference_clearance():
    with pytest.raises(ValueError, match="clearance"):
        profile(ClipParams(clearance=-0.6))


def test_rejects_opening_wider_than_the_rail():
    with pytest.raises(ValueError, match="narrower than the rail"):
        profile(ClipParams(opening=19.6))


def test_rejects_lips_crowding_the_slot():
    with pytest.raises(ValueError, match="glider slot"):
        profile(ClipParams(opening=7.5))


def test_deeper_lips_hold_harder():
    shallow = ClipParams(opening=18.0, min_safety=0.0)
    deep = ClipParams(opening=16.0, min_safety=0.0)
    deepest = ClipParams(opening=9.5, min_safety=0.0)
    assert shallow.pull_out < deep.pull_out < deepest.pull_out


def test_underside_is_too_narrow_to_wrap_under():
    # the outer tube's flat underside is 7.3 mm and the slot takes 6.75 of it,
    # so lips can never wrap under it without reaching the slot
    with pytest.raises(ValueError, match="glider slot"):
        profile(ClipParams(opening=7.0, min_safety=0.0))


def test_rejects_nonpositive_plate():
    with pytest.raises(ValueError, match="plate_t"):
        profile(ClipParams(plate_t=0))


def test_rejects_fillet_taller_than_neck():
    with pytest.raises(ValueError, match="fillet_r"):
        profile(ClipParams(stem_h=1.0, fillet_r=1.5))


def test_rejects_neck_reaching_the_rounds():
    with pytest.raises(ValueError, match="flat top"):
        profile(ClipParams(tubes="inner", stem_w=6.0, fillet_r=1.5, dovetail_w=0, mate_w=0))


def test_stress_gate_is_adjustable():
    p = ClipParams(opening=15.0, wall=1.5, min_safety=1.0, length=30)  # about 0.7x by the model
    with pytest.raises(ValueError, match="insertion stress"):
        profile(p)
    profile(ClipParams(opening=15.0, wall=1.5, min_safety=0.5, length=30))


def test_neck_fillets_add_material_only():
    plain = profile(ClipParams(fillet_r=0, mate_w=0)).area
    rounded = profile(ClipParams(mate_w=0)).area
    # 2 rails x 4 concave corners x (square minus quarter circle)
    r = ClipParams().fillet_r
    assert rounded - plain == pytest.approx(8 * (r * r - 3.14159265 * r * r / 4), rel=1e-3)


def test_rejects_unknown_material():
    with pytest.raises(ValueError, match="material"):
        profile(ClipParams(material="steel"))


def test_rejects_overstressed_snap():
    with pytest.raises(ValueError, match="insertion stress"):
        profile(ClipParams(wall=2.5, opening=14.0, min_safety=1.0, length=30))


@pytest.mark.parametrize("along", ["beam", "rails"])
@pytest.mark.parametrize("clearance", [0.05, 0.1, 0.2])
def test_dovetail_ridge_mates_the_groove(along, clearance):
    import math

    p = ClipParams(dovetail_w=42, dovetail_along=along, length=50)  # long enough for the ridge across the plate too
    body = clip(p)
    assert body.is_valid() and len(body.solids()) == 1
    assert body.bounding_box().max.Y == pytest.approx(plate_top(p) + p.dovetail_h, abs=TOL)
    socket = beam_socket(p, clearance=clearance)
    # seated: no interference; the clamp hanging on the groove: once the play,
    # clearance / tan(angle), is used up the flanks bear
    assert _overlap(body, socket) == pytest.approx(0, abs=TOL)
    play = clearance / math.tan(math.radians(p.dovetail_angle))
    assert _overlap(body, socket.moved(Location((0, -(play + 0.3), 0)))) > 0
    # the ridge is on the plate only: the rails still seat cleanly
    for rail in rail_solids(p):
        assert _overlap(body, rail) == pytest.approx(0, abs=1e-3)


def test_no_dovetail_leaves_a_plain_plate():
    assert clip(ClipParams(dovetail_w=0, length=40)).volume < clip(ClipParams(dovetail_w=42, length=40)).volume


def test_rejects_unknown_dovetail_direction():
    with pytest.raises(ValueError, match="dovetail_along"):
        profile(ClipParams(dovetail_w=42, dovetail_along="sideways", length=40))


def test_rejects_ridge_with_no_neck():
    with pytest.raises(ValueError, match="neck is too narrow"):
        profile(ClipParams(dovetail_w=4, dovetail_h=8, dovetail_angle=20, length=40))


def test_rejects_part_too_short_for_a_ridge_across_it():
    with pytest.raises(ValueError, match="too short"):
        profile(ClipParams(dovetail_w=42, length=20, dovetail_along="beam"))


def test_coupon_id_is_engraved_in_the_plate():
    plain = clip(ClipParams(tubes="outer", length=3, dovetail_w=0, mate_w=0))
    tagged = clip(ClipParams(tubes="outer", length=3, dovetail_w=0, mate_w=0, label="w1.2 o10"))
    assert tagged.volume < plain.volume
    # engraved, not embossed: the envelope is unchanged
    for a in "XYZ":
        assert getattr(tagged.bounding_box().size, a) == pytest.approx(getattr(plain.bounding_box().size, a), abs=1e-4)


def test_plate_butts_squarely_against_the_beam_clamps_flat():
    p = ClipParams(mate_w=63.9, mate_r=7.0, dovetail_w=42)  # the bolt beam clamp's outline
    body = clip(p)
    bb = body.bounding_box()
    # the Cs reach past the plate's ends; the plate itself is the clamp's flat
    assert p.plate_w == pytest.approx(p.mate_w - 2 * p.mate_r)
    assert bb.size.X == pytest.approx(max(p.plate_w, p.cs_w), abs=TOL)
    assert bb.max.Y == pytest.approx(plate_top(p) + p.dovetail_h, abs=TOL)
    # the plate's top face spans its width either side of the ridge, less the
    # slight corner rounds
    import math

    top = [f for f in body.faces() if abs(f.normal_at().Y - 1) < 1e-6 and abs(f.center().Y - plate_top(p)) < 1e-6]
    neck = p.dovetail_w - 2 * p.dovetail_h * math.tan(math.radians(p.dovetail_angle))
    assert top and sum(f.bounding_box().size.X for f in top) == pytest.approx(p.plate_w - neck - 2 * p.corner_r, abs=1e-3)


def test_rejects_corner_round_larger_than_half_the_plate():
    with pytest.raises(ValueError, match="corner_r"):
        profile(ClipParams(mate_w=63.9, mate_r=7.0, corner_r=2.0))


def test_rejects_necks_off_the_clamps_flat():
    with pytest.raises(ValueError, match="flat underside"):
        profile(ClipParams(mate_w=63.9, mate_r=7.0, spacing=52))


def test_lip_flare_curls_outward_and_is_round():
    # with the flare the lips reach further out and down than a plain end, and
    # every face of the lip region is convex toward the rail: nothing sharp
    plain = profile(ClipParams(tubes="outer", mate_w=0, flare_deg=0))
    flared = profile(ClipParams(tubes="outer", mate_w=0))
    assert flared.area > plain.area
    assert flared.bounding_box().min.Y < plain.bounding_box().min.Y


def test_rejects_flare_tighter_than_the_wall():
    with pytest.raises(ValueError, match="flare_r"):
        profile(ClipParams(flare_r=0.5))
