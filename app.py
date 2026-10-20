"""OS Performance Observatory: live OS monitor + labs + Prometheus exporter.
Privacy: only numbers are collected. No process names, paths or user data are ever read or shown."""
import collections
import re
import threading
import time

import psutil
from flask import Flask, jsonify, request
from prometheus_client import Gauge, start_http_server

import sim

INTERVAL = 5                      # seconds between samples
LEAK_WINDOW = 8                   # samples (~40 s) a process must keep growing
LEAK_GROWTH = 80 * 1024 * 1024    # and grow by at least 80 MB

ALERTS = {
    "cpu_saturation": ("warn", "High CPU load: processes are competing for the CPU (scheduling contention)."),
    "memory_pressure": ("warn", "Memory pressure: free memory is very low, paging is likely."),
    "thrashing": ("bad", "Possible thrashing: memory is nearly full and swap use is heavy."),
    "memory_leak": ("warn", "Possible memory leak: {n} process(es) show sustained memory growth."),
    "high_context_switches": ("warn", "High context-switch rate: the scheduler is switching very frequently."),
    "heavy_disk_io": ("warn", "Heavy disk activity: sustained high read/write throughput."),
    "low_disk_space": ("bad", "Low disk space: a volume is more than 90% full."),
    "deadlock_lab": ("bad", "Deadlock detected in the Dining Philosophers lab (circular wait)."),
}

g = lambda n, d: Gauge(n, d)
G = {
    "cpu": g("os_cpu_percent", "CPU utilisation %"),
    "mem": g("os_mem_percent", "Memory used %"),
    "swap": g("os_swap_percent", "Swap/page-file used %"),
    "rd": g("os_disk_read_bytes_per_s", "Disk read bytes/s"),
    "wr": g("os_disk_write_bytes_per_s", "Disk write bytes/s"),
    "ctx": g("os_ctx_switches_per_s", "Context switches per second"),
    "intr": g("os_interrupts_per_s", "Interrupts per second"),
    "sysc": g("os_syscalls_per_s", "System calls per second"),
    "procs": g("os_process_count", "Number of processes"),
    "threads": g("os_thread_count", "Number of threads"),
    "health": g("os_health_score", "OS health score 0-100"),
}
G_MODE = Gauge("os_cpu_mode_percent", "CPU time by mode", ["mode"])
G_ALERT = Gauge("os_alert_active", "1 when the alert is active", ["alert"])
G_SCHED = Gauge("sched_avg_waiting_seconds", "Average waiting time under each algorithm", ["algorithm"])
G_VOL = Gauge("os_disk_used_percent", "Volume usage %", ["volume"])

STATE = {"ready": False}
LAB = {"deadlock_at": 0.0}


def volumes():
    out = {}
    for p in psutil.disk_partitions(all=False):
        try:
            out[p.mountpoint] = psutil.disk_usage(p.mountpoint).percent
        except (OSError, PermissionError):
            pass
    return out


