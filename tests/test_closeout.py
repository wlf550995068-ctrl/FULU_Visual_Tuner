from copy import deepcopy
from pathlib import Path
import json,math,tempfile,unittest,subprocess,sys
import numpy as np,moderngl
from fulu_visual.config import ROOT,DEFAULTS,TuningSession,load_config,save_config,validate_shape,SHAPE_PARAMETERS,EYE_PARAMETERS
from fulu_visual.geometry import EYE_DEFAULTS,mix_shape,seed_contour,validate_contour
from fulu_visual.rig import EyeRig
from fulu_visual.renderer import EyeRenderer
from fulu_visual.visual_elements import clamp_accent,element_frame
from fulu_visual.element_renderer import VisualElementRenderer
from fulu_visual.runtime import VisualRuntime,GAZE_ENTER,GAZE_HOLD,GAZE_RETURN,SHAKE_DURATION
from fulu_visual.extensions import EYE_EXTENSION_DEFAULTS,ACCENT_REGISTRY,import_accent_manifest

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


class ContourTests(unittest.TestCase):
    def test_closed_freeform_and_builtin_protection(self):
        s=TuningSession(deepcopy(DEFAULTS));pid=s.set_contour('normal',seed_contour('rectangle'),seed=True)
        p=s.config['poses'][pid]['shape'];p['contour'][0]=[.7,.9];validate_shape(p)
        self.assertEqual(s.config['poses']['normal'],DEFAULTS['poses']['normal'])
        self.assertNotIn('type',p)
    def test_invalid_contours_rejected(self):
        for points in ([[0,0],[1,1],[0,1],[1,0]],[[0,0],[0,0],[1,1]],[[0,0],[1,0],[0,float('nan')]]):
            with self.assertRaises(ValueError):validate_contour(points)
    def test_independent_save_restart_undo(self):
        s=TuningSession(deepcopy(DEFAULTS));pid=s.set_contour('normal',seed_contour('triangle'),'left_contour',True)
        s.set_contour(pid,seed_contour('circle'),'right_contour');expected=deepcopy(s.config)
        s.undo();self.assertNotIn('right_contour',s.config['poses'][pid]['shape']);s.redo();self.assertEqual(s.config,expected)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'library.json';s.save(path)
            code="from fulu_visual.config import load_config;import sys,json;print(json.dumps(load_config(sys.argv[1])['poses'][sys.argv[2]]['shape']))"
            shape=json.loads(subprocess.check_output([sys.executable,'-B','-c',code,str(path),pid],cwd=ROOT))
            self.assertEqual(shape,expected['poses'][pid]['shape'])
    def test_contour_morph_interrupt(self):
        s=TuningSession(deepcopy(DEFAULTS));pid=s.set_contour('normal',seed_contour('triangle'),seed=True)
        r=VisualRuntime(s.config);r.retarget(pid);r.advance(r.duration*.46);before=deepcopy(r.current);frame=r.frame()
        r.retarget('happy');self.assertEqual(r.current,before);self.assertEqual(r.frame().eyes,frame.eyes)
        r.advance(r.duration);self.assertEqual(r.current,s.config['poses']['happy']['shape'])
    def test_seeds_irregular_morph_volume_on_gpu(self):
        s=TuningSession(deepcopy(DEFAULTS));shapes=[seed_contour(k) for k in ('circle','rectangle','triangle')]
        shapes.append([[1,.3],[.55,1],[-.5,.8],[-1,.1],[-.7,-.9],[.4,-.75]])
        ids=[s.set_contour('normal',p,seed=True) for p in shapes]
        ctx=moderngl.create_standalone_context(require=330);fb=ctx.simple_framebuffer((640,360),components=3);r=EyeRenderer(ctx,s.config)
        try:
            for pid in ids:
                r.render(EyeRig(s.config).pose_frame(pid),fb);vol=fb.read(components=3,alignment=1)
                s.config['volume']['volume_depth']=0;r.configure(s.config);r.render(EyeRig(s.config).pose_frame(pid),fb);flat=fb.read(components=3,alignment=1)
                self.assertNotEqual(vol,flat);self.assertTrue(any(flat))
                pixels=np.frombuffer(flat,np.uint8).reshape(360,640,3);mask=pixels[:,:,2]>100
                for _ in range(3):mask&=np.roll(mask,1,0)&np.roll(mask,-1,0)&np.roll(mask,1,1)&np.roll(mask,-1,1)
                self.assertGreater(mask.sum(),100);self.assertEqual(np.ptp(pixels[:,:,2][mask]),0)
                s.config['volume']['volume_depth']=.85;r.configure(s.config)
            for source,target in zip(ids,ids[1:]+ids[:1]):
                for i in range(21):
                    shape=mix_shape(s.config['poses'][source]['shape'],s.config['poses'][target]['shape'],i/20)
                    validate_shape(shape);r.render(EyeRig(s.config).shape_frame(shape,i/20),fb)
                    self.assertTrue(any(fb.read(components=3,alignment=1)))
            shape=deepcopy(s.config['poses'][ids[1]]['shape']);r.render(EyeRig(s.config).shape_frame(shape,0),fb);rect=fb.read()
            shape['corner_roundness']=.8;r.render(EyeRig(s.config).shape_frame(shape,0),fb);self.assertNotEqual(rect,fb.read())
            shape['scale']=0;r.render(EyeRig(s.config).shape_frame(shape,0),fb);self.assertFalse(any(fb.read()))
        finally:r.release();fb.release();ctx.release()
    def test_gaze_hold_center_and_shake_restore(self):
        r=VisualRuntime(deepcopy(DEFAULTS));start=r.frame().eyes[0].x;r.dispatch('Look Left');r.advance(GAZE_ENTER)
        self.assertLess(r.frame().eyes[0].x,start-.15);r.advance(GAZE_HOLD*.8);self.assertEqual(r.gaze,-1)
        r.dispatch('Center');self.assertEqual(r.gaze,-1);r.advance(GAZE_RETURN/2);self.assertTrue(-1<r.gaze<0)
        r.advance(GAZE_RETURN);self.assertEqual(r.gaze,0)
        r.dispatch('Look Right');r.advance(GAZE_ENTER+GAZE_HOLD*.5);self.assertGreater(r.frame().eyes[0].x,start+.15)
        r.advance(GAZE_RETURN+GAZE_HOLD);self.assertEqual(r.gaze,0)
        current=deepcopy(r.current);base=r.frame();r.dispatch('Shake');r.advance(SHAKE_DURATION*.4)
        self.assertGreater(abs(r.frame().eyes[0].x-base.eyes[0].x),.01)
        r.advance(SHAKE_DURATION);self.assertEqual(r.current,current);self.assertEqual(r.frame().eyes,base.eyes)
        self.assertEqual(len(r.cfg['poses']),2)
    def test_wrapped_text_mapping_does_not_change_value(self):
        from fulu_visual.tuner_extensions import WorkbenchExtensions
        value='长中文路径和名称测试'*50
        wrapped,mapping=WorkbenchExtensions.wrap_text(value,15,lambda char:1)
        self.assertEqual(wrapped.replace('\n',''),value);self.assertGreater(wrapped.count('\n'),20)
        for pos in mapping:
            mapped=mapping[pos];self.assertEqual(wrapped.encode()[:mapped].replace(b'\n',b''),value.encode()[:pos])

if __name__=='__main__':unittest.main(verbosity=2)
