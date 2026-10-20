"""Generate bounded CPU load. Usage: python cpu_burn.py [seconds]."""
import multiprocessing as mp
import os, sys, time, signal
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

def burn(end: float) -> None:
    while time.monotonic() < end:
        pass

if __name__ == '__main__':
    duration=max(1,min(120,int(sys.argv[1]) if len(sys.argv)>1 else 30))
    end=time.monotonic()+duration
    workers=max(1,min(os.cpu_count() or 1, 64))
    children=[mp.Process(target=burn,args=(end,)) for _ in range(workers)]
    try:
        for child in children: child.start()
        for child in children: child.join(max(0,end-time.monotonic()))
    except KeyboardInterrupt:
        pass
    finally:
        for child in children:
            if child.is_alive(): child.terminate()
            child.join(timeout=1)
