"""Disabled extension seams only. No plugin is auto-loaded or rendered."""
from dataclasses import dataclass
from typing import Protocol
EYE_EXTENSION_DEFAULTS={name:False for name in ('Brow','Eyelash','Pupil','Iris','Highlight','Style','Realism')}

class EyeExtension(Protocol):
    name: str
    def evaluate(self,eye,frame_time): ...

class AccentPlugin(Protocol):
    name: str
    def validate(self,parameters): ...
    def render(self,renderer,frame,parameters): ...

@dataclass(frozen=True)
class AccentEntry:
    name: str
    status: str='Experimental / Unverified'
    source: str='builtin_sdf'

ACCENT_REGISTRY={name:AccentEntry(name) for name in ('QUESTION','EXCLAMATION')}

def import_accent_manifest(manifest):
    """Validate import metadata only; no code execution, install or UI additions."""
    if not isinstance(manifest,dict) or set(manifest)!={'name','version','kind'}:raise ValueError('Invalid accent manifest')
    if not isinstance(manifest['name'],str) or not manifest['name'].strip() or len(manifest['name'])>64:raise ValueError('Invalid name')
    if manifest['kind']!='vector_plugin' or manifest['version']!=1:raise ValueError('Unsupported import interface')
    return dict(manifest,status='Experimental / Unverified',enabled=False)
