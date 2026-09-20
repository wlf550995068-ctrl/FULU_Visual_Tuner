"""Deterministic single-result derivation. No model, candidate search or product policy."""
from copy import deepcopy
import re
from .config import SHAPE_PARAMETERS,validate_shape,validate_config,record
from .geometry import mix_shape

FAMILIES={'NORMAL':'NEUTRAL','HAPPY':'POSITIVE','SAD':'LOW','CURIOUS':'NEUTRAL',
          'ANNOYED':'TENSION','SURPRISED':'NEUTRAL'}
ALIASES={'悲伤':'SAD','难过':'SAD','好奇':'CURIOUS','不耐烦':'ANNOYED','惊讶':'SURPRISED'}
RANGES={key:(lo,hi) for key,label,lo,hi,fmt in SHAPE_PARAMETERS}

def semantic_name(text):
    name=ALIASES.get(text.strip(),text.strip().upper())
    if not re.fullmatch('[A-Z][A-Z0-9_]{0,39}',name) or 'ROOT' in name or name.startswith('VERY_'):
        raise ValueError('使用语义名称，例如 SAD；Root / VERY_* 不可作为 Pose')
    return name

def style_guard(p):
    q=dict(p)
    # Derivation stays in FULU's fuller language; manual editing has wider freedom.
    for key,lo,hi in (('corner_roundness',.25,1),('thickness',.75,1.5),
                      ('center_bulge',.04,.5),('end_taper',0,.35),
                      ('squash',0,.45),('stretch',-.15,.45),('eye_height',.05,.5)):
        q[key]=max(lo,min(hi,q[key]))
    q['volume_preserve']=max(.8,q['volume_preserve'])
    for key,(lo,hi) in RANGES.items():q[key]=max(lo,min(hi,q[key]))
    return q

def fit_safe(base,proposed,display):
    for i in range(41):
        u=1-i/40
        q=mix_shape(base,proposed,u)
        try:validate_shape(q,display);return q,u
        except ValueError:continue
    raise ValueError('Base Pose 非法，无法安全衍生')

def apply_text(shape,prompt):
    q=dict(shape);text=prompt.lower();notes=[]
    locks=set()
    if any(t in text for t in ('宽度保持','保持宽度','宽度不要','宽度不变','不要收窄','不能收窄','不收窄','宽度保持','keep width','keep the width')):
        locks.add('eye_width')
    if any(t in text for t in ('高度保持','保持高度','高度不变','keep height')):locks.add('eye_height')
    # Directions are explicit and deterministic, not free-form language understanding.
    rules=[
      (('矮一点','变矮','扁一点','更扁','shorter','flatter'), 'eye_height',.90,'mul'),
      (('高一点','更高','taller'), 'eye_height',1.10,'mul'),
      (('宽一点','更宽','wider'), 'eye_width',1.10,'mul'),
      (('窄一点','收窄','narrower'), 'eye_width',.90,'mul'),
      (('上眼缘再压','上眼皮压低','上缘往下压','上缘压低','上眼缘下压','lower top'), 'top_curve',-.014,'add'),
      (('上眼缘抬','上缘抬高','raise top'), 'top_curve',.014,'add'),
      (('整体上弯','更上弯','bend up'), 'whole_bend',.12,'add'),
      (('整体下弯','bend down'), 'whole_bend',-.12,'add'),
      (('再饱满','更饱满','鼓一点','fuller','plumper'), 'thickness',1.08,'mul'),
      (('再饱满','更饱满','fuller','plumper'), 'center_bulge',.035,'add'),
      (('薄一点','更薄','thinner'), 'thickness',.92,'mul'),
      (('不要那么尖','不要尖','更圆','保持圆润','rounder','less pointed'), 'corner_roundness',.07,'add'),
      (('不要水滴','不能像水滴','不要像水滴','不要钻石','not a teardrop'), 'end_taper',-.08,'add'),
      (('克制','subtle','restrained'), 'whole_bend',.8,'mul'),
      (('克制','subtle','restrained'), 'tilt',.8,'mul'),
    ]
    for phrases,key,value,op in rules:
        if key not in locks and any(t in text for t in phrases):
            # A negated narrowing request is a lock, not an instruction to narrow.
            q[key]=q[key]*value if op=='mul' else q[key]+value
            notes.append(key+' '+('×' if op=='mul' else '+')+str(value))
    notes.extend('保持 '+key for key in sorted(locks))
    return q,locks,notes

class DerivationEngine:
    def derive(self,session,base_id,semantic,prompt,measurement=None,refine_id=None):
        name=semantic_name(semantic)
        if name in ('NORMAL','HAPPY'):raise ValueError('NORMAL/HAPPY 受保护；请使用新语义名称衍生，原 Pose 可作为 Base')
        cfg=session.config
        if refine_id and refine_id not in cfg['poses']:raise ValueError('当前衍生结果不存在')
        if refine_id:name=cfg['poses'][refine_id].get('metadata',{}).get('semantic',name)
        original=deepcopy(cfg['poses'][refine_id or base_id]['shape']);shape=dict(original);notes=[]
        if not refine_id:
            if name=='SAD':shape.update(eye_height=shape['eye_height']*.82,top_curve=shape['top_curve']-.025,tilt=-5.)
            elif name=='CURIOUS':shape.update(eye_height=shape['eye_height']*1.08,tilt=5.)
            elif name=='ANNOYED':shape.update(eye_height=shape['eye_height']*.72,top_curve=shape['top_curve']-.018,tilt=8.)
            elif name=='SURPRISED':shape.update(eye_height=shape['eye_height']*1.20,corner_roundness=max(.70,shape['corner_roundness']))
            notes.append('内部 Family: '+FAMILIES.get(name,'NEUTRAL'))
            if measurement and measurement.get('usable'):
                shape['eye_width']=measurement['width']/(1+shape['stretch'])
                shape['eye_height']=measurement['height']/((1-shape['squash'])*shape['thickness'])
                shape['eye_gap']=measurement['gap'];notes.append('参考图仅拟合宽/高/间隔')
        shape,locks,mapped=apply_text(shape,prompt);notes+=mapped
        shape=style_guard(shape)
        for key in locks:shape[key]=original[key]
        shape,fraction=fit_safe(original,shape,cfg['display'])
        if not mapped and prompt.strip():notes.append('未识别到支持的文字方向；未按任意自然语言猜测修改')
        if fraction<1:notes.append('安全约束将变形强度降低至 '+str(round(fraction,2)))
        candidate=deepcopy(cfg)
        pid=refine_id
        if not pid:
            pid=next((p for p,v in cfg['poses'].items() if v['name'].upper()==name and not v.get('archived')),None)
            if pid and cfg['poses'][pid]['builtin']:raise ValueError('不能覆盖已确认内置 Pose')
            if pid is None:
                import uuid
                pid='pose_'+uuid.uuid4().hex[:12]
                candidate['poses'][pid]=record(name,original)
        candidate['poses'][pid]['shape']=shape
        candidate['poses'][pid]['metadata']=dict(semantic=name,family=FAMILIES.get(name,'NEUTRAL'),
            derived=True,base=base_id,last_prompt=prompt,reference_used=bool(measurement and measurement.get('usable')))
        candidate['selection']['selected']=pid
        validate_config(candidate);session.commit(candidate)
        return pid,notes

