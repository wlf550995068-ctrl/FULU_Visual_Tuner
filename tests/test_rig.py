import math
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys
from fulu_visual.config import DEFAULTS,load_config,save_config,validate_config,validate_pair,TuningSession
from fulu_visual.motion import MotionPlayer
from fulu_visual.geometry import dimensions,deform,outline
from fulu_visual.rig import EyeRig

class MotionTests(unittest.TestCase):
    def setUp(self):self.p=MotionPlayer(deepcopy(DEFAULTS['motion']))
    def test_automatic_roundtrip_without_seek(self):
        self.p.play();samples=[]
        for i in range(640):self.p.advance(1/60);samples.append(self.p.blend)
        self.assertLess(min(samples),.001);self.assertGreater(max(samples),.999)
        peaks=sum(a>.99 and b<=.99 for a,b in zip(samples,samples[1:]))
        self.assertGreaterEqual(peaks,2)
    def test_pause_resume_no_time_loss(self):
        self.p.play();self.p.advance(.2);t=self.p.cursor;b=self.p.blend
        self.p.pause();self.p.advance(50)
        self.assertEqual((t,b),(self.p.cursor,self.p.blend))
        self.p.play();self.assertEqual(t,self.p.cursor)
        self.p.advance(.01);self.assertGreater(self.p.blend,b)
    def test_scrub_pauses_and_step_works(self):
        self.p.play();self.p.seek(.57)
        self.assertTrue(self.p.paused);self.assertAlmostEqual(self.p.progress,.57)
        t=self.p.cursor;self.p.advance(1/60,force=True)
        self.assertAlmostEqual(self.p.cursor,t+1/60)
    def test_frame_rate_independence(self):
        values=[]
        for fps in (24,30,60,144):
            p=MotionPlayer(deepcopy(DEFAULTS['motion']));p.play()
            for _ in range(fps):p.advance(.3/fps)
            values.append(p.blend)
        for v in values:self.assertAlmostEqual(v,values[0],12)
    def test_invalid_dt(self):
        for v in (-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):self.p.advance(v)
    def test_continuity_at_reversal_and_wrap(self):
        for t in (0,self.p.half_period,self.p.period):
            self.p.cursor=t-1e-5;a=self.p.blend
            self.p.cursor=t+1e-5;b=self.p.blend
            self.assertLess(abs(a-b),1e-8)
    def test_reconfigure_preserves_cycle_position(self):
        self.p.seek(.23);settings=dict(self.p.settings,target_interval=4.)
        self.p.reconfigure(settings);self.assertAlmostEqual(self.p.progress,.23)

class GeometryTests(unittest.TestCase):
    def test_whole_bend_curves_both_contours_without_micro_curves(self):
        p=deepcopy(DEFAULTS['poses']['happy']['shape']);p.update(top_curve=0.,bottom_curve=0.)
        a,b,*_=dimensions(p)
        for y in (-b,b):
            self.assertGreater(deform(p,0,y)[1],deform(p,.8*a,y)[1])
        p['whole_bend']=-p['whole_bend']
        for y in (-b,b):self.assertLess(deform(p,0,y)[1],deform(p,.8*a,y)[1])
    def test_thickness_and_bulge_change_actual_outline(self):
        p=deepcopy(DEFAULTS['poses']['normal']['shape']);before=outline(p)
        for key in ('thickness','center_bulge'):
            changed=dict(p);changed[key]+=.2
            self.assertNotEqual(outline(changed),before)
    def test_preserve_retains_area_under_bend(self):
        def area(p):
            xy=outline(p,80)
            return abs(sum(x*v-y*u for (x,y),(u,v) in zip(xy,xy[1:]+xy[:1])))/2
        p=deepcopy(DEFAULTS['poses']['happy']['shape'])
        p.update(top_curve=0.,bottom_curve=0.,volume_preserve=1.,whole_bend=0.)
        straight=area(p);p['whole_bend']=1.
        preserved=area(p);p['volume_preserve']=0.
        self.assertLess(abs(preserved/straight-1),.02)
        self.assertLess(area(p),preserved*.7)
    def test_invalid_fold_rejected(self):
        c=deepcopy(DEFAULTS);c['poses']['normal']['shape'].update(whole_bend=1.2,thickness=1.6)
        with self.assertRaises(ValueError):validate_config(c)

