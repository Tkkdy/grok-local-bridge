"""User-facing local management. No remote admin endpoints or secret arguments."""
import argparse
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from .config import Backend,ConnectConfig
from .io_utils import read_json,write_json
from .oauth import validate_origin
from .processes import manager_alive
from .supervisor import base_env,probe


def default_home():
    """The installer and direct CLI share state, including installed-wheel calls."""
    candidates = [Path(__file__).resolve().parents[2], Path(sys.prefix).resolve().parent]
    for root in candidates:
        if (root / ".grok-local-bridge-install").is_file():
            return root / ".runtime"
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / "Grok Local Bridge" / "state"

def emit(value): print(json.dumps(value,ensure_ascii=False,indent=2))

def find_cloudflared():
    candidates=[shutil.which("cloudflared"),str(Path(__file__).resolve().parents[2]/"tools/cloudflared.exe"),
                r"C:\Program Files (x86)\cloudflared\cloudflared.exe",r"C:\Program Files\cloudflared\cloudflared.exe"]
    return next((str(Path(p).resolve()) for p in candidates if p and Path(p).is_file()),None)

def owner_ui_available():
    """Probe Tcl without opening a window or loading an owner credential."""
    try:
        import tkinter
        tkinter.Tcl()
    except Exception:
        return False
    return True


def config(home): return ConnectConfig.model_validate(read_json(home/"connect.json"))

def no_inline_secrets(backend):
    for arg in backend.args:
        if re.search(r"(?i)(?:--?|/)(?:api[-_]?key|token|secret|password|cookie|authorization)(?:$|[=: ])",arg):
            raise ValueError("use_secret_slots")
        if "-----BEGIN " in arg: raise ValueError("use_secret_slots")

def initialize(home,cloudflared):
    home.mkdir(parents=True,exist_ok=True)
    marker=home/".grok-local-bridge"
    if not marker.exists() and any((home/name).exists() for name in ("connect.json","settings.json","status.json","manager.lock")):
        raise ValueError("existing_unmanaged_state_choose_empty_directory")
    if not marker.exists(): marker.write_text("grok-local-bridge-v1\n",encoding="ascii")
    if not (home/"connect.json").exists(): write_json(home/"connect.json",{"version":1,"backends":[]})
    if not (home/"settings.json").exists():
        write_json(home/"settings.json",{"mode":"quick","port":0,"cloudflared":cloudflared or find_cloudflared(),"max_minutes":120})

def status(home):
    value=read_json(home/"status.json") if (home/"status.json").exists() else {"phase":"NOT_STARTED"}
    value["manager_alive"]=manager_alive(home)
    if value.get("state_dir"):
        state=Path(value["state_dir"]).resolve()
        if state.is_relative_to(home/"oauth") and (state/"reload.status.json").exists():
            value["configuration"]=read_json(state/"reload.status.json")
    return value

async def inspect_backend(backend,home):
    from .composition import backend_client
    from .secret_store import SecretStore
    async with backend_client(backend,SecretStore(home/"secrets")) as client:
        tools=await client.list_tools()
        return [{"name":t.name,"read_only_hint":getattr(t.annotations,"readOnlyHint",None),
                 "destructive_hint":getattr(t.annotations,"destructiveHint",None)} for t in tools]

def start(home):
    if manager_alive(home): return status(home)
    config(home)
    settings=read_json(home/"settings.json")
    if not settings.get("cloudflared") or not Path(settings["cloudflared"]).is_file(): raise ValueError("cloudflared_missing")
    launched=time.time()
    process=subprocess.Popen([sys.executable,"-m","grok_local_bridge.supervisor","--home",str(home)],
                             env=base_env(),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS)
    for _ in range(120):
        if process.poll() is not None: return status(home)
        value=status(home)
        if value.get("pid")==process.pid and value.get("phase") not in ("STARTING",None): return value
        # Windows venv launches a separate interpreter: wait for its owned lock/status too.
        if value.get("manager_alive") and value.get("started_at",0)>=launched-.5 and value.get("phase")=="READY_LOCAL_AUTH_BOUNDARY": return value
        time.sleep(1)
    return {**status(home),"notice":"Startup still running; inspect status, do not start another instance."}

