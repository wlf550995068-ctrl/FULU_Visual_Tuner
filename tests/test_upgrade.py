from copy import deepcopy
import json,math,hashlib,tempfile,unittest,subprocess,sys
from pathlib import Path
import numpy as np
import moderngl
from PIL import Image
from fulu_visual.config import DEFAULTS,ROOT,SHAPE_PARAMETERS,TuningSession,load_config,save_config,validate_shape
from fulu_visual.reference import ReferenceImage
from fulu_visual.runtime import VisualRuntime
from fulu_visual.rig import EyeRig
from fulu_visual.renderer import EyeRenderer
from fulu_visual.motion import MotionPlayer

class RuntimeTests(unittest.TestCase):
    def test_interrupt_has_no_jump_and_pause(self):
        s=TuningSession(deepcopy(DEFAULTS));r=VisualRuntime(s.config);r.retarget('happy');r.advance(r.duration*.46)
        state=deepcopy(r.current);r.retarget('normal');self.assertEqual(state,r.start)
        r.advance(1e-6);self.assertLess(max(abs(r.current[k]-state[k]) for k in state),1e-8)
        r.paused=True;before=deepcopy(r.current);r.advance(4);self.assertEqual(before,r.current)
        r.paused=False;r.advance(5);self.assertEqual(r.current,s.config['poses']['normal']['shape'])
    def test_missing_pose_and_unknown_action(self):
        r=VisualRuntime(deepcopy(DEFAULTS));before=deepcopy(r.current)
        with self.assertRaises(ValueError):r.retarget('missing')
        with self.assertRaises(ValueError):r.dispatch('unknown')
        self.assertEqual(before,r.current)
        for dt in (-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):r.advance(dt)
    def test_idle_does_not_change_pose(self):
        cfg=deepcopy(DEFAULTS);r=VisualRuntime(cfg);before=r.frame();r.advance(10)
        self.assertEqual(before.eyes,r.frame().eyes)
        cfg['runtime']['idle_enabled']=True;r.advance(.3)
        self.assertNotEqual(before.eyes,r.frame().eyes);self.assertEqual(r.target,'normal')

class ReferenceRangeTests(unittest.TestCase):
    def test_import_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory);a=np.zeros((180,320,3),np.uint8)
            a[50:120,60:105]=180;a[50:120,180:225]=180
            src=d/'ref.png';Image.fromarray(a).save(src);original=src.read_bytes()
            ref=ReferenceImage();ref.load(str(src),d/'assets')
            self.assertEqual(src.read_bytes(),original)
            self.assertEqual(ref.path.parent,d/'assets')
            restored=ReferenceImage();restored.load(ref.path)
            self.assertEqual(restored.image.tobytes(),ref.image.tobytes())
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

