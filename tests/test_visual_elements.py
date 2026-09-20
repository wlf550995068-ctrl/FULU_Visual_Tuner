from copy import deepcopy
from pathlib import Path
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
import moderngl
import numpy as np
from PIL import Image
from fulu_visual.config import (ROOT,DEFAULTS,ACCENT_ANIMATIONS,ACCENT_DEFAULTS,
                               TuningSession,load_config,save_config,validate_config)
from fulu_visual.visual_elements import (ELEMENT_TYPES,ElementAnimation,clamp_accent,
                                         element_frame,world_bounds)
from fulu_visual.renderer import EyeRenderer
from fulu_visual.element_renderer import VisualElementRenderer
from fulu_visual.rig import EyeRig

class ElementTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'library.json'
        save_config(DEFAULTS,self.path);self.s=TuningSession(load_config(self.path),self.path)
    def test_exactly_two_symbols_and_none(self):
        self.assertEqual(ELEMENT_TYPES,('NONE','QUESTION','EXCLAMATION'))
        with self.assertRaises((ValueError,KeyError)):self.s.edit_accent(type='FLAME')
    def test_default_disabled_migrates_existing_library(self):
        old=deepcopy(DEFAULTS);old.pop('accent')
        self.path.write_text(json.dumps(old),encoding='utf-8')
        c=load_config(self.path)
        self.assertEqual(c['accent'],ACCENT_DEFAULTS)
        for key in old:self.assertEqual(old[key],c[key])
    def test_save_and_new_process_restart(self):
        self.s.edit_accent(type='QUESTION',enabled=True,position=dict(x=-.62,y=.32),
                           scale=1.3,rotation=37.,opacity=.61)
        self.s.save()
        raw=subprocess.check_output([sys.executable,'-c',
            'import json,sys;from fulu_visual.config import load_config;print(json.dumps(load_config(sys.argv[1])["accent"]))',
            str(self.path)],text=True)
        self.assertEqual(json.loads(raw),self.s.config['accent'])
    def test_reset_only_accent_and_undo_redo(self):
        self.s.edit_accent(type='EXCLAMATION',enabled=True,rotation=60.)
        before=deepcopy(self.s.config)
        self.s.restore('accent')
        self.assertEqual(self.s.config['accent'],ACCENT_DEFAULTS)
        for key in before:
            if key!='accent':self.assertEqual(before[key],self.s.config[key])
        self.s.undo();self.assertEqual(before,self.s.config)
        self.s.redo();self.assertEqual(self.s.config['accent'],ACCENT_DEFAULTS)
    def test_drag_gesture_groups_into_one_undo(self):
        self.s.begin_gesture()
        for value in (.2,.3,.4):self.s.edit('accent.position','x',value)
        self.s.end_gesture()
        self.assertEqual(len(self.s.undo_stack),1)
        self.s.undo();self.assertEqual(self.s.config,DEFAULTS)
    def test_clamp_considers_size_rotation_both_symbols_all_corners(self):
        for kind in ELEMENT_TYPES[1:]:
            for scale in (.35,1.,3.):
                for rotation in range(-180,181,15):
                    for x,y in ((-2,-2),(-2,2),(2,-2),(2,2)):
                        a=dict(deepcopy(ACCENT_DEFAULTS),type=kind,enabled=True,scale=scale,rotation=rotation,position=dict(x=x,y=y))
                        d=dict(DEFAULTS['display'],design_aspect=1.2,safe_margin=.12)
                        a=clamp_accent(a,d);x0,x1,y0,y1=world_bounds(a)
                        self.assertGreaterEqual(x0,-.48);self.assertLessEqual(x1,.48)
                        self.assertGreaterEqual(y0,-.38);self.assertLessEqual(y1,.38)
    def test_unsafe_disk_config_rejected(self):
        c=deepcopy(DEFAULTS);c['accent'].update(scale=3.,rotation=45.)
        c['accent']['position']=dict(x=.88,y=.49)
        with self.assertRaises(ValueError):validate_config(c)
    def test_shape_volume_motion_resets_leave_accent(self):
        self.s.edit_accent(type='QUESTION',enabled=True,rotation=30.)
        a=deepcopy(self.s.config['accent'])
        for group in ('shape','volume','motion'):
            self.s.restore(group,'normal');self.assertEqual(a,self.s.config['accent'])
    def test_pose_save_does_not_overwrite_accent(self):
        self.s.edit_accent(type='QUESTION',enabled=True);self.s.save()
        self.s.edit_accent(type='EXCLAMATION')
        self.s.save_pose('normal')
        self.assertEqual(load_config(self.path)['accent']['type'],'QUESTION')

