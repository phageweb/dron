/*
 * Independent concept CAD for the OpenIPC CineLog30 V3 build.
 *
 * Coordinate convention (millimetres): X forward, Y left, Z up.
 * Origin: centre of the upper surface of the carbon plate.
 *
 * Visual confidence convention:
 *   normal component colours = published/verified outer dimensions
 *   magenta / amber           = placeholder geometry or placement
 *   transparent red           = propeller plane / keep-out
 *
 * This is a packaging model, not a manufacturable frame drawing.  Dimensions
 * labelled PLACEHOLDER below must be replaced by measurements or drawings.
 */

$fn = 72;

// Customizer ---------------------------------------------------------------
battery_variant = "compact"; // [compact,long]
show_prop_keepouts = true;
show_sensor_fields = true;
show_usb_service_envelope = true;
show_axes = true;
show_cg = true;

// Published / verified geometry -------------------------------------------
motor_xy = 45.25;
prop_d = 76;
plate_t = 2.5;
motor_d = 18.2;
motor_h = 13.8;
shaft_d = 1.5;
fc_size = [36, 36, 8];
fc_mount = 25.5;
fc_hole_d = 3;
rx_size_xy = [18.4, 10.4];
mtf_size = [21.6, 16, 6.5];
ld06_size = [38.59, 38.59, 33.5];
ld06_turret_d = 35.29;
ld06_turret_h = 12.8;
ld06_window_h = 7.8;
camera_lens_d = 19;
battery_compact = [60, 31, 27];
battery_long = [76, 17, 28];

// Packaging positions ------------------------------------------------------
prop_z = motor_h + 1;
ld06_clearance = 2;
// z=22 is 2 mm above the PLACEHOLDER duct top (20 mm) and 7.2 mm above
// the verified propeller plane. Recompute after measuring the real duct.
ld06_pos = [47, 0, 22];                       // bottom-centre datum
battery_pos = [-28, 0, 24.5];                // bottom-centre datum
fc_pos = [0, 0, 6];                          // envelope centre
vtx_pos = [4, 0, 16];                        // envelope centre, PLACEHOLDER
rx_pos = [-27, 13, 6];                       // PLACEHOLDER position/thickness
mtf_pos = [6, 0, -2.5 - mtf_size[2]];        // bottom-mounted, lower Z datum
camera_pos = [51, 0, 8];                     // body centre, PLACEHOLDER

// PLACEHOLDER frame geometry: only plate thickness and mounting patterns are
// verified.  These numbers intentionally remain conspicuous in the source.
duct_inner_d_PLACEHOLDER = 79;
duct_wall_PLACEHOLDER = 3.5;
duct_z_min_PLACEHOLDER = -5;
duct_h_PLACEHOLDER = 25;
arm_width_PLACEHOLDER = 15;
camera_body_PLACEHOLDER = [19, 21, 19];
vtx_size_PLACEHOLDER = [30, 30, 7];
rx_thickness_PLACEHOLDER = 2;
usb_plug_PLACEHOLDER = [10, 16, 5];
usb_board_x_PLACEHOLDER = -5;

motor_positions = [
    [ motor_xy, -motor_xy], // front right
    [-motor_xy,  motor_xy], // rear left
    [ motor_xy,  motor_xy], // front left
    [-motor_xy, -motor_xy]  // rear right
];

// Published/vendor masses plus an explicit central allowance for wiring,
// fasteners and mounts.  Positions are lumped estimates for CG exploration.
mass_items = [
    [78.0,  [  0, 0, -1.25], "frame"],
    [42.0,  [  0, 0,  6.90], "motors"],
    [ 6.6,  [  0, 0, prop_z], "propellers"],
    [10.0,  fc_pos,            "FC/AIO"],
    [13.76, vtx_pos,           "Wyvern incl. camera (lumped)"],
    [ 1.3,  [-27, 0, 6],       "RX and antenna"],
    [ 1.5,  [6, 0, -7.25],     "MTF-02P"],
    [71.5,  [-28, 0, 38.0],    "battery midpoint mass"],
    [42.0,  [47, 0, 38.75],    "LD06"],
    [27.3,  [0, 0, 4],         "wiring/fasteners/mounts estimate"]
];

