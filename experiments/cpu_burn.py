"""Creates CPU load so the 'High CPU load' message appears. Usage: python cpu_burn.py [seconds]"""
import multiprocessing as mp, os, sys, time

def burn(end):
    while time.time() < end:
        pass

if __name__ == "__main__":
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    end = time.time() + secs
    n = (os.cpu_count() or 4) * 2
    print(f"Burning CPU with {n} processes for {secs}s...")
    ps = [mp.Process(target=burn, args=(end,)) for _ in range(n)]
    [p.start() for p in ps]; [p.join() for p in ps]
    print("Done.")
