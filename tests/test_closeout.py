from copy import deepcopy
from pathlib import Path
import json,math,tempfile,threading,time,unittest,hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from types import SimpleNamespace
import numpy as np,moderngl
from fulu_visual.config import ROOT,DEFAULTS,TuningSession,load_config,save_config,validate_shape,SHAPE_PARAMETERS,EYE_PARAMETERS
from fulu_visual.geometry import EYE_DEFAULTS,mix_shape
from fulu_visual.rig import EyeRig
from fulu_visual.renderer import EyeRenderer
from fulu_visual.visual_elements import clamp_accent,element_frame
from fulu_visual.element_renderer import VisualElementRenderer
from fulu_visual.eye_intent import context,validate_intent,solve,apply_intent,rule_intent
from fulu_visual.ai_settings import AISettings,PROVIDERS
from fulu_visual.ai_provider import AIProvider
from fulu_visual.ai_ui import AIWorkbench
from fulu_visual.runtime import VisualRuntime
from fulu_visual.extensions import EYE_EXTENSION_DEFAULTS,ACCENT_REGISTRY,import_accent_manifest
from fulu_visual.export_tools import export_source

def intent(section='shape',parameter='eye_height',op='multiply',value=.8):
    return dict(label='',operations=[dict(section=section,parameter=parameter,op=op,value=value)])

class EyeSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=deepcopy(DEFAULTS);cls.ctx=moderngl.create_standalone_context(require=330)
        cls.renderer=EyeRenderer(cls.ctx,cls.cfg);cls.element=VisualElementRenderer(cls.ctx)
        cls.fb=cls.ctx.simple_framebuffer((960,540),components=3)
    @classmethod
    def tearDownClass(cls):
        cls.renderer.release();cls.element.release();cls.fb.release();cls.ctx.release()
    def draw(self,shape):
        validate_shape(shape,self.cfg['display'])
        self.renderer.render(EyeRig(self.cfg).shape_frame(shape,0),self.fb)
        return np.frombuffer(self.fb.read(components=3,alignment=1),np.uint8).reshape(540,960,3).copy()
    def test_confirmed_current_pixels_exact(self):
        cfg=load_config();self.renderer.configure(cfg)
        try:
            for pid in ('normal','happy'):
                baseline=ROOT/('test_output/closeout/'+pid+'_before.npy')
                if not baseline.exists():self.skipTest('Private current visual baseline not exported')
                self.renderer.render(EyeRig(cfg).pose_frame(pid),self.fb)
                self.assertTrue(np.array_equal(np.frombuffer(self.fb.read(components=3,alignment=1),np.uint8),np.load(baseline)),pid)
        finally:self.renderer.configure(self.cfg)
    def test_every_zero_size_route_is_black(self):
        for key,value in (('eye_width',0),('eye_height',0),('thickness',0),('squash',1),('stretch',-1),('scale',0),('opacity',0)):
            shape=dict(DEFAULTS['poses']['normal']['shape'],**{key:value})
            self.assertFalse(self.draw(shape).any(),key)
    def test_happy_scale_and_opening_reach_zero(self):
        for value in (1.,.1,.001,0.):
            p=dict(DEFAULTS['poses']['happy']['shape'],scale=value)
            pixels=self.draw(p)
            if value==0:self.assertFalse(pixels.any())
    def test_left_disappears_right_unchanged(self):
        p=dict(DEFAULTS['poses']['normal']['shape']);base=self.draw(p)
        for key in ('left_opacity','left_width_scale','left_height_scale'):
            arr=self.draw(dict(p,**{key:0.}))
            self.assertFalse(arr[:,:480].any())
            self.assertTrue(np.array_equal(base[:,480:],arr[:,480:]))
    def test_distinct_realtime_entities_and_asymmetry(self):
        p=dict(DEFAULTS['poses']['normal']['shape'],left_height_scale=.3,right_rotation=25.)
        frame=EyeRig(self.cfg).shape_frame(p,0)
        self.assertIsNot(frame.eyes[0],frame.eyes[1]);self.assertIsNot(frame.eyes[0].shape,frame.eyes[1].shape)
        self.assertNotEqual(frame.eyes[0].shape['eye_height'],frame.eyes[1].shape['eye_height'])
        self.assertTrue(self.draw(p).any())
    def test_independent_zero_transition_interrupt(self):
        cfg=deepcopy(DEFAULTS);s=TuningSession(cfg);pid=s.create('TEST')
        s.config['poses'][pid]['shape'].update(left_opacity=0.,right_height_scale=.6,position_x=.01)
        runtime=VisualRuntime(s.config);runtime.retarget(pid);runtime.advance(runtime.duration*.46)
        current=deepcopy(runtime.current);frame=runtime.frame()
        runtime.retarget('happy');self.assertEqual(runtime.current,current);self.assertEqual(frame.eyes,runtime.frame().eyes)
        runtime.advance(runtime.duration);self.assertEqual(runtime.current,s.config['poses']['happy']['shape'])
    def test_optional_keys_save_load_roundtrip(self):
        cfg=deepcopy(DEFAULTS);cfg['poses']['happy']['shape'].update(left_opacity=0.,right_x=.04,scale=.8)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'cfg.json';save_config(cfg,path);self.assertEqual(cfg,load_config(path))
    def test_ranges_and_finite_guard(self):
        ranges={k:(lo,hi) for k,_,lo,hi,_ in SHAPE_PARAMETERS}
        self.assertEqual(ranges['eye_width'],(0.,3.));self.assertEqual(ranges['squash'],(0.,1.))
        self.assertEqual(ranges['stretch'],(-1.,8.));self.assertGreater(ranges['whole_bend'][1],1.5)
        for key in list(EYE_DEFAULTS)+['eye_width']:
            p=dict(DEFAULTS['poses']['normal']['shape'],**{key:float('nan')})
            with self.assertRaises(ValueError):validate_shape(p)
    def test_all_control_extremes_do_not_crash(self):
        count=0
        for key,_,lo,hi,_ in SHAPE_PARAMETERS+EYE_PARAMETERS:
            for value in (lo,hi):
                p=dict(DEFAULTS['poses']['normal']['shape'],**{key:value})
                try:validate_shape(p)
                except ValueError:continue
                self.draw(p);count+=1
        self.assertGreater(count,30)
    def test_accent_zero_scale_and_safe_large_scale(self):
        base=self.draw(DEFAULTS['poses']['normal']['shape'])
        for kind in ACCENT_REGISTRY:
            a=deepcopy(DEFAULTS['accent']);a.update(type=kind,enabled=True,scale=0.)
            a=clamp_accent(a,DEFAULTS['display'])
            self.element.render(element_frame(a),self.fb,DEFAULTS['display'],True)
            self.assertTrue(np.array_equal(base,np.frombuffer(self.fb.read(components=3,alignment=1),np.uint8).reshape(540,960,3)))
            a.update(scale=10.,rotation=620.);a['position']={'x':2.,'y':-2.}
            a=clamp_accent(a,DEFAULTS['display']);f=element_frame(a)
            self.assertLessEqual(f.bounds[1],DEFAULTS['display']['design_aspect']/2-.04)
            self.assertGreaterEqual(f.bounds[2],-.46)
    def test_extension_seams_disabled(self):
        self.assertEqual(set(EYE_EXTENSION_DEFAULTS),{'Brow','Eyelash','Pupil','Iris','Highlight','Style','Realism'})
        self.assertFalse(any(EYE_EXTENSION_DEFAULTS.values()))
        self.assertEqual(set(ACCENT_REGISTRY),{'QUESTION','EXCLAMATION'})
        m=import_accent_manifest(dict(name='future',kind='vector_plugin',version=1))
        self.assertFalse(m['enabled']);self.assertEqual(len(ACCENT_REGISTRY),2)

