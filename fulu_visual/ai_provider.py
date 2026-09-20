"""Replaceable OpenAI-compatible interpreter; bounded HTTP, validated contours, no code execution."""
import json
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from .ai_settings import validate_endpoint
from .eye_intent import SCHEMA,validate_intent

SYSTEM="""You interpret instructions for a real-time procedural two-eye editor. Return JSON only, matching the supplied Eye Intent schema.
Use the current shape as context; modifications are incremental. A semantic like happy changes the current eyes, not an image.
Allowed sections: shape, left, right, volume, motion. No Accent, files, URLs, pixels, image generation, code, mouth, eyebrows, pupils, iris, highlights, or realism.
Use operations set/add/multiply and valid parameter names/ranges only. Avoid unrelated changes, especially volume/material.
shape uses shared width/height/gap, whole_bend, curves, thickness, bulge, taper, tilt, squash/stretch and position/scale/rotation/opacity.
left/right width_scale and height_scale modify each eye independently (zero closes/hides it); x/y are gaze offsets; bend is added to shared whole_bend.
Upward whole-body arch uses positive whole_bend. Width/height are viewport-height units, rotations are degrees, bend is radians.
Contours are editable closed polygons, NOT fixed shape types. Return contours=[] for no contour change.
For contour edits return ordered simple polygons: eye shared/left/right, points [{x,y}], 3..64 vertices, normalized [-1,1], y up, implicit closure.
For input images identify ONLY the two eye silhouettes; ignore mouth/background/accents. Output left/right contours and width/height/position operations as needed. No raster output.
Existing contour points are pre-deformation coordinates. Preserve existing shape transforms unless explicitly changing them. For tracing an image use zero bend/curves/bulge/taper, thickness=1,squash=0,stretch=0 to avoid double deformation.
Preserve requested width. No random emotion. Empty operations when impossible. label is optional semantic text or empty, never ROOT or VERY_*.
"""
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('AI Endpoint 重定向被拒绝，请填写最终 API 地址')

class AIProvider:
    def __init__(self,settings):self.settings=dict(settings)
    def interpret(self,prompt,ctx,image=None):
        p=self.settings
        if p['provider']=='Rule Fallback':raise ValueError('Rule Fallback 已停用；请连接真实 AI')
        if not p['model']:raise ValueError('请在 Settings / AI 填写 Model')
        if p['provider'] in ('OpenAI','DeepSeek') and not p['key']:raise ValueError('请在 Settings / AI 保存 API Key')
        endpoint=validate_endpoint(p['endpoint'])
        fmt=dict(type='json_schema',json_schema=dict(name='eye_intent',strict=True,schema=SCHEMA)) if p['provider']=='OpenAI' else dict(type='json_object')
        content=json.dumps(dict(instruction=prompt,eyes=ctx),ensure_ascii=False)
        if image:
            content=[dict(type='text',text=content),dict(type='image_url',image_url=dict(url=image,detail='high'))]
        payload=dict(model=p['model'],messages=[dict(role='system',content=SYSTEM+'\nJSON Schema: '+json.dumps(SCHEMA)),
             dict(role='user',content=content)],response_format=fmt)
        headers={'Content-Type':'application/json'}
        if p['key']:headers['Authorization']='Bearer '+p['key']
        req=Request(endpoint+'/chat/completions',json.dumps(payload,ensure_ascii=False).encode('utf-8'),headers)
        try:
            with build_opener(NoRedirect()).open(req,timeout=p['timeout']) as response:
                raw=response.read(2_000_001)
            if len(raw)>2_000_000:raise ValueError('AI 回复过大')
            data=json.loads(raw)
            msg=data['choices'][0]['message']
            if msg.get('refusal'):raise ValueError('AI 未提供可用眼睛参数')
            content=msg['content']
            if not isinstance(content,str):raise ValueError('AI 回复不是 JSON 文本')
            return validate_intent(json.loads(content))
        except HTTPError as exc:raise ValueError('AI HTTP '+str(exc.code)+'；检查设置、额度或模型权限') from None
        except (URLError,TimeoutError,OSError):raise ValueError('AI 网络连接失败或超时；手动编辑仍可用') from None
        except (KeyError,IndexError,json.JSONDecodeError):raise ValueError('AI 回复格式无效，未应用') from None
    def test(self):
        return self.interpret('Connection test only. Return {"label":"","operations":[],"contours":[]}.',{})

class ProviderRegistry:
    """Small explicit factory; no dynamic code loading."""
    factories={}
    @classmethod
    def create(cls,settings):
        factory=cls.factories.get(settings['provider'],AIProvider)
        return factory(settings)
