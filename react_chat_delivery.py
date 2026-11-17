"""Durable delivery worker for the experimental React chat.

The React queue has its own encrypted account/origin namespace until a
single-writer migration from the native chat is implemented.
"""
import copy,threading
from chat_delivery import DeliveryQueue

class ReactDelivery:
    def __init__(self,folder,origin,user_id,client_provider):
        if not user_id:raise ValueError('حساب کاربری مشخص نیست.')
        self.queue=DeliveryQueue(folder,origin+'#react-chat-v1',user_id);self.origin=origin;self.user_id=user_id
        self.client_provider=client_provider;self.lock=threading.Lock()
        if not self.queue.path.exists() and not self.queue.value['drafts'] and not self.queue.value['outbox']:
            legacy=DeliveryQueue(folder,origin+'#saved-chat-v2',user_id)
            if legacy.value.get('drafts'):
                self.queue.value['drafts']=copy.deepcopy(legacy.value['drafts'])
                try:self.queue.persist()
                except Exception:pass
    def enqueue(self,payload):
        if not isinstance(payload,dict) or not payload.get('company') or not payload.get('room'):raise ValueError('مقصد پیام مشخص نیست.')
        with self.queue.lock:
            key=payload.get('request_id')
            prior=next((x for x in self.queue.value['outbox'] if x['payload'].get('request_id')==key),None) if key else None
            if prior:
                if prior['payload']!=payload:raise ValueError('شناسه ارسال برای پیام دیگری استفاده شده است.')
                return key
            previous=copy.deepcopy(self.queue.value)
            try:return self.queue.enqueue(payload)
            except Exception:self.queue.value=previous;raise
    def enqueue_and_clear_draft(self,payload):
        """Commit queued payload and removal of its room draft in one save."""
        import json,uuid
        if not isinstance(payload,dict) or not payload.get('company') or not payload.get('room'):raise ValueError('مقصد پیام مشخص نیست.')
        payload=copy.deepcopy(payload);payload.setdefault('request_id',uuid.uuid4().hex)
        with self.queue.lock:
            prior=next((x for x in self.queue.value['outbox'] if x['payload'].get('request_id')==payload['request_id']),None)
            if prior:
                if prior['payload']!=payload:raise ValueError('شناسه ارسال برای پیام دیگری استفاده شده است.')
                return payload['request_id']
            if len(self.queue.value['outbox'])>=30:raise ValueError('صف ارسال پر است؛ ابتدا پیام‌های قبلی را بررسی کنید.')
            if len(json.dumps(self.queue.value,ensure_ascii=False).encode())+len(json.dumps(payload,ensure_ascii=False).encode())>64*1024*1024:raise ValueError('حجم صف ارسال زیاد است.')
            previous=copy.deepcopy(self.queue.value)
            try:
                self.queue.value['outbox'].append(dict(payload=payload,status='queued',error=''))
                self.queue.value['drafts'].pop(self.queue.room_key(payload['company'],payload['room']),None)
                self.queue.persist()
            except Exception:self.queue.value=previous;raise
            return payload['request_id']
    def acknowledge(self,key):
        with self.queue.lock:
            previous=copy.deepcopy(self.queue.value)
            try:self.queue.acknowledge(key)
            except Exception:self.queue.value=previous;raise
    def draft(self,company,room):
        if not company or not room:raise ValueError('مقصد پیش‌نویس مشخص نیست.')
        return self.queue.draft(company,room)
    def save_draft(self,company,room,text,files,reply_to):
        if not isinstance(company,str) or not company or not isinstance(room,str) or not room or not isinstance(text,str) or len(text)>8000 or not isinstance(files,list) or len(files)>5 or (reply_to is not None and not isinstance(reply_to,str)):raise ValueError('پیش‌نویس معتبر نیست.')
        if any(not isinstance(f,dict) or set(f)!={'name','data','size'} or not isinstance(f['name'],str) or not 0<len(f['name'])<=180 or not isinstance(f['data'],str) or type(f['size']) is not int or not 0<f['size']<=12*1024*1024 for f in files) or sum(f['size'] for f in files)>12*1024*1024:raise ValueError('پیوست پیش‌نویس معتبر نیست.')
        with self.queue.lock:
            previous=copy.deepcopy(self.queue.value)
            try:self.queue.save_draft(company,room,text,files,reply_to)
            except Exception:self.queue.value=previous;raise
    def flush_one(self):
        if not self.lock.acquire(False):return {'status':'busy'}
        try:
            item=self.queue.pending()
            if not item:return {'status':'empty'}
            client=self.client_provider()
            if not client or not client.token:return {'status':'offline'}
            origin=('network://'+client.fingerprint) if getattr(client,'fingerprint',None) else client.url
            if origin!=self.origin or (client.user or {}).get('id')!=self.user_id:return {'status':'offline'}
            from org_client import Client
            worker=Client(client.url,client.session.verify if isinstance(client.session.verify,str) else None,getattr(client,'fingerprint',None));worker.token=client.token;worker.user=client.user
            payload=copy.deepcopy(item['payload']);key=payload['request_id']
            try:
                result=worker.request('chat/messages',payload)
                self.acknowledge(key)
                return {'status':'sent','id':key,'result':result}
            except Exception as exc:
                permanent=getattr(exc,'status',503) not in (429,500,502,503,504)
                self.queue.failed(key,exc,permanent=permanent)
                return {'status':'needs_review' if permanent else 'offline','id':key,'error':str(exc)}
            finally:worker.session.close()
        finally:self.lock.release()
