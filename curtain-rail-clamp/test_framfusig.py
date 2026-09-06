"""The rail sections match the measured dimensions."""

import pytest

from framfusig import INNER, OUTER, PROFILES

TOL = 1e-4


@pytest.mark.parametrize("profile", list(PROFILES.values()))
def test_section_matches_measurements(profile):
    bb = profile.section().bounding_box()
    assert bb.size.X == pytest.approx(profile.width, abs=TOL)
    assert bb.size.Y == pytest.approx(profile.height, abs=TOL)
    # the slot removes exactly slot_w x wall from the underside
    assert profile.envelope().area - profile.section().area == pytest.approx(profile.slot_w * profile.wall, rel=1e-3)
    # a full stadium when the radius reaches half the height
    assert profile.radius <= profile.height / 2


def test_inner_fits_inside_outer():
    assert INNER.width < OUTER.width and INNER.height < OUTER.height
