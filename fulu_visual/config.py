"""Editor-only library. Custom poses do not add formal Visual V2 BASE states."""
from copy import deepcopy
from pathlib import Path
import json
import math
import os
import re
import tomllib
import uuid
from .geometry import dimensions,bounds,mix_shape,EYE_DEFAULTS,side_shape,visible,CONTOUR_FIELDS,CONTOUR_KEYS,validate_contour
from .visual_elements import ELEMENT_TYPES,clamp_accent

ROOT=Path(__file__).resolve().parents[1]
LIBRARY_PATH=ROOT/'data/pose_library.json'
SHAPE_PARAMETERS=(
 ('eye_width','Eye width / 眼宽',0.,3.,'%.3f'),
 ('eye_height','Eye height / 眼高',0.,3.,'%.3f'),
 ('eye_gap','Eye gap / 双眼间隔',0.,3.,'%.3f'),
 ('corner_roundness','Roundness / 圆角',0.,1.,'%.2f'),
 ('whole_bend','Whole Bend / 整体弯曲',-3.,3.,'%.2f rad'),
 ('thickness','Thickness / 主体厚度',0.,6.,'%.2f'),
 ('center_bulge','Center Bulge / 几何鼓起',-.95,5.,'%.2f'),
 ('end_taper','End Taper / 两端收缩',-3.,.99,'%.2f'),
 ('volume_preserve','Volume Preserve / 保形',0.,1.,'%.2f'),
 ('top_curve','Top Curve / 上缘微调',-2.,2.,'%.3f'),
 ('bottom_curve','Bottom Curve / 下缘微调',-2.,2.,'%.3f'),
 ('tilt','Tilt / 镜像倾斜',-180.,180.,'%.1f deg'),
 ('squash','Squash / 纵向压缩',0.,1.,'%.2f'),
 ('stretch','Stretch / 横向拉伸',-1.,8.,'%.2f'),
)
EYE_PARAMETERS=(
 ('position_x','水平位置 Position X',-3.,3.,'%.3f'),
 ('position_y','垂直位置 Position Y',-3.,3.,'%.3f'),
 ('scale','整体缩放 Scale',0.,8.,'%.3f'),
 ('rotation','整体旋转 Rotation',-720.,720.,'%.1f'),
 ('opacity','整体不透明度 Opacity',0.,1.,'%.2f'),
)+tuple((side+'_'+key,label+' / '+side,lo,hi,fmt)
 for side in ('left','right') for key,label,lo,hi,fmt in (
 ('width_scale','宽度比例 Width',0.,8.,'%.2f'),('height_scale','开合比例 Opening',0.,8.,'%.2f'),
 ('x','水平偏移 Gaze X',-3.,3.,'%.3f'),('y','垂直偏移 Gaze Y',-3.,3.,'%.3f'),
 ('rotation','独立旋转 Rotation',-720.,720.,'%.1f'),('opacity','独立不透明度 Opacity',0.,1.,'%.2f'),
 ('bend','独立弯曲 Bend',-3.,3.,'%.2f')))
VOLUME_PARAMETERS=(
 ('volume_depth','Volume Depth / 曲面深度',0.,5.,'%.2f'),
 ('surface_roundness','Surface Roundness / 宽域圆润度',2.,12.,'%.2f'),
 ('center_fill','Center Fill / 宽域中心亮度',0.,1.,'%.2f'),
 ('bulge_influence','Bulge Influence / 曲面鼓起',0.,4.,'%.2f'),
 ('side_falloff','Side Falloff / 侧面滚暗',0.,1.5,'%.2f'),
 ('bottom_falloff','Bottom Falloff / 下缘滚暗',0.,1.5,'%.2f'),
 ('edge_falloff','Edge Falloff / 曲面边缘衰减',0.,1.5,'%.2f'),
 ('edge_softness','Edge Softness / 抗锯齿宽度',0.,4.,'%.2f px'),
)
MOTION_PARAMETERS=(
 ('enter_response','Enter Response / 进入 B',.1,60.,'%.1f'),
 ('return_response','Return Response / 返回 A',.1,60.,'%.1f'),
 ('target_interval','Target Interval / 半周期',.05,30.,'%.1f s'),
 ('single_step_seconds','Step / 小步时长',1/240,.1,'%.4f s'),
)
ACCENT_PARAMETERS=(
 ('scale','Scale / 大小',0.,10.,'%.2f'),
 ('rotation','Rotation / 旋转',-720.,720.,'%.1f deg'),
 ('opacity','Opacity / 不透明度',0.,1.,'%.2f'),
)
# Visual-internal lifecycle settings. No product-level timing or new clock.
ACCENT_ANIMATIONS={'simple_pop':dict(enter=.24,hold=.90,exit=.28,
                                   enter_scale=.86,exit_scale=.94,easing='minimum_jerk')}
