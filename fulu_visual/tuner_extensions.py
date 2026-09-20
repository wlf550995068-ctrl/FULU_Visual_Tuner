"""Additional editor panels; the existing window and render loop stay in simulator.py."""
from pathlib import Path
from copy import deepcopy
import json
from imgui_bundle import imgui
from .config import ROOT,save_config
from .ai_ui import AIWorkbench
from .reference import ReferenceImage
from .runtime import VisualRuntime,TRIGGERS
from .export_tools import export_source,export_pose

V=imgui.ImVec2

class WorkbenchExtensions(AIWorkbench):
    def setup_extensions(self):
        self.reference=ReferenceImage();self.reference_path=self.cfg['reference']['path']
        self.setup_ai()
        self.runtime=VisualRuntime(self.cfg,self.selected)
        self.rendered_frame=self.rig.pose_frame(self.selected)
        self.reference_restore_path=None
        if self.reference_path:
            try:self.restore_reference()
            except (ValueError,OSError) as exc:self.status='参考图加载失败：'+str(exc)
    def sync_extensions(self):
        self.runtime.configure(self.cfg)
        if self.runtime.target not in self.cfg['poses']:
            self.runtime=VisualRuntime(self.cfg,'normal');self.mode='edit'
        path=self.cfg['reference']['path']
        if path!=self.reference_restore_path:
            try:self.restore_reference()
            except (ValueError,OSError) as exc:self.status='参考图加载失败：'+str(exc)
    def restore_reference(self):
        path=self.cfg['reference']['path']
        if path:
            self.reference.load(ROOT/path);self.reference.upload(self.ctx,self.gui)
        else:
            if self.reference.texture:
                self.gui.remove_texture(self.reference.texture);self.reference.texture.release()
            self.reference=ReferenceImage()
        self.reference_restore_path=path;self.reference_path=path
    def import_reference(self,path):
        self.reference.load(path,ROOT/'assets/references')
        self.reference.upload(self.ctx,self.gui)
        candidate=deepcopy(self.cfg)
        candidate['reference'].update(path=self.reference.path.relative_to(ROOT).as_posix(),enabled=True)
        self.reference_restore_path=candidate['reference']['path']
        self.reference_path=candidate['reference']['path']
        self.session.commit(candidate)
    def browse_reference(self):
        import tkinter
        from tkinter import filedialog
        root=tkinter.Tk();root.withdraw()
        try:
            path=filedialog.askopenfilename(title='导入参考图',filetypes=[('Images','*.png *.jpg *.jpeg *.webp *.bmp')])
        finally:root.destroy()
        if path:self.import_reference(path)
    def edit_setting(self,section,key,value):
        candidate=deepcopy(self.cfg);candidate[section][key]=value
        self.session.commit(candidate)
    def draw_reference(self,rect,side_rect=None):
        ref=self.cfg['reference']
        if not ref['enabled'] or not self.reference.texture:return
        target=side_rect or rect
        dest=self.reference.placement(self.reference.image.size,target,ref['fit'],ref['zoom'],ref['x'],ref['y'])
        dl=imgui.get_window_draw_list()
        dl.push_clip_rect(V(target[0],target[1]),V(target[2],target[3]),True)
        opacity=1. if side_rect else ref['opacity']
        color=imgui.get_color_u32(imgui.ImVec4(1,1,1,opacity))
        dl.add_image(self.reference.texture.glo,V(dest[0],dest[1]),V(dest[2],dest[3]),V(0,0),V(1,1),color)
        dl.pop_clip_rect()
    def build_reference_ui(self):
        imgui.text('参考图 Reference')
        _,self.reference_path=imgui.input_text('路径',self.reference_path)
        if self.button('浏览图片','reference-browse'):self.attempt(self.browse_reference,'参考图已导入 D 盘资源目录。')
        imgui.same_line()
        if self.button('导入路径','reference-import'):
            self.attempt(lambda:self.import_reference(str(ROOT/Path(self.reference_path))) if not Path(self.reference_path).is_absolute() else self.import_reference(self.reference_path))
        c=self.cfg['reference']
        for key,label in (('enabled','显示参考图'),('side_by_side','左右对照')):
            changed,value=imgui.checkbox(label,c[key])
            if changed:self.attempt(lambda k=key,v=value:self.edit_setting('reference',k,v))
        changed,index=imgui.combo('显示方式',('Fit','Fill','1:1').index(c['fit']),['Fit','Fill','1:1'])
        if changed:self.attempt(lambda:self.edit_setting('reference','fit',('Fit','Fill','1:1')[index]))
        for p in (('opacity','Overlay 透明度',0.,1.,'%.2f'),('zoom','缩放',.05,10.,'%.2f'),
                  ('x','水平位置',-3.,3.,'%.2f'),('y','垂直位置',-3.,3.,'%.2f')):
            self.edit_slider('reference',*p)
        if self.reference.measurement:imgui.text_wrapped(self.reference.measurement['reason'])
    def build_derive_ui(self):
        self.build_ai_ui()
    def dispatch_runtime(self,event):
        if self.mode!='runtime':
            from .geometry import mix_shape
            initial=self.cfg['poses'][self.selected]['shape'] if self.mode=='edit' else mix_shape(
                self.cfg['poses'][self.cfg['selection']['source']]['shape'],
                self.cfg['poses'][self.cfg['selection']['target']]['shape'],self.player.blend)
            self.runtime=VisualRuntime(self.cfg,self.selected,initial=initial)
            self.player.pause();self.mode='runtime'
        self.runtime.dispatch(event)
    def play_runtime_pose(self,pid):
        if self.mode!='runtime':
            from .geometry import mix_shape
            initial=self.cfg['poses'][self.selected]['shape'] if self.mode=='edit' else mix_shape(
                self.cfg['poses'][self.cfg['selection']['source']]['shape'],self.cfg['poses'][self.cfg['selection']['target']]['shape'],self.player.blend)
            self.runtime=VisualRuntime(self.cfg,self.selected,initial=initial)
            self.player.pause();self.mode='runtime'
        self.runtime.retarget(pid)
    def build_runtime_ui(self):
        imgui.text('实时触发 Runtime')
        for i,(label,event) in enumerate((('看左 Left','Look Left'),('回中 Center','Center'),('看右 Right','Look Right'),('Wake','Wake'),('Shake','Shake'))):
            if i in (1,2,4):imgui.same_line()
            if self.button(label,'event-'+event):self.attempt(lambda e=event:self.dispatch_runtime(e))
        ids=[pid for pid,p in self.cfg['poses'].items() if not p.get('archived')]
        target=getattr(self,'runtime_choice',self.selected)
        if target not in ids:target=self.selected
        _,index=imgui.combo('目标 Pose',ids.index(target),[self.cfg['poses'][pid]['name'] for pid in ids])
        self.runtime_choice=ids[index]
        if self.button('播放过渡 Play transition','runtime-play'):
            self.attempt(lambda:self.play_runtime_pose(self.runtime_choice))
        imgui.text(f'Progress: {self.runtime.progress:.3f}')

    def set_contour(self,points,key='contour',seed=False):
        from .geometry import validate_contour
        from .eye_intent import apply_intent
        validate_contour(points)
        channel={'contour':'shared','left_contour':'left','right_contour':'right'}[key]
        intent=dict(label='CONTOUR',operations=[],contours=[dict(eye=channel,points=[dict(x=x,y=y) for x,y in points])])
        current=self.cfg['poses'][self.selected]['shape']
        if not seed and key in current:
            intent['operations'].append(dict(section='shape',parameter='corner_roundness',op='set',value=current['corner_roundness']))
        if seed:
            values=dict(whole_bend=0.,top_curve=0.,bottom_curve=0.,center_bulge=0.,end_taper=0.,squash=0.,stretch=0.,thickness=1.,tilt=0.)
            intent['operations']=[dict(section='shape',parameter=k,op='set',value=v) for k,v in values.items()]
        pid,_=apply_intent(self.session,self.selected,intent)
        self.choose_pose(pid)
    def build_contour_ui(self):
        from .geometry import seed_contour,legacy_contour,side_shape
        imgui.text('闭合轮廓 Contour')
        sides=['双眼 Both','左眼 Left','右眼 Right'];keys=['contour','left_contour','right_contour']
        _,self.contour_side=imgui.combo('编辑对象',getattr(self,'contour_side',0),sides)
        key=keys[self.contour_side];shape=self.cfg['poses'][self.selected]['shape']
        own=side_shape(shape,('left','right')[self.contour_side-1]) if self.contour_side else shape
        points=deepcopy(own.get('contour',[]))
        if not points:
            if self.button('转换当前轮廓 Edit contour','contour-convert'):
                self.attempt(lambda:self.set_contour(legacy_contour(own),key))
        for i,(label,kind) in enumerate((('圆 Circle','circle'),('矩形 Rect','rectangle'),('三角 Triangle','triangle'))):
            if i:imgui.same_line()
            if self.button(label,'seed-'+kind):self.attempt(lambda k=kind:self.set_contour(seed_contour(k),key,seed=True))
        if not points:return
        index=min(getattr(self,'contour_vertex',0),len(points)-1)
        changed,index=imgui.slider_int('顶点 Point',index,0,len(points)-1);self.contour_vertex=index
        origin=imgui.get_cursor_screen_pos();w=max(160.,imgui.get_content_region_avail().x);h=180.
        imgui.invisible_button('contour-pad',V(w,h));self.remember_rect('contour-pad')
        dl=imgui.get_window_draw_list();color=imgui.get_color_u32(imgui.ImVec4(.4,.75,.95,1))
        def screen(p):return V(origin.x+(p[0]+1)*.5*(w-16)+8,origin.y+(1-p[1])*.5*(h-16)+8)
        for j,point in enumerate(points):
            dl.add_line(screen(point),screen(points[(j+1)%len(points)]),color,1.5)
            dl.add_circle_filled(screen(point),4 if j==index else 2.5,color)
        io=imgui.get_io()
        if imgui.is_item_activated():
            self.session.begin_gesture()
            self.contour_vertex=min(range(len(points)),key=lambda j:(screen(points[j]).x-io.mouse_pos.x)**2+(screen(points[j]).y-io.mouse_pos.y)**2)
        if imgui.is_item_active() and imgui.is_mouse_dragging(0):
            points[self.contour_vertex]=[max(-1.,min(1.,2*(io.mouse_pos.x-origin.x-8)/(w-16)-1)),max(-1.,min(1.,1-2*(io.mouse_pos.y-origin.y-8)/(h-16)))]
            self.attempt(lambda:self.session.edit('poses.'+self.selected+'.shape',key,points))
        if imgui.is_item_deactivated():self.session.end_gesture()
        if self.button('加点 +','contour-add') and len(points)<64:
            a,b=points[index],points[(index+1)%len(points)];points.insert(index+1,[(x+y)/2 for x,y in zip(a,b)])
            self.attempt(lambda:self.set_contour(points,key))
        imgui.same_line()
        imgui.begin_disabled(len(points)<=3)
        if self.button('删点 −','contour-delete'):
            points.pop(index);self.attempt(lambda:self.set_contour(points,key))
        imgui.end_disabled();imgui.separator()
    def build_export_ui(self):
        imgui.text('导出 Export')
        imgui.text_wrapped('源码包排除个人库、参考图片、备份、缓存、虚拟环境与主项目。不会自动上传 GitHub。')
        if self.button('导出当前 Pose JSON'):
            self.attempt(lambda:export_pose(self.cfg,self.selected), '已导出到 D 盘项目 exports。')
        if self.button('生成工具源码包'):
            self.attempt(lambda:export_source(), '已生成 exports/FULU_Visual_Tuner_source.zip；尚未发布。')
        imgui.text_wrapped('许可证尚未决定；发布前需选择许可证并确认 FULU 视觉资产及参考图权利。')
    def build_extension_panel(self,tag):
        imgui.begin_child('extension-scroll-'+tag,V(0,max(100,imgui.get_content_region_avail().y-130)))
        if tag=='reference':self.build_reference_ui()
        elif tag=='derive':self.build_derive_ui()
        elif tag=='runtime':self.build_runtime_ui()
        elif tag=='export':self.build_export_ui()
        elif tag=='settings':self.build_settings_ui()
        imgui.end_child()

