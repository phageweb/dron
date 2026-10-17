{
  description = "KiCad for the Pavo20 Pro custom boards, and the OpenDrone projects they start from";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAll (pkgs: {
        default = pkgs.mkShell {
          # kicad-small: KiCad with its symbols and footprints, without the
          # 3D models (several GB); the OpenDrone boards bring their own.
          packages = [ pkgs.kicad-small pkgs.git pkgs.jq ];
          shellHook = ''
            echo "KiCad $(kicad-cli version) — ./check.sh runs ERC/DRC on the OpenDrone sources"
          '';
        };
        # ArduPilot for the board's own hwdef: ARM compiler and waf's Python
        # (python 3.14 in nixpkgs has no `future`; the ChibiOS build does not need it).
        # mkShellNoCC: mkShell would set CC/CXX to the host gcc, and waf prefers those.
        firmware = pkgs.mkShellNoCC {
          packages = [
            pkgs.gcc-arm-embedded
            pkgs.gnumake
            pkgs.git
            (pkgs.python3.withPackages (p: with p; [ empy pexpect intelhex pymavlink lxml setuptools ]))
          ];
        };
      });

      apps = forAll (pkgs: {
        check = {
          type = "app";
          program = toString (pkgs.writeShellScript "dps-check" ''
            export PATH=${pkgs.lib.makeBinPath [ pkgs.kicad-small pkgs.git pkgs.jq pkgs.coreutils pkgs.gnugrep ]}:$PATH
            exec ${./check.sh} "$@"
          '');
        };
      });
    };
}
