"""Authenticated loopback runtime with local atomic configuration reload."""
import argparse
import asyncio
import contextlib
import hashlib
import json
import logging
import os
from pathlib import Path
import time
import uvicorn
from .app import create_application
from .config import ConnectConfig
from .io_utils import write_json

class ConfigurationReload:
    def __init__(self,path,registry,status_path):
        self.path,self.registry,self.status_path=Path(path),registry,Path(status_path)
        self.last_hash=None;self.generation=0;self.started_at=time.time()
    def tick(self):
        try:
            data=self.path.read_bytes()
            if len(data)>262144: raise ValueError("configuration too large")
            digest=hashlib.sha256(data).hexdigest()
            if digest==self.last_hash: return
            self.last_hash=digest
            config=ConnectConfig.model_validate_json(data.decode("utf-8-sig"))
            self.registry.replace(config)
            self.generation+=1
            value={"result":"APPLIED","config_sha256":digest,"generation":self.generation,
                   "tool_count":sum(len(b.tools) for b in config.backends),"backend_count":len(config.backends)}
        except Exception as error:
            self.registry.block()
            value={"result":"INVALID_CONFIG_TOOLS_CLOSED","error_type":type(error).__name__,
                   "generation":self.generation}
        write_json(self.status_path,{**value,"pid":os.getpid(),"started_at":self.started_at,"updated_at":time.time()})
    async def watch(self):
        while True:
            self.tick()
            await asyncio.sleep(.5)

async def serve(args):
    config=ConnectConfig.model_validate_json(args.config.read_text(encoding="utf-8-sig"))
    app,_,_=create_application(config,origin=args.origin,port=args.port,state_dir=args.state,dynamic=True,
                                 secrets_dir=args.secrets_dir)
    reload=ConfigurationReload(args.config,app.registry,args.state/"reload.status.json")
    reload.tick()
    watcher=asyncio.create_task(reload.watch())
    server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=args.port,access_log=False,
                                       log_level="critical",log_config=None,proxy_headers=False))
    try:
        await server.serve()
    finally:
        watcher.cancel()
        with contextlib.suppress(asyncio.CancelledError): await watcher

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--state",type=Path,required=True)
    parser.add_argument("--secrets-dir",type=Path)
    parser.add_argument("--origin",required=True)
    parser.add_argument("--port",type=int,required=True)
    args=parser.parse_args()
    logging.basicConfig(level=logging.CRITICAL,handlers=[logging.NullHandler()],force=True)
    try: asyncio.run(serve(args))
    except KeyboardInterrupt: pass
    except Exception as error:
        print(json.dumps({"error":"runtime_failed","type":type(error).__name__}))
        raise SystemExit(1) from None

if __name__=="__main__": main()
