# Research: Simulating Small Rotors for ArduPilot SITL in Gazebo

Written 2026-09-10 while the custom cinewhoop would arm and produce thrust but
flip within about 1.5 s of throttle-up. Everything below is external material
plus arithmetic against our own measurements; anything not verified in this
repository is marked as such.

## The question

Our rotors are driven by `ArduPilotPlugin`'s `<control>` blocks with
`type=VELOCITY` and `useForce=1`, and lift comes from eight `LiftDrag` surfaces,
copied from the Iris reference. At the real inertia of a 3 in propeller
(izz 8.0e-07) that velocity loop changes rotor speed by 168 % of its target in a
single physics step. Raising the inertia stabilises the loop but stores real
angular momentum, so spin-up reaction yaws our 0.00038 kg m^2 airframe at
thousands of deg/s. Is there a better primitive?

## Finding 1: Gazebo has a purpose-built rotor system

`gz-sim` ships `MulticopterMotorModel`, which is designed for exactly this and
avoids the velocity PID entirely. It commands the joint velocity directly and
computes thrust and reaction torque analytically:

```
realMotorVelocity = jointVelocity * rotorVelocitySlowdownSim
thrust            = turningDirection * sign(v) * v^2 * motorConstant
dragTorque        = -turningDirection * thrust * momentConstant
```

The reaction torque is applied to the parent link, so yaw authority is explicit
and always consistent with thrust, rather than emerging from blade drag.

### Parameters, with defaults from the implementation

| Parameter | Default | Meaning |
|---|---|---|
| `motorConstant` | 8.54858e-06 | thrust coefficient, N/(rad/s)^2 |
| `momentConstant` | 0.016 | reaction torque per unit thrust, m |
| `maxRotVelocity` | 838.0 | command saturation, rad/s |
| `timeConstantUp` | 1/80 s | first-order spin-up lag |
| `timeConstantDown` | 1/40 s | first-order spin-down lag |
| `rotorDragCoefficient` | 1.0e-4 | air drag scaling |
| `rollingMomentCoefficient` | 1.0e-6 | rolling moment scaling |
| `rotorVelocitySlowdownSim` | 10.0 | velocity rescale for numerical stability |
| `turningDirection` | required | `cw` or `ccw` |
| `actuator_number` | required | index into the `Actuators` velocity array |

### `rotorVelocitySlowdownSim` is the answer to our stability problem

The joint turns ten times slower than the modelled rotor, and the thrust
computation multiplies the speed back up before squaring. Physics therefore
never sees the high angular rate that makes our loop diverge, while thrust and
torque stay correct. This is a default, not an exotic setting, which suggests
everyone building small rotors in Gazebo hits our problem.

Note that `ArduPilotPlugin` reads the same-named `<rotorVelocitySlowdownSim>`,
while both Iris and our model write `<controlVelocitySlowdownSim>`. The plugin
therefore silently uses its default of 1. Harmless today because 1 is what those
models want, but it means the knob we needed was never actually connected.

## Finding 2: `ArduPilotPlugin` can drive a topic instead of a joint

Alongside `VELOCITY`, `POSITION` and `EFFORT`, the plugin supports
`type=COMMAND`, which publishes a `gz.msgs.Double` to `cmd_topic` and touches no
joint at all. Verified in our own checkout at `src/ArduPilotPlugin.cc:629` and
`:1317`. Community examples point `cmd_topic` at things like
`/model/<name>/joint/<joint>/cmd_vel` and at thruster topics for underwater
vehicles.

This gives two clean architectures that both remove the PID:

- **COMMAND to `JointController`** - kinematic velocity, exact tracking, but no
  motor reaction torque, so yaw authority would have to come from blade drag
  alone. We measured that a kinematic velocity command does drive our rotors to
  exactly the commanded speed and lifts the airframe on the thrust stand.
- **COMMAND to `MulticopterMotorModel`** - needs a small adapter, because the
  plugin publishes one `Double` per joint while the motor model subscribes to a
  single `Actuators` array indexed by `actuator_number`. Roughly thirty lines of
  Python or a tiny Gazebo system.

The second is the better target: it gives thrust, explicit yaw torque and motor
lag, with no joint force loop anywhere.

## Finding 3: ArduPilot's default gains are for a much larger vehicle

