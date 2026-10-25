"""A round base for a plant pot: a floor and a low wall, whose top edge rises
and falls in a gentle wave round the rim.

The pot is ``pot_d`` across at its foot. Its sides slope outward, which is
not modeled: the pocket is just made ``slack`` wider than the foot, so the
pot drops in without catching on the wall, whatever the slope.

The wall's top edge is a raised cosine of ``lobes`` periods round the rim:

    z(theta) = trough_h + (peak_h - trough_h) * (1 + cos(lobes * theta)) / 2

so it peaks at ``peak_h`` and dips to ``trough_h``, both measured from the
bed. The wall is lofted through its cross-section stood up in radial planes
round the rim, each one cut off at the crest's height there, one half-lobe
at a time. In every one
the crest is level across the wall with both corners rounded to
``crest_r``, so the rounding stays the same however steep the wave gets,
and the outer corner on the bed is chamfered by ``foot_chamfer`` so the
first layer's squash does not leave a lip.

The base sits on z = 0, centered on the axis, and prints the way it is
modeled: floor on the bed, wall straight up. The crest only ever faces up,
so nothing overhangs and nothing needs support.

Usage:
    python base.py -o base.stl [--pot_d 70] [--slack 5] [--peak_h 10] [--lobes 6]
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, fields
from pathlib import Path

from build123d import (
    Line,
    Part,
    Plane,
    RadiusArc,
    Rot,
    Solid,
    Wire,
    export_stl,
)

# The printer's bed, mm. The base's footprint must fit on it.
BED = 256.0
# Cross-sections each half-lobe of the wall is lofted through.
SECTIONS_PER_HALF_LOBE = 12


@dataclass(frozen=True)
class BaseParams:
    """Every dimension of the base, in millimeters."""

    # The pot's diameter at its foot.
    pot_d: float = 70.0
    # How much wider the pocket is than the pot's foot, across the diameter.
    # Covers the pot's slope, which is not modeled.
    slack: float = 5.0
    wall: float = 2.4
    floor: float = 2.0
    # The wave on the wall's top edge, measured from the bed.
    peak_h: float = 10.0
    trough_h: float = 6.0
    lobes: int = 6
    # Radius the crest's inner and outer edges are rounded to.
    crest_r: float = 1.0
    # Chamfer on the outer edge of the floor, against elephant's foot.
    foot_chamfer: float = 0.5

    # ----- derived -----
    @property
    def pocket_d(self) -> float:
        """The clear diameter inside the wall."""
        return self.pot_d + self.slack

    @property
    def outer_d(self) -> float:
        """The base's footprint."""
        return self.pocket_d + 2 * self.wall

    @property
    def swing(self) -> float:
        """How far the crest rises from trough to peak."""
        return self.peak_h - self.trough_h

    @property
    def wavelength(self) -> float:
        """One lobe, measured round the outside of the wall."""
        return math.pi * self.outer_d / self.lobes

    def crest_z(self, theta: float) -> float:
        """Height of the wall's top edge at angle theta round the rim."""
        return self.trough_h + self.swing * (1 + math.cos(self.lobes * theta)) / 2

    def validate(self) -> None:
        if self.pot_d <= 0 or self.wall <= 0 or self.floor <= 0:
            raise ValueError("pot_d, wall and floor must be positive")
        if self.slack < 0:
            raise ValueError("slack must not be negative")
        if self.lobes < 1:
            raise ValueError("lobes must be at least 1")
        if self.peak_h < self.trough_h:
            raise ValueError("peak_h must not be below trough_h")
        if self.trough_h - self.floor < 2 * self.crest_r:
            raise ValueError(
                f"the wall stands only {self.trough_h - self.floor:g} above the floor at its "
                f"troughs, under the {2 * self.crest_r:g} the crest rounding needs: "
                "raise trough_h or shrink crest_r"
            )
        if not 0 <= self.crest_r < self.wall / 2:
            raise ValueError("crest_r must be at least 0 and under half the wall")
        if not 0 <= self.foot_chamfer < min(self.wall, self.floor):
            raise ValueError("foot_chamfer must be at least 0 and under the wall and the floor")
        if self.outer_d > BED:
            raise ValueError(f"the base is {self.outer_d:g} across, over the {BED:g} bed")

    def report(self) -> str:
        return (
            f"base for a {self.pot_d:g} pot: {self.pocket_d:g} pocket, {self.outer_d:g} across, "
            f"{self.floor:g} floor, {self.wall:g} wall waving {self.trough_h:g}-{self.peak_h:g} "
            f"high over {self.lobes} lobes of {self.wavelength:.1f}"
        )


