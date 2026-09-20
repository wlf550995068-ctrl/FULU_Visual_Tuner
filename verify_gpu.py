"""Uses exactly the editor's GPU renderer; this is a verification command, not another editor."""
from copy import deepcopy
import json
import statistics
import time
import moderngl
import numpy as np
from PIL import Image
from fulu_visual.config import ROOT,DEFAULTS,VOLUME_PARAMETERS,load_config,validate_config
from fulu_visual.rig import EyeRig
from fulu_visual.renderer import EyeRenderer
from fulu_visual.motion import MotionPlayer

# Frozen historical geometry fixture: independent of the user's current saved art.
# Current confirmed poses are checked against migration baseline in test_upgrade.py.
SHAPE_PARAMETERS=(('eye_width', 'Eye width / 眼宽', 0.16, 0.4, '%.3f'), ('eye_height', 'Eye height / 眼高', 0.075, 0.4, '%.3f'), ('eye_gap', 'Eye gap / 双眼间隔', 0.06, 0.34, '%.3f'), ('corner_roundness', 'Roundness / 圆角', 0.08, 1.0, '%.2f'), ('whole_bend', 'Whole Bend / 整体弯曲', -1.2, 1.2, '%.2f rad'), ('thickness', 'Thickness / 主体厚度', 0.55, 1.6, '%.2f'), ('center_bulge', 'Center Bulge / 几何鼓起', 0.0, 0.6, '%.2f'), ('end_taper', 'End Taper / 两端收缩', 0.0, 0.65, '%.2f'), ('volume_preserve', 'Volume Preserve / 保形', 0.0, 1.0, '%.2f'), ('top_curve', 'Top Curve / 上缘微调', -0.07, 0.07, '%.3f'), ('bottom_curve', 'Bottom Curve / 下缘微调', -0.07, 0.07, '%.3f'), ('tilt', 'Tilt / 镜像倾斜', -18.0, 18.0, '%.1f deg'), ('squash', 'Squash / 纵向压缩', 0.0, 0.48, '%.2f'), ('stretch', 'Stretch / 横向拉伸', 0.0, 0.4, '%.2f'))

