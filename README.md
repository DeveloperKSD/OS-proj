# OS Performance Observatory

A monitoring platform that links live operating-system behaviour to each unit of the Operating Systems syllabus, plus interactive labs for the classic algorithms.

- **Live status page** with plain-language messages such as "Possible memory leak", "High CPU load", "Deadlock detected". No process names are ever collected or shown, only numbers.
- **Grafana dashboard** with one panel per syllabus unit (auto-loaded).
- **Algorithm labs:** page replacement, disk scheduling, Banker's algorithm, dining philosophers (deadlock detection), race condition.
- **Prometheus exporter** that publishes everything as metrics.

## 1. What you need (one-time setup)

| Requirement | How to check | Where to get it |
|---|---|---|
| Python 3.10 or newer | `python --version` | python.org (tick "Add Python to PATH" while installing) |
| Docker Desktop (WSL2 backend) | `docker --version` | docker.com, restart the PC after installing |

Make sure Docker Desktop is **open and running** (whale icon in the system tray) before step 3.

## 2. Unzip

Unzip `os-observatory.zip` somewhere simple, for example `C:\os-observatory`. You should see `app.py`, `docker-compose.yml`, `start.bat` and more in the same folder.

## 3. Start everything (easy way)

1. Double-click **`start.bat`**.
2. It creates a Python virtual environment, installs the packages, opens a second window running the app (**keep it open**), and starts Prometheus and Grafana with Docker.
3. The first run downloads the Docker images (a few minutes). If Windows Firewall asks about Python, click **Allow**.

Then open:

| What | Address | Notes |
|---|---|---|
| Live status and labs | http://localhost:5050 | Messages appear within about 5 seconds |
| Grafana dashboard | http://localhost:3000 | Opens the dashboard directly. To edit, log in with `admin` / `admin` |
| Prometheus | http://localhost:9090 | Check `Status > Targets`: `os-observatory` should be UP |
| Raw metrics | http://localhost:8000/metrics | What Prometheus scrapes |

### Manual way (if `start.bat` fails)

```powershell
cd C:\os-observatory
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py            # leave this running
```
Open a second PowerShell in the same folder:
```powershell
docker compose up -d
```
Mac or Linux: the same steps work, using `source .venv/bin/activate`.

## 4. Check that it works (2 minutes)

1. http://localhost:5050 shows a health score and "All clear" (or a real warning such as low disk space).
2. http://localhost:9090/targets shows `os-observatory` as **UP**. The `windows` target may be DOWN, which is fine (see section 7).
3. http://localhost:3000 shows the dashboard with graphs moving every 5 seconds.

## 5. Demo script (what to show faculty)

Open the Live status page and Grafana side by side.

| Step | Do this | You should see | Syllabus link |
|---|---|---|---|
| 1 | Open Live status | Health score, CPU split between user and kernel mode, system calls/sec | Unit 1 |
| 2 | In a terminal: `python experiments\cpu_burn.py 60` | After about 10 s: "High CPU load: processes are competing for the CPU". Context switches/sec rise, health score falls | Unit 2 |
| 3 | Look at "Scheduling comparison" | FCFS vs SJF vs Round Robin waiting times, lowest highlighted (SJF is always lowest) | Unit 2 |
| 4 | Algorithm labs > Race condition > Run | Updates are lost without a lock, correct but slower with a lock | Unit 3 |
| 5 | Algorithm labs > Dining philosophers > naive > Run | "Deadlock detected: circular wait P0 -> P1 -> ...". The same message appears on the Live tab for 2 minutes | Unit 4 |
| 6 | Same lab, switch to the fixed strategy > Run | "No deadlock": ordered fork pickup removes circular wait | Unit 4 |
| 7 | Algorithm labs > Banker's > Check safety, then set Available to `0 0 0` | Safe sequence, then "Unsafe state" | Unit 4 |
| 8 | In a terminal: `python experiments\memory_leak.py 600` | After about 45 s: "Possible memory leak: 1 process(es) show sustained memory growth" | Unit 5 |
| 9 | Algorithm labs > Page replacement > "Show Belady's anomaly" | FIFO gets worse with more frames (9 faults at 3 frames, 10 at 4) | Unit 5 |
| 10 | Algorithm labs > Disk scheduling > Compare | SSTF 236, LOOK 299, SCAN 331, C-SCAN 382, FCFS 640 head movement | Unit 6 |
| 11 | In a terminal: `python experiments\disk_stress.py 40` | "Heavy disk activity" and the Grafana disk throughput panel climbs (needs a fast disk, may not trigger on slow ones) | Unit 6 |
| 12 | Look at "disk volumes" and Grafana "Volume usage" | Usage per drive | Unit 7 |

