"""A session stays in memory. Offline snapshots are scoped to a signed-in user."""
import base64,hashlib,json,ssl,socket
from pathlib import Path
from urllib.parse import urlsplit
import requests
from org_store import DomainError

class PinnedAdapter(requests.adapters.HTTPAdapter):
    """A known certificate identity remains valid when the LAN address moves."""
    def __init__(self,fingerprint,**kwargs):
        if not __import__('re').fullmatch('[0-9A-Fa-f]{64}',str(fingerprint)):raise ValueError('اثر انگشت گواهی معتبر نیست.')
        self.fingerprint=fingerprint;super().__init__(**kwargs)
    def init_poolmanager(self,*args,**kwargs):
        kwargs['assert_fingerprint']=self.fingerprint
        return super().init_poolmanager(*args,**kwargs)

def validate_url(url):
    p=urlsplit(url)
    if p.scheme not in ('https','http') or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('','/'):raise ValueError('نشانی مرکز را به صورت https://server:8843 وارد کنید.')
    if p.scheme=='http' and p.hostname not in ('localhost','127.0.0.1','::1'):raise ValueError('HTTP فقط روی همین کامپیوتر مجاز است؛ برای شبکه HTTPS انتخاب کنید.')
    return url.rstrip('/')
def inspect_certificate(url):
    p=urlsplit(validate_url(url));context=ssl._create_unverified_context()
    # No credentials are sent. Trust is only persisted after an explicit visual
    # comparison with the fingerprint shown by the user's server control window.
    with socket.create_connection((p.hostname,p.port or 443),timeout=8) as sock:
        with context.wrap_socket(sock,server_hostname=p.hostname) as conn:der=conn.getpeercert(binary_form=True)
    return ssl.DER_cert_to_PEM_cert(der),hashlib.sha256(der).hexdigest().upper()

class Client:
    def __init__(self,url,certificate=None,fingerprint=None):
        self.url=validate_url(url);self.session=requests.Session();self.session.trust_env=False;self.session.verify=certificate or True;self.token=None;self.user=None;self.fingerprint=fingerprint;self.timeout=(5,40)
        if fingerprint:
            if not certificate or not self.url.startswith('https://'):raise ValueError('اتصال خودکار به گواهی معتبر و HTTPS نیاز دارد.')
            self.session.mount(self.url+'/',PinnedAdapter(fingerprint))
    def request(self,path,payload=None,**query):
        headers={'X-Karname':'1'}
        if self.token:headers['Authorization']='Bearer '+self.token
        try:
            r=self.session.request('POST' if payload is not None else 'GET',self.url+'/api/'+path,json=payload,params={k:v for k,v in query.items() if v not in (None,'')},headers=headers,timeout=self.timeout,allow_redirects=False)
            data=r.json()
            if not r.ok:
                if r.status_code==404 and data.get('error')=='مسیر پیدا نشد.' and (path=='inventory' or path.startswith('inventory/') or path=='finance' or path.startswith('finance/')):
                    raise DomainError('نسخه مرکز شرکت از برنامه قدیمی‌تر است. نسخه جدید را روی رایانه میزبان نصب و مرکز شرکت را دوباره راه‌اندازی کنید.',404)
                raise DomainError(data.get('error','خطای مرکز اطلاعات'),r.status_code)
            return data
        except requests.exceptions.SSLError as exc:raise DomainError('گواهی اتصال تأیید نشد. گواهی معتبر یا گواهی جفت‌شده با میزبان را انتخاب کنید.',503) from exc
        except (requests.RequestException,ValueError) as exc:raise DomainError('اتصال مرکز اطلاعات برقرار نشد؛ وضعیت میزبان و شبکه را بررسی کنید.',503) from exc
    def login(self,username,password):
        value=self.request('login',{'username':username,'password':password});self.token=value['token'];self.user=value['user'];return self.user
    def records(self,company=None,kind=None):
        page=1;result=[]
        while True:
            value=self.request('records',company=company,kind=kind,limit=500,page=page);result.extend(value['items'])
            if len(result)>=value['total']:return result
            page+=1
    def logout(self):
        if self.token:
            try:self.request('logout',{})
            finally:self.token=None;self.user=None;self.session.cookies.clear()
