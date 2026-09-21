"""A right-angle corner bracket for two M8 bolts, one through each leg, with a
reinforcing rib in the inside corner along one edge.

In profile the bracket is the L's centreline dilated by half the
``thickness``: each leg is a stadium ``thickness`` thick, so the leg ends and
the outer corner are rounded and nothing is left sharp to snag. The legs
reach ``leg`` from the outer faces. The inside corner, where a bracket
cracks, is filleted to ``fillet_r``. A 45 degree gusset fills the inside
corner out to ``rib_l`` along each leg, but only for ``rib_t`` of the
bracket's ``width``, so it braces the corner along one edge and leaves the
rest of each leg's inside face clear for a bolt head and washer.

Each leg has one ``hole_d`` hole square to it, centred on the width and
``hole_at`` out from the outer corner: midway along the leg's free length
unless ``hole_x`` sets it. The bolt heads sit on the legs' inside faces, so
a ``washer_d`` washer must clear the other leg, the leg's end and the rib.

The L lies in the XY plane with its outer corner on the origin, one leg along
X and the other along Y, and is extruded ``width`` up Z. Print it on its
side, as drawn: every layer runs round the whole corner, so the bend is not
a stack of layer seams, and the gusset is the first ``rib_t`` of the print.
The two holes then run horizontally and print as short round bridges.

Usage:
    python bracket.py -o bracket.stl [--leg 40] [--thickness 6] [--width 30] ...
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, fields
from pathlib import Path

from build123d import (
    Compound,
    Cylinder,
    FontStyle,
    Location,
    Part,
    Plane,
    Polygon,
    Rotation,
    Sketch,
    SlotCenterToCenter,
    Text,
    export_stl,
    extrude,
)


@dataclass(frozen=True)
class BracketParams:
    """Every dimension of the bracket, in millimetres."""

    # Each leg's reach from the outer face of the other.
    leg: float = 40.0
    thickness: float = 6.0
    # Along the corner: the print's height.
    width: float = 30.0
    # Radius in the inside corner.
    fillet_r: float = 3.0
    # The gusset: how far it runs along each leg's inside face from the
    # corner, and how much of the width it fills, from z = 0.
    rib_l: float = 25.0
    rib_t: float = 5.0
    # M8 clearance is 8.4 (ISO 273 fine); 0.2 more lets a printed hole,
    # which comes out narrow, pass the bolt.
    hole_d: float = 8.6
    # Distance of each hole's centre from the outer corner. 0 = midway along
    # the leg's free length, from the other leg's inside face to its end.
    hole_x: float = 0.0
    # What has to sit flat round each hole on the leg's inside face: an M8
    # washer (ISO 7089) is 16 across.
    washer_d: float = 16.0
    # ID engraved into the print's top face, along the leg on X. Empty
    # disables.
    label: str = ""
    label_depth: float = 0.4
    label_size: float = 3.0

    # ----- derived -----
    @property
    def hole_at(self) -> float:
        """Each hole's centre, out from the outer corner."""
        if self.hole_x > 0:
            return self.hole_x
        return self.thickness + (self.leg - self.thickness) / 2

    def validate(self) -> None:
        if min(self.leg, self.thickness, self.width, self.hole_d, self.washer_d, self.rib_l, self.rib_t) <= 0:
            raise ValueError("leg, thickness, width, hole_d, washer_d, rib_l and rib_t must be positive")
        if self.fillet_r < 0:
            raise ValueError("fillet_r must not be negative")
        if self.leg <= 2 * self.thickness:
            raise ValueError("leg must be longer than twice the thickness")
        if self.hole_d >= self.width:
            raise ValueError("hole_d must be less than width")
        if self.rib_t >= self.width:
            raise ValueError("rib_t must be less than width")
        if self.thickness + self.rib_l > self.leg - self.thickness / 2:
            raise ValueError("rib_l must end before the leg's rounded end")
        if self.fillet_r >= self.rib_l:
            raise ValueError("fillet_r must be less than rib_l, so the gusset covers the fillet")
        w = self.washer_d / 2
        if self.hole_at - w < self.thickness:
            raise ValueError("the washer would foul the other leg: move the hole out or use a smaller washer")
        if self.hole_at + w > self.leg:
            raise ValueError("the washer would overhang the end of the leg: move the hole in or lengthen the leg")
        if self.width / 2 - w < self.rib_t:
            raise ValueError("the washer would foul the rib: widen the bracket or thin the rib")
        if self.label and self.label_depth >= self.width:
            raise ValueError("label_depth must be less than width")

    def report(self) -> str:
        return (
            f"{self.leg:g} x {self.leg:g} x {self.width:g} bracket, {self.thickness:g} thick, "
            f"{self.hole_d:g} holes {self.hole_at:g} from the corner, "
            f"rib {self.rib_l:g} along each leg x {self.rib_t:g}"
        )


