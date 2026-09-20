from copy import deepcopy
import json,math,hashlib,tempfile,unittest,subprocess,sys
from pathlib import Path
import numpy as np
import moderngl
from PIL import Image
from fulu_visual.config import DEFAULTS,ROOT,SHAPE_PARAMETERS,TuningSession,load_config,save_config,validate_shape
from fulu_visual.derive import DerivationEngine,FAMILIES
from fulu_visual.reference import ReferenceImage
from fulu_visual.runtime import VisualRuntime
from fulu_visual.rig import EyeRig
from fulu_visual.renderer import EyeRenderer
from fulu_visual.motion import MotionPlayer
from fulu_visual.export_tools import export_source

class DeriveRuntimeTests(unittest.TestCase):
    def setUp(self):self.s=TuningSession(deepcopy(DEFAULTS));self.d=DerivationEngine()
    def test_single_result_and_no_visible_roots(self):
        before=len(self.s.config['poses'])
        pid,notes=self.d.derive(self.s,'normal','SAD','变矮，不要收窄，不要水滴')
        self.assertEqual(len(self.s.config['poses']),before+1)
        p=self.s.config['poses'][pid]
        self.assertEqual(p['metadata']['family'],'LOW')
        self.assertEqual(p['name'],'SAD')
        self.assertEqual(p['shape']['eye_width'],DEFAULTS['poses']['normal']['shape']['eye_width'])
        self.assertFalse(any('ROOT' in p['name'].upper() for p in self.s.config['poses'].values()))
    def test_refine_same_id_and_manual_control(self):
        pid,_=self.d.derive(self.s,'normal','SAD','')
        before=deepcopy(self.s.config['poses'][pid]['shape'])
        pid2,_=self.d.derive(self.s,'normal','SAD','上眼缘再压一点，宽度保持',refine_id=pid)
        self.assertEqual(pid,pid2);self.assertEqual(len(self.s.config['poses']),3)
        self.assertLess(self.s.config['poses'][pid]['shape']['top_curve'],before['top_curve'])
        self.assertEqual(self.s.config['poses'][pid]['shape']['eye_width'],before['eye_width'])
        self.s.begin_gesture();self.s.edit('poses.'+pid+'.shape','eye_gap',.22);self.s.end_gesture()
        self.assertEqual(self.s.config['poses'][pid]['shape']['eye_gap'],.22)
    def test_protected_normal_happy_unchanged(self):
        before=deepcopy(self.s.config)
        for semantic in ('SAD','CURIOUS','ANNOYED','SURPRISED'):
            self.d.derive(self.s,'normal',semantic,'饱满一点')
        for key in ('normal','happy'):self.assertEqual(self.s.config['poses'][key],before['poses'][key])
        self.assertEqual(self.s.config['volume'],before['volume'])
        for name in ('LOW_ROOT','VERY_SAD','NORMAL','HAPPY'):
            with self.assertRaises(ValueError):self.d.derive(self.s,'normal',name,'')
    def test_repeat_derive_updates_one_result(self):
        a,_=self.d.derive(self.s,'normal','SAD','')
        b,_=self.d.derive(self.s,'normal','SAD','整体再克制一些')
        self.assertEqual(a,b);self.assertEqual(len(self.s.config['poses']),3)
    def test_style_guard_and_unknown_text(self):
        pid,notes=self.d.derive(self.s,'normal','SAD','加一个人类瞳孔和嘴')
        self.assertTrue(any('未识别' in n for n in notes))
        p=self.s.config['poses'][pid]['shape']
        self.assertGreaterEqual(p['corner_roundness'],.25);self.assertLessEqual(p['end_taper'],.35)
    def test_derive_save_load_metadata(self):
        pid,_=self.d.derive(self.s,'normal','SAD','变矮')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'config.json';self.s.save(path)
            c=load_config(path);self.assertEqual(c['poses'][pid],self.s.config['poses'][pid])
    def test_interrupt_at_46_percent_has_no_jump(self):
        pid,_=self.d.derive(self.s,'normal','SAD','')
        r=VisualRuntime(self.s.config);r.dispatch('Semantic HAPPY');r.advance(r.duration*.46)
        state=deepcopy(r.current);pixels_state=EyeRig(self.s.config).shape_frame(state,0)
        r.dispatch('Semantic SAD')
        self.assertEqual(r.current,state)
        self.assertEqual(r.start,state);self.assertEqual(r.target,pid);self.assertEqual(r.progress,0)
        r.advance(1e-6)
        self.assertLess(max(abs(r.current[k]-state[k]) for k in state),1e-8)
        r.advance(5);self.assertEqual(r.current,self.s.config['poses'][pid]['shape'])
        self.assertEqual(r.log,['Semantic HAPPY','Semantic SAD'])
    def test_all_semantic_triggers_and_return(self):
        for name in ('SAD','CURIOUS','ANNOYED'):self.d.derive(self.s,'normal',name,'')
        r=VisualRuntime(self.s.config)
        for event in ('Shake','Look Left','Center','Look Right','Wake','Semantic SAD','Return'):
            r.dispatch(event);r.advance(.02)
        r.advance(3);self.assertEqual(r.current,self.s.config['poses']['normal']['shape'])
    def test_missing_target_rejected_without_changing_state(self):
        r=VisualRuntime(self.s.config);before=deepcopy(r.current)
        with self.assertRaises(ValueError):r.dispatch('Semantic SAD')
        self.assertEqual(before,r.current)
    def test_idle_default_no_motion_and_optional_drift_no_emotion(self):
        r=VisualRuntime(self.s.config);before=r.frame()
        r.advance(10);self.assertEqual(before.eyes,r.frame().eyes)
        self.s.config['runtime']['idle_enabled']=True;r.advance(.3)
        self.assertNotEqual(before.eyes,r.frame().eyes);self.assertEqual(r.target,'normal')
    def test_runtime_pause_and_finite_dt(self):
        r=VisualRuntime(self.s.config);r.retarget('happy');r.advance(.2);r.paused=True
        before=deepcopy(r.current);r.advance(4);self.assertEqual(before,r.current)
        for dt in (float('nan'),float('inf'),-1):
            with self.assertRaises(ValueError):r.advance(dt)

