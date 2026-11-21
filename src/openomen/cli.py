"""
OpenOMEN - CLI tool for controlling fan and RGB behavior on HP OMEN/Victus laptops
audixdev - (C) Copyright 2026 - GPL-3.0 License

The command line front-end: argument parsing, getting root, and turning the
data returned by openomen.core into text (or JSON with --json).
"""

import argparse
import json
import logging
import os
import sys
import time

from . import VERSION
from .core import OpenOMENError, cpu, doctor, fans, gpu, power, rgb, system, update
from .core.runtime import is_frozen, is_root, restore_child_library_path

CLEAR_SCREEN = "\033[2J\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
WATCH_INTERVAL = 1.5


# ---------------------------------------------------------------- helpers

def setup_logging():
    """ Core reports non-fatal problems through the 'openomen' logger; show them on stderr as-is. """
    logger = logging.getLogger("openomen")
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.handlers[:] = [handler]
    logger.setLevel(logging.WARNING)
    logger.propagate = False


def print_error(error):
    for line in error.lines:
        print(line, file=sys.stderr)


def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def ensure_root():
    """ Re-run this exact command through sudo when we're not root (replaces the process). """
    if is_root():
        return
    # PyInstaller sets sys.executable to the actual binary path
    script_path = sys.executable if is_frozen() else os.path.abspath(sys.argv[0])
    args = ['sudo', script_path] + sys.argv[1:]
    try:
        os.execvp('sudo', args)
    except FileNotFoundError:
        print("Error: this command needs root, but 'sudo' was not found.", file=sys.stderr)
        print("Run it as root instead (e.g. 'su -c \"openomen ...\"').", file=sys.stderr)
        sys.exit(1)


def monitor_stats_loop(render, interval=WATCH_INTERVAL):
    """ Redraw `render` every `interval` seconds. """
    try:
        while True:
            sys.stdout.write(CLEAR_SCREEN)
            sys.stdout.write(HIDE_CURSOR)
            sys.stdout.flush()
            print("=== OpenOMEN Monitor Mode (Ctrl+C to exit) ===")
            print()
            render()
            time.sleep(interval)
    except KeyboardInterrupt:
        pass
    finally:
        print(SHOW_CURSOR, end="", flush=True)
        print("\nExited.")


