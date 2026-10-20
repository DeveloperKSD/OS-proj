"""Heavy sequential disk I/O so the 'Heavy disk activity' message can appear.
Writes and reads a temp file (default 1500 MB) in a loop for N seconds, then deletes it.
Usage: python disk_stress.py [seconds] [file_MB]"""
import os, sys, tempfile, time

secs = int(sys.argv[1]) if len(sys.argv) > 1 else 40
size = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
path = os.path.join(tempfile.gettempdir(), "obs_disk_stress.tmp")
chunk = os.urandom(8 * 1024 * 1024)
end = time.time() + secs
print(f"Disk stress for {secs}s using {size} MB temp file...")
try:
    while time.time() < end:
        with open(path, "wb") as f:
            for _ in range(size // 8):
                f.write(chunk)
            f.flush(); os.fsync(f.fileno())
        with open(path, "rb") as f:
            while f.read(8 * 1024 * 1024):
                pass
finally:
    if os.path.exists(path):
        os.remove(path)
print("Done, temp file removed.")
