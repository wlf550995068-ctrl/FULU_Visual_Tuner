"""Strict eyes-only contract and local transactional solver. No renderer access."""
from copy import deepcopy
import json,math,re,uuid
from .config import SHAPE_PARAMETERS,EYE_PARAMETERS,VOLUME_PARAMETERS,MOTION_PARAMETERS,validate_config,record
from .geometry import EYE_DEFAULTS,mix_shape,validate_contour
from .derive import apply_text

RANGES={s:{k:(lo,hi) for k,_,lo,hi,_ in parameters}
        for s,parameters in (('shape',SHAPE_PARAMETERS+EYE_PARAMETERS[:5]),('volume',VOLUME_PARAMETERS),('motion',MOTION_PARAMETERS))}
SIDE_RANGES={k.removeprefix('left_'):(lo,hi) for k,_,lo,hi,_ in EYE_PARAMETERS if k.startswith('left_')}
RANGES.update(left=SIDE_RANGES,right=SIDE_RANGES)
SCHEMA=dict(type='object',additionalProperties=False,required=['label','operations'],
    properties=dict(label=dict(type='string'),operations=dict(type='array',items=dict(
        type='object',additionalProperties=False,required=['section','parameter','op','value'],
        properties=dict(section=dict(type='string',enum=list(RANGES)),
                        parameter=dict(type='string',enum=sorted(set(k for group in RANGES.values() for k in group))),
                        op=dict(type='string',enum=['set','add','multiply']),value=dict(type='number'))))))
SCHEMA['required'].append('contours')
SCHEMA['properties']['contours']=dict(type='array',maxItems=3,items=dict(type='object',additionalProperties=False,
    required=['eye','points'],properties=dict(eye=dict(type='string',enum=['shared','left','right']),
    points=dict(type='array',minItems=3,maxItems=64,items=dict(type='object',additionalProperties=False,
    required=['x','y'],properties=dict(x=dict(type='number'),y=dict(type='number')))))))

def validate_intent(data):
    if not isinstance(data,dict) or set(data)-{'label','operations','contours'} or not {'label','operations'}<=set(data):raise ValueError('AI 返回不符合 Eye Intent 结构')
    label=data['label']
    if not isinstance(label,str) or len(label)>40 or 'ROOT' in label.upper() or label.upper().startswith('VERY_'):
        raise ValueError('AI Pose 标签无效')
    if not isinstance(data['operations'],list) or len(data['operations'])>64:raise ValueError('AI 操作列表无效')
    for op in data['operations']:
        if not isinstance(op,dict) or set(op)!={'section','parameter','op','value'}:raise ValueError('AI 操作字段无效')
        if op['section'] not in RANGES or op['parameter'] not in RANGES[op['section']]:raise ValueError('AI 只能编辑白名单 Eye 参数')
        v=op['value']
        if op['op'] not in ('set','add','multiply') or isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):
            raise ValueError('AI 参数必须为有限数值')
    contours=data.get('contours',[])
    if not isinstance(contours,list) or len(contours)>3:raise ValueError('Contour intent 无效')
    seen=set()
    for item in contours:
        if not isinstance(item,dict) or set(item)!={'eye','points'} or item['eye'] not in ('shared','left','right') or item['eye'] in seen:raise ValueError('Contour eye 无效')
        seen.add(item['eye'])
        if not isinstance(item['points'],list) or any(not isinstance(p,dict) or set(p)!={'x','y'} for p in item['points']):raise ValueError('Contour points 无效')
        validate_contour([[p['x'],p['y']] for p in item['points']])
    return deepcopy(data)

def context(cfg,pid):
    return dict(shape=deepcopy(cfg['poses'][pid]['shape']),volume=deepcopy(cfg['volume']),motion=deepcopy(cfg['motion']),
                limits=RANGES,eye_defaults=EYE_DEFAULTS)

def fingerprint(cfg,pid):
    return json.dumps(dict(id=pid,context=context(cfg,pid)),sort_keys=True)

