"""One input, one Apply. Network/dictation workers never touch GL or editor state."""
from copy import deepcopy
from queue import Queue,Empty
from threading import Thread
from imgui_bundle import imgui
from .ai_settings import AISettings,PROVIDERS,DEFAULTS as AI_DEFAULTS
from .ai_provider import ProviderRegistry
from .eye_intent import context,fingerprint,apply_intent
from .speech import SpeechInput
from .config import EYE_PARAMETERS
from .geometry import EYE_DEFAULTS,mix_shape
V=imgui.ImVec2

class AIWorkbench:
    def setup_ai(self):
        self.ai_settings=AISettings()
        self.ai_input='';self.ai_key_input='';self.stt_key_input='';self.ai_image=None;self.ai_busy=False;self.ai_connected=False
        self.ai_limited=True;self.ai_detail=self.ai_settings.error
        self.ai_events=Queue();self.ai_generation=0
        self.speech=SpeechInput();self.speech_busy=False;self.speech_generation=0
        if self.ai_settings.data['auto_connect'] and not self.argv.smoke_seconds:self.test_ai_connection()
    def worker(self,fn):
        Thread(target=fn,daemon=True).start()
    def test_ai_connection(self):
        if self.ai_busy:return
        try:
            settings=self.ai_settings.connection()
            if self.ai_key_input.strip():settings['key']=self.ai_key_input.strip()
        except ValueError as exc:self.ai_detail=str(exc);self.ai_connected=False;return
        self.ai_generation+=1;generation=self.ai_generation;self.ai_busy=True
        def run():
            try:
                if settings['provider']=='Rule Fallback':
                    self.ai_events.put(('connection',generation,False,'Limited / Fallback'))
                else:
                    ProviderRegistry.create(settings).test()
                    self.ai_events.put(('connection',generation,True,'连接测试成功 Connection verified'))
            except Exception as exc:
                self.ai_events.put(('connection',generation,False,self.safe_ai_error(exc)))
        self.worker(run)
    @staticmethod
    def safe_ai_error(exc):
        return str(exc) if isinstance(exc,ValueError) else 'AI 服务异常；手动编辑仍可用'
    def ai_view_token(self):
        if self.mode=='runtime':return (self.mode,self.runtime.target)
        if self.mode=='ab':return (self.mode,self.cfg['selection']['source'],self.cfg['selection']['target'])
        return (self.mode,)
    def generate_apply(self):
        if self.ai_busy:return
        if not self.ai_connected:raise ValueError('AI 未连接；请在 Settings 连接后使用，手动编辑可用')
        prompt=self.ai_input.strip()
        if not prompt and self.ai_image:prompt='提取图片中两只眼睛的轮廓，转换为可编辑 Contour。'
        if not prompt:raise ValueError('请输入一句眼睛修改要求')
        if len(prompt)>6000:raise ValueError('输入过长，请缩短描述')
        pid=self.selected;source=deepcopy(self.cfg);base_shape=None
        if self.mode=='runtime':base_shape=deepcopy(self.runtime.current)
        elif self.mode=='ab':
            base_shape=mix_shape(self.cfg['poses'][self.cfg['selection']['source']]['shape'],self.cfg['poses'][self.cfg['selection']['target']]['shape'],self.player.blend)
        if base_shape is not None:source['poses'][pid]['shape']=base_shape
        ctx=context(source,pid);token=fingerprint(self.cfg,pid);poses=deepcopy(self.cfg['poses'])
        view=self.ai_view_token()
        settings=self.ai_settings.connection();image=self.ai_image.ai_payload() if self.ai_image else None
        self.ai_generation+=1;generation=self.ai_generation;self.ai_busy=True
        def run():
            try:
                provider=ProviderRegistry.create(settings)
                intent=provider.interpret(prompt,ctx,image=image) if image else provider.interpret(prompt,ctx)
                if image and not intent.get('contours'):raise ValueError('AI 未提取有效 Contour；当前眼睛保持不变')
                self.ai_events.put(('apply',generation,pid,token,intent,False,'',base_shape,view))
            except Exception as exc:self.ai_events.put(('error',generation,self.safe_ai_error(exc)))
        self.worker(run)
    def toggle_microphone(self):
        if self.speech_busy:
            self.speech.finish();self.status='录音结束，等待转文字 Transcribing';return
        self.speech_busy=True;self.speech_generation+=1;generation=self.speech_generation
        before=self.ai_input
        def run():
            try:self.ai_events.put(('speech',generation,self.speech.recognize(settings=self.ai_settings.stt_connection()),before,''))
            except Exception as exc:self.ai_events.put(('speech',generation,'',before,self.safe_ai_error(exc)))
        self.worker(run)
    def accept_transcript(self,text,before):
        if not text:raise ValueError('没有识别到语音；可以重试或直接打字')
        # Never erase edits typed during dictation. There is still only one prompt.
        self.ai_input=text if self.ai_input==before else (self.ai_input+' '+text).strip()
        self.status='语音已填入输入框；点击生成 / 应用。Dictation ready.'
    def poll_ai(self):
        while True:
            try:item=self.ai_events.get_nowait()
            except Empty:return
            if item[0]=='speech':
                if item[1]!=self.speech_generation:continue
                self.speech_busy=False
                if item[4]:self.status=item[4];self.error=True
                else:self.attempt(lambda:self.accept_transcript(item[2],item[3]),'语音已填入同一输入框 Dictation ready')
                continue
            if item[1]!=self.ai_generation:continue
            self.ai_busy=False
            if item[0]=='connection':
                self.ai_connected=item[2];self.ai_limited=not item[2];self.ai_detail=item[3]
                self.status=item[3]
            elif item[0]=='error':
                self.ai_connected=False;self.ai_limited=True;self.ai_detail=item[2];self.status=item[2];self.error=True
            elif item[0]=='apply':
                _,_,pid,token,intent,fallback,detail,base_shape,view=item
                self.ai_connected=not fallback;self.ai_limited=fallback;self.ai_detail=detail
                if self.selected!=pid or fingerprint(self.cfg,pid)!=token or self.ai_view_token()!=view:
                    self.status='等待期间眼睛已变化；旧 AI 结果已丢弃，请重新 Apply';self.error=True;continue
                def commit():
                    selected,strength=apply_intent(self.session,pid,intent,base_shape)
                    self.choose_pose(selected)
                    self.last_intent=deepcopy(intent)
                self.attempt(commit,'已应用眼睛参数 Applied')
    def import_ai_image(self,path):
        from .reference import ReferenceImage
        image=ReferenceImage();image.load(path);self.ai_image=image
    def browse_ai_image(self):
        import tkinter
        from tkinter import filedialog
        root=tkinter.Tk();root.withdraw()
        try:path=filedialog.askopenfilename(title='AI 眼睛轮廓 / Eye contour',filetypes=[('Images','*.png *.jpg *.jpeg *.webp *.bmp')])
        finally:root.destroy()
        if path:self.import_ai_image(path)
    def build_ai_ui(self):
        imgui.text('AI 已连接 AI Connected' if self.ai_connected else 'AI 未连接 AI Disconnected')
        if not self.ai_connected:
            for key in ('eye-input','microphone','ai-image','apply'):self.ui_rects.pop(key,None)
            imgui.text_wrapped('请在设置 Settings 连接 AI。形状与其他手动编辑始终可用。')
            return
        imgui.set_next_item_width(-1)
        _,self.ai_input=imgui.input_text_multiline('##eye-input',self.ai_input,V(-1,150))
        self.remember_rect('eye-input')
        stt=self.ai_settings.stt_connection()
        ready=stt['provider']!='Disabled' and (stt['provider']!='OpenAI' or bool(stt['key']))
        imgui.begin_disabled(not ready)
        if self.button('结束录音 Stop' if self.speech_busy else '麦克风 Mic','microphone'):self.toggle_microphone()
        imgui.end_disabled();imgui.same_line()
        if self.button('导入图片 Image','ai-image'):self.attempt(self.browse_ai_image)
        imgui.begin_disabled(self.ai_busy)
        if self.button('生成 / 应用 Generate / Apply','apply'):self.attempt(self.generate_apply,'AI 正在处理…')
        imgui.end_disabled()
        if not ready:imgui.text_disabled('STT 待接 / Not configured')
        if self.ai_image:
            imgui.text_wrapped(self.ai_image.path.name)
            if self.button('移除图片 Clear image'):self.ai_image=None
        if self.speech_busy:imgui.text('录音 / 转文字 Recording / Transcribing…')
        if self.ai_busy:imgui.text('处理中 Working…')
    def save_ai_settings(self):
        if self.ai_key_input.strip():
            self.ai_settings.set_key(self.ai_key_input.strip());self.ai_key_input=''
        if self.stt_key_input.strip():
            self.ai_settings.set_key(self.stt_key_input.strip(),'STT');self.stt_key_input=''
        self.ai_settings.save()
        self.ai_generation+=1;self.ai_busy=False
        self.ai_connected=False;self.ai_limited=True
    def build_settings_ui(self):
        imgui.text('设置 Settings / AI')
        data=self.ai_settings.data;name=data['provider']
        labels=['OpenAI / ChatGPT API','DeepSeek','本地 Local AI (Ollama)','自定义 Custom']
        changed,index=imgui.combo('服务 Provider',PROVIDERS.index(name),labels)
        if changed:
            data['provider']=PROVIDERS[index];self.ai_key_input=''
            self.ai_connected=False;self.ai_limited=True;self.ai_generation+=1;self.ai_busy=False
            name=data['provider']
        if name!='Rule Fallback':
            p=data['profiles'][name]
            changed,p['model']=imgui.input_text('模型 Model',p['model'])
            changed_endpoint,p['endpoint']=imgui.input_text('地址 Endpoint',p['endpoint'])
            if changed or changed_endpoint:
                self.ai_connected=False;self.ai_limited=True;self.ai_generation+=1;self.ai_busy=False
            _,self.ai_key_input=imgui.input_text('密钥 API Key',self.ai_key_input,flags=imgui.InputTextFlags_.password)
            imgui.text_disabled('留空保留已存密钥 / Blank keeps stored key')
        _,data['auto_connect']=imgui.checkbox('启动尝试连接 Auto connect',data['auto_connect'])
        imgui.separator();imgui.text('语音转文字 STT')
        stts=('Disabled','OpenAI','Custom')
        _,si=imgui.combo('STT 服务',stts.index(data['stt_provider']),['待接 Disabled','OpenAI','Custom compatible'])
        data['stt_provider']=stts[si]
        if si:
            sp=data['profiles']['STT']
            _,sp['model']=imgui.input_text('STT Model',sp['model'])
            if si==2:_,sp['endpoint']=imgui.input_text('STT Endpoint',sp['endpoint'])
            _,self.stt_key_input=imgui.input_text('STT Key',self.stt_key_input,flags=imgui.InputTextFlags_.password)
            imgui.text_wrapped('OpenAI 留空复用本机 OpenAI Key。未完成真实语音验证。')
        imgui.begin_disabled(self.ai_busy)
        if self.button('保存设置 Save','ai-save'):self.attempt(self.save_ai_settings,'AI 设置已在本机保存')
        if self.button('测试连接 Test Connection','ai-test'):self.test_ai_connection()
        imgui.end_disabled()
        if self.ai_detail:imgui.text_wrapped(self.ai_detail)
        if imgui.collapsing_header('高级 Advanced'):
            _,data['timeout']=imgui.slider_float('超时 Timeout',data['timeout'],1.,120.,'%.0f s')
            if self.button('清除本服务密钥 Clear key'):
                self.ai_settings.set_key('');self.ai_settings.save();self.ai_connected=False;self.ai_key_input=''
            imgui.text_wrapped('文字、当前眼睛参数与 AI 区导入的图片会发到所选 API；Reference Overlay 不自动上传。录音仅发送到配置的 STT 服务。')
            imgui.text_wrapped('ChatGPT 订阅登录与 API Key 分开配置。Custom 使用 OpenAI-compatible Chat Completions。')
    def build_eye_axes(self):
        if imgui.collapsing_header('左右眼与位置 Eyes / Transform'):
            shape=self.cfg['poses'][self.selected]['shape']
            # Optional keys are read through defaults; inspecting the panel does not mutate data.
            for parameter in EYE_PARAMETERS:self.edit_slider('poses.'+self.selected+'.shape',*parameter)
