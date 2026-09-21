"""Real-window checks for the manual editor and clipboard. No network services."""
from copy import deepcopy
import json
from imgui_bundle import imgui
from fulu_visual.config import ROOT,load_config
from fulu_visual.geometry import seed_contour

def tick(app,time):
    io=imgui.get_io()
    def event(name,fn):
        if name not in app.smoke_done:fn();app.smoke_done.add(name);app.events.append(name)
    def click(name):
        x0,y0,x1,y1=app.ui_rects[name];io.add_mouse_pos_event((x0+x1)/2,(y0+y1)/2)
        io.add_mouse_button_event(0,True);io.add_mouse_button_event(0,False)
    if time>.2:
        def start():
            app.choose_pose('normal');app.request_tab='shape';app.protected=deepcopy(app.cfg['poses']['normal']);app.capture('manual_normal')
        event('normal-and-shape',start)
    if time>.5:event('rectangle-seed-click',lambda:click('seed-rectangle'))
    if time>.8:
        def drag_down():
            assert app.selected!='normal' and 'contour' in app.cfg['poses'][app.selected]['shape']
            app.contour_id=app.selected;app.contour_before=deepcopy(app.cfg['poses'][app.selected]['shape'])
            x0,y0,x1,y1=app.ui_rects['contour-pad'];io.add_mouse_pos_event(x1-8,y0+8);io.add_mouse_button_event(0,True)
        event('drag-point-down',drag_down)
    if time>1.:
        def drag():
            x0,y0,x1,y1=app.ui_rects['contour-pad'];io.add_mouse_pos_event(x1-35,y0+30)
        event('drag-point',drag)
    if time>1.15:event('drag-point-up',lambda:io.add_mouse_button_event(0,False))
    if time>1.4:
        def saved():
            assert app.cfg['poses'][app.selected]['shape']!=app.contour_before
            app.session.undo();app.sync();assert app.cfg['poses'][app.selected]['shape']==app.contour_before
            app.session.redo();app.sync();app.session.save_pose(app.selected)
            assert load_config(app.session.path)['poses'][app.selected]['shape']==app.cfg['poses'][app.selected]['shape']
            assert app.cfg['poses']['normal']==app.protected;app.capture('manual_contour')
            app.reference_path=str(ROOT/'test_output/upgrade/manual_normal_eyes.png');app.request_tab='reference'
        event('contour-undo-redo-save-preserves-normal',saved)
    if time>1.75:event('import-reference',lambda:click('reference-import'))
    if time>2.1:
        def overlay():
            assert app.reference.texture and app.cfg['reference']['enabled'];app.capture('manual_reference')
            app.edit_setting('reference','side_by_side',True);app.sync()
        event('reference-overlay',overlay)
    if time>2.4:
        def runtime():
            app.capture('manual_reference_comparison');app.edit_setting('reference','enabled',False)
            app.choose_pose('normal');app.request_tab='runtime';app.runtime_choice='happy'
        event('reference-comparison-and-runtime',runtime)
    if time>2.7:event('runtime-play-click',lambda:click('runtime-play'))
    if app.mode=='runtime' and app.runtime.target=='happy' and .46<=app.runtime.progress<.9:
        def interrupt():
            before=deepcopy(app.runtime.current);app.play_runtime_pose(app.contour_id)
            assert app.runtime.current==before and app.runtime.start==before
        event('interrupt-at-46-percent',interrupt)
    if time>4.1:
        def arrived():
            assert 'interrupt-at-46-percent' in app.smoke_done and app.runtime.target==app.contour_id and app.runtime.progress==1
            app.capture('manual_runtime');app.dispatch_runtime('Look Left')
        event('pose-transition-completed',arrived)
    if time>4.6:
        def left():assert app.runtime.gaze==-1.;app.capture('look_left');app.dispatch_runtime('Center')
        event('look-left-hold-center',left)
    if time>5.5:
        def right():assert app.runtime.gaze==0.;app.dispatch_runtime('Look Right')
        event('center-completed-look-right',right)
    if time>6.:
        def held_right():assert app.runtime.gaze==1.;app.capture('look_right')
        event('look-right-held',held_right)
    if time>7.5:
        def shake():
            assert app.runtime.gaze==0.;app.shake_before=deepcopy(app.runtime.current);app.dispatch_runtime('Shake')
        event('look-returned-shake',shake)
    if time>7.76:event('shake-visible',lambda:app.capture('shake_preview'))
    if time>8.3:
        def flat():
            assert app.runtime.current==app.shake_before
            app.choose_pose('normal');app.request_tab='volume';app.depth=app.cfg['volume']['volume_depth']
            app.edit_setting('volume','volume_depth',0.);app.sync()
        event('shake-restored-depth-zero',flat)
    if time>8.6:
        def depth():assert app.renderer.program['u_volume_a'].value[0]==0.;app.capture('manual_depth_zero');app.request_tab='light'
        event('depth-zero-live',depth)
    if time>8.9:
        def light():
            app.edit_setting('volume','volume_depth',app.depth);app.sync();app.capture('manual_light')
            app.session.save();assert load_config(app.session.path)==app.cfg
        event('light-and-save-reload',light)
    if time>9.2:
        def inspect():app.clean=True;app.capture('manual_inspect')
        event('inspect',inspect)
    if time>9.5:
        def exit_inspect():
            from moderngl_window.context.base.keys import KeyModifiers
            k=app.wnd.keys;app.on_key_event(k.ESCAPE,k.ACTION_PRESS,KeyModifiers());app.on_key_event(k.ESCAPE,k.ACTION_RELEASE,KeyModifiers())
            assert not app.clean;app.choose_pose('happy');app.request_tab='shape'
        event('inspect-exit-happy',exit_inspect)
    if time>9.8:event('happy-capture',lambda:app.capture('manual_happy'))
    if time>=app.argv.smoke_seconds:
        durations=sorted(app.measured);report=dict(gpu=app.ctx.info['GL_RENDERER'],events=app.events,average_fps=len(durations)/sum(durations),p95_ms=durations[int(len(durations)*.95)]*1000,visual_acceptance='Pending user review')
        (ROOT/'test_output/upgrade/window_smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2),flush=True);app.wnd.close()

def tick_input(app,time):
    """Clipboard regression in the real ImGui window, using ordinary text values.

    Writes no report or screenshots; restores the user's clipboard on exit.
    """
    from moderngl_window.context.base.keys import KeyModifiers
    io=imgui.get_io()
    def check(condition,message):
        if not condition:
            print('INPUT DEBUG',app.input_steps[app.input_index][0],io.want_text_input,app.clean,flush=True)
            raise AssertionError(message)
    def click(rect,button=0):
        x0,y0,x1,y1=app.ui_rects[rect]
        io.add_mouse_pos_event((x0+x1)/2,(y0+y1)/2)
        io.add_mouse_button_event(button,True);io.add_mouse_button_event(button,False)
    def key(name,ctrl=False,shift=False,alt=False):
        modifiers=KeyModifiers();modifiers.ctrl=ctrl;modifiers.shift=shift;modifiers.alt=alt
        code=getattr(app.wnd.keys,name)
        app.on_key_event(code,app.wnd.keys.ACTION_PRESS,modifiers)
        app.on_key_event(code,app.wnd.keys.ACTION_RELEASE,modifiers)
        if ctrl or shift or alt:
            app.on_key_event(app.wnd.keys.LEFT_CTRL,app.wnd.keys.ACTION_RELEASE,KeyModifiers())
    if not hasattr(app,'input_steps'):
        app.input_original_clipboard=imgui.get_clipboard_text()
        app.input_steps=[];app.input_index=0;app.input_next=.25;app.input_passed=[]
        def step(name,fn):app.input_steps.append((name,fn))
        cases=[('Path','reference','路径',lambda:app.reference_path),('Pose name','shape','名称',lambda:app.name_buffer)]
        for name,panel,label,getter in cases:
            def setup(n=name,p=panel):
                app.request_tab=p
                if n=='Pose name':app.open_dialog('new')
            step(name+' focus panel',setup)
            step(name+' focus text',lambda l=label:click('text:'+l))
            step(name+' Ctrl+A',lambda:key('A',ctrl=True))
            def paste():imgui.set_clipboard_text('dummy-中英-123');key('V',ctrl=True)
            step(name+' Ctrl+V',paste)
            step(name+' paste verified',lambda g=getter:check(g()=='dummy-中英-123' and not app.clean,'Ctrl+V text/Inspect conflict'))
            step(name+' select for replacement',lambda:key('A',ctrl=True))
            def replace():imgui.set_clipboard_text('替换 selected ABC');key('V',ctrl=True)
            step(name+' replace selection',replace)
            step(name+' Ctrl+A replacement verified',lambda g=getter:check(g()=='替换 selected ABC' and not app.clean,'Ctrl+A did not select entire input'))
            step(name+' select for copy',lambda:key('A',ctrl=True))
            step(name+' Ctrl+C',lambda:key('C',ctrl=True))
            step(name+' copy verified',lambda:check(imgui.get_clipboard_text()=='替换 selected ABC' and not app.clean,'Ctrl+C clipboard/Inspect conflict'))
            step(name+' Ctrl+X',lambda:key('X',ctrl=True))
            step(name+' cut verified',lambda g=getter:check(g()=='' and imgui.get_clipboard_text()=='替换 selected ABC' and not app.clean,'Ctrl+X failed'))
            step(name+' restore via Ctrl+V',lambda:key('V',ctrl=True))
            # Bare V while typing must be input, not a global shortcut.
            step(name+' end of text',lambda:key('END'))
            def type_v():key('V');app.on_unicode_char_entered('v')
            step(name+' plain V in text',type_v)
            step(name+' plain V stays in text',lambda g=getter:check(g()=='替换 selected ABCv' and not app.clean,'Plain V while typing triggered Inspect'))
            step(name+' right click',lambda l=label:click('text:'+l,1))
            def choose_all():click('text-menu-all')
            step(name+' context Select All',choose_all)
            step(name+' reopen context',lambda l=label:click('text:'+l,1))
            def context_paste():imgui.set_clipboard_text('右键 Paste 完成');click('text-menu-paste')
            step(name+' context Paste',context_paste)
            step(name+' context paste verified',lambda g=getter:check(g()=='右键 Paste 完成' and not app.clean,'Context Paste did not replace selection'))
            step(name+' context select start',lambda l=label:click('text:'+l,1))
            step(name+' context Select All again',lambda:click('text-menu-all'))
            step(name+' context copy open',lambda l=label:click('text:'+l,1))
            step(name+' context Copy',lambda:click('text-menu-copy'))
            step(name+' context Copy verified',lambda:check(imgui.get_clipboard_text()=='右键 Paste 完成','Context Copy failed'))
            step(name+' context cut open',lambda l=label:click('text:'+l,1))
            step(name+' context Cut',lambda:click('text-menu-cut'))
            step(name+' context Cut verified',lambda g=getter:check(g()=='' and imgui.get_clipboard_text()=='右键 Paste 完成','Context Cut failed'))
            if name=='Path':
                long_text='用于验证自动换行与光标选区的长中文路径内容/'*35
                def paste_long(text=long_text):imgui.set_clipboard_text(text);key('V',ctrl=True)
                step('Paste long Chinese',paste_long)
                def verify_long(text=long_text):
                    check(app.reference_path==text,'Soft wrap changed the logical value')
                    layout=app.text_layouts['路径'];check(layout['lines']>10,'Long Chinese did not wrap')
                    check(all(imgui.calc_text_size(line).x<=layout['width']+1 for line in layout['display'].split('\n')),'Line exceeds wrapping width')
                step('Wrapped Chinese and vertical overflow verified',verify_long)
                step('Long Chinese start',lambda:key('HOME',ctrl=True))
                step('Long Chinese next visual line',lambda:key('DOWN'))
                step('Long Chinese visual line start',lambda:key('HOME'))
                def delete_wrap():
                    app.wrap_boundary=len(app.text_layouts['路径']['display'].split('\n')[0]);key('BACKSPACE')
                step('Backspace across visual wrap',delete_wrap)
                step('Wrap boundary edits logical character',lambda text=long_text:check(app.reference_path==text[:app.wrap_boundary-1]+text[app.wrap_boundary:],'Backspace consumed only a layout newline'))
                step('Select wrapped edited value',lambda:key('A',ctrl=True))
                step('Restore long Chinese',paste_long)
                step('Long Chinese select all',lambda:key('A',ctrl=True))
                step('Long Chinese copy',lambda:key('C',ctrl=True))
                step('Long Chinese clipboard preserved',lambda text=long_text:check(imgui.get_clipboard_text()==text,'Copy included visual line breaks'))
                step('Long Chinese cut',lambda:key('X',ctrl=True))
                step('Long Chinese cut verified',lambda:check(app.reference_path=='','Cut failed after wrap'))
            if name=='Pose name':step('Close name dialog without saving',lambda:click('cancel-dialog'))
        def blur():
            app.request_tab='shape';io.add_mouse_pos_event(500,400)
            io.add_mouse_button_event(0,True);io.add_mouse_button_event(0,False)
        step('Blur all text inputs',blur)
        step('Plain V enters Inspect',lambda:key('V'))
        step('Inspect entered',lambda:check(app.clean,'Bare V no longer enters Inspect'))
        step('Plain V exits Inspect',lambda:key('V'))
        step('Inspect exited',lambda:check(not app.clean,'Bare V no longer exits Inspect'))
        for mod in ('ctrl','shift','alt'):
            step(mod+' V ignored globally',lambda m=mod:key('V',**{m:True}))
            step(mod+' V verified',lambda:check(not app.clean,'Modified V toggled Inspect'))
        step('Final global Esc not requested',lambda:check(not app.close_requested,'A text shortcut closed the app'))
    if time>=app.input_next and app.input_index<len(app.input_steps):
        name,fn=app.input_steps[app.input_index]
        try:fn()
        except Exception:
            imgui.set_clipboard_text(app.input_original_clipboard)
            print('INPUT TEST FAILED: '+name,flush=True);raise
        app.input_passed.append(name);app.input_index+=1;app.input_next=time+.16
    if app.input_index==len(app.input_steps):
        imgui.set_clipboard_text(app.input_original_clipboard)
        print(json.dumps(dict(input_checks=len(app.input_passed),passed=app.input_passed,
            result='PASS',scope='Real GPU window, native window key callbacks, ImGui mouse events and OS clipboard; ordinary fields and real OS clipboard; no personal configuration save'),ensure_ascii=True,indent=2),flush=True)
        app.wnd.close()
    elif time>=app.argv.smoke_seconds:
        imgui.set_clipboard_text(app.input_original_clipboard)
        raise AssertionError('Input smoke timeout at '+app.input_steps[app.input_index][0])
