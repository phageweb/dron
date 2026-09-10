// OpenIPC cinewhoop - whole-drone layout model
//
// This exists to answer mechanical questions before parts are bought, not to be
// pretty: where the LD06 can sit so it sees forward without meeting a
// propeller, whether the MTF-02P has a clear view down, and roughly where the
// centre of mass lands. See spec/realna_stavba_dronu/05_cad_dily.md.
//
// Units are millimetres. The frame convention matches the ROS model so the two
// cannot drift: X forward, Y left, Z up, origin at the centre of the top plate.
// ROS works in metres, so every number here is 1000x the one in
// ros_ws/src/openipc_cinewhoop_description/config/physical_params.yaml.
//
//   openscad -o drone.png --imgsize=1600,1200 drone.scad
//   openscad -o drone.stl drone.scad

// ---------------------------------------------------------------- confidence
// Some dimensions come from a vendor, the rest are placeholders standing in
// until the parts are measured. Placeholders render in a flat warning colour so
// a glance at the picture shows what is not yet real.
// Placeholders keep their own colour and go translucent instead, because
// tinting them all one colour made the picture unreadable: most of the drone is
// still a placeholder, so the whole thing turned orange.
placeholder_alpha = 0.35;

module part(c, verified = true) {
  color(c, verified ? 1 : placeholder_alpha) children();
}

// ------------------------------------------------------------------ geometry
// Verified: GEPRC publish a 128 mm wheelbase for the CineLog30 V3.
wheelbase        = 128;
arm_xy           = wheelbase / 2 / sqrt(2);   // 45.25, quad X diagonal
plate_thickness  = 2.5;                        // verified: 2.5 mm carbon
plate_size       = 105;                        // PLACEHOLDER: frame outline

// Verified: GEPRC SPEEDX2 1404, 18.2 x 13.8 mm, 1.5 mm shaft.
motor_d          = 18.2;
motor_h          = 13.8;
motor_shaft_d    = 1.5;

// Verified: HQProp DT76MMX3 V2, 76 mm three-blade.
prop_d           = 76;
prop_thickness   = 2;
prop_z           = 10;                         // PLACEHOLDER: above the plate
prop_blades      = 3;
prop_blade_w     = 9;

// PLACEHOLDER: the whole duct. Nothing about it is measured yet, and it is the
// single most important thing to get from GEPRC's drawing, because it decides
// where anything can be mounted without meeting a propeller.
duct_inner_d     = prop_d + 4;
duct_outer_d     = duct_inner_d + 8;
duct_h           = 20;
duct_z           = -9;

// Verified: MicoAir H743 V2 45A AIO, 36 x 36 x 8 mm on a 25.5 mm pattern.
fc_size          = 36;
fc_h             = 8;
fc_mount         = 25.5;

// PLACEHOLDER for the board; the 25.5 mm pattern and 19 mm lens are published.
vtx_size         = 30;
vtx_h            = 8;
lens_d           = 19;
lens_len         = 12;

// Verified: MicoAir MTF-02P, 21.6 x 16 x 6.5 mm.
flow_l           = 21.6;
flow_w           = 16;
flow_h           = 6.5;

// Verified: SpeedyBee ELRS Nano, 10.4 x 18.4 mm.
rx_l             = 18.4;
rx_w             = 10.4;
rx_h             = 3;                          // PLACEHOLDER

// Verified: Tattu R-Line 4S LiHV 750, standard pack.
batt_l           = 60;
batt_w           = 31;
batt_h           = 27;
// Moved back from the centre to trade against the lidar on the nose. This is a
// number to settle with the real parts on a balance, not from the drawing.
batt_x           = -10;

// PLACEHOLDER, and the one that matters most: an LD06 is roughly a 38 mm square
// tower with the optical window partway up. Take the real figures off the
// datasheet linked in 05_cad_dily.md before trusting any clearance below.
ld06_l           = 38.6;
ld06_w           = 38.6;
ld06_h           = 34.8;
ld06_window_z    = 20;                         // window centre above its base
ld06_x           = 46;                         // where we are proposing to put it
// Not chosen freely: at any height where the body overlaps the propeller discs
// it collides with them, so the base has to sit above the propeller plane. That
// forces a mast and lifts the centre of mass.
ld06_mast_h      = 16;
ld06_z           = prop_z + prop_thickness + ld06_mast_h + ld06_h / 2;

