"""Beam wrap: two identical C halves that snap together around a rectangular
beam.

Each half is the beam clamp profile with arms reaching half the beam height.
The left arm jogs outward and ends in a tab with a row of sawtooth teeth on
its inner face; the right arm stays flush against the beam and carries a
matching row cut into its outer face. Rotate a second copy 180 degrees about
the beam axis and its left tab lands outside the first copy's right arm (and
vice versa): the rows ratchet past each other on assembly and lock on their
flat faces, so the joint holds in tension and closes at whichever tooth the
halves reach.

Coordinates match beam_clamp.py: the beam's bottom-left inner corner is at
(0, 0), the beam occupies x in [0, inner_w], y in [0, beam_h]. The joint is
centred at y = beam_h / 2.

Usage:
    python beam_wrap.py -o out.stl [--wall 3] [--joint_clearance 0.25] ...
    python beam_wrap.py -o coupon.stl --coupon 1   # just the joint, for fit tests
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from build123d import (
    Align,
    Circle,
    FontStyle,
    Location,
    Part,
    Plane,
    Polygon,
    Rectangle,
    Sketch,
    Text,
    extrude,
    mirror,
)

from beam_clamp import _elbow, _sk, run_cli, seat_offset, top_face_label, validate_dovetail, with_base_dovetail


@dataclass(frozen=True)
class WrapParams:
    """Every dimension of one half, in millimetres."""

    # Beam cross-section.
    beam_w: float = 53.6
    beam_h: float = 206.5
    # Extra inner span beyond beam_w. Negative = interference at the walls.
    clearance: float = 0.3
    # Wall thickness of base and arms.
    wall: float = 3.0
    # Extrusion along the beam.
    length: float = 40.0
    # Inner fillet radius at each corner. Outer radius = fillet_r + wall.
    fillet_r: float = 2.0
    # Tension bump on each arm's inner face: height (0 disables), forming
    # circle radius, and height above the inner base face.
    bump_h: float = 0.6
    bump_r: float = 4.0
    bump_y: float = 60.0
    # --- joint ---
    # Height of the overlap between the outer tab and the inner arm.
    lap_len: float = 30.0
    # Gap between the outer tab's inner face and the inner arm's outer face.
    joint_clearance: float = 0.25
    # Height over which the left arm jogs outward. 0 = auto (about 27 deg).
    jog_len: float = 0.0
    # Gap between the inner arm's tip and the start of the other half's jog at
    # the nominal position, beyond the cinch travel (cinch_teeth * tooth_pitch).
    tip_gap: float = 0.5
    # Ratchet teeth: protrusion of each tooth from the face it sits on, pitch
    # along the arm, number of teeth, and distance from the tab tip down to
    # the top of the row.
    tooth_h: float = 1.5
    tooth_pitch: float = 4.0
    teeth_from_tip: float = 2.0
    # How many teeth the joint can close beyond the nominal all-engaged
    # position (for a beam slightly shorter than beam_h), and how many it can
    # stop short by (a taller beam; n_teeth - slack_teeth stay engaged).
    # Both cost lap length.
    cinch_teeth: int = 1
    slack_teeth: int = 1
    # Label engraved on the outer face of the base. Empty disables.
    # Female dovetail groove in the underside of the base, running along the
    # beam (see beam_clamp.py). Width at the wide end; 0 = none.
    dovetail_w: float = 0.0
    dovetail_h: float = 3.0
    dovetail_angle: float = 12.0
    dovetail_clearance: float = -0.025
    label: str = ""
    label_depth: float = 0.4
    label_size: float = 5.0
    # Coupon mode: 1 keeps only a band around the joint (see coupon_stub).
    coupon: int = 0
    # Height of plain arm kept below the jog / below the teeth in coupon mode.
    coupon_stub: float = 25.0

    # ----- derived -----
    @property
    def inner_w(self) -> float:
        return self.beam_w + self.clearance

    @property
    def seat(self) -> float:
        """Gap between a base's inner face and the beam, set by the fillets."""
        return seat_offset(self.fillet_r, self.clearance)

    @property
    def span_h(self) -> float:
        """Distance between the two halves' inner base faces when assembled:
        the beam plus the seat gap at each end."""
        return self.beam_h + 2 * self.seat

    @property
    def jog(self) -> float:
        """Outward offset of the tab relative to the arm."""
        return self.wall + self.joint_clearance

    @property
    def jog_height(self) -> float:
        return self.jog_len if self.jog_len > 0 else 2 * self.jog

    @property
    def lap_y0(self) -> float:
        """Bottom of the lap region (joint centred on the beam)."""
        return (self.span_h - self.lap_len) / 2

    @property
    def outer_arm_len(self) -> float:
        """Reach of the left arm including its tab."""
        return self.lap_y0 + self.lap_len

    @property
    def cinch_travel(self) -> float:
        return self.cinch_teeth * self.tooth_pitch

    @property
    def inner_step(self) -> float:
        """Lowest point of the right arm that can carry teeth: below the lap
        it only faces the other half's jog, so this is just a sensible floor."""
        return self.lap_y0 - self.jog_height

    @property
    def inner_arm_len(self) -> float:
        """Reach of the right arm: it must stop short of the other half's jog
        even when the joint is cinched fully."""
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
        tip_r = self.half / 2 if hasattr(self, "half") else self.wall / 2
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

    def validate(self) -> None:
        if self.wall <= 0:
            raise ValueError(f"wall must be positive, got {self.wall}")
        if self.inner_w <= 2 * self.fillet_r:
            raise ValueError(
                f"inner span {self.inner_w} must exceed twice the fillet radius {self.fillet_r}"
            )
        if self.joint_clearance < 0:
            raise ValueError("joint_clearance must be non-negative")
        if self.tooth_h <= self.joint_clearance:
            raise ValueError(
                f"tooth_h {self.tooth_h} must exceed joint_clearance {self.joint_clearance} or the teeth never engage"
            )
        if self.tooth_h >= self.wall:
            raise ValueError(f"tooth_h {self.tooth_h} must be less than wall {self.wall}")
        if self.tooth_pitch <= 0:
            raise ValueError("tooth_pitch must be positive")
        if self.cinch_teeth < 0:
            raise ValueError("cinch_teeth must be non-negative")
        if self.slack_teeth < 1:
            raise ValueError("slack_teeth must be at least 1")
        tip_r = self.wall / 2
        if self.teeth_from_tip < tip_r:
            raise ValueError(f"teeth_from_tip {self.teeth_from_tip} must be at least wall/2")
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
        if self.bump_h > 0 and not (
            self.fillet_r + self.bump_r < self.bump_y < self.lap_y0 - self.jog_height - self.bump_r
        ):
            raise ValueError("bump does not fit on the straight part of the arm")
        if self.label and self.label_depth >= self.wall:
            raise ValueError(f"label_depth {self.label_depth} must be less than wall {self.wall}")
        validate_dovetail(self)