def sampler():
    psutil.cpu_percent(None)
    psutil.cpu_times_percent(None)
    prev_io, prev_cs, prev_t = psutil.disk_io_counters(), psutil.cpu_stats(), time.time()
    hist, hot_cpu, hot_io, delay = {}, 0, 0, 2
    while True:
        time.sleep(delay)
        delay = INTERVAL
        now = time.time()
        dt = max(now - prev_t, 0.001)
        cpu, vm, sw = psutil.cpu_percent(None), psutil.virtual_memory(), psutil.swap_memory()
        modes = psutil.cpu_times_percent(None)
        io, cs = psutil.disk_io_counters(), psutil.cpu_stats()
        rd = (io.read_bytes - prev_io.read_bytes) / dt if io and prev_io else 0
        wr = (io.write_bytes - prev_io.write_bytes) / dt if io and prev_io else 0
        ctx = (cs.ctx_switches - prev_cs.ctx_switches) / dt
        intr = (cs.interrupts - prev_cs.interrupts) / dt
        sysc = (getattr(cs, "syscalls", 0) - getattr(prev_cs, "syscalls", 0)) / dt
        prev_io, prev_cs, prev_t = io, cs, now

        # per-process numbers only (no names)
        bursts, nthreads, nprocs, suspects, seen = [], 0, 0, 0, set()
        for p in psutil.process_iter(["pid", "create_time", "cpu_times", "memory_info", "num_threads"]):
            i = p.info
            nprocs += 1
            nthreads += i["num_threads"] or 0
            if i["cpu_times"]:
                bursts.append((i["create_time"] or 0, i["cpu_times"].user + i["cpu_times"].system))
            if i["memory_info"]:
                key = (i["pid"], i["create_time"])
                seen.add(key)
                d = hist.setdefault(key, collections.deque(maxlen=LEAK_WINDOW))
                d.append(i["memory_info"].rss)
                if len(d) == LEAK_WINDOW and d[-1] - d[0] >= LEAK_GROWTH and \
                        all(d[k] <= d[k + 1] for k in range(LEAK_WINDOW - 1)):
                    suspects += 1
        for k in [k for k in hist if k not in seen]:
            del hist[k]
        bursts.sort()
        sched = sim.sched_waits([b for _, b in bursts][-12:])

        vols = volumes()
        hot_cpu = hot_cpu + 1 if cpu >= 90 else 0
        hot_io = hot_io + 1 if (rd + wr) > 100 * 1024 * 1024 else 0
        active = {
            "cpu_saturation": hot_cpu >= 2,
            "memory_pressure": vm.percent >= 90,
            "thrashing": vm.percent >= 90 and sw.percent >= 60,
            "memory_leak": suspects > 0,
            "high_context_switches": ctx > 150000,
            "heavy_disk_io": hot_io >= 2,
            "low_disk_space": any(v >= 90 for v in vols.values()),
            "deadlock_lab": now - LAB["deadlock_at"] < 120,
        }
        score = 100 - max(0, cpu - 80) * 0.3 - max(0, vm.percent - 80) * 0.5
        for a, on in active.items():
            if on and a != "deadlock_lab":
                score -= 20 if ALERTS[a][0] == "bad" else 10
        score = max(0, min(100, score))

        msgs = [{"id": a, "level": ALERTS[a][0], "message": ALERTS[a][1].format(n=suspects)}
                for a, on in active.items() if on]
        msgs.sort(key=lambda m: m["level"] != "bad")

        mode_vals = {"user": modes.user, "kernel": modes.system, "interrupt": getattr(modes, "interrupt", 0),
                     "dpc": getattr(modes, "dpc", 0), "idle": modes.idle}
        G["cpu"].set(cpu); G["mem"].set(vm.percent); G["swap"].set(sw.percent)
        G["rd"].set(rd); G["wr"].set(wr); G["ctx"].set(ctx); G["intr"].set(intr); G["sysc"].set(sysc)
        G["procs"].set(nprocs); G["threads"].set(nthreads); G["health"].set(score)
        for k, v in mode_vals.items():
            G_MODE.labels(k).set(v)
        for a, on in active.items():
            G_ALERT.labels(a).set(1 if on else 0)
        for k, v in sched.items():
            G_SCHED.labels(k).set(v)
        for k, v in vols.items():
            G_VOL.labels(k).set(v)

        STATE.update(ready=True, health=score, cpu=cpu, mem=vm.percent, swap=sw.percent, rd=rd, wr=wr,
                     ctx=ctx, intr=intr, sysc=sysc, procs=nprocs, threads=nthreads, modes=mode_vals,
                     volumes=vols, sched=sched, alerts=msgs, ts=now)


app = Flask(__name__, static_folder="static", static_url_path="/static")


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/status")
def status():
    return jsonify(STATE)


def nums(s):
    return [int(x) for x in re.findall(r"-?\d+", str(s))]


def matrix(s):
    return [nums(line) for line in str(s).strip().splitlines() if line.strip()]


@app.post("/api/lab/<kind>")
def lab(kind):
    d = request.get_json(force=True, silent=True) or {}
    try:
        if kind == "pages":
            r = sim.page_all(nums(d["refs"])[:200], int(d["frames"]))
        elif kind == "disk":
            r = sim.disk_all(nums(d["requests"])[:60], int(d["head"]), int(d.get("size", 200)))
        elif kind == "banker":
            r = sim.banker(nums(d["available"]), matrix(d["max"]), matrix(d["alloc"]))
        elif kind == "dining":
            r = sim.dining(int(d["n"]), d["strategy"])
            if r["deadlock"]:
                LAB["deadlock_at"] = time.time()
        elif kind == "race":
            r = sim.race(int(d["threads"]), int(d["iters"]))
        else:
            return jsonify(error="Unknown lab"), 404
        return jsonify(r)
    except (KeyError, ValueError, TypeError) as e:
        return jsonify(error=str(e)), 400


if __name__ == "__main__":
    start_http_server(8000)
    threading.Thread(target=sampler, daemon=True).start()
    print("Live UI:      http://localhost:5050\nMetrics:      http://localhost:8000/metrics")
    app.run(host="127.0.0.1", port=5050, threaded=True)
