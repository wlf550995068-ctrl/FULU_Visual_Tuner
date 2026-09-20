from .config import ROOT
from .geometry import dimensions,render_contour
import moderngl

class EyeRenderer:
    """Existing ModernGL draw path shared by editor, Inspect and automated checks."""
    def __init__(self,context,config):
        self.ctx=context
        self.program=context.program(
            vertex_shader=(ROOT/'shaders/eye.vert').read_text(encoding='utf-8-sig'),
            fragment_shader=(ROOT/'shaders/eye.frag').read_text(encoding='utf-8-sig'))
        self.vao=context.vertex_array(self.program,[])
        self.configure(config)

    def configure(self,config):
        self.config=config
        v=config['volume']
        self.program['u_volume_a'].value=tuple(v[k] for k in ('volume_depth','center_fill','bulge_influence','side_falloff'))
        self.program['u_volume_b'].value=tuple(v[k] for k in ('bottom_falloff','edge_falloff','edge_softness','surface_roundness'))
        self.program['u_design_aspect'].value=config['display']['design_aspect']
        self.program['u_safe_margin'].value=config['display']['safe_margin']

    def render(self,frame,framebuffer,show_safe=False,flat=False):
        framebuffer.use()
        width,height=framebuffer.size
        self.ctx.viewport=(0,0,width,height);self.ctx.scissor=None
        self.ctx.disable(moderngl.BLEND|moderngl.DEPTH_TEST|moderngl.CULL_FACE)
        p=self.program;p['u_resolution'].value=(width,height)
        aa=[];bb=[];cc=[];contours=[];counts=[];weights=[]
        for e in frame.eyes:
            s=e.shape;a,b,r,k,comp=dimensions(s)
            points=render_contour(s);counts.append(len(points));weights.append(s.get('contour_mix',1.) if points else 0.)
            contours.extend([tuple(point) for point in points]+[(0.,0.)]*(64-len(points)))
            aa.append((e.x,e.y,a,b))
            bb.append((r,k,s['top_curve']*(1-s['squash']),s['bottom_curve']*(1-s['squash'])))
            cc.append((e.rotation,s['center_bulge'],s['end_taper'],comp))
        p['u_eye_a'].value=aa;p['u_eye_b'].value=bb;p['u_eye_c'].value=cc
        p['u_contour'].value=contours;p['u_contour_count'].value=tuple(counts);p['u_contour_mix'].value=tuple(weights)
        p['u_eye_opacity'].value=tuple(e.opacity for e in frame.eyes)
        p['u_show_safe'].value=show_safe;p['u_flat'].value=flat
        self.vao.render(mode=moderngl.TRIANGLES,vertices=3)

    def release(self):
        self.vao.release();self.program.release()

