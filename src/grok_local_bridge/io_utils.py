"""Small atomic local state helpers. Never serializes a credential."""
import json
import os
from pathlib import Path
import tempfile


def atomic_bytes(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=".connect-",suffix=".tmp",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


def write_json(path,value):
    atomic_bytes(path,(json.dumps(value,ensure_ascii=False,indent=2)+"\n").encode("utf-8"))


def read_json(path):
    data=Path(path).read_bytes()
    if len(data)>262144: raise ValueError("local state too large")
    return json.loads(data)
