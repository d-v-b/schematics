"""Beam flex: two identical C halves that snap together around a rectangular
beam using the arms' own compliance. The third option, after the ratchet
(beam_wrap.py) and the bolt (beam_bolt.py).

Each half is the clamp profile with straight arms flush against the beam and
reaching half the beam height. The mating half is rotated 180 degrees about
the beam axis, so at each joint one part's arm is inside (against the beam)
and the other's is outside. There is no jog: over the lap each arm is halved
across the wall. The left arm keeps its OUTER half and carries a row of teeth
on the resulting inner face; the right arm keeps its INNER half and carries a
matching row recessed into its outer face. The halves nest flush, so the
outer profile of the assembly is unbroken.

To assemble, the halves are pushed together and the outside arm flexes
outward by the tooth height to click over the teeth; it then springs back
and, with a small built-in interference (a negative joint_clearance), stays
pressed against the inside arm so the teeth cannot walk out. The ratchet
closes at whichever tooth the halves reach. No hardware.

The arm is a cantilever of the wall thickness, so the deflection it needs is
cheap: see ``FlexParams.flex_report`` and compliance.py.

Coordinates match beam_clamp.py: the beam's bottom-left inner corner is at
(0, 0), the beam occupies x in [0, inner_w], and the part extends along +z by
``length``.

Usage:
    python beam_flex.py -o out.stl [--wall 5] [--joint_clearance -0.3] ...
    python beam_flex.py -o coupon.stl --coupon 1   # just the joint, for fit tests
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from build123d import (
    Polygon,
    Circle,
    FontStyle,
    Location,
    Part,
    Plane,
    Sketch,
    Text,
    extrude,
    mirror,
)

from beam_clamp import _elbow, _sk, run_cli, seat_offset, top_face_label, validate_dovetail, with_base_dovetail
from beam_wrap import _rect, _teeth_row
from compliance import MATERIALS, ArmFlex


@dataclass(frozen=True)
class FlexParams:
    """Every dimension of one half, in millimetres."""

    beam_w: float = 53.6
    beam_h: float = 206.5
    clearance: float = 0.3
    wall: float = 5.0
    length: float = 50.0
    fillet_r: float = 2.0
    # --- joint ---
    # Height of the overlap between the two laps.
    lap_len: float = 30.0
    # Gap between the nested lap faces. Negative = interference: the outside
    # arm is held flexed outward by that much and presses the teeth together.
    joint_clearance: float = -0.3
    # Gap between the lap ends and the other half's shoulders at the nominal
    # position, beyond the cinch travel.
    tip_gap: float = 0.5
    # Height over which each arm tapers from the full wall down to its lap
    # slab, just below the lap. A smooth taper instead of a step spreads the
    # bending where the arm changes section, which is where it would break.
    taper_len: float = 8.0
    # Ratchet teeth: protrusion, pitch, count, distance from the tab tip down
    # to the top of the row, and how many teeth the joint may close past or
    # stop short of nominal.
    tooth_h: float = 2.0
    tooth_pitch: float = 4.0
    teeth_from_tip: float = 2.0
    cinch_teeth: int = 1
    slack_teeth: int = 1
    # Material for the compliance report.
    material: str = "pla"
    # Female dovetail groove in the underside of the base, running along the
    # beam (see beam_clamp.py). Width at the wide end; 0 = none.
    dovetail_w: float = 0.0
    dovetail_h: float = 3.0
    dovetail_angle: float = 12.0
    dovetail_clearance: float = -0.025
    label: str = ""
    label_depth: float = 0.4
    label_size: float = 5.0
    coupon: int = 0
    coupon_stub: float = 25.0

    # ----- derived -----
    @property
    def inner_w(self) -> float:
        return self.beam_w + self.clearance

    @property
    def seat(self) -> float:
        return seat_offset(self.fillet_r, self.clearance)

    @property
    def span_h(self) -> float:
        """Distance between the two halves' inner base faces when assembled."""
        return self.beam_h + 2 * self.seat

    @property
    def half(self) -> float:
        """Thickness of each lap (half the wall, less half the clearance)."""
        return self.wall / 2 - self.joint_clearance / 2

    @property
    def preload(self) -> float:
        """How far the outside arm is held flexed when assembled."""
        return max(0.0, -self.joint_clearance)

    @property
    def slab(self) -> float:
        """Thickness of each lap's solid slab, from its outer surface to the
        root line of its teeth. The parting plane runs through the middle of
        the tooth height, so both laps are identical: slab plus teeth."""
        return self.half - self.tooth_h / 2

    @property
    def tip_r(self) -> float:
        return self.slab / 2

    @property
    def cinch_travel(self) -> float:
        return self.cinch_teeth * self.tooth_pitch

    @property
    def lap_y0(self) -> float:
        """Shoulder of the left (outside) arm: where its lap begins."""
        return (self.span_h - self.lap_len) / 2

    @property
    def outer_arm_len(self) -> float:
        """Reach of the left arm (its lap tip)."""
        return self.lap_y0 + self.lap_len

    @property
    def inner_step(self) -> float:
        """Where the right arm thins to its inner half: below the point where
        the other half's outside lap tip arrives, even when cinched."""
        return self.span_h - self.outer_arm_len - self.tip_gap - self.cinch_travel

    @property
    def inner_arm_len(self) -> float:
        """Reach of the right arm: clears the other half's shoulder when cinched."""
        return self.span_h - self.lap_y0 - self.tip_gap - self.cinch_travel

    @property
    def n_tab(self) -> int:
        """Teeth on the tab: as many as fit between the shoulder and the tip
        that the arm's row can still cover at the cinched position (the arm's
        rounded tip, plus tip_gap, ends up just above the shoulder there, so
        the tab's lowest teeth must start above that line)."""
        p = self.tooth_pitch
        n_max = int(math.floor((self.outer_arm_len - self.teeth_from_tip - self.lap_y0) / p + 1e-9))
        for n in range(n_max, 0, -1):
            t0 = self.outer_arm_len - self.teeth_from_tip - n * p
            r0, r1 = self._arm_row_bounds_for(t0)
            # the mating row moves up with slack: its bottom must still cover
            # the tab's lowest tooth at the slackest position
            if r1 > r0 and self.span_h - r1 + self.slack_teeth * p <= t0 + 1e-6:
                return n
        return 0

    @property
    def row_len(self) -> float:
        return self.n_tab * self.tooth_pitch

    @property
    def tab_teeth_y0(self) -> float:
        """Flat face of the lowest tooth on the tab; the row runs from here to
        teeth_from_tip below the tip."""
        return self.outer_arm_len - self.teeth_from_tip - self.row_len

    def _arm_flat(self, m: int) -> float:
        """Flat face of arm tooth m. The phase is set so that, after the 180
        degree rotation, the mating half's arm teeth land flat-to-flat on this
        half's tab teeth at every whole-pitch position."""
        return self.span_h - self.tab_teeth_y0 - m * self.tooth_pitch

    def _arm_row_bounds_for(self, t0: float) -> tuple[float, float]:
        """The arm's toothed span for a tab row starting at t0: every tooth of
        the matching phase that fits between the step and the tip round. No
        empty runs: the teeth go all the way."""
        tip_r = self.tip_r if hasattr(self, "tip_r") else self.wall / 2
        lo, hi = self.inner_step, self.inner_arm_len - tip_r
        p = self.tooth_pitch
        m_lo = math.ceil((self.span_h - t0 - (hi - p)) / p - 1e-9)
        m_hi = math.floor((self.span_h - t0 - lo) / p + 1e-9)
        if m_hi < m_lo:
            return (lo, lo)
        return (self.span_h - t0 - m_hi * p, self.span_h - t0 - m_lo * p + p)

    @property
    def arm_row_bounds(self) -> tuple[float, float]:
        return self._arm_row_bounds_for(self.tab_teeth_y0)

    @property
    def arm_teeth_y0(self) -> float:
        return self.arm_row_bounds[0]

    @property
    def n_arm(self) -> int:
        y0, y1 = self.arm_row_bounds
        return int(round((y1 - y0) / self.tooth_pitch))

    @property
    def recess_y0(self) -> float:
        return self.arm_row_bounds[0]

    @property
    def recess_y1(self) -> float:
        return self.arm_row_bounds[1]

    @property
    def free_arm(self) -> float:
        """Cantilever length from the elbow to the lap."""
        return self.lap_y0 - self.fillet_r

    def flex(self, deflection: float | None = None) -> ArmFlex:
        """Cantilever model of the outside arm. Default deflection: what it
        takes to click over the teeth (tooth height plus any interference)."""
        if deflection is None:
            deflection = self.tooth_h + self.preload
        return ArmFlex(self.wall, self.length, self.free_arm, deflection, MATERIALS[self.material])

    def flex_report(self) -> str:
        click = self.flex()
        held = self.flex(self.preload)
        return (
            f"to click over the teeth ({click.deflection:.1f} mm): {click.force:.1f} N, {click.stress:.1f} MPa "
            f"(strength {click.safety_vs_strength:.1f}x)\n"
            f"held flexed by the interference ({held.deflection:.1f} mm): {held.force:.1f} N, {held.stress:.1f} MPa "
            f"(creep limit {held.safety_vs_creep:.1f}x)"
        )

    def validate(self) -> None:
        if self.wall <= 0:
            raise ValueError(f"wall must be positive, got {self.wall}")
        if self.inner_w <= 2 * self.fillet_r:
            raise ValueError(
                f"inner span {self.inner_w} must exceed twice the fillet radius {self.fillet_r}"
            )
        if self.material not in MATERIALS:
            raise ValueError(f"material must be one of {sorted(MATERIALS)}")
        if self.slab < 1.0:
            raise ValueError(
                f"lap slab {self.slab:.2f} mm (half wall less half a tooth) must be at least 1 mm: thin the teeth or thicken the wall"
            )
        if self.tooth_h <= max(0.0, self.joint_clearance):
            raise ValueError("tooth_h must exceed joint_clearance or the teeth never engage")
        if self.tooth_pitch <= 0:
            raise ValueError("tooth_pitch must be positive")
        if self.cinch_teeth < 0:
            raise ValueError("cinch_teeth must be non-negative")
        if self.slack_teeth < 1:
            raise ValueError("slack_teeth must be at least 1")
        tip_r = self.tip_r
        if self.taper_len < 0:
            raise ValueError("taper_len must be non-negative")
        if min(self.lap_y0, self.inner_step) - self.taper_len <= self.fillet_r:
            raise ValueError("taper_len runs into the elbow: shorten it")
        if self.teeth_from_tip < tip_r:
            raise ValueError(f"teeth_from_tip {self.teeth_from_tip} must be at least a quarter wall")
        n_max = int(math.floor((self.outer_arm_len - self.teeth_from_tip - self.lap_y0) / self.tooth_pitch + 1e-9))
        if self.slack_teeth > n_max - 1:
            raise ValueError(f"slack_teeth must leave a tooth engaged: at most {n_max - 1}")
        if self.n_tab < 2:
            raise ValueError("lap_len is too short for a tooth row on the tab")
        if self.n_arm < 1:
            raise ValueError("lap_len is too short for a tooth row on the arm")
        # the arm's toothed span must cover the tab row at every allowed
        # position, from cinched by cinch_teeth to slack by slack_teeth
        p = self.tooth_pitch
        t0, t1 = self.tab_teeth_y0, self.tab_teeth_y0 + self.row_len
        if self.span_h - self.recess_y1 + self.slack_teeth * p > t0 + 1e-6:
            raise ValueError("lap_len is too short for the slack travel: the tab's bottom tooth would leave the arm's row")
        if self.span_h - self.recess_y0 - self.cinch_teeth * p < t1 - 1e-6:
            raise ValueError("lap_len is too short for the cinch travel: the tab's top tooth would leave the arm's row")
        if self.free_arm <= 0:
            raise ValueError("arms are too short for the lap")
        if self.label and self.label_depth >= self.wall:
            raise ValueError(f"label_depth {self.label_depth} must be less than wall {self.wall}")
        validate_dovetail(self)


