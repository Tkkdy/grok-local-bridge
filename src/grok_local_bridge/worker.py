"""Join the owner's job BEFORE starting a runtime or external child process."""
import argparse
import json
import runpy
import subprocess
import sys
from .processes import join_job

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--job",required=True)
    parser.add_argument("kind",choices=["runtime","exec"]);parser.add_argument("rest",nargs=argparse.REMAINDER)
    args=parser.parse_args()
    try:
        join_job(args.job)
        if args.kind=="runtime":
            sys.argv=["grok_local_bridge.runtime",*args.rest]
            runpy.run_module("grok_local_bridge.runtime",run_name="__main__")
        else:
            child=subprocess.Popen(args.rest,stdin=subprocess.DEVNULL)
            raise SystemExit(child.wait())
    except SystemExit: raise
    except Exception as error:
        print(json.dumps({"worker_error_type":type(error).__name__,"os_error":getattr(error,"errno",None)}),flush=True)
        raise SystemExit(1) from None

if __name__=="__main__": main()
