#!/usr/bin/env python3
"""Build a reproducible, allowlisted source bundle with per-file SHA-256 hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PACKAGE='regulatory-change-to-action'
ROOT_FILES=('README.md','require.md','requirements.txt','Makefile','.env.example','.gitignore',
            '.github/workflows/check.yml')
DIRECTORIES={
    'agent':{'.py','.json'},'scripts':{'.py'},'docs':{'.md'},
    'calibrated_v0_2':{'.json','.csv','.md'},'config':{'.json','.md'},
    'materials':{'.json','.txt','.md'},'examples':{'.md','.json'},
    'data/person1':{'.json','.csv','.md'},'data/person2':{'.json','.csv','.md'},
    'data/person3':{'.json','.csv','.md'},'data/person4':{'.json','.csv','.md'},
    'data/regulatory-governance-dataset':{'.py','.md','.yaml'},
}
RESEARCH_FILES=('market_landscape_2026-09-08.md','source_audit.md','calibration_report.md',
                'm1_implementation_2026-09-12.md')


def submission_files(root=ROOT):
    root=Path(root).resolve()
    selected={root/name for name in ROOT_FILES}
    for directory,suffixes in DIRECTORIES.items():
        selected.update(p for p in (root/directory).rglob('*') if p.is_file()
            and p.suffix in suffixes and not any(part.startswith('.') or part=='__pycache__'
                for part in p.relative_to(root).parts))
    selected.update((root/'data').glob('*.md'))
    selected.update(root/'research'/name for name in RESEARCH_FILES)
    # The validation inventory names the original inputs required for rebuilding.
    inventory=json.loads((root/'calibrated_v0_2/calibration/input_inventory.json').read_text())
    for entry in inventory:
        path=root/'data'/entry['path']
        if not path.resolve().is_relative_to(root/'data'):
            raise ValueError('Dataset inventory path leaves the data directory')
        selected.add(path)
    for path in sorted(selected):
        if not path.is_file():raise ValueError('Required submission file missing: '+str(path.relative_to(root)))
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p!=root and p.is_relative_to(root)):
            raise ValueError('Submission files must not be symlinks: '+str(path.relative_to(root)))
        if not path.resolve().is_relative_to(root):raise ValueError('Submission file leaves project root')
        relative=path.relative_to(root)
        if any(part in ('.env','.env.local','.git','.venv','runs','backups','__pycache__','dist') for part in relative.parts):
            raise ValueError('Private or generated path selected: '+str(relative))
    return sorted(selected,key=lambda p:p.relative_to(root).as_posix())


def build_submission(output,root=ROOT):
    root=Path(root).resolve();output=Path(output).resolve()
    if output.suffix!='.zip':raise ValueError('Output must be a .zip file')
    contents={p.relative_to(root).as_posix():p.read_bytes() for p in submission_files(root)}
    manifest=dict(project=PACKAGE,format_version=1,
        default_demo='python scripts/demo.py (scripted replay; synthetic scenario)',
        files={name:hashlib.sha256(data).hexdigest() for name,data in contents.items()},
        excluded=['local credentials','runtime databases and audit logs','virtual environments',
                  'development handoff/history','third-party reference PDFs'])
    contents['SUBMISSION_MANIFEST.json']=(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent,suffix='.zip',delete=False) as stream:temporary=Path(stream.name)
    try:
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for name,data in sorted(contents.items()):
                info=zipfile.ZipInfo(PACKAGE+'/'+name,date_time=(2026,9,21,0,0,0))
                info.create_system=3;info.external_attr=(stat.S_IFREG|0o644)<<16
                info.compress_type=zipfile.ZIP_DEFLATED
                archive.writestr(info,data)
        temporary.replace(output)
    finally:temporary.unlink(missing_ok=True)
    sha=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(sha+'  '+output.name+'\n',encoding='ascii')
    return dict(archive=str(output),sha256=sha,files=len(contents),bytes=output.stat().st_size)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'dist'/f'{PACKAGE}.zip')
    args=parser.parse_args()
    print(json.dumps(build_submission(args.output),indent=2))


if __name__=='__main__':main()
