// Pavo20 Pro 4S - obalova studie sestavy k spec/realna_stavba_dronu/10_pavo20.md
//
// Souradnice v mm, pocatek uprostred HORNI plochy karbonove desky.
// X dopredu, Y doleva, Z nahoru - stejna konvence jako cad_codex.
//
// Model neni vyrobni vykres. Barvy nesou jistotu udaje:
//   normalni  = publikovany rozmer (BetaFPV, Rotorama, datasheet)
//   PURPUROVA = placeholder, ktery se musi zmerit na plastu
//   ORANZOVA  = neoverena obalka/poloha
//   CERVENA   = kolize, a nic jineho - aby znacka neprebarvila to, co znaci
//   JANTAR    = deska presahuje rovinu vrtuli
//   zluty kriz = odhadnute teziste

$fn = 64;

// ---------------------------------------------------------------- prepinace
// Kazdy pohled kresli jen to, co ma ukazat - jinak je z toho kase.
// render.sh je prepina pres -D.
show_props      = true;   // disky vrtuli a volny stredovy kruh
show_scan       = true;   // rovina skenu LD06
show_cg         = true;   // teziste a vyvazovaci rameno
show_collision  = true;   // prekryv LD06 s kamerovou vezi

// ------------------------------------------------- overene rozmery [publik.]
wheelbase       = 93.7;                       // BetaFPV / Rotorama
motor_xy        = wheelbase / (2 * sqrt(2));  // 33.13
prop_d          = 55.88;                      // Gemfan 2218, 2.2"
prop_r          = prop_d / 2;
plate_t         = 2.0;                        // horni deska, katalog ramu
fc_size         = [36, 36, 8];                // MicoAir H743 V2
fc_mount        = 25.5;                       // MicoAir
frame_fc_mount  = 26.0;                       // rozteč v ramu
damper_d        = 8.0;                        // silentbloky z baleni ramu
motor_d         = 15.4;                       // Flashhobby A1204
motor_h         = 15.2;
vtx_size        = [30, 30, 7];                // Wyvern, deska 25.5 rozteč
vtx_mount       = 25.5;
cam_lens_d      = 19;                         // Micro, drzak ramu 19 mm
gps_size        = [18, 18, 4.6];              // Walksnail WS-M181
mtf_size        = [21.6, 16, 6.5];            // MicoAir MTF-02P
battery         = [73, 17, 32];               // Tattu 850 4S HV, nastojato ve slotu
ld06_size       = [38.59, 38.59, 33.3];       // datasheet LDROBOT
ld06_turret_d   = 35.29;
ld06_turret_h   = 12.6;
ld06_window_c   = 22.7;                       // stred optickeho okna nad zakladnou

// ------------------------------------------------------- PLACEHOLDER rozmery
// Tohle se z webu vytahnout neda a rozhoduje to o cele stavbe.
duct_inner_d_P  = 57.5;
duct_wall_P     = 2.5;
duct_z_min_P    = -6;
duct_h_P        = 16;
tower_P         = [60, 28, 38];               // kamerova vez, obalka
tower_x_P       = 10;
prop_z_P        = 13.5;                       // rovina vrtuli nad deskou
fc_z_P          = 6;                          // spodek FC na stlacenem silentbloku

// ------------------------------------------------------------ polohy sestavy
// Dve opravy proti prvni verzi:
//  1) lidar byl vpredu na x=+36.4 a spodkem v 19 mm, coz vychazelo z vyvazeni -
//     jenze pak mirila rovina skenu POD baterii a 360 stupnovy senzor neni
//     360 stupnovy. Vyska okna je tvrdsi podminka nez teziste.
//  2) baterie nepatri nahoru, ale ZESPODU do slotu v duktove sestave. Pasek je
//     na teardownu protazeny duktem, ne horni deskou, a katalog uvadi slot
//     sirky 20 mm s "neomezenou vyskou", coz dava smysl jen u visici baterie.
//     Tim teziste spadne POD rovinu vrtuli a stozar se zkrati o 34 mm.
batt_x          = 0;
batt_z          = -(plate_t + battery[2]/2);      // visi pod deskou ve slotu
ld06_x          = 0;
ld06_z          = tower_P[2] + 2;                 // nejvyssi prekazka je uz jen vez

// ------------------------------------------------------------------ hmotnosti
// Publikovane hodnoty; zadna neni zvazena. Poloha je lumped odhad pro CG.
mass_items = [
  [28.70, [  0, 0, -1.0 ], "ram bez drzaku O3"],
  [11.00, [tower_x_P/2, 0, tower_P[2]/2 + 4], "TPU vez a stozar"],
  [24.80, [  0, 0,  motor_h/2 ], "motory 4x A1204"],
  [ 2.32, [  0, 0,  prop_z_P ], "vrtule"],
  [10.00, [  0, 0,  fc_z_P + fc_size[2]/2 ], "MicoAir H743 V2"],
  [13.76, [  8, 0,  22 ], "Wyvern vc. kamery"],
  [ 1.60, [-24, 0,   4 ], "RX a antena"],
  [ 1.50, [  5, 14, -plate_t - mtf_size[2]/2 ], "MTF-02P"],
  [ 4.30, [-26, 0,   6 ], "GPS"],
  [13.36, [  0, 0,   5 ], "kabelaz a srouby"],
  [76.00, [batt_x, 0, batt_z], "baterie"],
  [42.00, [ld06_x, 0, ld06_z + ld06_size[2]/2], "LD06"],
];

