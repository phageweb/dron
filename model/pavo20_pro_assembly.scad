// Pavo20 Pro / Ascent Lite+ / detachable lidar. Millimetres, grams.
// X right, Y rear, Z up. Z=0 is the TOP of the upper carbon plate.
include <camera_insert.scad>
include <print_mass_properties.scad>

/* [Zobrazeni a export] */
part = "drone"; // [drone:Cely dron,assembly:Drzak sestava,base:Zakladna,insert:Objimka kamery,lidar:Modul lidaru,print:Tiskove dily]
lidar_enabled = true;
show_hardware = true;
show_cg = true;
show_scan = true;

/* [Zakladna Pavo20 Pro] */
frame_hole_x = 26;
frame_hole_y = 45.6;
// Direct M2 attachment assumption; measure OEM dampers if retaining them.
frame_hole_d = 2.3;
foot_diameter = 7;
base_thickness = 3.2;
rail_width = 3.2;
// VTX heads sit flush underneath; the same head size is recessed atop the bridge.
underside_head_d = 4.2;
underside_head_depth = 1.6;
frame_head_d = 4.2;
frame_head_h = 2;

/* [Kamera] */
camera_angle = 20; // [0:5:40]
camera_y = -32;
camera_axis_z = 14;
cheek_thickness = 2.4;
camera_bolt_d = 2.2;

/* [VTX] */
vtx_hole_pitch = 20;
vtx_hole_d = 2.3;
vtx_standoff_height = 6.4;
vtx_post_d = 5.8;

/* [Antena - overit prumer] */
antenna_diameter = 3;
antenna_clearance = 0.2;
antenna_wall = 1.6;
antenna_slit = 1.4;
antenna_tilt = 25;
antenna_y = 30;
antenna_length = 12;
tie_width = 2.8;
antenna_reference_length = 32;

/* [GPS WS-M181] */
gps_y = 49;
gps_width = 18;
gps_length = 18;
gps_height = 4.6;
gps_clearance = 0.8; // Total: 0.4 mm each side.
gps_wall = 1.6;
gps_rim_height = 2;
gps_tape_thickness = 1;
// Part of the existing wiring/tape allowance, not added twice.
gps_tape_mass = 0.2;

/* [Odnimatelny D500 STL-19P] */
// Datasheet v1.0: 54 x 46.29 x 35 including mounting ears; 3 holes.
lidar_bottom_z = 25;
lidar_plate_thickness = 3;
lidar_dock_x = 26;
lidar_dock_y = 34;
lidar_dock_bolt_d = 2.3;
lidar_sensor_bolt_d = 2.6;
lidar_nut_af = 4.2;
lidar_nut_depth = 1.8;
lidar_mass = 47;
lidar_cg_x_offset = 0;
lidar_cg_y_offset = 0;
lidar_cg_z_offset = 17.5;

/* [Baterie a vyvazeni] */
// Purchased packs: spec/realna_stavba_dronu/13_nakoupeno.md.
battery_variant = "750"; // [750:Tattu 750mAh 69g,550:Tattu 550mAh 57g]
auto_balance_battery = true;
battery_manual_y = 0;
battery_manual_x = 0;
battery_travel = 10;
// Published component masses; wiring and positions remain estimates.
frame_mass = 28.7;
motors_mass = 24.8;
props_mass = 2.32;
fc_mass = 10;
rx_mass = 1.6;
flow_mass = 1.5;
gps_mass = 4.3;
wiring_mass = 13.36;
// Split of the documented 10.5 g kit is an estimate, sum remains 10.5 g.
camera_mass = 2;
vtx_mass = 8;
antenna_mass = 0.5;
// Volumes and local centroids are refreshed from STL by refresh_model.py.
petg_density = 1.25; // g/cm3, solid-volume estimate.
tpu_density = 1.20;
// Positive overrides allow weighing the actual printed parts.
base_measured_mass = 0;
insert_measured_mass = 0;
lidar_mount_measured_mass = 0;
// Estimated complete camera CG relative to its pivot, in print coordinates.
camera_cg_depth_offset = -3;

