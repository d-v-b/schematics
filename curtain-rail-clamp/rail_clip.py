"""Snap-on clamp for one or more IKEA FRAMFUSIG curtain rails side by side,
gripping from above.

Each rail sits in a thin C of uniform ``wall`` that follows the rail's
section at a small ``clearance``, open at the bottom. The C's two lips reach
``lip_depth`` below the start of the rail's lower rounds, so the opening is
narrower than the rail by an interference and the rail has to be pushed up
into the C: each half flexes outward as a curved cantilever and springs back
to trap the rail. The underside stays open for the gliders and the curtain.

The Cs hang from a flat top plate (``plate_t`` thick) that spans them at
``spacing`` centre to centre; the plate is the mounting face. Each C hangs by
a short neck (``stem_w`` x ``stem_h``) on its flat top, filleted into both
the plate and the C, so the transitions are smooth while the C's rounds,
where the flex lives, stay free. Each C can fit the inner or the outer tube
(``tubes``), since the rail is telescopic.

The profile is drawn in the XY plane with the rail's axis along Z, the slot
facing -Y, and the section centred on X = 0, Y = 0; it is extruded ``length``
along the rail. Print it with the profile flat on the bed.

Usage:
    python rail_clip.py -o clip.stl [--tube outer] [--wall 1.2] [--lip_depth 2.5] ...
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, fields
from pathlib import Path

from build123d import (
    Align,
    Axis,
    Circle,
    Polygon,
    Location,
    Part,
    Rectangle,
    RectangleRounded,
    Sketch,
    export_stl,
    extrude,
)

from compliance import MATERIALS, ArmFlex
from framfusig import PROFILES, RailProfile


def _sk(shape) -> Sketch:
    return Sketch(list(shape.faces()))


@dataclass(frozen=True)
class ClipParams:
    """Every dimension of the clip, in millimetres."""

    # Rail section each C fits, left to right, comma-separated: "inner" or
    # "outer". One entry per rail.
    tubes: str = "outer,outer"
    # Centre-to-centre distance between neighbouring rails.
    spacing: float = 40.0
    # Gap between the rail and the clip's cavity all round. Zero or negative
    # makes the walls grip the rail everywhere, not only at the lips.
    clearance: float = 0.0
    # Thickness of the C. The flex happens here, so keep it thin.
    wall: float = 1.2
    # Width of the opening between the lip tips. The lips follow the rail's
    # lower rounds down until the cavity is this wide, or, if this is narrower
    # than the rail's flat underside, along the underside to this width. The
    # rail is wider than this by the interference and must be pushed in.
    opening: float = 16.0
    # Insertion stress below this multiple of the material's strength is
    # refused; between it and 1.5x a warning is printed. Printed thin walls
    # have proved more compliant than the cantilever model, so 1.0 is usable.
    min_safety: float = 1.0
    # Extent along the rail.
    length: float = 20.0
    # Thickness of the flat top plate that joins the Cs and mounts the clamp.
    plate_t: float = 3.0
    # Neck joining each C's flat top to the plate, and the fillet radius at
    # its four concave corners. Neck plus fillets must stay on the C's flat
    # top so the rounds, where the flex lives, are not stiffened.
    stem_w: float = 4.0
    stem_h: float = 3.0
    fillet_r: float = 1.5
    # Material for the compliance report.
    material: str = "pla"

    # ----- derived -----
    @property
    def tube_list(self) -> list[str]:
        return [t.strip() for t in self.tubes.split(",") if t.strip()]

    @property
    def n_rails(self) -> int:
        return len(self.tube_list)

    @property
    def tube(self) -> str:
        """The tube the compliance figures refer to: the largest fitted."""
        return "outer" if "outer" in self.tube_list else "inner"

    @property
    def rail(self) -> RailProfile:
        return PROFILES[self.tube]

    def rail_x(self, i: int) -> float:
        """Centre of rail i, rails centred on x = 0 as a group."""
        return (i - (self.n_rails - 1) / 2) * self.spacing

    @property
    def plate_w(self) -> float:
        return (self.n_rails - 1) * self.spacing + self.out_w

    @property
    def cav_w(self) -> float:
        return self.rail.width + 2 * self.clearance

    @property
    def cav_h(self) -> float:
        return self.rail.height + 2 * self.clearance

    @property
    def cav_r(self) -> float:
        return self.rail.radius + self.clearance

    @property
    def out_w(self) -> float:
        return self.cav_w + 2 * self.wall

    @property
    def out_h(self) -> float:
        return self.cav_h + 2 * self.wall

    @property
    def out_r(self) -> float:
        return self.cav_r + self.wall

    @property
    def side_bottom(self) -> float:
        """Y where the cavity's straight side ends and its lower round begins."""
        return -(self.cav_h / 2 - self.cav_r)

    @property
    def flat_bottom(self) -> float:
        """Width of the cavity's flat underside."""
        return self.cav_w - 2 * self.cav_r

    @property
    def on_underside(self) -> bool:
        """Whether the lips wrap past the rounds onto the underside."""
        return self.opening <= self.flat_bottom

    @property
    def lip_depth(self) -> float:
        """How far below the start of the lower rounds the lips reach."""
        if self.on_underside:
            return self.cav_r
        half_narrowing = (self.cav_w - self.opening) / 2
        return math.sqrt(self.cav_r**2 - (self.cav_r - half_narrowing) ** 2)

    @property
    def lip_y(self) -> float:
        """Y of the lip tips."""
        return self.side_bottom - self.lip_depth

    @property
    def interference(self) -> float:
        """How much wider the rail itself is than the opening."""
        return self.rail.width - self.opening

    @property
    def lip_angle(self) -> float:
        """Angle of the rail's surface at the lip, from vertical (degrees).
        90 when the lips wrap onto the underside."""
        return math.degrees(math.asin(min(1.0, self.lip_depth / self.cav_r)))

    @property
    def flat_half(self) -> float:
        """Half the width of a C's flat top (for the largest tube)."""
        return self.out_w / 2 - self.out_r

    @property
    def fixed_x(self) -> float:
        """How far from a C's top centre it is effectively clamped: the edge
        of the neck plus its fillet."""
        return self.stem_w / 2 + self.fillet_r

    @property
    def arc_len(self) -> float:
        """Cantilever length of one half of the C: along the wall's centreline
        from where it is fixed to the lip."""
        r_c = self.cav_r + self.wall / 2
        top = max(0.0, (self.cav_w / 2 - self.cav_r) - self.fixed_x)
        along_bottom = (self.flat_bottom - self.opening) / 2 if self.on_underside else 0.0
        return top + math.pi * r_c / 2 + (self.cav_h / 2 - self.cav_r) + self.lip_depth + along_bottom

    def flex(self) -> ArmFlex:
        """Each half of the C opening by half the interference on insertion."""
        return ArmFlex(self.wall, self.length, self.arc_len, self.interference / 2, MATERIALS[self.material])

    @property
    def pull_out(self) -> float:
        """Rough downward force before the rail pushes the lips apart and
        escapes, friction ignored. Each lip presses on the rail's lower round
        with the spring force F held at the full interference; the round's
        surface there is lip_angle from vertical, so the contact normal is
        that far from horizontal and carries F * tan(angle) vertically per
        lip. Shallow lips (small angle) barely hold; lips near the underside
        hold until they break. N"""
        if self.on_underside:
            return float("inf")
        f = self.flex().force
        return 2 * f * math.tan(math.radians(self.lip_angle))

    def report(self) -> str:
        fl = self.flex()
        hold = "cannot pull out: the lips wrap under the rail (slide the clamp on from the rail's end)" if self.on_underside else (
            f"holds about {self.pull_out:.0f} N ({self.pull_out / 9.81:.1f} kg) before the rail pulls out"
        )
        warn = "" if fl.safety_vs_strength >= 1.5 else "  WARNING: insertion stress is within 1.5x of the material's strength\n"
        return (
            f"{self.n_rails} rail(s) [{self.tubes}] at {self.spacing} mm; figures for the {self.tube} tube, "
            f"wall {self.wall}, clearance {self.clearance}, opening {self.opening}: lips reach {self.lip_depth:.2f} mm "
            f"below the rounds ({'onto the underside' if self.on_underside else f'lip angle {self.lip_angle:.0f} deg'}), "
            f"interference {self.interference:.2f} mm\n"
            f"  insertion: each half opens {fl.deflection:.2f} mm over {fl.arm_len:.1f} mm -> "
            f"{fl.force:.1f} N, {fl.stress:.1f} MPa ({fl.safety_vs_strength:.1f}x under {fl.material.name} strength)\n"
            f"{warn}  {hold}"
        )

    def validate(self) -> None:
        if not self.tube_list or any(t not in PROFILES for t in self.tube_list):
            raise ValueError(f"tubes must be a comma-separated list of {sorted(PROFILES)}")
        if self.n_rails > 1 and self.spacing < self.out_w:
            raise ValueError(f"spacing {self.spacing} must be at least the clip width {self.out_w:.1f}")
        if self.wall <= 0:
            raise ValueError("wall must be positive")
        if self.clearance < -0.5:
            raise ValueError("clearance below -0.5 mm is more interference than the walls can take")
        if self.opening >= self.rail.width:
            raise ValueError(f"opening {self.opening} must be narrower than the rail ({self.rail.width}) to grip it")
        if self.opening <= self.rail.slot_w + 2 * self.wall:
            raise ValueError("opening is too narrow: the lips would reach the glider slot")
        if self.plate_t <= 0:
            raise ValueError("plate_t must be positive")
        if self.stem_w <= 0 or self.stem_h < 0 or self.fillet_r < 0:
            raise ValueError("stem_w must be positive; stem_h and fillet_r non-negative")
        if self.fillet_r > self.stem_h:
            raise ValueError(f"fillet_r {self.fillet_r} must not exceed stem_h {self.stem_h}")
        for tube in self.tube_list:
            q = PROFILES[tube]
            flat_half = (q.width + 2 * self.clearance + 2 * self.wall) / 2 - (q.radius + self.clearance + self.wall)
            if self.fixed_x > flat_half + 1e-9:
                raise ValueError(
                    f"stem_w/2 + fillet_r = {self.fixed_x:.2f} must fit on the {tube} C's flat top "
                    f"(half width {flat_half:.2f}) or it stiffens the rounds"
                )
        if self.material not in MATERIALS:
            raise ValueError(f"material must be one of {sorted(MATERIALS)}")
        # lips wrapped under the rail cannot snap over it; the clamp slides on
        # from the rail's end instead, so insertion stress does not apply
        if not self.on_underside and self.flex().safety_vs_strength < self.min_safety:
            raise ValueError(
                f"insertion stress {self.flex().stress:.0f} MPa exceeds the material's strength / min_safety: "
                "thin the wall, widen the opening or lower min_safety"
            )