def _taper(x_full_edge: float, x_slab_edge: float, x_fixed: float, y0: float, y1: float) -> Sketch:
    """The transition from the full wall to the lap slab: a trapezoid whose
    moving edge goes from x_full_edge at y0 to x_slab_edge at y1 while the
    other edge stays at x_fixed."""
    pts = [(x_fixed, y0), (x_full_edge, y0), (x_slab_edge, y1), (x_fixed, y1)]
    if x_fixed > x_full_edge:  # keep the winding counter-clockwise
        pts = [(x_full_edge, y0), (x_fixed, y0), (x_fixed, y1), (x_slab_edge, y1)]
    return _sk(Polygon(*pts, align=None))


def _outer_arm(p: FlexParams) -> Sketch:
    """Left arm: full wall to the shoulder, then the lap slab on the outside
    with its teeth reaching inward, and a rounded tip."""
    w, t, tip_r = p.wall, p.slab, p.tip_r
    full = _rect(-w, p.fillet_r, 0, p.lap_y0 - p.taper_len)
    # the inner face tapers from the beam side to the slab face
    taper = _taper(0.0, -w + t, -w, p.lap_y0 - p.taper_len, p.lap_y0)
    lap = _rect(-w, p.lap_y0, -w + t, p.outer_arm_len - tip_r)
    tip = Circle(tip_r).moved(Location((-w + tip_r, p.outer_arm_len - tip_r)))
    teeth = _teeth_row(-w + t, p.tab_teeth_y0, p, direction=+1, n=p.n_tab)
    return _sk(_sk(full + taper) + _sk(lap + tip + teeth))


