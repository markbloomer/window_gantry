# Planar gantry specification

As built by `scripts/build_gantry.py` and saved in `planar_stage.blend`. Units are inches unless noted. One Blender unit is one inch.

Origin is the floor center of the machine. X is width, Y is depth with the front negative, and Z is up.

## Envelope

The fixed frame is 48 wide × 6 deep × 72 tall.

| Axis | Frame | Carriage travel |
| --- | --- | --- |
| X | −24 to 24 | −17.77 to 17.11 |
| Y | −3 to 3 | Camera head may swing past ±3 |
| Z | 0 to 72 | Beam axis 8.39 to 69.78 |

The left limit is set by the 23 mm tilt motor: at pan 0 its outboard face stays about 0.12 in clear of the left vertical beam. The right limit is set by the camera swing, with the same clearance to the right beam. Vertical travel keeps the carriage off the base plate and the underside of the top plate.

Home is the bottom-left corner: X = −17.77, Z = 8.39.

## Assumptions

- Beams and drive axles are rigid.
- Belts do not stretch.
- The vertical lift is a 5:1 worm. The horizontal belt is direct. The pan pair is 1:1.
- Control software and wiring are out of scope and do not change the range.
- No component may overlap another anywhere in the travel box. The camera head may swing past the 6 in depth. The upright lift motor may hang past the front of that depth.

## Frame

| Part | Size | Position |
| --- | --- | --- |
| Bottom plate | 48 × 6 × 0.5 | Center Z = 0.25 |
| Top plate | 48 × 6 × 0.5 | Center Z = 71.75 |
| Vertical beams | Ø1.3125, length 71.04 | Centers X = ±22.30, Y = −0.40, Z = 36 |

Inner face of each vertical beam is at X = ±21.644. A 15 mm wide, 3 mm pitch belt is fixed on the front of each beam (teeth toward +Y). The belt is split into a lower run and an upper run; the gap between them follows the gantry.

## Gantry beams and wheels

| Item | Value |
| --- | --- |
| Horizontal beams | Ø1.125 |
| Front beam center Y | −1.645 |
| Rear beam center Y | 1.345 |
| Beam ends | X = ±21.642 |
| Gap between beam faces and a NEMA 17 body | 0.10 |

Both beams stop at the inner vertical-wheel pillow blocks. A bracket at each end continues out to the outer wheel and the vertical motor.

Vertical crowned rollers, groove matched to Ø1.3125:

| Roller | Contact radius | Flange radius | Width |
| --- | --- | --- | --- |
| Inner (stacked above and below the beam) | 0.45 | 0.52 | 0.36 |
| Outer | 0.45 | 0.52 | 0.30 |

Radial gap from groove to rail is 0.012. Inner axle centers are at X = ±21.182. Outer axle centers are at X = ±23.418. The outer flanges reach about X = ±23.94.

Carriage crowned rollers, groove matched to Ø1.125:

| | Value |
| --- | --- |
| Contact radius | 0.36 |
| Flange radius | 0.46 |
| Width | 0.28 |
| Gap | 0.012 |
| Upper wheels | Two per beam, at X = ±1.35 from the carriage center |
| Lower wheels | One per beam, on the carriage centerline |

Each lower wheel is on a short axle that runs in from the outside cheek and stops before the pan gear.

## Belts and pinions

GT2 pitch, used on the horizontal belt, is 2 mm (0.0787 in). A 20-tooth pinion has pitch radius 0.251 in.

The vertical belts are 15 mm wide and 3 mm pitch. A 6 mm, 2 mm printer belt is not enough for this climb: the heavier side carries about 8 kg (78 N) all the time, and a printer belt is meant to run near a 30 N install tension. A 16-tooth pinion has pitch radius 0.301 in.

Vertical drive: a Ø0.25 timing rod runs inside the front beam at Y = −1.80 and carries one of those pinions at each rail. Idlers ride the smooth back and are wide enough for the 15 mm belt. A 20-tooth worm wheel sits on that rod just to the right of the right pinion. A 4-start worm stands upright in front of the beam, shaft up, for a 5:1 reduction, and a NEMA 17 hangs under it. The wider pinion shifts that motor out to about X 22.06–23.73, still inside the frame, and the larger wheel drops the body to clear the wheel, about Y −3.27 to −1.61. At about 600 rpm the gantry rises at 3.8 in/s. The worm backdrives, so the motor holds the gantry. Both ends of the gantry still have the same belt-pinion mount.