class IntentTests(unittest.TestCase):
    def setUp(self):self.cfg=deepcopy(DEFAULTS)
    def test_protected_builtins_and_same_result_refinement(self):
        s=TuningSession(self.cfg);pid,_=apply_intent(s,'normal',intent())
        self.assertEqual(s.config['poses']['normal'],self.cfg['poses']['normal'])
        self.assertEqual(s.config['poses']['happy'],self.cfg['poses']['happy'])
        old=s.config['poses'][pid]['shape']['eye_height'];size=len(s.config['poses'])
        again,_=apply_intent(s,pid,intent());self.assertEqual(again,pid)
        self.assertEqual(len(s.config['poses']),size);self.assertLess(s.config['poses'][pid]['shape']['eye_height'],old)
    def test_no_accent_or_code_or_extra_fields(self):
        for payload in (intent('accent','opacity'),dict(label='',operations=[],code='bad'),intent('shape','pupil'),intent(value=float('inf'))):
            with self.assertRaises(ValueError):validate_intent(payload)
    def test_transactional_rejection_and_undo(self):
        s=TuningSession(self.cfg)
        with self.assertRaises(ValueError):apply_intent(s,'normal',intent('accent','scale'))
        self.assertEqual(s.config,self.cfg)
        apply_intent(s,'normal',intent());s.undo();self.assertEqual(s.config,self.cfg)
    def test_solver_bounds_and_separate_eye(self):
        cfg,strength=solve(self.cfg,'normal',intent('left','opacity','set',-999))
        self.assertEqual(cfg['poses']['normal']['shape']['left_opacity'],0)
        self.assertEqual(cfg['accent'],self.cfg['accent']);self.assertEqual(cfg['volume'],self.cfg['volume'])
    def test_rules_explicit_limited_and_known_phrases(self):
        for prompt in ('开心','再扁一点','圆一点，两边不要那么尖','眼睛消失'):
            self.assertTrue(rule_intent(prompt,context(self.cfg,'normal'),self.cfg['poses'])['operations'])
        with self.assertRaises(ValueError):rule_intent('这是未支持的未知描述',context(self.cfg,'normal'))
    def test_ai_intent_zero_is_not_fitted_away(self):
        cfg,strength=solve(self.cfg,'normal',intent(parameter='eye_width',op='set',value=0))
        self.assertEqual(strength,1);self.assertEqual(cfg['poses']['normal']['shape']['eye_width'],0)
    def test_runtime_snapshot_is_interpreted_without_replacing_builtins(self):
        s=TuningSession(self.cfg);snapshot=dict(self.cfg['poses']['normal']['shape'],eye_height=.15)
        pid,_=apply_intent(s,'normal',intent(),base_shape=snapshot)
        self.assertAlmostEqual(s.config['poses'][pid]['shape']['eye_height'],.12)
        self.assertEqual(s.config['poses']['normal'],self.cfg['poses']['normal'])
    def test_empty_and_bad_labels_rejected(self):
        for label in ('LOW_ROOT','VERY_HAPPY'):
            payload=intent();payload['label']=label
            with self.assertRaises(ValueError):validate_intent(payload)
        with self.assertRaises(ValueError):solve(self.cfg,'normal',dict(label='',operations=[]))

class ProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length=int(self.headers.get('Content-Length',0));rawbody=self.rfile.read(length)
                if self.path.endswith('/audio/transcriptions'):
                    cls.requests.append((self.path,rawbody));raw=json.dumps({'text':'圆一点，两边不要尖'}).encode()
                    self.send_response(200);self.end_headers();self.wfile.write(raw);return
                body=json.loads(rawbody)
                cls.requests.append((self.path,body))
                if body['model']=='offline':self.send_response(503);self.end_headers();return
                answer=intent('accent','scale') if body['model']=='invalid' else dict(label='',operations=[]) if body['model']=='test' else intent()
                if body['model']=='contour':answer=contour_intent()
                raw=json.dumps(dict(choices=[dict(message=dict(content=json.dumps(answer)))])).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
            def log_message(self,*args):pass
        cls.requests=[];cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.endpoint='http://127.0.0.1:'+str(cls.server.server_port)+'/v1'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def provider(self,name='OpenAI',model='test'):
        return AIProvider(dict(provider=name,endpoint=self.endpoint,model=model,key='test-only-not-a-real-key',timeout=2,fallback=False))
    def test_all_provider_protocols_on_mock_http_not_real_ai(self):
        for name in ('OpenAI','DeepSeek','Local AI','Custom'):
            self.assertEqual(self.provider(name).test(),dict(label='',operations=[]))
            path,payload=self.requests[-1]
            self.assertEqual(path,'/v1/chat/completions')
            self.assertEqual(payload['response_format']['type'],'json_schema' if name=='OpenAI' else 'json_object')
    def test_image_to_contour_contract_on_mock_http(self):
        from fulu_visual.reference import ReferenceImage
        image=ReferenceImage();image.load(ROOT/'baseline/normal.png');before=image.path.read_bytes()
        result=self.provider(model='contour').interpret('提取轮廓',{},image.ai_payload())
        self.assertTrue(result['contours']);self.assertEqual(image.path.read_bytes(),before)
        payload=self.requests[-1][1]['messages'][1]['content']
        self.assertEqual(payload[1]['type'],'image_url');self.assertTrue(payload[1]['image_url']['url'].startswith('data:image/png;base64,'))
        s=TuningSession(deepcopy(DEFAULTS));pid,_=apply_intent(s,'normal',result)
        self.assertIn('contour',s.config['poses'][pid]['shape'])
    def test_stt_multipart_protocol_not_real_recognition(self):
        from fulu_visual.speech import STTProvider
        result=STTProvider(dict(provider='Custom',endpoint=self.endpoint,model='test',key='',timeout=2)).transcribe(b'RIFF-test-only')
        self.assertEqual(result,'圆一点，两边不要尖');body=self.requests[-1][1]
        self.assertIn(b'RIFF-test-only',body);self.assertIn(b'name="model"',body)
    def test_output_validation_precedes_solver(self):
        with self.assertRaises(ValueError):self.provider(model='invalid').interpret('x',{})
    def test_http_failure_is_explicit(self):
        with self.assertRaisesRegex(ValueError,'503'):self.provider(model='offline').test()
    def test_missing_credentials_no_call(self):
        settings=dict(provider='OpenAI',endpoint=self.endpoint,model='test',key='',timeout=2)
        with self.assertRaisesRegex(ValueError,'API Key'):AIProvider(settings).test()
    def test_settings_encrypted_save_reload_and_connect(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'settings.local.json';s=AISettings(path);s.set_key('fake-secret-for-DPAPI-test')
            s.data['profiles']['OpenAI'].update(endpoint=self.endpoint,model='test')
            s.save();self.assertNotIn('fake-secret-for-DPAPI-test',path.read_text(encoding='utf-8'))
            loaded=AISettings(path);self.assertEqual(loaded.key(),'fake-secret-for-DPAPI-test')
            self.assertTrue(loaded.data['auto_connect']);self.assertEqual(AIProvider(loaded.connection()).test()['operations'],[])
    def test_saved_preferences_auto_connect_on_workbench_start(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'ai.local.json';settings=AISettings(path)
            settings.set_key('mock-startup-key');settings.data['profiles']['OpenAI'].update(endpoint=self.endpoint,model='test');settings.save()
            app=Dummy(path);app.argv.smoke_seconds=0
            with patch('fulu_visual.ai_ui.AISettings',return_value=AISettings(path)):app.setup_ai()
            deadline=time.monotonic()+3
            while app.ai_busy and time.monotonic()<deadline:app.poll_ai();time.sleep(.005)
            self.assertTrue(app.ai_connected);self.assertFalse(app.ai_limited)
    def test_export_omits_local_settings_includes_speech(self):
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            with zipfile.ZipFile(export_source(d)) as z:names=z.namelist()
        self.assertIn('fulu_visual/speech_capture.ps1',names)
        self.assertFalse(any('.local.json' in n for n in names))

class Dummy(AIWorkbench):
    def __init__(self,path):
        self.session=TuningSession(deepcopy(DEFAULTS));self.argv=SimpleNamespace(smoke_seconds=1)
        self.status='';self.error=False;self.mode='edit';self.setup_ai()
        self.ai_settings=AISettings(path);self.ai_settings.data['provider']='OpenAI'
    @property
    def cfg(self):return self.session.config
    @property
    def selected(self):return self.cfg['selection']['selected']
    def choose_pose(self,pid):self.cfg['selection']['selected']=pid
    def attempt(self,fn,message=''):
        try:fn();self.status=message;return True
        except ValueError as exc:self.status=str(exc);self.error=True;return False

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=Dummy(Path(self.temp.name)/'ai.local.json')
        from unittest.mock import patch
        self.provider_patch=patch('fulu_visual.ai_ui.ProviderRegistry.create',return_value=SimpleNamespace(interpret=lambda *a,**kw:intent()))
        self.provider_patch.start();self.app.ai_connected=True
    def tearDown(self):self.provider_patch.stop();self.temp.cleanup()
    def finish(self):
        deadline=time.monotonic()+3
        while self.app.ai_busy and time.monotonic()<deadline:self.app.poll_ai();time.sleep(.005)
        self.assertFalse(self.app.ai_busy)
    def test_unified_input_repeat_apply(self):
        a=self.app;a.ai_input='开心';a.generate_apply();self.finish()
        first=a.selected;self.assertNotEqual(first,'normal');self.assertTrue(a.ai_connected);self.assertFalse(a.ai_limited)
        a.ai_input='再扁一点';a.generate_apply();self.finish();self.assertEqual(first,a.selected)
    def test_stale_result_does_not_overwrite_manual_edit(self):
        a=self.app;a.ai_input='再扁一点';a.generate_apply()
        a.session.edit('poses.normal.shape','corner_roundness',.6)
        self.finish();self.assertEqual(a.selected,'normal');self.assertEqual(a.cfg['poses']['normal']['shape']['corner_roundness'],.6)
        self.assertIn('丢弃',a.status)
    def test_disconnected_ai_has_no_rule_fallback(self):
        a=self.app;a.ai_connected=False;a.ai_input='再扁一点';before=deepcopy(a.cfg)
        with self.assertRaisesRegex(ValueError,'AI 未连接'):a.generate_apply()
        self.assertEqual(a.cfg,before)
    def test_offline_preserves_manual_editing(self):
        a=self.app;a.ai_connected=False;before=deepcopy(a.cfg);a.ai_input='再扁一点'
        with self.assertRaises(ValueError):a.generate_apply()
        self.assertEqual(before,a.cfg);a.session.edit('poses.normal.shape','eye_height',.2)
        self.assertEqual(a.cfg['poses']['normal']['shape']['eye_height'],.2)
    def test_speech_uses_same_input_and_never_applies(self):
        a=self.app;before=deepcopy(a.cfg);a.ai_input='';a.accept_transcript('再扁一点','')
        self.assertEqual(a.ai_input,'再扁一点');self.assertEqual(before,a.cfg)
        a.ai_input='手动输入';a.accept_transcript('开心','')
        self.assertEqual(a.ai_input,'手动输入 开心')
    def test_startup_connection_attempt_is_nonblocking(self):
        a=self.app;a.ai_settings.data['provider']='OpenAI';a.ai_settings.key=lambda name=None:''
        self.provider_patch.stop();a.test_ai_connection();self.finish();self.assertFalse(a.ai_connected)
    def test_corrupt_ai_config_does_not_block_startup(self):
        path=Path(self.temp.name)/'bad.json';path.write_text('{bad')
        settings=AISettings(path);self.assertTrue(settings.error)
        path.write_text('[]');self.assertTrue(AISettings(path).error)


def contour_intent(kind='rectangle',eye='shared'):
    from fulu_visual.geometry import seed_contour
    return dict(label='CONTOUR',operations=[],contours=[dict(eye=eye,points=[dict(x=x,y=y) for x,y in seed_contour(kind)])])

class ContourTests(unittest.TestCase):
    def test_closed_freeform_not_shape_enum_and_builtin_protection(self):
        s=TuningSession(deepcopy(DEFAULTS));pid,_=apply_intent(s,'normal',contour_intent())
        p=s.config['poses'][pid]['shape'];self.assertIn('contour',p);self.assertNotIn('type',p)
        p['contour'][0]=[.7,.9];validate_shape(p)
        self.assertEqual(s.config['poses']['normal'],DEFAULTS['poses']['normal'])
    def test_invalid_self_crossing_nonfinite_and_duplicate_rejected(self):
        from fulu_visual.geometry import validate_contour
        for points in ([[0,0],[1,1],[0,1],[1,0]],[[0,0],[0,0],[1,1]],[[0,0],[1,0],[0,float('nan')]]):
            with self.assertRaises(ValueError):validate_contour(points)
    def test_independent_contours_save_restart_and_undo(self):
        import subprocess,sys
        s=TuningSession(deepcopy(DEFAULTS));pid,_=apply_intent(s,'normal',contour_intent('triangle','left'))
        apply_intent(s,pid,contour_intent('circle','right'));expected=deepcopy(s.config)
        s.undo();self.assertNotIn('right_contour',s.config['poses'][pid]['shape']);s.redo();self.assertEqual(s.config,expected)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'library.json';s.save(path)
            code="from fulu_visual.config import load_config;import sys,json;print(json.dumps(load_config(sys.argv[1])['poses'][sys.argv[2]]['shape']))"
            shape=json.loads(subprocess.check_output([sys.executable,'-c',code,str(path),pid],cwd=ROOT))
            self.assertEqual(shape,expected['poses'][pid]['shape'])
    def test_contour_morph_and_interrupt_current_state(self):
        from fulu_visual.geometry import mix_shape
        s=TuningSession(deepcopy(DEFAULTS));pid,_=apply_intent(s,'normal',contour_intent('triangle'))
        r=VisualRuntime(s.config);r.retarget(pid);r.advance(r.duration*.46);before=deepcopy(r.current);frame=r.frame()
        r.retarget('happy');self.assertEqual(r.current,before);self.assertEqual(r.frame().eyes,frame.eyes)
        r.advance(r.duration);self.assertEqual(r.current,s.config['poses']['happy']['shape'])
    def test_depth_zero_flat_and_current_visual_unchanged(self):
        ctx=moderngl.create_standalone_context(require=330);cfg=load_config();renderer=EyeRenderer(ctx,cfg);fb=ctx.simple_framebuffer((960,540),components=3)
        try:
            for pid in ('normal','happy'):
                renderer.render(EyeRig(cfg).pose_frame(pid),fb)
                before=ROOT/('test_output/closeout/'+pid+'_contour_before.npy')
                if not before.exists():continue
                self.assertTrue(np.array_equal(np.load(before),np.frombuffer(fb.read(components=3,alignment=1),np.uint8)))
            cfg['volume']['volume_depth']=0.;renderer.configure(cfg);renderer.render(EyeRig(cfg).pose_frame('normal'),fb)
            pixels=np.frombuffer(fb.read(components=3,alignment=1),np.uint8).reshape(540,960,3)
            mask=pixels[:,:,2]>100
            for _ in range(4):mask=mask&np.roll(mask,1,0)&np.roll(mask,-1,0)&np.roll(mask,1,1)&np.roll(mask,-1,1)
            self.assertGreater(mask.sum(),1000);self.assertEqual(np.ptp(pixels[:,:,2][mask]),0)
            s=TuningSession(cfg)
            for kind in ('circle','rectangle','triangle'):
                pid,_=apply_intent(s,'normal',contour_intent(kind));renderer.render(EyeRig(s.config).pose_frame(pid),fb)
                base=fb.read(components=3,alignment=1);self.assertTrue(any(base))
                s.config['poses'][pid]['shape']['corner_roundness']=.8
                renderer.render(EyeRig(s.config).pose_frame(pid),fb)
                self.assertNotEqual(base,fb.read(components=3,alignment=1))
                s.config['poses'][pid]['shape']['scale']=0.;renderer.render(EyeRig(s.config).pose_frame(pid),fb)
                self.assertFalse(any(fb.read(components=3,alignment=1)))
        finally:renderer.release();fb.release();ctx.release()
    def test_gaze_moves_holds_returns_and_center_is_continuous(self):
        r=VisualRuntime(deepcopy(DEFAULTS));start=r.frame().eyes[0].x;r.dispatch('Look Left')
        self.assertEqual(r.gaze,0);r.advance(.22);self.assertLess(r.frame().eyes[0].x,start-.1)
        r.advance(.5);self.assertEqual(r.gaze,-1);before=r.gaze;r.dispatch('Center');self.assertEqual(r.gaze,before)
        r.advance(.2);self.assertTrue(-1<r.gaze<0);r.advance(.4);self.assertEqual(r.gaze,0)
        r.dispatch('Look Right');r.advance(.8);self.assertEqual(r.gaze,1);r.advance(.8);self.assertEqual(r.gaze,0)
    def test_shake_does_not_require_or_create_emotion_pose(self):
        r=VisualRuntime(deepcopy(DEFAULTS));before=deepcopy(r.current);r.dispatch('Shake');r.advance(.08)
        self.assertEqual(r.current,before);self.assertEqual(len(r.cfg['poses']),2)
        for event in ('Touch','Pet','Person Detected'):
            with self.assertRaises(ValueError):r.dispatch(event)
    def test_stt_disabled_no_fabricated_text(self):
        from fulu_visual.speech import SpeechInput
        with self.assertRaisesRegex(ValueError,'STT'):SpeechInput().recognize()
        self.assertNotIn('System.Speech',(ROOT/'fulu_visual/speech.py').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main(verbosity=2)