def _inner_arm(p: FlexParams) -> Sketch:
    """Right arm (built on the left, mirrored later): full wall to inner_step,
    then the lap slab on the beam side with its teeth reaching outward, and a
    rounded tip. The same slab and teeth as the outer arm, mirrored about the
    parting plane, so the two laps are identical in thickness."""
    w, t, tip_r = p.wall, p.slab, p.tip_r
    full = _rect(-w, p.fillet_r, 0, p.inner_step - p.taper_len)
    # the outer face tapers from the full wall to the slab face
    taper = _taper(-w, -t, 0.0, p.inner_step - p.taper_len, p.inner_step)
    lap = _rect(-t, p.inner_step, 0, p.inner_arm_len - tip_r)
    tip = Circle(tip_r).moved(Location((-tip_r, p.inner_arm_len - tip_r)))
    teeth = _teeth_row(-t, p.arm_teeth_y0, p, direction=-1, n=p.n_arm)
    return _sk(_sk(full + taper) + _sk(lap + tip + teeth))


def profile(p: FlexParams) -> Sketch:
    p.validate()
    base = _rect(p.fillet_r, -p.wall, p.inner_w - p.fillet_r, 0)
    left = _sk(_elbow(p) + _outer_arm(p))
    right = _sk(mirror(_sk(_elbow(p) + _inner_arm(p)), about=Plane.YZ.offset(p.inner_w / 2)))
    merged = with_base_dovetail(_sk(base + left + right), p)
    if p.coupon:
        band = _rect(-2 * p.beam_w, min(p.lap_y0, p.inner_step) - p.taper_len - p.coupon_stub, 3 * p.beam_w, p.span_h)
        merged = _sk(merged & band)
        assert len(merged.faces()) == 2, "coupon should be the two joint pieces"
    else:
        assert len(merged.faces()) == 1, "profile did not fuse into a single face"
    return merged


