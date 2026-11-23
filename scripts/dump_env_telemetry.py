import json
import os
import platform
import subprocess

def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception as exc:
        return f"ERR: {exc}"

def collect_telemetry():
    return {
        "kernel": run_cmd("uname -a"),
        "arch": run_cmd("uname -m"),
        "model": run_cmd("getprop ro.product.model"),
        "brand": run_cmd("getprop ro.product.brand"),
        "manufacturer": run_cmd("getprop ro.product.manufacturer"),
        "release": run_cmd("getprop ro.build.version.release"),
        "sdk": run_cmd("getprop ro.build.version.sdk"),
        "soc": run_cmd("getprop ro.soc.model"),
        "hardware": run_cmd("getprop ro.hardware"),
        "verified_boot": run_cmd("getprop ro.boot.verifiedbootstate"),
        "fingerprint": run_cmd("getprop ro.build.fingerprint"),
        "cpu_cores": os.cpu_count(),
        "loadavg": run_cmd("cat /proc/loadavg"),
        "memory": run_cmd("free -m"),
        "disk_home": run_cmd("df -h $HOME"),
        "disk_data": run_cmd("df -h /data"),
        "thermal_zone0": run_cmd("cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null"),
        "thermal_zone1": run_cmd("cat /sys/class/thermal/thermal_zone1/temp 2>/dev/null"),
        "termux_prefix": os.environ.get("PREFIX", ""),
        "python_ver": platform.python_version(),
        "services": run_cmd("sv status /data/data/com.termux/files/usr/var/service/* 2>/dev/null"),
        "tailscale": run_cmd("tailscale --socket=$HOME/.tailscale/tailscaled.sock status 2>/dev/null"),
        "listening_ports": run_cmd("netstat -tlpn 2>/dev/null || ss -tlpn 2>/dev/null"),
        "sshd_version": run_cmd("ssh -V 2>&1")
    }

if __name__ == "__main__":
    data = collect_telemetry()
    print(json.dumps(data, indent=2))
