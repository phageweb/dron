{
  description = "ArduCopter firmware for the Pavo20 Pro flight controller (MicoAir743v2), and the tools to flash it over USB";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});

      # Pinned to one stable release, so every flash writes the same bytes.
      # To move up: change version and commit, then refresh the hashes with
      #   nix store prefetch-file <url>
      version = "4.7.1";
      commit = "dbe792162d06cab66c3475fd5556bf7a120f119e";
      board = "MicoAir743v2";
      base = "https://firmware.ardupilot.org/Copter/stable-${version}/${board}";
    in
    {
      packages = forAll (pkgs:
        let
          apj = pkgs.fetchurl {
            url = "${base}/arducopter.apj";
            hash = "sha256-XUoa/QgM7qqE7mFCHj1r3YJyQyXZnwSs1l3SHdDg9nA=";
          };
          hex = pkgs.fetchurl {
            url = "${base}/arducopter_with_bl.hex";
            hash = "sha256-wBe/+MNO33OvOPGbb2rH7TxfoE6YWIHnDU7W1A4ZIB4=";
          };
          # The uploader from the same commit the firmware was built from.
          uploaderPy = pkgs.fetchurl {
            url = "https://raw.githubusercontent.com/ArduPilot/ardupilot/${commit}/Tools/scripts/uploader.py";
            hash = "sha256-74tuK8xZf8XCkBzr7d/HjCQq4D73EPnYkujTX3RbcW4=";
          };
          python = pkgs.python3.withPackages (p: [ p.pyserial ]);
        in
        rec {
          firmware = pkgs.runCommand "arducopter-${board}-${version}"
            { nativeBuildInputs = [ pkgs.binutils ]; }
            ''
              mkdir -p $out
              cp ${apj} $out/arducopter.apj
              cp ${hex} $out/arducopter_with_bl.hex
              # dfu-util takes raw binary, not Intel hex; the image starts
              # at 0x08000000 with the bootloader in front.
              objcopy -I ihex -O binary ${hex} $out/arducopter_with_bl.bin
              echo "ArduCopter ${version} ${board} ${commit}" > $out/VERSION
            '';

          # Board already runs ArduPilot (its bootloader shows up as ttyACM).
          flash = pkgs.writeShellApplication {
            name = "flash";
            text = ''
              echo "Flashing ArduCopter ${version} to ${board} over USB serial"
              exec ${python}/bin/python3 ${uploaderPy} "$@" ${firmware}/arducopter.apj
            '';
          };

          # Board in STM32 DFU mode: hold BOOT while plugging in USB.
          # Writes bootloader and firmware together.
          flash-dfu = pkgs.writeShellApplication {
            name = "flash-dfu";
            runtimeInputs = [ pkgs.dfu-util ];
            text = ''
              if ! dfu-util -l 2>/dev/null | grep -q '0483:df11'; then
                echo "No STM32 in DFU mode (0483:df11). Hold BOOT, plug in USB, try again." >&2
                echo "If lsusb shows it, it is permissions: see firmware/README.md." >&2
                exit 1
              fi
              echo "Flashing ArduCopter ${version} with bootloader to ${board} over DFU"
              dfu-util -a 0 -s 0x08000000:leave -D ${firmware}/arducopter_with_bl.bin
            '';
          };

          default = firmware;
        });

      apps = forAll (pkgs:
        let p = self.packages.${pkgs.stdenv.hostPlatform.system}; in
        {
          flash = { type = "app"; program = "${p.flash}/bin/flash"; };
          flash-dfu = { type = "app"; program = "${p.flash-dfu}/bin/flash-dfu"; };
          default = self.apps.${pkgs.stdenv.hostPlatform.system}.flash;
        });

      devShells = forAll (pkgs: {
        default = pkgs.mkShell {
          packages = [
            self.packages.${pkgs.stdenv.hostPlatform.system}.flash
            self.packages.${pkgs.stdenv.hostPlatform.system}.flash-dfu
            pkgs.dfu-util
            pkgs.usbutils
            pkgs.mavproxy
            pkgs.qgroundcontrol
          ];
          shellHook = ''
            export FIRMWARE=${self.packages.${pkgs.stdenv.hostPlatform.system}.firmware}
            echo "ArduCopter ${version} for ${board} is in \$FIRMWARE"
            echo "flash | flash-dfu | qgroundcontrol | mavproxy.py"
          '';
        };
      });
    };
}
