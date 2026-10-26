"""Run the packaged synthetic fixture; never a real Hub."""
import runpy
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))
runpy.run_module("grok_local_bridge.demo_server",run_name="__main__")
