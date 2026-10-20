# OS Observatory

A local-first live system monitor built with Flask, psutil and Prometheus, with a self-contained canvas-chart UI and Grafana dashboard. It reports measured OS values only; the UI reports measured OS values only.

## Run with Docker (recommended for the bundled dashboards)

1. Install and start Docker Desktop / Docker Engine.
2. From this folder run `docker compose up --build -d` (or double-click `start.bat` on Windows).
3. Open the UI at http://localhost:5050, Grafana at http://localhost:3000 and Prometheus targets at http://localhost:9090/targets.
4. Check `docker compose ps` for health status. The app health endpoint is http://localhost:5050/healthz. The Prometheus target should be UP.

Ports are bound to `127.0.0.1` by default. Grafana admin password is configured with `GRAFANA_ADMIN_PASSWORD`; set it in your shell or a local `.env` file before starting. The default is `change-me-now`, so change it before use. Grafana anonymous viewing is enabled for the local dashboard. Stop with `stop.bat` or `docker compose down`.

## Run natively without Docker

- Windows: double-click `run-native.bat`.
- Linux/macOS: run `./run-native.sh`.
- Manual alternative: `python -m venv .venv`, activate it, `pip install -r requirements.txt`, then `python app.py`.

The native server binds to `127.0.0.1` by default. UI is `http://127.0.0.1:5050`; Prometheus metrics are at `http://127.0.0.1:8000/metrics` when enabled.

## Configuration

| Variable | Default | Purpose |
|---|---:|---|
| `UI_PORT` | `5050` | Flask UI/API port |
| `METRICS_PORT` | `8000` | Prometheus exporter port |
| `SAMPLE_INTERVAL` | `5` | Sampling interval in seconds |
| `ENABLE_METRICS` | `1` | Set `0` to disable Prometheus exporter |
| `ENABLE_STRESS` | `1` | Set `0` to disable stress-test endpoints |
| `SHOW_PROCESS_NAMES` | Native `1`, Docker `0` | Reveal process names in UI/API |
| `GRAFANA_ADMIN_PASSWORD` | `change-me-now` | Grafana admin password in Docker |
| `ALERT_CPU_PERCENT` | `90` | CPU saturation threshold |
| `ALERT_CPU_DURATION_SECONDS` | `10` | Sustained CPU threshold duration |
| `ALERT_MEMORY_PERCENT` | `90` | Memory pressure threshold |
| `ALERT_SWAP_PERCENT` | `60` | Swap threshold for thrashing alert |
| `ALERT_CONTEXT_SWITCHES_PER_S` | `150000` | Context switch threshold |
| `ALERT_DISK_BYTES_PER_S` | `20971520` | Disk throughput threshold |
| `ALERT_DISK_DURATION_SECONDS` | `10` | Sustained disk threshold duration |
| `ALERT_DISK_USED_PERCENT` | `90` | Volume usage threshold |
| `ALERT_LEAK_WINDOW_SECONDS` | `40` | Leak observation window |
| `ALERT_LEAK_GROWTH_MB` | `80` | Required monotonic RSS growth |

The effective values are available at `/api/config`. Stress-test limits are enforced server-side: CPU and disk duration at most 120 seconds, memory at most 2048 MB, disk test file at most 1024 MB. Only one stress test can run at a time. **Stress tests really load or allocate resources in the machine/container.** Keep the UI local; Docker ports are loopback-bound by default.

## Honest scope and limitations

- Docker reports the Linux container environment (often a Docker Desktop Linux VM), not your complete Windows/macOS host. Run natively for host-level metrics.
- psutil cannot guarantee access to every process or volume. Platform APIs expose different CPU modes, load averages, interrupt counters and swap semantics; unavailable data is omitted where appropriate.
- Process names are shown only when enabled. No telemetry is sent and the UI has no external CDN dependencies.
- The health score is a project-specific heuristic, not an OS standard. Leak detection indicates sustained RSS growth; it cannot prove a code-level memory leak.

## Verification

Install dev dependency `pytest` and run `pytest -q` (or `make test`). `test-monitor.ps1` checks the main endpoints and metric response on a running instance. See [METRICS.md](METRICS.md) for every metric's source, verification method and limitations.
