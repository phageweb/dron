// Run with -D 'part="check"'. Expected result: empty geometry.
include <pavo20_pro_assembly.scad>
assert(part=="check", "Use -D part=\"check\"");
module rotor_sweep() {
    for(x=[-1,1],y=[-1,1]) translate([x*motor_xy,y*motor_xy,propeller_z-1])
        cylinder(d=propeller_d,h=2,$fn=128);
}
// Printed geometry must clear the full swept disk, not just pictured blades.
intersection() {
    union() {
        base();
        camera_transform() adapter();
        if(lidar_enabled) translate([0,0,lidar_mount_z]) lidar_module();
    }
    rotor_sweep();
}
intersection() { base(); fc_envelope(); }
// The base intentionally rests on carbon at z=0. Exclude only the top 0.02 mm
// from this test: coplanar contact is not a material collision.
intersection() { base(); carbon_reference(top_clearance=eps); }
intersection() { base(); camera_transform() adapter(); }
intersection() { camera_transform() adapter(); carbon_reference(); }
intersection() { fc_envelope(); carbon_reference(); }
intersection() { fc_envelope(); rx_envelope(); }
intersection() { fc_envelope(); battery_envelope(); }
intersection() { rx_envelope(); battery_envelope(); }
intersection() {
    union() { fc_envelope(); rx_envelope(); battery_envelope(); }
    rotor_sweep();
}
if(lidar_enabled) intersection() {
    translate([0,0,lidar_mount_z]) lidar_module();
    translate([0,0,deck_z+vtx_standoff_height+4]) cube([23.5,23.5,8],center=true);
}
// Include the fasteners and GPS omitted in the first review. Require 0.4 mm
// radial clearance around frame heads, in addition to the actual envelope.
if(lidar_enabled) intersection() {
    translate([0,0,lidar_mount_z]) lidar_module();
    frame_heads(clearance=0.4);
}
// Ignore only the intended coplanar seating surface of the heads.
intersection() { base(); frame_heads(bottom_clearance=eps); }
intersection() { base(); gps_envelope(); }
intersection() { base(); gps_cable_envelope(); }
intersection() {
    union() { gps_envelope(); gps_cable_envelope(); }
    antenna_transform() cylinder(d=antenna_diameter,h=antenna_reference_length);
}
if(lidar_enabled) intersection() {
    translate([0,0,lidar_mount_z]) lidar_module();
    union() { gps_envelope(); gps_cable_envelope(); camera_transform() camera_reference(); }
}
intersection() { base(); camera_transform() camera_reference(); }
// The lower edge of the rotating optical band must exceed the antenna envelope.
assert(lidar_bottom_z+22.2 > deck_z+base_thickness-0.3+antenna_reference_length*cos(antenna_tilt)+antenna_diameter/2,
       "Antenna may obstruct the lidar optical band");
