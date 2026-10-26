"""Build a source-only release from the same checked file whitelist."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from release_check import source_files

root = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(); p.add_argument("--output",type=Path,required=True); args = p.parse_args()
subprocess.run([sys.executable,str(root/"scripts/release_check.py")],check=True)
files,mode = source_files(root)
args.output.mkdir(parents=True,exist_ok=True)
target = args.output/"grok-local-bridge-v0.1.0-alpha.zip"
if target.exists(): raise SystemExit("Refuse to overwrite an existing release archive")
with zipfile.ZipFile(target,"x",zipfile.ZIP_DEFLATED) as z:
    for rel in sorted(files): z.write(root/rel,"grok-local-bridge/"+rel.as_posix())
sha = hashlib.sha256(target.read_bytes()).hexdigest()
manifest = {"version":"v0.1.0-alpha","experimental":True,"file":target.name,"bytes":target.stat().st_size,
            "sha256":sha,"members":len(files),"source_set":mode}
(target.parent/"RELEASE_MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
(target.parent/"SHA256SUMS.txt").write_text(sha+"  "+target.name+"\n",encoding="ascii")
print(json.dumps(manifest,indent=2))
