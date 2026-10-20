"""Simulates a memory leak (grows ~25 MB every 4 s) so the 'Possible memory leak' message appears.
Usage: python memory_leak.py [max_MB]   (default 1000 MB, then it frees everything and exits)"""
import sys, time

limit = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
hold, mb = [], 0
print(f"Leaking up to {limit} MB. Press Ctrl+C to stop early.")
try:
    while mb < limit:
        hold.append(bytearray(25 * 1024 * 1024))
        for i in range(0, len(hold[-1]), 4096):
            hold[-1][i] = 1          # touch pages so they really count
        mb += 25
        print(f"  allocated {mb} MB", end="\r")
        time.sleep(4)
    print("\nHolding for 20 s, then releasing...")
    time.sleep(20)
except KeyboardInterrupt:
    pass
print("Released.")