ACCENT_DEFAULTS=dict(enabled=False,type='NONE',position=dict(x=.53,y=.28),
                     scale=1.,rotation=0.,opacity=1.,animation='simple_pop')
REFERENCE_DEFAULTS=dict(path='',enabled=False,opacity=.4,fit='Fit',zoom=1.,x=0.,y=0.,side_by_side=False)
RUNTIME_DEFAULTS=dict(idle_enabled=False,idle_amplitude=.002,idle_hz=.15,gaze_amplitude=.018)
NORMAL=dict(eye_width=.28,eye_height=.30,eye_gap=.18,corner_roundness=.55,
 whole_bend=0.,thickness=1.,center_bulge=.14,end_taper=.08,volume_preserve=1.,
 top_curve=0.,bottom_curve=0.,tilt=0.,squash=0.,stretch=0.)
HAPPY=dict(NORMAL,eye_width=.30,eye_height=.14,corner_roundness=.88,
 whole_bend=1.0,center_bulge=.18,end_taper=.22,eye_gap=.17,squash=.10,stretch=.04)
def record(name,shape,builtin=False):
    return dict(name=name,shape=deepcopy(shape),defaults=deepcopy(shape),builtin=builtin)
DEFAULTS=dict(schema_version=2,
 display=dict(width=1460,height=920,design_aspect=16/9,target_fps=60,vsync=True,safe_margin=.04),
 poses={'normal':record('NORMAL',NORMAL,True),'happy':record('HAPPY',HAPPY,True)},
 volume=dict(volume_depth=.85,surface_roundness=3.,center_fill=.82,bulge_influence=.8,side_falloff=.48,
             bottom_falloff=.42,edge_falloff=.24,edge_softness=.8),
 motion=dict(enter_response=9.,return_response=8.,target_interval=2.6,single_step_seconds=1/60),
 selection=dict(selected='normal',source='normal',target='happy'),
 accent=deepcopy(ACCENT_DEFAULTS),reference=deepcopy(REFERENCE_DEFAULTS),runtime=deepcopy(RUNTIME_DEFAULTS))

def validate_name(name):
    if not isinstance(name,str) or not name.strip() or len(name.strip())>40 or any(ord(c)<32 for c in name) or '##' in name:
        raise ValueError('名称需为 1–40 个可见字符，不能包含 ##')
    if re.search(r'(^|[ _])ROOT($|[ _])',name.upper()) or name.upper().startswith('VERY_'):
        raise ValueError('Root 只能作为内部 metadata；不创建 ROOT / VERY_* 可见 Pose')
    return name.strip()

def numeric_group(data,definitions):
    if set(data)!={item[0] for item in definitions}:
        raise ValueError('参数字段不完整或版本不匹配')
    for key,_,low,high,_ in definitions:
        value=data[key]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
            raise ValueError(f'{key} 超出范围 [{low}, {high}]')

