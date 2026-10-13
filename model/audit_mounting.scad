// Review of the supplied STL files, 2026-10-13. Does not modify the parts.
// Run with -D 'part="check"'. Nonempty output means a collision.
// Regression checks against the actual STL exports. Expected: empty geometry.
include <pavo20_pro_assembly.scad>
audit_case = "frame_heads_bridge"; // [frame_heads_bridge,gps_base,gps_antenna,gps_cable_base]
assert(part == "check", "Use -D 'part=\"check\"'");
assert(audit_case == "frame_heads_bridge" || audit_case == "gps_base" || audit_case == "gps_antenna" || audit_case == "gps_cable_base");

module supplied_bridge() {
    // Inverse of the print orientation, followed by assembly placement.
    translate([0,0,lidar_bottom_z]) rotate([180,0,0])
        import("3-d500_module.stl");
}
if(audit_case == "frame_heads_bridge") intersection() {
    supplied_bridge();
    frame_heads(clearance=0.4);
}
if(audit_case == "gps_base") intersection() {
    import("1-base.stl");
    gps_envelope();
}
if(audit_case == "gps_antenna") intersection() {
    antenna_transform() cylinder(d=antenna_diameter,h=antenna_reference_length);
    gps_envelope();
}
if(audit_case == "gps_cable_base") intersection() {
    import("1-base.stl");
    gps_cable_envelope();
}
