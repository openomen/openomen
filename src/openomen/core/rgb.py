"""
RGB keyboard control (0.4.0 — EXPERIMENTAL)

This feature is new and untested across the full range of OMEN/Victus
hardware. If you have a supported device and want to help, see the
Discord: https://discord.gg/UHQ5cztbUj
"""

import glob
import json
import os
import re

from . import log
from .errors import OpenOMENError
from .runtime import chown_to_real_user, real_user_home

FOUR_ZONE_DIR = "/sys/devices/platform/hp-wmi/rgb_zones"
LEGACY_PATH = "/sys/devices/platform/hp-wmi/keyboardleds"
KERNEL_PATCH_PATH = "/sys/class/leds/hp_omen::kbd_backlight/zone_colors"

ZONE_COUNT = 4

NO_HARDWARE_ERROR = ("Error: No supported RGB hardware interface detected.",
                     "Ensure you have a supported hp-wmi dkms module loaded.")

DEFAULT_RGB_PROFILES = {
    "rainbow": {
        "name": "Rainbow",
        "description": "Static rainbow across all 4 zones",
        "length_ms": 0,
        "change": "instant",
        "brightness": 100,
        "speed": 100,
        "loop": False,
        "zones": {
            "0": "#FF0000",
            "1": "#FF7F00",
            "2": "#00FF00",
            "3": "#0000FF"
        }
    },
    "white": {
        "name": "White",
        "description": "Static white, all zones",
        "length_ms": 0,
        "change": "instant",
        "brightness": 100,
        "speed": 100,
        "loop": False,
        "zones": {
            "0": "#FFFFFF",
            "1": "#FFFFFF",
            "2": "#FFFFFF",
            "3": "#FFFFFF"
        }
    },
    "gaming": {
        "name": "Gaming",
        "description": "Red sides, blue middle zones",
        "length_ms": 0,
        "change": "instant",
        "brightness": 100,
        "speed": 100,
        "loop": False,
        "zones": {
            "0": "#FF0000",
            "1": "#0000FF",
            "2": "#0000FF",
            "3": "#FF0000"
        }
    },
}


# Paths are resolved on use (not at import) so they follow the invoking user
# under sudo or pkexec.
def config_dir():
    return os.path.join(real_user_home(), ".config/openomen/rgb")


def profiles_dir():
    return os.path.join(config_dir(), "profiles")


def state_path():
    return os.path.join(config_dir(), "state.json")


def normalize_hex_color(value):
    """Return a 6-digit uppercase hex string for '#RRGGBB'/'RRGGBB', or None if invalid."""
    if not isinstance(value, str):
        return None
    value = value.strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return value.upper()
    return None


def ensure_rgb_config():
    for d in (config_dir(), profiles_dir()):
        if not os.path.exists(d):
            os.makedirs(d, exist_ok=True)
            chown_to_real_user(d)
    for profile_id, data in DEFAULT_RGB_PROFILES.items():
        profile_path = os.path.join(profiles_dir(), f"{profile_id}.json")
        if not os.path.exists(profile_path):
            try:
                with open(profile_path, 'w') as f:
                    json.dump(data, f, indent=4)
                chown_to_real_user(profile_path)
            except IOError as e:
                log.warning(f"Warning: Failed to create default profile: {e}")


def read_rgb_state():
    ensure_rgb_config()
    if os.path.exists(state_path()):
        try:
            with open(state_path(), 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            pass
    return {"enabled": False, "active_profile": "white"}


def write_rgb_state(state):
    ensure_rgb_config()
    try:
        with open(state_path(), 'w') as f:
            json.dump(state, f, indent=4)
        chown_to_real_user(state_path())
    except IOError as e:
        raise OpenOMENError(f"Error: Could not save state file: {e}")


def list_rgb_profiles():
    """ {profile_id: profile dict}, sorted by id. Invalid files are skipped (logged). """
    ensure_rgb_config()
    profiles = {}
    for path in sorted(glob.glob(os.path.join(profiles_dir(), "*.json"))):
        profile_id = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path, 'r') as f:
                profiles[profile_id] = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            log.warning(f"Warning: skipping invalid profile '{profile_id}': {e}")
    return profiles


