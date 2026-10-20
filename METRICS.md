# Metrics: definitions, verification and limitations

All values are collected from the OS interface visible to the Python process. Counter rates use the difference between consecutive readings divided by actual elapsed wall time; a counter reset produces 0 for that interval.

| Metric | Exact source / calculation | How to verify | Limitations |
|---|---|---|---|
| CPU utilisation (%) | `psutil.cpu_percent(interval=None)` | Task Manager → Performance → CPU; `top`/`htop`; `docker stats` for container load | Container view is not full host telemetry. First sample is primed before sampling. |
| Per-core CPU (%) | `psutil.cpu_percent(interval=None, percpu=True)` | Task Manager CPU → Change graph to logical processors; `top` | Logical CPU topology and container visibility vary. |
| CPU mode split (%) | `psutil.cpu_times_percent(interval=None)` and fields exposed by the platform | `top`/`htop` CPU states | Only modes present on the platform are emitted; fields are CPU-time percentages, not a mutually exhaustive cross-platform contract. |
| Memory % and used/total GB | `psutil.virtual_memory()` (`percent`, `used`, `total`) | Task Manager → Memory; `free -h`; `docker stats` | OS and container memory accounting differ; GB uses decimal units. |
| Swap % and used/total GB | `psutil.swap_memory()` | Task Manager page-file view where available; `free -h`; `docker stats` | Some platforms have no swap; values may legitimately be 0. |
| Disk read/write bytes/s | `psutil.disk_io_counters()` byte counters, delta / elapsed seconds | `docker stats` block I/O; Windows Resource Monitor; `iostat` | Counters may be unavailable or aggregate physical devices; container disk activity can include shared backing storage. |
| Network up/down bytes/s | `psutil.net_io_counters()` `bytes_sent` / `bytes_recv`, delta / elapsed seconds | `docker stats` network I/O; Resource Monitor; `ip -s link` | Includes interfaces visible to the process, potentially virtual/container interfaces. |
| Context switches/s | `psutil.cpu_stats().ctx_switches`, delta / elapsed seconds | `vmstat 1`; `pidstat -w 1` (process-level, not directly identical) | Platform availability and scope vary. |
| Interrupts/s | `psutil.cpu_stats().interrupts`, delta / elapsed seconds, only when exposed | `vmstat 1`; `/proc/interrupts` on Linux | Missing when the platform does not expose a counter; resets yield 0 for one sample. |
| Process count / thread count | `psutil.process_iter()` and each accessible process's `num_threads` | Task Manager Details; `ps -e`; `top` | Access-denied processes may be omitted; the list can change during collection. |
| Top 5 process CPU / RSS | `psutil.process_iter()` fields `cpu_percent`, `memory_info.rss` | Task Manager Details; `top` sorted by CPU or memory | Process CPU can be 0 during initial measurement; permission restrictions and process churn apply. Names are hidden unless `SHOW_PROCESS_NAMES=1`. |
| Disk volume used % | `psutil.disk_partitions()` and `psutil.disk_usage(mountpoint)` | File Explorer drive properties; `df -h` | Permission-denied/unmounted volumes are omitted; container mount points are not necessarily host volumes. |
| Load average | `os.getloadavg()` where available | `uptime`; `top` | Linux/macOS only in common deployments; not emitted as a value when unavailable. |
| Uptime | `time.time() - psutil.boot_time()` | `uptime` on Unix; Task Manager uptime | In a container, boot time commonly describes the host kernel, not container start time. |
| Heuristic health score | Formula described in UI: base 100, CPU penalty above 80%, memory penalty above 80%, then alert penalties, clamped 0–100 | Compare displayed CPU, memory and active alerts | A project-specific heuristic, not an OS standard or a diagnostic. |

## Environment scope

The app checks `/.dockerenv` and `/proc/1/cgroup` for common container markers. Docker Desktop on Windows runs Linux containers in a VM, so this app reports that container/VM view—not complete Windows host CPU, RAM, processes or disks. Run natively on the host for host-level psutil metrics.

## Sampling and alerts

`SAMPLE_INTERVAL` defaults to 5 seconds. Rate values are based on actual elapsed time. Alert thresholds are configurable with environment variables prefixed `ALERT_`; `/api/config` lists the effective thresholds. Leak detection compares per-process RSS snapshots across a time window and requires monotonic growth. This is a heuristic and cannot prove a software memory leak.