def validate_shape(p,display=None):
    required={k for k,*_ in SHAPE_PARAMETERS};optional={k for k,*_ in EYE_PARAMETERS}
    if not required<=p.keys() or set(p)-required-optional-CONTOUR_FIELDS:raise ValueError('Shape 参数字段无效')
    numeric_group({k:p[k] for k in required},SHAPE_PARAMETERS)
    numeric_group({k:p.get(k,EYE_DEFAULTS[k]) for k in optional},EYE_PARAMETERS)
    for key in CONTOUR_KEYS:
        if key in p:validate_contour(p[key])
        if key+'_mix' in p:
            value=p[key+'_mix']
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:raise ValueError('Contour mix 无效')
    # Size zero is an intentional invisible entity, not an invalid shape.
    for side in ('left','right'):
        q=side_shape(p,side)
        if not visible(q):continue
        a,b,r,k,compression=dimensions(q)
        top=q['top_curve']*(1-q['squash']);bottom=q['bottom_curve']*(1-q['squash'])
        max_y=0.
        for i in range(33):
            u=i/32;arch=1-u*u
            profile=(1+q['center_bulge']*arch)*(1-q['end_taper']*u*u)*compression
            thickness=profile+(top-bottom)*arch/(2*b)
            if thickness<.001:raise ValueError('上下轮廓交叉；请调整 Curve / Bulge')
            max_y=max(max_y,abs((top+bottom)*.5*arch)+b*thickness)
        if abs(k)>1e-4 and max_y>=abs(a/k)*.86:
            raise ValueError('弯曲与厚度组合会折叠；请调整参数，保留上个有效状态')
    # Large eyes may be cropped by the viewport; ranges are not reduced to fit it.
    return p

def validate_config(cfg):
    if cfg.get('schema_version')!=2:
        raise ValueError('不支持的 Pose 库版本')
    d=cfg['display']
    if not (1100<=d['width']<=3840 and 780<=d['height']<=2160 and 1.2<=d['design_aspect']<=2.4 and 30<=d['target_fps']<=144 and .01<=d['safe_margin']<=.12):
        raise ValueError('窗口配置无效')
    if not {'normal','happy'}<=set(cfg['poses']):
        raise ValueError('默认 NORMAL / HAPPY 记录需要保留')
    names=set()
    for pid,entry in cfg['poses'].items():
        if not isinstance(pid,str) or not re.fullmatch('[a-zA-Z0-9_-]{1,64}',pid):
            raise ValueError('Pose ID 无效')
        name=validate_name(entry['name'])
        if name.casefold() in names:raise ValueError('Pose 名称重复')
        names.add(name.casefold())
        validate_shape(entry['shape'],d);validate_shape(entry['defaults'],d)
        if entry['builtin']!=(pid in ('normal','happy')):raise ValueError('默认 Pose 标记不可变')
    if cfg['poses']['normal']['name']!='NORMAL':raise ValueError('NORMAL 名称受保护')
    numeric_group(cfg['volume'],VOLUME_PARAMETERS);numeric_group(cfg['motion'],MOTION_PARAMETERS)
    a=cfg['accent']
    if set(a)!=set(ACCENT_DEFAULTS) or not isinstance(a['enabled'],bool) or a['type'] not in ELEMENT_TYPES or a['animation'] not in ACCENT_ANIMATIONS:
        raise ValueError('Accent 配置无效；当前只允许 NONE / QUESTION / EXCLAMATION')
    numeric_group({key:a[key] for key,*_ in ACCENT_PARAMETERS},ACCENT_PARAMETERS)
    numeric_group(a['position'],(('x','x',-2.,2.,''),('y','y',-2.,2.,'')))
    safe=clamp_accent(a,d)
    if abs(safe['scale']-a['scale'])>1e-9 or any(abs(safe['position'][k]-a['position'][k])>1e-9 for k in ('x','y')):
        raise ValueError('Accent 的完整边界必须在安全区内')
    if set(cfg['selection'])!={'selected','source','target'} or not all(v in cfg['poses'] for v in cfg['selection'].values()):
        raise ValueError('Pose 选择指向不存在的记录')
    ref=cfg.get('reference',REFERENCE_DEFAULTS)
    if ref.get('fit') not in ('Fit','Fill','1:1') or not isinstance(ref.get('path'),str):
        raise ValueError('Reference 配置无效')
    for key,lo,hi in (('opacity',0,1),('zoom',.05,10),('x',-3,3),('y',-3,3)):
        value=ref[key]
        if not isinstance(value,(int,float)) or not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Reference 参数非法')
    rt=cfg.get('runtime',RUNTIME_DEFAULTS)
    for key,lo,hi in (('idle_amplitude',0,.01),('idle_hz',.02,1),('gaze_amplitude',0,.3)):
        v=rt[key]
        if not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError('Runtime 参数非法')
    return cfg