The ArduPilot MethodicConfigurator tuning guide states plainly that the default
PID gains target a **9 to 12 inch propeller** vehicle, and that smaller props
need lower than default rate gains. Our `ardupilot_params.parm` sets only
`FRAME_CLASS` and `FRAME_TYPE`, so every gain is a default meant for a vehicle
roughly five times our size.

Concrete anchors from the official tuning page:

- `INS_GYRO_FILTER` 80 Hz for 5 in props (higher for smaller)
- `MOT_THST_EXPO` 0.55 for 5 in props
- `ATC_RAT_*_FLTD` and `ATC_RAT_*_FLTT` at `INS_GYRO_FILTER / 2` on roll and
  pitch, `INS_GYRO_FILTER / 4` on yaw

The LiftDrag thread on ArduPilot Discourse ends with the reporter resolving very
similar instability purely by iterating `ATC_RAT_RLL_P/I`, `ATC_RAT_PIT_P/I` and
`ATC_RAT_YAW_P/I`, which supports tuning as a real part of the fix rather than a
distraction from the model.

## Finding 4: `AHRS_EKF_TYPE 10` separates vehicle dynamics from estimation

Recommended on the same thread and documented as the SITL AHRS type, this makes
ArduPilot use simulator ground truth instead of running the EKF. It removes the
whole class of failures we burned time on today - "Check mag field", "Accels
inconsistent", "Gyros inconsistent" and repeated EKF resets - none of which were
what we were trying to measure. It should be the default for any run whose
purpose is validating the airframe rather than the estimator.

**Tried here, and it does not work yet.** With `AHRS_EKF_TYPE 10` the estimator
noise does disappear - reported gyro rates drop to zero and the EKF messages
stop - but ArduPilot then reports the airframe as pitched about -90 degrees
while it sits level in Gazebo, and prearm refuses to arm a vehicle it believes
is on its side. Our `modelXYZToAirplaneXForwardZDown` and `gazeboXYZToNED` are
identical to the Iris reference, and the plugin does send ground-truth pose
through those transforms (`CreateStateJSON`), so the fault is somewhere in that
composition rather than in the parameter. The parameter is deliberately not in
`ardupilot_params.parm`; resolving the attitude offset is its own task, and the
Iris reference is the obvious control experiment.

## Finding 5: this is a known hard spot with no published answer