def _c_profile(p: ClipParams, tube: str) -> Sketch:
    """One C for the given tube, centred on x = 0. The ring is cut at each
    lower round along the radial line at the lip angle, so the cut face is
    perpendicular to the wall, and the lip end is rounded with half the
    wall thickness."""
    q = ClipParams(**{**{f.name: getattr(p, f.name) for f in fields(ClipParams)}, "tubes": tube})
    ring = _sk(RectangleRounded(q.out_w, q.out_h, q.out_r) - RectangleRounded(q.cav_w, q.cav_h, q.cav_r))
    phi = math.radians(q.lip_angle)  # radial direction of the lip, below horizontal
    big = q.out_r + 2
    keep = Rectangle(q.out_w + 2, q.out_h + 2, align=(Align.CENTER, Align.MIN)).moved(Location((0, q.side_bottom)))
    cav = RectangleRounded(q.cav_w, q.cav_h, q.cav_r)
    c = None
    for sign in (-1, 1):
        cx, cy = sign * (q.cav_w / 2 - q.cav_r), q.side_bottom  # centre of this lower round
        # sector from the horizontal (the side) sweeping down to the lip angle
        n = 12
        pts = [(cx, cy)] + [
            (cx + sign * big * math.cos(a), cy - big * math.sin(a)) for a in [phi * k / n for k in range(n + 1)]
        ]
        sector = Polygon(*pts, align=None)
        keep = _sk(keep + sector)
    c = _sk(ring & keep)
    for sign in (-1, 1):
        cx, cy = sign * (q.cav_w / 2 - q.cav_r), q.side_bottom
        r_mid = q.cav_r + q.wall / 2
        tip = (cx + sign * r_mid * math.cos(phi), cy - r_mid * math.sin(phi))
        c = _sk(c + _sk(Circle(q.wall / 2).moved(Location(tip)) - cav))
    return c


