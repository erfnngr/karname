"""A bounded, cancelable connection to a user's local LM Studio API."""
import ipaddress,json,threading
from urllib.parse import urlsplit
import requests

DEFAULT_URL='http://127.0.0.1:1234/v1'

class LMError(ValueError):pass
class Cancelled(Exception):pass

def base_url(value):
    try:
        p=urlsplit(str(value).strip());port=p.port
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.query or p.fragment or p.path.rstrip('/') not in ('','/v1'):raise ValueError()
        host=p.hostname.lower()
        if host!='localhost':
            ip=ipaddress.ip_address(host)
            networks=['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','fc00::/7']
            if not (ip.is_loopback or any(ip in ipaddress.ip_network(n) for n in networks if ip.version==ipaddress.ip_network(n).version)):raise ValueError()
        if port is not None and not 1<=port<=65535:raise ValueError()
        return p.scheme+'://'+p.netloc+'/v1'
    except (ValueError,TypeError):raise LMError('نشانی LM Studio را با localhost یا IP خصوصی شبکه وارد کنید؛ مانند http://127.0.0.1:1234/v1') from None

def content_text(value):
    if isinstance(value,str):return value
    if isinstance(value,list):return ''.join(x.get('text','') for x in value if isinstance(x,dict) and isinstance(x.get('text'),str))
    return ''

def messages_for(history,system,max_chars=10000):
    result=[];size=0
    for item in reversed(history[-24:]):
        if item.get('role') not in ('user','assistant'):continue
        text=str(item.get('content',''))[:6000]
        if not text:continue
        if result and size+len(text)>max_chars:break
        result.append(dict(role=item['role'],content=text));size+=len(text)
    result=list(reversed(result))
    while result and result[0]['role']!='user':result.pop(0)
    if len(system)>32000:raise LMError('اطلاعات درخواستی برای ارسال یکجا بیش از حد طولانی است؛ درخواست را محدودتر کنید.')
    return [dict(role='system',content=system)]+result

