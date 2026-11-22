"""Cross-process locks for one shared local appliance volume."""
from pathlib import Path
import os

class FileLock:
    def __init__(self,path): self.path=Path(path); self.handle=None
    def acquire(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.handle=self.path.open('a+b')
        try:
            if os.name=='nt':
                import msvcrt
                self.handle.seek(0);self.handle.write(b'0');self.handle.flush();self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            return True
        except OSError:
            self.handle.close();self.handle=None;return False
    def release(self):
        if self.handle:
            if os.name=='nt':
                import msvcrt
                self.handle.seek(0);msvcrt.locking(self.handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(),fcntl.LOCK_UN)
            self.handle.close();self.handle=None