/* [Referencni model dronu] */
wheelbase = 93.7;
duct_outer_d = 67;
duct_inner_d = 57;
propeller_d = 55.88;
carbon_thickness = 2;
// Pusher layout: motors and FC hang BELOW the upper carbon plate.
// Vertical envelopes are design estimates; measure the actual dampers/motors.
motor_body_height = 12;
propeller_z = -15.5;
fc_bottom_z = -11;
rx_z = -13.5;
// Manufacturer frame drawing: upper carbon to duct top = 27.3 - 16.9 mm.
duct_top_z = -10.4;
duct_height = 7.5;
// Battery enters the slot below FC/RX; do not place it directly under carbon.
battery_top_z = -18;

/* [Hidden] */
deck_z = 0;
antenna_bore = antenna_diameter+antenna_clearance;
antenna_outer = antenna_bore+2*antenna_wall;
fork_x = mount_width/2+cheek_thickness/2;
gps_outer_w = gps_width+gps_clearance+2*gps_wall;
gps_outer_l = gps_length+gps_clearance+2*gps_wall;
gps_bottom_z = base_thickness+gps_tape_thickness;
gps_z = gps_bottom_z+gps_height/2;
lidar_mount_z = deck_z+base_thickness;
lidar_module_height = lidar_bottom_z-lidar_mount_z;
lidar_plate_z = lidar_module_height-lidar_plate_thickness;
// Derived from datasheet p.7, origin at square body centre, +Y rear.
// Side row = (42.69 - 31.92) - 38.59/2; rear hole = 42.69 - 38.59/2.
lidar_holes = [[-23.4,-8.525],[23.4,-8.525],[0,23.395]];
battery_width = battery_variant=="750" ? 18 : 16;
battery_length = battery_variant=="750" ? 77 : 68;
battery_height = battery_variant=="750" ? 28 : 26;
battery_mass = battery_variant=="750" ? 69 : 57;
battery_z = battery_top_z-battery_height/2;
flow_z = battery_top_z-6.5/2;
motor_xy = wheelbase/(2*sqrt(2));
base_mass = base_measured_mass>0 ? base_measured_mass : base_volume_mm3*petg_density/1000;
insert_mass = insert_measured_mass>0 ? insert_measured_mass : insert_volume_mm3*tpu_density/1000;
lidar_mount_mass = lidar_mount_measured_mass>0 ? lidar_mount_measured_mass : lidar_volume_mm3*petg_density/1000;
function camera_point(p) = let(a=-90-camera_angle,q=p-[0,pivot_height,pivot_z])
    [q[0],camera_y+q[1]*cos(a)-q[2]*sin(a),camera_axis_z+q[1]*sin(a)+q[2]*cos(a)];
insert_cg = camera_point(insert_print_cg);
camera_cg = camera_point([0,pivot_height,pivot_z+camera_cg_depth_offset]);
lidar_mount_cg = [lidar_print_cg[0],-lidar_print_cg[1],lidar_bottom_z-lidar_print_cg[2]];
antenna_cg = [0,antenna_y+antenna_reference_length/2*sin(antenna_tilt),
    deck_z+base_thickness-0.3+antenna_reference_length/2*cos(antenna_tilt)];
function mass_at(m,p) = concat([m],p);
mass_names = concat(["frame","motors","props","FC","RX","MTF-02P","GPS",
    "wiring_except_GPS_tape","GPS_tape","base","camera_insert","camera","VTX","antenna"],
    lidar_enabled ? ["D500_bridge","D500"] : []);