Experiment scripts end by themselves, or press Ctrl+C. `memory_leak.py` releases its memory when it stops.

## 6. How the messages are decided

| Message | Rule |
|---|---|
| High CPU load | CPU at 90% or more for 2 samples in a row (10 s) |
| Memory pressure | Memory used 90% or more |
| Possible thrashing | Memory 90% or more **and** swap/page-file 60% or more |
| Possible memory leak | A process grew in every sample for about 40 s and gained 80 MB or more (the process is never named) |
| High context-switch rate | More than 150,000 context switches/s |
| Heavy disk activity | Disk read + write above 100 MB/s for 2 samples in a row |
| Low disk space | Any volume 90% full or more |
| Deadlock detected | Raised by the Dining Philosophers lab (see limits below) |

Thresholds are at the top of `app.py` (`ALERTS`, `LEAK_*`) and in the `active = {...}` block, so you can tune them.

**Health score** starts at 100. It drops with high CPU and memory use and by 10 per warning or 20 per serious alert.

## 7. Optional: Windows Exporter

The project does not need it. If you also install Windows Exporter (https://github.com/prometheus-community/windows_exporter/releases, default settings), Prometheus will scrape it on port 9182, and you can build extra Grafana panels from its metrics (page faults, processor queue length, per-disk latency).

## 8. Stop and restart

- Stop: double-click `stop.bat` (stops Docker), then close the "OS Observatory" window.
- Start again: double-click `start.bat`. Grafana settings persist in a Docker volume.

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `python` is not recognised | Reinstall Python and tick "Add Python to PATH", or use `py` instead of `python` |
| `docker compose` errors or "cannot connect" | Open Docker Desktop and wait until it says it is running |
| Prometheus target `os-observatory` is DOWN | Check the app window is still open, then open http://localhost:8000/metrics. Allow Python in Windows Firewall (Private networks) |
| Grafana panels say "No data" | Wait 15 seconds, set the time range to "Last 15 minutes", and check the target is UP |
| Port already in use (5050, 8000, 3000, 9090) | Close the program using it, or change the port in `app.py` or `docker-compose.yml` |
| Dashboard not showing | Run `docker compose restart grafana` |
| `docker compose up` is slow the first time | It is downloading images. Wait |

## 10. Project layout

```text
os-observatory/
  app.py                  # monitor + Prometheus exporter + web API
  sim.py                  # scheduling, page replacement, disk, Banker's, dining philosophers, race
  static/index.html       # live status page and labs
  experiments/            # cpu_burn.py, memory_leak.py, disk_stress.py
  prometheus/prometheus.yml
  grafana/                # auto-loaded datasource and dashboard
  docker-compose.yml      # Prometheus + Grafana
  start.bat / stop.bat
```

## 11. Honest limits (good to state upfront)

- **Deadlock detection is done in the lab**, with a wait-for graph and cycle detection. The app does not claim to detect deadlocks among your real programs, because that cannot be done reliably from outside.
- **The scheduling comparison is a model.** It uses each recent process's total CPU time as its burst time and assumes all arrive at once. It shows how the algorithms would rank, not what Windows actually does.
- **The memory-leak message is a heuristic.** Sustained growth is a sign, not proof.
- Context switches, interrupts and system calls come from the OS counters via `psutil`. Some values may read zero on certain platforms.

## 12. Privacy

The app reads only numbers (CPU times, memory sizes, thread counts, process IDs for internal tracking). It never reads or displays process names, file paths, window titles or user data. Everything stays on your computer.
