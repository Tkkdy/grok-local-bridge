import os
import socket
import subprocess
import sys
import time
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "synthetic_mcp.py"

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def wait_port(process, port, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("owned test subprocess exited")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=.2):
                return
        except OSError:
            time.sleep(.1)
    raise TimeoutError("owned test subprocess did not start")

@pytest.fixture
def owned_processes():
    processes = []
    def start(args):
        p = subprocess.Popen(args, cwd=ROOT, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        processes.append(p)
        return p
    yield start
    for p in reversed(processes):
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)

@pytest.fixture
def backends(tmp_path, owned_processes):
    from grok_local_bridge.config import ConnectConfig
    port = free_port()
    audit = tmp_path / "backend-events.jsonl"
    process = owned_processes([sys.executable, str(FIXTURE), "--kind", "probe",
                               "--port", str(port), "--audit", str(audit)])
    wait_port(process, port)
    config = ConnectConfig.model_validate({"backends": [
        {"name": "hub", "transport": "stdio", "command": sys.executable,
         "args": [str(FIXTURE), "--kind", "hub", "--audit", str(audit)],
         "tools": [{"name": "get_hub_state"}]},
        {"name": "probe", "transport": "http", "url": f"http://127.0.0.1:{port}/mcp",
         "tools": [{"name": "ping"}]}
    ]})
    return config, process, audit
