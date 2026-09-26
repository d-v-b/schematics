# Bedside holder

A clip that hooks over the bed's side rail and stores a device upright in a
pocket that hangs down the rail's outer face. The device sits low, so it's
out of the way when you get in and out of bed, and it leans 7° with its top
toward the bed, so it can't flop outward. The same design makes a laptop clip (a 15" MacBook Air; print
two, about 200 mm apart) and a phone clip (an iPhone 4).

It's one 3 mm strip, bent like heat-formed plastic: straight runs joined by
tangent arcs, thickened evenly either side. From the bed side:

- a flared tip and the **inner leaf**, which leans in so that, relaxed, it
  overlaps the 23 mm rail by 1 mm and springs against it when pushed on
- two soft bends over the rail's top corners, with an inside radius of 3.5.
  They're placed to touch the corners, so the strip stands about 1 mm clear
  of the top edge and doesn't care how square it is
- the **hanger**, leaning 7° down and away from the rail's outer face. The
  device lies on it, so the device's top tips toward the bed: the laptop's
  top ends up 35 mm above the rail top, right over the rail's outer face
- a solid **pad**, 140 mm below the rail top and 20 mm clear of the rail's
  bottom edge, that holds the hanger off the rail (18 mm at 7°). It's a
  buttress on the hanger's rail side only: an R6 nose touches the rail
  face, and R15 concave fillets sweep it tangentially into the hanger above
  and below, so the device-side face stays flat. The device's weight
  presses the hanger onto the pad and the clamp, so the lean is set by
  solid material, not by a spring
- a 180° **J**, in which the device's foot seats 200 mm below the rail top
- the **spring lip**, which leans in 6° to overlap the device by 0.75 mm,
  pressing its lower back onto the hanger, then flares out as a lead-in

![profile](profile.svg)

The profile relaxed, over the rail (dashed), with the laptop's foot dotted.

It prints flat: the profile lies on the bed and the clip's width along the
rail is print Z.

## Springs and creep

The inner leaf and the lip are cantilevers of the strip, held deflected for
as long as the clip is on. At a deflection δ, a cantilever of arm L has a
root stress of `σ = 3·E·(t/2)·δ / L²`. That gives 12.5 MPa in the inner
leaf and 12.4 MPa in the lip at the defaults, against PETG's creep ceiling
of about 15 MPa. The bends add compliance on top of this, so the estimate
is conservative. `validate()` refuses any geometry over the ceiling, and
any inner leaf that would stand more than 5 mm off the rail, since that's
all the room there is before the mattress. It also refuses a pad that
would hang off the bottom of the rail or miss the hanger, and a lean too
small to hold the hanger off the rail at the pad.

A rail 0.5 mm thicker than nominal takes the inner leaf over the ceiling.
That's what the coupons are for.

## Coupons

The part is one profile, so a coupon is a 1 mm slice of the whole thing:
clamp, lean, pad and pocket, exactly where they'll be. Each one tests the
fit on the rail and the fit of the device at once. Its parameters are
engraved in its top face, along the hanger:

```bash
pixi run just coupons         # (inner_pre, lip_pre) = (0.5, 0.5) / (1.0, 0.75) / (1.5, 1.0) x t 2.5/3, laptop
pixi run just phone-coupons   # the same for the phone
```

Coupons relax the creep ceiling to 30 MPa, because the sweep deliberately
brackets it. Push each onto the rail and slide the device in. Pick the
loosest one that doesn't slide on the rail and holds the device without
rattling. Set those values at the top of the `justfile`, then:

```bash
pixi run just laptop   # print two
pixi run just phone
```

`pixi run just preview` regenerates `profile.svg`.
