"""Snap-on clamp for one or more IKEA FRAMFUSIG curtain rails side by side,
gripping from above.

Each rail sits in a thin C of uniform ``wall`` that follows the rail's
section at a small ``clearance``, open at the bottom. The C's two lips reach
``lip_depth`` below the start of the rail's lower rounds, so the opening is
narrower than the rail by an interference and the rail has to be pushed up
into the C: each half flexes outward as a curved cantilever and springs back
to trap the rail. The underside stays open for the gliders and the curtain.

The Cs hang from a flat top plate (``plate_t`` thick) that spans them at
``spacing`` centre to centre. The plate carries a male dovetail ridge on
top that slides into the female groove in the underside of a beam clamp
(see beam_clamp.py). The ridge runs along the beam, which is parallel to
the rails, so it lies along the rails in the profile (``dovetail_along =
"rails"``); ``"beam"`` runs it across the plate instead for a beam that
crosses the rails. The beam clamp holds the clearance, so the ridge is
the nominal size. Each C hangs by
a short neck (``stem_w`` x ``stem_h``) on its flat top, filleted into both
the plate and the C, so the transitions are smooth while the C's rounds,
where the flex lives, stay free. Each C can fit the inner or the outer tube
(``tubes``), since the rail is telescopic.

The profile is drawn in the XY plane with the rail's axis along Z, the slot
facing -Y, and the section centred on X = 0, Y = 0; it is extruded ``length``
along the rail. Print it with the profile flat on the bed.

Usage:
    python rail_clamp.py -o clip.stl [--tube outer] [--wall 1.2] [--lip_depth 2.5] ...
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
    FontStyle,
    Plane,
    Polygon,
    Text,
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
    # Thickness of the C. Grip scales with its cube: 1.2 mm gripped too
    # weakly on curtains, 2.0 holds about 4.6x harder. The rail is rolled in.
    wall: float = 2.0
    # Width of the opening between the lip tips. The lips follow the rail's
    # lower rounds down until the cavity is this wide, or, if this is narrower
    # than the rail's flat underside, along the underside to this width. The
    # rail is wider than this by the interference and must be pushed in.
    opening: float = 10.0
    # Insertion stress below this multiple of the material's strength is
    # refused; between it and 1.5x a warning is printed. Printed thin walls
    # have proved more compliant than the cantilever model, so 1.0 is usable.
    min_safety: float = 0.0
    # Each lip ends by curling outward, away from the rail, on this radius
    # (to the wall's centreline) through this many degrees, then a full
    # round: no edge faces the rail, and the rail rides the convex flare as
    # it rolls in. 0 degrees = a plain rounded end.
    flare_r: float = 2.0
    flare_deg: float = 40.0
    # Extent along the rail.
    length: float = 20.0
    # Thickness of the flat top plate that joins the Cs and carries the ridge.
    plate_t: float = 3.0
    # The beam clamp the plate sits under: its outer width and its elbows'
    # outer radius. The plate is a square-cornered bar exactly as wide as the
    # clamp's flat underside (mate_w - 2 * mate_r), butting squarely against
    # it where the clamp's arcs begin. 0 width = a plate just wide enough
    # for the Cs.
    mate_w: float = 0.0
    mate_r: float = 7.0
    # Radius on the plate's four outer corners: slight, so the butt against
    # the clamp still reads as square.
    corner_r: float = 0.6
    # Male dovetail ridge on the plate's top, mating the beam clamp's female
    # groove (same width, height and flank angle; the groove carries the
    # clearance). Width at the wide (top) end; 0 = none.
    dovetail_w: float = 0.0
    dovetail_h: float = 3.0
    dovetail_angle: float = 12.0
    # "rails": the groove runs along the rails, in the profile (the beam is
    # parallel to the rails). "beam": across the plate, for a beam that
    # crosses the rails.
    dovetail_along: str = "rails"
    # Neck joining each C's flat top to the plate, and the fillet radius at
    # its four concave corners. Neck plus fillets must stay on the C's flat
    # top so the rounds, where the flex lives, are not stiffened.
    stem_w: float = 4.0
    stem_h: float = 2.0
    fillet_r: float = 1.0
    # Material for the compliance report.
    material: str = "pla"
    # ID engraved into the plate on the print's top face (z = length), reading
    # along the plate. Empty disables. Coupons must carry one.
    label: str = ""
    label_depth: float = 0.4
    label_size: float = 2.2

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
    def cs_w(self) -> float:
        """Width the Cs themselves span."""
        return (self.n_rails - 1) * self.spacing + self.out_w

    @property
    def plate_w(self) -> float:
        return self.mate_w - 2 * self.mate_r if self.mate_w > 0 else self.cs_w

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
        if self.flare_r < 0 or not 0 <= self.flare_deg <= 90:
            raise ValueError("flare_r must be non-negative and flare_deg between 0 and 90")
        if self.flare_deg > 0 and self.flare_r < self.wall / 2:
            raise ValueError("flare_r must be at least half the wall so the flare's inner surface has a positive radius")
        if self.opening < self.rail.slot_w + 1.0:
            raise ValueError("opening is too narrow: the lips would crowd the glider slot")
        if self.plate_t <= 0:
            raise ValueError("plate_t must be positive")
        if self.dovetail_w < 0 or self.dovetail_h < 0:
            raise ValueError("dovetail dimensions must be non-negative")
        if self.dovetail_w > 0:
            if self.dovetail_along not in ("beam", "rails"):
                raise ValueError('dovetail_along must be "beam" or "rails"')
            if not 0 < self.dovetail_angle < 45:
                raise ValueError("dovetail_angle must be between 0 and 45 degrees from vertical")
            if self.dovetail_w - 2 * self.dovetail_h * math.tan(math.radians(self.dovetail_angle)) < 2:
                raise ValueError("dovetail neck is too narrow: lower dovetail_h or dovetail_angle")
            if self.dovetail_along == "rails" and self.dovetail_w + 2 > self.plate_w:
                raise ValueError("the plate is too narrow for the dovetail ridge along the rails")
            if self.dovetail_along == "beam" and self.dovetail_w + 2 > self.length:
                raise ValueError(
                    f"length {self.length} is too short for a {self.dovetail_w} mm ridge across the plate"
                )
        if self.mate_w < 0 or self.mate_r < 0:
            raise ValueError("mate_w and mate_r must be non-negative")
        if not 0 <= self.corner_r <= self.plate_t / 2:
            raise ValueError(f"corner_r must be between 0 and half the plate thickness ({self.plate_t / 2})")
        if self.mate_w > 0:
            if self.mate_r > self.mate_w / 2:
                raise ValueError("mate_r must not exceed half of mate_w")
            flat = self.mate_w - 2 * self.mate_r
            need = (self.n_rails - 1) * self.spacing + self.stem_w + 2 * self.fillet_r
            if flat < need:
                raise ValueError(
                    f"the clamp's flat underside ({flat:.1f} mm) cannot carry the necks ({need:.1f} mm): reduce spacing"
                )
            if self.dovetail_w > 0 and self.dovetail_along == "rails" and self.dovetail_w + 2 > flat:
                raise ValueError("the dovetail ridge must fit on the clamp's flat underside")
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
        if self.label and self.label_depth >= self.length:
            raise ValueError("label_depth must be less than length")
        # lips wrapped under the rail cannot snap over it; the clamp slides on
        # from the rail's end instead, so insertion stress does not apply
        if not self.on_underside and self.flex().safety_vs_strength < self.min_safety:
            raise ValueError(
                f"insertion stress {self.flex().stress:.0f} MPa exceeds the material's strength / min_safety: "
                "thin the wall, widen the opening or lower min_safety"
            )


def _dovetail_ridge(p: ClipParams, x0: float, y_top: float, clearance: float = 0.0) -> Sketch:
    """The male ridge's cross-section: a trapezoid with its narrow neck on the
    plate's top y_top and its wide end dovetail_h above, centred on x0, in
    whatever plane it is drawn in. A clearance grows it (for the socket)."""
    t = math.tan(math.radians(p.dovetail_angle))
    hh = p.dovetail_h + clearance
    wt = p.dovetail_w + 2 * clearance
    wn = wt - 2 * hh * t
    pts = [(x0 - wn / 2, y_top - 1e-3), (x0 + wn / 2, y_top - 1e-3), (x0 + wt / 2, y_top + hh), (x0 - wt / 2, y_top + hh)]
    return _sk(Polygon(*pts, align=None))


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
        # the lip's centreline end P, and the radial (outward) direction there
        dx, dy = sign * math.cos(phi), -math.sin(phi)
        px, py = cx + r_mid * dx, cy + r_mid * dy
        if q.flare_deg > 0 and q.flare_r > 0:
            # flare: an arc of the wall curling outward about a centre F beyond
            # the outer surface, starting tangent to the C at P
            R, theta = q.flare_r, math.radians(q.flare_deg)
            fx, fy = px + R * dx, py + R * dy
            a0 = math.atan2(py - fy, px - fx)
            step = theta / 12 * (1 if sign > 0 else -1)
            angles = [a0 + step * k for k in range(13)]
            wedge = Polygon((fx, fy), *[(fx + (R + q.wall) * math.cos(a), fy + (R + q.wall) * math.sin(a)) for a in angles], align=None)
            if sign < 0:
                wedge = Polygon((fx, fy), *[(fx + (R + q.wall) * math.cos(a), fy + (R + q.wall) * math.sin(a)) for a in reversed(angles)], align=None)
            annulus = _sk(Circle(R + q.wall / 2).moved(Location((fx, fy))) - Circle(R - q.wall / 2).moved(Location((fx, fy))))
            c = _sk(c + _sk(annulus & wedge))
            ex, ey = fx + R * math.cos(angles[-1]), fy + R * math.sin(angles[-1])
            c = _sk(c + Circle(q.wall / 2).moved(Location((ex, ey))))
        else:
            c = _sk(c + _sk(Circle(q.wall / 2).moved(Location((px, py))) - cav))
    return c


def cavity(p: ClipParams, i: int = 0) -> Sketch:
    q = PROFILES[p.tube_list[i]]
    return RectangleRounded(q.width + 2 * p.clearance, q.height + 2 * p.clearance, q.radius + p.clearance).moved(
        Location((p.rail_x(i), 0))
    )


def clips_profile(p: ClipParams, y_attach: float) -> Sketch:
    """The Cs and their necks, with every neck's top at y = y_attach (the
    underside of whatever they hang from) and the rails centred on x = 0.
    Fillets go on the neck-to-C corners; the neck-to-carrier corners are the
    carrier's business."""
    p.validate()
    y_top = y_attach - p.stem_h  # top of the largest C
    parts = None
    for i, tube in enumerate(p.tube_list):
        c = _c_profile(p, tube)
        q = PROFILES[tube]
        c_top = q.height / 2 + p.clearance + p.wall
        c = c.moved(Location((p.rail_x(i), y_top - c_top)))
        parts = c if parts is None else _sk(parts + c)
    out = parts
    for i in range(p.n_rails):
        x = p.rail_x(i)
        neck = Rectangle(p.stem_w, p.stem_h + 0.02, align=(Align.CENTER, Align.MIN)).moved(Location((x, y_top - 0.01)))
        out = _sk(out + neck)
        for sign in (-1, 1):
            x_c = x + sign * p.stem_w / 2
            for y_c, up in ((y_top, +1), (y_attach, -1)):
                if p.fillet_r <= 0:
                    continue
                x0, x1 = sorted((x_c, x_c + sign * p.fillet_r))
                y0, y1 = sorted((y_c, y_c + up * p.fillet_r))
                square = Rectangle(x1 - x0, y1 - y0, align=(Align.MIN, Align.MIN)).moved(Location((x0, y0)))
                circle = Circle(p.fillet_r).moved(Location((x_c + sign * p.fillet_r, y_c + up * p.fillet_r)))
                out = _sk(out + _sk(square - circle))
    return out