class ReferenceRangeTests(unittest.TestCase):
    def test_import_preserves_original_and_measures_two_shapes(self):
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory);a=np.zeros((180,320,3),np.uint8)
            a[50:120,60:105]=180;a[50:120,180:225]=180
            src=d/'ref.png';Image.fromarray(a).save(src);original=src.read_bytes()
            ref=ReferenceImage();m=ref.load(str(src),d/'assets')
            self.assertEqual(src.read_bytes(),original);self.assertTrue(m['usable'])
            self.assertEqual(ref.path.parent,d/'assets')
            restored=ReferenceImage();restored.load(ref.path)
            self.assertEqual(restored.image.tobytes(),ref.image.tobytes())
            self.assertAlmostEqual(m['height'],70/180,delta=.03)
    def test_reference_saved_config_restores_in_new_process(self):
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory);src=d/'ref.png';Image.new('RGB',(60,40),'gray').save(src)
            ref=ReferenceImage();ref.load(src,d/'assets')
            cfg=deepcopy(DEFAULTS);cfg['reference'].update(path=str(ref.path),enabled=True,fit='1:1',zoom=1.2,x=.1)
            saved=d/'library.json';save_config(cfg,saved)
            code="from fulu_visual.config import load_config;from fulu_visual.reference import ReferenceImage;from pathlib import Path;import moderngl,sys; c=load_config(sys.argv[1]);r=ReferenceImage();r.load(Path(c['reference']['path']));ctx=moderngl.create_standalone_context(require=330);g=type('G',(),{'register_texture':lambda self,t:None})();r.upload(ctx,g);assert r.texture.size==(60,40);assert c['reference']['fit']=='1:1' and c['reference']['zoom']==1.2 and c['reference']['x']==.1 and c['reference']['enabled'];r.texture.release();ctx.release()"
            result=subprocess.run([sys.executable,'-c',code,str(saved)],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
    def test_reference_fit_fill_and_one_to_one(self):
        rect=(0,0,400,400)
        self.assertEqual(ReferenceImage.placement((400,200),rect,'Fit',1,0,0),(0,100,400,300))
        self.assertEqual(ReferenceImage.placement((400,200),rect,'Fill',1,0,0),(-200,0,600,400))
        self.assertEqual(ReferenceImage.placement((100,50),rect,'1:1',1,0,0),(150,175,250,225))
    def test_reference_invalid_and_non_eye_fallback(self):
        with self.assertRaises(ValueError):ReferenceImage().load('missing.png')
        m=ReferenceImage.measure(Image.new('RGB',(100,100),'black'));self.assertFalse(m['usable'])
    def test_point_like_shape_and_every_axis_kept(self):
        p=deepcopy(DEFAULTS['poses']['normal']['shape'])
        p.update(eye_width=.006,eye_height=.006,eye_gap=.03,center_bulge=0.,whole_bend=0.)
        validate_shape(p,DEFAULTS['display'])
        self.assertEqual(len(SHAPE_PARAMETERS),14)
    def test_nonfinite_and_invalid_dimensions_rejected(self):
        for key in ('eye_width','eye_height','whole_bend','squash'):
            for v in (float('nan'),float('inf'),-float('inf')):
                p=deepcopy(DEFAULTS['poses']['normal']['shape']);p[key]=v
                with self.assertRaises(ValueError):validate_shape(p)
        p=deepcopy(DEFAULTS['poses']['normal']['shape']);p['eye_width']=-1
        with self.assertRaises(ValueError):validate_shape(p)
    def test_export_excludes_private_data_and_main_project(self):
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            path=export_source(d)
            with zipfile.ZipFile(path) as z:names=z.namelist()
            self.assertIn('simulator.py',names)
            for prefix in ('.venv/','baseline/','backups/','assets/','data/pose_library.json','sources/'):
                self.assertFalse(any(n.startswith(prefix) for n in names))

class ProtectedGPURegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx=moderngl.create_standalone_context(require=330)
        cls.cfg=load_config()
        cls.renderer=EyeRenderer(cls.ctx,cls.cfg);cls.fbo=cls.ctx.simple_framebuffer((960,540),components=3)
    @classmethod
    def tearDownClass(cls):
        cls.renderer.release();cls.fbo.release();cls.ctx.release()
    def test_confirmed_normal_happy_exact_pixels_and_material(self):
        baseline=ROOT/'baseline'
        if not (baseline/'library.json').exists():self.skipTest('Private migration baseline not shipped in public source')
        original=json.loads((baseline/'library.json').read_text(encoding='utf-8'))
        for name in ('normal','happy'):
            self.assertEqual(original['poses'][name]['shape'],self.cfg['poses'][name]['shape'])
            self.renderer.render(EyeRig(self.cfg).pose_frame(name),self.fbo)
            a=np.frombuffer(self.fbo.read(components=3,alignment=1),np.uint8).reshape(540,960,3)[::-1].copy()
            self.assertTrue(np.array_equal(a,np.load(baseline/(name+'.npy'))),name)
        self.assertEqual(original['volume'],self.cfg['volume'])
        hashes=json.loads((baseline/'hashes.json').read_text())
        for p,h in hashes.items():
            if p in ('shaders/eye.vert','fulu_visual/motion.py'):
                self.assertEqual(hashlib.sha256((ROOT/p).read_bytes()).hexdigest(),h,p)
    def test_existing_ab_timing_exact(self):
        path=ROOT/'baseline/motion.json'
        if not path.exists():self.skipTest('Private baseline absent')
        p=MotionPlayer(self.cfg['motion']);p.play();actual=[]
        for _ in range(360):p.advance(1/60);actual.append(p.blend)
        self.assertEqual(actual,json.loads(path.read_text()))
    def test_extremes_valid_render_or_rejected_no_crash(self):
        accepted=0
        for key,label,lo,hi,fmt in SHAPE_PARAMETERS:
            for v in (lo,hi):
                shape=deepcopy(DEFAULTS['poses']['normal']['shape']);shape[key]=v
                try:validate_shape(shape,DEFAULTS['display'])
                except ValueError:continue
                self.renderer.render(EyeRig(self.cfg).shape_frame(shape,0),self.fbo);self.ctx.finish()
                self.assertEqual(len(self.fbo.read(components=3)),960*540*3)
                accepted+=1
        self.assertGreater(accepted,10)
if __name__=='__main__':unittest.main(verbosity=2)

