"""Real GPU/UI regression. HTTP/STT fixtures are explicitly simulated, never real AI."""
from copy import deepcopy
import json
from imgui_bundle import imgui
from fulu_visual.config import ROOT,load_config
from tests.test_closeout import ProviderTests

def tick(app,time):
    io=imgui.get_io()
    def event(name,fn):
        if name not in app.smoke_done:
            fn();app.smoke_done.add(name);app.events.append(name)
    def down(name):
        x0,y0,x1,y1=app.ui_rects[name];io.add_mouse_pos_event((x0+x1)/2,(y0+y1)/2);io.add_mouse_button_event(0,True)
    def up():io.add_mouse_button_event(0,False)
    if time>.2:
        def disconnected():
            app.choose_pose('normal');app.ai_connected=False;app.request_tab='derive'
            app.protected=deepcopy(app.cfg['poses']['normal']);app.before_count=len(app.cfg['poses'])
        event('disconnected-panel',disconnected)
    if time>.4:
        def hidden():
            assert 'eye-input' not in app.ui_rects and 'apply' not in app.ui_rects
            app.capture('ai_disconnected');app.request_tab='shape'
        event('no-fake-ai-controls',hidden)
    if time>.6:event('seed-down',lambda:down('seed-rectangle'))
    if time>.72:event('seed-up',up)
    if time>.95:
        def contour():
            assert app.selected!='normal';assert 'contour' in app.cfg['poses'][app.selected]['shape']
            assert app.cfg['poses']['normal']==app.protected
            app.contour_id=app.selected;app.contour_before=deepcopy(app.cfg['poses'][app.selected]['shape'])
            x0,y0,x1,y1=app.ui_rects['contour-pad'];io.add_mouse_pos_event(x1-8,y0+8);io.add_mouse_button_event(0,True)
        event('protected-seed-and-point-down',contour)
    if time>1.1:
        def drag():
            x0,y0,x1,y1=app.ui_rects['contour-pad'];io.add_mouse_pos_event(x1-42,y0+32)
        event('contour-drag',drag)
    if time>1.25:event('point-up',up)
    if time>1.5:
        def edited():
            assert app.cfg['poses'][app.selected]['shape']!=app.contour_before
            app.capture('contour_editor');app.session.undo();app.sync()
            assert app.cfg['poses'][app.selected]['shape']==app.contour_before
            app.session.redo();app.sync();app.session.save_pose(app.selected)
            assert load_config(app.session.path)['poses'][app.selected]['shape']==app.cfg['poses'][app.selected]['shape']
            ProviderTests.setUpClass();app.test_http=ProviderTests
            app.ai_settings.data['profiles']['OpenAI'].update(model='edit',endpoint=ProviderTests.endpoint)
            app.ai_settings.key=lambda name=None:'local-protocol-test-key'
            app.request_tab='derive';app.test_ai_connection()
        event('drag-undo-redo-save-and-local-http-connect',edited)
    if time>1.9:
        def focus():
            assert app.ai_connected;down('eye-input')
        event('unified-input-down',focus)
    if time>2.05:
        def typing():up();io.add_input_characters_utf8('再扁一点，保持宽度')
        event('real-ui-chinese-typing',typing)
    if time>2.3:event('apply-down',lambda:down('apply'))
    if time>2.42:event('apply-up',up)
    if time>2.75:
        def applied():
            assert app.selected==app.contour_id and app.last_intent['operations']
            assert app.ai_input=='再扁一点，保持宽度'
            app.import_ai_image(ROOT/'test_output/upgrade/ai_disconnected_eyes.png')
            app.ai_settings.data['profiles']['OpenAI']['model']='contour';app.ai_input='提取眼睛轮廓'
        event('current-eye-text-apply-then-image-input',applied)
    if time>2.95:event('image-apply-down',lambda:down('apply'))
    if time>3.08:event('image-apply-up',up)
    if time>3.4:
        def image_result():
            assert app.last_intent['contours'];assert app.selected==app.contour_id
            assert app.test_http.requests[-1][1]['messages'][1]['content'][1]['type']=='image_url'
            app.capture('ai_image_contour');app.ai_image=None
            app.ai_settings.data['stt_provider']='Custom'
            app.ai_settings.data['profiles']['STT'].update(endpoint=ProviderTests.endpoint,model='test')
            app.speech.record=lambda seconds=10.:b'RIFF-test-only-audio'
            app.voice_before=deepcopy(app.cfg);app.ai_input=''
        event('mock-image-return-is-editable-contour',image_result)
    if time>3.65:event('mic-down',lambda:down('microphone'))
    if time>3.78:event('mic-up',up)
    if time>4.1:
        def transcript():
            assert not app.speech_busy and app.ai_input=='圆一点，两边不要尖'
            assert app.cfg==app.voice_before
            app.capture('stt_same_input_mock');app.reference_path=str(ROOT/'test_output/upgrade/ai_disconnected_eyes.png');app.request_tab='reference'
        event('stt-protocol-to-same-input-no-auto-apply',transcript)
    if time>4.4:event('reference-down',lambda:down('reference-import'))
    if time>4.52:event('reference-up',up)
    if time>4.8:
        def reference():
            assert app.reference.texture and app.cfg['reference']['enabled'];app.capture('reference_overlay')
            app.edit_setting('reference','side_by_side',True)
        event('reference-overlay',reference)
    if time>5.1:
        def runtime():
            app.capture('reference_comparison');app.edit_setting('reference','enabled',False)
            app.choose_pose('normal');app.request_tab='runtime';app.runtime_choice='happy'
        event('existing-reference-comparison-and-runtime-panel',runtime)
    if time>5.4:event('runtime-play-down',lambda:down('runtime-play'))
    if time>5.52:event('runtime-play-up',up)
    if app.mode=='runtime' and app.runtime.target=='happy' and .46<=app.runtime.progress<.9:
        def interrupt():
            before=deepcopy(app.runtime.current);app.play_runtime_pose(app.contour_id)
            assert app.runtime.current==before and app.runtime.start==before
        event('interrupt-at-46-percent-from-rendered-state',interrupt)
    if time>6.7:
        def arrived():
            assert 'interrupt-at-46-percent-from-rendered-state' in app.smoke_done
            assert app.runtime.target==app.contour_id and app.runtime.progress==1
            assert all('semantic-'+name not in app.ui_rects for name in ('NORMAL','HAPPY','SAD'))
            app.capture('runtime_contour');app.dispatch_runtime('Look Left')
        event('runtime-dropdown-actual-pose-reached',arrived)
    if time>7.15:
        def held():
            assert app.runtime.gaze== -1.;app.capture('gaze_hold');app.dispatch_runtime('Center')
            assert app.runtime.gaze== -1.
        event('gaze-visible-hold-and-smooth-center',held)
    if time>7.8:
        def centered():
            assert app.runtime.gaze==0;app.dispatch_runtime('Shake');app.capture('runtime_page')
            app.choose_pose('normal');app.request_tab='volume'
            app.saved_depth=app.cfg['volume']['volume_depth'];app.edit_setting('volume','volume_depth',0.);app.sync()
        event('center-completed-and-depth-zero',centered)
    if time>8.1:
        def flat():
            assert app.renderer.program['u_volume_a'].value[0]==0.;app.capture('depth_zero');app.request_tab='light'
        event('flat-depth-zero-capture',flat)
    if time>8.4:
        def light():
            app.capture('light_panel');app.edit_setting('volume','volume_depth',app.saved_depth);app.sync()
            app.request_tab='settings'
        event('light-five-controls-and-restore-depth',light)
    if time>8.7:
        def inspect():
            app.capture('settings_stt');app.clean=True
        event('settings-existing-page-and-inspect',inspect)
    if time>9.:
        def exit_inspect():
            from moderngl_window.context.base.keys import KeyModifiers
            k=app.wnd.keys;app.on_key_event(k.ESCAPE,k.ACTION_PRESS,KeyModifiers());app.on_key_event(k.ESCAPE,k.ACTION_RELEASE,KeyModifiers())
            assert not app.clean;app.session.save();assert load_config(app.session.path)==app.cfg
            app.ai_settings.data['profiles']['OpenAI']['model']='offline';app.test_ai_connection();app.request_tab='derive'
        event('inspect-exit-and-save-load',exit_inspect)
    if time>9.5:
        def offline():
            assert not app.ai_connected and 'apply' not in app.ui_rects
            app.session.edit('poses.normal.shape','eye_height',.25);app.sync()
            assert app.cfg['poses']['normal']['shape']['eye_height']==.25
            app.session.load_pose('normal');app.sync();app.choose_pose(app.contour_id);app.request_tab='shape'
        event('http-offline-hides-ai-manual-editing-works',offline)
    if time>10:event('final-capture',lambda:app.capture('contour_workbench'))
    if time>=app.argv.smoke_seconds:
        durations=sorted(app.measured)
        report=dict(gpu=app.ctx.info['GL_RENDERER'],events=app.events,average_fps=len(durations)/sum(durations),p95_ms=durations[int(len(durations)*.95)]*1000,
            real_window=True,ai='Local mock HTTP protocol only; no real model/key',stt='Mock audio + local HTTP transcription protocol; no human microphone validation',visual_acceptance='Pending user review')
        (ROOT/'test_output/upgrade/window_smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        app.test_http.tearDownClass();print(json.dumps(report,indent=2),flush=True);app.wnd.close()
