"""Check the exact publishable source set; never print matched secret values."""
from __future__ import annotations
import argparse
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib

SKIP = {".git", ".venv", ".runtime", ".build", ".pytest_cache", "__pycache__", "work", "build", "dist", "tools"}
FORBIDDEN = {".git", ".venv", ".runtime", ".build", "state", "work", "__pycache__", "node_modules"}
PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_credential": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    "private_windows_path": re.compile(r"[A-Za-z]:[\\/]Users[\\/](?!Public\b|example\b|<)[^\s\"<>\\/]+", re.I),
    "private_unix_path": re.compile(r"/(?:home|Users)/[A-Za-z][\w.-]+"),
    "real_quick_tunnel": re.compile(r"https://(?!synthetic-owned-fixture\b)[a-z0-9-]+\.trycloudflare\.com", re.I),
    "credential_literal": re.compile(r"(?i)(?:access_token|refresh_token|api_key|client_secret|password|cookie)\s*[=:]\s*[\"']([A-Za-z0-9_./+=-]{24,})[\"']"),
}

def source_files(root):
    check = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, text=True)
    if check.returncode == 0 and Path(check.stdout.strip()).resolve() == root.resolve():
        names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
        return [Path(n) for n in names if n], "git-tracked"
    files = []
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.endswith(".egg-info")]
        files.extend((Path(folder) / n).relative_to(root) for n in names)
    return files, "source-tree-excluding-local-artifacts"

def scan(root, files):
    issues = []
    for rel in files:
        path = root / rel
        if path.is_symlink() or not path.is_file():
            issues.append({"file": rel.as_posix(), "kind": "not_regular_file"}); continue
        if (set(rel.parts) & FORBIDDEN or path.name.startswith(".env") or
            path.suffix.lower() in {".dpapi", ".db", ".sqlite", ".sqlite3", ".pem", ".key", ".exe", ".log", ".jsonl"}):
            issues.append({"file": rel.as_posix(), "kind": "forbidden_artifact"}); continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError:
            issues.append({"file": rel.as_posix(), "kind": "unexpected_binary"}); continue
        if any(ord(c) < 32 and c not in "\n\r\t" for c in text):
            issues.append({"file": rel.as_posix(), "kind": "control_character"})
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                if kind == "credential_literal" and "SYNTHETIC" in match.group().upper():
                    continue
                issues.append({"file": rel.as_posix(), "line": text.count("\n", 0, match.start()) + 1, "kind": kind})
        if path.suffix == ".py":
            try: ast.parse(text, filename=rel.as_posix())
            except SyntaxError: issues.append({"file":rel.as_posix(), "kind":"python_syntax"})
        if path.suffix == ".md":
            for target in re.findall(r"\]\(([^)]+)\)", text):
                target = target.split("#", 1)[0]
                if not target or "://" in target: continue
                if not (path.parent / target).exists():
                    issues.append({"file":rel.as_posix(), "kind":"broken_local_link", "target":target})
    return issues

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(); root = args.root.resolve(); files, mode = source_files(root)
    issues = scan(root, files)
    if mode == "git-tracked":
        dirty = subprocess.run(["git","diff","--quiet"],cwd=root)
        if dirty.returncode:
            issues.append({"file":"<worktree>","kind":"unstaged_changes_stage_and_review_before_release"})
    required = {"README.md", "README_EN.md", "LICENSE", "SKILL.md", "SECURITY.md", "THIRD_PARTY_NOTICES.md", "pyproject.toml"}
    issues.extend({"file": n, "kind": "missing_release_file"} for n in sorted(required - {p.as_posix() for p in files}))
    if (root / "pyproject.toml").exists():
        version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        if version != "0.1.1a0": issues.append({"file":"pyproject.toml", "kind":"wrong_version"})
    print(json.dumps({"result":"FAIL" if issues else "PASS", "mode":mode, "files":len(files), "issues":issues,
                      "limits":"Pattern scan of publishable files; not proof against all secrets, not a full dependency vulnerability audit."}, indent=2))
    return int(bool(issues))

if __name__ == "__main__": sys.exit(main())
