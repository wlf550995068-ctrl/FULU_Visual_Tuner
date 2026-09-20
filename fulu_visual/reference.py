"""Non-destructive raster reference loading and optional two-body measurements."""
from pathlib import Path
from hashlib import sha256
from collections import deque
import shutil
import numpy as np
from PIL import Image,ImageOps

class ReferenceImage:
    def __init__(self):
        self.path=None;self.image=None;self.texture=None;self.measurement=None
    def load(self,path,assets=None):
        path=Path(str(path).strip().strip('"')).expanduser()
        if not path.is_file():raise ValueError('参考图不存在')
        if path.suffix.lower() not in ('.png','.jpg','.jpeg','.webp','.bmp'):
            raise ValueError('支持 PNG / JPG / WEBP / BMP 静态参考图')
        try:
            src=Image.open(path)
        except Image.DecompressionBombError as exc:
            raise ValueError("参考图像素过大，请使用较小版本") from exc
        with src:
            if src.width*src.height>24_000_000:raise ValueError('参考图超过 2400 万像素，请先使用较小版本')
            im=ImageOps.exif_transpose(src).convert('RGBA')
        if assets:
            assets=Path(assets);assets.mkdir(parents=True,exist_ok=True)
            dest=assets/(sha256(path.read_bytes()).hexdigest()[:20]+path.suffix.lower())
            if path.resolve()!=dest.resolve() and not dest.exists():shutil.copy2(path,dest)
            path=dest
        im.thumbnail((4096,4096),Image.Resampling.LANCZOS)
        self.path=path;self.image=im;self.measurement=self.measure(im)
        return self.measurement
    def ai_payload(self):
        import base64,io
        if self.image is None:raise ValueError('请先导入图片')
        image=self.image.copy();image.thumbnail((1024,1024),Image.Resampling.LANCZOS)
        stream=io.BytesIO();image.save(stream,format='PNG')
        return 'data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode('ascii')
    def upload(self,ctx,gui):
        if self.texture:
            gui.remove_texture(self.texture);self.texture.release()
        self.texture=ctx.texture(self.image.size,4,self.image.tobytes())
        import moderngl
        self.texture.filter=(moderngl.LINEAR,moderngl.LINEAR)
        gui.register_texture(self.texture)
    @staticmethod
    def measure(image):
        im=image.copy();im.thumbnail((256,160))
        a=np.asarray(im.convert('RGBA'),dtype=float)/255
        rgb=a[:,:,:3];alpha=a[:,:,3]
        border=np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]))
        bg=np.median(border,axis=0)
        mask=(np.max(abs(rgb-bg),axis=2)>.16)&(alpha>.5)
        seen=np.zeros(mask.shape,bool);components=[]
        h,w=mask.shape
        for y,x in zip(*np.where(mask)):
            if seen[y,x]:continue
            queue=deque([(y,x)]);seen[y,x]=True;points=[]
            while queue:
                py,px=queue.popleft();points.append((py,px))
                for ny,nx in ((py-1,px),(py+1,px),(py,px-1),(py,px+1)):
                    if 0<=ny<h and 0<=nx<w and mask[ny,nx] and not seen[ny,nx]:
                        seen[ny,nx]=True;queue.append((ny,nx))
            if len(points)>20:
                ys,xs=zip(*points);components.append((len(points),min(xs),max(xs)+1,min(ys),max(ys)+1))
        components=sorted(components,reverse=True)[:2]
        if len(components)!=2:return dict(usable=False,reason='未检测到两个清晰主体；仅作 Overlay 参考')
        left,right=sorted(components,key=lambda c:c[1])
        area_ratio=left[0]/right[0]
        if not .4<area_ratio<2.5 or left[2]>=right[1] or abs((left[3]+left[4]-right[3]-right[4])/2)>.18*h:
            return dict(usable=False,reason='双主体测量置信度不足；仅作 Overlay 参考')
        return dict(usable=True,width=((left[2]-left[1])+(right[2]-right[1]))/(2*h),
                    height=((left[4]-left[3])+(right[4]-right[3]))/(2*h),
                    gap=(right[1]-left[2])/h,reason='仅提取两个亮主体的宽/高/间隔，不识别语义或材质')
    @staticmethod
    def placement(image_size,rect,mode,zoom,x,y):
        x0,y0,x1,y1=rect;w,h=image_size
        factor=min((x1-x0)/w,(y1-y0)/h) if mode=='Fit' else max((x1-x0)/w,(y1-y0)/h) if mode=='Fill' else 1.
        factor*=zoom;rw,rh=w*factor,h*factor
        cx=(x0+x1)/2+x*(y1-y0);cy=(y0+y1)/2-y*(y1-y0)
        return cx-rw/2,cy-rh/2,cx+rw/2,cy+rh/2

