#!/usr/bin/env python3
"""Package only distributable implementation files, never private test stores."""
import hashlib
import argparse
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent


def build_archive(destination=None):
    version=json.loads((ROOT/'.claude-plugin/plugin.json').read_text())['version']
    files=[ROOT/'.claude-plugin/plugin.json',ROOT/'.mcp.json',ROOT/'docs/plugin-readme.md',ROOT/'pyproject.toml',
           ROOT/'bin/ally-session',ROOT/'scripts/ally-session.py']
    files += [ROOT/'docs'/name for name in ('investigation-evaluation.md','writing-quality.md','implementation-status.md','validation.md',
                                           'single-session-usage.md','single-session-investigation-spec.md','session-analyzer-product-design.md',
                                           'claude-session-analyzer-spec.md','decisions/0001-session-evidence-graph.md',
                                           'system-overview.md','session-analyzer-system.mmd','release-audit-0.10.3.md',
                                           'release-audit-0.10.4.md','release-audit-0.11.0.md','release-audit-0.12.0.md','developer-usefulness-audit-2026-10-15.md')]
    files+=list((ROOT/'ally_analyzer').glob('*.py'))+[ROOT/'ally_analyzer'/name for name in ('report.html','session_report.css','session_report.js','session_library.html','session_library.css','session_library.js')]
    files+=list((ROOT/'skills').glob('*/SKILL.md'))
    files+=list((ROOT/'ally_analyzer/icons').glob('*'))
    destination=Path(destination) if destination else ROOT/'dist'/('ally-session-analyzer-'+version+'.zip')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            member='README.md' if path==ROOT/'docs/plugin-readme.md' else path.relative_to(ROOT).as_posix()
            info=zipfile.ZipInfo(member,date_time=(2026,1,1,0,0,0))
            info.external_attr=((0o100755 if member=='bin/ally-session' else 0o100644)<<16)
            info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,path.read_bytes())
    return {'path':str(destination.resolve()),'files':len(files),'bytes':destination.stat().st_size,
            'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'private_sources_included':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='ZIP destination; defaults to dist/<name>-<version>.zip')
    args=parser.parse_args()
    print(json.dumps(build_archive(args.output),indent=2))


if __name__=='__main__':main()