// Items: mass, X, Y, Z. Unlike the old model, side-mounted flow affects lateral CG.
mass_items = concat([
    [frame_mass,0,0,-8], [motors_mass,0,0,-carbon_thickness-motor_body_height/2], [props_mass,0,0,propeller_z],
    [fc_mass,0,0,fc_bottom_z+4], [rx_mass,0,0,rx_z],
    [flow_mass,19,0,flow_z], [gps_mass,0,gps_y,gps_z],
    [wiring_mass-gps_tape_mass,0,0,-4],
    [gps_tape_mass,0,gps_y,base_thickness+gps_tape_thickness/2],
    mass_at(base_mass,base_print_cg),
    mass_at(insert_mass,insert_cg),
    mass_at(camera_mass,camera_cg),
    [vtx_mass,0,0,deck_z+vtx_standoff_height+4],
    mass_at(antenna_mass,antenna_cg)
],lidar_enabled ? [
    mass_at(lidar_mount_mass,lidar_mount_cg),
    [lidar_mass,lidar_cg_x_offset,lidar_cg_y_offset,lidar_bottom_z+lidar_cg_z_offset]
] : []);
function sum_values(v,i=0) = i>=len(v) ? 0 : v[i]+sum_values(v,i+1);
function moment(items,axis) = sum_values([for(item=items) item[0]*item[axis]]);
other_mass = sum_values([for(item=mass_items) item[0]]);
battery_target_y = -moment(mass_items,2)/battery_mass;
battery_y = auto_balance_battery ? max(-battery_travel,min(battery_travel,battery_target_y)) : battery_manual_y;
total_mass = other_mass+battery_mass;
battery_target_x = -moment(mass_items,1)/battery_mass;
battery_x_travel = max(0,(20-battery_width)/2-0.2);
battery_x = auto_balance_battery ? max(-battery_x_travel,min(battery_x_travel,battery_target_x)) : battery_manual_x;
cg_x = (moment(mass_items,1)+battery_mass*battery_x)/total_mass;
cg_y = (moment(mass_items,2)+battery_mass*battery_y)/total_mass;
cg_z = (moment(mass_items,3)+battery_mass*battery_z)/total_mass;
assert(frame_hole_d > 0 && foot_diameter-frame_hole_d >= 2.4);
assert(base_thickness-underside_head_depth >= 1.2);
assert(base_thickness-lidar_nut_depth >= 1.2);
assert(vtx_post_d-vtx_hole_d >= 2.4 && vtx_standoff_height>=base_thickness);
assert(antenna_slit>0 && antenna_slit<antenna_bore && antenna_wall>=1.2);
assert(camera_axis_z>outer_h/2+base_thickness+1);
assert(battery_mass>0 && battery_travel>=0 && lidar_mass>=0);
assert(petg_density>0 && tpu_density>0);
assert(gps_tape_mass>=0 && gps_tape_mass<=wiring_mass);
assert(gps_clearance>=0.4 && gps_wall>=1.2 && gps_tape_thickness>0);
assert(lidar_plate_z > 10);
assert(battery_variant=="750" || battery_variant=="550");
assert(part=="drone" || part=="assembly" || part=="base" || part=="insert" || part=="lidar" || part=="print" || part=="check");

