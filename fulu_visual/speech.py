"""Replaceable STT. Recording produces audio, never a guessed/fixed-phrase transcript."""
import ctypes,json,os,threading,uuid
from pathlib import Path
from urllib.request import Request,build_opener
from urllib.error import HTTPError,URLError
from .ai_settings import validate_endpoint
from .ai_provider import NoRedirect

class STTProvider:
    def __init__(self,settings):self.settings=dict(settings)
    def transcribe(self,audio):
        p=self.settings
        if p['provider']=='Disabled':raise ValueError('STT 待接；请在 Settings 配置真实语音服务')
        if p['provider']=='OpenAI' and not p['key']:raise ValueError('STT 需要真实 API Key')
        if not p['model']:raise ValueError('请设置 STT Model')
        boundary='fulu'+uuid.uuid4().hex
        fields=[]
        for key,value in (('model',p['model']),('response_format','json')):
            fields.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+key+'"\r\n\r\n'+value+'\r\n').encode())
        fields.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="speech.wav"\r\nContent-Type: audio/wav\r\n\r\n').encode()+audio+b'\r\n')
        body=b''.join(fields)+('--'+boundary+'--\r\n').encode()
        headers={'Content-Type':'multipart/form-data; boundary='+boundary}
        if p['key']:headers['Authorization']='Bearer '+p['key']
        req=Request(validate_endpoint(p['endpoint'])+'/audio/transcriptions',body,headers)
        try:
            with build_opener(NoRedirect()).open(req,timeout=p['timeout']) as response:raw=response.read(100001)
            if len(raw)>100000:raise ValueError('STT 返回过大')
            data=json.loads(raw);text=data.get('text')
            if not isinstance(text,str) or not text.strip() or len(text)>6000:raise ValueError('STT 未返回有效文字')
            return text.strip()
        except HTTPError as exc:raise ValueError('STT HTTP '+str(exc.code)+'；请检查服务配置') from None
        except (OSError,URLError,TimeoutError):raise ValueError('STT 网络不可用；请继续打字') from None
        except (ValueError,TypeError,AttributeError) as exc:
            if isinstance(exc,json.JSONDecodeError):raise ValueError('STT 返回格式无效') from None
            raise

class STTRegistry:
    factories={}
    @classmethod
    def create(cls,settings):return cls.factories.get(settings['provider'],STTProvider)(settings)

class SpeechInput:
    def __init__(self):self.stop=threading.Event();self.cancelled=False
    def finish(self):self.stop.set()
    def cancel(self):self.cancelled=True;self.stop.set()
    def record(self,seconds=10.):
        if os.name!='nt':raise ValueError('当前录音适配器需要 Windows；STT 接口可替换')
        alias='fulu'+uuid.uuid4().hex
        directory=Path(__file__).resolve().parents[1]/'.cache/tmp';directory.mkdir(parents=True,exist_ok=True)
        path=directory/(alias+'.wav')
        api=ctypes.windll.winmm.mciSendStringW
        def command(text):
            if api(text,None,0,None):raise ValueError('无法录音，请检查默认麦克风和系统麦克风权限')
        try:
            command('open new type waveaudio alias '+alias)
            command('set '+alias+' time format milliseconds bitspersample 16 channels 1 samplespersec 16000 bytespersec 32000 alignment 2')
            command('record '+alias);self.stop.wait(seconds)
            command('stop '+alias)
            if self.cancelled:return b''
            command('save '+alias+' "'+str(path)+'"');return path.read_bytes()
        finally:
            api('close '+alias,None,0,None)
            if path.exists():path.unlink()
    def recognize(self,settings=None,wave_path=None):
        if not settings or settings.get('provider')=='Disabled':raise ValueError('STT 待接；未启用语音识别')
        if settings.get('provider')=='OpenAI' and not settings.get('key'):raise ValueError('STT 待接：缺少 API Key')
        self.stop.clear();self.cancelled=False
        audio=Path(wave_path).read_bytes() if wave_path else self.record()
        if self.cancelled:return ''
        return STTRegistry.create(settings).transcribe(audio)