function sum_values(v, i=0) = i >= len(v) ? 0 : v[i] + sum_values(v, i+1);
function total_mass(items) = sum_values([for (item=items) item[0]]);
function cg_axis(items, axis) =
    sum_values([for (item=items) item[0] * item[1][axis]]) / total_mass(items);
cg = [cg_axis(mass_items, 0), cg_axis(mass_items, 1), cg_axis(mass_items, 2)];

echo(str("Estimated model mass [g]: ", total_mass(mass_items)));
echo(str("Estimated CG [mm] (X,Y,Z): ", cg));
echo(str("LD06 bottom / prop plane / clearance [mm]: ",
         ld06_pos[2], " / ", prop_z, " / ", ld06_pos[2]-prop_z));

// Palette ------------------------------------------------------------------
C_CARBON = [0.07, 0.08, 0.09, 1.0];
C_METAL = [0.55, 0.58, 0.62, 1.0];
C_MOTOR = [0.18, 0.19, 0.20, 1.0];
C_PCB = [0.04, 0.29, 0.22, 1.0];
C_SENSOR = [0.10, 0.55, 0.83, 1.0];
C_BATTERY = [0.78, 0.12, 0.12, 1.0];
C_PLACEHOLDER = [0.95, 0.10, 0.72, 0.42];
C_ESTIMATE = [1.00, 0.58, 0.05, 0.78];
C_KEEPOUT = [1.00, 0.05, 0.05, 0.11];
C_FIELD = [0.15, 0.90, 0.36, 0.13];
C_SERVICE = [0.10, 0.82, 1.00, 0.22];

// Generic helpers ----------------------------------------------------------
module rounded_box(size, r=2) {
    translate([0, 0, -size[2]/2])
        linear_extrude(height=size[2])
            offset(r=r)
                square([size[0]-2*r, size[1]-2*r], center=true);
}

module ring(outer_d, inner_d, h) {
    difference() {
        cylinder(d=outer_d, h=h);
        translate([0,0,-0.1]) cylinder(d=inner_d, h=h+0.2);
    }
}

module line_3d(a, b, d=0.7) {
    v = b-a;
    length = norm(v);
    translate(a)
        rotate([0, acos(v[2]/length), atan2(v[1], v[0])])
            cylinder(d=d, h=length);
}

module crosshair(p, size=5, d=0.7) {
    translate(p) {
        line_3d([-size,0,0], [size,0,0], d);
        line_3d([0,-size,0], [0,size,0], d);
        line_3d([0,0,-size], [0,0,size], d);
    }
}

// Frame and propulsion -----------------------------------------------------
module plate_2d() {
    difference() {
        union() {
            square([42, 42], center=true); // PLACEHOLDER central outline
            for (p=motor_positions)
                hull() {
                    circle(d=arm_width_PLACEHOLDER);
                    translate(p) circle(d=20);
                }
        }
        // PLACEHOLDER MTF optical opening; aperture position is not published.
        translate([mtf_pos[0], mtf_pos[1]])
            offset(r=2) square([10, 10], center=true);
    }
}

module carbon_plate() {
    color(C_CARBON)
        translate([0,0,-plate_t]) linear_extrude(height=plate_t) plate_2d();

    // Magenta rim says that the plan outline, unlike thickness, is estimated.
    color(C_PLACEHOLDER)
        translate([0,0,0.02]) linear_extrude(height=0.35)
            difference() {
                offset(r=0.9) plate_2d();
                plate_2d();
            }
}

module duct(p) {
    outer_d = duct_inner_d_PLACEHOLDER + 2*duct_wall_PLACEHOLDER;
    color(C_PLACEHOLDER)
        translate([p[0], p[1], duct_z_min_PLACEHOLDER])
            ring(outer_d, duct_inner_d_PLACEHOLDER, duct_h_PLACEHOLDER);
}

