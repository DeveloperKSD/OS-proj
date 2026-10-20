"""Safe single-job subprocess stress-test manager."""
from __future__ import annotations
import os, subprocess, sys, threading, time
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parent
CAPS={'cpu': {'max_duration':120}, 'memory': {'max_mb':2048}, 'disk': {'max_duration':120,'max_mb':1024}}
class StressManager:
    def __init__(self, enabled: bool=True):
        self.enabled=enabled; self.lock=threading.RLock(); self.proc: subprocess.Popen | None=None
        self.kind: str | None=None; self.started=0.0; self.deadline=0.0; self.params: dict[str,Any]={}
    def start(self, kind: str, data: dict[str,Any]) -> dict[str,Any]:
        if not self.enabled: raise ValueError('Stress tests are disabled (ENABLE_STRESS=0).')
        if kind not in CAPS: raise ValueError('Unknown stress test.')
        with self.lock:
            self._refresh()
            if self.proc and self.proc.poll() is None: raise RuntimeError('A stress test is already running.')
            if kind=='cpu':
                duration=int(data.get('duration',30))
                if not 1<=duration<=120: raise ValueError('Duration must be 1–120 seconds.')
                args=[sys.executable,str(ROOT/'experiments/cpu_burn.py'),str(duration)]; deadline=duration
                params={'duration':duration}
            elif kind=='memory':
                size=int(data.get('size_mb',256))
                if not 16<=size<=2048: raise ValueError('Memory size must be 16–2048 MB.')
                args=[sys.executable,str(ROOT/'experiments/memory_leak.py'),str(size)]; deadline=120
                params={'size_mb':size}
            else:
                duration=int(data.get('duration',30)); size=int(data.get('size_mb',128))
                if not 1<=duration<=120: raise ValueError('Duration must be 1–120 seconds.')
                if not 8<=size<=1024: raise ValueError('Disk file size must be 8–1024 MB.')
                args=[sys.executable,str(ROOT/'experiments/disk_stress.py'),str(duration),str(size)]; deadline=duration
                params={'duration':duration,'size_mb':size}
            kwargs={'cwd':str(ROOT),'stdout':subprocess.DEVNULL,'stderr':subprocess.DEVNULL}
            if os.name=='nt': kwargs['creationflags']=subprocess.CREATE_NEW_PROCESS_GROUP
            else: kwargs['start_new_session']=True
            self.proc=subprocess.Popen(args,**kwargs); self.kind=kind; self.started=time.time(); self.deadline=self.started+deadline; self.params=params
            return self.status()
    def _refresh(self):
        if self.proc and self.proc.poll() is not None: self.proc=None; self.kind=None
        elif self.proc and time.time() >= self.deadline:
            self._kill_process_tree()
            self.proc=None; self.kind=None
    def _kill_process_tree(self) -> None:
        if not self.proc: return
        try:
            if os.name == 'nt':
                subprocess.run(['taskkill','/PID',str(self.proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
            else:
                import signal
                os.killpg(self.proc.pid, signal.SIGTERM)
        except (OSError, subprocess.SubprocessError):
            self.proc.terminate()
        try: self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try: self.proc.kill()
            except OSError: pass
            self.proc.wait(timeout=2)
    def status(self) -> dict[str,Any]:
        with self.lock:
            self._refresh()
            active=bool(self.proc and self.proc.poll() is None)
            return {'enabled':self.enabled,'active':active,'kind':self.kind if active else None,
                    'started_at':self.started if active else None,'deadline':self.deadline if active else None,
                    'remaining_seconds':max(0,round(self.deadline-time.time())) if active else 0,'params':self.params if active else {}}
    def stop(self) -> dict[str,Any]:
        with self.lock:
            if self.proc and self.proc.poll() is None:
                self._kill_process_tree()
            self.proc=None; self.kind=None
        return self.status()
