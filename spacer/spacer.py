"""A star-shaped band that sits between an acrylic sheet and the rafter it is
screwed to, with the fixing screw passing through the aperture in its middle.

The screw drives home into the rafter and the band holds the sheet off the
timber, so the sheet is spaced rather than drawn down onto it.

The shape is the *perimeter* of a ``points``-pointed star dilated by a disk
of radius ``band_r``: every point within ``band_r`` of the star's outline,
and nothing else. Dilating the outline rather than the whole star is what
gives the part an inside as well as an outside. The outer boundary is the
star grown by ``band_r``, which rounds each tip to that radius; the inner
boundary is the star shrunk by the same, which leaves a clear aperture down
the middle. So the part is a band ``2 * band_r`` wide everywhere, using
roughly half the material of the solid disk that would span the same circle
and leaving no broad flat face for water to sit on.

The star has its tips on ``star_r = outer_r - band_r`` and its valleys on
``waist`` of that, so the finished tips reach ``outer_r`` exactly. Eroding by
``band_r`` leaves an aperture of ``2 * (star_r * waist - band_r)`` across,
which must clear ``min_aperture`` so the screw passes: at the defaults it is
7.0 mm, a shade over the 6 mm hole, so the spacer threads onto the screw and
stays centred on it instead of sliding about during assembly.

The band lies in the XY plane centred on the origin and is extruded
``thickness`` up Z. Print it flat, as drawn: the aperture runs along the
print's Z, so nothing overhangs.

Usage:
    python spacer.py -o spacer.stl [--outer_r 20] [--band_r 3] [--waist 0.382]
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, fields
from pathlib import Path

from build123d import (
    Kind,
    Part,
    Polygon,
    Sketch,
    export_stl,
    extrude,
    offset,
)


@dataclass(frozen=True)
class SpacerParams:
    """Every dimension of the spacer, in millimetres."""

    # How far the finished tips reach from the axis.
    outer_r: float = 20.0
    # Radius of the disk the star's perimeter is dilated by: half the band's
    # width, and the radius every tip is rounded to.
    band_r: float = 3.0
    # The star's valleys, as a fraction of its tips. 0.382 (1 / phi^2) is the
    # proportion of a regular pentagram.
    waist: float = 0.382
    points: int = 5
    # The standoff it sets.
    thickness: float = 3.0
    # The aperture must stay at least this wide for the screw to pass.
    min_aperture: float = 6.0

    # ----- derived -----
    @property
    def star_r(self) -> float:
        """The star's circumradius, before dilation: the tips land on
        outer_r once the band is grown round them."""
        return self.outer_r - self.band_r

    @property
    def waist_r(self) -> float:
        """The star's valleys, before dilation."""
        return self.star_r * self.waist

    @property
    def band_w(self) -> float:
        """Width of the band: the diameter of the disk dilating the outline."""
        return 2 * self.band_r

    @property
    def aperture(self) -> float:
        """The clear opening down the middle, where the star eroded by
        band_r survives. Negative means the erosion closed it up."""
        return 2 * (self.waist_r - self.band_r)

    def validate(self) -> None:
        if self.outer_r <= 0 or self.thickness <= 0:
            raise ValueError("outer_r and thickness must be positive")
        if self.band_r <= 0:
            raise ValueError("band_r must be positive")
        if not 0 < self.waist < 1:
            raise ValueError("waist must be between 0 and 1, exclusive")
        if self.points < 3:
            raise ValueError("points must be at least 3")
        if self.band_r >= self.star_r:
            raise ValueError("band_r must be less than outer_r, or the star has no room")
        if self.aperture < self.min_aperture:
            raise ValueError(
                f"the clear aperture is {self.aperture:.2f}, under the {self.min_aperture:g} "
                "the screw needs: widen the waist, narrow the band, or grow outer_r"
            )

    def report(self) -> str:
        return (
            f"R{self.outer_r:g} x {self.thickness:g} spacer, "
            f"{self.points}-point star outline dilated by R{self.band_r:g} "
            f"into a {self.band_w:g} band, {self.aperture:.1f} clear aperture"
        )


def star(p: SpacerParams) -> Sketch:
    """The star the band is built round, tips up."""
    pts = []
    for i in range(2 * p.points):
        a = math.pi / 2 + i * math.pi / p.points
        r = p.star_r if i % 2 == 0 else p.waist_r
        pts.append((r * math.cos(a), r * math.sin(a)))
    return Sketch(list(Polygon(*pts, align=None).faces()))


def profile(p: SpacerParams) -> Sketch:
    """The spacer's plan: the star's perimeter dilated by a disk of band_r,
    i.e. the star grown by that radius less the star shrunk by it."""
    p.validate()
    face = star(p).faces()[0]
    band = offset(face, amount=p.band_r, kind=Kind.ARC).faces()[0]
    for hole in offset(face, amount=-p.band_r, kind=Kind.ARC).faces():
        band = band - hole
    return Sketch(list(band.faces()))


def spacer(p: SpacerParams) -> Part:
    return extrude(profile(p), amount=p.thickness, dir=(0, 0, 1))


def _cli() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, required=True, help=".stl, .step or .svg path")
    for f in fields(SpacerParams):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _cli().parse_args(argv)
    p = SpacerParams(**{f.name: getattr(args, f.name) for f in fields(SpacerParams)})
    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".svg":
        from build123d import ExportSVG

        svg = ExportSVG(scale=2, margin=10, line_weight=0.4)
        svg.add_shape(profile(p))
        svg.write(str(out))
    elif out.suffix == ".step":
        from build123d import export_step

        export_step(spacer(p), str(out))
    else:
        export_stl(spacer(p), str(out), tolerance=0.01, angular_tolerance=0.1)
    print(f"-> {out}")
    print(p.report())


if __name__ == "__main__":
    main()
