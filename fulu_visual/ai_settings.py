"""Local-only provider preferences; Windows DPAPI protects secrets at rest."""
from copy import deepcopy
from pathlib import Path
import base64, ctypes, json, os
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
PROVIDERS=('OpenAI','DeepSeek','Local AI','Custom')
DEFAULTS=dict(provider='OpenAI',auto_connect=True,fallback=False,timeout=30.,stt_provider='Disabled',
    profiles={
      'OpenAI':dict(model='gpt-4.1-mini',endpoint='https://api.openai.com/v1',secret=''),
      'DeepSeek':dict(model='deepseek-chat',endpoint='https://api.deepseek.com',secret=''),
      'Local AI':dict(model='',endpoint='http://127.0.0.1:11434/v1',secret=''),
      'Custom':dict(model='',endpoint='',secret=''),
      'STT':dict(model='gpt-4o-mini-transcribe',endpoint='https://api.openai.com/v1',secret='')})

class Blob(ctypes.Structure):
    _fields_=[('size',ctypes.c_ulong),('data',ctypes.POINTER(ctypes.c_ubyte))]

def crypt(data,decrypt=False):
    if os.name!='nt':raise ValueError('此版本密钥保存需要 Windows DPAPI')
    buf=ctypes.create_string_buffer(data);source=Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)));out=Blob()
    api=ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    if not api(ctypes.byref(source),None,None,None,None,1,ctypes.byref(out)):raise ValueError('本机密钥加密/解密失败')
    try:return ctypes.string_at(out.data,out.size)
    finally:
        free=ctypes.windll.kernel32.LocalFree;free.argtypes=[ctypes.c_void_p];free.restype=ctypes.c_void_p
        free(out.data)

def validate_endpoint(endpoint):
    p=urlsplit(endpoint)
    if p.username or p.password or p.query or p.fragment or not p.hostname:raise ValueError('Endpoint 必须是无凭据/查询串的 API 基础地址')
    if p.scheme!='https' and not (p.scheme=='http' and p.hostname in ('localhost','127.0.0.1','::1')):
        raise ValueError('远程 Endpoint 使用 HTTPS；本机可使用 HTTP')
    return endpoint.rstrip('/')

class AISettings:
    def __init__(self,path=None):
        self.path=Path(path or ROOT/'data/ai_settings.local.json')
        self.data=deepcopy(DEFAULTS);self.error=''
        if self.path.exists():
            try:
                loaded=json.loads(self.path.read_text(encoding='utf-8-sig'))
                if isinstance(loaded,dict) and loaded.get('provider')=='Rule Fallback':loaded['provider']='OpenAI'
                if not isinstance(loaded,dict) or loaded.get('provider') not in PROVIDERS:raise ValueError('未知 Provider')
                for k in ('provider','auto_connect','fallback','timeout','stt_provider'):
                    if k in loaded:self.data[k]=loaded[k]
                if not isinstance(loaded.get('profiles',{}),dict):raise ValueError('Invalid profiles')
                for name,profile in loaded.get('profiles',{}).items():
                    if not isinstance(profile,dict):raise ValueError('Invalid profile')
                    if name in self.data['profiles']:self.data['profiles'][name].update({k:v for k,v in profile.items() if k in ('model','endpoint','secret')})
                self.validate()
            except (OSError,ValueError,TypeError,KeyError):
                self.data=deepcopy(DEFAULTS);self.error='AI 设置读取失败；可在 Settings 重新保存，手动编辑可用'
    def validate(self):
        if self.data['stt_provider'] not in ('Disabled','OpenAI','Custom'):raise ValueError('未知 STT Provider')
        if self.data['provider'] not in PROVIDERS:raise ValueError('未知 Provider')
        if any(not isinstance(self.data[k],bool) for k in ('auto_connect','fallback')):raise ValueError('Invalid settings flags')
        if not 1<=self.data['timeout']<=120:raise ValueError('Timeout 必须为 1–120 秒')
        for name,p in self.data['profiles'].items():
            if any(not isinstance(p.get(k),str) for k in ('model','endpoint','secret')):raise ValueError('设置字段无效')
            if p['endpoint']:validate_endpoint(p['endpoint'])
    def key(self,name=None):
        name=name or self.data['provider'];encoded=self.data['profiles'][name]['secret']
        if encoded:return crypt(base64.b64decode(encoded),True).decode('utf-8')
        return os.environ.get({'OpenAI':'OPENAI_API_KEY','DeepSeek':'DEEPSEEK_API_KEY'}.get(name,''),'')
    def set_key(self,value,name=None):
        name=name or self.data['provider']
        self.data['profiles'][name]['secret']=base64.b64encode(crypt(value.encode())).decode('ascii') if value else ''
    def save(self):
        self.validate();self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(tmp,self.path)
    def connection(self):
        name=self.data['provider'];p=self.data['profiles'][name]
        return dict(provider=name,model=p['model'].strip(),endpoint=p['endpoint'].strip(),key=self.key(name),
                    timeout=self.data['timeout'],fallback=self.data['fallback'])

    def stt_connection(self):
        name=self.data['stt_provider'];p=self.data['profiles']['STT']
        return dict(provider=name,model=p['model'].strip(),endpoint='https://api.openai.com/v1' if name=='OpenAI' else p['endpoint'].strip(),
                    key=self.key('STT') or (self.key('OpenAI') if name=='OpenAI' else ''),timeout=self.data['timeout'])
