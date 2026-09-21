"""Additional editor panels; the existing window and render loop stay in simulator.py."""
from pathlib import Path
from copy import deepcopy
from imgui_bundle import imgui
from .config import ROOT
from .reference import ReferenceImage
from .runtime import VisualRuntime

V=imgui.ImVec2

class WorkbenchExtensions:
    @staticmethod
    def wrap_text(value,width,measure):
        """Soft line layout for single logical values (names/paths), with UTF-8 caret mapping."""
        value=value.replace('\r','').replace('\n','');out=[];mapping={0:0};x=0.;raw_pos=0;display_pos=0
        for char in value:
            advance=measure(char)
            if x and x+advance>width:out.append('\n');display_pos+=1;x=0.
            mapping[raw_pos]=display_pos
            out.append(char);n=len(char.encode('utf-8'));raw_pos+=n;display_pos+=n;x+=advance
            mapping[raw_pos]=display_pos
        return ''.join(out),mapping

    def text_input(self,label,value,flags=0,size=None):
        # Remaining values are paths and Pose names: visual wraps never enter saved text.
        if not hasattr(self,'text_states'):self.text_states={};self.text_actions={}
        value=value.replace('\r','').replace('\n','')
        imgui.text(label);size=size or V(-1,86)
        width=max(40.,(imgui.get_content_region_avail().x if size.x<=0 else size.x)-32.)
        measure=lambda char:imgui.calc_text_size(char).x
        displayed,mapping=self.wrap_text(value,width,measure)
        field=imgui.get_id('##text-'+label)
        state=self.text_states.setdefault(field,dict(cursor=len(displayed.encode('utf-8')),start=0,end=0))
        if field in self.text_actions:imgui.set_keyboard_focus_here()
        io=imgui.get_io()
        copying=io.key_ctrl and (imgui.is_key_pressed(imgui.Key.c,False) or imgui.is_key_pressed(imgui.Key.x,False)) and imgui.internal.get_active_id()==field
        def callback(data):
            action=self.text_actions.pop(field,None)
            if action:
                operation,saved=action;length=data.buf_text_len
                start=max(0,min(length,saved['start']));end=max(0,min(length,saved['end']))
                data.cursor_pos=max(0,min(length,saved['cursor']));data.selection_start=start;data.selection_end=end
                if operation=='all':data.select_all()
                elif operation in ('paste','cut'):
                    lo,hi=sorted((start,end))
                    if lo!=hi:data.delete_chars(lo,hi-lo);data.cursor_pos=lo
                    if operation=='paste':data.insert_chars(data.cursor_pos,imgui.get_clipboard_text().replace('\r','').replace('\n',''))
                    data.clear_selection()
            before=data.buf;raw=before.encode('utf-8')
            def logical(pos):return len(raw[:pos].replace(b'\r',b'').replace(b'\n',b''))
            cursor,start,end=(logical(pos) for pos in (data.cursor_pos,data.selection_start,data.selection_end))
            logical_value=before.replace('\r','').replace('\n','')
            # A visual newline is not a character: deleting across it must edit the value.
            if logical_value==value and before!=displayed and start==end:
                index=len(logical_value.encode('utf-8')[:cursor].decode('utf-8'))
                if imgui.is_key_pressed(imgui.Key.backspace,True) and index:
                    logical_value=logical_value[:index-1]+logical_value[index:]
                    cursor=len(logical_value[:index-1].encode('utf-8'));start=end=cursor
                elif imgui.is_key_pressed(imgui.Key.delete,True) and index<len(logical_value):
                    logical_value=logical_value[:index]+logical_value[index+1:]
            wrapped,positions=self.wrap_text(logical_value,width,measure)
            if wrapped!=before:
                data.delete_chars(0,data.buf_text_len);data.insert_chars(0,wrapped)
                data.cursor_pos=positions.get(cursor,len(wrapped.encode('utf-8')))
                data.selection_start=positions.get(start,data.cursor_pos);data.selection_end=positions.get(end,data.cursor_pos)
            state.update(cursor=data.cursor_pos,start=data.selection_start,end=data.selection_end)
            return 0
        changed,result=imgui.input_text_multiline('##text-'+label,displayed,size,
            flags=flags|imgui.InputTextFlags_.callback_always|imgui.InputTextFlags_.no_horizontal_scroll,callback=callback)
        self.remember_rect('text:'+label)
        self.text_layouts=getattr(self,'text_layouts',{});self.text_layouts[label]=dict(lines=result.count('\n')+1,width=width,display=result)
        if copying:imgui.set_clipboard_text(imgui.get_clipboard_text().replace('\r','').replace('\n',''))
        if imgui.begin_popup_context_item('text-menu-'+str(field)):
            self.text_menu_open=True;lo,hi=sorted((state['start'],state['end']))
            for title,shortcut,operation in (('粘贴 Paste','Ctrl+V','paste'),('全选 Select All','Ctrl+A','all'),('剪切 Cut','Ctrl+X','cut'),('复制 Copy','Ctrl+C','copy')):
                selected,_=imgui.menu_item(title,shortcut,False,operation not in ('cut','copy') or lo!=hi)
                self.remember_rect('text-menu-'+operation)
                if selected:
                    if operation in ('copy','cut'):imgui.set_clipboard_text(result.encode('utf-8')[lo:hi].decode('utf-8').replace('\n',''))
                    self.text_actions[field]=(operation,dict(state))
            imgui.end_popup()
        logical_result=result.replace('\r','').replace('\n','')
        return logical_result!=value,logical_result

    def setup_extensions(self):
        self.reference=ReferenceImage();self.reference_path=self.cfg['reference']['path']
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
        _,self.reference_path=self.text_input('路径',self.reference_path)
        if self.button('浏览图片','reference-browse'):self.attempt(self.browse_reference,'参考图已导入本项目资源目录。')
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
        for i,(label,event) in enumerate((('看左 Left','Look Left'),('回中 Center','Center'),('看右 Right','Look Right'),('Shake','Shake'))):
            if i in (1,2):imgui.same_line()
            if self.button(label,'event-'+event):self.attempt(lambda e=event:self.dispatch_runtime(e))
        ids=[pid for pid,p in self.cfg['poses'].items() if not p.get('archived')]
        target=getattr(self,'runtime_choice',self.selected)
        if target not in ids:target=self.selected
        _,index=imgui.combo('目标 Pose',ids.index(target),[self.cfg['poses'][pid]['name'] for pid in ids])
        self.runtime_choice=ids[index]
        if self.button('播放过渡 Play transition','runtime-play'):
            self.attempt(lambda:self.play_runtime_pose(self.runtime_choice))
        imgui.text(f'Progress: {self.runtime.progress:.3f}')
        imgui.text_disabled('Look / Shake：待肉眼验收')

    def set_contour(self,points,key='contour',seed=False):
        self.choose_pose(self.session.set_contour(self.selected,points,key,seed))
    def build_contour_ui(self):
        from .geometry import seed_contour,legacy_contour,side_shape
        imgui.text('闭合轮廓 Contour · Experimental / 待验收')
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
    def build_extension_panel(self,tag):
        imgui.begin_child('extension-scroll-'+tag,V(0,max(100,imgui.get_content_region_avail().y-130)))
        if tag=='reference':self.build_reference_ui()
        elif tag=='runtime':self.build_runtime_ui()
        imgui.end_child()

    def build_eye_axes(self):
        from .config import EYE_PARAMETERS
        if imgui.collapsing_header('左右眼与位置 Eyes / Transform'):
            shape=self.cfg['poses'][self.selected]['shape']
            # Optional keys are read through defaults; inspecting the panel does not mutate data.
            for parameter in EYE_PARAMETERS:self.edit_slider('poses.'+self.selected+'.shape',*parameter)