module motor_and_prop(p, index=0) {
    translate([p[0], p[1], 0]) {
        color(C_MOTOR) cylinder(d=motor_d, h=motor_h);
        color(C_METAL) translate([0,0,motor_h]) cylinder(d=shaft_d, h=3.2);
        color([0.18,0.18,0.20,1]) translate([0,0,prop_z-0.6])
            cylinder(d=9, h=1.2);

        // Simplified but dimensionally bounded three-blade propeller.
        color([0.42,0.46,0.50,0.86])
            translate([0,0,prop_z-0.35])
                rotate([0,0,index*17])
                    linear_extrude(height=0.7)
                        for (a=[0:120:240]) rotate(a)
                            hull() {
                                translate([5,0]) circle(d=5);
                                translate([prop_d/2-4,3]) scale([1.5,0.8]) circle(d=6);
                            }

        if (show_prop_keepouts)
            color(C_KEEPOUT)
                translate([0,0,prop_z-0.15]) cylinder(d=prop_d, h=0.3);
    }
}

module frame_and_propulsion() {
    carbon_plate();
    for (i=[0:len(motor_positions)-1]) {
        duct(motor_positions[i]);
        motor_and_prop(motor_positions[i], i);
    }
}

// Avionics -----------------------------------------------------------------
module mounting_holes(pattern, d, h) {
    for (x=[-pattern/2, pattern/2], y=[-pattern/2, pattern/2])
        translate([x,y,-h/2-0.1]) cylinder(d=d, h=h+0.2);
}

module flight_controller() {
    translate(fc_pos) {
        color([C_SENSOR[0], C_SENSOR[1], C_SENSOR[2], 0.13])
            rounded_box(fc_size, 2);

        color(C_PCB)
            difference() {
                rounded_box([36,36,1.6], 2);
                mounting_holes(fc_mount, fc_hole_d, 2);
            }

        // Published hole pattern; simplified metal vibration hardware.
        color(C_METAL)
            for (x=[-fc_mount/2,fc_mount/2], y=[-fc_mount/2,fc_mount/2])
                translate([x,y,-4]) ring(5,fc_hole_d,8);

        // Board forward arrow (+X).
        color([1,1,1,1]) translate([10,8,0.86])
            linear_extrude(height=0.2)
                polygon([[0,3],[-2,-2],[0,-1],[2,-2]]);

        // USB-C is on the +Y board edge when the arrow faces +X.  Connector
        // envelope is estimated from the official product photograph.
        color(C_METAL)
            translate([usb_board_x_PLACEHOLDER, 19.5, 0])
                rounded_box([9,7,3.4], 1);
    }
}

module vtx_board() {
    translate(vtx_pos) {
        color(C_ESTIMATE)
            difference() {
                rounded_box(vtx_size_PLACEHOLDER, 2);
                mounting_holes(25.5, 2.5, vtx_size_PLACEHOLDER[2]+0.2);
            }
        color([0.35,0.35,0.38,1]) translate([0,0,4.1])
            rounded_box([15,15,1.2],1);
    }
}

module receiver() {
    translate(rx_pos) {
        color(C_PCB) rounded_box([rx_size_xy[0],rx_size_xy[1],rx_thickness_PLACEHOLDER],1);
        // PLACEHOLDER thickness and placement are amber-rimmed.
        color(C_ESTIMATE) translate([0,0,1.1])
            rounded_box([rx_size_xy[0]+0.6,rx_size_xy[1]+0.6,0.35],1);
    }
}

module mtf_sensor() {
    // Lower datum: body lives below the carbon plate and looks down (-Z).
    translate(mtf_pos) {
        color(C_SENSOR) translate([0,0,mtf_size[2]/2])
            rounded_box(mtf_size, 1.2);
        color([0.05,0.08,0.10,1]) translate([0,0,-0.35]) cylinder(d=6,h=0.7);

        if (show_sensor_fields)
            color(C_FIELD)
                translate([0,0,-60])
                    cylinder(h=60, r1=2+60*tan(21), r2=2);
    }
}

