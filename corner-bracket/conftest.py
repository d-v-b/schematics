"""Shared test helpers."""

import math


def assert_printable(part, max_overhang_deg: float = 45.0, min_area: float = 1.0, ignore=None) -> None:
    """The part prints with its profile on the bed (z up): no downward-facing
    face steeper than max_overhang_deg from vertical may exist above the bed.
    Tiny faces (engraved lettering) are ignored, as is any face for which
    ignore(face) is true."""
    # a face at exactly the limit is allowed (hence the epsilon)
    limit = -math.sin(math.radians(90 - max_overhang_deg)) - 1e-6
    bad = []
    for f in part.faces():
        if f.area < min_area or f.center().Z < 0.01:
            continue
        if ignore is not None and ignore(f):
            continue
        # a curved face can face down in places only (a horizontal bore's
        # roof is a narrow band of it), so test it on a dense grid
        grid = [i / 24 for i in range(25)]
        normals = [f.normal_at(u, v) for u in grid for v in (0.0, 0.5, 1.0)]
        if min(n.Z for n in normals) < limit:
            bad.append((round(f.center().X, 1), round(f.center().Y, 1), round(f.center().Z, 1), round(f.area, 1)))
    assert not bad, f"unsupported downward faces (x, y, z, area): {bad}"
