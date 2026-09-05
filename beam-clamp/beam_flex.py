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

from dataclasses import dataclass

from build123d import (
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

from beam_clamp import _elbow, _sk, run_cli, seat_offset
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
    # Height of the overlap between the two half-thickness laps.
    lap_len: float = 24.0
    # Gap between the nested lap faces. Negative = interference: the outside
    # arm is held flexed outward by that much and presses the teeth together.
    joint_clearance: float = -0.3
    # Gap between the lap ends and the other half's shoulders at the nominal
    # position, beyond the cinch travel.
    tip_gap: float = 0.5
    # Fillet radius at the re-entrant corner where each arm steps down to its
    # lap: the arm bends there, so it should not be a sharp corner. Must not
    # exceed the lap tips' round (a quarter wall) so the tips still nest.
    shoulder_r: float = 1.0
    # Ratchet teeth: protrusion, pitch, count, distance from the tab tip down
    # to the top of the row, and how many teeth the joint may close past or
    # stop short of nominal.
    tooth_h: float = 0.8
    tooth_pitch: float = 2.0
    n_teeth: int = 4
    teeth_from_tip: float = 2.0
    cinch_teeth: int = 1
    slack_teeth: int = 2
    # Material for the compliance report.
    material: str = "pla"
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
    def recess_depth(self) -> float:
        """The arm-side recess is deeper than the teeth by the preload, so the
        lap faces, not the tooth tips, carry it."""
        return self.tooth_h + self.preload

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
    def row_len(self) -> float:
        return self.n_teeth * self.tooth_pitch

    @property
    def tab_teeth_y0(self) -> float:
        """Flat face of the lowest tooth on the left arm's lap."""
        return self.outer_arm_len - self.teeth_from_tip - self.row_len

    @property
    def arm_teeth_y0(self) -> float:
        """Flat face of the lowest tooth on the right arm's lap, placed so the
        mating half's row lands flat-to-flat on this half's tab row."""
        return self.span_h - self.tab_teeth_y0 - (self.n_teeth - 1) * self.tooth_pitch

    @property
    def recess_y0(self) -> float:
        return self.arm_teeth_y0 - (1 + self.cinch_teeth) * self.tooth_pitch

    @property
    def recess_y1(self) -> float:
        return self.arm_teeth_y0 + self.row_len + (self.slack_teeth - 1) * self.tooth_pitch

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
        if self.half - self.recess_depth < 0.5:
            raise ValueError(
                f"half wall {self.half:.2f} must exceed the recess depth {self.recess_depth:.2f} by at least 0.5 mm"
            )
        if self.tooth_h <= max(0.0, self.joint_clearance):
            raise ValueError("tooth_h must exceed joint_clearance or the teeth never engage")
        if self.n_teeth < 1 or self.tooth_pitch <= 0:
            raise ValueError("need at least one tooth with a positive pitch")
        if self.cinch_teeth < 0:
            raise ValueError("cinch_teeth must be non-negative")
        if not 1 <= self.slack_teeth <= self.n_teeth - 1:
            raise ValueError("slack_teeth must be between 1 and n_teeth - 1")
        tip_r = self.half / 2
        if not 0 <= self.shoulder_r <= tip_r:
            raise ValueError(f"shoulder_r must be between 0 and the tip round {tip_r:.2f}")
        if self.teeth_from_tip < tip_r:
            raise ValueError(f"teeth_from_tip {self.teeth_from_tip} must be at least a quarter wall")
        if self.tab_teeth_y0 - self.tooth_pitch < self.lap_y0:
            raise ValueError("lap_len is too short for the tooth row (tab side)")
        if self.recess_y1 > self.inner_arm_len - tip_r:
            raise ValueError("lap_len is too short for the tooth row (arm side)")
        if self.recess_y0 < self.inner_step:
            raise ValueError("cinch_teeth * tooth_pitch must not exceed teeth_from_tip + tip_gap")
        if self.free_arm <= 0:
            raise ValueError("arms are too short for the lap")
        if self.label and self.label_depth >= self.wall:
            raise ValueError(f"label_depth {self.label_depth} must be less than wall {self.wall}")


def _shoulder_fillet(x_c: float, y_c: float, r: float, dx: int) -> Sketch | None:
    """Material that rounds a re-entrant corner at (x_c, y_c) whose free
    space lies toward +y and toward dx (+1 or -1) in x: a square in that
    quadrant minus the circle tangent to both faces."""
    if r <= 0:
        return None
    x0, x1 = sorted((x_c, x_c + dx * r))
    square = _rect(x0, y_c, x1, y_c + r)
    return _sk(square - Circle(r).moved(Location((x_c + dx * r, y_c + r))))


def _outer_arm(p: FlexParams) -> Sketch:
    """Left arm: full wall to the shoulder, then the outer half only, with a
    rounded tip and a tooth row on its inner face."""
    w, h = p.wall, p.half
    tip_r = h / 2
    full = _rect(-w, p.fillet_r, 0, p.lap_y0)
    lap = _rect(-w, p.lap_y0, -w + h, p.outer_arm_len - tip_r)
    tip = Circle(tip_r).moved(Location((-w + tip_r, p.outer_arm_len - tip_r)))
    teeth = _teeth_row(-w + h, p.tab_teeth_y0, p, direction=+1)
    arm = _sk(full + lap + tip + teeth)
    fillet = _shoulder_fillet(-w + h, p.lap_y0, p.shoulder_r, dx=+1)
    return arm if fillet is None else _sk(arm + fillet)


def _inner_arm(p: FlexParams) -> Sketch:
    """Right arm (built on the left, mirrored later): full wall to inner_step,
    then the inner half only, with a rounded tip and a tooth row recessed
    into its outer face."""
    w, h = p.wall, p.half
    tip_r = h / 2
    full = _rect(-w, p.fillet_r, 0, p.inner_step)
    lap = _rect(-h, p.inner_step, 0, p.inner_arm_len - tip_r)
    tip = Circle(tip_r).moved(Location((-tip_r, p.inner_arm_len - tip_r)))
    recess = _rect(-h, p.recess_y0, -h + p.recess_depth, p.recess_y1)
    # teeth reach back out to the face, so their crests meet the mating tab
    teeth = _teeth_row(-h + p.recess_depth, p.arm_teeth_y0, p, direction=-1, height=p.recess_depth)
    body = _sk(_sk(full + lap + tip) - recess)  # keep it a Sketch: Face + Sketch does not fuse
    arm = _sk(body + teeth)
    fillet = _shoulder_fillet(-h, p.inner_step, p.shoulder_r, dx=-1)
    return arm if fillet is None else _sk(arm + fillet)


def profile(p: FlexParams) -> Sketch:
    p.validate()
    base = _rect(p.fillet_r, -p.wall, p.inner_w - p.fillet_r, 0)
    left = _sk(_elbow(p) + _outer_arm(p))
    right = _sk(mirror(_sk(_elbow(p) + _inner_arm(p)), about=Plane.YZ.offset(p.inner_w / 2)))
    merged = _sk(base + left + right)
    if p.coupon:
        band = _rect(-2 * p.beam_w, min(p.lap_y0, p.inner_step) - p.coupon_stub, 3 * p.beam_w, p.span_h)
        merged = _sk(merged & band)
        assert len(merged.faces()) == 2, "coupon should be the two joint pieces"
    else:
        assert len(merged.faces()) == 1, "profile did not fuse into a single face"
    return merged


def _label_cut(p: FlexParams) -> Part | None:
    if not p.label or p.coupon:
        return None
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
