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

// ------------------------------------------------------------------- helpers
motor_positions = [
  [ arm_xy, -arm_xy], // motor_1 front right
  [-arm_xy,  arm_xy], // motor_2 rear left
  [ arm_xy,  arm_xy], // motor_3 front left
  [-arm_xy, -arm_xy], // motor_4 rear right
];

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

module flight_controller() {
  part([0.10, 0.45, 0.20])
    translate([0, 0, 3])
      cube([fc_size, fc_size, fc_h], center = true);
  // The 25.5 mm pattern, drawn so a mount can be checked against it.
  for (sx = [-1, 1], sy = [-1, 1])
    part([0.5, 0.5, 0.5])
      translate([sx * fc_mount / 2, sy * fc_mount / 2, 3])
        cylinder(h = fc_h + 2, d = 2, center = true, $fn = 16);
}

module video_unit() {
  part([0.15, 0.15, 0.18], false)
    translate([12, 0, 14])
      cube([vtx_size, vtx_size, vtx_h], center = true);
  part([0.05, 0.05, 0.05], false)
    translate([12 + vtx_size / 2, 0, 14])
      rotate([0, 90, 0])
        cylinder(h = lens_len, d = lens_d, $fn = 32);
}

module receiver() {
  part([0.20, 0.20, 0.25])
    translate([-20, 18, 4])
      cube([rx_l, rx_w, rx_h], center = true);
}

module optical_flow() {
  part([0.85, 0.85, 0.78])
    translate([20, 0, -plate_thickness - flow_h / 2])
      cube([flow_l, flow_w, flow_h], center = true);
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

// ------------------------------------------------------------------ assembly
module drone(show_checks = false) {
  frame_plate();
  for (p = motor_positions) {
    duct(p[0], p[1]);
    motor(p[0], p[1]);
    propeller(p[0], p[1]);
  }
  flight_controller();
  video_unit();
  receiver();
  optical_flow();
  battery();
  ld06();

  if (show_checks) {
    prop_discs();
    lidar_sightline();
    flow_cone();
  }
}

show_checks = false;
drone(show_checks);
