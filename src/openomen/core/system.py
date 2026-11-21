""" System information for debugging and bug reports (`openomen info`). """

import glob
import os
import subprocess

from .. import VERSION
from . import fans, power
from .gpu import VENDOR_AMD, VENDOR_INTEL, get_amd_driver_info


def _read_kernel():
    try:
        with open("/proc/version", "r") as f:
            return f.read().strip()
    except IOError:
        return None


def _read_cpu():
    """ (model, model_error, cores). model_error is 'missing' or 'unreadable' when model is None. """
    model, model_error = None, None
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                    break
            else:
                model_error = "missing"
    except IOError:
        model_error = "unreadable"
    try:
        with open("/proc/cpuinfo", "r") as f:
            cores = sum(1 for line in f if line.startswith("processor"))
    except IOError:
        cores = None
    return model, model_error, cores


def _list_gpus():
    gpus = []
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            for line in result.stdout.strip().split("\n"):
                nvidia_info = line.split(",")
                if len(nvidia_info) >= 2:
                    gpus.append({"vendor": "NVIDIA", "name": nvidia_info[0].strip(),
                                 "driver": nvidia_info[1].strip()})
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    try:
        for card_dir in glob.glob("/sys/class/drm/card*/device"):
            vendor_file = os.path.join(card_dir, "vendor")
            if os.path.exists(vendor_file):
                with open(vendor_file, 'r') as f:
                    vendor = f.read().strip().lower()
                if vendor == VENDOR_AMD:
                    gpus.append({"vendor": "AMD", "name": None, "driver": get_amd_driver_info(card_dir)})
                elif vendor == VENDOR_INTEL:
                    gpus.append({"vendor": "Intel", "name": None, "driver": None})
    except IOError:
        pass
    return gpus


def _list_hwmon():
    hwmon_dirs = glob.glob("/sys/class/hwmon/hwmon*")
    devices = []
    for hwmon_dir in sorted(hwmon_dirs):
        name_path = os.path.join(hwmon_dir, "name")
        if os.path.exists(name_path):
            try:
                with open(name_path, 'r') as f:
                    devices.append({"id": os.path.basename(hwmon_dir), "name": f.read().strip()})
            except IOError:
                continue
    return bool(hwmon_dirs), devices


def _hp_wmi_status():
    hp_wmi_path = "/sys/devices/platform/hp-wmi/hwmon"
    if not os.path.exists(hp_wmi_path):
        return {"status": "missing", "devices": 0}
    count = len(glob.glob(f"{hp_wmi_path}/hwmon*"))
    return {"status": "found" if count else "no_hwmon", "devices": count}


def _read_sysfs_value(path, split=False):
    """ (value, status) with status 'ok', 'unreadable' or 'unsupported'. """
    if not os.path.exists(path):
        return None, "unsupported"
    try:
        with open(path, 'r') as f:
            text = f.read().strip()
        return (text.split() if split else text), "ok"
    except IOError:
        return None, "unreadable"


def _fan_info():
    hwmon_path = fans.find_hwmon_path()
    info = {"hwmon_path": hwmon_path, "pwm1_enable": None, "pwm1_status": None, "rpm": {}}
    if not hwmon_path:
        return info
    pwm_enable_path = os.path.join(hwmon_path, "pwm1_enable")
    if os.path.exists(pwm_enable_path):
        try:
            with open(pwm_enable_path, 'r') as f:
                info["pwm1_enable"] = f.read().strip()
            info["pwm1_status"] = "ok"
        except IOError:
            info["pwm1_status"] = "unreadable"
    else:
        info["pwm1_status"] = "missing"
    info["rpm"] = fans.read_fan_rpm()
    return info


def get_system_info():
    """ Everything `openomen info` shows, as a dict. """
    cpu_model, cpu_model_error, cpu_cores = _read_cpu()
    hwmon_present, hwmon_devices = _list_hwmon()
    choices, choices_status = _read_sysfs_value(power.PROFILE_CHOICES_PATH, split=True)
    current, current_status = _read_sysfs_value(power.PROFILE_PATH)
    return {
        "version": VERSION,
        "kernel": _read_kernel(),
        "cpu": {"model": cpu_model, "model_error": cpu_model_error, "cores": cpu_cores},
        "gpus": _list_gpus(),
        "hwmon": {"present": hwmon_present, "devices": hwmon_devices},
        "hp_wmi": _hp_wmi_status(),
        "acpi": {"choices": choices, "choices_status": choices_status,
                 "current": current, "current_status": current_status},
        "fan": _fan_info(),
    }
