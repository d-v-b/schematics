"""Flat bar with a row of M6 clearance holes down its middle, to sit on top
of a 40 mm aluminium extrusion rail and be bolted into its T-slot.

The bar is ``width`` x ``thickness`` in section and ``length`` long, with
its plan corners rounded to ``corner_r``. The holes are ``hole_d`` in
diameter (M6 clearance plus a print allowance), on a ``pitch`` along the
bar's centreline, and the row is centred along the length so the end holes
sit at least ``end_margin`` from the ends. ``holes`` fixes the count
instead when it is positive.

The bar lies in the XY plane centred on the origin, its length along X and
its width along Y, and is extruded ``thickness`` up Z. Print it flat, as
drawn: the holes run along the print's Z, so nothing overhangs.

Usage:
    python bolt_bar.py -o bar.stl [--length 200] [--pitch 40] [--hole_d 6.6] ...
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, fields
from pathlib import Path

from build123d import (
    Circle,
    FontStyle,
    Location,
    Part,
    Plane,
    RectangleRounded,
    Sketch,
    Text,
    export_stl,
    extrude,
)


@dataclass(frozen=True)
class BarParams:
    """Every dimension of the bar, in millimetres."""

    # Extent along the rail.
    length: float = 200.0
    # Across the rail: the same as the 40 mm extrusion it sits on.
    width: float = 40.0
    thickness: float = 4.0
    # Hole diameter. M6 clearance is 6.4 (ISO 273 fine); 0.2 more lets a
    # printed hole, which comes out small, pass the bolt.
    hole_d: float = 6.6
    # Centre-to-centre distance between neighbouring holes.
    pitch: float = 40.0
    # Least distance from either end of the bar to the nearest hole's
    # centre. The row is centred along the bar, so the actual margin is this
    # or more.
    end_margin: float = 20.0
    # Number of holes. 0 = as many as fit at the pitch inside the margins.
    holes: int = 0
    # Radius on the bar's four plan corners.
    corner_r: float = 3.0
    # ID engraved into the top face, reading along the bar, between the
    # first two holes (or centred when there is one hole). Empty disables.
    label: str = ""
    label_depth: float = 0.4
    label_size: float = 3.0

    # ----- derived -----
    @property
    def n_holes(self) -> int:
        if self.holes > 0:
            return self.holes
        span = self.length - 2 * self.end_margin
        if span < 0:
            return 0
        return int(math.floor(span / self.pitch + 1e-9)) + 1

    @property
    def hole_xs(self) -> list[float]:
        """Hole centres along X, centred on the bar."""
        n = self.n_holes
        return [(i - (n - 1) / 2) * self.pitch for i in range(n)]

    @property
    def ligament(self) -> float:
        """Solid material between two neighbouring holes."""
        return self.pitch - self.hole_d

    @property
    def edge_ligament(self) -> float:
        """Solid material between a hole and the bar's long edge."""
        return (self.width - self.hole_d) / 2

    def validate(self) -> None:
        if self.length <= 0 or self.width <= 0 or self.thickness <= 0:
            raise ValueError("length, width and thickness must be positive")
        if self.hole_d <= 0:
            raise ValueError("hole_d must be positive")
        if self.pitch <= self.hole_d:
            raise ValueError("pitch must exceed hole_d, or the holes merge")
        if self.hole_d >= self.width:
            raise ValueError("hole_d must be less than width")
        if self.n_holes < 1:
            raise ValueError("no hole fits: length must be at least 2 * end_margin")
        xs = self.hole_xs
        if xs[-1] + self.hole_d / 2 >= self.length / 2:
            raise ValueError("the end holes break out of the bar's ends")
        if self.corner_r < 0 or 2 * self.corner_r > min(self.length, self.width):
            raise ValueError("corner_r must fit within the bar")
        if self.label and self.label_depth >= self.thickness:
            raise ValueError("label_depth must be less than thickness")

    def report(self) -> str:
        xs = self.hole_xs
        return (
            f"{self.width} x {self.thickness} x {self.length} bar, "
            f"{self.n_holes} holes d{self.hole_d} at {self.pitch} pitch, "
            f"end margin {self.length / 2 - xs[-1]:.1f}, "
            f"ligament {self.ligament:.1f} between holes, {self.edge_ligament:.1f} to the edge"
        )


def outline(p: BarParams) -> Sketch:
    """The bar's plan without holes."""
    return Sketch(list(RectangleRounded(p.length, p.width, p.corner_r).faces()))


def holes(p: BarParams) -> Sketch:
    return Sketch([Circle(p.hole_d / 2).moved(Location((x, 0))).face() for x in p.hole_xs])


def profile(p: BarParams) -> Sketch:
    """The bar's plan with the holes cut."""
    p.validate()
    return Sketch(list((outline(p) - holes(p)).faces()))


def _label_cut(p: BarParams) -> Part | None:
    if not p.label:
        return None
    xs = p.hole_xs
    x_mid = (xs[0] + xs[1]) / 2 if len(xs) > 1 else 0.0
    size = min(p.label_size, p.width / 4)
    plane = Plane(origin=(x_mid, 0, p.thickness), x_dir=(1, 0, 0), z_dir=(0, 0, 1))
    text = plane * Text(p.label, font_size=size, font_style=FontStyle.BOLD)
    return extrude(text, amount=-p.label_depth)


def bar(p: BarParams) -> Part:
    body = extrude(profile(p), amount=p.thickness, dir=(0, 0, 1))
    cut = _label_cut(p)
    if cut is not None:
        body = body - cut
    return body


def _cli() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, required=True, help=".stl, .step or .svg path")
    for f in fields(BarParams):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _cli().parse_args(argv)
    p = BarParams(**{f.name: getattr(args, f.name) for f in fields(BarParams)})
    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".svg":
        from build123d import ExportSVG

        svg = ExportSVG(scale=2, margin=10, line_weight=0.4)
        svg.add_shape(profile(p))
        svg.write(str(out))
    elif out.suffix == ".step":
        from build123d import export_step

        export_step(bar(p), str(out))
    else:
        export_stl(bar(p), str(out), tolerance=0.01, angular_tolerance=0.1)
    print(f"-> {out}")
    print(p.report())


if __name__ == "__main__":
    main()