def solve(cfg,pid,intent):
    intent=validate_intent(intent)
    if not intent['operations'] and not intent.get('contours'):raise ValueError('没有可应用的眼睛参数；请换一句描述')
    original=deepcopy(cfg);candidate=deepcopy(cfg);shape=candidate['poses'][pid]['shape']
    for item in intent['operations']:
        section,key=item['section'],item['parameter']
        lo,hi=RANGES[section][key]
        target=shape if section in ('shape','left','right') else candidate[section]
        key=section+'_'+key if section in ('left','right') else key
        old=target.get(key,EYE_DEFAULTS.get(key,0.));v=item['value']
        value=v if item['op']=='set' else old+v if item['op']=='add' else old*v
        if not math.isfinite(value):raise ValueError('AI 计算溢出')
        target[key]=max(lo,min(hi,value))
    if intent.get('contours') and not any(o['section']=='shape' and o['parameter']=='corner_roundness' for o in intent['operations']):shape['corner_roundness']=0.
    for item in intent.get('contours',[]):
        key='contour' if item['eye']=='shared' else item['eye']+'_contour'
        shape[key]=[[p['x'],p['y']] for p in item['points']];shape.pop(key+'_mix',None)
        if key=='contour':
            for side in ('left','right'):shape.pop(side+'_contour',None);shape.pop(side+'_contour_mix',None)
    # Fit one intent continuously toward current state; never generate candidates for users.
    for step in range(40):
        strength=1-step/40
        trial=deepcopy(candidate)
        trial['poses'][pid]['shape']=mix_shape(original['poses'][pid]['shape'],shape,strength)
        for section in ('volume','motion'):
            trial[section]={k:original[section][k]+(candidate[section][k]-original[section][k])*strength for k in original[section]}
        try:validate_config(trial)
        except ValueError:continue
        return trial,strength
    raise ValueError('这次参数要求无法安全应用；当前眼睛未改动')

def apply_intent(session,pid,intent,base_shape=None):
    source=deepcopy(session.config)
    if base_shape is not None:source['poses'][pid]['shape']=deepcopy(base_shape)
    candidate,strength=solve(source,pid,intent)
    # Keep approved builtins untouched. Subsequent Apply edits the currently selected result.
    if candidate['poses'][pid]['builtin']:
        name=intent['label'].strip() or 'EDIT'
        existing={p['name'].casefold() for p in candidate['poses'].values()}
        if name.casefold() in existing:name='EDIT'
        base=name;i=1
        while name.casefold() in existing:name=base+'_'+str(i);i+=1
        newid='pose_'+uuid.uuid4().hex[:12]
        candidate['poses'][newid]=record(name,candidate['poses'][pid]['shape'])
        candidate['poses'][pid]=deepcopy(session.config['poses'][pid])
        pid=newid
    candidate['poses'][pid]['metadata']=dict(candidate['poses'][pid].get('metadata',{}),eye_intent=True)
    candidate['selection']['selected']=pid
    session.commit(candidate)
    return pid,strength

def rule_intent(prompt,ctx,poses=None):
    old=ctx['shape'];shape=dict(old);text=prompt.lower()
    if any(w in text for w in ('开心','happy')):
        if poses:shape.update(poses['happy']['shape'])
        else:shape.update(whole_bend=.7,eye_height=old['eye_height']*.6)
    elif any(w in text for w in ('正常','normal')) and poses:shape.update(poses['normal']['shape'])
    elif any(w in text for w in ('难过','伤心','sad')):shape.update(eye_height=old['eye_height']*.82,tilt=-5.)
    shape,_,_=apply_text(shape,text.replace('圆一点','更圆').replace('再扁一点','扁一点'))
    if any(w in text for w in ('消失','隐藏眼睛','hide eyes')):shape['opacity']=0.
    if any(w in text for w in ('显示眼睛','show eyes')):shape['opacity']=1.
    ops=[dict(section='shape',parameter=k,op='set',value=v) for k,v in shape.items() if k in RANGES['shape'] and v!=old.get(k,EYE_DEFAULTS.get(k))]
    if not ops:raise ValueError('Limited / Fallback：仅识别开心、变扁、变圆、上下弯、饱满、消失等有限描述')
    label='SAD' if any(w in text for w in ('难过','伤心','sad')) else 'HAPPY' if any(w in text for w in ('开心','happy')) else ''
    return validate_intent(dict(label=label,operations=ops))
