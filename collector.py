"""Real OS metric collection helpers for OS Observatory."""
from __future__ import annotations
import os, platform, time
from typing import Any
import psutil


def detect_environment() -> str:
    """Return whether this process appears to run inside a container."""
    if os.path.exists('/.dockerenv'):
        return 'docker-container'
    try:
        with open('/proc/1/cgroup', encoding='utf-8') as f:
            content = f.read().lower()
        if any(token in content for token in ('docker', 'containerd', 'kubepods', 'podman')):
            return 'docker-container'
    except OSError:
        pass
    return 'native-host'


def safe_rate(current: int | float | None, previous: int | float | None, elapsed: float) -> float:
    """Calculate a nonnegative counter rate; counter resets/wraps yield zero."""
    if current is None or previous is None or elapsed <= 0 or current < previous:
        return 0.0
    return (current - previous) / elapsed


def collect_volumes() -> dict[str, dict[str, float]]:
    result = {}
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            result[part.mountpoint] = {'percent': usage.percent, 'used_bytes': usage.used, 'total_bytes': usage.total}
        except (OSError, PermissionError):
            continue
    return result


def process_snapshot(show_names: bool) -> tuple[int, int, list[dict[str, Any]], list[dict[str, Any]], dict[tuple[int, float], int]]:
    """Return counts, top processes and RSS observations, tolerating process races."""
    count = threads = 0
    rows: list[dict[str, Any]] = []
    rss: dict[tuple[int, float], int] = {}
    for proc in psutil.process_iter(['pid', 'name', 'create_time', 'cpu_percent', 'memory_info', 'num_threads']):
        try:
            info = proc.info
            count += 1
            threads += int(info.get('num_threads') or 0)
            mem = info.get('memory_info')
            created = float(info.get('create_time') or 0)
            if mem and created:
                rss[(int(info['pid']), created)] = int(mem.rss)
            row = {'pid': int(info['pid']), 'name': (info.get('name') or 'unknown') if show_names else None,
                   'cpu_percent': float(info.get('cpu_percent') or 0), 'rss_bytes': int(mem.rss) if mem else 0}
            rows.append(row)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError, TypeError, ValueError):
            continue
    return count, threads, sorted(rows, key=lambda x: x['cpu_percent'], reverse=True)[:5], sorted(rows, key=lambda x: x['rss_bytes'], reverse=True)[:5], rss


def collect_base() -> dict[str, Any]:
    """Collect instantaneous OS values; rates are computed by the sampler."""
    vm, sw = psutil.virtual_memory(), psutil.swap_memory()
    cpu_times = psutil.cpu_times_percent(interval=None)
    modes = {name: float(getattr(cpu_times, name)) for name in cpu_times._fields if hasattr(cpu_times, name)}
    per_core = psutil.cpu_percent(interval=None, percpu=True)
    io = psutil.disk_io_counters()
    stats = psutil.cpu_stats()
    net = psutil.net_io_counters()
    try: load = list(os.getloadavg())
    except (AttributeError, OSError): load = None
    boot = psutil.boot_time()
    return {'cpu': psutil.cpu_percent(interval=None), 'per_core': per_core, 'modes': modes,
        'mem': vm.percent, 'mem_used_gb': vm.used / 1e9, 'mem_total_gb': vm.total / 1e9,
        'swap': sw.percent, 'swap_used_gb': sw.used / 1e9, 'swap_total_gb': sw.total / 1e9,
        'io_read': io.read_bytes if io else None, 'io_write': io.write_bytes if io else None,
        'ctx_total': stats.ctx_switches, 'intr_total': getattr(stats, 'interrupts', None),
        'net_sent': net.bytes_sent if net else None, 'net_recv': net.bytes_recv if net else None,
        'load_average': load, 'uptime_seconds': max(0, time.time()-boot), 'volumes': collect_volumes()}
