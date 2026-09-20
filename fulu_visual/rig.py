"""Editor pose rig: no product BASE enum and no pose-specific deformation code."""
from dataclasses import dataclass
from .geometry import dimensions,bounds,mix_shape,side_shape,visible

@dataclass(frozen=True)
class Eye:
    x: float
    y: float
    rotation: float
    shape: dict
    opacity: float = 1.

@dataclass(frozen=True)
class RigFrame:
    eyes: tuple
    blend: float

class EyeRig:
    def __init__(self,config):
        self.config=config

    def pose_frame(self,pid):
        return self.shape_frame(self.config['poses'][pid]['shape'],0.)

    def shape_frame(self,shape,blend):
        import math
        x0,x1,y0,y1=bounds(shape)
        offset=shape['eye_gap']/2-x0
        y=-(y0+y1)/2
        angle=math.radians(shape['tilt'])
        eyes=[]
        for sign,side in ((-1,'left'),(1,'right')):
            own=side_shape(shape,side)
            opacity=shape.get('opacity',1.)*shape.get(side+'_opacity',1.) if visible(own) else 0.
            eyes.append(Eye(sign*offset+shape.get('position_x',0.)+shape.get(side+'_x',0.),
                            y+shape.get('position_y',0.)+shape.get(side+'_y',0.),
                            sign*angle+math.radians(shape.get('rotation',0.)+shape.get(side+'_rotation',0.)),
                            own,opacity))
        return RigFrame(tuple(eyes),blend)

    def frame_at_blend(self,blend,source=None,target=None):
        source=source or self.config['selection']['source']
        target=target or self.config['selection']['target']
        a,b=(self.config['poses'][pid]['shape'] for pid in (source,target))
        return self.shape_frame(mix_shape(a,b,max(0.,min(1.,blend))),blend)

