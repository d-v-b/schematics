"""Beam clamp: a C-shaped spring clip that cups the bottom of a rectangular
wooden beam and grips its two sides.

Coordinate system for the 2D profile (before extrusion):
  - The beam's bottom-left inner corner sits at (0, 0).
  - The beam occupies x in [0, inner_w], y >= 0.
  - The clamp base runs below y = 0; the arms run up the sides at x < 0 and
    x > inner_w.
The profile is extruded along +Z by ``length`` (the dimension along the beam).

Print with the C profile flat on the bed (the orientation of the exported
part), so bending stress in the arms lies within layers, not across them.

Usage:
    python beam_clamp.py -o out.stl [--wall 3] [--clearance 0.3] [--length 40] ...
    python beam_clamp.py --help
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, fields
from pathlib import Path

from build123d import (
    Align,
    Polygon,
    Axis,
    Circle,
    Compound,
    ExportSVG,
    FontStyle,
    Location,
    Mode,
    Part,
    Plane,
    Rectangle,
    Sketch,
    Text,
    export_stl,
    extrude,
    mirror,
)


def seat_offset(fillet_r: float, clearance: float) -> float:
    """How far the beam's square corners, resting on the inner fillets, hold
    the beam off the inner base face. The beam is centred in the inner span,
    so each corner sits clearance / 2 in from the arm."""
    inset = clearance / 2
    if inset >= fillet_r:
        return 0.0
    dx = min(fillet_r - inset, fillet_r)
    return fillet_r - math.sqrt(fillet_r**2 - dx**2)


@dataclass(frozen=True)
class ClampParams:
    """Every dimension of the clamp, in millimetres."""

    # Width of the beam face the clamp spans.
    beam_w: float = 53.6
    # Extra inner span beyond beam_w. Negative = interference at the walls.
    clearance: float = 0.3
    # Wall thickness of base and arms.
    wall: float = 3.0
    # How far the arms reach along the beam side, from the inner base face.
    arm_len: float = 53.6
    # Extrusion along the beam. 40 for the real part, ~10 for fit prototypes.
    length: float = 40.0
    # Inner fillet radius at each corner. Outer radius = fillet_r + wall.
    fillet_r: float = 2.0
    # Height of the tension bump on each arm's inner face. 0 disables.
    bump_h: float = 0.6
    # Radius of the circle that forms the bump (larger = gentler bump).
    bump_r: float = 4.0
    # Distance from the arm tip down to the bump centre.
    bump_from_tip: float = 6.0
    # Text engraved on the outer face of the base. Empty disables.
    label: str = ""
    # Engraving depth.
    label_depth: float = 0.4
    # Text height.
    label_size: float = 5.0
    # Female dovetail groove in the underside of the base, running along the
    # beam, for hanging things from the clamp: the curtain rail clamp's male
    # dovetail slides into it. Width at the wide (inner) end; 0 = none.
    # Depth, flank angle from vertical, and clearance added all round. The
    # printer cuts grooves oversize: 0.05 measured 0.15 mm of play, so the
    # modelled clearance is negative to land on a snug sliding fit.
    dovetail_w: float = 0.0
    dovetail_h: float = 3.0
    dovetail_angle: float = 12.0
    dovetail_clearance: float = -0.025

    @property
    def inner_w(self) -> float:
        return self.beam_w + self.clearance

    @property
    def seat(self) -> float:
        """Gap between the inner base face and the beam, set by the fillets."""
        return seat_offset(self.fillet_r, self.clearance)

    def validate(self) -> None:
        if self.wall <= 0:
            raise ValueError(f"wall must be positive, got {self.wall}")
        if self.inner_w <= 2 * self.fillet_r:
            raise ValueError(
                f"inner span {self.inner_w} must exceed twice the fillet radius {self.fillet_r}"
            )
        if self.arm_len <= self.fillet_r + self.wall / 2:
            raise ValueError(
                f"arm_len {self.arm_len} must exceed fillet_r + wall/2 = {self.fillet_r + self.wall / 2}"
            )
        if self.bump_h > 0 and not (
            self.fillet_r + self.bump_r < self.arm_len - self.bump_from_tip < self.arm_len - self.wall / 2
        ):
            raise ValueError("bump does not fit on the straight part of the arm")
        if self.label and self.label_depth >= self.wall:
            raise ValueError(f"label_depth {self.label_depth} must be less than wall {self.wall}")
        validate_dovetail(self)


def _sk(shape) -> Sketch:
    """Normalise an algebra result (Face, Compound or list) to a single Sketch."""
    return Sketch(list(shape.faces()))


def dovetail_profile(w: float, h: float, angle: float, x0: float, y0: float, clearance: float = 0.0) -> Sketch:
    """A dovetail cross-section: a trapezoid with its narrow neck on the line
    y = y0 and its wide end of width w at y0 + h, flanks `angle` degrees
    from vertical, centred on x0. Used as the groove cut up into a beam
    clamp's base (y0 = the underside) and as the ridge standing on the rail
    clamp's plate (y0 = the plate top). A positive clearance grows it by that
    much all round, for the female side."""
    t = math.tan(math.radians(angle))
    hh = h + clearance
    wt = w + 2 * clearance
    wn = wt - 2 * hh * t
    # counter-clockwise so the face normal is +Z and booleans behave
    pts = [(x0 - wn / 2, y0 - 1e-3), (x0 + wn / 2, y0 - 1e-3), (x0 + wt / 2, y0 + hh), (x0 - wt / 2, y0 + hh)]
    return _sk(Polygon(*pts, align=None))


def validate_dovetail(p) -> None:
    """Shared checks for the female base groove on any of the beam models."""
    if p.dovetail_w < 0 or p.dovetail_h < 0:
        raise ValueError("dovetail dimensions must be non-negative")
    if p.dovetail_clearance < -0.2:
        raise ValueError("dovetail_clearance below -0.2 mm is more than print oversize can absorb")
    if p.dovetail_w > 0:
        if not 0 < p.dovetail_angle < 45:
            raise ValueError("dovetail_angle must be between 0 and 45 degrees from vertical")
        flat = p.inner_w - 2 * p.fillet_r  # the base's flat underside between the elbow rounds
        if p.dovetail_w + 2 * p.dovetail_clearance + 2 > flat:
            raise ValueError(f"dovetail_w {p.dovetail_w} must fit on the base's flat underside ({flat:.1f} mm) with material beside it")
        if p.dovetail_w - 2 * p.dovetail_h * math.tan(math.radians(p.dovetail_angle)) < 2:
            raise ValueError("dovetail neck is too narrow: lower dovetail_h or dovetail_angle")
        floor = p.wall - p.dovetail_h - p.dovetail_clearance
        if floor < 1.0:
            raise ValueError(
                f"the groove leaves only {floor:.2f} mm of base above it; keep at least 1 mm (thicken the wall or shallow the groove)"
            )


def top_face_label(p, x: float, y: float, along: str = "y", size: float | None = None) -> Part | None:
    """Text engraved into the part's top face when printed (the profile face
    at z = length), centred on (x, y), reading along +x or along +y (for a
    narrow arm). Used to put an ID on coupons, which are too short along the
    beam to carry text on their sides."""
    if not p.label:
        return None
    size = p.label_size if size is None else size
    x_dir = (0, 1, 0) if along == "y" else (1, 0, 0)
    plane = Plane(origin=(x, y, p.length), x_dir=x_dir, z_dir=(0, 0, 1))
    text = plane * Text(p.label, font_size=size, font_style=FontStyle.BOLD)
    return extrude(text, amount=-p.label_depth)


def with_base_dovetail(profile_sketch: Sketch, p) -> Sketch:
    """Cut the female groove up into the base's underside at y = -wall."""
    if p.dovetail_w <= 0:
        return profile_sketch
    groove = dovetail_profile(
        p.dovetail_w, p.dovetail_h, p.dovetail_angle, p.inner_w / 2, -p.wall, p.dovetail_clearance
    )
    return _sk(profile_sketch - groove)


