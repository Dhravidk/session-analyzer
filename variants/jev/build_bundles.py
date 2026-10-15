#!/usr/bin/env python3
"""Freeze both variants with byte-identical baseline code; never package logs or keys."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def collect(root, names):
    files = {}
    for name in names:
        path = root / name
        if not path.exists():
            continue
        paths = sorted(path.rglob("*")) if path.is_dir() else [path]
        for p in paths:
            if p.is_file() and not p.is_symlink() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".pyo"):
                files[p.relative_to(root).as_posix()] = p.read_bytes()
    return files


def build(output):
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError("Choose a new output directory")
    common = collect(ROOT, ["ally_analyzer"])
    if "ally_analyzer/report.html" not in common:
        raise ValueError("Baseline report is not built yet")
    a = {**common, **collect(ROOT, [".claude-plugin", ".mcp.json", "skills", "bin", "pyproject.toml", "README.md"])}
    b = {**common, **collect(HERE, [".claude-plugin", ".mcp.json", "plugin.json", "mcp.json", "skills", "run.py", "ally_analyzer_jev", "config.example.json", "README.md"])}
    starts = {
        "A": "From this directory: python3 -m ally_analyzer run /path/to/session.log --output /path/to/A.html\nClaude Code: claude --plugin-dir /absolute/path/to/this-directory\n",
        "B": "From this directory: python3 run.py compare /path/to/session.log --output /path/to/new-comparison --config config.example.json\nThis prepares reports locally. Add --live after setting TYPESAFE_API_KEY to request real Jev judgments.\nClaude Code: set TYPESAFE_API_KEY, ALLY_JEV_ENABLED=1 and ALLY_JEV_CONFIG=/absolute/path/to/config.example.json in the launching environment, then claude --plugin-dir /absolute/path/to/this-directory\n",
    }
    output.mkdir(parents=True, mode=0o700)
    artifacts = {}
    for variant, name, files in (("A","ally-session-analyzer",a),("B","ally-session-analyzer-jev",b)):
        files["START_HERE.txt"] = starts[variant].encode()
        destination = output / (name + ".zip")
        with zipfile.ZipFile(destination,"x",zipfile.ZIP_DEFLATED) as archive:
            for path, data in sorted(files.items()):
                info = zipfile.ZipInfo(name + "/" + path, date_time=(2026,10,13,0,0,0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info,data)
        artifacts[variant] = {"path": str(destination), "sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}
    manifest = {"variants":artifacts,"baseline_files_identical":True,
                "baseline_files_sha256":{p:hashlib.sha256(data).hexdigest() for p,data in common.items()},
                "note":"Both archives contain the same captured baseline bytes. Rebuild together after baseline changes. No source logs, API credentials, stores or results are included."}
    (output / "manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return manifest


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",required=True)
    print(json.dumps(build(p.parse_args().output),indent=2))