def _rect(x0: float, y0: float, x1: float, y1: float) -> Sketch:
    return Rectangle(x1 - x0, y1 - y0, align=(Align.MIN, Align.MIN)).moved(Location((x0, y0)))


def _bump(p: WrapParams) -> Sketch | None:
    if p.bump_h <= 0:
        return None
    circle = Circle(p.bump_r).moved(Location((p.bump_h - p.bump_r, p.bump_y)))
    clip = _rect(-p.wall, 0, p.bump_r, p.beam_h)
    return _sk(circle & clip)


def _teeth_row(x_face: float, y0: float, p, direction: int, n: int, height: float | None = None) -> Sketch:
    """A row of n sawteeth growing from the vertical line x = x_face in the
    +x direction (direction=+1) or -x (direction=-1). Tooth k has its flat
    face at y0 + k * pitch and a ramp back to the face at y0 + (k + 1) * pitch.
    Teeth stand tooth_h proud of the face unless a height is given."""
    d = direction * (p.tooth_h if height is None else height)
    teeth = []
    for k in range(n):
        pts = [
            (x_face, y0 + k * p.tooth_pitch),
            (x_face + d, y0 + k * p.tooth_pitch),
            (x_face, y0 + (k + 1) * p.tooth_pitch),
        ]
        if direction < 0:
            pts.reverse()  # keep the winding counter-clockwise so the face normal is +Z
        teeth.append(Polygon(*pts, align=None))
    acc = teeth[0]
    for t in teeth[1:]:
        acc = acc + t
    return _sk(acc)


def _outer_arm(p: WrapParams) -> Sketch:
    """Left arm: straight, jog outward, tab with a tooth row, rounded tip."""
    w, tip_r = p.wall, p.wall / 2
    y_jog0 = p.lap_y0 - p.jog_height
    straight = _rect(-w, p.fillet_r, 0, y_jog0)
    jog = Polygon(
        (-w, y_jog0), (0, y_jog0), (-p.jog, p.lap_y0), (-(w + p.jog), p.lap_y0), align=None
    )
    x_tab0, x_tab1 = -(w + p.jog), -p.jog  # outer and inner faces of the tab
    tab = _rect(x_tab0, p.lap_y0, x_tab1, p.outer_arm_len - tip_r)
    tip = Circle(tip_r).moved(Location((x_tab0 + tip_r, p.outer_arm_len - tip_r)))
    # sawteeth on the tab's inner face: flat retention face on the base side,
    # ramp rising to the face on the tip side
    teeth = _teeth_row(x_tab1, p.tab_teeth_y0, p, direction=+1, n=p.n_tab)
    return _sk(straight + jog + tab + tip + teeth)


