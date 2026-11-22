<div align="center">

# OpenOMEN

**Unofficial CLI, driver, and daemon for managing HP OMEN / Victus laptops on Linux**

[![Latest Release](https://img.shields.io/github/v/release/openomen/openomen?label=release)](https://github.com/openomen/openomen/releases/latest)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-green.svg)](LICENSE)
[![Discord](https://img.shields.io/discord/1496418617716375615?label=discord&logo=discord&refresh=1)](https://discord.gg/UHQ5cztbUj)
[![Stars](https://img.shields.io/github/stars/openomen/openomen?style=social)](https://github.com/openomen/openomen/stargazers)

[Website](https://openomen.github.io/) · [Wiki](https://github.com/openomen/openomen/wiki) · [Discord](https://discord.gg/UHQ5cztbUj) · [Report a Bug](https://github.com/openomen/openomen/issues) · [Request a Feature](https://github.com/openomen/openomen/issues)

</div>

---

## About

OpenOMEN is a free, open-source replacement for the Windows only **OMEN Gaming Hub** application, built for Linux users who don't want to dual-boot just to control their hardware.

It currently lets you:

- 🌀 Manage **fan speed and fan profiles**
- ⚡ Switch **power profiles**
- 📊 View **real-time CPU and GPU stats**
- 🌈 Partial 50/50 **Keyboard RGB support**
  
Planned features include:

- 📈 Manual fan curves
- 🖥️ GUI version built ontop of the CLI
- 🔧 HP-WMI EC support

> OpenOMEN is community-maintained and not affiliated with HP. See the [Disclaimer](#disclaimer) below.

> If you're looking for information on usage, see the [Usage](#usage) section below.

---

## Table of Contents

- [Supported Devices](#supported-devices)
- [Supported Linux Distributions](#supported-linux-distributions)
- [Installation](#installation)
- [Updating](#updating)
- [Uninstalling](#uninstalling)
- [Usage](#usage)
- [Contributing](#contributing)
- [Support & Community](#support--community)
- [FAQ](#faq)
- [License](#license)
- [Disclaimer](#disclaimer)

---

## Supported Devices

The following devices have been tested and confirmed to work without model-specific issues:

| Device               | Status | Support     | Notes     |
|----------------------|:------:|-------------|-----------|
| Victus 17 17z-db100  |   ✅   | Since v0.1 |            |
| Victus 16 16-ap0xxx  |   ✅   | Since v0.1 |            |
| Victus 16 16-r0xxx   |   ✅   | Since v0.1 |            |
| Victus 15 15-fb0xxx  |   ✅   | Since v0.1 |            |
| HP OMEN X 2S         |   ✅   | Since v0.1 |            |
| HP OMEN 15           |   ✅   | Since v0.1 |            |
| HP OMEN 17           |   ✅   | Since v0.1 |            |
| HP OMEN 16           |   ✅   | Since v0.1 |            |

Most HP OMEN / Victus laptops share similar embedded-controller architectures, so devices outside this list often work too but this isn't guaranteed, since firmware varies by model.

**Don't see your device?** Test it and [let us know](https://github.com/openomen/openomen/issues) how it works so we can update the list!

---

## Supported Linux Distributions

OpenOMEN has been tested on **Linux 5.14 to Linux 7.1**, on:

- Arch Linux
- NixOS 26.05
- Ubuntu (22/24/26 LTS)
- CachyOS

It should also work on most distributions, as long as the required dependencies are available, like the `hp-wmi` library. For Power Profiles, your kernel must support `platform_profile` (Linux 5.17+).

Use `openomen doctor` to test your computer's and kernel's capabilities.

---

## Installation

### Automated Global Installation
On your terminal, run:
```bash
curl -fsSL https://raw.githubusercontent.com/openomen/openomen/main/install.sh | sudo bash
```

This will automatically install the latest **OpenOMEN Release Binary** to `/usr/local/bin`.

## Debian Install

For 64-bit (`amd64`) Debian/Ubuntu systems.

1. Add the Repository Public Key
```bash
sudo install -d -m 755 /etc/apt/keyrings
curl -fsSL https://pratschi.github.io/apt/openomen-archive.asc | sudo gpg --dearmor -o /etc/apt/keyrings/openomen.gpg > /dev/null
```

2. Add the Repository
```bash
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/openomen.gpg] https://openomen.github.io/apt stable main" | sudo tee /etc/apt/sources.list.d/openomen.list > /dev/null
```

3. Update APT and Install OpenOMEN
```bash
sudo apt update
sudo apt install openomen
```

## Manual Install
1. Get **OpenOMEN's** [Latest Release](https://github.com/openomen/openomen/releases/latest).
2. Download the release file (`openomen`).
3. Move it to a directory on your `$PATH`, typically `/usr/local/bin`:
   ```bash
   sudo mv openomen /usr/local/bin/
   sudo chmod +x /usr/local/bin/openomen
   ```
4. Verify it works:
   ```bash
   openomen --version
   ```

---

## Updating

You can directly update **OpenOMEN** by running:
```bash
openomen update
```

If you seem to have connection or certificate issues, you can, as a last resource, use the `--force` parameter at your own risk.

To manually update **OpenOMEN**, download the latest release's binary and replace your existing binary. (If **OpenOMEN** is in your path, you can use `which openomen` to find it.)

---

## Uninstalling

Uninstalling **OpenOMEN** only requires deleting the original binary. (In automated installs, located in `/usr/local/bin/openomen`).

If you want to also delete your configuration (not neccesary, less than a megabyte), it is located in `~/.config/openomen`, so different users may have each own configuration.

---

## Usage

**OpenOMEN** has a variety of commands that allow for different operations.

For a detailed guide on all of them, see the [Usage Guide](USAGE.md)

---

## Contributing

Contributions are welcome and appreciated, whether that's code, documentation, bug reports, or testing on new hardware.

1. Fork or Clone the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Open a Pull Request describing what you changed and why

If you're planning a larger change, please open an issue first so it can be discussed before you put in the work.

Bug reports and feature requests are just as valuable as code, please [open an issue](https://github.com/openomen/openomen/issues) for either.

---

## Support & Community

- 🐛 **Bugs & feature requests:** [open an issue](https://github.com/openomen/openomen/issues)
- 💬 **Chat, help, and discussion:** [join the Discord server](https://discord.gg/UHQ5cztbUj)

---

## FAQ

**How does OpenOMEN work?**<br>
Openomen uses the integrated `hp-wmi` library built inside Linux to manage your `HP OMEN/Victus's` Embedded Controller (EC) that manages your fans, keyboard lighting, power profiles and more.

<br>**What files does OpenOMEN create?**<br>
**OpenOMEN** has every feature embedded into a single binary and only creates `~/.config/openomen` on your user folder when saving data such as your keybord RGB profiles.

<br>**Is OpenOMEN safe to use?**<br>
**OpenOMEN** does not obtain any data and doesn't use an Internet connection. But, some devices could suffer problems when interacting with the Embedded Controller. If this happens, you can report it and obtain support on the [Discord server](https://discord.gg/UHQ5cztbUj).

---

## License

**OpenOMEN** is a free, *open-source* project under the **GPL-3.0 License.**

See the `LICENSE` file included within this source code folder, if no copy of it has been provided, you can obtain a copy at <https://www.gnu.org/licenses/gpl-3.0.html>.

---

## Disclaimer

OpenOMEN is an independent, open-source project and is **not affiliated with, endorsed by, or sponsored by HP Inc.** or the OMEN / Victus brands.

"OMEN" and "Victus" are trademarks of HP Inc. Any references to them in this project are strictly for the purpose of device compatibility and identification.

This software is provided **"as is"**, without warranty of any kind, express or implied. By using this software, you acknowledge that:

- You are responsible for any potential damage to your device.
- Modifying hardware or system behavior may void your warranty.
- The authors and contributors are not liable for any outcome resulting from the use of this software.

**Use this software at your own risk.**