module bar(a,b,d,h) {
    hull() for(p=[a,b]) translate([p[0],p[1],0]) cylinder(d=d,h=h);
}
module antenna_transform() {
    translate([0,antenna_y,deck_z+base_thickness-0.3]) rotate([-antenna_tilt,0,0]) children();
}
module antenna_holder() {
    antenna_transform() difference() {
        cylinder(d=antenna_outer,h=antenna_length);
        translate([-antenna_slit/2,0,-eps]) cube([antenna_slit,antenna_outer,antenna_length+2*eps]);
        translate([0,0,antenna_length/2-tie_width/2]) difference() {
            cylinder(d=antenna_outer+2,h=tie_width);
            translate([0,0,-eps]) cylinder(d=antenna_outer-0.6,h=tie_width+2*eps);
        }
    }
}
module camera_cheek(side) {
    difference() {
        hull() {
            translate([side*fork_x,camera_y,deck_z+base_thickness/2]) cube([cheek_thickness,12,base_thickness],center=true);
            translate([side*fork_x,camera_y,camera_axis_z]) rotate([0,90,0]) cylinder(d=8,h=cheek_thickness,center=true);
        }
        translate([side*fork_x,camera_y,camera_axis_z]) rotate([0,90,0]) cylinder(d=camera_bolt_d,h=cheek_thickness+2*eps,center=true);
    }
}
module lidar_dock_holes(h) {
    for(x=[-1,1],y=[-1,1])
        translate([x*lidar_dock_x/2,y*lidar_dock_y/2,-eps])
            cylinder(d=lidar_dock_bolt_d,h=h+2*eps);
}
module gps_holder() {
    // Two flat rails avoid the central antenna sleeve. All bottoms are z=0.
    for(side=[-1,1])
        bar([side*9,frame_hole_y/2],[side*9,gps_y-gps_outer_l/2+2],4,base_thickness);
    translate([0,gps_y,0]) {
        linear_extrude(base_thickness) rounded_rectangle(gps_outer_w,gps_outer_l,2);
        translate([0,0,base_thickness]) difference() {
            linear_extrude(gps_rim_height) difference() {
                rounded_rectangle(gps_outer_w,gps_outer_l,2);
                square([gps_width+gps_clearance,gps_length+gps_clearance],center=true);
            }
            // Wide front opening accepts an off-centre connector/cable.
            translate([-7,-gps_outer_l/2-eps,-eps]) cube([14,gps_wall+2*eps,gps_rim_height+2*eps]);
        }
    }
}
module gps_envelope() {
    translate([0,gps_y,gps_z]) cube([gps_width,gps_length,gps_height],center=true);
}
module gps_cable_envelope() {
    // Reserved connector space; route the wire forward along a side rail.
    translate([0,gps_y-gps_length/2-2,gps_bottom_z+1.5]) cube([12,4,3],center=true);
}
module frame_heads(clearance=0,bottom_clearance=0) {
    for(x=[-1,1],y=[-1,1])
        translate([x*frame_hole_x/2,y*frame_hole_y/2,base_thickness+bottom_clearance])
            cylinder(d=frame_head_d+2*clearance,h=frame_head_h-bottom_clearance);
}
module base() {
    difference() {
        union() {
            // Flat feet and rails sit directly on the upper carbon plate.
            for(x=[-1,1],y=[-1,1])
                translate([x*frame_hole_x/2,y*frame_hole_y/2,0]) cylinder(d=foot_diameter,h=base_thickness);
            translate([0,0,deck_z]) {
                for(side=[-1,1]) {
                    bar([side*frame_hole_x/2,-frame_hole_y/2],[side*frame_hole_x/2,frame_hole_y/2],rail_width,base_thickness);
                    bar([side*frame_hole_x/2,-frame_hole_y/2],[side*fork_x,camera_y],rail_width,base_thickness);
                    for(end=[-1,1]) {
                        bar([0,end*frame_hole_y/2],[side*frame_hole_x/2,end*frame_hole_y/2],4.4,base_thickness);
                        translate([side*lidar_dock_x/2,end*lidar_dock_y/2,0]) cylinder(d=7,h=base_thickness);
                    }
                }
                for(y=[-frame_hole_y/2,frame_hole_y/2,-vtx_hole_pitch/2,vtx_hole_pitch/2])
                    bar([-frame_hole_x/2,y],[frame_hole_x/2,y],rail_width,base_thickness);
                for(x=[-1,1],y=[-1,1]) translate([x*vtx_hole_pitch/2,y*vtx_hole_pitch/2,0]) cylinder(d=vtx_post_d,h=vtx_standoff_height);
                bar([0,frame_hole_y/2],[0,antenna_y],antenna_outer,base_thickness);
            }
            for(side=[-1,1]) camera_cheek(side);
            antenna_holder();
            gps_holder();
        }
        for(x=[-1,1],y=[-1,1]) {
            translate([x*frame_hole_x/2,y*frame_hole_y/2,-eps]) cylinder(d=frame_hole_d,h=base_thickness+2*eps);
            translate([x*vtx_hole_pitch/2,y*vtx_hole_pitch/2,deck_z-eps]) cylinder(d=vtx_hole_d,h=vtx_standoff_height+2*eps);
            translate([x*vtx_hole_pitch/2,y*vtx_hole_pitch/2,-eps]) cylinder(d=underside_head_d,h=underside_head_depth+eps);
            // Captive dock nuts enter from below before the base is fitted.
            translate([x*lidar_dock_x/2,y*lidar_dock_y/2,-eps]) cylinder(d=lidar_nut_af/cos(30),h=lidar_nut_depth+eps,$fn=6);
        }
        translate([0,0,deck_z]) lidar_dock_holes(base_thickness);
        antenna_transform() translate([0,0,-4]) cylinder(d=antenna_bore,h=antenna_length+4+eps);
    }
}
// Rigid removable four-column bridge. Print inverted, top plate on the bed.
module lidar_module() {
    difference() {
        union() {
            for(x=[-1,1],y=[-1,1])
                translate([x*lidar_dock_x/2,y*lidar_dock_y/2,0]) cylinder(d=6.4,h=lidar_module_height);
            translate([0,0,lidar_plate_z]) {
                // Support ring under the stationary housing, open centre for cooling.
                linear_extrude(lidar_plate_thickness) difference() {
                    rounded_rectangle(42,42,3);
                    rounded_rectangle(32,30,3);
                }
                for(p=lidar_holes) {
                    bar([p[0]*0.75,p[1]*0.75],p,7,lidar_plate_thickness);
                    translate([p[0],p[1],0]) cylinder(d=7,h=lidar_plate_thickness);
                }
            }
        }
        lidar_dock_holes(lidar_module_height);
        for(x=[-1,1],y=[-1,1])
            translate([x*lidar_dock_x/2,y*lidar_dock_y/2,lidar_module_height-underside_head_depth])
                cylinder(d=underside_head_d,h=underside_head_depth+eps);
        for(p=lidar_holes)
            translate([p[0],p[1],lidar_plate_z-eps]) cylinder(d=lidar_sensor_bolt_d,h=lidar_plate_thickness+2*eps);
    }
}
module camera_transform() {
    translate([0,camera_y,camera_axis_z]) rotate([-90-camera_angle,0,0]) translate([0,-pivot_height,-pivot_z]) children();
}
module printable_assembly() {
    color([0.15,0.45,0.57]) base();
    color([1,0.5,0.08]) camera_transform() adapter();
    if(lidar_enabled) color([0.6,0.3,0.8]) translate([0,0,lidar_mount_z]) lidar_module();
}
module hardware_reference() {
    camera_transform() camera_reference();
    color([0.25,0.27,0.3]) translate([0,0,deck_z+vtx_standoff_height+4]) cube([23.5,23.5,8],center=true);
    color([0.15,0.15,0.18]) antenna_transform() cylinder(d=antenna_diameter,h=antenna_reference_length);
    color([0.7,0.7,0.72]) frame_heads();
    color([0.8,0.75,0.45]) gps_envelope();
    for(side=[-1,1]) color([0.75,0.77,0.8])
        translate([side*(mount_width/2+cheek_thickness),camera_y,camera_axis_z]) rotate([0,-side*90,0]) {
            cylinder(d=2,h=cheek_thickness+screw_depth);
            translate([0,0,-1.4]) cylinder(d=3.8,h=1.4);
        }
    if(lidar_enabled) translate([0,0,lidar_bottom_z]) {
        color([0.2,0.23,0.25]) {
            linear_extrude(22.2) rounded_rectangle(38.59,38.59,4);
            for(p=lidar_holes) translate([p[0],p[1],0]) difference() {
                cylinder(d=7.2,h=1.5);
                translate([0,0,-eps]) cylinder(d=2.5,h=2);
            }
        }
        color([0.12,0.14,0.17]) translate([0,0,22.2]) cylinder(d=35.29,h=12.8);
        if(show_scan) %color([0.1,0.7,0.9,0.25]) translate([0,0,27.2]) difference() {
            cylinder(d=112,h=0.4);
            cylinder(d=106,h=1,center=true);
        }
    }
}