def json_watch_loop(collect, interval=WATCH_INTERVAL):
    """ --json with --watch: one compact JSON object per line, every `interval` seconds. """
    try:
        while True:
            print(json.dumps(collect(), ensure_ascii=False), flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        pass


def run_read_command(args, render, collect):
    """ Shared handling of -w/--watch and --json for the read-only commands. """
    if args.json:
        if args.watch:
            json_watch_loop(collect)
            return 0
        print_json(collect())
        return 0
    if args.watch:
        monitor_stats_loop(render)
        return 0
    return 0 if render() else 1


# ---------------------------------------------------------------- fans

def print_fan_status():
    status = fans.get_fan_status()
    label = {"max": "Max (Manual control)", "auto": "Auto (BIOS control)"}.get(status["mode"], "Unknown")
    print(f"Fan Status:       {label}")
    if "fan1" in status["rpm"]:
        print(f"Fan 1 RPM:        {status['rpm']['fan1']} RPM")
    if "fan2" in status["rpm"]:
        print(f"Fan 2 RPM:        {status['rpm']['fan2']} RPM")
    return status["raw"] is not None


def cmd_fan_set(mode):
    try:
        fans.require_hwmon()
        # Only ask for root once we know the hardware and mode are valid.
        ensure_root()
        fans.set_fan_mode(mode)
    except OpenOMENError as e:
        print_error(e)
        return False
    print(fans.MODE_SET_MESSAGES[mode])
    return True


def cmd_fan_toggle():
    try:
        mode = fans.next_toggle_mode()
    except OpenOMENError as e:
        print_error(e)
        return False
    return cmd_fan_set(mode)


# ---------------------------------------------------------------- cpu / gpu

def collect_cpu_stats():
    sampler = cpu.CpuSampler()
    sampler.sample()
    time.sleep(0.5)
    return cpu.get_cpu_stats(sampler)


def print_cpu_stats():
    print(f"CPU:              {cpu.read_cpu_name()}\n")

    temp = cpu.find_cpu_temperature()
    if temp:
        label = temp["label"] + ": " if temp["label"] else ""
        print(f"{label}Temperature: {temp['celsius']:.1f}°C")

    try:
        # Two reads 500ms apart to get a real usage
        sampler = cpu.CpuSampler()
        sampler.sample()
        time.sleep(0.5)
        cores = sampler.sample()

        print()  # just an blank line before core table
        for core in cores:
            usage = core["usage"]
            freq = f"  {core['freq_mhz']:.0f} MHz" if core["freq_mhz"] is not None else ""
            bar_len = 20
            filled = int(usage / 100 * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"  Core {core['cpu']:<2}  [{bar}] {usage:5.1f}%{freq}")
    except KeyboardInterrupt:
        print("\nCPU stats reading cancelled by user.")
        return False
    except IOError as e:
        print(f"Error reading CPU stats: {e}", file=sys.stderr)
        return False
    return True


GPU_HEADER_PADDING = {"NVIDIA": "    ", "AMD": "       ", "Intel": "     "}


def collect_gpu_stats():
    return [gpu.public(g) for g in gpu.query_gpus()]


def print_gpu_stats(quiet_missing=False):
    """
    quiet_missing: print a plain "No GPU detected" line to stdout instead of an error
    on stderr (used by dashboards, where a missing GPU is not a failure).
    """
    try:
        gpus = gpu.query_gpus()
    except KeyboardInterrupt:
        print("\nGPU stats reading cancelled by user.")
        return False

    for g in gpus:
        raw = g["_raw"]
        print(f"GPU {g['index']} ({g['vendor']}):{GPU_HEADER_PADDING[g['vendor']]}{g['name']}")
        if g["vendor"] == "NVIDIA":
            print(f"  Temperature:    {raw['temperature']}°C")
            print(f"  Utilization:    {raw['utilization']}%")
            print(f"  VRAM:           {raw['vram_used']} / {raw['vram_total']} MiB")
            print(f"  Power Draw:     {raw['power']} W\n")
            continue
        if g["temperature_c"] is not None:
            print(f"  Temperature:    {g['temperature_c']:.1f}°C")
        if "utilization" in raw:
            print(f"  Utilization:    {raw['utilization']}%")
        if "frequency" in raw:
            print(f"  Frequency:      {raw['frequency']} MHz")
        print()

    if not gpus:
        if quiet_missing:
            print("No GPU detected.")
        else:
            print("Error: No GPU found (nvidia-smi unavailable, no AMD/Intel hwmon).", file=sys.stderr)
        return False
    return True


# ---------------------------------------------------------------- stats dashboard

def collect_all_stats():
    return {
        "fan": fans.get_fan_status(),
        "power": {"profile": power.read_power_profile()},
        "cpu": collect_cpu_stats(),
        "gpus": collect_gpu_stats(),
    }


def print_all_stats():
    """ Unified dashboard: fan status, power profile, CPU stats and GPU stats. """
    print("─── Fan ──────────────────────────")
    print_fan_status()
    print()

    print("─── Power ────────────────────────")
    power_profile = power.read_power_profile()
    print(f"Power Profile:    {power_profile if power_profile else 'Unknown'}")
    print()

    print("─── CPU ──────────────────────────")
    print_cpu_stats()
    print()

    print("─── GPU ──────────────────────────")
    print_gpu_stats(quiet_missing=True)
    return True


# ---------------------------------------------------------------- info

def print_system_info():
    """ System information for debugging and bug reports. """
    info = system.get_system_info()

    print("OpenOMEN System Information")
    print("=" * 50)
    print(f"OpenOMEN Version: {info['version']}")
    print()

    if info["kernel"] is not None:
        print(f"Kernel Version: {info['kernel']}")
    else:
        print("Kernel Version: Unable to read /proc/version")
    print()

    print("CPU Information:")
    cpu_info = info["cpu"]
    if cpu_info["model"] is not None:
        print(f"  Model: {cpu_info['model']}")
    elif cpu_info["model_error"] == "missing":
        print("  Model: Unable to detect")
    else:
        print("  Model: Unable to read /proc/cpuinfo")
    print(f"  Cores: {cpu_info['cores']}" if cpu_info["cores"] is not None else "  Cores: Unable to detect")
    print()

    print("GPU Information:")
    for g in info["gpus"]:
        if g["vendor"] == "NVIDIA":
            print(f"  NVIDIA: {g['name']} (Driver: {g['driver']})")
        elif g["vendor"] == "AMD":
            print(f"  AMD: GPU detected (Driver: {g['driver']})")
        else:
            print("  Intel: iGPU / Arc Desktop Graphics detected")
    if not info["gpus"]:
        print("  No supported GPU detected")
    print()

    print("hwmon Drivers:")
    if info["hwmon"]["present"]:
        for device in info["hwmon"]["devices"]:
            print(f"  {device['id']}: {device['name']}")
    else:
        print("  No hwmon devices found")
    hp_wmi = info["hp_wmi"]
    if hp_wmi["status"] == "found":
        print(f"  hp-wmi: Found ({hp_wmi['devices']} device(s))")
    elif hp_wmi["status"] == "no_hwmon":
        print("  hp-wmi: Platform found but no hwmon devices")
    else:
        print("  hp-wmi: Not found")
    print()

    print("ACPI Platform Profiles:")
    acpi = info["acpi"]
    print({"ok": f"  Available: {', '.join(acpi['choices'] or [])}",
           "unreadable": "  Available: Unable to read choices",
           "unsupported": "  Available: Not supported"}[acpi["choices_status"]])
    print({"ok": f"  Current: {acpi['current']}",
           "unreadable": "  Current: Unable to read",
           "unsupported": "  Current: Not supported"}[acpi["current_status"]])
    print()

    print("Fan Control:")
    fan = info["fan"]
    if fan["hwmon_path"]:
        print(f"  hwmon path: {fan['hwmon_path']}")
        if fan["pwm1_status"] == "ok":
            status_map = {"0": "Max (Manual)", "2": "Auto (BIOS)"}
            value = fan["pwm1_enable"]
            print(f"  pwm1_enable: {status_map.get(value, f'Unknown ({value})')}")
        elif fan["pwm1_status"] == "unreadable":
            print("  pwm1_enable: Unable to read")
        else:
            print("  pwm1_enable: Not found")
        if fan["rpm"]:
            for name, rpm in fan["rpm"].items():
                print(f"  {name}_input: {rpm} RPM")
        else:
            print("  fan inputs: Not found")
    else:
        print("  hwmon path: Not found")
        print("  Fan control: hp-wmi hwmon device not available")
    return True


# ---------------------------------------------------------------- power

def cmd_power_set(profile):
    try:
        profile = power.validate_power_profile(profile)
        # Only ask for root once the profile name is known to be valid.
        ensure_root()
        power.set_power_profile(profile)
    except OpenOMENError as e:
        print_error(e)
        return False
    print(f"Power profile set to: {profile}")
    return True


def cmd_power_apply(name):
    """ Apply a combined profile (power mode + fan setting), reporting each step. """
    try:
        # Validate everything before asking for root or touching hardware.
        name, acpi_profile, fan_mode = power.resolve_combined_profile(name)
    except OpenOMENError as e:
        print_error(e)
        return False

    ensure_root()
    print(f"Applying '{name}' profile...")

    # Stop on the first failure so a profile is never left half-applied
    # (for example fans on max without the performance power profile).
    if not cmd_power_set(acpi_profile):
        print(f"Profile '{name}' was not applied; fan mode left unchanged.", file=sys.stderr)
        return False
    if not cmd_fan_set(fan_mode):
        print(f"Profile '{name}' only partly applied: power profile is '{acpi_profile}', "
              "but the fan mode could not be set.", file=sys.stderr)
        return False

    print(f"Profile '{name}' applied successfully.")
    return True


def cmd_power_list(as_json):
    try:
        choices = power.read_choices_file()
    except IOError as e:
        print(f"Error: {e}", file=sys.stderr)
        return False
    if as_json:
        print_json({"acpi": choices, "combined": list(power.COMBINED_PROFILES.keys()),
                    "current": power.read_power_profile()})
        return True
    print("ACPI profiles:    " + ", ".join(choices))
    print("Combined profiles: " + ", ".join(power.COMBINED_PROFILES.keys()))
    return True


# ---------------------------------------------------------------- rgb

def cmd_rgb_status(as_json):
    status = rgb.get_rgb_status()
    if as_json:
        print_json(status)
        return True
    print(f"Keyboard Lights: {'On' if status['enabled'] else 'Off'}")
    print(f"Current Profile: {status['active_name']}" if status["active_name"] else "Current Profile: None set")
    names = ', '.join(p.get('name', pid) for pid, p in status["profiles"].items())
    print(f"Available Profiles: {names or 'None'}")
    return True


def cmd_rgb_list(as_json):
    profiles = rgb.list_rgb_profiles()
    if as_json:
        print_json(profiles)
        return True
    if not profiles:
        print("No RGB profiles found.")
        return True
    print("Available Profiles:")
    for profile_id, data in profiles.items():
        name = data.get("name", profile_id)
        desc = data.get("description", "")
        print(f" - {name}: {desc}" if desc else f" - {name}")
    return True


def cmd_rgb_set(name):
    """ Select a profile and show it on the keyboard (this also turns the lights on). """
    try:
        profile_id, profile = rgb.resolve_profile(name)
        rgb.require_rgb_hardware()
        # Elevate before printing anything, so the re-exec under sudo doesn't print twice.
        ensure_root()
        print(rgb.apply_rgb_hardware(profile))
        # Save state only after the hardware write succeeded.
        rgb.save_active_profile(profile_id)
    except OpenOMENError as e:
        print_error(e)
        return False
    print(f"RGB Profile set to {profile.get('name', profile_id)} (keyboard lights on)")
    return True


def cmd_rgb_power(on):
    try:
        rgb.require_rgb_hardware()
        ensure_root()
        profile_id, profile = rgb.active_profile_for_power_on() if on else (None, None)
        # Write the hardware first; only record the new state if that worked.
        print(rgb.apply_rgb_hardware(profile))
        rgb.save_enabled(on)
    except OpenOMENError as e:
        print_error(e)
        return False
    if on:
        print(f"Keyboard lights on (profile: {profile.get('name', profile_id)})")
    else:
        print("Keyboard lights off")
    return True


# ---------------------------------------------------------------- doctor

def print_doctor():
    print(f"OpenOMEN {VERSION} — Hardware Compatibility Check\n")
    result = doctor.run_checks()
    titles = dict(doctor.SECTIONS)
    current = None
    for check in result["checks"]:
        if check["section"] != current:
            title = titles[check["section"]]
            prefix = "" if current is None else "\n"
            # Section rules are padded to a fixed width, like "─── Fan Control ─────..."
            print(f"{prefix}─── {title} {'─' * (SECTION_RULE_WIDTH[check['section']])}")
            current = check["section"]
        print(f"[{'✓' if check['ok'] else '✗'}] {check['message']}")
    print(f"\nDoctor complete: {result['passed']} passed, {result['failed']} failed.")
    return result


# Number of trailing '─' after each doctor section title (kept from the original output).
SECTION_RULE_WIDTH = {
    "kernel": 17,
    "fan": 22,
    "thermal": 18,
    "power": 19,
    "gpu": 24,
    "battery": 26,
    "rgb": 22,
}


# ---------------------------------------------------------------- argument parsing

def build_parser():
    parser = argparse.ArgumentParser(
        description=f"CLI tool for controlling fans, power and RGB on HP OMEN/Victus laptops - V{VERSION} - audixdev",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands: fan, cpu, gpu, stats, info, power, rgb, doctor, update
Run 'openomen <command> --help' for details.
Run 'openomen <command> -w' to watch in real-time.
"""
    )

    def add_watch(p):
        p.add_argument('-w', '--watch', action='store_true', help='Refresh every 1.5 seconds (exit with Ctrl+C)')

    def add_json(p):
        p.add_argument('--json', action='store_true', help='Print machine-readable JSON')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    fan_parser = subparsers.add_parser('fan', help='Control fan behavior')
    fan_subparsers = fan_parser.add_subparsers(dest='fan_command', help='Fan commands')
    fan_subparsers.add_parser('max', help='Fans at maximum RPM')
    fan_subparsers.add_parser('auto', help='Auto/BIOS control')
    fan_subparsers.add_parser('toggle', help='Toggle fan max on/off')
    fan_status_parser = fan_subparsers.add_parser('status', help='Show current fan status')
    add_watch(fan_status_parser)
    add_json(fan_status_parser)
    cpu_parser = subparsers.add_parser('cpu', help='Read current CPU stats')
    add_watch(cpu_parser)
    add_json(cpu_parser)
    gpu_parser = subparsers.add_parser('gpu', help='Read current GPU stats')
    add_watch(gpu_parser)
    add_json(gpu_parser)
    stats_parser = subparsers.add_parser('stats', help='Print snapshot of all systems')
    add_watch(stats_parser)
    add_json(stats_parser)
    info_parser = subparsers.add_parser('info', help='Display diagnostic layout parameters')
    add_json(info_parser)
    power_parser = subparsers.add_parser('power', help='Manage power configurations')
    power_subparsers = power_parser.add_subparsers(dest='power_command', help='Power commands')
    set_parser = power_subparsers.add_parser('set', help='Set active ACPI power profile')
    set_parser.add_argument('profile', help='Power profile name (e.g. performance, balanced, quiet)')
    apply_parser = power_subparsers.add_parser('apply', help='Apply predefined profile templates')
    apply_parser.add_argument('profile', help='Combined profile name')
    power_list_parser = power_subparsers.add_parser('list', help='List available profiles')
    add_json(power_list_parser)

    # RGB command
    rgb_parser = subparsers.add_parser('rgb', help='Control keyboard RGB lighting')
    rgb_subparsers = rgb_parser.add_subparsers(dest='rgb_command', help='RGB commands')
    rgb_status_parser = rgb_subparsers.add_parser('status', help='Show current state and active profile')
    add_json(rgb_status_parser)
    rgb_list_parser = rgb_subparsers.add_parser('list', help='List available RGB profiles')
    add_json(rgb_list_parser)
    rgb_set_parser = rgb_subparsers.add_parser('set', help='Set the active RGB profile')
    rgb_set_parser.add_argument('profile', help='Profile name (e.g. rainbow, white, gaming)')
    rgb_subparsers.add_parser('on', help='Turn keyboard lights on')
    rgb_subparsers.add_parser('off', help='Turn keyboard lights off')

    doctor_parser = subparsers.add_parser('doctor', help='Check hardware compatibility and driver status')
    add_json(doctor_parser)

    # Update command with force and verification toggle arguments
    update_parser = subparsers.add_parser('update', help='Update OpenOMEN to the latest version')
    update_parser.add_argument('-f', '--force', action='store_true', help='Force direct update download from releases/latest/download')
    update_parser.add_argument('--no-verify', action='store_false', dest='verify', help='Disable post-download version execution verification')

    parser.add_argument('-v', '--version', action='version', version=f'%(prog)s {VERSION}')
    return parser, {"fan": fan_parser, "power": power_parser, "rgb": rgb_parser}


def main():
    restore_child_library_path()
    setup_logging()
    parser, sub = build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    if args.command == 'fan':
        if not args.fan_command:
            sub["fan"].print_help()
            return 1
        if args.fan_command == 'max':
            return 0 if cmd_fan_set('max') else 1
        if args.fan_command == 'auto':
            return 0 if cmd_fan_set('auto') else 1
        if args.fan_command == 'toggle':
            return 0 if cmd_fan_toggle() else 1
        if args.fan_command == 'status':
            return run_read_command(args, print_fan_status, fans.get_fan_status)

    elif args.command == 'cpu':
        return run_read_command(args, print_cpu_stats, collect_cpu_stats)

    elif args.command == 'gpu':
        return run_read_command(args, print_gpu_stats, collect_gpu_stats)

    elif args.command == 'stats':
        if args.json:
            return run_read_command(args, print_all_stats, collect_all_stats)
        if args.watch:
            monitor_stats_loop(print_all_stats)
            return 0
        print_all_stats()
        return 0

    elif args.command == 'info':
        if args.json:
            print_json(system.get_system_info())
            return 0
        print_system_info()
        return 0

    elif args.command == 'power':
        if not args.power_command:
            sub["power"].print_help()
            return 1
        if args.power_command == 'set':
            return 0 if cmd_power_set(args.profile) else 1
        if args.power_command == 'apply':
            return 0 if cmd_power_apply(args.profile) else 1
        if args.power_command == 'list':
            return 0 if cmd_power_list(args.json) else 1

    elif args.command == 'rgb':
        if not args.rgb_command:
            sub["rgb"].print_help()
            return 1
        if args.rgb_command == 'status':
            return 0 if cmd_rgb_status(args.json) else 1
        if args.rgb_command == 'list':
            return 0 if cmd_rgb_list(args.json) else 1
        if args.rgb_command == 'set':
            return 0 if cmd_rgb_set(args.profile) else 1
        if args.rgb_command == 'on':
            return 0 if cmd_rgb_power(True) else 1
        if args.rgb_command == 'off':
            return 0 if cmd_rgb_power(False) else 1

    elif args.command == 'doctor':
        if args.json:
            print_json(doctor.run_checks())
            return 0
        # Doctor only reads state, so it runs unprivileged; some checks may be less complete.
        if not is_root():
            print("Note: running without root; some checks may be incomplete (try sudo).\n")
        print_doctor()
        return 0

    elif args.command == 'update':
        return 0 if update.update_openomen(force=args.force, verify=args.verify) else 1

    return 0