class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'library.json'
        save_config(DEFAULTS,self.path);self.s=TuningSession(load_config(self.path),self.path)
    def edit(self,section,key,value):
        self.s.begin_gesture();self.s.edit(section,key,value);self.s.end_gesture()
    def test_only_two_initial_records(self):self.assertEqual(set(self.s.config['poses']),{'normal','happy'})
    def test_create_copy_rename_save_restart_load_delete(self):
        pid=self.s.create('自定义眼形','happy')
        self.assertEqual(self.s.config['poses'][pid]['shape'],self.s.config['poses']['happy']['shape'])
        self.s.rename(pid,'Arc')
        self.s.save_pose(pid)
        restarted=TuningSession(load_config(self.path),self.path)
        self.assertEqual(restarted.config['poses'][pid]['name'],'Arc')
        output=subprocess.check_output([sys.executable,'-c',
            'import sys;from fulu_visual.config import load_config;print(load_config(sys.argv[1])["poses"][sys.argv[2]]["name"])',
            str(self.path),pid],text=True)
        self.assertEqual(output.strip(),'Arc')
        self.edit('poses.'+pid+'.shape','eye_gap',.23)
        self.s.load_pose(pid);self.assertNotEqual(self.s.config['poses'][pid]['shape']['eye_gap'],.23)
        self.s.delete(pid);self.s.save()
        self.assertNotIn(pid,load_config(self.path)['poses'])
    def test_normal_protected(self):
        with self.assertRaises(ValueError):self.s.delete('normal')
        with self.assertRaises(ValueError):self.s.rename('normal','X')
        with self.assertRaises(ValueError):self.s.delete('happy')
    def test_duplicate_name_and_invalid_name_rejected(self):
        for name in ('NORMAL','happy',' ','bad##id','x'*41):
            with self.assertRaises(ValueError):self.s.create(name)
    def test_each_pose_saved_independently(self):
        self.edit('poses.normal.shape','eye_width',.31)
        self.edit('poses.happy.shape','eye_width',.32)
        self.s.save_pose('normal')
        disk=load_config(self.path)
        self.assertEqual(disk['poses']['normal']['shape']['eye_width'],.31)
        self.assertEqual(disk['poses']['happy']['shape']['eye_width'],DEFAULTS['poses']['happy']['shape']['eye_width'])
        self.s.save_pose('happy')
        self.assertEqual(load_config(self.path)['poses']['happy']['shape']['eye_width'],.32)
    def test_arbitrary_ab_and_delete_reference_repair(self):
        a=self.s.create('Custom A');b=self.s.create('Custom B','happy')
        self.s.config['selection'].update(source=b,target=a)
        validate_pair(self.s.config,b,a)
        rig=EyeRig(self.s.config)
        self.assertEqual(rig.frame_at_blend(0).eyes[0].shape,self.s.config['poses'][b]['shape'])
        self.assertEqual(rig.frame_at_blend(1).eyes[0].shape,self.s.config['poses'][a]['shape'])
        self.s.delete(b);self.assertEqual(self.s.config['selection']['source'],'normal')
    def test_resets_are_isolated_and_undoable(self):
        self.edit('poses.normal.shape','eye_width',.31)
        self.edit('poses.happy.shape','eye_gap',.23)
        self.edit('volume','volume_depth',1.2)
        self.edit('motion','target_interval',4.)
        for group in ('shape','volume','motion'):
            before=deepcopy(self.s.config);self.s.restore(group,'normal')
            after=self.s.config
            if group=='shape':
                self.assertEqual(after['poses']['normal']['shape'],DEFAULTS['poses']['normal']['shape'])
                self.assertEqual(before['poses']['happy'],after['poses']['happy'])
                self.assertEqual(before['volume'],after['volume']);self.assertEqual(before['motion'],after['motion'])
            else:
                self.assertEqual(after[group],DEFAULTS[group])
                self.assertEqual(before['poses'],after['poses'])
                other='volume' if group=='motion' else 'motion'
                self.assertEqual(before[other],after[other])
            self.s.undo();self.assertEqual(before,self.s.config)
    def test_all_reset_preserves_custom_library(self):
        pid=self.s.create('Keep me','happy')
        self.edit('poses.'+pid+'.shape','eye_gap',.24)
        before=deepcopy(self.s.config);self.s.restore('all')
        self.assertIn(pid,self.s.config['poses'])
        self.assertEqual(self.s.config['poses'][pid]['shape'],before['poses'][pid]['defaults'])
        self.s.undo();self.assertEqual(before,self.s.config)
    def test_gesture_undo_redo_and_branch(self):
        self.s.begin_gesture()
        for width in (.29,.30,.31):self.s.edit('poses.normal.shape','eye_width',width)
        self.s.end_gesture();self.assertEqual(len(self.s.undo_stack),1)
        self.s.undo();self.assertFalse(self.s.dirty)
        self.s.redo();self.assertEqual(self.s.config['poses']['normal']['shape']['eye_width'],.31)
        self.s.undo();self.edit('poses.normal.shape','eye_gap',.22)
        self.assertFalse(self.s.redo_stack)
    def test_atomic_save_and_roundtrip(self):
        self.s.save();self.assertEqual(load_config(self.path),self.s.config)
        self.assertFalse(self.path.with_suffix('.json.tmp').exists())

if __name__=='__main__':unittest.main(verbosity=2)

