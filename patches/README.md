# Upstream Patches

Local modifications to the upstream sources cloned into the ignored
`external/` directory. Because `external/` is not tracked, these patches are
the only reproducible record of the changes; a fresh clone needs them applied
before the SITL build succeeds.

## `ardupilot-8b9ea700-sitl-dds-compat.patch`

Applies to ArduPilot at `8b9ea7004582267d79a97858e4fda1dd4fe18305`.

```bash
git -C external/ardupilot apply ../../patches/ardupilot-8b9ea700-sitl-dds-compat.patch
```

Three unrelated fixes, all SITL-only:

- `AP_Scripting/generator/src/main.c` initialises `var_type_name`. GCC 15
  treats the upstream may-be-uninitialised warning as an error; the Nix shell
  pins GCC 14 as well, so this is belt and braces.
- `AP_DDS/AP_DDS_Client.cpp` and `AP_DDS/AP_DDS_ExternalControl.cpp` replace
  generated C++ constants that the current Micro-XRCE-DDS-Gen no longer emits
  with their literal values.

The DDS changes track a generator/checkout mismatch, not an ArduPilot defect.
Re-evaluate them against a matched generator and ArduPilot revision rather
than carrying them forward indefinitely; do not apply them to firmware
intended for a real vehicle.
