"""Actual-window input regression for the small Visual Elements increment."""
from copy import deepcopy
import json
from imgui_bundle import imgui
from fulu_visual.config import ROOT,load_config,ACCENT_DEFAULTS
from fulu_visual.visual_elements import world_bounds

def tick(app,time):
    io=imgui.get_io()
    def event(name,fn):
        if name not in app.smoke_done:
            fn();app.smoke_done.add(name);app.events.append(name)
    def down(name,fraction=.5):
        x0,y0,x1,y1=app.ui_rects[name]
        io.add_mouse_pos_event(x0+(x1-x0)*fraction,(y0+y1)/2)
        io.add_mouse_button_event(0,True)
    def up():io.add_mouse_button_event(0,False)
    def key(code):
        from moderngl_window.context.base.keys import KeyModifiers
        app.on_key_event(code,app.wnd.keys.ACTION_PRESS,KeyModifiers())
        app.on_key_event(code,app.wnd.keys.ACTION_RELEASE,KeyModifiers())
    def canvas_pos(x,y):
        x0,y0,x1,y1=app.ui_rects['canvas']
        factor=min(y1-y0,(x1-x0)/app.cfg['display']['design_aspect'])
        return (x0+x1)/2+x*factor,(y0+y1)/2-y*factor
    if time>.2:
        def start():
            app.before_accent=deepcopy(app.cfg)
            app.request_tab='accent'
        event('show-accent-tab',start)
    if time>.5:event('open-type-combo',lambda:down('accent-type'))
    if time>.65:event('release-type-combo',up)
    if time>.8:event('combo-question-down',lambda:down('accent-choice-QUESTION'))
    if time>1.:event('combo-question-up',up)
    if time>1.5:
        def visible():
            assert app.cfg['accent']['type']=='QUESTION' and app.cfg['accent']['enabled']
            app.capture('question_workbench')
        event('question-selected-through-ui',visible)
    if time>1.7:
        def drag_down():
            a=app.cfg['accent']
            io.add_mouse_pos_event(*canvas_pos(a['position']['x'],a['position']['y']))
            io.add_mouse_button_event(0,True)
        event('drag-element-down',drag_down)
    if time>1.9:
        def drag_move():
            io.add_mouse_pos_event(*canvas_pos(2.,2.))
        event('drag-beyond-screen',drag_move)
    if time>2.1:event('drag-element-up',up)
    if time>2.4:
        def drag_check():
            x0,x1,y0,y1=world_bounds(app.cfg['accent'])
            assert x1<=app.cfg['display']['design_aspect']/2-app.cfg['display']['safe_margin']
            assert y1<=.5-app.cfg['display']['safe_margin']
            assert app.cfg['accent']['position']!=ACCENT_DEFAULTS['position']
            app.session.undo();app.sync()
            assert app.cfg['accent']['position']==ACCENT_DEFAULTS['position']
        event('drag-clamp-and-single-undo',drag_check)
    if time>2.6:event('position-slider-down',lambda:down('x',.65))
    if time>2.8:event('position-slider-up',up)
    if time>3:
        def position_check():
            assert app.cfg['accent']['position']['x']!=ACCENT_DEFAULTS['position']['x']
            app.session.undo();app.sync()
        event('position-slider-live',position_check)
    if time>3.2:event('play-button-down',lambda:down('accent-play'))
    if time>3.35:event('play-button-up',up)
    if 3.4<time<5.1:
        if not hasattr(app,'accent_phases'):app.accent_phases=set()
        app.accent_phases.add(app.accent_animation.phase)
    if time>5.1:
        def played():
            assert {'ENTER','HOLD','EXIT','DONE'}<=app.accent_phases,app.accent_phases
            assert app.accent_animation.sample()[0]==0.
            app.accent_animation.play()
        event('full-lifecycle-through-existing-frame-time',played)
    if time>5.3:event('pause-button-down',lambda:down('accent-pause'))
    if time>5.45:event('pause-button-up',up)
    if time>5.6:
        def paused():
            assert app.accent_animation.paused
            app.paused_accent_cursor=app.accent_animation.cursor
        event('pause-cursor-captured',paused)
    if time>5.9:
        def still_paused():
            assert app.accent_animation.cursor==app.paused_accent_cursor
            down('accent-resume')
        event('pause-stable-and-resume-down',still_paused)
    if time>6.05:event('resume-up',up)
    if time>6.2:
        def resumed():
            assert app.accent_animation.cursor>app.paused_accent_cursor
            down('accent-animation-reset')
        event('resume-continues-and-animation-reset-down',resumed)
    if time>6.35:event('animation-reset-up',up)
    if time>6.6:
        def reset_anim():
            assert app.accent_animation.phase=='EDIT'
            assert app.accent_animation.sample()==(1.,1.)
            app.session.edit_accent(type='EXCLAMATION',scale=2.8,rotation=55.,
                                   position=dict(x=.8,y=.45))
            app.sync();app.show_safe=True;app.choose_pose('happy')
        event('animation-reset-and-rotated-exclamation',reset_anim)
    if time>7:event('safe-bounds-capture',lambda:app.capture('exclamation_safe_bounds'))
    if time>7.2:
        def inspect():
            renderer=app.renderer
            key(app.wnd.keys.V);assert app.clean
            key(app.wnd.keys.F);assert app.flat
            app.inspected_renderer=renderer
        event('inspect-flat-with-accent',inspect)
    if time>7.5:event('inspect-capture',lambda:app.capture('accent_inspect'))
    if time>7.7:
        def return_from_inspect():
            key(app.wnd.keys.ESCAPE);assert not app.clean
            key(app.wnd.keys.F);assert not app.flat
            assert app.renderer is app.inspected_renderer
            app.reset_snapshot=deepcopy(app.cfg)
        event('inspect-exit',return_from_inspect)
    if time>7.9:event('reset-accent-down',lambda:down('reset-accent'))
    if time>8.05:event('reset-accent-up',up)
    if time>8.25:
        def reset_scope():
            assert app.cfg['accent']==ACCENT_DEFAULTS
            for section in app.cfg:
                if section!='accent':assert app.cfg[section]==app.reset_snapshot[section]
            app.session.undo();app.sync()
            assert app.cfg==app.reset_snapshot
            app.session.save()
            assert load_config(app.session.path)==app.cfg
        event('accent-reset-isolated-undo-save-load',reset_scope)
    if time>8.4:
        def concurrent():
            app.session.edit_accent(type='QUESTION',scale=1.,rotation=0.,position=dict(x=.53,y=.28))
            app.sync();app.accent_animation.play();app.toggle_play()
        event('concurrent-eye-and-accent-preview',concurrent)
    if time>8.8:
        def check_concurrent():
            assert not app.player.paused and app.player.cursor>0
            assert app.accent_animation.cursor>0
            app.capture('composition_animation')
        event('both-use-same-frame-delta',check_concurrent)
    if time>9.3:
        def no_mutations():
            for group in ('poses','volume','motion'):
                assert app.cfg[group]==app.before_accent[group]
            app.player.pause();app.mode='edit';app.choose_pose('normal')
            app.accent_animation.reset()
            app.session.save()
        event('eyes-shapes-material-motion-preserved',no_mutations)
    if time>9.7:event('final-accent-workbench',lambda:app.capture('accent_final'))
    if time>=app.argv.smoke_seconds:
        durations=sorted(app.measured)
        report=dict(gpu=app.ctx.info['GL_RENDERER'],events=app.events,
            lifecycle_phases=sorted(app.accent_phases),
            frames=len(durations),average_fps=len(durations)/sum(durations),
            p95_ms=durations[int((len(durations)-1)*.95)]*1000,
            input_method='Actual ImGui combo, slider, drag and button events; window key callbacks',
            config_path=str(app.session.path),visual_acceptance='engineering preview only; user review pending')
        (ROOT/'test_output/accent/window_smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2),flush=True)
        app.wnd.close()

