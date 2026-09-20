"""One independent vector/SDF overlay pass; composed after the unchanged EyeRenderer."""
import math
import moderngl
from .config import ROOT
from .visual_elements import PATHS,BASE_SIZE,STROKE,DOT,DOT_RADIUS

class VisualElementRenderer:
    def __init__(self,ctx):
        self.ctx=ctx
        self.program=ctx.program(
            vertex_shader=(ROOT/'shaders/eye.vert').read_text(encoding='utf-8-sig'),
            fragment_shader=(ROOT/'shaders/visual_element.frag').read_text(encoding='utf-8-sig'))
        self.vao=ctx.vertex_array(self.program,[])
    def render(self,frame,framebuffer,display,show_bounds=False):
        if frame.kind=='NONE' or frame.opacity<=0 or frame.scale<=0:return
        framebuffer.use()
        self.ctx.viewport=(0,0,*framebuffer.size);self.ctx.scissor=None
        p=self.program
        p['u_resolution'].value=framebuffer.size
        p['u_design_aspect'].value=display['design_aspect']
        p['u_safe_margin'].value=display['safe_margin']
        p['u_position'].value=frame.position
        p['u_scale'].value=BASE_SIZE*frame.scale
        p['u_rotation'].value=math.radians(frame.rotation)
        p['u_opacity'].value=frame.opacity
        points=PATHS[frame.kind]
        p['u_points'].value=points+(points[-1],)*(40-len(points))
        p['u_count'].value=len(points)
        p['u_stroke'].value=STROKE
        p['u_dot'].value=(*DOT,DOT_RADIUS)
        p['u_color'].value=(.62,.80,.90)
        p['u_bounds'].value=frame.bounds
        p['u_show_bounds'].value=show_bounds
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func=(moderngl.SRC_ALPHA,moderngl.ONE_MINUS_SRC_ALPHA,
                             moderngl.ONE,moderngl.ONE_MINUS_SRC_ALPHA)
        self.vao.render(mode=moderngl.TRIANGLES,vertices=3)
        self.ctx.disable(moderngl.BLEND)
    def release(self):
        self.vao.release();self.program.release()

