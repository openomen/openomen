# Usage
All main commands support the `--help` argument to obtain information about them.

You can run `openomen -v` or `openomen --version` to see your current Binary's version.

## Fan Management
`openomen fan` is the main command for **Fan management**-

* `openomen fan max` > Puts your fans in *Max RPM mode*.
* `openomen fan auto` > Lets your EC control automatically your fan speeds (*default*).
* `openomen fan toggle` > Switch between **Auto** and **Max RPM** modes.
* `openomen fan status` > See your current fan's speeds.

## CPU Monitoring
`openomen cpu` is the main command for **CPU Monitoring.**

* Shows exact CPU Model and Speed.
* Shows Temperature using various drivers depending on your model.
* Shows your current, per-core load.

> This command allows for the `--watch` option, which allows for real-time monitoring of these stats.

## GPU Monitoring
`openomen gpu` is the main command for **GPU Monitoring.**

* Shows your GPU Model.
* Shows current Temperature, Utilization and Frequency.
* Shows VRAM and Power Draw (some NVIDIA cards with `nvidia-smi` installed).

> This command allows for the `--watch` option, which allows for real-time monitoring of these stats.

> NVIDIA cards with nvidia-smi installed get the Temperature and Utilization directly from it.

## Stats Monitoring
`openomen stats` is the main command for **Full-System Monitoring.**

* Shows Fan status (same as `openomen fan status`).
* Shows Power Profiles Information.
* Shows CPU Information (same as `openomen cpu`).
* Shows GPU Information (same as `openomen gpu`).

> This command allows for the `--watch` option, which allows for real-time monitoring of these stats.

## System Information
`openomen info` is the main command for showing **System Information.**

* Shows Kernel Information.
* Shows CPU/GPU Models.
* Shows hwmon drivers.
* Shows ACPI Platform Profiles list & support.
* Shows Fan Status (hwmon path & hp-wmi status).

> This command is useful for when you have to report errors or bugs.

## Power Management
`openomen power` is the main command for **Power Management.**

* `openomen power set <profile>` > Set an active ACPI Power Profile.
* `openomen power apply <profile>` > Apply predefined profile templates.
* `openomen power list` > Show available profiles.

## RGB Management
`openomen rgb` is the main command for **RGB Management.**

* `openomen rgb status` > Show keyboard lighting status, profile and available profiles.
* `openomen rgb list` > Show available profiles.
* `openomen rgb set` > Set an active profile.
* `openomen rgb on|off` > Turn keyboard lights on/off.

> Right now, limited RGB support is given for Keyboards. Future updates will bring more support and features.

## Doctor Utility
`openomen doctor` is the main command for the **Doctor Utility.**

* Shows `hp-wmi` and `hp-wmi_ec` module's status.
* Shows Fan control status.
* Shows detected Thermal Sensors.
* Shows `platform_profile` and `platform_profile_choices` availability.
* Shows GPU stats.
* Shows Battery status and `charge_control_end_threshold` availability.
* Shows RGB Control files availability.

> This command is a diagnostic tool useful to detect errors and report them.

## Updater
`openomen update` is the main command for the **Updater.**

This command updates your **OpenOMEN Binary** to the latest version from Github Releases.

It has integrated Checksum verification to avoid corruption or undesired downloads.

* `--force` > Direct download from the latest release (from releases/latest/download).
* `--no-verify` > Skips binary execution verification post-download. (execution + version checking)