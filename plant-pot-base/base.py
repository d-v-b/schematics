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
``crest_r``, so the rounding stays the same however steep the wave gets.
The loft stands on a plain ring, turned about the axis, that runs from the
bed to just above the floor; its outer corner on the bed is chamfered by
``foot_chamfer`` so the first layer's squash does not leave a lip.

The floor's top can be flat, or rippled in two directions so the pot rests
on a grid of rounded peaks and water stands in the dimples between them,
where air reaches it and it dries:

    z(x, y) = floor + ripple_a * (1 + cos(k x) * cos(k y)),  k = 2 pi / ripple_l

so ``floor`` is the thickness under the dimples, the peaks stand
``2 * ripple_a`` above that, and one peak sits on the axis. With
``ripple_a = 0`` the floor is flat.

The base sits on z = 0, centered on the axis, and prints the way it is
modeled: floor on the bed, wall straight up. The crest only ever faces up,
so nothing overhangs and nothing needs support.

Usage:
    python base.py -o base.stl [--pot_d 70] [--slack 5] [--peak_h 10] [--lobes 6]
    python base.py -o base.stl --pot_d 140.2 --peak_h 25 --trough_h 21 --lobes 11 --ripple_a 5
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, fields
from pathlib import Path

from build123d import (
    Axis,
    Face,
    Keep,
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
# Grid points per ripple wavelength the floor's surface is fitted through,
# and how far the fit may stray from the cosine, mm.
RIPPLE_SAMPLES = 16
RIPPLE_TOL = 1e-3


@dataclass(frozen=True)
class BaseParams:
    """Every dimension of the base, in millimeters."""

    # The pot's diameter at its foot.
    pot_d: float = 70.0
    # How much wider the pocket is than the pot's foot, across the diameter.
    # Covers the pot's slope, which is not modeled.
    slack: float = 5.0
    wall: float = 2.4
    # The floor's thickness; with ripples, its thickness under the dimples.
    floor: float = 2.0
    # The wave on the wall's top edge, measured from the bed.
    peak_h: float = 10.0
    trough_h: float = 6.0
    lobes: int = 6
    # Radius the crest's inner and outer edges are rounded to.
    crest_r: float = 1.0
    # Chamfer on the outer edge of the floor, against elephant's foot.
    foot_chamfer: float = 0.5
    # Ripples on the floor's top: amplitude (0 for a flat floor) and
    # wavelength along x and y.
    ripple_a: float = 0.0
    ripple_l: float = 40.0

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

    @property
    def ring_h(self) -> float:
        """Height of the plain ring the wavy wall stands on: midway between
        the floor's top and where the crest's rounding starts at the
        troughs. The floor meets only the ring's cylinder, never the loft."""
        return (self.floor_top + self.trough_h - self.crest_r) / 2

    @property
    def floor_top(self) -> float:
        """The highest point of the floor: the ripples' peaks."""
        return self.floor + 2 * self.ripple_a

    def floor_z(self, x: float, y: float) -> float:
        """Height of the floor's top at (x, y) inside the pocket."""
        k = 2 * math.pi / self.ripple_l
        return self.floor + self.ripple_a * (1 + math.cos(k * x) * math.cos(k * y))

    def validate(self) -> None:
        if self.pot_d <= 0 or self.wall <= 0 or self.floor <= 0:
            raise ValueError("pot_d, wall and floor must be positive")
        if self.slack < 0:
            raise ValueError("slack must not be negative")
        if self.lobes < 1:
            raise ValueError("lobes must be at least 1")
        if self.peak_h < self.trough_h:
            raise ValueError("peak_h must not be below trough_h")
        if self.ripple_a < 0 or self.ripple_l <= 0:
            raise ValueError("ripple_a must not be negative and ripple_l must be positive")
        if self.trough_h - self.floor_top < 2 * self.crest_r or self.trough_h <= self.floor_top:
            raise ValueError(
                f"the wall stands only {self.trough_h - self.floor_top:g} above the floor at its "
                f"troughs, under the {2 * self.crest_r:g} the crest rounding needs: "
                "raise trough_h or shrink crest_r or ripple_a"
            )
        if not 0 <= self.crest_r < self.wall / 2:
            raise ValueError("crest_r must be at least 0 and under half the wall")
        if not 0 <= self.foot_chamfer < min(self.wall, self.floor):
            raise ValueError("foot_chamfer must be at least 0 and under the wall and the floor")
        if self.outer_d > BED:
            raise ValueError(f"the base is {self.outer_d:g} across, over the {BED:g} bed")

    def report(self) -> str:
        floor = (f"floor rippled {self.floor:g}-{self.floor_top:g} high every {self.ripple_l:g}"
                 if self.ripple_a else f"{self.floor:g} floor")
        return (
            f"base for a {self.pot_d:g} pot: {self.pocket_d:g} pocket, {self.outer_d:g} across, "
            f"{floor}, {self.wall:g} wall waving {self.trough_h:g}-{self.peak_h:g} "
            f"high over {self.lobes} lobes of {self.wavelength:.1f}"
        )


def _section(p: BaseParams, theta: float) -> Wire:
    """The wall's cross-section at angle theta round the rim, stood up in the
    radial plane there: ring to crest, pocket to outside, with the crest
    corners rounded."""
    r_in, r_out = p.pocket_d / 2, p.outer_d / 2
    z, r, h = p.crest_z(theta), p.crest_r, p.ring_h
    pts = [(r_in, h), (r_out, h), (r_out, z - r), (r_out - r, z), (r_in + r, z), (r_in, z - r)]
    # drop the zero-length sides left by a zero rounding
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


def _ring(p: BaseParams) -> Solid:
    """The foot of the wall: bed to ring_h, turned about the axis, with the
    outer corner on the bed chamfered."""
    r_in, r_out, c, h = p.pocket_d / 2, p.outer_d / 2, p.foot_chamfer, p.ring_h
    pts = [(r_in, 0), (r_out - c, 0), (r_out, c), (r_out, h), (r_in, h)]
    pts = [q for i, q in enumerate(pts) if q != pts[i - 1]]
    profile = Plane.XZ.from_local_coords(Wire.make_polygon(pts, close=True))
    return Solid.revolve(Face(profile), 360, Axis.Z)


def _wall(p: BaseParams) -> list[Solid]:
    """The wall above the ring, as 2 * lobes congruent pieces. Each lofts one half-lobe,
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


def _floor(p: BaseParams) -> Solid:
    """The floor: a disc running halfway into the wall, so its rim fuses
    inside solid material rather than along the wall's inner face. With
    ripples, its top is a B-spline fitted through the cosine on a square
    grid, and the disc is cut off under it."""
    r = p.pocket_d / 2 + p.wall / 2
    if p.ripple_a == 0:
        return Solid.make_cylinder(r, p.floor)
    half = r + p.ripple_l / RIPPLE_SAMPLES
    n = math.ceil(2 * half * RIPPLE_SAMPLES / p.ripple_l)
    xs = [-half + 2 * half * i / n for i in range(n + 1)]
    top = Face.make_surface_from_array_of_points(
        [[(x, y, p.floor_z(x, y)) for x in xs] for y in xs], tol=RIPPLE_TOL)
    # split keeps the side the face's normal points to as its top
    keep = Keep.TOP if top.normal_at(top.center()).Z < 0 else Keep.BOTTOM
    return Solid.make_cylinder(r, p.floor_top + 1).split(top, keep=keep)


def base(p: BaseParams) -> Part:
    p.validate()
    # the ripples' B-spline meets only the ring's cylinder: OCCT fails to
    # intersect it with the loft's faces
    body = _floor(p).fuse(_ring(p)).fuse(*_wall(p)).clean()
    return Part([body.solids()[0]])


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