def cavity(p: ClipParams, i: int = 0) -> Sketch:
    q = PROFILES[p.tube_list[i]]
    return RectangleRounded(q.width + 2 * p.clearance, q.height + 2 * p.clearance, q.radius + p.clearance).moved(
        Location((p.rail_x(i), 0))
    )


def profile(p: ClipParams) -> Sketch:
    """The clamp's cross-section: one C per rail under a common top plate.
    Every C's top sits at the same height, so the plate lies flat on all of
    them; smaller tubes hang lower inside."""
    p.validate()
    y_top = p.out_h / 2  # top of the largest C
    parts = None
    for i, tube in enumerate(p.tube_list):
        c = _c_profile(p, tube)
        q = PROFILES[tube]
        c_top = q.height / 2 + p.clearance + p.wall
        c = c.moved(Location((p.rail_x(i), y_top - c_top)))
        parts = c if parts is None else _sk(parts + c)
    y_plate = y_top + p.stem_h
    plate = Rectangle(p.plate_w, p.plate_t, align=(Align.CENTER, Align.MIN)).moved(Location((0, y_plate)))
    out = _sk(parts + plate)
    # each C hangs from the plate by a neck on its flat top, with concave
    # fillets at the neck's four corners
    for i in range(p.n_rails):
        x = p.rail_x(i)
        neck = Rectangle(p.stem_w, p.stem_h + 0.02, align=(Align.CENTER, Align.MIN)).moved(Location((x, y_top - 0.01)))
        out = _sk(out + neck)
        for sign in (-1, 1):
            x_c = x + sign * p.stem_w / 2  # neck's side face
            for y_c, up in ((y_top, +1), (y_plate, -1)):
                if p.fillet_r <= 0:
                    continue
                # fillet material: a square in the free quadrant minus the circle tangent to both faces
                x0, x1 = sorted((x_c, x_c + sign * p.fillet_r))
                y0, y1 = sorted((y_c, y_c + up * p.fillet_r))
                square = Rectangle(x1 - x0, y1 - y0, align=(Align.MIN, Align.MIN)).moved(Location((x0, y0)))
                circle = Circle(p.fillet_r).moved(Location((x_c + sign * p.fillet_r, y_c + up * p.fillet_r)))
                out = _sk(out + _sk(square - circle))
    # round the plate's top corners
    r = p.plate_t / 2
    for sign in (-1, 1):
        corner = Rectangle(r, r, align=(Align.MIN, Align.MIN)).moved(Location((sign * p.plate_w / 2 - (r if sign > 0 else 0), y_plate + p.plate_t - r)))
        out = _sk(_sk(out - corner) + Circle(r).moved(Location((sign * (p.plate_w / 2 - r), y_plate + p.plate_t - r))))
    assert len(out.faces()) == 1, "profile did not fuse into a single face"
    return out


