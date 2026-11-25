"""A turtle that walks a centreline of straight lines and tangent circular
arcs in the XY plane, and the pure-Python geometry of the strip it traces:
points along the centreline, or along either face of a strip of given
thickness laid on it.

Headings are in radians, counter-clockwise from +x. An arc's ``turn`` is
positive to the left (counter-clockwise) and negative to the right.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Pt = tuple[float, float]


@dataclass(frozen=True)
class Seg:
    """One piece of centreline: a line (``r == 0``) or an arc of radius
    ``r`` turning ``turn`` radians, from ``start`` at heading ``h0``."""

    start: Pt
    h0: float
    length: float = 0.0
    r: float = 0.0
    turn: float = 0.0

    @property
    def is_arc(self) -> bool:
        return self.r > 0

    @property
    def h1(self) -> float:
        return self.h0 + self.turn

    @property
    def centre(self) -> Pt:
        s = 1.0 if self.turn > 0 else -1.0
        return (self.start[0] - s * self.r * math.sin(self.h0), self.start[1] + s * self.r * math.cos(self.h0))

    def at(self, f: float, offset: float = 0.0) -> Pt:
        """The point a fraction f of the way along, moved ``offset`` to the
        left of the direction of travel (negative: to the right)."""
        if self.is_arc:
            h = self.h0 + f * self.turn
            s = 1.0 if self.turn > 0 else -1.0
            cx, cy = self.centre
            # the radius from the centre to the point is the left normal
            # turned by -s * 90 deg; walk out r, less the offset on the inside
            nx, ny = s * math.sin(h), -s * math.cos(h)
            rr = self.r - s * offset
            return (cx + rr * nx, cy + rr * ny)
        d = f * self.length
        x = self.start[0] + d * math.cos(self.h0) - offset * math.sin(self.h0)
        y = self.start[1] + d * math.sin(self.h0) + offset * math.cos(self.h0)
        return (x, y)

    @property
    def end(self) -> Pt:
        return self.at(1.0)

    @property
    def mid(self) -> Pt:
        return self.at(0.5)

    def sample(self, offset: float = 0.0, step_deg: float = 0.25) -> list[Pt]:
        n = max(1, math.ceil(abs(math.degrees(self.turn)) / step_deg)) if self.is_arc else 1
        return [self.at(i / n, offset) for i in range(n + 1)]


class Turtle:
    """Walks a centreline, collecting its segments."""

    def __init__(self, start: Pt, heading: float):
        self.pos, self.heading = start, heading
        self.segs: list[Seg] = []

    def _add(self, seg: Seg) -> "Turtle":
        self.segs.append(seg)
        self.pos, self.heading = seg.end, seg.h1
        return self

    def line(self, length: float) -> "Turtle":
        return self._add(Seg(self.pos, self.heading, length=length))

    def arc(self, r: float, turn: float) -> "Turtle":
        return self._add(Seg(self.pos, self.heading, r=r, turn=turn))

    def replay_reversed(self, segs: list[Seg]) -> "Turtle":
        """Walk ``segs`` backwards: each line again, each arc turning the
        other way. Start the turtle at their end, heading back."""
        for s in reversed(segs):
            if s.is_arc:
                self.arc(s.r, -s.turn)
            else:
                self.line(s.length)
        return self


def sample(segs: list[Seg], offset: float = 0.0) -> list[Pt]:
    return [p for s in segs for p in s.sample(offset)]
