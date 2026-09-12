"""The beam fits inside each assembled model.

The beam is seated on the lower fillets. The only material allowed to cross
into the beam is the tension bumps of the friction-fit models, by exactly
their protrusion; the bolted model must not touch the beam at all.
"""

import pytest

import beam_bolt
import beam_clamp
import beam_flex
import beam_wrap
from assembly import beam, interference

TOL = 1e-3


def _bump_volume(p) -> float:
    """Volume of the profile that lies inside the beam's footprint: with the
    beam centred and seated, that is the tips of the bumps only."""
    from build123d import Align, Location, Rectangle

    from beam_clamp import _sk

    prof = beam_clamp.profile(p) if isinstance(p, beam_clamp.ClampParams) else beam_wrap.profile(p)
    footprint = Rectangle(p.beam_w, getattr(p, "beam_h", 206.5), align=(Align.MIN, Align.MIN)).moved(
        Location((p.clearance / 2, p.seat))
    )
    inside = prof & footprint
    faces = list(inside.faces()) if hasattr(inside, "faces") else [f for s in inside for f in s.faces()]
    return sum(f.area for f in faces) * p.length


@pytest.mark.parametrize("clearance", [0.0, 0.3, 0.6])
def test_clamp_only_bumps_touch_the_beam(clearance):
    p = beam_clamp.ClampParams(clearance=clearance, length=10)
    assert interference("clamp", p)["clamp"] == pytest.approx(_bump_volume(p), abs=TOL)


@pytest.mark.parametrize("clearance", [0.0, 0.3, 0.6])
def test_wrap_only_bumps_touch_the_beam(clearance):
    p = beam_wrap.WrapParams(clearance=clearance, length=10)
    both = interference("wrap", p)
    assert both["lower"] == pytest.approx(_bump_volume(p), abs=TOL)
    assert both["upper"] == pytest.approx(_bump_volume(p), abs=TOL)


@pytest.mark.parametrize("clearance", [0.0, 0.3, 0.6])
def test_bolt_wrap_clears_the_beam(clearance):
    p = beam_bolt.BoltParams(clearance=clearance)
    both = interference("bolt", p)
    assert both["lower"] == pytest.approx(0, abs=TOL)
    assert both["upper"] == pytest.approx(0, abs=TOL)
    assert both["bolts"] == pytest.approx(0, abs=TOL)


@pytest.mark.parametrize("clearance", [0.0, 0.3, 0.6])
def test_flex_wrap_clears_the_beam(clearance):
    p = beam_flex.FlexParams(clearance=clearance, length=10)
    both = interference("flex", p)
    assert both["lower"] == pytest.approx(0, abs=TOL)
    assert both["upper"] == pytest.approx(0, abs=TOL)


def test_beam_is_seated_between_the_bases():
    p = beam_bolt.BoltParams()
    bb = beam(p).bounding_box()
    assert bb.min.Y == pytest.approx(p.seat, abs=TOL)
    assert bb.max.Y == pytest.approx(p.span_h - p.seat, abs=TOL)
    assert p.seat > 0


def test_hanger_stacks_without_interference():
    """Beam, beam clamp halves, rail clamp on the dovetail, rails in the clamp."""
    from assembly import bodies

    p = beam_bolt.BoltParams(rails="outer,outer", length=30)
    both = interference("hanger", p)
    for name in ("lower", "upper", "bolts", "rails", "bolts/lower", "bolts/upper", "rails/lower", "lower/upper"):
        assert both[name] == pytest.approx(0, abs=TOL), name
    # and the rails hang below the beam, inside the fused clamps
    d = dict(bodies("hanger", p))
    assert d["rails"].bounding_box().max.Y < 0
    assert d["lower"].bounding_box().min.Y < d["rails"].bounding_box().min.Y
