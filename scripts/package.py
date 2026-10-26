"""Build a commit-identified source release; never overwrite existing artifacts."""
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
if mode != "git-tracked":
    raise SystemExit("Build candidates from a clean Git checkout to identify their exact source commit")
if subprocess.check_output(["git","status","--porcelain"],cwd=root).strip():
    raise SystemExit("Commit reviewed source before packaging; working tree must be clean")
commit = subprocess.check_output(["git","rev-parse","HEAD"],cwd=root,text=True).strip()
tree = subprocess.check_output(["git","rev-parse","HEAD^{tree}"],cwd=root,text=True).strip()
args.output.mkdir(parents=True,exist_ok=True)
target = args.output/"grok-local-bridge-v0.1.1-alpha.zip"
if any((args.output/name).exists() for name in (target.name,"RELEASE_MANIFEST.json","SHA256SUMS.txt")):
    raise SystemExit("Refuse to overwrite existing release artifacts")
archive = subprocess.check_output(["git","archive","--format=zip","--prefix=grok-local-bridge/","HEAD"],cwd=root)
with target.open("xb") as output:
    output.write(archive)
with zipfile.ZipFile(target) as zipped:
    members = [name for name in zipped.namelist() if not name.endswith("/")]
    if set(members) != {"grok-local-bridge/"+rel.as_posix() for rel in files}:
        raise SystemExit("Archive differs from reviewed whitelist")
sha = hashlib.sha256(archive).hexdigest()
manifest = {"version":"v0.1.1-alpha","experimental":True,"file":target.name,"bytes":len(archive),
            "sha256":sha,"members":len(members),"source_set":mode,
            "source_commit":commit,"source_tree":tree}
(target.parent/"RELEASE_MANIFEST.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
(target.parent/"SHA256SUMS.txt").write_text(sha+"  "+target.name+"\n",encoding="ascii")
print(json.dumps(manifest,indent=2))
