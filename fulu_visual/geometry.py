"""Shared shape mathematics, independent of window, storage or product semantics."""
import math

EPSILON=1e-7
EYE_DEFAULTS=dict(position_x=0.,position_y=0.,scale=1.,rotation=0.,opacity=1.)
for _side in ('left','right'):
    for _key,_default in dict(width_scale=1.,height_scale=1.,x=0.,y=0.,rotation=0.,opacity=1.,bend=0.).items():
        EYE_DEFAULTS[_side+'_'+_key]=_default

def visible(p):
    return p['eye_width']>0 and p['eye_height']>0 and p['thickness']>0 and p['squash']<1 and p['stretch']>-1 and p.get('scale',1)>0

def side_shape(shape,side):
    p=dict(shape)
    p['eye_width']*=p.get(side+'_width_scale',1.)*p.get('scale',1.)
    vertical=p.get(side+'_height_scale',1.)*p.get('scale',1.)
    p['eye_height']*=vertical
    p['top_curve']*=vertical;p['bottom_curve']*=vertical
    p['whole_bend']+=p.get(side+'_bend',0.)
    if side+'_contour' in shape:
        p['contour']=shape[side+'_contour']
        p['contour_mix']=shape.get(side+'_contour_mix',1.)
    return p


def dimensions(p):
    a=max(EPSILON,p['eye_width']*(1+p['stretch'])/2)
    b=max(EPSILON,p['eye_height']*(1-p['squash'])*p['thickness']/2)
    k=p['whole_bend']
    compression=1-(1-p['volume_preserve'])*(1-1/(1+.7*k*k))
    return a,b,p['corner_roundness']*min(a,b),k,compression

def deform(p,x,y):
    a,b,_,k,compression=dimensions(p)
    u=x/a
    arch=max(0.,1-u*u)
    profile=(1+p['center_bulge']*arch)*(1-p['end_taper']*u*u)*compression
    top=p['top_curve']*(1-p['squash'])
    bottom=p['bottom_curve']*(1-p['squash'])
    v=y*profile+(top+bottom)*.5*arch+y/(2*b)*(top-bottom)*arch
    if abs(k)<1e-4:
        return x,v
    radius=a/k
    angle=x/radius
    return (radius+v)*math.sin(angle),(radius+v)*math.cos(angle)-radius*math.cos(k)

def outline(p,samples=16):
    a,b,r,_,_=dimensions(p)
    points=[]
    angle=math.radians(p['tilt'])
    ca,sa=math.cos(angle),math.sin(angle)
    if p.get('contour') and p.get('contour_mix',1.)>0:
        polygon=render_contour(p)
        for i,(x0,y0) in enumerate(polygon):
            x1,y1=polygon[(i+1)%len(polygon)]
            for j in range(8):
                t=j/8;x,y=deform(p,(x0+(x1-x0)*t)*a,(y0+(y1-y0)*t)*b)
                points.append((ca*x-sa*y,sa*x+ca*y))
        if p.get('contour_mix',1.)<1:
            legacy=dict(p);legacy.pop('contour');points+=outline(legacy,samples)
        return points
    corners=((1,1,0),(-1,1,math.pi/2),(-1,-1,math.pi),(1,-1,3*math.pi/2))
    for index,(sx,sy,start) in enumerate(corners):
        for i in range(samples+1):
            theta=start+math.pi/2*i/samples
            x=sx*(a-r)+r*math.cos(theta)
            y=sy*(b-r)+r*math.sin(theta)
            x,y=deform(p,x,y)
            points.append((ca*x-sa*y,sa*x+ca*y))
        # Connect consecutive corners in perimeter order; these edges also bend.
        end=start+math.pi/2
        x0=sx*(a-r)+r*math.cos(end);y0=sy*(b-r)+r*math.sin(end)
        nx,ny,ns=corners[(index+1)%4]
        x1=nx*(a-r)+r*math.cos(ns);y1=ny*(b-r)+r*math.sin(ns)
        for i in range(1,samples*2):
            t=i/(samples*2)
            x=x0+(x1-x0)*t;y=y0+(y1-y0)*t
            x,y=deform(p,x,y)
            points.append((ca*x-sa*y,sa*x+ca*y))
    return points

def bounds(p):
    weight=p.get('contour_mix',1.)
    if p.get('contour') and 0<weight<1:
        legacy=dict(p);legacy.pop('contour');polygon=dict(p,contour_mix=1.)
        return tuple(a+(b-a)*weight for a,b in zip(bounds(legacy),bounds(polygon)))
    pts=outline(p)
    return min(x for x,y in pts),max(x for x,y in pts),min(y for x,y in pts),max(y for x,y in pts)

CONTOUR_KEYS=('contour','left_contour','right_contour')
CONTOUR_FIELDS=set(CONTOUR_KEYS)|{k+'_mix' for k in CONTOUR_KEYS}