def validate_pair(cfg,source,target):
    a,b=(cfg['poses'][p]['shape'] for p in (source,target))
    for i in range(101):
        validate_shape(mix_shape(a,b,i/100),cfg['display'])

def migrate_legacy(path):
    cfg=deepcopy(DEFAULTS)
    if not path.exists():return cfg
    old=tomllib.loads(path.read_text(encoding='utf-8-sig'))
    for name,p in old.get('poses',{}).items():
        pid=name.lower()
        if pid not in cfg['poses']:continue
        shape=deepcopy(cfg['poses'][pid]['shape'])
        for key in shape:
            if key in p:shape[key]=p[key]
        # Transfer the old common-edge arch into the new whole-body bend control.
        common=(p.get('top_curve',0)+p.get('bottom_curve',0))/2
        shape['whole_bend']=max(-1.12,min(1.12,2*common/(shape['eye_width']/2)))
        shape['top_curve']=max(-.07,min(.07,p.get('top_curve',0)-common))
        shape['bottom_curve']=max(-.07,min(.07,p.get('bottom_curve',0)-common))
        try:validate_shape(shape,cfg['display'])
        except ValueError:
            shape['whole_bend']*=.75
            validate_shape(shape,cfg['display'])
        cfg['poses'][pid]['shape']=shape
    old_t=old.get('timing',{})
    for new,oldkey in (('enter_response','happy_response'),('return_response','normal_response'),('target_interval','demo_hold_seconds')):
        if oldkey in old_t:cfg['motion'][new]=old_t[oldkey]
    return validate_config(cfg)

def save_config(cfg,path=None):
    validate_config(cfg)
    path=Path(path or LIBRARY_PATH);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temp,path)

def load_config(path=None):
    path=Path(path or LIBRARY_PATH)
    if not path.exists():
        cfg=migrate_legacy(ROOT/'config.toml') if path==LIBRARY_PATH else deepcopy(DEFAULTS)
        save_config(cfg,path)
    cfg=json.loads(path.read_text(encoding='utf-8-sig'))
    if cfg.get('schema_version')==2:
        cfg['volume'].setdefault('surface_roundness',DEFAULTS['volume']['surface_roundness'])
        cfg.setdefault('accent',clamp_accent(ACCENT_DEFAULTS,cfg['display']))
        cfg.setdefault('reference',deepcopy(REFERENCE_DEFAULTS))
        cfg.setdefault('runtime',deepcopy(RUNTIME_DEFAULTS))
        for pid,pose in cfg['poses'].items():
            if re.search(r'(^|[ _])ROOT($|[ _])',pose['name'].upper()):
                pose['legacy_name']=pose['name']
                if pid=='happy':pose['name']='HAPPY'
                elif pid=='normal':pose['name']='NORMAL'
                else:
                    pose['name']='IMPORTED_'+pid[-8:]
                    pose['archived']=True
                    for key,value in cfg['selection'].items():
                        if value==pid:cfg['selection'][key]='normal'
    return validate_config(cfg)