// --------------------------------------------------------------- placements
// Where each board sits. These are proposals to be argued with, not measured
// positions: the stack height follows from the standoffs, the rest from what
// has to see out.
fc_z       = 5;    // flight controller, just above the plate
vtx_z      = 16;   // video board, stacked on standoffs above it
cam_x      = 50;   // camera module out at the nose
cam_z      = 6;
rx_x       = -22;  // receiver behind, antenna trailing
rx_y       = 16;
rx_z       = 5;
flow_x     = 20;   // optical flow under the plate, looking down

// ------------------------------------------------------------------- helpers
motor_positions = [
  [ arm_xy, -arm_xy], // motor_1 front right
  [-arm_xy,  arm_xy], // motor_2 rear left
  [ arm_xy,  arm_xy], // motor_3 front left
  [-arm_xy, -arm_xy], // motor_4 rear right
];

// ------------------------------------------------------------ pcb primitives
// The boards were plain cubes, which hid the things that actually constrain a
// build: where the mounting pattern is, which edge the USB is on, how tall the
// stack gets once components and standoffs are counted.

pcb_t          = 1.6;   // ordinary 4-layer FPV board
pcb_green      = [0.05, 0.32, 0.14];
pcb_black      = [0.10, 0.10, 0.11];
copper         = [0.72, 0.55, 0.30];
metal          = [0.70, 0.71, 0.74];
plastic_black  = [0.09, 0.09, 0.10];

// A board with its mounting holes actually cut, so a standoff can be checked
// against it instead of assumed.
module pcb(l, w, mount = 0, hole_d = 2.2, t = pcb_t, col = pcb_green) {
  difference() {
    color(col) cube([l, w, t], center = true);
    if (mount > 0)
      for (sx = [-1, 1], sy = [-1, 1])
        translate([sx * mount / 2, sy * mount / 2, 0])
          cylinder(h = t + 1, d = hole_d, center = true, $fn = 20);
  }
}

module chip(l, w, h, col = plastic_black) {
  color(col) cube([l, w, h], center = true);
}

module usb_c() {
  color(metal) cube([7.5, 3.2, 9], center = true);
}

module jst_sh(pins) {
  color([0.85, 0.85, 0.88]) cube([pins * 1.0 + 2, 4, 2.8], center = true);
}

module ipex() {
  color(metal) cylinder(h = 1.6, d = 3, center = true, $fn = 16);
}

module standoff(h) {
  color(metal) cylinder(h = h, d = 4, center = true, $fn = 20);
}

// --------------------------------------------------------------------- parts
module frame_plate() {
  part([0.10, 0.10, 0.12])
    translate([0, 0, -plate_thickness / 2])
      cube([plate_size, plate_size, plate_thickness], center = true);
}

module duct(x, y) {
  part([0.05, 0.30, 0.45], false)
    translate([x, y, duct_z])
      difference() {
        cylinder(h = duct_h, d = duct_outer_d, $fn = 96);
        translate([0, 0, -1])
          cylinder(h = duct_h + 2, d = duct_inner_d, $fn = 96);
      }
}

module motor(x, y) {
  part([0.75, 0.75, 0.78])
    translate([x, y, 0]) {
      cylinder(h = motor_h, d = motor_d, $fn = 48);
      cylinder(h = motor_h + 4, d = motor_shaft_d, $fn = 12);
    }
}

module propeller(x, y) {
  part([0.20, 0.65, 0.95])
    translate([x, y, prop_z])
      for (i = [0 : prop_blades - 1])
        rotate([0, 0, i * 360 / prop_blades])
          translate([prop_d / 4, 0, 0])
            cube([prop_d / 2, prop_blade_w, prop_thickness], center = true);
}