def clip(p: ClipParams) -> Part:
    return extrude(profile(p), amount=p.length, dir=(0, 0, 1))


def rail_solids(p: ClipParams, margin: float = 10.0) -> list[Part]:
    """Each rail's section seated in its C, for checking the fit. Every C's
    top is at the same height, so rail i sits so that its top clears the
    plate by clearance + wall."""
    y_top = p.out_h / 2
    out = []
    for i, tube in enumerate(p.tube_list):
        q = PROFILES[tube]
        y = y_top - p.wall - p.clearance - q.height / 2
        sec = q.section().moved(Location((p.rail_x(i), y, -margin)))
        out.append(extrude(sec, amount=p.length + 2 * margin, dir=(0, 0, 1)))
    return out


def _cli() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--output", type=Path, required=True, help=".stl, .step or .svg path")
    for f in fields(ClipParams):
        ap.add_argument(f"--{f.name}", type=type(f.default), default=f.default)
    return ap


def main(argv: list[str] | None = None) -> None:
    args = _cli().parse_args(argv)
    p = ClipParams(**{f.name: getattr(args, f.name) for f in fields(ClipParams)})
    out: Path = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix == ".svg":
        from build123d import ExportSVG

        svg = ExportSVG(scale=4, margin=10, line_weight=0.4)
        svg.add_shape(profile(p))
        for i, tube in enumerate(p.tube_list):
            q = PROFILES[tube]
            svg.add_shape(q.section().moved(Location((p.rail_x(i), p.out_h / 2 - p.wall - p.clearance - q.height / 2))))
        svg.write(str(out))
    elif out.suffix == ".step":
        from build123d import export_step

        export_step(clip(p), str(out))
    else:
        export_stl(clip(p), str(out), tolerance=0.01, angular_tolerance=0.1)
    print(f"-> {out}")
    print(p.report())


if __name__ == "__main__":
    main()