def validate_contour(points):
    if not isinstance(points,(list,tuple)) or not 3<=len(points)<=64:
        raise ValueError('Contour 需要 3–64 个顶点')
    for p in points:
        if not isinstance(p,(list,tuple)) or len(p)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1 for v in p):
            raise ValueError('Contour 坐标必须为 [-1,1] 有限数值')
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    area=sum(points[i][0]*points[(i+1)%len(points)][1]-points[(i+1)%len(points)][0]*points[i][1] for i in range(len(points)))
    if abs(area)<1e-6:raise ValueError('Contour 不能退化为零面积；隐藏请使用 Scale/Opacity=0')
    for i,a in enumerate(points):
        b=points[(i+1)%len(points)]
        if math.dist(a,b)<1e-6:raise ValueError('Contour 相邻点不能重合')
        for j in range(i+2,len(points)):
            if i==0 and j==len(points)-1:continue
            c,d=points[j],points[(j+1)%len(points)]
            if cross(a,b,c)*cross(a,b,d)<=0 and cross(c,d,a)*cross(c,d,b)<=0 and max(min(a[0],b[0]),min(c[0],d[0]))<=min(max(a[0],b[0]),max(c[0],d[0])) and max(min(a[1],b[1]),min(c[1],d[1]))<=min(max(a[1],b[1]),max(c[1],d[1])):
                raise ValueError('Contour 不允许自交')
    return points

def seed_contour(kind):
    if kind=='rectangle':return [[1,1],[-1,1],[-1,-1],[1,-1]]
    if kind=='triangle':return [[0,1],[-1,-1],[1,-1]]
    if kind=='circle':return [[math.cos(i*math.tau/32),math.sin(i*math.tau/32)] for i in range(32)]
    raise ValueError('Unknown contour seed')

def render_contour(shape):
    points=shape.get('contour',[]);amount=shape['corner_roundness']
    if not points or amount<=0:return points
    # Rounded vertices are still derived from the editable closed contour, not a shape enum.
    steps=max(1,64//len(points)-1);out=[]
    for i,p in enumerate(points):
        prev,nxt=points[i-1],points[(i+1)%len(points)]
        radius=.48*amount*min(math.dist(prev,p),math.dist(p,nxt))
        start=[p[k]+(prev[k]-p[k])*radius/max(EPSILON,math.dist(prev,p)) for k in (0,1)]
        end=[p[k]+(nxt[k]-p[k])*radius/max(EPSILON,math.dist(nxt,p)) for k in (0,1)]
        for j in range(steps+1):
            t=j/steps
            out.append([(1-t)**2*start[k]+2*t*(1-t)*p[k]+t*t*end[k] for k in (0,1)])
    return out if len(out)<=64 else resample_contour(out)

def legacy_contour(p):
    a,b,r,_,_=dimensions(p);points=[]
    for sx,sy,start in ((1,1,0),(-1,1,math.pi/2),(-1,-1,math.pi),(1,-1,3*math.pi/2)):
        for i in range(8):
            t=start+math.pi/2*i/7
            point=[(sx*(a-r)+r*math.cos(t))/a,(sy*(b-r)+r*math.sin(t))/b]
            if not points or math.dist(points[-1],point)>1e-6:points.append(point)
    if math.dist(points[0],points[-1])<1e-6:points.pop()
    return points

def resample_contour(points,n=64):
    pts=[list(p) for p in points]
    if sum(pts[i][0]*pts[(i+1)%len(pts)][1]-pts[(i+1)%len(pts)][0]*pts[i][1] for i in range(len(pts)))<0:pts.reverse()
    start=max(range(len(pts)),key=lambda i:(pts[i][0],pts[i][1]));pts=pts[start:]+pts[:start]
    lengths=[math.dist(pts[i],pts[(i+1)%len(pts)]) for i in range(len(pts))]
    total=sum(lengths);out=[];j=0;distance=0.
    for i in range(n):
        target=total*i/n
        while j<len(pts)-1 and distance+lengths[j]<target:distance+=lengths[j];j+=1
        t=(target-distance)/max(EPSILON,lengths[j]);a,b=pts[j],pts[(j+1)%len(pts)]
        out.append([a[k]+(b[k]-a[k])*t for k in (0,1)])
    return out

def mix_shape(a,b,u):
    if u<=0:return dict(a)
    if u>=1:return dict(b)
    result={key:a.get(key,EYE_DEFAULTS.get(key,0))+(b.get(key,EYE_DEFAULTS.get(key,0))-a.get(key,EYE_DEFAULTS.get(key,0)))*u for key in (a.keys()|b.keys())-CONTOUR_FIELDS}
    for key in CONTOUR_KEYS:
        if key not in a and key not in b:continue
        side=key.split('_')[0] if key!='contour' else None
        def effective(p):
            own=side_shape(p,side) if side else p
            return own.get('contour',legacy_contour(own)),own.get('contour_mix',1.) if 'contour' in own else 0.
        pa,wa=effective(a);pb,wb=effective(b)
        if pa==pb:result[key]=pa
        else:
            pa=resample_contour(pa);pb=resample_contour(pb)
            result[key]=[[x+(y-x)*u for x,y in zip(aa,bb)] for aa,bb in zip(pa,pb)]
        result[key+'_mix']=wa+(wb-wa)*u
    return result
