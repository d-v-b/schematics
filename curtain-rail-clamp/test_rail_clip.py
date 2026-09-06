"""The clamp fits the rails it is built for and holds them.

One test covers combinations of tube sizes, wall, lip depth and spacing; the
rest each cover one validation error.
"""

import pytest

from rail_clip import ClipParams, clip, profile, rail_solids

TOL = 1e-4


def _overlap(a, b):
    r = a & b
    return r.volume if hasattr(r, "volume") else sum(s.volume for s in r)


@pytest.mark.parametrize("tubes", ["outer", "inner", "outer,outer", "inner,outer", "inner,inner"])
@pytest.mark.parametrize("wall,opening,clearance", [(1.2, 16.0, 0.0), (1.5, 16.5, 0.1), (1.2, 9.5, 0.0)])
@pytest.mark.parametrize("spacing", [30.0, 40.0])
def test_fit(tubes, wall, opening, clearance, spacing):
    # min_safety 0: the deepest case cannot snap on and would slide on instead
    p = ClipParams(tubes=tubes, wall=wall, opening=opening, clearance=clearance, spacing=spacing, min_safety=0.0)
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
    assert bb.min.Y >= lowest_rail_bottom - wall - clearance - 1e-3
    # flat plate on top spanning all the Cs, above the necks
    assert bb.max.Y == pytest.approx(p.out_h / 2 + p.stem_h + p.plate_t, abs=TOL)
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


def test_rejects_lips_reaching_the_slot():
    with pytest.raises(ValueError, match="glider slot"):
        profile(ClipParams(opening=9.0))


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
        profile(ClipParams(tubes="inner", stem_w=6.0, fillet_r=1.5))


def test_stress_gate_is_adjustable():
    p = ClipParams(opening=15.0, wall=1.5)  # about 0.7x by the model
    with pytest.raises(ValueError, match="insertion stress"):
        profile(p)
    profile(ClipParams(opening=15.0, wall=1.5, min_safety=0.5))


def test_neck_fillets_add_material_only():
    plain = profile(ClipParams(fillet_r=0)).area
    rounded = profile(ClipParams()).area
    # 2 rails x 4 concave corners x (square minus quarter circle)
    r = 1.5
    assert rounded - plain == pytest.approx(8 * (r * r - 3.14159265 * r * r / 4), rel=1e-3)


def test_rejects_unknown_material():
    with pytest.raises(ValueError, match="material"):
        profile(ClipParams(material="steel"))


def test_rejects_overstressed_snap():
    with pytest.raises(ValueError, match="insertion stress"):
        profile(ClipParams(wall=2.5, opening=14.0))
