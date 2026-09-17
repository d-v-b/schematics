"""A flat disk with a bore down its axis: a spacer to sit between an acrylic
sheet and the rafter it is screwed to, with the fixing screw passing through
it.

The screw drives home into the rafter and the disk holds the sheet off the
timber, so it is spaced rather than drawn down onto it. The disk is
``outer_r`` in radius and ``thickness`` thick, with a ``hole_d`` bore through
the middle leaving ``wall`` of material all round it. ``thickness`` is the
dimension worth varying: it is the standoff the spacer exists to set. The
bore is the clearance hole the screw passes through, modelled at the size it
is drilled to.

The disk lies in the XY plane centred on the origin and is extruded
``thickness`` up Z. Print it flat, as drawn: the bore runs along the print's
Z, so nothing overhangs.

Usage:
    python spacer.py -o spacer.stl [--outer_r 20] [--hole_d 6] [--thickness 3]
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, fields
from pathlib import Path

from build123d import (
    Circle,
    FontStyle,
    Part,
    Plane,
    Sketch,
    Text,
    export_stl,
    extrude,
)


@dataclass(frozen=True)
class SpacerParams:
    """Every dimension of the spacer, in millimetres."""

    # Radius of the disk.
    outer_r: float = 20.0
    # Diameter of the bore: the clearance hole the screw passes through.
    hole_d: float = 6.0
    # The standoff the spacer sets.
    thickness: float = 3.0
    # ID engraved into the top face, reading along X, in the ring of
    # material round the bore. Empty disables.
    label: str = ""
    label_depth: float = 0.4
    label_size: float = 3.0

    # ----- derived -----
    @property
    def wall(self) -> float:
        """Material between the bore and the rim."""
        return self.outer_r - self.hole_d / 2

    def validate(self) -> None:
        if self.outer_r <= 0 or self.thickness <= 0:
            raise ValueError("outer_r and thickness must be positive")
        if self.hole_d <= 0:
            raise ValueError("hole_d must be positive")
        if self.hole_d >= 2 * self.outer_r:
            raise ValueError("hole_d must be less than the disk it is bored through")
        if self.label and self.label_depth >= self.thickness:
            raise ValueError("label_depth must be less than thickness")

    def report(self) -> str:
        return (
            f"R{self.outer_r:g} x {self.thickness:g} spacer, "
            f"{self.hole_d:g} bore, {self.wall:.1f} of wall round it"
        )


def profile(p: SpacerParams) -> Sketch:
    """The spacer's plan: an annulus."""
    p.validate()
    return Sketch(list((Circle(p.outer_r) - Circle(p.hole_d / 2)).faces()))


def _label_cut(p: SpacerParams) -> Part | None:
    if not p.label:
        return None
    # in the ring of material beside the bore (+y side), reading along X
    y_mid = (p.hole_d / 2 + p.outer_r) / 2
    size = min(p.label_size, p.wall - 1.0)
    plane = Plane(origin=(0, y_mid, p.thickness), x_dir=(1, 0, 0), z_dir=(0, 0, 1))
    text = plane * Text(p.label, font_size=size, font_style=FontStyle.BOLD)
    return extrude(text, amount=-p.label_depth)


def spacer(p: SpacerParams) -> Part:
    body = extrude(profile(p), amount=p.thickness, dir=(0, 0, 1))
    cut = _label_cut(p)
    if cut is not None:
        body = body - cut
    return body


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