class TuningSession:
    def __init__(self,cfg,path=None):
        self.config=deepcopy(validate_config(cfg));self.saved=deepcopy(cfg)
        self.path=Path(path or LIBRARY_PATH)
        self.undo_stack=[];self.redo_stack=[];self.gesture=None

    @property
    def dirty(self):return self.config!=self.saved
    def begin_gesture(self):
        if self.gesture is None:self.gesture=deepcopy(self.config)
    def end_gesture(self):
        if self.gesture is not None and self.gesture!=self.config:
            self.undo_stack.append(self.gesture);self.undo_stack=self.undo_stack[-80:];self.redo_stack.clear()
        self.gesture=None
    def commit(self,candidate):
        validate_config(candidate)
        self.begin_gesture();self.config=candidate;self.end_gesture()
    def edit(self,section,key,value):
        candidate=deepcopy(self.config);target=candidate
        for part in section.split('.'):target=target[part]
        target[key]=value
        if section.startswith('accent'):
            candidate['accent']=clamp_accent(candidate['accent'],candidate['display'])
        validate_config(candidate);self.config=candidate
    def edit_accent(self,**changes):
        candidate=deepcopy(self.config)
        candidate['accent'].update(changes)
        candidate['accent']=clamp_accent(candidate['accent'],candidate['display'])
        self.commit(candidate)
    def unique_name(self,name,exclude=None):
        name=validate_name(name)
        if any(p['name'].casefold()==name.casefold() for pid,p in self.config['poses'].items() if pid!=exclude):
            raise ValueError('已有同名 Pose')
        return name
    def create(self,name,copy_from=None):
        name=self.unique_name(name);candidate=deepcopy(self.config)
        pid='pose_'+uuid.uuid4().hex[:12]
        shape=deepcopy(candidate['poses'][copy_from]['shape'] if copy_from else NORMAL)
        candidate['poses'][pid]=record(name,shape)
        candidate['selection']['selected']=pid
        self.commit(candidate);return pid
    def set_contour(self,pid,points,key='contour',seed=False):
        if key not in CONTOUR_KEYS:raise ValueError('Unknown contour channel')
        validate_contour(points)
        candidate=deepcopy(self.config);source=candidate['poses'][pid];shape=deepcopy(source['shape'])
        if seed or key not in shape:shape['corner_roundness']=0.
        if seed:
            shape.update(whole_bend=0.,top_curve=0.,bottom_curve=0.,center_bulge=0.,end_taper=0.,squash=0.,stretch=0.,thickness=1.,tilt=0.)
        shape[key]=deepcopy(points);shape.pop(key+'_mix',None)
        if key=='contour':
            for side in ('left','right'):shape.pop(side+'_contour',None);shape.pop(side+'_contour_mix',None)
        validate_shape(shape,candidate['display'])
        if source['builtin']:
            names={p['name'] for p in candidate['poses'].values()};name='CONTOUR';i=1
            while name in names:name='CONTOUR_'+str(i);i+=1
            pid='pose_'+uuid.uuid4().hex[:12];candidate['poses'][pid]=record(name,shape)
        else:candidate['poses'][pid]['shape']=shape
        candidate['selection']['selected']=pid;self.commit(candidate)
        return pid
    def rename(self,pid,name):
        if pid=='normal':raise ValueError('NORMAL 名称受保护')
        candidate=deepcopy(self.config);candidate['poses'][pid]['name']=self.unique_name(name,pid);self.commit(candidate)
    def delete(self,pid):
        if self.config['poses'][pid]['builtin']:raise ValueError('只能删除自定义 Pose')
        candidate=deepcopy(self.config);del candidate['poses'][pid]
        for key,value in candidate['selection'].items():
            if value==pid:candidate['selection'][key]='normal'
        self.commit(candidate)
    def restore(self,group,pid=None):
        candidate=deepcopy(self.config)
        if group=='shape':candidate['poses'][pid]['shape']=deepcopy(candidate['poses'][pid]['defaults'])
        elif group in ('volume','motion'):candidate[group]=deepcopy(DEFAULTS[group])
        elif group=='accent':candidate['accent']=clamp_accent(ACCENT_DEFAULTS,candidate['display'])
        elif group=='all':
            for item in candidate['poses'].values():item['shape']=deepcopy(item['defaults'])
            for section in ('display','volume','motion','accent','reference','runtime'):candidate[section]=deepcopy(DEFAULTS[section])
        else:raise ValueError('Unknown reset group')
        self.commit(candidate)
    def undo(self):
        self.end_gesture()
        if self.undo_stack:self.redo_stack.append(deepcopy(self.config));self.config=self.undo_stack.pop()
    def redo(self):
        if self.redo_stack:self.undo_stack.append(deepcopy(self.config));self.config=self.redo_stack.pop()
    def save(self,path=None):
        self.end_gesture();save_config(self.config,path or self.path);self.saved=deepcopy(self.config)
    def save_pose(self,pid):
        self.end_gesture()
        disk=load_config(self.path)
        disk['poses'][pid]=deepcopy(self.config['poses'][pid])
        validate_config(disk);save_config(disk,self.path)
        self.saved['poses'][pid]=deepcopy(self.config['poses'][pid])
    def load_pose(self,pid):
        disk=load_config(self.path)
        if pid not in disk['poses']:raise ValueError('这个 Pose 尚未保存')
        candidate=deepcopy(self.config);candidate['poses'][pid]=deepcopy(disk['poses'][pid])
        self.commit(candidate)