def _label_cut(p: FlexParams) -> Part | None:
    if not p.label:
        return None
    if p.coupon:
        # coupons are short along the beam: engrave the ID on the top face,
        # along the left arm's stub
        return top_face_label(p, -p.wall / 2, min(p.lap_y0, p.inner_step) - p.taper_len - p.coupon_stub / 2, along="y", size=max(1.5, p.wall - 1.5))
    if p.length < p.label_size + 1.0:
        # too short along the beam for text on the base's outer face: engrave
        # it on the top face instead, across the base
        return top_face_label(p, p.inner_w / 2, -p.wall / 2, along="x", size=max(1.5, p.wall - 1.5))
    face_plane = Plane(
        origin=(p.inner_w / 2, -p.wall, p.length / 2), x_dir=(1, 0, 0), z_dir=(0, -1, 0)
    )
    text = face_plane * Text(p.label, font_size=p.label_size, font_style=FontStyle.BOLD)
    return extrude(text, amount=-p.label_depth)


def half(p: FlexParams) -> Part:
    body = extrude(profile(p), amount=p.length, dir=(0, 0, 1))
    cut = _label_cut(p)
    if cut is not None:
        body = body - cut
    return body


def mate_location(p: FlexParams) -> Location:
    """Rotate 180 degrees about the beam axis through the centre of the span."""
    return Location((p.inner_w / 2, p.span_h / 2, 0), (0, 0, 180)) * Location(
        (-p.inner_w / 2, -p.span_h / 2, 0)
    )


def assembly(p: FlexParams):
    """Both halves in the assembled position, as (lower, upper). With a
    negative joint_clearance the as-printed laps overlap by the interference;
    in the real part the outside arm flexes out by that much."""
    lower = half(p)
    return lower, lower.moved(mate_location(p))


def export_assembly_svg(p: FlexParams, path: str) -> None:
    from build123d import ExportSVG

    lower = profile(p)
    upper = lower.moved(mate_location(p))
    svg = ExportSVG(scale=2, margin=10, line_weight=0.5)
    svg.add_shape(lower)
    svg.add_shape(upper)
    svg.write(path)


def main(argv: list[str] | None = None) -> None:
    import sys

    run_cli(FlexParams, __doc__, half, profile, argv)
    # echo the compliance numbers alongside the file
    from dataclasses import fields

    from beam_clamp import make_cli

    args = make_cli(FlexParams, __doc__).parse_args(argv if argv is not None else sys.argv[1:])
    p = FlexParams(**{f.name: getattr(args, f.name) for f in fields(FlexParams)})
    print(p.flex_report())


if __name__ == "__main__":
    main()
