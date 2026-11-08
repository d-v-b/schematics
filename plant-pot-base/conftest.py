"""Shared test helpers."""

import math


def assert_printable(part, max_overhang_deg: float = 45.0, min_area: float = 1.0) -> None:
    """The part prints with its profile on the bed (z up): no downward-facing
    face steeper than max_overhang_deg from vertical may exist above the bed.
    Tiny faces (engraved lettering) are ignored."""
    # a face at exactly the limit is allowed (hence the epsilon)
    limit = -math.sin(math.radians(90 - max_overhang_deg)) - 1e-6
    bad = []
    for f in part.faces():
        if f.area < min_area or f.center().Z < 0.01:
            continue
        n = f.normal_at()
        if n.Z < limit:
            bad.append((round(f.center().X, 1), round(f.center().Y, 1), round(f.center().Z, 1), round(f.area, 1)))
    assert not bad, f"unsupported downward faces (x, y, z, area): {bad}"


def volume(part, eps: float = 1e-6) -> float:
    """The part's volume, integrated to a relative error of eps. The
    default integration is off by several parts per thousand on the
    rippled floor's B-spline."""
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(part.wrapped, props, eps)
    return props.Mass()
