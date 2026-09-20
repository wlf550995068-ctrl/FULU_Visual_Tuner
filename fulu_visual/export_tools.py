"""Explicit allowlist export; never walks the parent/main project."""
from pathlib import Path
from copy import deepcopy
import json,zipfile
from .config import ROOT,DEFAULTS,save_config

def export_pose(cfg,pid,out=None):
    out=Path(out or ROOT/'exports');out.mkdir(parents=True,exist_ok=True)
    path=out/(pid+'.json')
    path.write_text(json.dumps(cfg['poses'][pid],ensure_ascii=False,indent=2),encoding='utf-8')
    return path

def export_source(out=None):
    out=Path(out or ROOT/'exports');out.mkdir(parents=True,exist_ok=True)
    path=out/'FULU_Visual_Tuner_source.zip'
    files=[]
    for name in ('simulator.py','run.cmd','README.md','requirements.txt','requirements-lock.txt',
                 '.gitignore','CONTRIBUTING.md','LICENSE_PENDING.md','verify_gpu.py','verify_upgrade.py'):
        if (ROOT/name).is_file():files.append(ROOT/name)
    for folder in ('fulu_visual','shaders','tests'):
        files.extend(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.frag','.vert','.ps1'))
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(ROOT))
        z.writestr('data/pose_library.example.json',json.dumps(DEFAULTS,ensure_ascii=False,indent=2))
    return path

