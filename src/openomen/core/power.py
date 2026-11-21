""" ACPI platform profiles and combined (power + fan) profiles. """

import os

from . import fans, log
from .errors import OpenOMENError

PROFILE_CHOICES_PATH = "/sys/firmware/acpi/platform_profile_choices"
PROFILE_PATH = "/sys/firmware/acpi/platform_profile"

# Combined profiles: name -> (ACPI profiles in order of preference, fan_mode).
# The first ACPI profile the machine actually offers is used, since boards
# expose different sets (e.g. 'quiet' vs 'cool' vs 'low-power').
COMBINED_PROFILES = {
    "gaming":   (["performance"],               "max"),
    "balanced": (["balanced"],                  "auto"),
    "quiet":    (["quiet", "low-power", "cool"], "auto"),
}

KERNEL_HINT = "Make sure your kernel supports platform profiles (5.15+)."


def read_choices_file():
    """ ACPI profile choices; raises OSError if the file can't be read. """
    with open(PROFILE_CHOICES_PATH, 'r') as f:
        return f.read().strip().split()


def read_power_profile_choices():
    """ Return the list of ACPI profiles this machine supports, or None if unreadable (logged). """
    try:
        return read_choices_file()
    except IOError as e:
        log.error(f"Error reading profile choices: {e}")
        log.error(KERNEL_HINT)
        return None


def _choices_or_raise():
    try:
        return read_choices_file()
    except IOError as e:
        raise OpenOMENError(f"Error reading profile choices: {e}", KERNEL_HINT)


def read_power_profile():
    """ Current ACPI power profile, or None if unavailable (logged). """
    if not os.path.exists(PROFILE_PATH):
        log.error("Error: ACPI platform_profile not found.")
        log.error(KERNEL_HINT)
        return None
    try:
        with open(PROFILE_PATH, 'r') as f:
            return f.read().strip()
    except IOError as e:
        log.error(f"Error reading power profile: {e}")
        return None


def get_power_status():
    """ {"current": str|None, "choices": [..]|None, "combined": [..]} """
    return {
        "current": read_power_profile(),
        "choices": read_power_profile_choices(),
        "combined": list(COMBINED_PROFILES.keys()),
    }


def validate_power_profile(profile):
    """ Return the normalised profile name, or raise if this machine doesn't offer it. """
    valid = _choices_or_raise()
    profile = profile.lower()
    if profile not in valid:
        raise OpenOMENError(f"Error: '{profile}' is not a valid profile.",
                            f"Available profiles: {', '.join(valid)}")
    return profile


def set_power_profile(profile):
    """ Set the ACPI power profile. Needs root. Returns the profile that was set. """
    profile = validate_power_profile(profile)
    try:
        with open(PROFILE_PATH, 'w') as f:
            f.write(profile)
    except PermissionError:
        raise OpenOMENError("Error: Permission denied. Run with sudo.")
    except IOError as e:
        raise OpenOMENError(f"Error writing power profile: {e}")
    return profile


def resolve_combined_profile(name):
    """
    Validate a combined profile without touching hardware.
    Returns (name, acpi_profile, fan_mode) or raises.
    """
    name = name.lower()
    if name not in COMBINED_PROFILES:
        raise OpenOMENError(f"Error: Unknown profile '{name}'.",
                            f"Available profiles: {', '.join(COMBINED_PROFILES.keys())}")
    preferred, fan_mode = COMBINED_PROFILES[name]

    choices = _choices_or_raise()
    acpi_profile = next((p for p in preferred if p in choices), None)
    if acpi_profile is None:
        raise OpenOMENError(f"Error: this machine offers none of {', '.join(preferred)} "
                            f"for the '{name}' profile.",
                            f"Available ACPI profiles: {', '.join(choices)}")
    if not fans.find_hwmon_path():
        raise OpenOMENError("Error: Could not find hp-wmi hwmon device for fan control.",
                            "Make sure the hp-wmi kernel module is loaded.")
    return name, acpi_profile, fan_mode


def current_combined_profile(acpi_profile, fan_mode):
    """
    Name of the combined profile the given state matches ('gaming', ...), or None.
    `fan_mode` is 'max' / 'auto' as returned by fans.get_fan_status().
    """
    for name, (preferred, profile_fan_mode) in COMBINED_PROFILES.items():
        if acpi_profile in preferred and fan_mode == profile_fan_mode:
            return name
    return None


def apply_combined_profile(name):
    """
    Apply a combined profile (power mode + fan mode). Needs root.
    Stops on the first failure so a profile is never left half-applied
    unnoticed; the raised error says how far it got.
    """
    name, acpi_profile, fan_mode = resolve_combined_profile(name)
    try:
        set_power_profile(acpi_profile)
    except OpenOMENError as e:
        raise OpenOMENError(*e.lines, f"Profile '{name}' was not applied; fan mode left unchanged.")
    try:
        fans.set_fan_mode(fan_mode)
    except OpenOMENError as e:
        raise OpenOMENError(*e.lines, f"Profile '{name}' only partly applied: power profile is "
                                      f"'{acpi_profile}', but the fan mode could not be set.")
    return {"name": name, "acpi_profile": acpi_profile, "fan_mode": fan_mode}
