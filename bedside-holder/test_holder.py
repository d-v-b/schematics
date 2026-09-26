"""The holder's parameters refuse geometry that would not fit, would not
print, or would creep. Each test covers one validation error; the geometry
itself is tested in test_holder."""

import pytest

from holder import HolderParams


def test_non_positive():
    with pytest.raises(ValueError, match="must be positive: t, bend_ri"):
        HolderParams(t=0, bend_ri=-1).validate()


def test_section():
    with pytest.raises(ValueError, match="section must be one of"):
        HolderParams(section="middle").validate()


def test_arc_too_tight():
    with pytest.raises(ValueError, match="radius must exceed t / 2"):
        HolderParams(lip_flare_r=1.4).validate()


def test_label_too_deep():
    with pytest.raises(ValueError, match="label_depth 3 must be less than t 3"):
        HolderParams(label_depth=3.0).validate()


def test_inner_leaf_cannot_lean():
    with pytest.raises(ValueError, match="inner leaf cannot lean in"):
        HolderParams(inner_len=2.0, inner_flare_r=2.0, inner_pre=4.0).validate()


def test_lip_cannot_reach():
    with pytest.raises(ValueError, match="lip reaches the device before it stops leaning"):
        HolderParams(lip_r=200.0, lip_lean=20.0).validate()


def test_mattress_clearance():
    with pytest.raises(ValueError, match="more than the 3 mattress clearance"):
        HolderParams(mattress_clear=3.0).validate()


def test_too_big_for_the_bed():
    with pytest.raises(ValueError, match="over the 250 bed limit"):
        HolderParams(drop=250.0).validate()


def test_inner_leaf_creep():
    with pytest.raises(ValueError, match="inner leaf would sit at"):
        HolderParams(inner_pre=1.5).validate()


def test_lip_creep():
    with pytest.raises(ValueError, match="lip would sit at"):
        HolderParams(lip_base=4.0).validate()
