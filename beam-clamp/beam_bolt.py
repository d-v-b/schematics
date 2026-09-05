"""Beam bolt: two identical C halves bolted together around a rectangular
beam. A competitor to the ratchet joint in beam_wrap.py.

Each half is the clamp profile with arms reaching half the beam height. The
part is mirror-symmetric: over the lap region each arm tapers, along the beam,
from the full ``length`` down to a finger of half that, and both fingers sit
on the same end of the length (the bed side when printed, so nothing floats).

The mating half is the same part flipped end-for-end: rotated 180 degrees
about the beam's width axis through the centre of the span. That maps each arm
onto the same-side arm of the other half and sends its fingers to the other
end of the length, so the two parts' fingers interlock, flat face to flat
face, and the assembled pair is one continuous band of the same ``length``
everywhere.

Each finger carries a slot running along the beam (a stadium in the 2D
profile, so it prints as a clean vertical slot) and elongated along the arm.
A bolt through the two aligned slots clamps the fingers together, and because
the faces are perpendicular to the bolt, the slot gives height tolerance
without any wedge effect. Head and nut sit on the parts' end faces, clear of
the wood. The wall carries the slot on its own (no boss) and the bolt holds
the wrap, so there are no tension bumps.

Coordinates match beam_clamp.py: the beam's bottom-left inner corner is at
(0, 0), the beam occupies x in [0, inner_w], and the part extends along +z by
``length``.

Usage:
    python beam_bolt.py -o out.stl [--wall 5] [--bolt_d 2.0] ...
    python beam_bolt.py -o coupon.stl --coupon 1   # just the joint, for fit tests
"""

from __future__ import annotations

from dataclasses import dataclass

from build123d import (
    Circle,
    FontStyle,
    Location,
    Part,
    Plane,
    Polygon,
    Sketch,
    SlotCenterToCenter,
    Text,
    extrude,
    mirror,
)

from beam_clamp import _elbow, _sk, run_cli, seat_offset
from beam_wrap import _rect


@dataclass(frozen=True)
class BoltParams:
    """Every dimension of one half, in millimetres."""

    beam_w: float = 53.6
    beam_h: float = 206.5
    clearance: float = 0.3
    # Thick enough to carry the bolt slot with min_slot_wall either side.
    wall: float = 5.0
    length: float = 50.0
    fillet_r: float = 2.0
    # --- joint ---
    # Length of each finger along the arm.
    lap_len: float = 24.0
    # Gap between the mating finger faces, along the beam.
    joint_clearance: float = 0.3
    # Gap between a finger's tip and the other half's shoulder when the joint
    # is cinched as far as the slots allow.
    tip_gap: float = 0.5
    # Height over which the arm tapers from length down to the finger. 0 = a
    # square step (an upward-facing face either way, so both print fine).
    taper_len: float = 25.0
    # Bolt: nominal diameter and hole clearance. Bolts run along the beam.
    bolt_d: float = 2.0
    hole_clearance: float = 0.3
    # Least material allowed either side of the slot, across the wall and
    # beyond the slot ends.
    min_slot_wall: float = 1.2
    # Slot length along the arm. Travel each way is slot_len - hole_d.
    slot_len: float = 8.0
    # Bolts per joint, spaced along the arm.
    n_bolts: int = 1
    bolt_spacing: float = 10.0
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
        """Gap between a base's inner face and the beam, set by the fillets."""
        return seat_offset(self.fillet_r, self.clearance)

    @property
    def span_h(self) -> float:
        """Distance between the two halves' inner base faces when assembled."""
        return self.beam_h + 2 * self.seat

    @property
    def hole_d(self) -> float:
        return self.bolt_d + self.hole_clearance

    @property
    def finger_len(self) -> float:
        """Extent of a finger along the beam."""
        return (self.length - self.joint_clearance) / 2

    @property
    def slot_travel(self) -> float:
        """How far the joint can move from nominal in each direction."""
        return self.slot_len - self.hole_d

    @property
    def shoulder(self) -> float:
        """Where each arm's full-length section ends and its finger begins.
        Placed so the other half's finger tip clears it by tip_gap even when
        the joint is cinched by slot_travel."""
        return (self.span_h - self.lap_len - self.tip_gap - self.slot_travel) / 2

    @property
    def arm_len(self) -> float:
        """Reach of each arm (the finger tip)."""
        return self.shoulder + self.lap_len

    @property
    def slot_y(self) -> float:
        """Slot centre: the centre of the span, which the flip maps to itself."""
        return self.span_h / 2

    def bolt_ys(self) -> list[float]:
        return [
            self.slot_y + (i - (self.n_bolts - 1) / 2) * self.bolt_spacing for i in range(self.n_bolts)
        ]

    def validate(self) -> None:
        if self.wall <= 0:
            raise ValueError(f"wall must be positive, got {self.wall}")
        if self.inner_w <= 2 * self.fillet_r:
            raise ValueError(
                f"inner span {self.inner_w} must exceed twice the fillet radius {self.fillet_r}"
            )
        if not 0 <= self.joint_clearance < self.length:
            raise ValueError("joint_clearance must be non-negative and less than length")
        if self.taper_len < 0:
            raise ValueError("taper_len must be non-negative")
        if self.n_bolts < 1:
            raise ValueError("need at least one bolt")
        if self.slot_len < self.hole_d:
            raise ValueError(f"slot_len {self.slot_len} must be at least the hole diameter {self.hole_d}")
        if self.wall < self.hole_d + 2 * self.min_slot_wall:
            raise ValueError(
                f"wall {self.wall} is too thin for a {self.hole_d} mm slot with {self.min_slot_wall} mm either side"
            )
        if self.shoulder - self.taper_len <= self.fillet_r:
            raise ValueError("arms are too short for the lap and taper: reduce lap_len or taper_len")
        ys = self.bolt_ys()
        lo = min(ys) - self.slot_len / 2 - self.min_slot_wall
        hi = max(ys) + self.slot_len / 2 + self.min_slot_wall
        if lo < self.shoulder or hi > self.arm_len:
            raise ValueError("lap_len is too short for the slots")
        if self.label and self.label_depth >= self.wall:
            raise ValueError(f"label_depth {self.label_depth} must be less than wall {self.wall}")