// MicoAir H743 V2 45A AIO. Board 36 x 36 mm on a 25.5 mm pattern, STM32H743
// with dual IMUs, and an ESC stage whose MOSFETs are metal-encapsulated - that
// block is the tallest thing on the underside and it needs airflow.
module flight_controller() {
  translate([0, 0, fc_z]) {
    pcb(fc_size, fc_size, mount = fc_mount);

    // Top side: MCU, the two gyros, the barometer.
    translate([0, 0, pcb_t / 2 + 1.5]) chip(10, 10, 3, [0.12, 0.12, 0.13]);
    translate([-11, 8, pcb_t / 2 + 1])  chip(3.5, 3.5, 1.2, [0.55, 0.55, 0.58]);
    translate([-11, 2, pcb_t / 2 + 1])  chip(3.5, 3.5, 1.2, [0.55, 0.55, 0.58]);
    translate([11, -9, pcb_t / 2 + 0.8]) chip(2.5, 2.5, 1, [0.30, 0.30, 0.32]);

    // USB-C on one edge. Whether this stays reachable once the canopy and the
    // battery are on is one of the questions the model exists to answer.
    translate([-fc_size / 2 + 2, -10, pcb_t / 2 + 4.5]) rotate([0, 0, 90]) usb_c();

    // UART headers: flow sensor, receiver, video.
    translate([fc_size / 2 - 4, 10, pcb_t / 2 + 1.4]) jst_sh(6);
    translate([fc_size / 2 - 4, 1, pcb_t / 2 + 1.4]) jst_sh(6);

    // Underside: the encapsulated ESC block and the four motor pads.
    translate([0, 0, -pcb_t / 2 - 2]) chip(26, 26, 4, [0.45, 0.45, 0.48]);
    for (sx = [-1, 1], sy = [-1, 1])
      translate([sx * 15, sy * 15, -pcb_t / 2 - 0.3])
        color(copper) cylinder(h = 0.6, d = 3, center = true, $fn = 16);
  }
}

// EMAX Wyvern Link Alpha, stacked above the flight controller on standoffs.
// The 25.5 mm pattern is published; the board outline and the heatsink are
// placeholders, so they stay translucent.
module video_unit() {
  // Standoffs between the two boards, which is where the stack height comes
  // from rather than from a guessed gap.
  for (sx = [-1, 1], sy = [-1, 1])
    translate([sx * fc_mount / 2, sy * fc_mount / 2, (fc_z + vtx_z) / 2])
      standoff(vtx_z - fc_z);

  translate([0, 0, vtx_z]) {
    color(pcb_black, placeholder_alpha)
      difference() {
        cube([vtx_size, vtx_size, pcb_t], center = true);
        for (sx = [-1, 1], sy = [-1, 1])
          translate([sx * fc_mount / 2, sy * fc_mount / 2, 0])
            cylinder(h = pcb_t + 1, d = 2.2, center = true, $fn = 20);
      }
    // SoC under a heatsink; this unit runs hot enough that RunCam quote 15 W
    // for the comparable WiFiLink and Mario ships a radiator and a fan.
    color([0.55, 0.56, 0.60], placeholder_alpha)
      translate([0, 0, pcb_t / 2 + 3]) cube([18, 18, 6], center = true);
    color([0.85, 0.85, 0.88], placeholder_alpha)
      translate([-vtx_size / 2 + 3, 0, pcb_t / 2 + 1.4]) ipex();
  }

  // Camera module on its ribbon, out at the nose, looking forward.
  translate([cam_x, 0, cam_z]) {
    color(pcb_black, placeholder_alpha) cube([14, 14, pcb_t], center = true);
    color(plastic_black, placeholder_alpha)
      rotate([0, 90, 0]) cylinder(h = lens_len, d = lens_d, $fn = 32);
  }
}

// SpeedyBee ELRS Nano: a 10.4 x 18.4 mm board, an SX1280 and an ESP8285, and a
// T-antenna on an IPEX pigtail that has to end up somewhere clear of carbon.
module receiver() {
  translate([rx_x, rx_y, rx_z]) {
    pcb(rx_l, rx_w, t = 1.0, col = pcb_black);
    translate([-3, 0, 1.2]) chip(5, 5, 1.2, [0.30, 0.30, 0.32]);
    translate([4, 0, 1.0]) chip(4, 3, 0.8, [0.30, 0.30, 0.32]);
    translate([rx_l / 2 - 2, 0, 1.3]) ipex();
    // The antenna, drawn because where it sits is a real constraint.
    color([0.85, 0.75, 0.20])
      translate([rx_l / 2 + 12, 0, 1]) rotate([0, 90, 0])
        cylinder(h = 24, d = 1.2, center = true, $fn = 12);
  }
}