def profile(p: ClipParams) -> Sketch:
    """The clamp's cross-section: the Cs and necks under a common top plate."""
    p.validate()
    y_top = p.out_h / 2  # top of the largest C
    y_plate = y_top + p.stem_h
    plate = Rectangle(p.plate_w, p.plate_t, align=(Align.CENTER, Align.MIN)).moved(Location((0, y_plate)))
    out = _sk(clips_profile(p, y_plate) + plate)
    # male dovetail along the rails: a ridge in the profile
    if p.dovetail_w > 0 and p.dovetail_along == "rails":
        out = _sk(out + _dovetail_ridge(p, 0.0, y_plate + p.plate_t))
    y_top_plate = y_plate + p.plate_t
    # round the plate's four outer corners slightly (the butt against the
    # clamp stays square in character)
    r = p.corner_r
    if r > 0:
        for sign in (-1, 1):
            x_edge = sign * p.plate_w / 2
            for y_edge, up in ((y_top_plate, -1), (y_plate, +1)):
                cx, cy = x_edge - sign * r, y_edge + up * r
                x0, x1 = sorted((x_edge, cx)); y0, y1 = sorted((y_edge, cy))
                corner = Rectangle(x1 - x0, y1 - y0, align=(Align.MIN, Align.MIN)).moved(Location((x0, y0)))
                out = _sk(_sk(out - corner) + Circle(r).moved(Location((cx, cy))))
    assert len(out.faces()) == 1, "profile did not fuse into a single face"
    return out