function sum_v(v, i=0) = i >= len(v) ? 0 : v[i] + sum_v(v, i+1);
function total_mass(it) = sum_v([for (x = it) x[0]]);
function cg_axis(it, a) =
    sum_v([for (x = it) x[0] * x[1][a]]) / total_mass(it);
cg = [cg_axis(mass_items,0), cg_axis(mass_items,1), cg_axis(mass_items,2)];

free_centre_r = motor_xy * sqrt(2) - prop_r;   // 18.91 mm
fc_half_diag  = fc_size[0] * sqrt(2) / 2;      // 25.46 mm

echo(str("Hmotnost celkem [g]: ", total_mass(mass_items)));
echo(str("Teziste [mm]: ", cg));
echo(str("Volny stredovy kruh r = ", free_centre_r,
         " mm; polovicni uhlopricka FC = ", fc_half_diag,
         " mm; zasah pod disky = ", fc_half_diag - free_centre_r, " mm"));
echo(str("FC vrsek z = ", fc_z_P + fc_size[2],
         " mm vs rovina vrtuli z = ", prop_z_P,
         " mm -> rezerva ", prop_z_P - fc_z_P - fc_size[2], " mm"));
batt_top   = tower_P[2];   // baterie je dole, nejvyssi prekazka je vez
window_z   = ld06_z + ld06_window_c;
echo(str("Nejvyssi prekazka ", batt_top, " mm; opticke okno LD06 ", window_z, " mm -> ",
         window_z > batt_top ? "sken je nad vsim, 360 stupnu plati"
                             : "SKEN MIRI POD BATERII, 360 stupnu neplati"));
echo(str("Teziste je ", cg[2] - prop_z_P, " mm nad rovinou vrtuli (CineLog ma +2.3)"));
echo(str("Baterie visi ", -batt_z - battery[2]/2, " az ", -batt_z + battery[2]/2,
         " mm pod deskou; ducty konci v ", -duct_z_min_P, " mm"));

// ------------------------------------------------------------------- pomocne
module rbox(size, r=1.5) {
    hull() for (sx=[-1,1], sy=[-1,1], sz=[-1,1])
        translate([sx*(size[0]/2-r), sy*(size[1]/2-r), sz*(size[2]/2-r)])
            sphere(r=r);
}
module ring(od, id, h) { difference() { cylinder(d=od,h=h); translate([0,0,-1]) cylinder(d=id,h=h+2); } }
module line3(a,b,d=0.7) {
    hull() { translate(a) sphere(d=d); translate(b) sphere(d=d); }
}
module cross3(p,s=6,d=0.7) {
    line3(p-[s,0,0],p+[s,0,0],d); line3(p-[0,s,0],p+[0,s,0],d); line3(p-[0,0,s],p+[0,0,s],d);
}
motors = [[ motor_xy,-motor_xy],[-motor_xy, motor_xy],
          [ motor_xy, motor_xy],[-motor_xy,-motor_xy]];

// --------------------------------------------------------------------- dily
module carbon_plate() {
    color([0.09,0.10,0.11,1])
    translate([0,0,-plate_t/2]) difference() {
        hull() for (p = motors) translate([p[0],p[1],0]) cylinder(d=22,h=plate_t,center=true);
        for (sx=[-1,1], sy=[-1,1])
            translate([sx*frame_fc_mount/2, sy*frame_fc_mount/2,0])
                cylinder(d=2.2,h=plate_t+2,center=true);
    }
}

module ducts() {
    color([0.55,0.10,0.62,0.30])                       // PLACEHOLDER
    for (p = motors) translate([p[0],p[1],duct_z_min_P])
        ring(duct_inner_d_P + 2*duct_wall_P, duct_inner_d_P, duct_h_P);
}

module dampers() {
    color([0.90,0.35,0.10,1])
    for (sx=[-1,1], sy=[-1,1])
        translate([sx*frame_fc_mount/2, sy*frame_fc_mount/2, 0])
            cylinder(d=damper_d, h=fc_z_P);
}

module motors_and_props() {
    for (p = motors) translate([p[0],p[1],0]) {
        color([0.22,0.23,0.25,1]) cylinder(d=motor_d,h=motor_h);
        if (show_props)
            color([0.95,0.15,0.15,0.13])
                translate([0,0,prop_z_P]) cylinder(d=prop_d,h=0.8);
    }
    // volny stredovy kruh: kam az nesaha zadny disk
    if (show_props)
        color([0.15,0.70,0.30,0.30])
            translate([0,0,prop_z_P]) ring(free_centre_r*2, free_centre_r*2-1.4, 0.9);
}