class LMClient:
    def __init__(self,url=DEFAULT_URL,token='',timeout=120):
        self.url=base_url(url);self.token=token.strip();self.timeout=timeout;self.cancelled=threading.Event();self.response=None;self.session=requests.Session();self.session.trust_env=False;self.company_mode=False
        if self.token:self.session.headers['Authorization']='Bearer '+self.token
    @classmethod
    def company(cls,client,timeout=120):
        if not client or not client.token:raise LMError('برای دستیار شبکه ابتدا با حساب خود وارد کارنامه شوید.')
        value=cls(timeout=timeout);value.url=client.url+'/api/ai';value.company_mode=True;value.session.verify=client.session.verify;value.session.headers.update({'Authorization':'Bearer '+client.token,'X-Karname':'1'})
        if client.fingerprint:
            from org_client import PinnedAdapter
            value.session.mount(client.url+'/',PinnedAdapter(client.fingerprint))
        return value
    def cancel(self):
        self.cancelled.set()
        # Closing a streaming response may wait for a read; never block the UI.
        response=self.response
        if response:threading.Thread(target=response.close,daemon=True).start()
    def close(self):self.session.close()
    def request(self,path,**kwargs):
        if self.cancelled.is_set():raise Cancelled()
        try:
            response=self.session.request('POST' if 'json' in kwargs else 'GET',self.url+path,timeout=(4,self.timeout),allow_redirects=False,**kwargs)
            if response.status_code!=200:
                response.close()
                if response.status_code in (401,403):raise LMError('حساب یا دسترسی دستیار شبکه تأیید نشد؛ دوباره وارد کارنامه شوید یا از مدیر بخواهید مجوز دستیار را بررسی کند.' if self.company_mode else 'LM Studio اجازه اتصال نداد؛ کلید دسترسی را در تنظیمات اتصال بررسی کنید.')
                if response.status_code==429:raise LMError('دستیار در حال پاسخ به همکاران است؛ کمی بعد دوباره تلاش کنید.')
                if response.status_code==400:raise LMError('LM Studio نتوانست درخواست یا مدل را اجرا کند؛ مدل انتخاب‌شده را در خود LM Studio بارگذاری و دوباره تلاش کنید.')
                if 300<=response.status_code<400:raise LMError('نشانی LM Studio به آدرس دیگری هدایت شد؛ نشانی مستقیم سرویس را وارد کنید.')
                raise LMError('LM Studio درخواست را نپذیرفت (کد '+str(response.status_code)+'). مدل بارگذاری‌شده و تنظیمات آن را بررسی کنید.')
            return response
        except requests.Timeout:raise LMError('زمان انتظار پاسخ LM Studio تمام شد؛ مدل یا اندازه درخواست را بررسی و دوباره تلاش کنید.') from None
        except requests.RequestException:
            if self.cancelled.is_set():raise Cancelled() from None
            raise LMError('ارتباط با LM Studio برقرار نشد؛ مدل را بارگذاری و Server را در بخش Developer روشن کنید.') from None
    def models(self):
        with self.request('/models') as response:
            try:
                if len(response.content)>1024*1024:raise ValueError()
                rows=response.json()['data'];assert isinstance(rows,list)
                ids=list(dict.fromkeys(x['id'] for x in rows[:200] if isinstance(x,dict) and isinstance(x.get('id'),str) and len(x['id'])<=300 and not any(t in x['id'].lower() for t in ('embedding','embed-text','embed_text'))))
            except (ValueError,KeyError,TypeError,AssertionError):raise LMError('فهرست مدل‌های LM Studio قابل خواندن نیست.') from None
        # Prefer already-loaded chat instances. /v1/models can also include
        # downloaded models which would otherwise be loaded automatically.
        try:
            if self.company_mode:return ids
            with self.session.get(self.url[:-3]+'/api/v1/models',timeout=(3,5),allow_redirects=False) as response:
                if response.status_code==200 and len(response.content)<1024*1024:
                    rows=response.json().get('models',[]);loaded=[];available=[]
                    for row in rows[:200]:
                        if not isinstance(row,dict) or row.get('type')!='llm':continue
                        key=row.get('key')
                        if isinstance(key,str) and len(key)<=300:available.append(key)
                        for instance in row.get('loaded_instances',[])[:20]:
                            if isinstance(instance,dict) and isinstance(instance.get('id'),str) and len(instance['id'])<=300:loaded.append(instance['id'])
                    ids=list(dict.fromkeys(loaded+available+ids))
        except (requests.RequestException,ValueError,TypeError,AttributeError):pass
        return ids
    def chat(self,model,messages,on_chunk):
        if not isinstance(model,str) or not model.strip() or len(model)>300:raise LMError('یک مدل گفتگو انتخاب کنید.')
        output=''
        try:
            with self.request('/chat/completions',json=dict(model=model,messages=messages,temperature=.3,max_tokens=1536,stream=True),stream=True) as response:
                self.response=response
                if 'text/event-stream' not in response.headers.get('Content-Type',''):
                    if len(response.content)>1024*1024:raise LMError('پاسخ مدل بیش از حد بزرگ است.')
                    try:output=content_text(response.json()['choices'][0]['message'].get('content'))
                    except (ValueError,KeyError,IndexError,TypeError):raise LMError('قالب پاسخ مدل قابل خواندن نیست.') from None
                    if output:on_chunk(output)
                else:
                    for raw in response.iter_lines(chunk_size=1):
                        if self.cancelled.is_set():raise Cancelled()
                        if not raw or not raw.startswith(b'data:'):continue
                        raw=raw[5:].strip()
                        if raw==b'[DONE]':break
                        if len(raw)>1024*1024:raise LMError('پاسخ مدل بیش از حد بزرگ است.')
                        try:
                            value=json.loads(raw)
                            if value.get('error'):raise LMError('LM Studio هنگام تولید پاسخ خطا داد؛ مدل و ظرفیت متن را بررسی کنید.')
                            piece=content_text(value.get('choices',[{}])[0].get('delta',{}).get('content'))
                        except (ValueError,IndexError,KeyError,TypeError):raise LMError('جریان پاسخ مدل کامل یا معتبر نیست؛ دوباره تلاش کنید.') from None
                        if piece:
                            output+=piece
                            if len(output)>60000:raise LMError('پاسخ مدل بیش از حد طولانی شد؛ درخواست کوتاه‌تری بنویسید.')
                            on_chunk(piece)
            if self.cancelled.is_set():raise Cancelled()
            if not output.strip():raise LMError('مدل پاسخ نهایی متنی نداد؛ مدل گفتگو و تنظیم تفکر آن را در LM Studio بررسی کنید.')
            return output
        except requests.RequestException:
            if self.cancelled.is_set():raise Cancelled() from None
            raise LMError('دریافت پاسخ قطع شد؛ پاسخ ناقص ثبت شد. می‌توانید دوباره تلاش کنید.') from None
        finally:self.response=None