def main():
    parser=argparse.ArgumentParser(prog="grok-local-bridge")
    parser.add_argument("--home",type=Path,default=default_home())
    sub=parser.add_subparsers(dest="command",required=True)
    p=sub.add_parser("init");p.add_argument("--cloudflared")
    p=sub.add_parser("configure");p.add_argument("--mode",choices=["quick","named"],required=True)
    p.add_argument("--origin");p.add_argument("--port",type=int,default=0);p.add_argument("--tunnel-secret");p.add_argument("--minutes",type=int,default=120)
    p=sub.add_parser("add");p.add_argument("--spec",type=Path,required=True);p.add_argument("--replace",action="store_true")
    p.add_argument("--permission",action="append",choices=["write","delete","exec","hardware"],default=[])
    p=sub.add_parser("probe");p.add_argument("--spec",type=Path,required=True)
    p=sub.add_parser("secret");p.add_argument("--name",required=True)
    p=sub.add_parser("remove");p.add_argument("--name",required=True)
    sub.add_parser("verify")
    sub.add_parser("demo")
    for cmd in ("doctor","start","status","stop","diagnose","recover","owner"):
        sub.add_parser(cmd)
    args=parser.parse_args();home=args.home.resolve()
    try:
        if args.command=="init":
            initialize(home,args.cloudflared);emit({"result":"INITIALIZED","home":str(home)})
        elif args.command=="doctor":
            settings=read_json(home/"settings.json") if (home/"settings.json").exists() else {}
            cf=settings.get("cloudflared") or find_cloudflared();version=None
            if cf:
                raw=subprocess.run([cf,"--version"],capture_output=True,text=True,timeout=10).stdout
                match=re.search(r"cloudflared version ([0-9.]+)",raw)
                version=match.group(1) if match else "UNRECOGNIZED"
            ui_ready=owner_ui_available()
            emit({"windows":os.name=="nt","python":sys.version.split()[0],"fastmcp":importlib.metadata.version("fastmcp"),
                  "cloudflared":cf,"cloudflared_version":version,"home_exists":home.exists(),
                  "owner_ui_available":ui_ready,
                  "owner_ui_hint":None if ui_ready else "Install full Python 3.13 with working Tcl/Tk for the local OAuth window."})
        elif args.command=="configure":
            if manager_alive(home): raise ValueError("stop_manager_before_tunnel_settings_change")
            settings=read_json(home/"settings.json")
            if not 0<=args.port<=65535 or not 0<=args.minutes<=1440: raise ValueError("invalid_port_or_duration")
            if args.mode=="named":
                if not args.origin or not args.tunnel_secret or not args.port: raise ValueError("named_requires_origin_port_and_secret_slot")
                if not validate_origin(args.origin).startswith("https://"): raise ValueError("named_requires_https")
                from .secret_store import SecretStore
                SecretStore(home/"secrets").slot_path(args.tunnel_secret)
            settings.update(mode=args.mode,origin=args.origin,port=args.port,tunnel_secret=args.tunnel_secret,max_minutes=args.minutes)
            write_json(home/"settings.json",settings);emit({"result":"CONFIGURED","mode":args.mode})
        elif args.command in ("add","probe"):
            backend=Backend.model_validate(read_json(args.spec));no_inline_secrets(backend)
            if args.command=="probe": emit({"backend":backend.name,"tools":asyncio.run(inspect_backend(backend,home)),"warning":"Backend metadata is untrusted; discovery is not Grok acceptance."});return
            elevated=set(backend.permissions)-{"read"}
            if not elevated.issubset(set(args.permission)): raise ValueError("explicit_permission_flag_required")
            current=config(home);existing=next((b for b in current.backends if b.name==backend.name),None)
            if existing and not args.replace: raise ValueError("namespace_exists_use_replace")
            write_json(home/"connect.previous.json",current.model_dump())
            current.backends=[b for b in current.backends if b.name!=backend.name]+[backend]
            write_json(home/"connect.json",current.model_dump())
            emit({"result":"SAVED_FOR_HOT_RELOAD","backend":backend.name,"tools":[t.name for t in backend.tools],
                  "permissions":backend.permissions,"notice":"Check configuration status and actual client discovery; saving is not acceptance."})
        elif args.command=="remove":
            current=config(home)
            if not any(b.name==args.name for b in current.backends): raise ValueError("namespace_not_found")
            write_json(home/"connect.previous.json",current.model_dump())
            current.backends=[b for b in current.backends if b.name!=args.name]
            write_json(home/"connect.json",current.model_dump())
            emit({"result":"SAVED_FOR_HOT_RELOAD","removed_backend":args.name,
                  "notice":"Wait for APPLIED configuration status; an in-flight call may complete. Refresh the client catalog."})
        elif args.command=="verify":
            async def verify_demo():
                from fastmcp import Client
                from .composition import build_server
                current=config(home)
                expected={"hub_get_hub_state","probe_ping"}
                if {b.name for b in current.backends}!={"hub","probe"}: raise ValueError("verify_requires_synthetic_demo")
                demo_script=Path(__file__).with_name("demo_server.py").resolve()
                for b in current.backends:
                    actual_script=Path(b.args[0]).resolve() if b.args else None
                    approved_scripts={demo_script,(home.parent/"src/grok_local_bridge/demo_server.py").resolve()}
                    if (b.transport!="stdio" or Path(b.command).resolve()!=Path(sys.executable).resolve()
                        or actual_script not in approved_scripts or b.env_secrets or b.bearer_secret
                        or actual_script.read_bytes()!=demo_script.read_bytes()
                        or b.args[1:]!=["--kind",b.name,"--audit",str(home/"demo-backend-events.jsonl")]):
                        raise ValueError("verify_requires_synthetic_demo")
                async with Client(build_server(current),mode="legacy") as client:
                    names={t.name for t in await client.list_tools()}
                    if names!=expected: raise ValueError("unexpected_demo_catalog")
                    hub=(await client.call_tool("hub_get_hub_state")).data
                    probe_value=(await client.call_tool("probe_ping")).data
                if (hub.get("provenance")!="SYNTHETIC" or probe_value.get("provenance")!="SYNTHETIC"
                    or hub.get("pid")==probe_value.get("pid") or probe_value.get("reply")!="pong"
                    or probe_value.get("authorization_header_received")):
                    raise ValueError("demo_verification_failed")
                return {"result":"PASS_LOCAL_SYNTHETIC","tools":sorted(names),"independent_backends":True,
                        "notice":"Local protocol verification only; does not prove OAuth, public HTTPS or Grok acceptance."}
            emit(asyncio.run(verify_demo()))
        elif args.command=="demo":
            current=config(home)
            if current.backends: raise ValueError("demo_requires_empty_config")
            script=str(Path(__file__).with_name("demo_server.py"))
            audit=str(home/"demo-backend-events.jsonl")
            demo={"version":1,"backends":[
                {"name":"hub","transport":"stdio","command":sys.executable,"args":[script,"--kind","hub","--audit",audit],"tools":[{"name":"get_hub_state"}]},
                {"name":"probe","transport":"stdio","command":sys.executable,"args":[script,"--kind","probe","--audit",audit],"tools":[{"name":"ping"}]}]}
            write_json(home/"connect.json",ConnectConfig.model_validate(demo).model_dump())
            emit({"result":"SYNTHETIC_DEMO_CONFIGURED","notice":"Two independent local processes. No real Hub, files, business writes or hardware."})
        elif args.command=="secret":
            from .ui import secret_window
            secret_window(home,args.name)
        elif args.command=="owner":
            from .ui import owner_window
            owner_window(home)
        elif args.command=="start": emit(start(home))
        elif args.command=="status": emit(status(home))
        elif args.command in ("stop","recover"):
            alive=manager_alive(home)
            if args.command=="recover" and not alive:
                emit(start(home));return
            if alive: (home/("stop.request" if args.command=="stop" else "recover.request")).touch()
            if args.command=="stop" and alive:
                for _ in range(80):
                    if not manager_alive(home): break
                    time.sleep(.25)
            emit({"request":args.command,"manager_alive":manager_alive(home),"notice":"Gateway recovery invalidates pending consent pages; begin a fresh authorization if necessary." if args.command=="recover" else "Only the owned manager/job is stopped."})
        elif args.command=="diagnose":
            value=status(home);issues=[]
            if not value.get("manager_alive"): issues.append("MANAGER_NOT_RUNNING")
            if value.get("manager_alive") and value.get("port"): value["local_unauthenticated_mcp"]=probe(f"http://127.0.0.1:{value['port']}/mcp")
            if value.get("manager_alive") and value.get("origin"):
                value["public_unauthenticated_mcp"]=probe(value["origin"]+"/mcp")
                value["public_oauth_metadata"]=probe(value["origin"]+"/.well-known/oauth-authorization-server")
                if value["public_unauthenticated_mcp"]!=401 or value["public_oauth_metadata"]!=200:
                    issues.append("PUBLIC_TUNNEL_OR_ORIGIN_NOT_READY")
            if value.get("configuration",{}).get("result")=="INVALID_CONFIG_TOOLS_CLOSED": issues.append("INVALID_CONFIG_TOOLS_CLOSED")
            if value.get("network_errors"): issues.append("TUNNEL_NETWORK_ERRORS_REVIEW_STATUS")
            if value.get("manager_alive") and value.get("local_unauthenticated_mcp")!=401: issues.append("LOCAL_AUTH_BOUNDARY_NOT_READY")
            emit({"status":value,"issues":issues,"diagnosis":"Process/HTTP checks do not prove Grok connectivity. For partial catalogs inspect backend discovery, then refresh the client's full namespace. Never disable OAuth to recover."})
    except Exception as error:
        hint=str(error) if isinstance(error,ValueError) and re.fullmatch(r"[a-z_]{1,90}",str(error)) else "inspect_configuration_and_diagnose"
        emit({"error":type(error).__name__,"hint":hint});raise SystemExit(1) from None

if __name__=="__main__": main()