// Simplified reference airframe: not replacement flight parts or manufacturer CAD.
module carbon_reference(top_clearance=0) {
    translate([0,0,-carbon_thickness]) linear_extrude(carbon_thickness-top_clearance) difference() {
        union() {
            rounded_rectangle(30,54,4);
            for(x=[-1,1],y=[-1,1]) hull() {
                circle(d=8);
                translate([x*motor_xy,y*motor_xy]) circle(d=12);
            }
        }
        for(x=[-1,1],y=[-1,1])
            translate([x*frame_hole_x/2,y*frame_hole_y/2]) circle(d=frame_hole_d);
    }
}
module fc_envelope() {
    translate([0,0,fc_bottom_z+4]) cube([36,36,8],center=true);
}
module rx_envelope() {
    translate([0,0,rx_z]) cube([10.4,18.4,3],center=true);
}
module battery_envelope() {
    translate([battery_x,battery_y,battery_z]) cube([battery_width,battery_length,battery_height],center=true);
}
module drone_reference() {
    for(x=[-1,1],y=[-1,1]) translate([x*motor_xy,y*motor_xy,0]) {
        color([0.2,0.23,0.25,0.55]) translate([0,0,duct_top_z-duct_height]) difference() {
            cylinder(d=duct_outer_d,h=duct_height);
            translate([0,0,-eps]) cylinder(d=duct_inner_d,h=duct_height+2*eps);
        }
        color([0.35,0.36,0.4]) translate([0,0,-carbon_thickness-motor_body_height]) cylinder(d=15.4,h=motor_body_height);
        color([0.7,0.7,0.72]) translate([0,0,propeller_z]) cylinder(d=1.5,h=-carbon_thickness-propeller_z);
        color([0.2,0.65,0.8,0.4]) translate([0,0,propeller_z])
            for(a=[0,120,240]) rotate([0,0,a]) hull() {
                cylinder(d=5,h=0.8);
                translate([propeller_d/2-5,0,0]) cylinder(d=9,h=0.8);
            }
    }
    color([0.12,0.14,0.16]) carbon_reference();
    color([0.1,0.5,0.3]) fc_envelope();
    color([0.12,0.5,0.25]) rx_envelope();
    color([0.1,0.5,0.3]) translate([19,0,flow_z]) cube([16,21.6,6.5],center=true);
    color([0.25,0.3,0.7]) battery_envelope();
    color([0.12,0.12,0.12]) translate([battery_x,battery_y,battery_z]) difference() {
        cube([battery_width+2,6,battery_height+2],center=true);
        cube([battery_width,8,battery_height],center=true);
    }
}
module cg_reference() {
    color([1,0.15,0.1]) translate([cg_x,cg_y,cg_z]) sphere(d=3);
    color([1,0.8,0]) translate([0,0,-18]) cylinder(d=0.6,h=40);
}