def profile(p: BracketParams) -> Sketch:
    """The L in profile: two stadiums thickness thick meeting at the corner
    (the centreline dilated by thickness / 2), the inside corner filleted."""
    p.validate()
    t, span = p.thickness, p.leg - p.thickness
    along_x = SlotCenterToCenter(span, t).moved(Location((p.leg / 2, t / 2)))
    along_y = SlotCenterToCenter(span, t).moved(Location((t / 2, p.leg / 2), 90))
    face = (along_x + along_y).faces()[0]
    if p.fillet_r > 0:
        corner = min(face.vertices(), key=lambda v: math.hypot(v.X - t, v.Y - t))
        face = face.fillet_2d(p.fillet_r, [corner])
    return Sketch([face])


def gusset(p: BracketParams) -> Sketch:
    """The rib in profile: a right triangle in the inside corner."""
    t = p.thickness
    return Sketch(list(Polygon((t, t), (t + p.rib_l, t), (t, t + p.rib_l), align=None).faces()))


def _holes(p: BracketParams) -> Part:
    t, z, h = p.thickness, p.width / 2, p.thickness + 2
    r = p.hole_d / 2
    through_x_leg = Cylinder(r, h).moved(Location((p.hole_at, t / 2, z)) * Rotation(90, 0, 0))
    through_y_leg = Cylinder(r, h).moved(Location((t / 2, p.hole_at, z)) * Rotation(0, 90, 0))
    return through_x_leg + through_y_leg


def _label_cut(p: BracketParams) -> Part | None:
    if not p.label:
        return None
    t = p.thickness
    x_mid = (p.leg - t / 2 + t) / 2  # along the leg on X, clear of the corner
    size = min(p.label_size, t - 1.0)
    plane = Plane(origin=(x_mid, t / 2, p.width), x_dir=(1, 0, 0), z_dir=(0, 0, 1))
    return extrude(plane * Text(p.label, font_size=size, font_style=FontStyle.BOLD), amount=-p.label_depth)


def bracket(p: BracketParams) -> Part:
    body = extrude(profile(p), amount=p.width) + extrude(gusset(p), amount=p.rib_t)
    body = body - _holes(p)
    cut = _label_cut(p)
    if cut is not None:
        body = body - cut
    return body


def _iso_svg(p: BracketParams, out: Path) -> None:
    """The part seen from outside the corner and above, hidden edges dashed."""
    from build123d import ExportSVG, LineType

    visible, hidden = bracket(p).project_to_viewport((110, 70, 90), viewport_up=(0, 0, 1))
    span = Compound(visible).bounding_box().size
    svg = ExportSVG(scale=120 / max(span.X, span.Y), margin=5, line_weight=0.4)
    svg.add_layer("hidden", line_color=(160, 160, 160), line_type=LineType.ISO_DASH, line_weight=0.2)
    svg.add_shape(visible)
    svg.add_shape(hidden, layer="hidden")
    svg.write(str(out))


def _cli() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, required=True, help=".stl, .step or .svg path")
    ap.add_argument("--iso", action="store_true", help="draw an .svg as an isometric view of the part, not its profile")
    for f in fields(BracketParams):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _cli().parse_args(argv)
    p = BracketParams(**{f.name: getattr(args, f.name) for f in fields(BracketParams)})
    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".svg" and args.iso:
        _iso_svg(p, out)
    elif out.suffix == ".svg":
        from build123d import ExportSVG

        svg = ExportSVG(scale=4, margin=10, line_weight=0.4)
        svg.add_shape(profile(p))
        svg.add_shape(gusset(p))
        svg.write(str(out))
    elif out.suffix == ".step":
        from build123d import export_step

        export_step(bracket(p), str(out))
    else:
        export_stl(bracket(p), str(out), tolerance=0.01, angular_tolerance=0.1)
    print(f"-> {out}")
    print(p.report())


if __name__ == "__main__":
    main()
