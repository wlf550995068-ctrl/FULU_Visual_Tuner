"""Only QUESTION / EXCLAMATION editor primitives; no product semantics or clock."""
from copy import deepcopy
from dataclasses import dataclass
import math

from .extensions import ACCENT_REGISTRY
ELEMENT_TYPES=('NONE',*ACCENT_REGISTRY)
BASE_SIZE=.22
STROKE=.052
DOT_RADIUS=.065
DOT=(.02,-.37)
SAFE_PADDING=.008

def cubic(a,b,c,d,t):
    s=1-t
    return tuple(s*s*s*a[i]+3*s*s*t*b[i]+3*s*t*t*c[i]+t*t*t*d[i] for i in (0,1))

def make_question():
    curves=(
        ((-.26,.24),(-.27,.49),(.30,.49),(.29,.23)),
        ((.29,.23),(.29,.08),(.04,.05),(.02,-.11)),
    )
    points=[cubic(*curve,i/16) for curve in curves for i in range(16)]
    return tuple(points+[(.02,-.11),(.02,-.16)])

PATHS={'QUESTION':make_question(),'EXCLAMATION':((.02,.40),(.02,-.14))}

def local_bounds(kind,scale,rotation):
    """Exact bounds of the rendered capsule polyline + dot, including rotation."""
    # NONE retains the larger editable envelope for predictable future selection.
    if kind=='NONE':kind='QUESTION'
    angle=math.radians(rotation);c,s=math.cos(angle),math.sin(angle)
    factor=BASE_SIZE*scale
    disks=[(x,y,STROKE) for x,y in PATHS[kind]]+[(DOT[0],DOT[1],DOT_RADIUS)]
    rotated=[((c*x-s*y)*factor,(s*x+c*y)*factor,r*factor) for x,y,r in disks]
    return (min(x-r for x,y,r in rotated),max(x+r for x,y,r in rotated),
            min(y-r for x,y,r in rotated),max(y+r for x,y,r in rotated))

def clamp_accent(accent,display):
    result=deepcopy(accent)
    hx=display['design_aspect']/2-display['safe_margin']-SAFE_PADDING
    hy=.5-display['safe_margin']-SAFE_PADDING
    x0,x1,y0,y1=local_bounds(result['type'],result['scale'],result['rotation'])
    fit=min(1.,2*hx/max(1e-9,x1-x0),2*hy/max(1e-9,y1-y0))
    result['scale']*=fit
    x0,x1,y0,y1=local_bounds(result['type'],result['scale'],result['rotation'])
    result['position']['x']=min(hx-x1,max(-hx-x0,result['position']['x']))
    result['position']['y']=min(hy-y1,max(-hy-y0,result['position']['y']))
    return result

def world_bounds(accent,scale_factor=1.):
    x0,x1,y0,y1=local_bounds(accent['type'],accent['scale']*scale_factor,accent['rotation'])
    x,y=accent['position']['x'],accent['position']['y']
    return x+x0,x+x1,y+y0,y+y1

@dataclass(frozen=True)
class ElementFrame:
    kind: str
    position: tuple
    scale: float
    rotation: float
    opacity: float
    bounds: tuple

def element_frame(accent,animation=None):
    opacity,scale=animation.sample() if animation else (1.,1.)
    kind=accent['type'] if accent['enabled'] else 'NONE'
    return ElementFrame(kind,(accent['position']['x'],accent['position']['y']),
                        accent['scale']*scale,accent['rotation'],accent['opacity']*opacity,
                        world_bounds(accent,scale))

class ElementAnimation:
    """A channel cursor advanced only by the existing window frame_time."""
    def __init__(self,settings):
        self.settings=settings
        self.reset()
    @property
    def total(self):return sum(self.settings[k] for k in ('enter','hold','exit'))
    @property
    def phase(self):
        if self.editing:return 'EDIT'
        if self.cursor>=self.total:return 'DONE'
        if self.cursor<self.settings['enter']:return 'ENTER'
        if self.cursor<self.settings['enter']+self.settings['hold']:return 'HOLD'
        return 'EXIT'
    def reset(self):
        self.cursor=0.;self.paused=True;self.editing=True
    def play(self):
        self.cursor=0.;self.paused=False;self.editing=False
    def pause(self):self.paused=True
    def resume(self):
        if not self.editing and self.cursor<self.total:self.paused=False
    def advance(self,dt):
        if not math.isfinite(dt) or dt<0:raise ValueError('Invalid frame delta')
        if not self.paused and not self.editing:
            self.cursor=min(self.total,self.cursor+dt)
            if self.cursor>=self.total:self.paused=True
    def sample(self):
        def ease(t):
            t=max(0.,min(1.,t))
            return t*t*t*(10+t*(-15+6*t))
        if self.phase=='EDIT' or self.phase=='HOLD':return 1.,1.
        if self.phase=='DONE':return 0.,self.settings['exit_scale']
        if self.phase=='ENTER':
            u=ease(self.cursor/self.settings['enter'])
            return u,self.settings['enter_scale']+(1-self.settings['enter_scale'])*u
        u=ease((self.cursor-self.settings['enter']-self.settings['hold'])/self.settings['exit'])
        return 1-u,1+(self.settings['exit_scale']-1)*u