def _elbow(p: ClampParams) -> Sketch:
    """Quarter annulus (inner radius fillet_r, outer fillet_r + wall) centred at
    (fillet_r, fillet_r), covering the quadrant that points towards (-x, -y)."""
    r_out = p.fillet_r + p.wall
    ring = Circle(r_out) - Circle(p.fillet_r)
    quadrant = Rectangle(r_out, r_out, align=(Align.MAX, Align.MAX))
    return _sk((ring & quadrant).moved(Location((p.fillet_r, p.fillet_r))))


def _arm(p: ClampParams) -> Sketch:
    """Left arm, x in [-wall, 0], with a fully rounded tip topping out at arm_len."""
    tip_r = p.wall / 2
    straight = Rectangle(
        p.wall, p.arm_len - tip_r - p.fillet_r, align=(Align.MIN, Align.MIN)
    ).moved(Location((-p.wall, p.fillet_r)))
    tip = Circle(tip_r).moved(Location((-tip_r, p.arm_len - tip_r)))
    return _sk(straight + tip)


def _bump(p: ClampParams) -> Sketch | None:
    """Tension bump on the left arm's inner face: a circle of radius bump_r
    whose centre sits inside the wall so that only bump_h protrudes."""
    if p.bump_h <= 0:
        return None
    circle = Circle(p.bump_r).moved(
        Location((p.bump_h - p.bump_r, p.arm_len - p.bump_from_tip))
    )
    # clip to the arm wall plus cavity so nothing pokes out the back
    clip = Rectangle(p.wall + p.bump_r, p.arm_len, align=(Align.MIN, Align.MIN)).moved(
        Location((-p.wall, 0))
    )
    return _sk(circle & clip)