module camera_and_view() {
    body = camera_body_PLACEHOLDER;
    translate(camera_pos) {
        color(C_ESTIMATE) rounded_box(body,2);
        color([0.10,0.10,0.12,1])
            translate([body[0]/2,0,0]) rotate([0,90,0])
                cylinder(d=camera_lens_d,h=5);
        color([0.25,0.45,0.75,0.9])
            translate([body[0]/2+4.7,0,0]) rotate([0,90,0])
                cylinder(d=11,h=0.8);

        // PLACEHOLDER 50 degree horizontal/vertical packaging cone.
        if (show_sensor_fields)
            color(C_FIELD)
                translate([body[0]/2+5.5,0,0]) rotate([0,90,0])
                    cylinder(h=65, r1=0, r2=30);
    }
}

// Payloads -----------------------------------------------------------------
module battery() {
    b = battery_variant == "long" ? battery_long : battery_compact;
    translate([battery_pos[0],battery_pos[1],battery_pos[2]+b[2]/2]) {
        color(C_BATTERY) rounded_box(b,3);
        color([0.08,0.08,0.09,1]) rounded_box([16,b[1]+2,b[2]+1],1);
        color([1,1,1,0.8]) translate([0,-b[1]/2-0.25,0])
            rotate([90,0,0]) linear_extrude(height=0.5)
                text(str("4S 750 / ", battery_variant), size=4,
                     halign="center", valign="center");
    }
}

module ld06() {
    translate(ld06_pos) {
        // Datasheet envelope: 38.59 square base, 33.5 overall height.
        color(C_SENSOR)
            difference() {
                translate([0,0,(ld06_size[2]-ld06_turret_h)/2])
                    rounded_box([ld06_size[0],ld06_size[1],
                                 ld06_size[2]-ld06_turret_h],3);
                // Datasheet shows two diagonal 4.8 mm mounting holes on a
                // 28.2 mm diagonal spacing. Counterbores are simplified.
                for (p=[[-14.1,-14.1],[14.1,14.1]])
                    translate([p[0],p[1],-0.1]) cylinder(d=4.8,h=21);
            }

        turret_z = ld06_size[2]-ld06_turret_h;
        color([0.17,0.20,0.23,1]) translate([0,0,turret_z])
            cylinder(d=ld06_turret_d,h=ld06_turret_h);

        // Optical window band: published 7.8 mm high and left unobstructed.
        color([0.02,0.03,0.04,0.82]) translate([0,0,turret_z])
            ring(ld06_turret_d+0.25,ld06_turret_d-0.55,ld06_window_h);

        // PLACEHOLDER mounting shelf, visually magenta.
        color(C_PLACEHOLDER) translate([0,0,-1])
            rounded_box([43,43,2],3);
    }
}

module usb_service_envelope() {
    if (show_usb_service_envelope) {
        // Straight plug/cable path. It deliberately exposes the clash with
        // the PLACEHOLDER left-side duct: plan for a right-angle extension.
        plug_z = fc_pos[2];
        color(C_SERVICE)
            translate([usb_board_x_PLACEHOLDER,
                       (22 + 72)/2,
                       plug_z])
                rounded_box([usb_plug_PLACEHOLDER[0],50,
                             usb_plug_PLACEHOLDER[2]],1);
        color([1,0.1,0.1,0.55])
            translate([usb_board_x_PLACEHOLDER,45,plug_z])
                rounded_box([10,18,5.5],1);
    }
}

module axes() {
    if (show_axes) {
        color([1,0.18,0.12,1]) {
            line_3d([0,0,0],[32,0,0],1.1);
            translate([34,0,0]) rotate([90,0,90]) cylinder(d1=3,d2=0,h=5);
            translate([39,-2,0.5]) linear_extrude(0.4) text("+X FRONT",size=4);
        }
        color([0.15,0.85,0.25,1]) {
            line_3d([0,0,0],[0,30,0],1.1);
            translate([0,32,0]) rotate([-90,0,0]) cylinder(d1=3,d2=0,h=5);
        }
        color([0.15,0.42,1,1]) line_3d([0,0,0],[0,0,30],1.1);
    }
}

module assembly() {
    frame_and_propulsion();
    flight_controller();
    vtx_board();
    receiver();
    mtf_sensor();
    camera_and_view();
    battery();
    ld06();
    usb_service_envelope();
    axes();

    if (show_cg) {
        color([1,1,0.05,1]) {
            translate(cg) sphere(d=5);
            crosshair(cg,8,0.65);
        }
    }
}

assembly();
