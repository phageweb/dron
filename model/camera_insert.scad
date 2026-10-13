// Pavo20 Pro / Walksnail Ascent Lite+ camera adapter, millimetres.
// Prototype: measure the camera body before printing. See README.md.
// Print coordinates: X = width, Y = height, Z = front -> rear.
// Front face lies on Z=0. Camera slides in from the rear in flexible TPU.

/* [Pavo20 Pro] */
// Measured inside distance between existing camera bracket cheeks.
mount_width = 20; // [19:0.1:21]
// Total clearance between adapter and bracket, not per side.
mount_clearance = 0.2; // [0:0.05:0.5]

/* [Telo kamery - OVERIT MERENIM] */
// Manufacturer lists 12 x 14 x 15.8 mm without identifying each axis.
// Assumption: width 14, height 12, total optical depth 15.8.
camera_width = 14;
camera_height = 12;
// Estimated body thickness EXCLUDING lens, NOT the published 15.8 mm.
body_depth = 4.5;
// Total cavity allowance in each dimension.
camera_clearance = 0.3; // [0:0.05:0.8]
wall = 1.4;

/* [Zachyceni kamery] */
// Small corner stops leave lens and middle of each edge unobstructed.
front_lip = 0.8;
rear_lip = 0.8;
lip_overlap = 0.55; // [0.3:0.05:0.8]
corner_length = 2.4;

/* [Bocni srouby] */
// Blind pilot holes for M2 screws into TPU; NOT holes in the camera.
screw_pilot = 1.7;
screw_depth = 1.5;
// Keep solid material between screw tip and camera.
minimum_inner_wall = 0.7;
// Position along camera height; 0 = centre.
pivot_height = 0;

/* [Pouze nahled] */
preview_angle = 20; // [0:5:40]
// Approximate lens geometry; never used to generate the adapter.
preview_lens_diameter = 10;
preview_total_depth = 15.8;

/* [Hidden] */
$fn = 64;
eps = 0.02;
inner_w = camera_width + camera_clearance;
inner_h = camera_height + camera_clearance;
outer_w = mount_width - mount_clearance;
outer_h = inner_h + 2*wall;
cavity_depth = body_depth + camera_clearance;
total_depth = front_lip + cavity_depth + rear_lip;
side_wall = (outer_w-inner_w)/2;
pivot_z = front_lip + cavity_depth/2;
outer_radius = 1;

assert(camera_width > 0 && camera_height > 0 && body_depth > 0);
assert(camera_clearance >= 0 && mount_clearance >= 0);
assert(wall >= 1 && side_wall >= 1, "Insufficient wall thickness");
assert(screw_depth > 0 && screw_pilot > 0);
assert(side_wall-screw_depth >= minimum_inner_wall,
       "Screw hole too deep: decrease screw_depth or increase mount_width");
assert(front_lip > 0 && rear_lip > 0 && lip_overlap > 0);
assert(lip_overlap < corner_length && 2*corner_length < min(inner_w,inner_h));
assert(abs(pivot_height)+screw_pilot/2+0.8 < outer_h/2);
assert(pivot_z-screw_pilot/2 >= 0.8 &&
       total_depth-pivot_z-screw_pilot/2 >= 0.8,
       "Body too thin for side screw: adjust body_depth or screw_pilot");

module rounded_rectangle(w,h,r) {
    hull()
        for(x=[-1,1],y=[-1,1])
            translate([x*(w/2-r),y*(h/2-r)]) circle(r=r);
}

// Stops overlap shell by eps, so exported mesh is one connected solid.
module corner_stops(z,thickness) {
    for(x=[-1,1], y=[-1,1])
        translate([x*(inner_w/2-lip_overlap/2),
                   y*(inner_h/2-corner_length/2),z+thickness/2])
            cube([lip_overlap+2*eps,corner_length+2*eps,thickness],center=true);
}

module adapter() {
    difference() {
        union() {
            difference() {
                linear_extrude(total_depth)
                    rounded_rectangle(outer_w,outer_h,outer_radius);
                translate([-inner_w/2,-inner_h/2,-eps])
                    cube([inner_w,inner_h,total_depth+2*eps]);
            }
            corner_stops(0,front_lip);
            corner_stops(front_lip+cavity_depth,rear_lip);
        }
        // Separate blind holes: no screw can pass through the camera cavity.
        for(side=[-1,1])
            translate([side*(outer_w/2+eps),pivot_height,pivot_z])
                rotate([0,-side*90,0])
                    cylinder(d=screw_pilot,h=screw_depth+eps);
    }
}

// Simplified envelopes ONLY; not a detailed CAD model of purchased parts.
module camera_reference() {
    color([0.16,0.18,0.2,0.7])
        translate([-camera_width/2,-camera_height/2,
                   front_lip+camera_clearance/2])
            cube([camera_width,camera_height,body_depth]);
    color([0.1,0.12,0.14,0.8])
        translate([0,0,front_lip-(preview_total_depth-body_depth)])
            cylinder(d=preview_lens_diameter,
                     h=preview_total_depth-body_depth+camera_clearance/2);
    color([0.2,0.7,0.9,0.5])
        translate([0,0,total_depth]) cylinder(d=1.4,h=7);
}

