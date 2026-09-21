"""Standalone GPU Pose Editor. Editor records are not product BASE definitions."""
from collections import deque
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path

import moderngl
import moderngl_window as mglw
from moderngl_window.integrations.imgui_bundle import ModernglWindowRenderer
from imgui_bundle import imgui
from PIL import Image

from fulu_visual.config import (ROOT, SHAPE_PARAMETERS, VOLUME_PARAMETERS, MOTION_PARAMETERS,
                                ACCENT_PARAMETERS,ACCENT_ANIMATIONS,
                                load_config, save_config, validate_pair, TuningSession)
from fulu_visual.visual_elements import ELEMENT_TYPES,ElementAnimation,element_frame,clamp_accent,world_bounds
from fulu_visual.element_renderer import VisualElementRenderer
from fulu_visual.rig import EyeRig
from fulu_visual.motion import MotionPlayer
from fulu_visual.renderer import EyeRenderer
from fulu_visual.frame_timer import FrameTimer
from fulu_visual.geometry import EYE_DEFAULTS
from fulu_visual.tuner_extensions import WorkbenchExtensions

CONFIG=load_config()
V=imgui.ImVec2

class Simulator(WorkbenchExtensions,mglw.WindowConfig):
    gl_version=(3,3)
    window_size=(CONFIG['display']['width'],CONFIG['display']['height'])
    aspect_ratio=None
    resizable=True
    vsync=CONFIG['display']['vsync']
    samples=0
    title='FULU Visual Tuner | Pose Editor'

    @classmethod
    def add_arguments(cls,parser):
        parser.add_argument('--smoke-seconds',type=float,default=0)
        parser.add_argument('--benchmark-seconds',type=float,default=0)
        parser.add_argument('--accent-smoke',action='store_true')
        parser.add_argument('--upgrade-smoke',action='store_true')
        parser.add_argument('--input-smoke',action='store_true')

    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        path=ROOT/('test_output/upgrade/smoke_library.json' if self.argv.upgrade_smoke else 'test_output/accent/smoke_library.json' if self.argv.accent_smoke else 'test_output/pose_editor/smoke_library.json') if self.argv.smoke_seconds else None
        initial=deepcopy(CONFIG)
        if self.argv.smoke_seconds and not self.argv.upgrade_smoke:
            from fulu_visual.config import DEFAULTS
            initial=deepcopy(DEFAULTS)
        if path:save_config(initial,path)
        self.session=TuningSession(initial,path)
        self.smoke_initial=deepcopy(initial)
        self.rig=EyeRig(self.cfg)
        self.renderer=EyeRenderer(self.ctx,self.cfg)
        self.element_renderer=VisualElementRenderer(self.ctx)
        self.accent_animation=ElementAnimation(ACCENT_ANIMATIONS[self.cfg['accent']['animation']])
        self.accent_drag=None
        self.player=MotionPlayer(self.cfg['motion'])
        self.mode='edit'
        if self.argv.benchmark_seconds:
            self.mode='ab';self.player.play()
        self.flat=False
        self.show_safe=False
        self.clean=False
        self.status='先选择 Pose，再调整 Shape。保存 Pose 与保存工作台分别独立。'
        self.error=False
        self.recent=deque(maxlen=120)
        self.measured=[]
        self.ui_rects={}
        self.events=[]
        self.smoke_done=set()
        self.capture_requested=False
        self.close_requested=False
        self.dialog_request=None
        self.dialog_kind=None
        self.dialog_pose=None
        self.name_buffer=''
        self.held_keys=set()
        self.exit_dialog_visible=False
        self.autoplay_samples=[]
        imgui.create_context()
        io=imgui.get_io()
        io.set_ini_filename('')
        font=Path('C:/Windows/Fonts/msyh.ttc')
        if not font.exists():raise RuntimeError('Microsoft YaHei font is required')
        # Use full CJK range so newly named custom poses also render correctly.
        io.fonts.add_font_from_file_ttf(str(font),18,glyph_ranges_as_int_list=[32,0xFFFD,0])
        self.gui=ModernglWindowRenderer(self.wnd)
        self.gui.REVERSE_KEYMAP.update({getattr(self.wnd.keys,c):getattr(imgui.Key,c.lower()) for c in 'ACVXYZ'})
        # This renderer backend does not install clipboard callbacks itself.
        # Reuse the existing native window clipboard for shortcuts and context menus.
        platform=imgui.get_platform_io()
        self.clipboard_get=lambda context:self.wnd._window.get_clipboard_text()
        self.clipboard_set=lambda context,text:self.wnd._window.set_clipboard_text(text)
        platform.platform_get_clipboard_text_fn=self.clipboard_get
        platform.platform_set_clipboard_text_fn=self.clipboard_set
        self.wnd.exit_key=None
        self.wnd._window.set_minimum_size(1180,820)
        self.setup_style()
        self.texture=None
        self.canvas=None
        self.ensure_canvas((960,540))
        self.active_panel="shape"
        self.setup_extensions()
        if self.argv.smoke_seconds and not self.argv.upgrade_smoke:self.active_panel='shape'
        self.wnd._window.push_handlers(on_close=self.native_close_request)
        print('GPU:',self.ctx.info['GL_RENDERER'],flush=True)
        print('SPACE play/pause | P pause/resume | RIGHT step | V inspect | ESC exit inspect',flush=True)

    @property
    def cfg(self):return self.session.config
    @property
    def selected(self):return self.cfg['selection']['selected']

    def setup_style(self):
        imgui.style_colors_dark()
        s=imgui.get_style()
        s.window_rounding=10;s.frame_rounding=5;s.grab_rounding=5
        s.window_padding=V(16,12);s.frame_padding=V(8,4);s.item_spacing=V(8,5)
        s.window_border_size=0
        for key,value in {
            imgui.Col_.window_bg:(.055,.067,.086,1),imgui.Col_.text:(.88,.92,.96,1),
            imgui.Col_.text_disabled:(.44,.52,.61,1),imgui.Col_.frame_bg:(.10,.13,.17,1),
            imgui.Col_.button:(.10,.18,.23,1),imgui.Col_.button_hovered:(.14,.28,.34,1),
            imgui.Col_.slider_grab:(.28,.68,.79,1),imgui.Col_.check_mark:(.35,.78,.86,1)
        }.items():s.set_color_(key,imgui.ImVec4(*value))

    def sync(self):
        self.rig.config=self.cfg
        self.renderer.configure(self.cfg)
        self.player.reconfigure(self.cfg['motion'])
        self.accent_animation.settings=ACCENT_ANIMATIONS[self.cfg['accent']['animation']]
        if hasattr(self,'runtime'):self.sync_extensions()
        if self.mode=='ab':
            try:validate_pair(self.cfg,self.cfg['selection']['source'],self.cfg['selection']['target'])
            except ValueError:
                self.mode='edit';self.player.pause()
                raise

    def attempt(self,fn,message='已更新。'):
        try:
            fn();self.sync();self.status=message;self.error=False
            return True
        except (ValueError,OSError,KeyError,TypeError) as exc:
            self.status=str(exc);self.error=True
            return False

    def ensure_canvas(self,size):
        size=tuple(max(64,int(x)) for x in size)
        if self.canvas is not None and self.canvas.size==size:return
        if self.canvas:
            self.gui.remove_texture(self.texture);self.canvas.release();self.texture.release()
        self.texture=self.ctx.texture(size,3)
        self.texture.filter=(moderngl.LINEAR,moderngl.LINEAR)
        self.canvas=self.ctx.framebuffer(color_attachments=[self.texture])
        self.gui.register_texture(self.texture)

    def panel(self,name,x,y,w,h):
        imgui.set_next_window_pos(V(x,y));imgui.set_next_window_size(V(w,h))
        flags=imgui.WindowFlags_.no_title_bar|imgui.WindowFlags_.no_resize|imgui.WindowFlags_.no_move|imgui.WindowFlags_.no_saved_settings
        imgui.begin(name,flags=flags)

    def remember_rect(self,name):
        a,b=imgui.get_item_rect_min(),imgui.get_item_rect_max()
        self.ui_rects[name]=(a.x,a.y,b.x,b.y)

    def button(self,label,name=None,width=0):
        clicked=imgui.button(label,V(width,29))
        if name:self.remember_rect(name)
        return clicked

    def choose_pose(self,pid):
        self.session.end_gesture()
        self.cfg['selection']['selected']=pid
        self.mode='edit';self.player.pause()
        self.status='编辑 '+self.cfg['poses'][pid]['name']+' 的独立形状。'

    def set_pair(self,key,pid):
        candidate=deepcopy(self.cfg);candidate['selection'][key]=pid
        validate_pair(candidate,candidate['selection']['source'],candidate['selection']['target'])
        self.session.commit(candidate)
        self.mode='ab';self.player.seek(0)

    def toggle_play(self):
        validate_pair(self.cfg,self.cfg['selection']['source'],self.cfg['selection']['target'])
        self.mode='ab';self.player.toggle()

    def step(self):
        validate_pair(self.cfg,self.cfg['selection']['source'],self.cfg['selection']['target'])
        self.mode='ab';self.player.pause()
        self.player.advance(self.cfg['motion']['single_step_seconds'],force=True)

    def scrub(self,pos):
        validate_pair(self.cfg,self.cfg['selection']['source'],self.cfg['selection']['target'])
        self.mode='ab';self.player.seek(pos)

    def pose_combo(self,label,key):
        ids=[pid for pid,p in self.cfg['poses'].items() if not p.get('archived')];names=[self.cfg['poses'][pid]['name'] for pid in ids]
        changed,index=imgui.combo(label,ids.index(self.cfg['selection'][key]),names)
        if changed:
            if key=='selected':self.choose_pose(ids[index])
            else:self.attempt(lambda:self.set_pair(key,ids[index]))

    def edit_slider(self,section,key,label,low,high,fmt):
        target=self.cfg
        for part in section.split('.'):target=target[part]
        imgui.text(label);imgui.set_next_item_width(-1)
        changed,value=imgui.slider_float('##'+section+key,float(target.get(key,EYE_DEFAULTS.get(key,0.))),low,high,fmt,
                                          flags=imgui.SliderFlags_.always_clamp)
        self.remember_rect(key)
        if imgui.is_item_activated():self.session.begin_gesture()
        if changed:
            self.session.begin_gesture()
            def apply():
                candidate=deepcopy(self.cfg);node=candidate
                for part in section.split('.'):node=node[part]
                node[key]=value
                if section.startswith('accent'):
                    candidate['accent']=clamp_accent(candidate['accent'],candidate['display'])
                # Validate the full transition while editing either endpoint.
                from fulu_visual.config import validate_config
                validate_config(candidate)
                if self.mode=='ab':
                    validate_pair(candidate,candidate['selection']['source'],candidate['selection']['target'])
                self.session.config=candidate
            self.attempt(apply,'实时预览已更新；S 保存整个工作台。')
        if imgui.is_item_deactivated():self.session.end_gesture()

    def build_ui(self,fps):
        self.text_menu_open=False
        w,h=self.wnd.size
        if self.clean:
            self.panel('inspect',0,0,w,h)
            if self.button('退出 Inspect  V / ESC','exit-inspect'):self.clean=False
            imgui.same_line();imgui.text(f'INSPECT   {fps:.1f} FPS')
            avail=imgui.get_content_region_avail();self.draw_canvas(avail.x,avail.y)
            imgui.end()
            return
        self.panel('header',12,10,w-24,73)
        imgui.text_colored(imgui.ImVec4(.44,.83,.91,1),'FULU  /  POSE EDITOR')
        imgui.same_line();imgui.text_disabled('   独立形状 · 体积 · 运动工作台')
        imgui.same_line();imgui.text(f'    {fps:5.1f} FPS')
        imgui.text_disabled('GPU / GLSL     '+('● 未保存' if self.session.dirty else '已保存')+'    中性光感 / 待肉眼验收')
        imgui.end()
        side=400;left=w-side-42
        preview_h=h-375
        self.panel('preview',12,94,left,preview_h)
        imgui.text('实时预览  /  '+(self.cfg['poses'][self.selected]['name'] if self.mode=='edit' else self.player.phase))
        imgui.same_line()
        if self.button('检视 Inspect V','inspect'):self.clean=True
        avail=imgui.get_content_region_avail();self.draw_canvas(avail.x,avail.y)
        imgui.end()

        self.panel('motion',12,104+preview_h,left,249)
        imgui.text_colored(imgui.ImVec4(.44,.83,.91,1),'MOTION  /  任意 A ↔ B')
        imgui.set_next_item_width(195);self.pose_combo('Source A','source')
        imgui.same_line();imgui.set_next_item_width(195);self.pose_combo('Target B','target')
        if self.button('往返播放 Play  SPACE' if self.player.paused else '暂停 Pause  SPACE','play'):
            self.attempt(self.toggle_play,'播放状态已更新。')
        imgui.same_line()
        if self.button('小步 →','step'):self.attempt(self.step)
        imgui.set_next_item_width(-1)
        changed,pos=imgui.slider_float('##timeline',self.player.progress,0.,1.,'A → B → A  %.3f')
        self.remember_rect('scrub')
        if changed:
            self.attempt(lambda:self.scrub(pos),'时间轴已暂停在所选位置。')
        imgui.text_disabled(f'{self.player.cursor:.2f} s  /  {self.player.period:.2f} s   |   {self.player.phase}   |   Blend {self.player.blend:.3f}')
        imgui.text_disabled('拖动即暂停；继续从当前位置播放。响应越大越快。')
        imgui.end()

        self.panel('editor',left+24,94,side,h-116)
        imgui.text_colored(imgui.ImVec4(.44,.83,.91,1),'姿态库 Pose Library')
        imgui.set_next_item_width(-105);self.pose_combo('当前编辑','selected')
        for idx,(label,kind) in enumerate((('新建','new'),('复制','copy'),('重命名','rename'),('删除','delete'))):
            if idx:imgui.same_line()
            protected=(kind=='rename' and self.selected=='normal') or (kind=='delete' and self.cfg['poses'][self.selected]['builtin'])
            if protected:imgui.begin_disabled()
            if self.button(label,kind):self.open_dialog(kind)
            if protected:imgui.end_disabled()
        if self.button('保存此 Pose','save-pose'):self.attempt(lambda:self.session.save_pose(self.selected),'当前 Pose 已单独保存。')
        imgui.same_line()
        if self.button('加载此 Pose','load-pose'):self.open_dialog('load')
        imgui.text_disabled('NORMAL 受保护；自定义 Pose 不新增产品 BASE。')
        imgui.separator()
        sections=[('shape','形状 Shape'),('volume','体积 Volume'),('light','光感 Light'),
                  ('motion','运动 Motion'),('accent','辅助元素 Accent'),('reference','参考图 Reference'),
                  ('runtime','实时触发 Runtime'),('inspect','检视 Inspect')]
        requested=getattr(self,'request_tab',None)
        if requested in [k for k,v in sections]:
            self.active_panel=requested;self.request_tab=None
        changed,index=imgui.combo('编辑分区',[k for k,v in sections].index(self.active_panel),[v for k,v in sections])
        if changed:self.active_panel=sections[index][0]
        tag=self.active_panel
        if tag in ('reference','runtime'):
            self.build_extension_panel(tag)
        elif tag=='accent':self.build_accent_ui()
        elif tag=='inspect':
            imgui.text('检视 Inspect')
            _,self.flat=imgui.checkbox('F  纯轮廓 / 平面检查',self.flat)
            _,self.show_safe=imgui.checkbox('G  安全区参考线',self.show_safe)
            imgui.text_wrapped('V 进入 / 退出；Inspect 内 ESC 返回工作台。参考图在 REFERENCE 分区。')
            if self.button('截图 F12'):self.capture_requested=True
        else:
            group='volume' if tag=='light' else tag
            definitions={'shape':SHAPE_PARAMETERS,'volume':VOLUME_PARAMETERS,'motion':MOTION_PARAMETERS}
            section='poses.'+self.selected+'.shape' if group=='shape' else group
            if tag!='light' and self.button('恢复默认 Reset '+group.title(),'reset-'+group):
                self.attempt(lambda:self.session.restore(group,self.selected))
            imgui.begin_child('scroll-'+tag,V(0,max(120,imgui.get_content_region_avail().y-130)))
            parameters=definitions[group]
            if group=='volume':
                volume_keys={'volume_depth','surface_roundness','bulge_influence'}
                parameters=[p for p in parameters if (p[0] in volume_keys)==(tag=='volume')]
            if tag=='shape':self.build_contour_ui()
            for parameter in parameters:self.edit_slider(section,*parameter)
            if tag=='shape':self.build_eye_axes()
            if tag=='light':imgui.text_wrapped('颜色待按批准参考图继续校准。')
            if tag=='motion':imgui.text('响应越大 → 过渡越快。')
            imgui.end_child()
        imgui.separator()
        if self.button('保存工作台 S','save'):self.attempt(self.session.save,'整个库、体积、运动与选择已保存。')
        imgui.same_line()
        if self.button('Undo Z','undo'):self.attempt(self.session.undo)
        imgui.same_line()
        if self.button('Redo Y','redo'):self.attempt(self.session.redo)
        if self.button('恢复全部默认…','reset-all'):self.open_dialog('all')
        imgui.same_line()
        if self.button('重新加载库 R','reload'):self.open_dialog('reload')
        imgui.end()
        imgui.push_style_var(imgui.StyleVar_.window_padding,V(16,6))
        self.panel('status',12,h-42,w-24,40)
        imgui.text_colored(imgui.ImVec4(1,.55,.38,1) if self.error else imgui.ImVec4(.60,.72,.79,1),self.status)
        imgui.end()
        imgui.pop_style_var()

    def draw_canvas(self,width,height):
        width=max(64,width);height=max(64,height)
        compare=self.cfg['reference']['enabled'] and self.cfg['reference']['side_by_side'] and self.reference.texture
        if compare:width=(width-12)/2
        scale=min(width/self.cfg['display']['design_aspect'],height)
        size=(int(scale*self.cfg['display']['design_aspect']),int(scale))
        self.ensure_canvas(tuple(int(x*self.wnd.pixel_ratio) for x in size))
        frame=self.runtime.frame() if self.mode=='runtime' else self.rig.pose_frame(self.selected) if self.mode=='edit' else self.rig.frame_at_blend(self.player.blend)
        self.rendered_frame=frame
        self.renderer.render(frame,self.canvas,self.show_safe,self.flat)
        self.element_renderer.render(element_frame(self.cfg['accent'],self.accent_animation),
                                     self.canvas,self.cfg['display'],self.show_safe)
        imgui.set_cursor_pos_x(imgui.get_cursor_pos_x()+(width-size[0])/2)
        imgui.image(self.texture.glo,V(*size),V(0,1),V(1,0))
        self.remember_rect('canvas')
        self.drag_accent()
        rect=self.ui_rects['canvas'];right=None
        if compare:right=(rect[2]+12,rect[1],rect[2]+12+rect[2]-rect[0],rect[3])
        self.draw_reference(rect,right)

    def build_accent_ui(self):
        imgui.text('辅助元素 Accent')
        imgui.text_disabled('Experimental / Unverified')
        changed,enabled=imgui.checkbox('Accent Enabled / 启用',self.cfg['accent']['enabled'])
        if changed:self.attempt(lambda:self.session.edit_accent(enabled=enabled));self.accent_animation.reset()
        opened=imgui.begin_combo('Accent Type',self.cfg['accent']['type'])
        self.remember_rect('accent-type')
        if opened:
            for kind in ELEMENT_TYPES:
                selected,_=imgui.selectable(kind,self.cfg['accent']['type']==kind)
                self.remember_rect('accent-choice-'+kind)
                if selected:
                    self.attempt(lambda k=kind:self.session.edit_accent(type=k,enabled=k!='NONE'))
                    self.accent_animation.reset()
            imgui.end_combo()
        if self.button('Preview / Play','accent-play'):self.accent_animation.play()
        imgui.same_line()
        if self.button('继续 Resume' if self.accent_animation.paused else '暂停 Pause',
                       'accent-resume' if self.accent_animation.paused else 'accent-pause'):
            if self.accent_animation.paused:self.accent_animation.resume()
            else:self.accent_animation.pause()
        if self.button('Reset Animation','accent-animation-reset'):self.accent_animation.reset()
        imgui.same_line();imgui.text(self.accent_animation.phase)
        if self.button('Reset Accent','reset-accent'):
            self.attempt(lambda:self.session.restore('accent'));self.accent_animation.reset()
        imgui.text_disabled('拖动预览中的符号；S 保存，R 恢复。')
        imgui.begin_child('scroll-accent',V(0,max(100,imgui.get_content_region_avail().y-130)))
        for key,label in (('x','Position X / 水平位置'),('y','Position Y / 垂直位置')):
            extent=self.cfg['display']['design_aspect']/2 if key=='x' else .5
            self.edit_slider('accent.position',key,label,-2.,2.,'%.3f')
        for p in ACCENT_PARAMETERS:self.edit_slider('accent',*p)
        imgui.end_child()

    def drag_accent(self):
        a=self.cfg['accent'];io=imgui.get_io()
        x0,y0,x1,y1=self.ui_rects['canvas']
        pixels=min(y1-y0,(x1-x0)/self.cfg['display']['design_aspect'])
        mx=(io.mouse_pos.x-(x0+x1)/2)/pixels
        my=((y0+y1)/2-io.mouse_pos.y)/pixels
        bounds=world_bounds(a,self.accent_animation.sample()[1])
        if (imgui.is_item_hovered() and imgui.is_mouse_clicked(0) and a['enabled'] and
                a['type']!='NONE' and a['opacity']*self.accent_animation.sample()[0]>0 and
                bounds[0]<=mx<=bounds[1] and bounds[2]<=my<=bounds[3]):
            self.session.begin_gesture()
            self.accent_drag=(mx-a['position']['x'],my-a['position']['y'])
        if self.accent_drag is not None:
            if imgui.is_mouse_down(0):
                candidate=deepcopy(self.cfg)
                candidate['accent']['position']=dict(x=mx-self.accent_drag[0],y=my-self.accent_drag[1])
                candidate['accent']=clamp_accent(candidate['accent'],candidate['display'])
                self.session.config=candidate
                self.status='Accent 位置已更新；完整尺寸限制在安全区内。S 保存。'
            else:
                self.session.end_gesture();self.accent_drag=None

    def open_dialog(self,kind):
        self.dialog_request=kind;self.dialog_pose=self.selected
        self.name_buffer='' if kind=='new' else self.cfg['poses'][self.selected]['name']+(' Copy' if kind=='copy' else '')

    def native_close_request(self):
        self.close_requested=True;return True

    def dialogs(self):
        if self.close_requested:
            if self.session.dirty:self.open_dialog('close')
            else:self.wnd.close()
            self.close_requested=False
        if self.dialog_request:
            self.dialog_kind=self.dialog_request;self.dialog_request=None
            imgui.open_popup('确认 / Pose 操作')
        opened,_=imgui.begin_popup_modal('确认 / Pose 操作',flags=imgui.WindowFlags_.always_auto_resize)
        self.exit_dialog_visible=opened and self.dialog_kind=='close'
        if not opened:return
        kind=self.dialog_kind;pid=self.dialog_pose
        messages={'new':'新建 Pose：以 NORMAL 标准形状起步。',
                  'copy':'复制当前形状为独立 Pose。',
                  'rename':'重命名；A/B 引用保持不变。',
                  'delete':'删除这个自定义 Pose？保存工作台后写入磁盘。',
                  'load':'加载此 Pose 的已保存形状，覆盖当前未保存修改？',
                  'all':'恢复所有 Pose 形状、Volume、Motion、Accent 默认值？',
                  'reload':'重新加载整个库？未保存修改会被替换。',
                  'close':'还有未保存修改。保存后退出，或放弃修改？'}
        imgui.text(messages[kind])
        if kind=='all':imgui.text('自定义记录与名称保留；本操作可 Undo。')
        if kind in ('new','copy','rename'):
            _,self.name_buffer=self.text_input('名称',self.name_buffer)
        def apply():
            if kind in ('new','copy'):
                self.session.create(self.name_buffer,pid if kind=='copy' else None)
                self.mode='edit';self.player.pause()
            elif kind=='rename':self.session.rename(pid,self.name_buffer)
            elif kind=='delete':
                self.session.delete(pid);self.mode='edit';self.player.pause()
            elif kind=='load':self.session.load_pose(pid)
            elif kind=='all':
                self.session.restore('all');self.player.seek(0)
                self.accent_animation.reset()
                self.mode='edit';self.flat=False;self.show_safe=False
            elif kind=='reload':
                self.session.commit(load_config(self.session.path))
                self.session.saved=deepcopy(self.cfg);self.player.seek(0);self.mode='edit'
                self.accent_animation.reset()
            elif kind=='close':self.session.save();self.wnd.close()
        if self.button('保存并退出' if kind=='close' else '确认','confirm-dialog'):
            if self.attempt(apply):imgui.close_current_popup()
        imgui.same_line()
        if self.button('取消','cancel-dialog'):imgui.close_current_popup()
        if kind=='close':
            imgui.same_line()
            if self.button('放弃并退出'):self.wnd.close();imgui.close_current_popup()
        if self.error:imgui.text_wrapped(self.status)
        imgui.end_popup()

    def on_render(self,time,frame_time):
        if min(self.wnd.buffer_size)<=0:return
        if frame_time>0:
            self.recent.append(frame_time)
            if (self.argv.smoke_seconds or self.argv.benchmark_seconds) and time>1:self.measured.append(frame_time)
        if self.mode=='ab':self.player.advance(frame_time)
        elif self.mode=='runtime':self.runtime.advance(frame_time)
        self.accent_animation.advance(frame_time)
        fps=len(self.recent)/sum(self.recent) if self.recent else 0
        io=imgui.get_io();io.delta_time=max(frame_time,1e-6)
        self.gui.resize(*self.wnd.size)
        imgui.new_frame();self.build_ui(fps);self.dialogs();imgui.render()
        self.wnd.fbo.use();self.ctx.viewport=(0,0,*self.wnd.buffer_size);self.ctx.scissor=None
        self.wnd.fbo.clear(.025,.032,.045,1)
        self.gui.render(imgui.get_draw_data())
        self.wnd.title=f'FULU Pose Editor | {fps:.1f} FPS | '+('unsaved' if self.session.dirty else 'saved')
        if self.capture_requested:self.capture();self.capture_requested=False
        if self.argv.smoke_seconds:
            if self.argv.input_smoke:
                from tests.upgrade_smoke import tick_input
                tick_input(self,time)
            elif self.argv.upgrade_smoke:
                from tests.upgrade_smoke import tick
                tick(self,time)
            elif self.argv.accent_smoke:
                from tests.accent_smoke import tick
                tick(self,time)
            else:self.smoke_tick(time)
        if self.argv.benchmark_seconds and time>=self.argv.benchmark_seconds:
            durations=sorted(self.measured)
            report=dict(gpu=self.ctx.info['GL_RENDERER'],window_size=self.wnd.size,
                frames=len(durations),average_fps=len(durations)/sum(durations),
                p95_ms=durations[int((len(durations)-1)*.95)]*1000,
                maximum_frame_ms=max(durations)*1000,
                scope='Full editor with automatic A/B playback; no screenshot/save/resize operations')
            out=ROOT/'test_output/pose_editor';out.mkdir(exist_ok=True)
            (out/'window_benchmark.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps(report,indent=2),flush=True);self.wnd.close()

    def capture(self,name=None):
        out=ROOT/(('test_output/upgrade' if self.argv.upgrade_smoke else 'test_output/accent' if self.argv.accent_smoke else 'test_output/pose_editor') if self.argv.smoke_seconds else 'captures')
        out.mkdir(exist_ok=True)
        stem=name or f'{datetime.now():%Y%m%d_%H%M%S}_{self.selected}'
        for suffix,fbo in (('_workbench',self.wnd.fbo),('_eyes',self.canvas)):
            size=self.wnd.buffer_size if suffix=='_workbench' else fbo.size
            im=Image.frombytes('RGB',size,fbo.read(viewport=(0,0,*size),components=3,alignment=1))
            im.transpose(Image.Transpose.FLIP_TOP_BOTTOM).save(out/(stem+suffix+'.png'))
        save_config(self.cfg,out/(stem+'.json'))

    def on_key_event(self,key,action,modifiers):
        k=self.wnd.keys
        if action==k.ACTION_RELEASE:self.held_keys.discard(key)
        pressed=action==k.ACTION_PRESS and key not in self.held_keys
        if action==k.ACTION_PRESS:self.held_keys.add(key)
        io=imgui.get_io()
        ctrl=bool(getattr(modifiers,'ctrl',False))
        shift=bool(getattr(modifiers,'shift',False))
        alt=bool(getattr(modifiers,'alt',False))
        io.add_key_event(imgui.Key.mod_ctrl,ctrl)
        io.add_key_event(imgui.Key.mod_shift,shift)
        io.add_key_event(imgui.Key.mod_alt,alt)
        # Text widgets receive every key first, including Ctrl+C/X/V/A.
        if ctrl or shift or alt or io.want_text_input or key not in (k.SPACE,k.P,k.RIGHT) or action==k.ACTION_RELEASE:
            self.gui.key_event(key,action,modifiers)
        if not pressed or ctrl or shift or alt or io.want_text_input or getattr(self,'text_menu_open',False):return
        if key==k.V:self.clean=not self.clean;return
        if key==k.ESCAPE and self.clean:self.clean=False;return
        if key==k.N:self.choose_pose('normal')
        elif key==k.H:self.choose_pose('happy')
        elif key in (k.SPACE,k.P):self.attempt(self.toggle_play)
        elif key==k.RIGHT:self.attempt(self.step)
        elif key==k.F:self.flat=not self.flat
        elif key==k.G:self.show_safe=not self.show_safe
        elif key==k.S:self.attempt(self.session.save,'整个工作台已保存。')
        elif key==k.Z:self.attempt(self.session.undo)
        elif key==k.Y:self.attempt(self.session.redo)
        elif key==k.R:self.open_dialog('reload')
        elif key==k.F12:self.capture_requested=True
        elif key==k.ESCAPE:self.close_requested=True

    def on_mouse_position_event(self,x,y,dx,dy):
        if not self.argv.smoke_seconds:self.gui.mouse_position_event(x,y,dx,dy)
    def on_mouse_drag_event(self,x,y,dx,dy):
        if not self.argv.smoke_seconds:self.gui.mouse_drag_event(x,y,dx,dy)
    def on_mouse_press_event(self,x,y,button):
        if not self.argv.smoke_seconds:self.gui.mouse_press_event(x,y,button)
    def on_mouse_release_event(self,x,y,button):
        if not self.argv.smoke_seconds:self.gui.mouse_release_event(x,y,button)
    def on_mouse_scroll_event(self,x,y):
        if not self.argv.smoke_seconds:self.gui.mouse_scroll_event(x,y)
    def on_unicode_char_entered(self,char):self.gui.unicode_char_entered(char)

    def smoke_tick(self,time):
        io=imgui.get_io()
        def event(name,fn):
            if name not in self.smoke_done:
                fn();self.smoke_done.add(name);self.events.append(name)
        def down(name,fraction=.5):
            x0,y0,x1,y1=self.ui_rects[name]
            io.add_mouse_pos_event(x0+(x1-x0)*fraction,(y0+y1)/2)
            io.add_mouse_button_event(0,True)
        def up():io.add_mouse_button_event(0,False)
        def key(code):
            from moderngl_window.context.base.keys import KeyModifiers
            self.on_key_event(code,self.wnd.keys.ACTION_PRESS,KeyModifiers())
            self.on_key_event(code,self.wnd.keys.ACTION_RELEASE,KeyModifiers())
        if time>.5:event('normal-capture',lambda:self.capture('editor_normal'))
        if time>.7:event('shape-slider-down',lambda:down('eye_width',.57))
        if time>.9:event('shape-slider-up',up)
        if time>1.1:
            def check():
                assert self.cfg['poses']['normal']['shape']!=self.smoke_initial['poses']['normal']['shape']
                self.session.undo();self.sync()
                assert self.cfg['poses']['normal']['shape']==self.smoke_initial['poses']['normal']['shape']
                self.cfg['motion'].update(enter_response=12.,return_response=12.,target_interval=1.)
                self.sync()
            event('real-slider-and-undo',check)
        if time>1.3:event('play-button-down',lambda:down('play'))
        if time>1.5:event('play-button-up',up)
        if 1.6<time<6.0:
            self.autoplay_samples.append((time,self.player.blend,self.player.phase))
        if time>6:
            def check_play():
                assert not self.player.paused
                phases={x[2] for x in self.autoplay_samples}
                assert {'A → B','B → A','HOLD A','HOLD B'}<=phases,phases
                assert min(x[1] for x in self.autoplay_samples)<.01
                assert max(x[1] for x in self.autoplay_samples)>.99
                self.player.pause();self.pause_cursor=self.player.cursor
            event('automatic-full-roundtrips-no-scrub',check_play)
        if time>6.3:
            def check_pause():
                assert self.player.cursor==self.pause_cursor
                self.step();assert self.player.cursor>self.pause_cursor
                self.toggle_play();assert not self.player.paused
                self.player.pause()
            event('pause-step-resume',check_pause)
        if time>6.5:event('scrub-down',lambda:down('scrub',.34))
        if time>6.7:event('scrub-up',up)
        if time>7:
            def check_scrub():
                assert self.player.paused and .25<self.player.progress<.43
                self.capture('editor_transition')
                self.before_inspect=deepcopy(self.cfg)
                self.renderer_identity=id(self.renderer)
                key(self.wnd.keys.V);assert self.clean
                key(self.wnd.keys.V);assert not self.clean
                key(self.wnd.keys.V);key(self.wnd.keys.ESCAPE);assert not self.clean
                assert self.cfg==self.before_inspect and id(self.renderer)==self.renderer_identity
                self.choose_pose('happy')
            event('scrub-and-global-inspect-exits',check_scrub)
        if time>7.4:event('happy-capture',lambda:self.capture('editor_happy'))
        if time>7.6:
            def custom():
                pid=self.session.create('测试自定义',self.selected)
                self.session.rename(pid,'Custom Arc')
                self.session.save_pose(pid)
                assert pid in load_config(self.session.path)['poses']
                self.set_pair('target',pid);self.sync()
                self.session.save()
                assert load_config(self.session.path)==self.cfg
                self.session.delete(pid);self.session.undo();self.session.redo();self.sync()
                self.choose_pose('normal')
            event('custom-save-load-pair-delete-undo-redo',custom)
        if time>8:event('all-reset-dialog-down',lambda:down('reset-all'))
        if time>8.2:event('all-reset-dialog-up',up)
        if time>8.5:event('all-reset-cancel-down',lambda:down('cancel-dialog'))
        if time>8.7:event('all-reset-cancel-up',up)
        if time>9:
            def inspect_text():
                self.open_dialog('new')
            event('open-name-field',inspect_text)
        if time>9.3:
            def text_keys():
                io.want_text_input=True
                key(self.wnd.keys.V);assert not self.clean
                key(self.wnd.keys.ESCAPE);assert not self.clean and not self.close_requested
                key(self.wnd.keys.V);key(self.wnd.keys.V);assert not self.clean
                io.want_text_input=False
                down('cancel-dialog')
            event('text-input-suppresses-global-shortcuts',text_keys)
        if time>9.5:event('name-dialog-cancel-up',up)
        if time>9.8:event('resize',lambda:setattr(self.wnd,'size',(1180,820)))
        if time>10.3:event('resize-capture',lambda:self.capture('editor_resized'))
        if time>10.5:
            def prepare_reset():
                self.before_reset=deepcopy(self.cfg)
                self.open_dialog('all')
            event('all-reset-request',prepare_reset)
        if time>10.8:
            def confirm_reset():
                assert self.cfg==self.before_reset
                down('confirm-dialog')
            event('all-reset-requires-confirmation',confirm_reset)
        if time>11:event('all-reset-confirm-up',up)
        if time>11.3:
            def verify_reset():
                from fulu_visual.config import DEFAULTS
                assert self.cfg['motion']==DEFAULTS['motion']
                assert self.cfg['poses']['normal']['shape']==self.cfg['poses']['normal']['defaults']
                self.session.undo();self.sync();assert self.cfg==self.before_reset
                self.session.begin_gesture();self.session.edit('volume','center_fill',.76)
                self.session.end_gesture();self.sync();self.native_close_request()
            event('confirmed-all-reset-and-undo',verify_reset)
        if time>11.6:
            def cancel_close():
                assert self.exit_dialog_visible
                down('cancel-dialog')
            event('unsaved-close-guard',cancel_close)
        if time>11.8:event('close-cancel-up',up)
        if time>12.1:
            def volume_capture():
                assert not self.exit_dialog_visible
                self.request_tab='volume'
            event('volume-panel',volume_capture)
        if time>12.5:event('volume-capture',lambda:self.capture('editor_volume'))
        if time>12.8:
            def reference_check():
                key(self.wnd.keys.F);assert self.flat
                key(self.wnd.keys.G);assert self.show_safe
                key(self.wnd.keys.V);assert self.clean
            event('flat-safe-inspect',reference_check)
        if time>13.1:event('inspect-capture',lambda:self.capture('editor_inspect'))
        if time>13.4:
            def finish_inspect():
                key(self.wnd.keys.ESCAPE);assert not self.clean and not self.close_requested
                key(self.wnd.keys.F);key(self.wnd.keys.G)
                self.cfg['selection']['target']='happy'
                self.request_tab='shape'
            event('inspect-esc-keeps-renderer',finish_inspect)
        if time>13.8:event('final-workbench-capture',lambda:self.capture('editor_final'))
        if time>=self.argv.smoke_seconds:
            durations=sorted(self.measured)
            report=dict(gpu=self.ctx.info['GL_RENDERER'],frames=len(durations),
                average_fps=len(durations)/sum(durations),
                p95_ms=durations[int((len(durations)-1)*.95)]*1000,
                events=self.events,autoplay_samples=self.autoplay_samples,
                input_method='Injected ImGui mouse events and native-window key callbacks; no physical input automation',
                visual_acceptance='pending user review')
            (ROOT/'test_output/pose_editor/window_smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in report.items() if k!='autoplay_samples'},indent=2),flush=True)
            self.wnd.close()

if __name__=='__main__':
    mglw.run_window_config(Simulator,timer=FrameTimer(CONFIG['display']['target_fps']))