module flight_controller() {
    // vrsek desky proti rovine vrtuli je cela otazka bodu 1
    over = (fc_z_P + fc_size[2]) > prop_z_P;
    color(over ? [0.95,0.62,0.10,1] : [0.05,0.32,0.24,1])   // jantar = presahuje vrtule
        translate([0,0,fc_z_P + fc_size[2]/2]) rbox(fc_size,1);
    color([0.75,0.75,0.78,1])
        for (sx=[-1,1], sy=[-1,1])
            translate([sx*fc_mount/2, sy*fc_mount/2, fc_z_P-1])
                cylinder(d=2.4,h=fc_size[2]+2);
}

module tower() {
    color([0.95,0.55,0.12,0.40])                        // neoverena obalka
        translate([tower_x_P,0,tower_P[2]/2]) rbox(tower_P,2);
    color([0.10,0.10,0.12,1])                           // Wyvern
        translate([tower_x_P-6,0,22]) rbox(vtx_size,1);
    color([0.12,0.12,0.14,1])                           // objektiv kamery
        translate([tower_x_P+tower_P[0]/2-2,0,20]) rotate([0,90,0])
            cylinder(d=cam_lens_d,h=6);
}

module small_boards() {
    color([0.05,0.32,0.24,1]) translate([-24,0,4]) rbox([17,13,2],0.8);      // RX
    color([0.05,0.32,0.24,1]) translate([-26,0,6]) rbox(gps_size,0.8);       // GPS
    color([0.05,0.32,0.24,1])                                                // MTF-02P
        translate([5,14,-plate_t - mtf_size[2]/2]) rbox(mtf_size,0.8);       // mimo slot baterie
    color([0.25,0.85,0.35,0.16])                                             // 42 deg dolu
        translate([5,14,-plate_t-mtf_size[2]]) rotate([180,0,0])
            cylinder(d1=0, d2=2*tan(21)*26, h=26);
}

module top_deck() {
    // Horni plosina veze, na ktere stoji stozar lidaru. PLACEHOLDER obrys.
    color([0.55,0.10,0.62,0.85])
        translate([tower_x_P, 0, tower_P[2]]) rbox([48, 30, 2], 1);
}

module battery_pack() {
    // Ve slotu duktove sestavy, pod deskou. Pasek je soucast ductu.
    color([0.12,0.14,0.35,1]) translate([batt_x,0,batt_z]) rbox(battery,2);
}

module mast() {
    // Stozar od horni paluby k lidaru. Musi obejit baterii, proto dve nohy.
    color([0.95,0.55,0.12,0.75])
    for (sy = [-1,1]) translate([ld06_x, sy*10, tower_P[2]])
        cylinder(d=5, h=ld06_z - tower_P[2]);
}

module ld06() {
    translate([ld06_x,0,ld06_z]) {
        color([0.20,0.21,0.23,1])
            translate([0,0,(ld06_size[2]-ld06_turret_h)/2])
                rbox([ld06_size[0],ld06_size[1],ld06_size[2]-ld06_turret_h],2);
        color([0.30,0.31,0.34,1])
            translate([0,0,ld06_size[2]-ld06_turret_h]) cylinder(d=ld06_turret_d,h=ld06_turret_h);
        // rovina skenu: jen naznak, aby byla videt vyska okna
        if (show_scan)
            color([0.15,0.70,0.95,0.35])
                translate([0,0,ld06_window_c]) ring(108, 104, 0.8);
    }
}

module ld06_tower_collision() {
    // Prunik obalky lidaru s vezi. Tohle je nalez, ne dekorace:
    // tezistovy vypocet posadi LD06 presne tam, kde stoji kamerova vez.
    color([1,0,0,0.45])
    intersection() {
        translate([ld06_x,0,ld06_z+ld06_size[2]/2]) cube(ld06_size,center=true);
        translate([tower_x_P,0,tower_P[2]/2]) cube(tower_P,center=true);
    }
}

module cg_marker() {
    color([1,0.95,0.05,1]) { translate(cg) sphere(d=4); cross3(cg,9,0.6); }
    // vyvazovaci rameno: lidar vpredu proti baterii vzadu
    color([1,0.95,0.05,0.7])
        line3([ld06_x,0,cg[2]], [batt_x,0,cg[2]], 0.8);
}

module axes() {
    color([1,0.25,0.25,1]) line3([0,0,0],[34,0,0],1.0);
    color([0.2,0.9,0.3,1])  line3([0,0,0],[0,34,0],1.0);
    color([0.25,0.5,1,1])   line3([0,0,0],[0,0,34],1.0);
}

// ----------------------------------------------------------------- sestaveni
carbon_plate();
ducts();
dampers();
motors_and_props();
flight_controller();
tower();
small_boards();
top_deck();
battery_pack();
mast();
ld06();
if (show_collision) ld06_tower_collision();
if (show_cg) cg_marker();
axes();
