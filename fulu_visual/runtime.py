"""Standalone semantic-trigger test layer. It never imports the main robot systems."""
from copy import deepcopy
from dataclasses import replace
import math
from .geometry import mix_shape,bounds
from .config import validate_shape
from .rig import EyeRig,RigFrame

TRIGGERS={'Wake':'NORMAL'}
GAZE_ENTER=.22
GAZE_HOLD=.75
GAZE_RETURN=.55
GAZE_AMPLITUDE=.12
SHAKE_DURATION=.55

def ease(t):
    t=max(0.,min(1.,t));return t*t*t*(10+t*(-15+6*t))

class VisualRuntime:
    def __init__(self,cfg,start='normal',initial=None):
        self.cfg=cfg;self.current=deepcopy(initial or cfg['poses'][start]['shape'])
        self.start=deepcopy(self.current);self.target_shape=deepcopy(self.current)
        self.target=start;self.progress=1.;self.elapsed=0.;self.total_time=0.
        self.duration=1.;self.paused=False;self.gaze=0.;self.log=[]
        self.gaze_start=0.;self.gaze_target=0.;self.gaze_elapsed=GAZE_ENTER+GAZE_HOLD+GAZE_RETURN;self.centering=False;self.shake_elapsed=SHAKE_DURATION
    def configure(self,cfg):self.cfg=cfg
    def resolve(self,semantic):
        semantic=semantic.upper()
        if 'ROOT' in semantic or semantic.startswith('VERY_'):raise ValueError('Root / VERY_* 不是运行时 Pose')
        for pid,p in self.cfg['poses'].items():
            if not p.get('archived') and (p['name'].upper()==semantic or p.get('metadata',{}).get('semantic')==semantic):
                return pid
        raise ValueError('尚未创建 '+semantic+'；请先 Auto Derive 或加载这个 Pose')
    def retarget(self,pid):
        if self.cfg['poses'][pid].get('archived'):raise ValueError('归档记录不能进入运行时')
        target=deepcopy(self.cfg['poses'][pid]['shape'])
        for i in range(101):validate_shape(mix_shape(self.current,target,i/100),self.cfg['display'])
        self.start=deepcopy(self.current);self.target_shape=target;self.target=pid
        self.elapsed=0.;self.progress=0.
        response=self.cfg['motion']['return_response' if pid=='normal' else 'enter_response']
        self.duration=6.64/response;self.paused=False
    def dispatch(self,event):
        # UI passes event labels only, never geometry, durations, easing or RGB.
        if event in ('Look Left','Look Right','Center'):
            self.gaze_start=self.gaze;self.gaze_target=0. if event=='Center' else -1. if event=='Look Left' else 1.
            self.gaze_elapsed=0.;self.centering=event=='Center';self.paused=False
        elif event=='Shake':self.shake_elapsed=0.;self.paused=False
        elif event in ('Touch','Pet','Person Detected'):raise ValueError('此测试事件已移除')
        else:
            semantic=TRIGGERS.get(event,'NORMAL' if event=='Return' else event.removeprefix('Semantic '))
            self.retarget(self.resolve(semantic))
        self.log.append(event);self.log=self.log[-12:]
    def advance(self,dt):
        if not math.isfinite(dt) or dt<0:raise ValueError('Invalid delta')
        if self.paused:return
        self.total_time+=dt
        self.gaze_elapsed+=dt;self.shake_elapsed=min(SHAKE_DURATION,self.shake_elapsed+dt)
        t=self.gaze_elapsed
        if self.centering:self.gaze=self.gaze_start*(1-ease(t/GAZE_RETURN))
        elif t<GAZE_ENTER:self.gaze=self.gaze_start+(self.gaze_target-self.gaze_start)*ease(t/GAZE_ENTER)
        elif t<GAZE_ENTER+GAZE_HOLD:self.gaze=self.gaze_target
        else:self.gaze=self.gaze_target*(1-ease((t-GAZE_ENTER-GAZE_HOLD)/GAZE_RETURN))
        self.elapsed=min(self.duration,self.elapsed+dt)
        self.progress=self.elapsed/self.duration
        t=self.progress;s=t*t*t*(10+t*(-15+6*t))
        self.current=mix_shape(self.start,self.target_shape,s)
    def frame(self):
        frame=EyeRig(self.cfg).shape_frame(self.current,self.progress)
        rt=self.cfg['runtime']
        dx=self.gaze*GAZE_AMPLITUDE;dy=0.
        if self.shake_elapsed<SHAKE_DURATION:
            t=self.shake_elapsed/SHAKE_DURATION;dx+=.025*math.sin(t*math.tau*3)*math.sin(t*math.pi)**2
        if rt['idle_enabled']:
            dx+=rt['idle_amplitude']*math.sin(self.total_time*math.tau*rt['idle_hz'])
            dy=rt['idle_amplitude']*.6*math.sin(self.total_time*math.tau*rt['idle_hz']*.73)
        x0,x1,y0,y1=bounds(self.current);margin=self.cfg['display']['safe_margin']
        outer=max(abs(e.x)+max(abs(x0),abs(x1)) for e in frame.eyes)
        roomx=max(0.,self.cfg['display']['design_aspect']/2-margin-outer)
        roomy=max(0.,.5-margin-(y1-y0)/2)
        dx=max(-roomx,min(roomx,dx));dy=max(-roomy,min(roomy,dy))
        return RigFrame(tuple(replace(e,x=e.x+dx,y=e.y+dy) for e in frame.eyes),frame.blend)