def profile(p: ClampParams) -> Sketch:
    """The 2D C-shaped cross-section in the XY plane."""
    p.validate()
    base = Rectangle(
        p.inner_w - 2 * p.fillet_r, p.wall, align=(Align.MIN, Align.MIN)
    ).moved(Location((p.fillet_r, -p.wall)))
    left = _elbow(p) + _arm(p)
    bump = _bump(p)
    if bump is not None:
        left = left + bump
    left = _sk(left)  # Face + Sketch does not fuse; keep everything a Sketch
    right = mirror(left, about=Plane.YZ.offset(p.inner_w / 2))
    merged = with_base_dovetail(_sk(base + left + right), p)
    assert len(merged.faces()) == 1, "profile did not fuse into a single face"
    return merged


def _label_cut(p: ClampParams) -> Part | None:
    if not p.label:
        return None
    # Plane on the outer face of the base (y = -wall), normal pointing out
    # (-y), local x along +x, local y along +z, so the text reads correctly
    # when viewed from outside.
    face_plane = Plane(
        origin=(p.inner_w / 2, -p.wall, p.length / 2), x_dir=(1, 0, 0), z_dir=(0, -1, 0)
    )
    text = face_plane * Text(p.label, font_size=p.label_size, font_style=FontStyle.BOLD)
    # extrude against the plane normal, i.e. into the wall
    return extrude(text, amount=-p.label_depth)


def clamp(p: ClampParams) -> Part:
    """The finished solid."""
    # boolean ops can leave the sketch face normal pointing -Z; force +Z
    body = extrude(profile(p), amount=p.length, dir=(0, 0, 1))
    cut = _label_cut(p)
    if cut is not None:
        body = body - cut
    return body


def make_cli(params_cls: type, doc: str) -> argparse.ArgumentParser:
    """Argument parser with one --flag per dataclass field, typed from its default."""
    ap = argparse.ArgumentParser(description=doc.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, required=True, help="STL (or .step/.svg) path")
    for f in fields(params_cls):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    return ap


def run_cli(params_cls: type, doc: str, build, profile_fn, argv: list[str] | None = None) -> None:
    """Parse params, then write .svg (profile), .step or .stl (default)."""
    args = make_cli(params_cls, doc).parse_args(argv)
    p = params_cls(**{f.name: getattr(args, f.name) for f in fields(params_cls)})
    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".svg":
        svg = ExportSVG(scale=4, margin=10, line_weight=0.5)
        svg.add_shape(profile_fn(p))
        svg.write(str(out))
    elif out.suffix == ".step":
        from build123d import export_step

        export_step(build(p), str(out))
    else:
        export_stl(build(p), str(out), tolerance=0.01, angular_tolerance=0.1)
    print(f"-> {out}")


def main(argv: list[str] | None = None) -> None:
    run_cli(ClampParams, __doc__, clamp, profile, argv)


if __name__ == "__main__":
    main()