def _inner_arm(p: WrapParams) -> Sketch:
    """Right arm: flush against the beam, rounded tip, tooth row recessed into
    the outer face."""
    w, tip_r = p.wall, p.wall / 2
    x0, x1 = p.inner_w, p.inner_w + w
    straight = _rect(x0, p.fillet_r, x1, p.inner_arm_len - tip_r)
    tip = Circle(tip_r).moved(Location((x1 - tip_r, p.inner_arm_len - tip_r)))
    # recess the outer face over the full toothed span, then
    # add back the teeth so their crests sit flush with the face: same
    # orientation as the tab's teeth (flat on the base side), which becomes
    # opposing after the rotation
    recess = _rect(x1 - p.tooth_h, p.recess_y0, x1, p.recess_y1)
    teeth = _teeth_row(x1 - p.tooth_h, p.arm_teeth_y0, p, direction=+1, n=p.n_arm)
    return _sk((straight + tip) - recess + teeth)


def profile(p: WrapParams) -> Sketch:
    """The 2D cross-section of one half in the XY plane."""
    p.validate()
    base = _rect(p.fillet_r, -p.wall, p.inner_w - p.fillet_r, 0)
    left = _sk(_elbow(p) + _outer_arm(p))
    right = _sk(mirror(_elbow(p), about=Plane.YZ.offset(p.inner_w / 2)) + _inner_arm(p))
    bump = _bump(p)
    if bump is not None:
        left = _sk(left + bump)
        right = _sk(right + mirror(bump, about=Plane.YZ.offset(p.inner_w / 2)))
    merged = with_base_dovetail(_sk(base + left + right), p)
    if p.coupon:
        band = _rect(
            -2 * p.beam_w, p.lap_y0 - p.jog_height - p.coupon_stub, 3 * p.beam_w, p.beam_h
        )
        merged = _sk(merged & band)
        assert len(merged.faces()) == 2, "coupon should be the two joint pieces"
    else:
        assert len(merged.faces()) == 1, "profile did not fuse into a single face"
    return merged


def _label_cut(p: WrapParams) -> Part | None:
    if not p.label:
        return None
    if p.coupon:
        # coupons are short along the beam: engrave the ID on the top face,
        # along the left arm's stub
        return top_face_label(p, -p.wall / 2, p.lap_y0 - p.jog_height - p.coupon_stub / 2, along="y", size=max(1.5, p.wall - 1.5))
    if p.length < p.label_size + 1.0:
        # too short along the beam for text on the base's outer face: engrave
        # it on the top face instead, across the base
        return top_face_label(p, p.inner_w / 2, -p.wall / 2, along="x", size=max(1.5, p.wall - 1.5))
    face_plane = Plane(
        origin=(p.inner_w / 2, -p.wall, p.length / 2), x_dir=(1, 0, 0), z_dir=(0, -1, 0)
    )
    text = face_plane * Text(p.label, font_size=p.label_size, font_style=FontStyle.BOLD)
    return extrude(text, amount=-p.label_depth)


def half(p: WrapParams) -> Part:
    """One finished half (or, in coupon mode, the two joint test pieces)."""
    body = extrude(profile(p), amount=p.length, dir=(0, 0, 1))
    cut = _label_cut(p)
    if cut is not None:
        body = body - cut
    return body


def mate_location(p: WrapParams) -> Location:
    """Transform that places a second half in its assembled position: rotated
    180 degrees about the beam axis through the centre of the span."""
    return Location((p.inner_w / 2, p.span_h / 2, 0), (0, 0, 180)) * Location(
        (-p.inner_w / 2, -p.span_h / 2, 0)
    )


def assembly(p: WrapParams):
    """Both halves in the assembled position, as (lower, upper)."""
    lower = half(p)
    upper = lower.moved(mate_location(p))
    return lower, upper


def export_assembly_svg(p: WrapParams, path: str) -> None:
    """Drawing of both halves in the assembled position."""
    from build123d import ExportSVG

    lower = profile(p)
    upper = lower.moved(mate_location(p))
    svg = ExportSVG(scale=2, margin=10, line_weight=0.5)
    svg.add_shape(lower)
    svg.add_shape(upper)
    svg.write(path)


def main(argv: list[str] | None = None) -> None:
    run_cli(WrapParams, __doc__, half, profile, argv)


if __name__ == "__main__":
    main()