def load_rgb_profile(profile_id):
    """ The profile dict, or None if missing or unreadable (logged). """
    ensure_rgb_config()
    path = os.path.join(profiles_dir(), f"{profile_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        log.error(f"Error: could not read profile '{profile_id}': {e}")
        return None


def detect_rgb_hardware():
    """ Human readable name of the RGB control interface, or None. """
    hw_type = detect_rgb_interface()
    return {
        "four_zone": "Four-Zone Control (rgb_zones)",
        "legacy": "Legacy/Standard Control (keyboardleds)",
        "kernel_patch": "Kernel Patch Control (zone_colors)",
    }.get(hw_type)


def detect_rgb_interface():
    """ 'four_zone', 'legacy', 'kernel_patch' or None. """
    if os.path.isdir(FOUR_ZONE_DIR):
        return "four_zone"
    if os.path.exists(LEGACY_PATH):
        return "legacy"
    if os.path.exists(KERNEL_PATCH_PATH):
        return "kernel_patch"
    return None


def require_rgb_hardware():
    if not detect_rgb_interface():
        raise OpenOMENError(*NO_HARDWARE_ERROR)


def resolve_rgb_profile_id(name):
    """
    Match a user-supplied profile name to an existing profile file id,
    case-insensitively. Only ids of real files in the profiles directory can
    match, so names like '../../foo' never reach the filesystem.
    """
    wanted = name.lower()
    for profile_id in list_rgb_profiles():
        if profile_id.lower() == wanted:
            return profile_id
    return None


def resolve_profile(name):
    """ (profile_id, profile) for a user-supplied name, or raise. """
    profile_id = resolve_rgb_profile_id(name)
    profile = load_rgb_profile(profile_id) if profile_id else None
    if profile is None:
        available = ', '.join(list_rgb_profiles().keys())
        lines = [f"Error: Unknown RGB profile '{name}'."]
        if available:
            lines.append(f"Available profiles: {available}")
        raise OpenOMENError(*lines)
    return profile_id, profile


def profile_colors(profile):
    """ The 4 zone colors ('RRGGBB') a profile shows; all black for None (lights off). """
    colors = ["000000"] * ZONE_COUNT
    if not profile:
        return colors
    if "zones" in profile:
        for i in range(ZONE_COUNT):
            key = str(i)
            if key in profile["zones"]:
                color = normalize_hex_color(profile["zones"][key])
                if color is None:
                    raise OpenOMENError(f"Error: invalid color '{profile['zones'][key]}' for zone {i} "
                                        "(expected #RRGGBB).")
                colors[i] = color
        return colors
    fallback_color = "000000"
    animation = profile.get("animation", {})
    if "full" in animation and "0" in animation["full"]:
        fallback_color = normalize_hex_color(animation["full"]["0"])
        if fallback_color is None:
            raise OpenOMENError(f"Error: invalid color '{animation['full']['0']}' (expected #RRGGBB).")
    return [fallback_color] * ZONE_COUNT


def apply_rgb_hardware(profile):
    """
    Write a profile's colors (None = lights off) to the detected RGB interface.
    Needs root. Returns a short description of what was written.
    """
    hw_type = detect_rgb_interface()
    if not hw_type:
        raise OpenOMENError(*NO_HARDWARE_ERROR)

    colors = profile_colors(profile)
    try:
        if hw_type == "four_zone":
            for i in range(ZONE_COUNT):
                zone_file = os.path.join(FOUR_ZONE_DIR, f"zone{i:02d}")
                if os.path.exists(zone_file):
                    with open(zone_file, "w") as f:
                        f.write(colors[i])
            return f"Applied zone colors: {', '.join(colors)}"

        if hw_type == "legacy":
            concatenated = "".join(colors)
            with open(LEGACY_PATH, "w") as f:
                f.write(concatenated)
            return f"Applied concatenated colors: {concatenated}"

        binary_data = bytearray()
        for col in colors:
            binary_data.extend([int(col[0:2], 16), int(col[2:4], 16), int(col[4:6], 16)])
        with open(KERNEL_PATCH_PATH, "wb") as f:
            f.write(binary_data)
        return f"Applied binary zone colors: {binary_data.hex()}"

    except PermissionError:
        raise OpenOMENError("Error: Permission denied writing to RGB control paths. Run with sudo.")
    except IOError as e:
        raise OpenOMENError(f"Error: Failed to write to RGB interface: {e}")


def get_rgb_status():
    """ {"enabled", "active_profile", "active_name", "profiles": {id: profile}, "hardware"} """
    state = read_rgb_state()
    profiles = list_rgb_profiles()
    active = state.get("active_profile")
    return {
        "enabled": state.get("enabled", False),
        "active_profile": active if active in profiles else None,
        "active_name": profiles[active].get('name', active) if active and active in profiles else None,
        "profiles": profiles,
        "hardware": detect_rgb_hardware(),
    }


def save_active_profile(profile_id):
    """ Record profile_id as active with the lights on (after the hardware write worked). """
    state = read_rgb_state()
    state["active_profile"] = profile_id
    state["enabled"] = True
    write_rgb_state(state)


def save_enabled(on):
    state = read_rgb_state()
    state["enabled"] = on
    write_rgb_state(state)


def active_profile_for_power_on():
    """ (profile_id, profile) of the saved active profile, or raise if there is none. """
    active = read_rgb_state().get("active_profile")
    active = resolve_rgb_profile_id(active) if active else None
    profile = load_rgb_profile(active) if active else None
    if profile is None:
        raise OpenOMENError("Error: no active profile set — run 'openomen rgb set <name>' first.")
    return active, profile


def set_profile(name):
    """ Select a profile and show it on the keyboard (turns the lights on). Needs root. """
    profile_id, profile = resolve_profile(name)
    require_rgb_hardware()
    apply_rgb_hardware(profile)
    save_active_profile(profile_id)
    return profile_id, profile


def set_power(on):
    """ Turn the keyboard lights on (with the active profile) or off. Needs root. """
    require_rgb_hardware()
    profile = active_profile_for_power_on()[1] if on else None
    apply_rgb_hardware(profile)
    save_enabled(on)
    return profile
