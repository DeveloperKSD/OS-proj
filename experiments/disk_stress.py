"""Bounded sequential disk I/O using a uniquely named temporary file."""
import os, sys, tempfile, time, signal
signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))

def main() -> None:
    seconds=max(1,min(120,int(sys.argv[1]) if len(sys.argv)>1 else 30))
    size=max(8,min(1024,int(sys.argv[2]) if len(sys.argv)>2 else 128))*1024*1024
    fd,path=tempfile.mkstemp(prefix='os-observatory-',suffix='.tmp'); chunk=os.urandom(1024*1024); end=time.monotonic()+seconds
    try:
        while time.monotonic()<end:
            with os.fdopen(os.dup(fd),'wb') as f:
                remaining=size
                while remaining>0 and time.monotonic()<end:
                    part=chunk[:min(len(chunk),remaining)]; f.write(part); remaining-=len(part)
                f.flush(); os.fsync(f.fileno())
            with open(path,'rb') as f:
                while f.read(1024*1024) and time.monotonic()<end: pass
    except KeyboardInterrupt:
        pass
    finally:
        os.close(fd)
        try: os.remove(path)
        except FileNotFoundError: pass
if __name__=='__main__': main()
