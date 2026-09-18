"""A narrow stadium-shaped spacer with a hole through its centre, to sit
between an acrylic sheet and the rafter it is screwed to where the round
star spacer is too wide.

The strip is ``length`` long and ``2 * half_width`` wide, its ends full
semicircles of radius ``half_width``, with a ``hole_d`` hole through the
centre for the screw leaving ``wall`` of material either side of it. Fit it
with the narrow dimension running down the slope: water then has only
``half_width`` to run before it is off the edge, and the rounded ends leave
no corner for a droplet to cling to.

The hole is modelled at the size it is drilled to. The strip lies in the XY
plane centred on the origin, its length along X, and is extruded
``thickness`` up Z. Print it flat, as drawn: the hole runs along the print's
Z, so nothing overhangs.

Usage:
    python strip.py -o strip.stl [--length 40] [--half_width 9] [--hole_d 6]
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, fields
from pathlib import Path

from build123d import Circle, Part, Sketch, SlotOverall, export_stl, extrude


@dataclass(frozen=True)
class StripParams:
    """Every dimension of the strip, in millimetres."""

    # Across the slope.
    length: float = 40.0
    # From the hole's centre to the long edges, down the slope; also the
    # radius of the round ends.
    half_width: float = 9.0
    # The hole the screw passes through, at the size it is drilled to.
    hole_d: float = 6.0
    # The standoff it sets.
    thickness: float = 3.0

    # ----- derived -----
    @property
    def width(self) -> float:
        return 2 * self.half_width

    @property
    def wall(self) -> float:
        """Material between the hole and the long edges."""
        return self.half_width - self.hole_d / 2

    def validate(self) -> None:
        if min(self.length, self.half_width, self.hole_d, self.thickness) <= 0:
            raise ValueError("length, half_width, hole_d and thickness must be positive")
        if self.hole_d >= self.width:
            raise ValueError("hole_d must be less than the strip's width")
        if self.length < self.width:
            raise ValueError("length must be at least 2 * half_width, or the ends cannot be round")

    def report(self) -> str:
        return (
            f"{self.length:g} x {self.width:g} x {self.thickness:g} strip, "
            f"{self.hole_d:g} hole, {self.wall:.1f} of wall either side"
        )


def profile(p: StripParams) -> Sketch:
    """The strip's plan: a stadium less the hole."""
    p.validate()
    # SlotOverall refuses a zero-length slot, so a strip as long as it is
    # wide is drawn as the disk it is
    outline = Circle(p.half_width) if p.length <= p.width + 1e-9 else SlotOverall(p.length, p.width)
    return Sketch(list((outline - Circle(p.hole_d / 2)).faces()))


def strip(p: StripParams) -> Part:
    return extrude(profile(p), amount=p.thickness, dir=(0, 0, 1))


def _cli() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, required=True, help=".stl, .step or .svg path")
    for f in fields(StripParams):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _cli().parse_args(argv)
    p = StripParams(**{f.name: getattr(args, f.name) for f in fields(StripParams)})
    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".svg":
        from build123d import ExportSVG

        svg = ExportSVG(scale=2, margin=10, line_weight=0.4)
        svg.add_shape(profile(p))
        svg.write(str(out))
    elif out.suffix == ".step":
        from build123d import export_step

        export_step(strip(p), str(out))
    else:
        export_stl(strip(p), str(out), tolerance=0.01, angular_tolerance=0.1)
    print(f"-> {out}")
    print(p.report())


if __name__ == "__main__":
    main()