def _section(p: BaseParams, theta: float) -> Wire:
    """The wall's cross-section at angle theta round the rim, stood up in the
    radial plane there: bed to crest, pocket to outside, with the crest
    corners rounded and the outer foot chamfered."""
    r_in, r_out = p.pocket_d / 2, p.outer_d / 2
    z, r, c = p.crest_z(theta), p.crest_r, p.foot_chamfer
    pts = [(r_in, 0), (r_out - c, 0), (r_out, c), (r_out, z - r), (r_out - r, z),
           (r_in + r, z), (r_in, z - r)]
    # drop the zero-length sides left by a zero chamfer or rounding
    pts = [q for i, q in enumerate(pts) if q != pts[i - 1]]
    edges = []
    for a, b in zip(pts, pts[1:] + pts[:1]):
        # the two sides that cross the crest's corners are arcs
        corner = r > 0 and {a[1], b[1]} == {z, z - r} and a[0] != b[0]
        edges.append(RadiusArc(a, b, -r) if corner else Line(a, b))
    # x radial, y up
    plane = Plane(origin=(0, 0, 0), x_dir=(math.cos(theta), math.sin(theta), 0),
                  z_dir=(math.sin(theta), -math.cos(theta), 0))
    return plane.from_local_coords(Wire(edges))


def _wall(p: BaseParams) -> list[Solid]:
    """The wall, as 2 * lobes congruent pieces. Each lofts one half-lobe,
    peak to trough; both ends lie on planes of symmetry of the wave, where
    the crest is level, so the pieces meet with no visible crease. One loft round
    the whole rim would be smoother still on paper, but OCCT's booleans
    give wrong volumes on a loft through that many sections."""
    half = math.pi / p.lobes
    piece = Solid.make_loft([_section(p, half * i / SECTIONS_PER_HALF_LOBE)
                             for i in range(SECTIONS_PER_HALF_LOBE + 1)])
    mirrored = piece.mirror(Plane.XZ)
    turns = [Rot(0, 0, math.degrees(2 * half * j)) for j in range(p.lobes)]
    return [t * q for t in turns for q in (piece, mirrored)]


def base(p: BaseParams) -> Part:
    p.validate()
    # the floor runs halfway into the wall, so its rim fuses inside solid
    # material rather than along the wall's inner face
    floor = Solid.make_cylinder(p.pocket_d / 2 + p.wall / 2, p.floor)
    return Part([floor.fuse(*_wall(p)).clean().solids()[0]])


def _svg(p: BaseParams, out: Path) -> None:
    """A three-quarter view of the base, hidden edges dashed."""
    from build123d import ExportSVG, LineType

    visible, hidden = base(p).project_to_viewport((-160, -220, 120), viewport_up=(0, 0, 1))
    svg = ExportSVG(scale=2, margin=6, line_weight=0.3)
    svg.add_layer("hidden", line_color=(160, 160, 160), line_type=LineType.ISO_DASH, line_weight=0.15)
    svg.add_shape(hidden, layer="hidden")
    svg.add_shape(visible)
    svg.write(str(out))


def _cli() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, required=True, help=".stl, .step or .svg path")
    for f in fields(BaseParams):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _cli().parse_args(argv)
    p = BaseParams(**{f.name: getattr(args, f.name) for f in fields(BaseParams)})
    p.validate()
    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".svg":
        _svg(p, out)
    elif out.suffix == ".step":
        from build123d import export_step

        export_step(base(p), str(out))
    else:
        export_stl(base(p), str(out), tolerance=0.01, angular_tolerance=0.1)
    print(f"-> {out}")
    print(p.report())


if __name__ == "__main__":
    main()