Two Discourse threads describe our exact situation on custom ardupilot_gazebo
models: one where the model arms but will not take off, and one where it arms
and then flips during takeoff. Neither received a working answer. There is also
an open `gz-sim` issue (#2657, October 2024) reporting that yaw direction is
inverted in `MulticopterVelocityControl`, so sign conventions around
`turningDirection` deserve an explicit test rather than trust.

Practical consequence: verify rotation sense by measurement on our own rig
before assuming any convention, and keep the Iris reference run as the control.

## Numbers for our airframe

Weight is 2.354 N, so hover needs 0.588 N per rotor. For a target thrust to
weight ratio:

| T/W | thrust per rotor at full throttle |
|---|---|
| 2.0 | 1.177 N |
| 3.0 | 1.765 N |
| 4.0 | 2.354 N |

Our current model reaches T/W 1.13, measured on the thrust stand, which is why
hover sits near 94 % throttle and leaves nothing for attitude correction.

Blade-element estimate for a 3 in prop, `T = Ct * rho * n^2 * D^4` with
D = 0.0762 m:

| RPM | Ct | thrust/rotor | implied `motorConstant` |
|---|---|---|---|
| 25000 | 0.10 | 0.72 N | 1.05e-07 |
| 30000 | 0.10 | 1.03 N | 1.05e-07 |
| 30000 | 0.12 | 1.24 N | 1.26e-07 |

`motorConstant` is independent of RPM by construction, so the calibration
reduces to choosing `maxRotVelocity` for the motor and `motorConstant` for the
propeller. These Ct values are textbook figures, not measurements of a specific
propeller, and they land below the 3 to 4 T/W that real cinewhoops achieve, so
treat them as a starting point to be trimmed against the thrust stand.

For `momentConstant`, the gz-sim example uses 0.016 m. Small propellers sit
around 0.01 to 0.02 m. This value sets yaw authority directly and is the first
thing to adjust if yaw is sluggish or divergent.

## Outcome

Implemented on 2026-09-10 and it works. The rotor drive now uses four
`MulticopterMotorModel` systems fed through `tools/ap_actuator_bridge` from the
plugin's `COMMAND` output, and `scripts/check_guided_takeoff.sh` measures a
repeatable guided takeoff that holds 2 m within 4 degrees of tilt. The
intermittent NaN that crashed SITL disappeared with the force PID.

## Calibration, 2026-09-10

Done, and it forced the gain tuning along with it.

Target hardware from [the model spec](../spec/01_model_dronu.md) is 4x GEPRC
SPEEDX2 1404 3850 KV on 4S with ducted 3 in propellers. GEPRC publish no thrust
table for the 3850 KV variant, so the numbers come from two independent figures:

- RCINPOWER's GTS V3 1404 Plus 3850 KV, the same KV and stator class, is quoted
  at 492 g max thrust on an open HQ T333 three-blade 3 in propeller and 421 g on
  a ducted GF D63.
- Community measurements of ducted 3 in props on 1404 motors give roughly
  1400 g total, i.e. 350 g per motor, with a 250 g dry airframe.

The ducted figure is the relevant one, and 350 g per rotor is what the model now
produces. Treat the vendor's own numbers with care: the same page quotes 328 W at
16.8 V, which is 19.5 A, against a stated maximum of 9.6 A.

| Parameter | Was | Now | Where it comes from |
|---|---|---|---|
| `maxRotVelocity` | 2600 | 3980 | 38000 RPM, 59 % of 3850 KV x 16.8 V unloaded |
| `motorConstant` | 2.611e-07 | 2.20e-07 | `Ct * rho * D^4 / (4*pi^2)`, Ct = 0.21 |
| `momentConstant` | 0.005 | 0.013 | `(Cq/Ct) * D`, Cq/Ct = 0.17 |
| `<multiplier>` | 2600 | 3980 | must track `maxRotVelocity` |

Ct = 0.21 is not a textbook slow-flyer figure. It is what real FPV props need to
explain their measured thrust: a 5 in racing prop making 1500 g at 27000 RPM
implies Ct = 0.23 by the same formula, so 0.21 for a high-pitch three-blade 3 in
is consistent rather than optimistic. The earlier 0.10 to 0.12 estimates in the
table above are textbook values for low-pitch propellers and land far too low.

Thrust to weight is now 5.9, so hover sits at sqrt(1/5.9) = 0.41 throttle.

### The calibration broke flight until the gains followed

The first calibrated takeoff overshot a 2 m target to 42 m. Scaling the vertical
acceleration gains down made it worse, 54 m, which ruled the Z axis out. Two
measurements then located the real fault:

- On the thrust stand, where attitude is locked, the climb was accurate: 5.42 m
  for a 5.0 m target. So the Z controller was fine all along.
- In free flight the dataflash log showed `ThO 0.000` and a commanded descent of
  `DCRt -2.5` m/s while the vehicle climbed at 15 m/s. Nothing was being
  commanded upward, so the lift had to be coming from saturation.

Reading the commanded rotor speeds during the climb confirmed it: one rotor
pinned at the `MOT_SPIN_MIN` floor of 597 rad/s while the others ran 1500 to
2200 rad/s, and which rotor saturated kept rotating. The rate loop was
oscillating into the stops, and Copter gives throttle away to preserve attitude
authority, which is why `ThO` read zero while the motors still averaged roughly
the vehicle's weight in thrust.

The cause is authority, not thrust. A full roll demand gives
`2 * 3.485 N * 0.04455 m = 0.311 N m` against `Ixx = 0.00022`, which is
1411 rad/s^2 or 80900 deg/s^2. A 1.5 kg ten-inch quad at a thrust-to-weight
ratio of 2 manages about 10500 deg/s^2, so this airframe has **7.7 times** the
angular acceleration per unit of controller output. Dividing the stock rate gains
by 7.7 restored controlled flight on the first attempt:

> Later correction: the arm was 0.04455 m here, from a 126 mm wheelbase that was
> an assumption rather than the frame's figure. GEPRC publish 128 mm, so the arm
> is 0.04525 m and the ratio is 7.8 rather than 7.7. The numbers above are left
> as they were measured; 1.6 per cent is inside the accuracy of the method and
> the gains were not re-derived for it.

| Parameter | Default | Now |
|---|---|---|
| `ATC_RAT_RLL_P`, `ATC_RAT_PIT_P` | 0.135 | 0.018 |
| `ATC_RAT_RLL_I`, `ATC_RAT_PIT_I` | 0.135 | 0.018 |
| `ATC_RAT_RLL_D`, `ATC_RAT_PIT_D` | 0.0036 | 0.0005 |
| `ATC_RAT_YAW_P` | 0.18 | 0.023 |
| `ATC_RAT_YAW_I` | 0.018 | 0.0023 |

Measured afterwards: guided takeoff peaks at 2.07 m and settles at 2.02 m for a
2.00 m target with 10.0 degrees of worst tilt, against 2.24 m and 2.04 m before;
the autonomy demo holds 1.04 m for a 1.0 m target, against 1.36 m before. The
thrust stand is unchanged and baseline CI still passes.

Still open: these are derived from published motor figures and textbook
coefficients, not from a thrust stand with this exact ducted propeller, and the
gains come from one authority-ratio calculation rather than a tuning sweep.
Braking from 0.5 m/s still takes about 0.6 m, which the extra authority did not
change, so that belongs to the velocity controller's deceleration limits rather
than to thrust.

## Original plan

1. Fix the ground-truth attitude offset so `AHRS_EKF_TYPE 10` becomes usable,
   checking the Iris reference first to see whether the 90 degree error is ours
   or general to the JSON path. This is worth doing early because it removes a
   whole class of noise from every later experiment.
2. Replace the eight `LiftDrag` surfaces and the four `<control>` force loops
   with four `MulticopterMotorModel` systems plus an adapter from the plugin's
   `COMMAND` doubles to one `Actuators` message.
3. Calibrate `motorConstant` on the existing thrust stand against a target T/W
   near 3, then `momentConstant` against a measured yaw step.
4. Only then tune `ATC_RAT_*` and the filters for a 3 in airframe.

Step 2 is the substantial one. Steps 1 and 3 reuse machinery that already works
here.

## Sources

- [gz-sim MulticopterMotorModel implementation](https://raw.githubusercontent.com/gazebosim/gz-sim/gz-sim8/src/systems/multicopter_motor_model/MulticopterMotorModel.cc)
- [gz-sim quadcopter.sdf example](https://github.com/ignitionrobotics/ign-gazebo/blob/master/examples/worlds/quadcopter.sdf)
- [MulticopterMotorModel class reference](https://gazebosim.org/api/sim/10/classgz_1_1sim_1_1systems_1_1MulticopterMotorModel.html)
- [MulticopterVelocityControl class reference](https://gazebosim.org/api/sim/8/classgz_1_1sim_1_1systems_1_1MulticopterVelocityControl.html)
- [gz-sim issue 2657: quadrotor yaw direction inverted](https://github.com/gazebosim/gz-sim/issues/2657)
- [Gazebo case study: migrating the ArduPilot ModelPlugin](https://gazebosim.org/api/sim/8/ardupilot.html)
- [ArduPilot/ardupilot_gazebo](https://github.com/ArduPilot/ardupilot_gazebo)
- [ArduPilot/SITL_Models](https://github.com/ArduPilot/SITL_Models)
- [Discourse: Lift drag plugin usage](https://discuss.ardupilot.org/t/lift-drag-plugin-usage/52177)
- [Discourse: Custom drone model in ardupilot gazebo](https://discuss.ardupilot.org/t/custom-drone-model-in-ardupilot-gazebo/145012)
- [Discourse: Tuning queries for 3 inch drone](https://discuss.ardupilot.org/t/tuning-queries-for-3-drone/143969)
- [Copter docs: Setting the Aircraft Up for Tuning](https://ardupilot.org/copter/docs/setting-up-for-tuning.html)
- [MethodicConfigurator ArduCopter tuning guide](https://ardupilot.github.io/MethodicConfigurator/TUNING_GUIDE_ArduCopter.html)
- [ArduPilot dev docs: SITL simulator](https://ardupilot.org/dev/docs/sitl-simulator-software-in-the-loop.html)
