<div align="center">

# OpenOMEN

**Unofficial CLI, driver, and daemon for managing HP OMEN / Victus laptops on Linux**

[![Latest Release](https://img.shields.io/github/v/release/openomen/openomen?label=release)](https://github.com/openomen/openomen/releases/latest)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Discord](https://img.shields.io/discord/UHQ5cztbUj?label=discord&logo=discord)](https://discord.gg/UHQ5cztbUj)
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

---

## Table of Contents

- [Supported Devices](#supported-devices)
- [Supported Distributions](#supported-linux-distributions)
- [Installation](#installation)
- [Usage](#usage)
- [Updating](#updating)
- [Uninstalling](#uninstalling)
- [Contributing](#contributing)
- [Support & Community](#support--community)
- [FAQ](#faq)
- [License](#license)
- [Disclaimer](#disclaimer)

---

## Supported Devices

The following devices have been tested and confirmed to work without model-specific issues:

| Device               | Status | Notes                                       |
|----------------------|:------:|----------------------------------------------|
| Victus 17 17z-db100  |   ✅   | Confirmed working, supported since v0.1       |
| Victus 16 16-ap0xxx  |   ✅   | Confirmed working, supported since v0.1       |
| Victus 16 16-r0xxx   |   ✅   | Confirmed working, supported since v0.1       |
| Victus 15 15-fb0xxx  |   ✅   | Confirmed working, supported since v0.1       |
| HP OMEN X 2S         |   ✅   | Confirmed working, supported since v0.1       |
| HP OMEN 17           |   ✅   | Confirmed working, supported since v0.1       |
| HP OMEN 16           |   ✅   | Confirmed working, supported since v0.1       |

Most HP OMEN / Victus laptops share similar embedded-controller architectures, so devices outside this list often work too but this isn't guaranteed, since firmware varies by model.

**Don't see your device?** Try it and [let us know](https://github.com/openomen/openomen/issues) how it went so we can add it to the list if working or not.

---

## Supported Linux Distributions

OpenOMEN has been tested on **Linux 6.18+**, on:

- Arch Linux (7.0.10-arch1-1)
- NixOS 26.05
- Ubuntu (22.04 / 24.04)
- CachyOS

It should also work on most other Debian-based distributions, as long as the required dependencies are available.

---

## Installation

Full instructions live on the [Installation & Updating wiki page](https://github.com/openomen/openomen/wiki), but the quick version:

1. Grab the latest binary from the [Releases page](https://github.com/openomen/openomen/releases/latest).
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

You're now ready to run `openomen` from anywhere in your terminal.

---

## Usage

See the [Usage wiki page](https://github.com/openomen/openomen/wiki/%F0%9F%92%BF-Usage) for the full CLI reference, examples, and configuration options.

---

## Updating

Update in place with:

```bash
openomen update
```

Or manually, by downloading the latest release and replacing your existing `openomen` binary.

---

## Uninstalling

See the [Uninstall wiki page](https://github.com/openomen/openomen/wiki/%E2%9D%8C-Uninstall) for full removal steps, including cleaning up any daemon/service files.

---

## Contributing

Contributions are welcome and appreciated, whether that's code, documentation, bug reports, or testing on new hardware.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Open a Pull Request describing what you changed and why

If you're planning a larger change, please open an issue first so it can be discussed before you put in the work.

Bug reports and feature requests are just as valuable as code, please [open an issue](https://github.com/openomen/openomen/issues) for either.

---

## Support & Community

- 🐛 **Bugs & feature requests:** [open an issue](https://github.com/openomen/openomen/issues)
- 💬 **Chat, help, and discussion:** [join the Discord server](https://discord.gg/UHQ5cztbUj)
- 📖 **Documentation:** [check the Wiki](https://github.com/openomen/openomen/wiki)

---

## FAQ

Common questions are answered on the [Support & FAQ wiki page](https://github.com/openomen/openomen/wiki/%F0%9F%92%AC-Support-&-FAQ).

---

## Disclaimer

OpenOMEN is an independent, open-source project and is **not affiliated with, endorsed by, or sponsored by HP Inc.** or the OMEN / Victus brands.

"OMEN" and "Victus" are trademarks of HP Inc. Any references to them in this project are strictly for the purpose of device compatibility and identification.

This software is provided **"as is"**, without warranty of any kind, express or implied. By using this software, you acknowledge that:

- You are responsible for any potential damage to your device.
- Modifying hardware or system behavior may void your warranty.
- The authors and contributors are not liable for any outcome resulting from the use of this software.

**Use this software at your own risk.**