def _arm(p: BoltParams) -> Sketch:
    """Left arm profile: a plain wall from the elbow to the finger tip, minus
    the slots on the wall's centreline."""
    arm = _rect(-p.wall, p.fillet_r, 0, p.arm_len)
    for y in p.bolt_ys():
        slot = SlotCenterToCenter(p.slot_len - p.hole_d, p.hole_d, rotation=90).moved(
            Location((-p.wall / 2, y))
        )
        arm = _sk(arm - slot)
    return arm


def profile(p: BoltParams) -> Sketch:
    """2D cross-section of one half before the finger cuts. Mirror-symmetric."""
    p.validate()
    base = _rect(p.fillet_r, -p.wall, p.inner_w - p.fillet_r, 0)
    left = _sk(_elbow(p) + _arm(p))
    right = _sk(mirror(left, about=Plane.YZ.offset(p.inner_w / 2)))
    merged = _sk(base + left + right)
    if p.coupon:
        band = _rect(-2 * p.beam_w, p.shoulder - p.taper_len - p.coupon_stub, 3 * p.beam_w, p.span_h)
        merged = _sk(merged & band)
        assert len(merged.faces()) == 2, "coupon should be the two joint pieces"
    else:
        assert len(merged.faces()) == 1, "profile did not fuse into a single face"
    return merged


def _finger_cuts(p: BoltParams) -> Part:
    """Prisms that remove, above each finger, everything beyond finger_len
    along the beam, with a taper leading into it. Drawn in the (y, z) plane
    and extruded along x across each wall."""
    L, e, f = p.length, 1.0, p.finger_len
    y_t0, y_s, y_tip = p.shoulder - p.taper_len, p.shoulder, p.arm_len + e
    poly = Polygon((y_t0, L + e), (y_s, f), (y_tip, f), (y_tip, L + e), align=None)

    def cut(x0: float) -> Part:
        plane = Plane(origin=(x0, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))  # local (y, z)
        return extrude(plane * poly, amount=p.wall + 2 * e, dir=(1, 0, 0))

    return cut(-p.wall - e) + cut(p.inner_w - e)


def _label_cut(p: BoltParams) -> Part | None:
    if not p.label or p.coupon:
        return None
    face_plane = Plane(
        origin=(p.inner_w / 2, -p.wall, p.length / 2), x_dir=(1, 0, 0), z_dir=(0, -1, 0)
    )
    text = face_plane * Text(p.label, font_size=p.label_size, font_style=FontStyle.BOLD)
    return extrude(text, amount=-p.label_depth)


def half(p: BoltParams) -> Part:
    body = extrude(profile(p), amount=p.length, dir=(0, 0, 1))
    body = body - _finger_cuts(p)
    cut = _label_cut(p)
    if cut is not None:
        body = body - cut
    return body


def mate_location(p: BoltParams) -> Location:
    """Transform that places the second half: flipped end-for-end, i.e.
    rotated 180 degrees about the beam's width axis (x) through the centre of
    the span and the middle of the length. Arms stay on their own sides;
    fingers go to the other end of the length."""
    return Location((0, p.span_h / 2, p.length / 2), (180, 0, 0)) * Location(
        (0, -p.span_h / 2, -p.length / 2)
    )


def assembly(p: BoltParams):
    """Both halves in the assembled (nominal) position, as (lower, upper)."""
    lower = half(p)
    return lower, lower.moved(mate_location(p))


def bolt_shafts(p: BoltParams, dy: float = 0.0) -> Part:
    """Cylinders of bolt_d along the beam through both joints, placed where
    the two slots overlap when the upper half is shifted by dy."""
    shafts = None
    for y in p.bolt_ys():
        for x in (-p.wall / 2, p.inner_w + p.wall / 2):
            c = extrude(
                Circle(p.bolt_d / 2).moved(Location((x, y + dy / 2, -1))), amount=p.length + 2, dir=(0, 0, 1)
            )
            shafts = c if shafts is None else shafts + c
    return shafts


def export_assembly_svg(p: BoltParams, path: str) -> None:
    from build123d import ExportSVG

    lower = profile(p)
    upper = lower.moved(mate_location(p))
    svg = ExportSVG(scale=2, margin=10, line_weight=0.5)
    svg.add_shape(lower)
    svg.add_shape(upper)
    svg.write(path)


def main(argv: list[str] | None = None) -> None:
    run_cli(BoltParams, __doc__, half, profile, argv)


if __name__ == "__main__":
    main()
