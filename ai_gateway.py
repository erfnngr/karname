"""Authenticated company relay to the host's existing local model server."""
import json,time,threading
import requests
from org_store import DomainError
from assistant_model import GEMMA_MODEL

def dispatch(handler,actor,path,method,payload):
    from permission_policy import any_allowed
    server=handler.server
    server.store.require(any_allowed(actor,'assistant','view') and any_allowed(actor,'assistant','use'))
    if path not in ('/api/ai/models','/api/ai/chat/completions'):raise DomainError('مسیر دستیار پیدا نشد.',404)
    if not server.ai_slots.acquire(False):raise DomainError('دستیار در حال پاسخ به همکاران است؛ کمی بعد دوباره تلاش کنید.',429)
    try:
        backend=getattr(server,'ai_backend','http://127.0.0.1:1234/v1')
        from urllib.parse import urlsplit
        p=urlsplit(backend)
        if p.scheme!='http' or p.hostname not in ('127.0.0.1','localhost','::1') or p.path.rstrip('/')!='/v1' or p.username or p.password or p.query or p.fragment:raise DomainError('نشانی مدل میزبان باید سرویس محلی همان کامپیوتر باشد.',503)
        secret=getattr(server,'ai_token','')
        if path.endswith('/models'):
            if method!='GET':raise DomainError('روش درخواست معتبر نیست.',405)
            from lmstudio_client import LMClient
            client=LMClient(backend,secret,12)
            try:return handler.reply(dict(data=[dict(id=k,object='model') for k in client.models() if k==GEMMA_MODEL]))
            finally:client.close()
        if method!='POST' or set(payload)-{'model','messages','temperature','max_tokens','stream'}:raise DomainError('درخواست دستیار معتبر نیست.')
        messages=payload.get('messages');model=payload.get('model');limit=payload.get('max_tokens',1536);temperature=payload.get('temperature',.3)
        if model!=GEMMA_MODEL:raise DomainError('فقط مدل Gemma برای دستیار کارنامه فعال است.',400)
        if type(limit) is not int or not 1<=limit<=4096 or type(temperature) not in (int,float) or not 0<=temperature<=2:raise DomainError('پارامترهای گفتگو معتبر نیستند.')
        if not isinstance(messages,list) or not 1<=len(messages)<=25 or len(json.dumps(messages,ensure_ascii=False))>60000:raise DomainError('حجم متن گفتگو بیش از حد مجاز است.')
        for msg in messages:
            if not isinstance(msg,dict) or set(msg)!={'role','content'} or msg['role'] not in ('system','user','assistant') or not isinstance(msg['content'],str) or len(msg['content'])>(32000 if msg['role']=='system' else 16000):raise DomainError('قالب پیام گفتگو معتبر نیست.')
        session=requests.Session();session.trust_env=False
        if secret:session.headers['Authorization']='Bearer '+secret
        response=None
        try:
            response=session.post(backend.rstrip('/')+'/chat/completions',json=dict(model=model,messages=messages,temperature=temperature,max_tokens=limit,stream=bool(payload.get('stream',True))),stream=True,allow_redirects=False,timeout=(4,120))
            if response.status_code!=200:raise DomainError('سرویس مدل میزبان پاسخ نداد؛ مدیر باید وضعیت LM Studio و مدل را بررسی کند.',503)
            kind=response.headers.get('Content-Type','')
            if 'text/event-stream' not in kind:
                raw=bytearray()
                for part in response.iter_content(8192):
                    raw.extend(part)
                    if len(raw)>1024*1024:raise DomainError('پاسخ مدل بیش از حد بزرگ است.',502)
                return handler.reply(json.loads(raw))
            handler.send_response(200);handler.send_header('Content-Type','text/event-stream; charset=utf-8');handler.send_header('Cache-Control','no-store');handler.send_header('X-Content-Type-Options','nosniff');handler.send_header('Connection','close');handler.end_headers();handler.close_connection=True
            count=0;start=time.monotonic()
            try:
                for line in response.iter_lines(chunk_size=1):
                    if server.closing.is_set() or time.monotonic()-start>180:break
                    count+=len(line)
                    if len(line)>65536 or count>1024*1024:break
                    if line.startswith(b'data:'):
                        handler.wfile.write(line+b'\n\n');handler.wfile.flush()
                else:return
                handler.wfile.write(b'data: {"error":"model stream interrupted"}\n\n');handler.wfile.flush()
            except (BrokenPipeError,ConnectionResetError,requests.RequestException,OSError):pass
        except requests.RequestException as exc:raise DomainError('مدل روی میزبان در دسترس نیست؛ LM Studio و Server آن باید روشن باشند.',503) from exc
        finally:
            if response is not None:response.close()
            session.close()
    finally:server.ai_slots.release()
