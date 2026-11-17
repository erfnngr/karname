"""Per-account Windows-encrypted drafts and idempotent outgoing messages."""
import copy,hashlib,uuid,threading,functools,json
from pathlib import Path
from local_vault import load,save

def synchronized(fn):
    @functools.wraps(fn)
    def run(self,*args,**kwargs):
        with self.lock:return fn(self,*args,**kwargs)
    return run

class DeliveryQueue:
    def __init__(self,folder,origin,user_id):
        self.lock=threading.RLock();identity=hashlib.sha256((origin.rstrip('/')+'\n'+user_id).encode()).hexdigest();self.path=Path(folder)/('chat-'+identity+'.dpapi');self.value=load(self.path,dict(drafts={},outbox=[]))
    @synchronized
    def persist(self):save(self.path,self.value)
    def room_key(self,company,room):return company+':'+room
    @synchronized
    def draft(self,company,room):return copy.deepcopy(self.value['drafts'].get(self.room_key(company,room),{}))
    @synchronized
    def save_draft(self,company,room,text,files=None,reply_to=None):
        key=self.room_key(company,room)
        if text or files:self.value['drafts'][key]=dict(text=text,files=files or [],reply_to=reply_to)
        else:self.value['drafts'].pop(key,None)
        self.persist()
    @synchronized
    def enqueue(self,payload):
        if len(self.value['outbox'])>=30:raise ValueError('صف ارسال پر است؛ ابتدا پیام‌های قبلی را بررسی کنید.')
        if len(json.dumps(self.value,ensure_ascii=False).encode())+len(json.dumps(payload,ensure_ascii=False).encode())>64*1024*1024:raise ValueError('حجم صف ارسال زیاد است؛ ابتدا پیام‌های قبلی را ارسال یا لغو کنید.')
        payload=copy.deepcopy(payload);payload.setdefault('request_id',uuid.uuid4().hex);self.value['outbox'].append(dict(payload=payload,status='queued',error=''));self.persist();return payload['request_id']
    @synchronized
    def pending(self):return copy.deepcopy(next((x for x in self.value['outbox'] if x['status']=='queued'),None))
    @synchronized
    def acknowledge(self,id):self.value['outbox']=[x for x in self.value['outbox'] if x['payload']['request_id']!=id];self.persist()
    @synchronized
    def failed(self,id,error,permanent=False):
        for x in self.value['outbox']:
            if x['payload']['request_id']==id:x['error']=str(error)[:500];x['status']='needs_review' if permanent else 'queued'
        self.persist()
    @synchronized
    def retry(self,id):
        for x in self.value['outbox']:
            if x['payload']['request_id']==id:x['status']='queued';x['error']=''
        self.persist()
