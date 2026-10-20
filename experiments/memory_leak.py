"""Allocate and touch memory gradually to demonstrate real RSS growth."""
import sys, time, signal
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

def main() -> None:
    limit=max(16,min(2048,int(sys.argv[1]) if len(sys.argv)>1 else 256))
    hold=[]; allocated=0
    try:
        while allocated < limit:
            amount=min(16,limit-allocated); block=bytearray(amount*1024*1024)
            for i in range(0,len(block),4096): block[i]=1
            hold.append(block); allocated+=amount; time.sleep(2)
        time.sleep(45)
    except KeyboardInterrupt:
        pass
    finally:
        hold.clear()
if __name__=='__main__': main()
