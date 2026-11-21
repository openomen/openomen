""" Hardware compatibility checks (`openomen doctor`). """

import glob
import os
import shutil
import subprocess

from . import cpu, fans, power
from .gpu import VENDOR_AMD, VENDOR_INTEL, get_amd_driver_info
from .rgb import detect_rgb_hardware

# Section ids in display order, with their titles.
SECTIONS = [
    ("kernel", "Kernel & Drivers"),
    ("fan", "Fan Control"),
    ("thermal", "Thermal Sensors"),
    ("power", "Power Profiles"),
    ("gpu", "GPU Stats"),
    ("battery", "Battery"),
    ("rgb", "RGB Keyboard"),
]


def _check(section, ok, message, weight=1):
    """ weight: how many checks this line stands for (a missing device fails several at once). """
    return {"section": section, "ok": ok, "message": message, "weight": weight}


def _module_loaded(name):
    """ True/False, falling back to lsmod when /proc/modules is unreadable. """
    try:
        with open("/proc/modules", "r") as f:
            return name in f.read()
    except IOError:
        try:
            result = subprocess.run(["lsmod"], capture_output=True, text=True, timeout=5)
            return name in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False


def _kernel_checks():
    if _module_loaded("hp_wmi"):
        yield _check("kernel", True, "hp-wmi kernel module loaded")
    else:
        yield _check("kernel", False, "hp-wmi kernel module not loaded")
    if _module_loaded("hp_wmi_ec"):
        yield _check("kernel", True, "hp_wmi_ec module loaded")
    else:
        yield _check("kernel", False, "hp_wmi_ec module not found (some models need this instead)")


def _read_fan_input(path):
    with open(path, 'r') as f:
        return int(f.read().strip())


def _fan_checks():
    hwmon_path = fans.find_hwmon_path()
    if not hwmon_path:
        yield _check("fan", False, "pwm1_enable not found (hp-wmi hwmon device unavailable)", weight=4)
        return
    yield _check("fan", True, f"pwm1_enable found at {hwmon_path}")

    if os.access(os.path.join(hwmon_path, "pwm1_enable"), os.W_OK):
        yield _check("fan", True, "pwm1_enable is writable")
    else:
        yield _check("fan", False, "pwm1_enable not writable (sudo required for fan control)")

    for fan, missing in (("fan1", "fan1_input not found"),
                         ("fan2", "fan2_input not found — single fan model or unsupported")):
        path = os.path.join(hwmon_path, f"{fan}_input")
        if os.path.exists(path) and os.access(path, os.R_OK):
            try:
                rpm = _read_fan_input(path)
                yield _check("fan", True, f"{fan}_input readable — {rpm} RPM")
            except (IOError, ValueError):
                yield _check("fan", False, f"{fan}_input not readable (permission denied or invalid data)")
        else:
            yield _check("fan", False, missing)


def _thermal_checks():
    hwmon_by_driver = cpu.scan_hwmon_temps()
    for driver in cpu.CPU_DRIVER_PRIORITY:
        for _hwmon_dir, temps in hwmon_by_driver.get(driver, []):
            for raw_label, temp_celsius in temps:
                if any(kw in raw_label for kw in cpu.SKIP_LABEL_KEYWORDS):
                    continue
                yield _check("thermal", True,
                             f"CPU Thermal sensor found (driver: {driver}) — {temp_celsius:.1f}°C")
                return
    yield _check("thermal", False, "No CPU thermal sensor detected")


def _power_checks():
    if os.path.exists(power.PROFILE_PATH) and os.access(power.PROFILE_PATH, os.R_OK):
        try:
            with open(power.PROFILE_PATH, 'r') as f:
                current_profile = f.read().strip()
            yield _check("power", True, f"ACPI platform_profile available — current: {current_profile}")
        except IOError:
            yield _check("power", False, "ACPI platform_profile not readable")
    else:
        yield _check("power", False, "ACPI platform_profile not available")

    if os.path.exists(power.PROFILE_CHOICES_PATH) and os.access(power.PROFILE_CHOICES_PATH, os.R_OK):
        try:
            choices = power.read_choices_file()
            yield _check("power", True, f"Available profiles: {', '.join(choices)}")
        except IOError:
            yield _check("power", False, "platform_profile_choices not readable")
    else:
        yield _check("power", False, "platform_profile_choices not available")


def _gpu_checks():
    has_nvidia_smi = bool(shutil.which('nvidia-smi'))
    if has_nvidia_smi:
        yield _check("gpu", True, "nvidia-smi available")
    else:
        yield _check("gpu", False, "nvidia-smi not found — install nvidia-utils for NVIDIA GPU stats")

    drm_hwmon_found = False
    for card_dir in glob.glob("/sys/class/drm/card*/device"):
        vendor_file = os.path.join(card_dir, "vendor")
        if os.path.exists(vendor_file):
            try:
                with open(vendor_file, 'r') as vf:
                    v_id = vf.read().strip().lower()
            except IOError:
                continue
            if v_id == VENDOR_AMD:
                yield _check("gpu", True, f"AMD GPU hwmon found (Driver: {get_amd_driver_info(card_dir)})")
                drm_hwmon_found = True
            elif v_id == VENDOR_INTEL:
                yield _check("gpu", True, "Intel Graphics (iGPU/Arc) detected")
                drm_hwmon_found = True

    if not drm_hwmon_found and not has_nvidia_smi:
        yield _check("gpu", False, "No GPU hwmon or tools found — no GPU stats available")


def _battery_checks():
    battery_paths = glob.glob("/sys/class/power_supply/BAT*")
    if not battery_paths:
        yield _check("battery", False, "Battery not found", weight=2)
        return
    yield _check("battery", True, f"Battery found: {os.path.basename(battery_paths[0])}")

    charge_control_path = os.path.join(battery_paths[0], "charge_control_end_threshold")
    if os.path.exists(charge_control_path) and os.access(charge_control_path, os.R_OK):
        try:
            with open(charge_control_path, 'r') as f:
                threshold = f.read().strip()
            yield _check("battery", True, f"charge_control_end_threshold available — current: {threshold}")
        except IOError:
            yield _check("battery", False, "charge_control_end_threshold not readable")
    else:
        yield _check("battery", False,
                     "charge_control_end_threshold not found — battery charge limiting unavailable")


def _rgb_checks():
    rgb_hint = detect_rgb_hardware()
    if rgb_hint:
        yield _check("rgb", True, f"RGB control interface detected: {rgb_hint}")
    else:
        yield _check("rgb", False, "No physical RGB control files found "
                                   "(/sys/devices/platform/hp-wmi/rgb_zones, keyboardleds, etc.)")


def run_checks():
    """
    Run every check. Returns
        {"checks": [{"section", "ok", "message", "weight"}, ...], "passed": int, "failed": int}
    """
    checks = []
    for group in (_kernel_checks, _fan_checks, _thermal_checks, _power_checks,
                  _gpu_checks, _battery_checks, _rgb_checks):
        checks.extend(group())
    return {
        "checks": checks,
        "passed": sum(c["weight"] for c in checks if c["ok"]),
        "failed": sum(c["weight"] for c in checks if not c["ok"]),
    }
