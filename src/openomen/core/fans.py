""" Fan RPM and fan mode (hp-wmi pwm1_enable). """

import glob
import os
import time

from . import log
from .errors import OpenOMENError

HP_WMI_HWMON_BASE = "/sys/devices/platform/hp-wmi/hwmon"

# pwm1_enable values
RAW_MAX = "0"
RAW_AUTO = "2"
MODE_TO_RAW = {"max": RAW_MAX, "auto": RAW_AUTO}
RAW_TO_MODE = {RAW_MAX: "max", RAW_AUTO: "auto"}

MODE_SET_MESSAGES = {
    "max": "Max RPM mode enabled, your fan(s) will now run at max RPM speeds.",
    "auto": "Auto mode enabled, your fan(s) will now run at automatic speeds and are controlled by the BIOS again.",
}


def find_hwmon_path():
    """ Dynamically resolve the hwmon path for hp-wmi (the one exposing pwm1_enable). """
    for hwmon_dir in glob.glob(f"{HP_WMI_HWMON_BASE}/hwmon*"):
        if os.path.exists(os.path.join(hwmon_dir, "pwm1_enable")):
            return hwmon_dir
    return None


def read_fan_rpm():
    """ Return {"fan1": rpm, "fan2": rpm} for the fan inputs that exist (may be empty). """
    hwmon_path = find_hwmon_path()
    if not hwmon_path:
        return {}
    fan_rpm = {}
    for fan in ("fan1", "fan2"):
        path = os.path.join(hwmon_path, f"{fan}_input")
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    fan_rpm[fan] = int(f.read().strip())
            except (IOError, ValueError):
                pass
    return fan_rpm


def read_fan_mode_raw():
    """ Raw pwm1_enable value ('0' max, '2' auto, ...) or None if unavailable. """
    hwmon_path = find_hwmon_path()
    if not hwmon_path:
        return None
    try:
        with open(os.path.join(hwmon_path, "pwm1_enable"), 'r') as f:
            return f.read().strip()
    except IOError as e:
        log.error(f"Error: Failed to read pwm1_enable: {e}")
        return None


def get_fan_status():
    """
    Snapshot of the fans:
        {"mode": "max" | "auto" | "unknown", "raw": "0"/"2"/None, "rpm": {"fan1": int, ...}}
    """
    raw = read_fan_mode_raw()
    return {
        "mode": RAW_TO_MODE.get(raw, "unknown"),
        "raw": raw,
        "rpm": read_fan_rpm(),
    }


def require_hwmon():
    """ Return the hp-wmi hwmon path or raise when fan control is unavailable. """
    hwmon_path = find_hwmon_path()
    if not hwmon_path:
        raise OpenOMENError("Error: Could not find hp-wmi hwmon device.",
                            "Make sure the hp-wmi kernel module is loaded.")
    return hwmon_path


def set_fan_mode(mode):
    """ Set fan mode to 'max' or 'auto' and verify it stuck. Needs root. """
    hwmon_path = require_hwmon()
    if mode not in MODE_TO_RAW:
        raise OpenOMENError("Error: Invalid mode. Use 'max' or 'auto'.")
    expected_value = MODE_TO_RAW[mode]
    pwm_enable_path = os.path.join(hwmon_path, "pwm1_enable")

    try:
        with open(pwm_enable_path, 'w') as f:
            f.write(expected_value)
    except PermissionError:
        raise OpenOMENError("Error: Permission denied writing to pwm1_enable.",
                            "Make sure you're running with sudo.")
    except IOError as e:
        raise OpenOMENError(f"Error: Failed to write to pwm1_enable: {e}")

    # Verify the write actually stuck by reading back the value
    time.sleep(0.1)  # Small delay for sanity check!!
    actual_value = read_fan_mode_raw()
    if actual_value != expected_value:
        raise OpenOMENError(
            "Error: pwm1_enable write failed to stick!",
            f"Expected: {expected_value}, Actual: {actual_value}",
            "This may indicate a hardware/firmware issue or blocked access.",
            "Try checking if any other daemon is managing fan control.",
        )


def next_toggle_mode():
    """ The mode a toggle switches to ('max' or 'auto'), based on the current one. """
    current = read_fan_mode_raw()
    if current is None:
        raise OpenOMENError("Error: Could not read current fan control status.")
    if current == RAW_AUTO:
        return "max"
    if current == RAW_MAX:
        return "auto"
    raise OpenOMENError(f"Error: Unknown fan control status: {current}")
