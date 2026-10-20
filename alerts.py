"""Threshold-based alerts and elapsed-time memory-growth detection."""
from __future__ import annotations
from collections import defaultdict, deque
from typing import Any

DEFAULT_THRESHOLDS = {'cpu_percent': 90.0, 'cpu_duration_seconds': 10.0, 'memory_percent': 90.0,
 'swap_percent': 60.0, 'context_switches_per_s': 150000.0, 'disk_bytes_per_s': 20*1024*1024,
 'disk_duration_seconds': 10.0, 'disk_used_percent': 90.0, 'leak_window_seconds': 40.0,
 'leak_growth_mb': 80.0, 'leak_sample_min_seconds': 5.0}

class LeakDetector:
    """Detect monotonic RSS growth over a time window, independent of sample count."""
    def __init__(self, window_seconds: float = 40, growth_mb: float = 80):
        self.window = max(1.0, window_seconds); self.growth = growth_mb * 1024 * 1024
        self.samples: dict[tuple[int,float], deque[tuple[float,int]]] = defaultdict(deque)
    def update(self, now: float, rss_by_process: dict[tuple[int,float], int]) -> list[dict[str, Any]]:
        found=[]
        for key, rss in rss_by_process.items():
            q=self.samples[key]; q.append((now, rss))
            while len(q)>2 and now-q[0][0] > self.window: q.popleft()
            if len(q)>=2 and q[-1][0]-q[0][0] >= self.window*0.75 and q[-1][1]-q[0][1] >= self.growth and all(q[i][1] <= q[i+1][1] for i in range(len(q)-1)):
                found.append({'pid': key[0], 'growth_mb': round((q[-1][1]-q[0][1])/1048576, 1)})
        for key in list(self.samples):
            if key not in rss_by_process:
                del self.samples[key]
        return found

def evaluate_alerts(sample: dict[str, Any], thresholds: dict[str, float], cpu_hot_seconds: float,
                    disk_hot_seconds: float, leaks: list[dict[str, Any]], now: float) -> list[dict[str, Any]]:
    """Return active alerts with measured values and configured thresholds."""
    checks = [
      ('cpu_saturation', sample['cpu'] >= thresholds['cpu_percent'] and cpu_hot_seconds >= thresholds['cpu_duration_seconds'], 'warn', f"CPU {sample['cpu']:.1f}% >= {thresholds['cpu_percent']:.0f}% for {cpu_hot_seconds:.0f}s"),
      ('memory_pressure', sample['mem'] >= thresholds['memory_percent'], 'warn', f"Memory {sample['mem']:.1f}% >= {thresholds['memory_percent']:.0f}%"),
      ('thrashing', sample['mem'] >= thresholds['memory_percent'] and sample['swap'] >= thresholds['swap_percent'], 'bad', f"Memory {sample['mem']:.1f}%; swap {sample['swap']:.1f}% >= {thresholds['swap_percent']:.0f}%"),
      ('memory_leak', bool(leaks), 'warn', 'Sustained process RSS growth: '+', '.join(f"PID {x['pid']} +{x['growth_mb']:.1f} MB" for x in leaks)),
      ('high_context_switches', sample['ctx'] >= thresholds['context_switches_per_s'], 'warn', f"Context switches {sample['ctx']:.0f}/s >= {thresholds['context_switches_per_s']:.0f}/s"),
      ('heavy_disk_io', sample['rd']+sample['wr'] >= thresholds['disk_bytes_per_s'] and disk_hot_seconds >= thresholds['disk_duration_seconds'], 'warn', f"Disk R/W {(sample['rd']+sample['wr'])/1048576:.1f} MB/s >= {thresholds['disk_bytes_per_s']/1048576:.1f} MB/s for {disk_hot_seconds:.0f}s"),
      ('low_disk_space', any(v['percent'] >= thresholds['disk_used_percent'] for v in sample['volumes'].values()), 'bad', 'Volume usage: '+', '.join(f"{name} {v['percent']:.1f}% >= {thresholds['disk_used_percent']:.0f}%" for name,v in sample['volumes'].items() if v['percent'] >= thresholds['disk_used_percent'])),
    ]
    out=[]
    for ident, active, level, detail in checks:
        if active: out.append({'id':ident,'level':level,'message':detail,'measured':detail,'threshold':thresholds,'started_at':now})
    out.sort(key=lambda a: a['level'] != 'bad')
    return out
