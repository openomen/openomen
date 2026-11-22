""" GPU stats for NVIDIA (nvidia-smi), AMD and Intel (sysfs/drm). """

import glob
import os
import subprocess

from . import log

VENDOR_AMD = "0x1002"
VENDOR_INTEL = "0x8086"


def get_amd_driver_info(card_device_dir):
    """ Detect the active AMD GPU driver (amdgpu, radeon, fglrx/catalyst) """
    driver_link = os.path.join(card_device_dir, "driver")
    if os.path.exists(driver_link):
        try:
            driver_name = os.path.basename(os.readlink(driver_link))
            if driver_name in ["amdgpu", "radeon", "fglrx"]:
                return driver_name
        except OSError:
            pass
    # Fallback module scan
    try:
        with open("/proc/modules", "r") as f:
            modules = f.read()
            for drv in ["amdgpu", "radeon", "fglrx"]:
                if drv in modules:
                    return drv
    except IOError:
        pass
    return "AMD Kernel Driver"


def _number(text):
    """ int/float from a sysfs or nvidia-smi field, None for '[N/A]' and friends. """
    try:
        return int(text)
    except (TypeError, ValueError):
        try:
            return float(text)
        except (TypeError, ValueError):
            return None


def _read_first_hwmon_temp(card_dir):
    hwmon_temps = glob.glob(os.path.join(card_dir, "hwmon/hwmon*/temp1_input"))
    if hwmon_temps:
        try:
            with open(hwmon_temps[0], 'r') as tf:
                return int(tf.read().strip()) / 1000.0
        except IOError:
            pass
    return None


def _new_gpu(index, vendor, name):
    return {
        "index": index,
        "vendor": vendor,
        "name": name,
        "driver": None,
        "temperature_c": None,
        "utilization_pct": None,
        "vram_used_mib": None,
        "vram_total_mib": None,
        "power_w": None,
        "frequency_mhz": None,
        # exact text as read, used by the CLI to print values unchanged
        "_raw": {},
    }


def _query_nvidia(start_index):
    gpus = []
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw,clocks.gr",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True, text=True, timeout=5
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return gpus
    if result.returncode != 0 or not result.stdout.strip():
        return gpus
    for line in result.stdout.strip().split("\n"):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        gpu_name, temp, util, vram_used, vram_total = parts[:5]
        power = parts[5] if len(parts) > 5 else "N/A"
        clock = parts[6] if len(parts) > 6 else "N/A"
        gpu = _new_gpu(start_index + len(gpus) + 1, "NVIDIA", gpu_name)
        gpu.update({
            "temperature_c": _number(temp),
            "utilization_pct": _number(util),
            "vram_used_mib": _number(vram_used),
            "vram_total_mib": _number(vram_total),
            "power_w": _number(power),
            "frequency_mhz": _number(clock),
        })
        gpu["_raw"] = {"temperature": temp, "utilization": util, "vram_used": vram_used,
                       "vram_total": vram_total, "power": power, "frequency": clock}
        gpus.append(gpu)
    return gpus


def query_gpus():
    """
    List of GPUs (dicts, see _new_gpu) across multi-GPU setups. Empty when none found.
    Keys starting with '_' are display helpers, not data.
    """
    gpus = _query_nvidia(0)

    # AMD & Intel through DRM sysfs
    try:
        for card_dir in sorted(glob.glob("/sys/class/drm/card[0-9]*/device")):
            vendor_file = os.path.join(card_dir, "vendor")
            if not os.path.exists(vendor_file):
                continue
            with open(vendor_file, 'r') as f:
                vendor = f.read().strip().lower()

            if vendor == VENDOR_AMD:
                driver_name = get_amd_driver_info(card_dir)
                gpu = _new_gpu(len(gpus) + 1, "AMD", f"{driver_name.upper()} Architecture")
                gpu["driver"] = driver_name
                gpu["temperature_c"] = _read_first_hwmon_temp(card_dir)
                busy_file = os.path.join(card_dir, "gpu_busy_percent")
                if os.path.exists(busy_file):
                    try:
                        with open(busy_file, 'r') as bf:
                            util = bf.read().strip()
                        gpu["utilization_pct"] = _number(util)
                        gpu["_raw"]["utilization"] = util
                    except IOError:
                        pass
                gpus.append(gpu)

            elif vendor == VENDOR_INTEL:
                gpu = _new_gpu(len(gpus) + 1, "Intel", "Intel Arc / iGPU")
                gpu["temperature_c"] = _read_first_hwmon_temp(card_dir)
                # card_dir is /sys/class/drm/cardN/device, so the i915 freq file
                # lives next to it in cardN/, not under a hardcoded card0.
                freq_file = os.path.join(os.path.dirname(card_dir), "gt_cur_freq_mhz")
                if not os.path.exists(freq_file):
                    found = glob.glob(os.path.join(card_dir, "gt*/freq0/act_freq"))
                    freq_file = found[0] if found else None
                if freq_file and os.path.exists(freq_file):
                    try:
                        with open(freq_file, 'r') as ff:
                            freq = ff.read().strip()
                        gpu["frequency_mhz"] = _number(freq)
                        gpu["_raw"]["frequency"] = freq
                    except IOError:
                        pass
                gpus.append(gpu)
    except IOError as e:
        log.error(f"Error reading sysfs GPU stats: {e}")

    return gpus


def public(gpu):
    """ A GPU dict without the display helpers, for JSON output. """
    return {k: v for k, v in gpu.items() if not k.startswith("_")}
