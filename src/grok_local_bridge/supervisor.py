"""One owned Tunnel and one OAuth runtime, with bounded recovery."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from .io_utils import read_json,write_json
from .oauth import validate_origin
from .processes import OwnerLock,WindowsJob
from .secret_store import SecretStore


def base_env():
    keys=("SYSTEMROOT","WINDIR","COMSPEC","PATH","PATHEXT","TEMP","TMP","USERPROFILE","LOCALAPPDATA")
    env={k:os.environ[k] for k in keys if k in os.environ}
    env["PYTHONPATH"]=str(Path(__file__).resolve().parents[1])
    return env


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0));return sock.getsockname()[1]


def ensure_port_free(port):
    with socket.socket() as sock: sock.bind(("127.0.0.1",port))


def probe(url):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url,timeout=5) as response: return response.status
    except urllib.error.HTTPError as error: return error.code
    except Exception: return None


def run(home):
    home=Path(home).resolve();settings=read_json(home/"settings.json")
    with OwnerLock(home/"manager.lock"):
        stop=home/"stop.request";recover=home/"recover.request"
        stop.unlink(missing_ok=True);recover.unlink(missing_ok=True)
        mode=settings["mode"];port=settings.get("port") or free_port();ensure_port_free(port)
        metrics=free_port();job=WindowsJob();children=[];q=queue.Queue()
        gateway_job=None
        status={"pid":os.getpid(),"phase":"STARTING","mode":mode,"port":port,"started_at":time.time(),
                "origin":None,"gateway_restarts":0,"tunnel_registered":0,"network_errors":0}
        origin=settings.get("origin")
        def save():
            status["updated_at"]=time.time();write_json(home/"status.json",status)
        def spawn(kind,args,*,capture=False,env=None,job_name=None):
            p=subprocess.Popen([sys.executable,"-m","grok_local_bridge.worker","--job",job_name or job.name,kind,*args],cwd=home,
                               env=env or base_env(),stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                               stderr=subprocess.STDOUT if capture else subprocess.DEVNULL,
                               text=True,encoding="utf-8",errors="replace",creationflags=subprocess.CREATE_NO_WINDOW)
            children.append(p);return p
        def start_gateway():
            nonlocal gateway_job
            gateway_job=WindowsJob()
            process = spawn("runtime",["--config",str(home/"connect.json"),"--state",str(state),
                                     "--origin",origin,"--port",str(port),"--secrets-dir",str(home/"secrets")],job_name=gateway_job.name,capture=True)
            def gateway_events():
                for line in process.stdout:
                    try:
                        record=json.loads(line)
                        category=record.get("worker_error_type") or record.get("type")
                        if isinstance(category,str) and re.fullmatch(r"[A-Za-z_]{1,80}",category):
                            status["gateway_error_type"]=category
                        if isinstance(record.get("os_error"),int): status["gateway_os_error"]=record["os_error"]
                    except (ValueError,AttributeError): pass
            threading.Thread(target=gateway_events,daemon=True).start()
            return process
        try:
            save();cloudflared=Path(settings["cloudflared"])
            if not cloudflared.is_file(): raise RuntimeError("cloudflared_missing")
            empty=home/"cloudflared.yml";empty.write_text("{}\n",encoding="utf-8")
            command=[str(cloudflared),"tunnel","--config",str(empty),"--origincert",str(home/"unused-cert.pem"),
                     "--no-autoupdate","--protocol","http2","--metrics",f"127.0.0.1:{metrics}"]
            env=base_env()
            if mode=="quick": command += ["--url",f"http://127.0.0.1:{port}"]
            elif mode=="named":
                origin=validate_origin(origin)
                if not origin.startswith("https://"): raise ValueError("named_requires_https")
                env["TUNNEL_TOKEN"]=SecretStore(home/"secrets").load(settings["tunnel_secret"])
                command += ["run"]
            else: raise ValueError("invalid tunnel mode")
            tunnel=spawn("exec",command,capture=True,env=env)
            def reader():
                for line in tunnel.stdout:
                    match=re.search(r"\|\s*(https://[a-z0-9]+(?:-[a-z0-9]+)+\.trycloudflare\.com)\s*\|",line)
                    if match: q.put(match.group(1))
                    if "Registered tunnel connection" in line: status["tunnel_registered"]+=1
                    if any(t in line for t in ("failed to dial","TLS handshake","context deadline exceeded")):
                        status["network_errors"]+=1
            threading.Thread(target=reader,daemon=True).start()
            if mode=="quick":
                deadline=time.monotonic()+90
                while time.monotonic()<deadline:
                    if stop.exists(): return
                    if tunnel.poll() is not None: raise RuntimeError("tunnel_exited")
                    try: origin=q.get(timeout=.5);break
                    except queue.Empty: pass
                if not origin: raise RuntimeError("tunnel_origin_unavailable")
            state=home/"oauth"/hashlib.sha256(origin.encode()).hexdigest()[:20]
            status.update(origin=origin,state_dir=str(state),mcp_url=origin+"/mcp")
            gateway=start_gateway();status["gateway_pid"]=gateway.pid;status["tunnel_pid"]=tunnel.pid
            deadline=time.monotonic()+45
            while time.monotonic()<deadline:
                if gateway.poll() is not None: raise RuntimeError("gateway_exited")
                if probe(f"http://127.0.0.1:{port}/mcp")==401: break
                time.sleep(.25)
            else: raise RuntimeError("gateway_not_ready")
            status["phase"]="READY_LOCAL_AUTH_BOUNDARY";save()
            expires=status["started_at"]+settings.get("max_minutes",120)*60 if settings.get("max_minutes",120) else float("inf")
            failures=0
            while not stop.exists() and time.time()<expires:
                if tunnel.poll() is not None: raise RuntimeError("tunnel_exited_reconnect_required")
                restart=recover.exists() or gateway.poll() is not None
                if restart:
                    recover.unlink(missing_ok=True)
                    if gateway_job: gateway_job.close()
                    if gateway.poll() is None:
                        try: gateway.wait(timeout=8)
                        except subprocess.TimeoutExpired: raise RuntimeError("gateway_stop_failed")
                    failures+=1
                    if failures>3: raise RuntimeError("gateway_recovery_limit")
                    gateway=start_gateway();status["gateway_pid"]=gateway.pid
                    status["gateway_restarts"]+=1;status["phase"]="RECOVERING_GATEWAY"
                    time.sleep(2)
                elif probe(f"http://127.0.0.1:{port}/mcp")==401:
                    status["phase"]="READY_LOCAL_AUTH_BOUNDARY"
                save();time.sleep(1)
            status["phase"]="STOPPED"
        except Exception as error:
            status["phase"]="FAILED";status["error_type"]=type(error).__name__
            status["reason"]=str(error) if isinstance(error,RuntimeError) and re.fullmatch(r"[a-z_]{1,60}",str(error)) else "component_failure"
        finally:
            if gateway_job: gateway_job.close()
            job.close()  # kills only this job's workers and their descendants
            for p in children:
                try: p.wait(timeout=8)
                except subprocess.TimeoutExpired: pass
            status["closed_at"]=time.time();save()

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--home",type=Path,required=True)
    args=parser.parse_args()
    try: run(args.home)
    except Exception: raise SystemExit(1) from None

if __name__=="__main__": main()
