# OS Observatory

A real-time system monitoring dashboard. It samples live OS metrics with `psutil`, shows them in a web UI, raises threshold-based alerts, exports Prometheus metrics, and ships with a Grafana dashboard and bounded stress tests for generating load.

#IMAGES
<img width="1363" height="610" alt="image" src="https://github.com/user-attachments/assets/620b47a0-2270-4f2d-8d17-fa1215af273a" />
Grafana Dashboard alonside other metrics

<img width="1068" height="511" alt="image" src="https://github.com/user-attachments/assets/83f17b12-ff2f-4922-8a8e-459362e0a185" />

<img width="1207" height="618" alt="image" src="https://github.com/user-attachments/assets/388c77b3-2a41-4a20-86d8-0136370b4771" />

<img width="992" height="516" alt="image" src="https://github.com/user-attachments/assets/de9cdd14-b06f-4d46-ad91-c4c294afc3c8" />

<img width="1004" height="255" alt="image" src="https://github.com/user-attachments/assets/840c82be-450b-4e2e-8094-dd7acd53c004" />
APP UI



<img width="1242" height="545" alt="image" src="https://github.com/user-attachments/assets/d14d1d2d-4d39-45a8-b50d-a7abcfb58adc" />
Docker


## Features

- **Live metrics:** CPU (total, per-core, mode split), memory, swap, disk I/O, network throughput, context switches, interrupts, process/thread counts, load average, uptime
- **Process tables:** top processes by CPU and memory (RSS)
- **Alerts:** CPU saturation, memory pressure, thrashing, memory growth (leak heuristic), high context switches, heavy disk I/O, low disk space
- **Built-in stress tests:** CPU, memory and disk, triggered from the UI or API, with size and time limits
- **Prometheus + Grafana:** pre-provisioned datasource and dashboard
- **Tests and CI:** pytest suite and GitHub Actions workflow

## Project layout

```
app.py            Flask app, sampling loop, API, Prometheus exporter
collector.py      Metric collection, environment detection, rate calculations
alerts.py         Alert thresholds and memory-growth detection
stress.py         Stress-test subprocess manager (limits, timeouts, stop)
experiments/      cpu_burn.py, memory_leak.py, disk_stress.py
static/           Web UI (index.html)
prometheus/       Prometheus config
grafana/          Dashboard JSON and provisioning
tests/            Pytest tests
METRICS.md        Metric definitions, verification methods, limitations
```

## Quick start (Docker)

```bash
docker compose up --build -d
```

| Service            | URL                              |
| ------------------ | -------------------------------- |
| Observatory UI     | http://localhost:5050            |
| Grafana            | http://localhost:3000            |
| Prometheus targets | http://localhost:9090/targets    |
| App health         | http://localhost:5050/healthz    |
| Prometheus metrics | http://localhost:8000/metrics    |

All ports bind to `127.0.0.1` only.

Set the Grafana admin password before use, via your environment or a `.env` file:

```
GRAFANA_ADMIN_PASSWORD=your-strong-password
```

The default is `change-me-now`. Change it.

Stop everything:

```bash
docker compose down
```

## Run natively (no Docker)

**Windows:** double-click `run-native.bat`

**Linux / macOS:**

```bash
chmod +x run-native.sh
./run-native.sh
```

**Manually:**

```bash
python -m venv .venv
# activate: .venv\Scripts\activate (Windows) or source .venv/bin/activate (Linux/macOS)
pip install -r requirements.txt
python app.py
```

UI: http://localhost:5050

> **Docker vs native:** Docker only sees its own Linux container (on Windows, a Linux VM), not the full host. For real host CPU, RAM, processes and disks, run natively.

## Stress testing

### Option 1: Built-in stress tester (UI)

Open the UI and use the stress-test controls to start a CPU, memory or disk test. Only one test runs at a time, and you can stop it at any point.

Limits enforced by the app:

| Test   | Parameters                                   |
| ------ | -------------------------------------------- |
| CPU    | Duration 1–120 s                             |
| Memory | Size 16–2048 MB                              |
| Disk   | Duration 1–120 s, file size 8–1024 MB        |

API equivalents:

```
POST /api/stress/cpu      {"duration": 30}
POST /api/stress/memory   {"size_mb": 256}
POST /api/stress/disk     {"duration": 30, "size_mb": 128}
POST /api/stress/stop
GET  /api/stress/status
```

Set `ENABLE_STRESS=0` to disable the built-in tester.

### Option 2: Manual stress test (if the built-in tester can't be used)

If the UI/API tester is disabled or unavailable, run the experiment scripts directly inside the container:

```bash
# CPU: burn all cores for 60 seconds
docker exec -it os-observatory-app python experiments/cpu_burn.py 60

# Memory: gradually allocate up to 600 MB (simulates a leak)
docker exec -it os-observatory-app python experiments/memory_leak.py 600

# Disk: sustained read/write I/O for 40 seconds
docker exec -it os-observatory-app python experiments/disk_stress.py 40
```

