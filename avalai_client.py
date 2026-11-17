"""AvalAI connection and per-user protected credentials for the assistant."""
import hashlib,re
from urllib.parse import urlsplit
from storage import app_dir
from lmstudio_client import LMClient,LMError

DEFAULT_AVALAI_URL='https://api.avalai.ir/v1'

def avalai_url(value):
    try:
        p=urlsplit(str(value).strip())
        if p.scheme!='https' or p.hostname!='api.avalai.ir' or p.port not in (None,443) or p.username or p.password or p.query or p.fragment or p.path.rstrip('/') not in ('/v1','/user/v1'):raise ValueError()
        return 'https://api.avalai.ir'+p.path.rstrip('/')
    except (ValueError,TypeError):raise LMError('نشانی امن سرویس اول‌ای‌آی معتبر نیست.') from None

def credential_path(user_id):
    if not user_id or user_id=='standalone':raise LMError('برای تنظیم کلید شخصی ابتدا وارد حساب کارنامه شوید.')
    digest=hashlib.sha256(str(user_id).encode('utf-8')).hexdigest()
    return app_dir()/'ai-credentials'/('avalai-'+digest+'.dpapi')

def save_credentials(user_id,api_key,model,url=DEFAULT_AVALAI_URL):
    from local_vault import save
    key=str(api_key).strip();model=str(model).strip()
    if not key or len(key)>4096 or not model or len(model)>300 or re.search(r'[\r\n]',key+model):raise LMError('کلید و شناسه مدل معتبر را وارد کنید.')
    save(credential_path(user_id),dict(key=key,model=model,url=avalai_url(url)))

def load_credentials(user_id):
    from local_vault import load
    return load(credential_path(user_id),{}) or {}

class AvalAIClient(LMClient):
    def __init__(self,url=DEFAULT_AVALAI_URL,token='',timeout=120):
        super().__init__(timeout=timeout);self.url=avalai_url(url);self.token=str(token).strip()
        if not self.token:raise LMError('کلید API شخصی را وارد کنید.')
        self.session.headers['Authorization']='Bearer '+self.token
    def request(self,path,**kwargs):
        try:return super().request(path,**kwargs)
        except LMError as exc:raise LMError(str(exc).replace('LM Studio','اول‌ای‌آی')) from None
    def models(self):
        with self.request('/models') as response:
            try:
                if len(response.content)>1024*1024:raise ValueError()
                rows=response.json()['data']
                if not isinstance(rows,list):raise ValueError()
                return list(dict.fromkeys(x['id'] for x in rows[:5000] if isinstance(x,dict) and isinstance(x.get('id'),str) and len(x['id'])<=300))
            except (ValueError,KeyError,TypeError):raise LMError('فهرست مدل‌های اول‌ای‌آی قابل خواندن نیست.') from None
