# OpenOMEN
Unofficial CLI, driver and daemon for managing HP Victus/OMEN laptops on Linux.

It works as a replacement for the Windows-only **Omen Gaming Hub Application**. At the moment, it allows you to manage your **Fan Speed and Profile**, **Power Profile** and view real-time **CPU and GPU** stats.

In the future, new features like **Keyboard RGB Support** and **Manual Fan Curves** will be added.

Also see the **[Official Wepage](https://openomen.github.io/)**

<br>

## Installation and Updates
1. Search OpenOMEN's [latest release](https://github.com/openomen/openomen/releases/latest)
2. Download the **Release File** (called `openomen`)
3. Place the file onto your **Binaries Folder** (usually located in `/usr/local/bin`)
4. Now you can run **OpenOMEN** by typing `openomen` in your terminal
5. See the [Wiki](https://github.com/openomen/openomen/wiki) for more information on how to use it

You can **update OpenOMEN** by running `openomen update`

You can also **update it manually** by replacing the `openomen` file with the latest version.

<br>

## How to Use
For a guide on how to use **OpenOMEN's CLI**, please see the **[Wiki](https://github.com/openomen/openomen/wiki)**.

<br>

## Support & Feedback
For support, feature requests, or to report bugs, please **open an issue on the GitHub Repository** or **[Join the Discord Server](https://discord.gg/UHQ5cztbUj)**, were you can report bugs, suggest new features, chat with others and way more.

<br>

## Supported devices
The list below contains devices that have been tested with the tool and don't show any Model-Specific problems.

| Devices              | Version | Notes                                      |
|----------------------|---------|--------------------------------------------|
| Victus 17 17z-db100  | ✅      | Confirmed working and supported since v0.1 |
| Victus 16 16-ap0xxx  | ✅      | Confirmed working and supported since v0.1 |
| Victus 16 16-r0xxx   | ✅      | Confirmed working and supported since v0.1 |
| Victus 15 15-fb0xxx  | ✅      | Confirmed working and supported since v0.1 |
| HP OMEN X 2S         | ✅      | Confirmed working and supported since v0.1 |
| HP OMEN 17           | ✅      | Confirmed working and supported since v0.1 |
| HP OMEN 16           | ✅      | Confirmed working and supported since v0.1 |

Most HP OMEN / Victus laptops should work with this tools due to them having very similar architectures, but some may not work due to specific hardware or firmware.

<br>

## Supported Linux Distributions
OpenOMEN has been tested on up to **Linux 7.0** on these Distributions:
* Ubuntu (22.04 / 24.04)
* CachyOS

*But it should still work on any **Debian-based Distribution** as long as it supports the tools it uses.*

<br>

## Disclaimer

OpenOmen is an independent open-source project and is **not affiliated with, endorsed by, or sponsored by HP Inc or the Omen or Victus brands**.

*“Omen” and "Victus" are trademarks of HP Inc., and any references to it in this project are strictly for the purpose of device compatibility and identification.*

This software is provided **"as is"**, without warranty of any kind, express or implied. By using this software, you acknowledge that:

- You are responsible for any potential damage to your device.
- You understand that modifying hardware or system behavior may void warranties.
- You will not hold the authors or contributors liable for any outcome resulting from the use of this software.

**Use this software at your own risk.**