Arguments:

| Script           | Arguments                              | Defaults       | Limits                    |
| ---------------- | -------------------------------------- | -------------- | ------------------------- |
| `cpu_burn.py`    | `[seconds]`                            | 30 s           | 1–120 s                   |
| `memory_leak.py` | `[megabytes]`                          | 256 MB         | 16–2048 MB                |
| `disk_stress.py` | `[seconds] [file_size_mb]`             | 30 s, 128 MB   | 1–120 s, 8–1024 MB        |

Notes:

- `memory_leak.py` allocates 16 MB every 2 seconds, then holds the memory for about 45 seconds before releasing it.
- `disk_stress.py` writes to a temporary file and deletes it on exit.
- Press `Ctrl+C` to stop any script early. All three clean up after themselves.
- Running natively? Use the same scripts without `docker exec`, e.g. `python experiments/cpu_burn.py 60`.

### What to watch

| Test   | Where you should see it                                          | Expected alert                |
| ------ | ---------------------------------------------------------------- | ----------------------------- |
| CPU    | CPU chart, per-core view, top processes                          | `cpu_saturation` (after 10 s above 90%) |
| Memory | Memory chart, process RSS                                        | `memory_leak` (≥ 80 MB growth over 40 s) |
| Disk   | Disk read/write chart                                            | `heavy_disk_io` (≥ 20 MB/s for 10 s) |

Cross-check against `docker stats` (or Task Manager / `top` when running natively). See `METRICS.md` for how each metric is calculated and verified.

## Configuration

Set via environment variables (or `.env` for Docker Compose).

| Variable                       | Default    | Description                                   |
| ------------------------------ | ---------- | --------------------------------------------- |
| `UI_PORT`                      | 5050       | Web UI port                                   |
| `METRICS_PORT`                 | 8000       | Prometheus metrics port                       |
| `UI_HOST`                      | 127.0.0.1  | Bind address (native runs)                    |
| `SAMPLE_INTERVAL`              | 5          | Seconds between samples (min 1)               |
| `ENABLE_METRICS`               | 1          | Set `0` to disable the Prometheus exporter    |
| `ENABLE_STRESS`                | 1          | Set `0` to disable built-in stress tests      |
| `SHOW_PROCESS_NAMES`           | 0 in Docker, 1 native | Show process names in tables      |
| `LOG_LEVEL`                    | INFO       | Logging level                                 |
| `ALERT_CPU_PERCENT`            | 90         | CPU alert threshold (%)                       |
| `ALERT_CPU_DURATION_SECONDS`   | 10         | Time CPU must stay above threshold            |
| `ALERT_MEMORY_PERCENT`         | 90         | Memory alert threshold (%)                    |
| `ALERT_SWAP_PERCENT`           | 60         | Swap threshold used for thrashing detection   |
| `ALERT_CONTEXT_SWITCHES_PER_S` | 150000     | Context switch rate threshold                 |
| `ALERT_DISK_BYTES_PER_S`       | 20971520   | Disk throughput threshold (bytes/s)           |
| `ALERT_DISK_DURATION_SECONDS`  | 10         | Time disk must stay above threshold           |
| `ALERT_DISK_USED_PERCENT`      | 90         | Volume usage threshold (%)                    |
| `ALERT_LEAK_WINDOW_SECONDS`    | 40         | Window for memory-growth detection            |
| `ALERT_LEAK_GROWTH_MB`         | 80         | Growth within window that triggers an alert   |

Effective thresholds are available at `GET /api/config`.

## API

| Endpoint                 | Method | Description                  |
| ------------------------ | ------ | ---------------------------- |
| `/`                      | GET    | Web UI                       |
| `/healthz`               | GET    | Health check                 |
| `/api/status`            | GET    | Current metrics and alerts   |
| `/api/history`           | GET    | Recent sample history        |
| `/api/config`            | GET    | Effective configuration      |
| `/api/stress/<kind>`     | POST   | Start `cpu`, `memory` or `disk` test |
| `/api/stress/stop`       | POST   | Stop the running test        |
| `/api/stress/status`     | GET    | Stress-test state            |

## Development

```bash
pip install -r requirements-dev.txt
pytest -q          # or: make test
```

CI runs the same tests via `.github/workflows/tests.yml`.

## Known limitations

- Inside Docker, metrics describe the container/VM environment, not the full host. Run natively for host-level data.
- Memory-leak alerts are a heuristic (sustained monotonic RSS growth). They can't prove a software leak.
- Some counters (interrupts, load average, disk I/O) aren't exposed on every platform and may be missing or zero.
- Full details per metric are in [`METRICS.md`](METRICS.md).