echo(str("ESTIMATE ONLY: mass ",total_mass," g; CG [",cg_x,",",cg_y,",",cg_z,"] mm"));
echo(str("Battery X=",battery_x," mm; +X right"));
echo(str("Battery target Y=",battery_target_y,"; used Y=",battery_y," mm; +Y rear"));
if(abs(battery_target_y)>battery_travel) echo("WARNING: battery travel insufficient for longitudinal balance");
if(abs(battery_target_x)>battery_x_travel) echo("WARNING: battery travel insufficient for lateral balance");
if(!auto_balance_battery && (abs(battery_manual_y)>battery_travel || abs(battery_manual_x)>battery_x_travel))
    echo("WARNING: manual battery position exceeds modelled travel");
echo(balance=[total_mass,cg_x,cg_y,cg_z,battery_x,battery_y,battery_target_x,battery_target_y]);
echo(mass_items=concat(mass_items,[[battery_mass,battery_x,battery_y,battery_z]]));
echo(mass_names=concat(mass_names,["battery"]));
if(part=="base") base();
if(part=="insert") adapter();
if(part=="lidar") translate([0,0,lidar_module_height]) rotate([180,0,0]) lidar_module();
if(part=="print") {
    base();
    translate([36,0,0]) adapter();
    if(lidar_enabled) translate([-48,0,lidar_module_height]) rotate([180,0,0]) lidar_module();
}
if(part=="assembly" || part=="drone") {
    printable_assembly();
    if(show_hardware) {
        if(part=="drone") hardware_reference(); else %hardware_reference();
    }
    if(part=="drone") drone_reference();
    if(show_cg) %cg_reference();
}