// MicoAir MTF-02P, 21.6 x 16 x 6.5 mm, looking down: a flow camera at 42
// degrees beside a 2 degree time-of-flight laser.
module optical_flow() {
  translate([flow_x, 0, -plate_thickness - flow_h / 2]) {
    pcb(flow_l, flow_w, t = 1.2, col = pcb_black);
    translate([0, 0, 1.4]) chip(8, 8, 2, [0.20, 0.20, 0.22]);
    // Downward optics on the underside.
    color(plastic_black)
      translate([-4, 0, -2]) cylinder(h = 3, d = 6, center = true, $fn = 24);
    color([0.35, 0.05, 0.05])
      translate([5, 0, -1.6]) cylinder(h = 2.4, d = 3, center = true, $fn = 20);
    translate([0, flow_w / 2 - 2, 1.5]) jst_sh(4);
  }
}

module battery() {
  // On top, which is how this frame carries it. Underneath it would hang below
  // the ducts and become the first thing to meet the ground. Sitting behind the
  // centre is also what balances the lidar hanging off the nose.
  part([0.55, 0.15, 0.15])
    translate([batt_x, 0, prop_z + prop_thickness + batt_h / 2 + 2])
      cube([batt_l, batt_w, batt_h], center = true);
}

module ld06() {
  // The mast the clearance above forces.
  part([0.25, 0.25, 0.28], false)
    translate([ld06_x, 0, (prop_z + ld06_z - ld06_h / 2) / 2])
      cube([12, 12, ld06_z - ld06_h / 2 - prop_z], center = true);
  part([0.85, 0.20, 0.20], false)
    translate([ld06_x, 0, ld06_z]) {
      cube([ld06_l, ld06_w, ld06_h], center = true);
      // The optical window, drawn as a band so its height can be compared with
      // the propeller plane.
      part([0.15, 0.15, 0.15], false)
        translate([0, 0, -ld06_h / 2 + ld06_window_z])
          cylinder(h = 6, d = ld06_l + 1, center = true, $fn = 48);
    }
}

// ----------------------------------------------------------------- questions
// What the model is for: each of these draws a clearance the build has to keep.

// The discs the propellers sweep. Anything intersecting these is a crash.
module prop_discs() {
  for (p = motor_positions)
    %translate([p[0], p[1], prop_z])
      cylinder(h = prop_thickness, d = prop_d, $fn = 96);
}

// The LD06 has to see forward. Drawn as the horizontal slab its scan plane
// sweeps, so the ducts and propellers can be checked against it.
module lidar_sightline() {
  // A forward beam rather than a full disc: a 220 mm slab covered the whole
  // drawing and hid the thing it was meant to show.
  %translate([ld06_x + 60, 0, ld06_z - ld06_h / 2 + ld06_window_z])
    cube([120, 60, 3], center = true);
}

// The MTF-02P looks down. Its flow camera is 42 degrees; the cone must reach
// the floor without clipping the frame or the battery.
module flow_cone() {
  %translate([20, 0, -plate_thickness])
    rotate([180, 0, 0])
      cylinder(h = 120, r1 = 0, r2 = 120 * tan(21), $fn = 48);
}

// ------------------------------------------------------- viewing the stack
// The battery sits over the boards, so a close-up of the electronics needs it
// out of the way. `explode` pulls the stack apart vertically, which is the only
// way to see a board sandwich at all.
explode      = 0;
show_battery = true;
show_ducts   = true;

// ------------------------------------------------------------------ assembly
module drone(show_checks = false) {
  frame_plate();
  for (p = motor_positions) {
    if (show_ducts) duct(p[0], p[1]);
    motor(p[0], p[1]);
    propeller(p[0], p[1]);
  }
  translate([0, 0, explode])      flight_controller();
  translate([0, 0, explode * 2])  video_unit();
  translate([0, 0, explode])      receiver();
  translate([0, 0, -explode])     optical_flow();
  if (show_battery) translate([0, 0, explode * 3]) battery();
  ld06();

  if (show_checks) {
    prop_discs();
    lidar_sightline();
    flow_cone();
  }
}

show_checks = false;
drone(show_checks);