Horizontal drive: the belt motor sits on the left of the carriage. Its shaft is just outside the left upper wheel axle (X = −1.35) and the inner idler is just inside that axle, so the axle is between them. The belt runs above the upper wheel axles, teeth toward the front beam, idlers on the smooth back. The motor center is 1.694 in left of the carriage center.

## Motors

Standard NEMA 17 body, used for the vertical drive, the horizontal belt, and pan:

| | Value |
| --- | --- |
| Face | 1.665 in square (42.3 mm) |
| Body length | 1.89 in |
| Shaft | Ø5 mm |
| Mounting pattern | 31 mm square, M3 clearance holes |
| Screw heads | Ø0.20 × 0.06 |

The exposed shaft between a motor face and its gear or pinion is at least 20 mm (0.787 in), except the tilt motor, which bolts directly to its plate.

Tilt motor: NEMA 17 pancake. Same face and mounting pattern. Body depth 23 mm (0.906 in), plus the Ø0.866 × 0.08 shaft boss.

## End brackets

Both ends are the same six-sided box, plate thickness 0.16. The walls are the inboard face, the outboard face, the back, the front, the top, and the bottom. The drive axle passes through the inboard wall. Idler axles run from the inboard wall to the outboard wall. The upper idler is a slot through the top edge of the back wall. The lower idler is a slot through the bottom edge. Each slot is only as deep as the back face.

The right bottom face carries the upright NEMA 17. The left box is the mirror of the right box and has no motor.

Each outer wheel axle runs through a block that protrudes from the back face, outboard of the vertical beam.

## Carriage

The truck is a U with a top plate. Width is 5.60 in, set so both carriage motors sit inside the end plates. Cheeks, bottom plate, and top plate are 0.10 thick.

End plates, 0.10 thick, close the left and right ends. Each has:

- A hole for each horizontal beam, radius 0.04 larger than the beam.
- A hole for the horizontal belt, radius 0.12.

## Pan and tilt

The pan axle is on the carriage centerline. A 1:1 miter pair (20 teeth, 45° pitch cones, pitch radius 0.28) turns the pan-motor shaft into that vertical axle. The pan motor is on the right, the same 1.694 in off center as the belt motor is on the left, shaft pointing toward the center.

Pan and tilt each travel ±45°.

The camera is an inverted Canon EOS M100. Body 4.26 × 1.39 × 2.64. Lens points toward the front (−Y). The tripod face is up and is fastened to the lower yoke by a Ø0.20 × 0.20 peg. Tilt rotates about X through the center of the camera body.

Both yokes use the same section: 0.16 thick and 0.48 deep. The upper yoke hangs from the pan axle. Its arms come down to the tilt pivot. The lower yoke is wider than the camera and meets the upper arms on a short pin at each side. The pins stop outside the camera body.

The tilt motor bolts to a plate the size of the NEMA face (1.665 in square, 0.16 thick) on the left arm. The plate has a shaft hole and four screws on the 31 mm pattern.

At 45° the lens stays about 0.33 in under the upper yoke bar and about 0.66 in under the carriage.

## Motion

One loop, `Loop_Box`, 24 fps, linear keys, frames 0–1046. The first frame and the last frame are the same pose, so playback wraps without a jump.

Vertical legs run at 3.8 in/s, the speed of the 5:1 worm and the 16-tooth, 3 mm pinion with the NEMA 17 near 600 rpm. A full rise or drop is 390 frames (16.3 s). Horizontal legs run at 15.7 in/s, a direct 20-tooth pinion at that same motor speed, and take 53 frames. When a leg moves both axes it lasts as long as the slower axis.

Order of corners: bottom-left, top-left, top-right, bottom-right, then back to bottom-left. At each corner the carriage holds still while pan and tilt trace the full ±45° square:

1. Pan −45°, tilt −45°
2. Pan +45°, tilt −45°
3. Pan +45°, tilt +45°
4. Pan −45°, tilt +45°
5. Pan −45°, tilt −45°

Each of those steps is 10 frames. Between corners, pan and tilt stay at −45° while the carriage travels at the speeds above.

Rollers and pinions spin with travel: angle = distance / pitch radius. Belt array lengths follow the gantry.

## Files

| File | Role |
| --- | --- |
| `scripts/build_gantry.py` | Builds the scene |
| `planar_stage.blend` | Saved scene, frame 0 |
| `docs/window_gantry_1.png` | Carriage, camera, and left end bracket |
| `docs/window_gantry_2.png` | Right end bracket, lift motor, and outer wheel |
