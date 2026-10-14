{
  description = "ArduCopter firmware for the Pavo20 Pro flight controller (MicoAir743v2), and the tools to flash it over USB";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      board = "MicoAir743v2";

      # Each build is pinned, so every flash writes the same bytes. To move
      # one: change commit and url, then refresh the hashes with
      #   nix store prefetch-file <url>
      builds = {
        # The stable release the board runs.
        stable = {
          version = "4.7.1";
          commit = "dbe792162d06cab66c3475fd5556bf7a120f119e";
          base = "https://firmware.ardupilot.org/Copter/stable-4.7.1/${board}";
          apj = "sha256-XUoa/QgM7qqE7mFCHj1r3YJyQyXZnwSs1l3SHdDg9nA=";
          hex = "sha256-wBe/+MNO33OvOPGbb2rH7TxfoE6YWIHnDU7W1A4ZIB4=";
          uploader = "sha256-74tuK8xZf8XCkBzr7d/HjCQq4D73EPnYkujTX3RbcW4=";
        };
        # Master, the newest official nightly. It has osd:write for Lua,
        # which lidar/osd/scan_osd.lua needs and 4.7.x lacks. Nightlies are
        # pruned from the server after about a month; move the pin then.
        master = {
          version = "4.8.0-dev";
          commit = "113108bd69954dfe9faed49f025601ffcaff2886";
          base = "https://firmware.ardupilot.org/Copter/2026-10/2026-10-12-07:10/${board}";
          apj = "sha256-zN03rKaCyi8tKbIKge/bWLvXzqXKdMtZW4JJTaWALLQ=";
          hex = "sha256-0q+qBQpWL6IvreZQcIQ+CXiof0jCgfUzWkuwYU4pGH8=";
          uploader = "sha256-myPAGlfcmQkpAkcS+DS/yWV9RSPsYZfN0WUFoONVOKw=";
        };
      };

      mkBuild = pkgs: suffix: b:
        let
          apj = pkgs.fetchurl { url = "${b.base}/arducopter.apj"; hash = b.apj; };
          hex = pkgs.fetchurl { url = "${b.base}/arducopter_with_bl.hex"; hash = b.hex; };
          # The uploader from the same commit the firmware was built from.
          uploaderPy = pkgs.fetchurl {
            url = "https://raw.githubusercontent.com/ArduPilot/ardupilot/${b.commit}/Tools/scripts/uploader.py";
            hash = b.uploader;
          };
          python = pkgs.python3.withPackages (p: [ p.pyserial ]);
          firmware = pkgs.runCommand "arducopter-${board}-${b.version}"
            { nativeBuildInputs = [ pkgs.binutils ]; }
            ''
              mkdir -p $out
              cp ${apj} $out/arducopter.apj
              cp ${hex} $out/arducopter_with_bl.hex
              # dfu-util takes raw binary, not Intel hex; the image starts
              # at 0x08000000 with the bootloader in front.
              objcopy -I ihex -O binary ${hex} $out/arducopter_with_bl.bin
              echo "ArduCopter ${b.version} ${board} ${b.commit}" > $out/VERSION
            '';
        in
        {
          "firmware${suffix}" = firmware;

          # Board already runs ArduPilot (its bootloader shows up as ttyACM).
          "flash${suffix}" = pkgs.writeShellApplication {
            name = "flash${suffix}";
            text = ''
              echo "Flashing ArduCopter ${b.version} to ${board} over USB serial"
              exec ${python}/bin/python3 ${uploaderPy} "$@" ${firmware}/arducopter.apj
            '';
          };

          # Board in STM32 DFU mode: hold BOOT while plugging in USB.
          # Writes bootloader and firmware together.
          "flash-dfu${suffix}" = pkgs.writeShellApplication {
            name = "flash-dfu${suffix}";
            runtimeInputs = [ pkgs.dfu-util ];
            text = ''
              if ! dfu-util -l 2>/dev/null | grep -q '0483:df11'; then
                echo "No STM32 in DFU mode (0483:df11). Hold BOOT, plug in USB, try again." >&2
                echo "If lsusb shows it, it is permissions: see firmware/README.md." >&2
                exit 1
              fi
              echo "Flashing ArduCopter ${b.version} with bootloader to ${board} over DFU"
              dfu-util -a 0 -s 0x08000000:leave -D ${firmware}/arducopter_with_bl.bin
            '';
          };
        };
    in
    {
      packages = forAll (pkgs:
        let
          stable = mkBuild pkgs "" builds.stable;
          master = mkBuild pkgs "-master" builds.master;
        in
        stable // master // { default = stable.firmware; });

      apps = forAll (pkgs:
        let p = self.packages.${pkgs.stdenv.hostPlatform.system}; in
        {
          flash = { type = "app"; program = "${p.flash}/bin/flash"; };
          flash-dfu = { type = "app"; program = "${p.flash-dfu}/bin/flash-dfu"; };
          flash-master = { type = "app"; program = "${p.flash-master}/bin/flash-master"; };
          flash-dfu-master = { type = "app"; program = "${p.flash-dfu-master}/bin/flash-dfu-master"; };
          default = self.apps.${pkgs.stdenv.hostPlatform.system}.flash;
        });

      devShells = forAll (pkgs: {
        default = pkgs.mkShell {
          packages = [
            self.packages.${pkgs.stdenv.hostPlatform.system}.flash
            self.packages.${pkgs.stdenv.hostPlatform.system}.flash-dfu
            self.packages.${pkgs.stdenv.hostPlatform.system}.flash-master
            self.packages.${pkgs.stdenv.hostPlatform.system}.flash-dfu-master
            pkgs.dfu-util
            pkgs.usbutils
            pkgs.mavproxy
            pkgs.qgroundcontrol
          ];
          shellHook = ''
            export FIRMWARE=${self.packages.${pkgs.stdenv.hostPlatform.system}.firmware}
            export FIRMWARE_MASTER=${self.packages.${pkgs.stdenv.hostPlatform.system}.firmware-master}
            echo "ArduCopter ${builds.stable.version} for ${board} is in \$FIRMWARE, ${builds.master.version} in \$FIRMWARE_MASTER"
            echo "flash | flash-dfu | flash-master | flash-dfu-master | qgroundcontrol | mavproxy.py"
          '';
        };
      });
    };
}