class AnimationTests(unittest.TestCase):
    def setUp(self):self.a=ElementAnimation(ACCENT_ANIMATIONS['simple_pop'])
    def test_full_enter_hold_exit_done(self):
        self.assertEqual(self.a.sample(),(1.,1.))
        self.a.play();self.assertEqual(self.a.sample()[0],0.)
        phases=set()
        for _ in range(100):
            phases.add(self.a.phase)
            opacity,scale=self.a.sample()
            self.assertTrue(0<=opacity<=1);self.assertTrue(.85<=scale<=1)
            self.a.advance(1/60)
        self.assertEqual(phases,{'ENTER','HOLD','EXIT','DONE'})
        self.assertEqual(self.a.sample()[0],0.)
    def test_pause_resume_reset_and_invalid_dt(self):
        self.a.play();self.a.advance(.10);self.a.pause()
        before=self.a.cursor,self.a.sample()
        self.a.advance(5);self.assertEqual(before,(self.a.cursor,self.a.sample()))
        self.a.resume();self.a.advance(.05);self.assertGreater(self.a.cursor,before[0])
        self.a.reset();self.assertEqual(self.a.phase,'EDIT');self.assertEqual(self.a.sample(),(1.,1.))
        for dt in (-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):self.a.advance(dt)
    def test_delta_rate_independence(self):
        results=[]
        for fps in (24,30,60,144):
            a=ElementAnimation(self.a.settings);a.play()
            for _ in range(fps):a.advance(.13/fps)
            results.append(a.sample())
        for result in results:
            self.assertAlmostEqual(result[0],results[0][0],12)
            self.assertAlmostEqual(result[1],results[0][1],12)

class ElementGPUTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctx=moderngl.create_standalone_context(require=330)
        cls.eyes=EyeRenderer(cls.ctx,DEFAULTS);cls.elements=VisualElementRenderer(cls.ctx)
        cls.fbo=cls.ctx.simple_framebuffer((960,540),components=3)
        cls.out=ROOT/'test_output/accent';cls.out.mkdir(parents=True,exist_ok=True)
    @classmethod
    def tearDownClass(cls):
        cls.elements.release();cls.eyes.release();cls.fbo.release();cls.ctx.release()
    def draw(self,a=None,pose='normal',animation=None,guides=False):
        c=deepcopy(DEFAULTS)
        self.eyes.render(EyeRig(c).pose_frame(pose),self.fbo)
        if a:self.elements.render(element_frame(a,animation),self.fbo,c['display'],guides)
        return np.frombuffer(self.fbo.read(components=3,alignment=1),np.uint8).reshape(540,960,3)[::-1].copy()
    def accent(self,kind='QUESTION',**kwargs):
        a=dict(deepcopy(ACCENT_DEFAULTS),enabled=True,type=kind)
        a.update(kwargs)
        return clamp_accent(a,DEFAULTS['display'])
    def test_none_disabled_zero_opacity_identical_eye_pixels(self):
        base=self.draw()
        for a in (self.accent('NONE'),self.accent(enabled=False),self.accent(opacity=0.)):
            self.assertTrue(np.array_equal(base,self.draw(a)))
        if (self.out/'before.json').exists():
            before=json.loads((self.out/'before.json').read_text(encoding='utf-8'))
            for name in ('fulu_visual/motion.py',):
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),before['hashes'][name],name)
    def test_symbols_distinct_and_eye_data_unchanged(self):
        original=deepcopy(DEFAULTS)
        q=self.draw(self.accent());e=self.draw(self.accent('EXCLAMATION'),pose='happy')
        self.assertFalse(np.array_equal(q,self.draw(self.accent('EXCLAMATION'))))
        # Geometry/material untouched, and main eye pixel rectangle bit-identical.
        self.assertEqual(original,DEFAULTS)
        base=self.draw()
        self.assertTrue(np.array_equal(q[160:380,220:710],base[160:380,220:710]))
        Image.fromarray(q).save(self.out/'normal_question.png')
        Image.fromarray(e).save(self.out/'happy_exclamation.png')
    def test_all_controls_change_actual_pixels(self):
        base=self.draw(self.accent())
        for kwargs in (dict(position=dict(x=.40,y=.28)),dict(position=dict(x=.53,y=.18)),
                       dict(scale=1.5),dict(rotation=45.),dict(opacity=.4)):
            self.assertGreater(np.count_nonzero(self.draw(self.accent(**kwargs))!=base),100)
    def test_bounds_clamp_no_pixels_outside_safe_area(self):
        base=self.draw();xs=(np.arange(960)+.5-480)/540
        ys=(270-(np.arange(540)+.5))/540
        outside=(np.abs(xs)[None,:]>16/18-.04)|(np.abs(ys)[:,None]>.5-.04)
        for kind in ('QUESTION','EXCLAMATION'):
            for rotation in (-180,-90,-45,0,45,90,135):
                for x,y in ((-2,-2),(-2,2),(2,-2),(2,2)):
                    a=self.accent(kind,scale=3.,rotation=rotation,position=dict(x=x,y=y))
                    image=self.draw(a,guides=True)
                    self.assertTrue(np.array_equal(image[outside],base[outside]))
    def test_animated_pixels_enter_and_exit(self):
        a=ElementAnimation(ACCENT_ANIMATIONS['simple_pop']);a.play()
        base=self.draw();cfg=self.accent()
        self.assertTrue(np.array_equal(base,self.draw(cfg,animation=a)))
        a.advance(.12);middle=self.draw(cfg,animation=a)
        a.advance(.2);full=self.draw(cfg,animation=a)
        self.assertFalse(np.array_equal(middle,full))
        a.advance(2)
        self.assertTrue(np.array_equal(base,self.draw(cfg,animation=a)))

if __name__=='__main__':unittest.main(verbosity=2)