def main():
    out=ROOT/'test_output/pose_editor';out.mkdir(parents=True,exist_ok=True)
    cfg=deepcopy(DEFAULTS);cfg['poses']={'normal': {'name': 'NORMAL', 'shape': {'eye_width': 0.28, 'eye_height': 0.3, 'eye_gap': 0.18, 'corner_roundness': 0.48, 'whole_bend': 0.0, 'thickness': 1.0, 'center_bulge': 0.14, 'end_taper': 0.08, 'volume_preserve': 1.0, 'top_curve': 0.0, 'bottom_curve': 0.0, 'tilt': 0.0, 'squash': 0.0, 'stretch': 0.0}, 'defaults': {'eye_width': 0.28, 'eye_height': 0.3, 'eye_gap': 0.18, 'corner_roundness': 0.55, 'whole_bend': 0.0, 'thickness': 1.0, 'center_bulge': 0.14, 'end_taper': 0.08, 'volume_preserve': 1.0, 'top_curve': 0.0, 'bottom_curve': 0.0, 'tilt': 0.0, 'squash': 0.0, 'stretch': 0.0}, 'builtin': True}, 'happy': {'name': 'HAPPY', 'shape': {'eye_width': 0.3, 'eye_height': 0.14, 'eye_gap': 0.17, 'corner_roundness': 0.88, 'whole_bend': 1.12, 'thickness': 1.0, 'center_bulge': 0.18, 'end_taper': 0.22, 'volume_preserve': 1.0, 'top_curve': -0.007500000000000007, 'bottom_curve': 0.007499999999999993, 'tilt': 0.0, 'squash': 0.12, 'stretch': 0.04}, 'defaults': {'eye_width': 0.3, 'eye_height': 0.14, 'eye_gap': 0.17, 'corner_roundness': 0.88, 'whole_bend': 1.0, 'thickness': 1.0, 'center_bulge': 0.18, 'end_taper': 0.22, 'volume_preserve': 1.0, 'top_curve': 0.0, 'bottom_curve': 0.0, 'tilt': 0.0, 'squash': 0.1, 'stretch': 0.04}, 'builtin': True}};ctx=moderngl.create_standalone_context(require=330)
    renderer=EyeRenderer(ctx,cfg);fbo=ctx.simple_framebuffer((960,540),components=3)
    checks=[]
    def check(name,value):
        if not bool(value):raise AssertionError(name)
        checks.append(name)
    def render(blend,config=None,flat=False):
        active=config or cfg
        renderer.configure(active);renderer.render(EyeRig(active).frame_at_blend(blend),fbo,flat=flat)
        return np.frombuffer(fbo.read(components=3,alignment=1),dtype=np.uint8).reshape(540,960,3)[::-1].copy()
    def inspect(arr,label):
        mask=arr[:,:,2]>20;h,w=mask.shape;rows,cols=np.where(mask)
        check(label+': pure black outside',np.all(arr[:12]==0) and np.all(arr[-12:]==0) and np.all(arr[:,w//2-5:w//2+5]==0))
        check(label+': safe area',rows.min()>.04*h and rows.max()<h-.04*h)
        occupied=mask.any(axis=0).astype(np.int8)
        check(label+': two bodies',np.sum(np.diff(np.pad(occupied,(1,1)))==1)==2)
        gaps=np.zeros_like(mask)
        for col in np.where(occupied)[0]:
            ys=np.where(mask[:,col])[0]
            gaps[ys[0]:ys[-1]+1,col]=~mask[ys[0]:ys[-1]+1,col]
        # Threshold jitter on the one-pixel AA fringe is not an internal hole.
        check(label+': no interior holes',not np.any(gaps & np.roll(mask,1,axis=1) & np.roll(mask,-1,axis=1)))
        check(label+': no white highlight',arr.max()<240)
    for u in np.linspace(0,1,41):
        arr=render(float(u));inspect(arr,f'morph {u:.3f}')
        if u in (0,.5,1):Image.fromarray(arr).save(out/('normal.png' if u==0 else 'happy.png' if u==1 else 'morph.png'))
    bend_only=deepcopy(cfg)
    bend_only['poses']['happy']['shape'].update(top_curve=0.,bottom_curve=0.)
    happy=render(1,bend_only,flat=True);mask=happy[:,:,2]>20
    xs=np.where(mask[:,:480].any(axis=0))[0];center=int((xs.min()+xs.max())/2);side=int(xs.min()+.16*(xs.max()-xs.min()))
    middle,edge=np.where(mask[:,center])[0],np.where(mask[:,side])[0]
    check('Whole Bend alone raises entire top',middle.min()+8<edge.min())
    check('Whole Bend alone raises entire bottom',middle.max()+4<edge.max())
    for name,blend in (('normal',0),('happy',1)):
        baseline=render(blend,flat=True)
        for key,_,low,high,_ in SHAPE_PARAMETERS:
            if key=='volume_preserve' and name=='normal':continue # a straight body has no bend compression
            changed=deepcopy(cfg);old=changed['poses'][name]['shape'][key]
            changed['poses'][name]['shape'][key]=old+(.025 if high<=1 else .1) if old+( .025 if high<=1 else .1)<=high else old-.2
            validate_config(changed)
            arr=render(blend,changed,flat=True)
            check(name+' '+key+': changes actual flat geometry',np.sum(np.any(arr!=baseline,axis=2))>15)
            inspect(arr,name+' '+key)
    baseline=render(0)
    for key,_,low,high,_ in VOLUME_PARAMETERS:
        changed=deepcopy(cfg);changed['volume'][key]=low if cfg['volume'][key]!=low else high
        arr=render(0,changed)
        check(key+': affects GPU pixels',np.sum(np.any(arr!=baseline,axis=2))>10)
        inspect(arr,'volume '+key)
    accepted=0;rejected=0
    for name,blend in (('normal',0),('happy',1)):
        for key,_,low,high,_ in SHAPE_PARAMETERS:
            for value in (low,high):
                altered=deepcopy(cfg);altered['poses'][name]['shape'][key]=value
                try:validate_config(altered)
                except ValueError:rejected+=1;continue
                inspect(render(blend,altered),f'limit {name} {key} {value}');accepted+=1
    # Actual frames change automatically on both legs, without any seek or scrub.
    player=MotionPlayer(dict(cfg['motion'],target_interval=1.,enter_response=12.,return_response=12.))
    player.play();images=[];phases=set()
    for i in range(150):
        player.advance(1/60);phases.add(player.phase)
        if i%5==0:images.append(render(player.blend))
    check('automatic playback changes GPU pixels on full cycle',len({im.tobytes() for im in images})>10 and 'B → A' in phases)
    base=render(0);flat=render(0,flat=True)
    check('broad volume tonal range',np.percentile(base[:,:,2][base[:,:,2]>50],90)-np.percentile(base[:,:,2][base[:,:,2]>50],10)>25)
    union=(base[:,:,2]>20)|(flat[:,:,2]>20);interior=union.copy()
    for axis in (0,1):
        for shift in (-1,1):interior &=np.roll(union,shift,axis)
    check('volume preserves flat silhouette beyond AA fringe',not np.any(((base[:,:,2]>20)!=(flat[:,:,2]>20))&interior))
    renderer.configure(cfg);rig=EyeRig(cfg);elapsed=[]
    for i in range(360):
        t=time.perf_counter();renderer.render(rig.frame_at_blend((i%120)/119),fbo);ctx.finish()
        if i>=60:elapsed.append(time.perf_counter()-t)
    report=dict(gpu=ctx.info['GL_RENDERER'],opengl=ctx.info['GL_VERSION'],checks_passed=len(checks),
        checks=checks,accepted_limit_configurations=accepted,rejected_unsafe_combinations=rejected,
        gpu_mean_ms=statistics.mean(elapsed)*1000,gpu_p95_ms=sorted(elapsed)[int(len(elapsed)*.95)]*1000,
        scope='960x540 GPU completion + rig; not full window FPS or subjective visual acceptance')
    (out/'gpu_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='checks'},indent=2))
    fbo.release();renderer.release();ctx.release()
if __name__=='__main__':main()

