""" CPU name, temperature, per-core usage and frequency. """

import glob
import os
import re

from . import log

HWMON_BASE = "/sys/class/hwmon"

# Driver names associated with CPU temperatures, in priority order
CPU_DRIVER_PRIORITY = [
    "coretemp",    # Intel per-core temps
    "k10temp",     # AMD CPU temps
    "zenpower",    # AMD Zen alternative driver
    "hp-wmi",      # HP-specific WMI sensors (BIOS/board)
    "acpitz",      # ACPI thermal zones (fallback)
]

# Label substrings that strongly indicate CPU/package temps
CPU_LABEL_KEYWORDS = ["package", "tctl", "tdie", "core", "cpu", "physical"]

# Sensors to explicitly skip
SKIP_LABEL_KEYWORDS = ["spd", "dram", "dimm", "ram", "mem", "nvme", "hdd", "ssd", "fan"]


def get_friendly_label(label):
    """ Convert technical hwmon labels to userfriendly names, better for everyone """
    # Keys are lowercase: scan_hwmon_temps lowercases labels before they get here.
    label_mapping = {
        'edge': 'GPU Edge',  # amdgpu edge sensor; this is a GPU temperature, not the CPU
        'tccd1': 'CPU CCD1',
        'tccd2': 'CPU CCD2',
        'tctl': 'CPU Control',
        'tdie': 'CPU Die',
        'package id 0': 'CPU Package',
        'composite': 'CPU Composite',
        'temp1': 'System',
        'temp2': 'CPU',
        'temp3': 'GPU',
    }
    return label_mapping.get(label.lower(), label)


def get_hwmon_driver(hwmon_dir):
    name_path = os.path.join(hwmon_dir, "name")
    if os.path.exists(name_path):
        try:
            with open(name_path, 'r') as f:
                return f.read().strip().lower()
        except IOError:
            pass
    return ""


def read_hwmon_temps(hwmon_dir):
    """ List of (lowercase label, temp_celsius) from a hwmon dir. """
    results = []
    for temp_file in sorted(glob.glob(os.path.join(hwmon_dir, "temp*_input"))):
        try:
            with open(temp_file, 'r') as f:
                temp_celsius = int(f.read().strip()) / 1000.0
            label_path = temp_file.replace("_input", "_label")
            raw_label = ""
            if os.path.exists(label_path):
                try:
                    with open(label_path, 'r') as lf:
                        raw_label = lf.read().strip().lower()
                except IOError:
                    pass
            results.append((raw_label, temp_celsius))
        except IOError:
            continue
    return results


def scan_hwmon_temps(hwmon_dirs=None):
    """ Map driver name -> [(hwmon_dir, [(label, temp), ...]), ...] for every hwmon with temps. """
    if hwmon_dirs is None:
        hwmon_dirs = glob.glob(f"{HWMON_BASE}/hwmon*")
    hwmon_by_driver = {}
    for hwmon_dir in hwmon_dirs:
        driver = get_hwmon_driver(hwmon_dir)
        temps = read_hwmon_temps(hwmon_dir)
        if temps:
            hwmon_by_driver.setdefault(driver, []).append((hwmon_dir, temps))
    return hwmon_by_driver


def _temp_result(driver, raw_label, temp_celsius):
    return {
        "label": get_friendly_label(raw_label) if raw_label else driver,
        "sensor": raw_label,
        "driver": driver,
        "celsius": temp_celsius,
    }


def find_cpu_temperature():
    """
    Best CPU temperature sensor, prioritising CPU drivers and package/core
    labels over RAM, NVMe and other sensors. Returns
        {"label": friendly name, "sensor": raw label, "driver": str, "celsius": float}
    or None (logged) when nothing suitable exists.
    """
    hwmon_dirs = glob.glob(f"{HWMON_BASE}/hwmon*")
    if not hwmon_dirs:
        log.error("Error: No hwmon devices found.")
        return None

    hwmon_by_driver = scan_hwmon_temps(hwmon_dirs)

    # Go through drivers in priority order, then fall back to everything else
    ordered_drivers = CPU_DRIVER_PRIORITY + [
        d for d in hwmon_by_driver if d not in CPU_DRIVER_PRIORITY
    ]
    for driver in ordered_drivers:
        for _hwmon_dir, temps in hwmon_by_driver.get(driver, []):
            for raw_label, temp_celsius in temps:
                if any(kw in raw_label for kw in SKIP_LABEL_KEYWORDS):
                    continue
                # Within a CPU driver, prefer package/core labels
                if driver in CPU_DRIVER_PRIORITY[:3]:  # coretemp / k10temp / zenpower
                    if not any(kw in raw_label for kw in CPU_LABEL_KEYWORDS):
                        continue  # skip non-package entries on first pass
                return _temp_result(driver, raw_label, temp_celsius)

    # Second pass: relax the label filter for CPU drivers (e.g. unlabelled coretemp entries)
    for driver in CPU_DRIVER_PRIORITY:
        for _hwmon_dir, temps in hwmon_by_driver.get(driver, []):
            for raw_label, temp_celsius in temps:
                if any(kw in raw_label for kw in SKIP_LABEL_KEYWORDS):
                    continue
                return _temp_result(driver, raw_label, temp_celsius)

    log.error("Error: No CPU temperature sensor found in any hwmon device.")
    return None


def read_cpu_name():
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except IOError:
        pass
    return "Unknown CPU"


def read_core_freq_mhz(cpu):
    """ Current frequency of a core in MHz, or None. """
    try:
        with open(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq", "r") as f:
            return int(f.read().strip()) / 1000
    except (IOError, ValueError):
        return None


def _read_proc_stat():
    """ Map CPU number -> counters, from the 'cpuN ...' lines of /proc/stat. Raises OSError. """
    out = {}
    with open("/proc/stat", "r") as f:
        for line in f:
            m = re.match(r"cpu(\d+)\s", line)
            if m:
                out[int(m.group(1))] = list(map(int, line.split()[1:]))
    return out


class CpuSampler:
    """
    Per-core CPU usage between two /proc/stat samples.

    Keep one instance around and call sample() periodically (a GUI timer);
    each call returns usage since the previous call. The first call only
    primes the sampler and returns None.
    """

    def __init__(self):
        self._prev = None

    def sample(self):
        current = _read_proc_stat()
        previous, self._prev = self._prev, current
        if previous is None:
            return None
        cores = []
        # Iterate by real CPU number: offline CPUs are absent from /proc/stat, and
        # the cpufreq path is built from the same number so it always matches.
        for cpu in sorted(previous.keys() & current.keys()):
            vals1, vals2 = previous[cpu], current[cpu]
            # idle + iowait count as idle; guest time is already in user/nice.
            idle1 = vals1[3] + (vals1[4] if len(vals1) > 4 else 0)
            idle2 = vals2[3] + (vals2[4] if len(vals2) > 4 else 0)
            total_delta = sum(vals2[:8]) - sum(vals1[:8])
            idle_delta = idle2 - idle1
            usage = 0.0 if total_delta <= 0 else max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100))
            cores.append({"cpu": cpu, "usage": usage, "freq_mhz": read_core_freq_mhz(cpu)})
        return cores


def get_cpu_stats(sampler):
    """
    {"name": str, "temperature": find_cpu_temperature(), "cores": [...] or None}
    `sampler` is a CpuSampler that has been primed at least once before.
    """
    return {
        "name": read_cpu_name(),
        "temperature": find_cpu_temperature(),
        "cores": sampler.sample(),
    }