def plate_top(p: ClipParams) -> float:
    return p.out_h / 2 + p.stem_h + p.plate_t


def _label_cut(p: ClipParams) -> Part | None:
    if not p.label:
        return None
    y_mid = p.out_h / 2 + p.stem_h + p.plate_t / 2
    size = min(p.label_size, p.plate_t - 0.8)
    plane = Plane(origin=(0, y_mid, p.length), x_dir=(1, 0, 0), z_dir=(0, 0, 1))
    text = plane * Text(p.label, font_size=size, font_style=FontStyle.BOLD)
    return extrude(text, amount=-p.label_depth)


def clip(p: ClipParams) -> Part:
    body = extrude(profile(p), amount=p.length, dir=(0, 0, 1))
    cut = _label_cut(p)
    if cut is not None:
        body = body - cut
    if p.dovetail_w > 0 and p.dovetail_along == "beam":
        # ridge across the plate: drawn in the (z, y) plane and extruded along x
        ridge = extrude(_zy_plane(p.plate_w / 2) * _dovetail_ridge(p, p.length / 2, plate_top(p)), amount=p.plate_w, dir=(-1, 0, 0))
        body = body + ridge
    return body


def _zy_plane(x: float) -> Plane:
    """A plane at world x whose local x is world z and local y is world y
    (normal -x, so the right-hand rule keeps y pointing up)."""
    return Plane(origin=(x, 0, 0), x_dir=(0, 0, 1), z_dir=(-1, 0, 0))


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


def beam_socket(p: ClipParams, clearance: float = 0.15, length: float = 30.0) -> Part:
    """A block standing in for the beam clamp's base, with the female groove
    (grown by the clearance) cut up into its underside, seated on the ridge
    with the clearance under the base. For checking the fit: it runs along
    z for "rails", along x for "beam"."""
    y_base = plate_top(p) + clearance  # underside of the beam clamp
    depth = p.dovetail_h + clearance + 3
    if p.dovetail_along == "rails":
        block = Rectangle(p.dovetail_w + 10, depth, align=(Align.CENTER, Align.MIN)).moved(Location((0, y_base)))
        sec = _sk(block - _dovetail_ridge(p, 0.0, y_base, clearance))
        return extrude(sec.moved(Location((0, 0, -5))), amount=p.length + 10, dir=(0, 0, 1))
    zc = p.length / 2
    block = Rectangle(p.dovetail_w + 10, depth, align=(Align.CENTER, Align.MIN)).moved(Location((zc, y_base)))
    sec = _sk(block - _dovetail_ridge(p, zc, y_base, clearance))
    return extrude(_zy_plane(length / 2) * sec, amount=length, dir=(-1, 0, 0))


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
