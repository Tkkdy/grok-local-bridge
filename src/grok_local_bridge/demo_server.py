"""Two process-distinct, synthetic MCP fixtures. Never accesses real Hub."""
import argparse
import json
import os
import time
from pathlib import Path
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

parser = argparse.ArgumentParser()
parser.add_argument("--kind", choices=["hub", "probe"], required=True)
parser.add_argument("--port", type=int)
parser.add_argument("--audit", required=True)
parser.add_argument("--verify-secret-fixture", action="store_true")
args = parser.parse_args()
mcp = FastMCP("Synthetic-" + args.kind, version="0.1.1a0", tasks=False)

def record(tool):
    # Windows CRT append is not atomic across independent processes. Serialize
    # the demo-only audit before opening the data file at its current end.
    with open(args.audit + ".lock", "a+b") as lock:
        if lock.seek(0, 2) == 0:
            lock.write(b"0"); lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(args.audit, "a", encoding="utf-8") as f:
                f.write(json.dumps({"time": time.time(), "pid": os.getpid(), "backend": args.kind,
                                    "tool": tool}) + "\n")
        finally:
            if os.name == "nt":
                lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def get_hub_state() -> dict:
    """Read an isolated synthetic Attention Router-shaped state."""
    record("get_hub_state")
    return {"provenance": "SYNTHETIC", "backend": args.kind, "pid": os.getpid(),
            "todos": {"revision": 1, "tasks": [{"id": "synthetic-1", "title": "Local Bridge demo", "status": "pending"}]},
            "current_item": None}

@mcp.tool(annotations={"readOnlyHint": True, "destructiveHint": False})
def ping() -> dict:
    """Return a deterministic reply from the independent probe process."""
    record("ping")
    headers = get_http_headers(include={"authorization"})
    if args.verify_secret_fixture:
        return {"provenance":"SYNTHETIC","reply":"pong",
                "backend_auth_matches":headers.get("authorization")=="Bearer SYNTHETIC_ONLY_TEST_VALUE",
                "configured_env_matches":os.environ.get("GLB_SYNTHETIC_KEY")=="SYNTHETIC_ONLY_TEST_VALUE",
                "unrelated_env_present":"GLB_UNRELATED_SYNTHETIC_SECRET" in os.environ}
    return {"provenance": "SYNTHETIC", "reply": "pong", "backend": args.kind,
            "pid": os.getpid(), "authorization_header_received": "authorization" in headers}

@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": True})
def forbidden_delete() -> str:
    """Synthetic forbidden side effect; must never be reached through Connect."""
    record("forbidden_delete")
    return "FORBIDDEN_TOOL_REACHED"

@mcp.resource("fixture://private")
def private_data() -> str:
    record("private_resource")
    return "SYNTHETIC_PRIVATE_RESOURCE"

@mcp.prompt
def private_prompt() -> str:
    record("private_prompt")
    return "Synthetic prompt"

if __name__ == "__main__":
    if args.port:
        mcp.run(transport="http", host="127.0.0.1", port=args.port, show_banner=False,
                stateless_http=True, json_response=True)
    else:
        mcp.run(transport="stdio", show_banner=False)
