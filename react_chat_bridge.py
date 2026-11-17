"""Narrow, asynchronous bridge for a future embedded chat view.

The server client remains on the native side; session tokens are never sent
to JavaScript. This module is not installed into a web view until navigation
and lifecycle restrictions are in place.
"""
import json,threading,hashlib
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QObject, Signal, Slot

READS = {
    'companies': ('companies', ()),
    'rooms': ('chat/rooms', ()),
    'updates': ('chat/updates', ('after',)),
    'messages': ('chat/messages', ('company', 'room', 'before', 'limit', 'q', 'thread', 'saved', 'pinned')),
    'people': ('workspace/direct', ('company',)),
    'group_people': ('workspace/group-people', ('company',)),
    'scheduled': ('chat/scheduled', ('company', 'room')),
    'file': ('chat/file', ('id',)),
}
WRITES = {
    'send': ('chat/messages', ('company', 'room', 'text', 'attachments', 'reply_to', 'mentions', 'request_id', 'kind', 'payload')),
    'direct': ('workspace/direct', ('company', 'person')),
    'group': ('workspace/group', ('company', 'title', 'members', 'company_name', 'avatar', 'request_id')),
    'hide_room': ('workspace/chat-hide', ('company', 'room')),
    'state': ('chat/state', ('company', 'room', 'muted', 'seq')),
    'schedule': ('chat/scheduled', ('company', 'room', 'text', 'attachments', 'due_at', 'request_id')),
    'schedule_cancel': ('chat/scheduled/cancel', ('id', 'expected_due_at')),
    'schedule_reschedule': ('chat/scheduled/reschedule', ('id', 'due_at', 'expected_due_at')),
    'saved_chat': ('workspace/saved-chat', ()),
    'message_action': ('chat/action', ('id', 'action', 'option')),
    'clear_room': ('workspace/chat-clear', ('company', 'room', 'through')),
    'restore_group': ('workspace/chat-restore-group', ('company', 'room')),
}

def _filter_rooms(rooms, user_id):
    from storage import normalize
    from chat_ui import room_labels
    def visible_room(r):
        name = normalize(r.get('title', '')).replace('\u200c', ' ').replace(' ', '')
        saved = r.get('saved') or str(r.get('room', '')).startswith('saved:') or 'پیامهایذخیرهشده' in name
        return not saved or (r.get('company') == '__shared_chat__' and r.get('room') == 'saved:' + str(user_id or ''))
    kept = [dict(r) for r in (rooms or []) if visible_room(r)]
    for r, label in zip(kept, room_labels(kept)):
        r['label'] = label
    return kept

def request_for(name, params):
    if not isinstance(params, dict): raise ValueError('پارامترهای درخواست معتبر نیستند.')
    if name in READS: path, fields = READS[name]; post = False
    elif name in WRITES: path, fields = WRITES[name]; post = True
    else: raise ValueError('این عملیات از طریق صفحه چت مجاز نیست.')
    if set(params) - set(fields): raise ValueError('پارامتر ناشناخته است.')
    if name=='message_action' and params.get('action') not in ('like','like_set','vote','seen','save','pin','delete'):
        raise ValueError('این عملیات پیام از طریق صفحه وب مجاز نیست.')
    if len(json.dumps(params, ensure_ascii=False)) > 18 * 1024 * 1024: raise ValueError('درخواست بیش از حد بزرگ است.')
    return path, post, params

class ReactChatBridge(QObject):
    completed = Signal(str, str)
    target_opened = Signal(str)
    native_message_ready = Signal(str, object, object, str)
    def __init__(self, client_provider, parent=None, native_reminder=None, native_task=None):
        super().__init__(parent); self.client_provider = client_provider; self.native_reminder=native_reminder;self.native_task=native_task;self.native_message_ready.connect(self._open_native_reminder);self.pool = ThreadPoolExecutor(max_workers=3); self.closed = False;self.delivery_lock=threading.RLock();self.delivery=None;self.delivery_identity=None;self.draft_versions={};self.enqueued={};self.last_target=None
    def open_target(self, company, room, thread=None, message_id=None):
        self.last_target = {'company': company, 'room': room, 'thread': thread, 'message_id': message_id}
        if not self.closed:
            self.target_opened.emit(json.dumps(self.last_target, ensure_ascii=False))
    @Slot(str, object, object, str)
    def _open_native_reminder(self,request_id,message,client,token):
        if self.closed or self.client_provider() is not client or client.token!=token:return
        try:
            action=message.pop('_native_action', 'native_reminder')
            handler=self.native_reminder if action=='native_reminder' else self.native_task
            if not handler:raise ValueError('این امکان در این نما در دسترس نیست.')
            handler(message)
            result={'ok':True,'value':{'opened':True}}
        except Exception as exc:result={'ok':False,'error':str(exc)}
        self.completed.emit(request_id,json.dumps(result,ensure_ascii=False))
    def delivery_for(self,client):
        from storage import app_dir
        from react_chat_delivery import ReactDelivery
        uid=(client.user or {}).get('id','');origin=('network://'+client.fingerprint) if getattr(client,'fingerprint',None) else client.url
        if not uid:raise ValueError('حساب کاربری مشخص نیست.')
        identity=(origin,uid)
        with self.delivery_lock:
            if identity!=self.delivery_identity:
                self.delivery=ReactDelivery(app_dir()/'secure-drafts',origin,uid,self.client_provider);self.delivery_identity=identity
            return self.delivery
    @Slot(str, str, str)
    def request(self, request_id, name, raw):
        try:
            if self.closed or len(request_id) > 80 or len(raw) > 18 * 1024 * 1024: raise ValueError('درخواست معتبر نیست.')
            params=json.loads(raw);client = self.client_provider()
            if not client or not client.token: raise ValueError('ابتدا به مرکز شرکت وارد شوید.')
            if name=='identity':
                if params!={}:raise ValueError('پارامتر حساب معتبر نیست.')
                from storage import today_j, jformat
                user=client.user or {}
                self.completed.emit(request_id,json.dumps({'ok':True,'value':{'id':user.get('id',''),'fullname':user.get('fullname',''),'today_jalali':jformat(today_j())}},ensure_ascii=False));return
            if name=='last_target':
                if params!={}:raise ValueError('پارامتر هدف معتبر نیست.')
                self.completed.emit(request_id,json.dumps({'ok':True,'value':self.last_target},ensure_ascii=False));return
            if name=='parse_jalali':
                if not isinstance(params,dict) or not {'date','time'}<=set(params) or set(params)-{'date','time','future'}:raise ValueError('تاریخ یا ساعت معتبر نیست.')
                if not isinstance(params.get('date'),str) or not isinstance(params.get('time'),str):raise ValueError('تاریخ یا ساعت معتبر نیست.')
                from datetime import datetime,timezone,timedelta
                from storage import parse_j
                import re
                m=re.fullmatch(r'\s*([01]?\d|2[0-3]):([0-5]\d)\s*',params['time'])
                if not m:raise ValueError('ساعت را به صورت HH:MM وارد کنید.')
                day=parse_j(params['date']).togregorian();when=datetime(day.year,day.month,day.day,int(m.group(1)),int(m.group(2)),tzinfo=timezone(timedelta(hours=3,minutes=30)))
                if params.get('future') and when<=datetime.now(timezone.utc):raise ValueError('زمان انتخاب‌شده باید در آینده باشد.')
                self.completed.emit(request_id,json.dumps({'ok':True,'value':{'iso':when.isoformat()}},ensure_ascii=False));return
            if name=='choose_schedule':
                if not isinstance(params,dict) or params:raise ValueError('پارامترهای انتخاب زمان معتبر نیستند.')
                from chat_ui import ScheduleDialog
                from PySide6.QtWidgets import QDialog
                dialog=ScheduleDialog()
                selected=dialog.exec()==QDialog.Accepted
                self.completed.emit(request_id,json.dumps({'ok':True,'value':{'due_at':dialog.due_at if selected else None}},ensure_ascii=False));return
            if name in ('choose_poll','choose_meeting'):
                if not isinstance(params,dict) or params:raise ValueError('پارامترهای انتخاب معتبر نیستند.')
                from chat_ui import MessageDialog
                from PySide6.QtWidgets import QDialog
                dialog=MessageDialog('poll' if name=='choose_poll' else 'meeting')
                selected=dialog.exec()==QDialog.Accepted
                value={'title':dialog.title.text().strip(),'payload':dialog.payload} if selected else None
                self.completed.emit(request_id,json.dumps({'ok':True,'value':value},ensure_ascii=False));return
            native_op=name in ('native_reminder','native_task')
            if native_op:
                if not (self.native_reminder if name=='native_reminder' else self.native_task):raise ValueError('این امکان در این نما در دسترس نیست.')
                if not isinstance(params,dict) or set(params)!={'company','room','id'} or not all(isinstance(params[k],str) and 0<len(params[k])<=200 for k in params):raise ValueError('پیام معتبر نیست.')
            queue_op=name in ('queue_enqueue','queue_flush','queue_list','queue_retry','queue_cancel','draft_get','draft_save')
            if queue_op:
                if not isinstance(params,dict):raise ValueError('پارامتر صف معتبر نیست.')
                if name=='queue_enqueue':
                    if set(params)!={'payload','draft_version'} or not isinstance(params['payload'],dict) or type(params['draft_version']) is not int or not 0<=params['draft_version']<=9007199254740991:raise ValueError('پارامتر صف معتبر نیست.')
                    request_for('send',params['payload'])
                    if not all(isinstance(params['payload'].get(x),str) and params['payload'][x] for x in ('company','room')):raise ValueError('مقصد پیام مشخص نیست.')
                    if not isinstance(params['payload'].get('request_id'),str) or not 16<=len(params['payload']['request_id'])<=80:raise ValueError('شناسه ارسال معتبر نیست.')
                elif name in ('queue_retry','queue_cancel'):
                    if set(params)!={'id'} or not isinstance(params['id'],str) or not 16<=len(params['id'])<=80:raise ValueError('شناسه صف معتبر نیست.')
                elif name in ('draft_get','draft_save'):
                    fields={'company','room'} if name=='draft_get' else {'company','room','text','files','reply_to','version'}
                    if set(params)!=fields or not all(isinstance(params[x],str) and 0<len(params[x])<=200 for x in ('company','room')):raise ValueError('پارامتر پیش‌نویس معتبر نیست.')
                    if name=='draft_save' and (type(params['version']) is not int or not 0<=params['version']<=9007199254740991):raise ValueError('نسخه پیش‌نویس معتبر نیست.')
                elif params:raise ValueError('پارامتر صف معتبر نیست.')
                path=None;post=False
            elif not native_op:path, post, params = request_for(name, params)
            token=client.token
        except Exception as exc:
            self.completed.emit(request_id, json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False)); return
        def run():
            try:
                if self.closed or self.client_provider() is not client or client.token!=token: raise ValueError('نشست کاربر تغییر کرده است.')
                if native_op:
                    from org_client import Client
                    worker=Client(client.url,client.session.verify if isinstance(client.session.verify,str) else None,getattr(client,'fingerprint',None));worker.token=token;worker.user=client.user
                    try:
                        data=worker.request('chat/messages',company=params['company'],room=params['room'],thread=params['id'],limit=100)
                        message=next((m for m in data['items'] if m['id']==params['id'] and not m.get('deleted')),None)
                        if not message:raise ValueError('پیام در دسترس نیست.')
                    finally:worker.session.close()
                    message['_native_action']=name
                    if not self.closed:self.native_message_ready.emit(request_id,message,client,token)
                    return
                if queue_op:
                    delivery=self.delivery_for(client)
                    if name=='queue_enqueue':
                        body=params['payload'];key=(self.delivery_identity,body['company'],body['room'])
                        with self.delivery_lock:
                            ident=(self.delivery_identity,body.get('request_id',''));digest=hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
                            if ident[1] and ident in self.enqueued:
                                if self.enqueued[ident]!=digest:raise ValueError('شناسه ارسال برای پیام دیگری استفاده شده است.')
                                value={'id':ident[1]}
                            else:
                                if params['draft_version']<=self.draft_versions.get(key,-1):raise ValueError('پیش‌نویس جدیدتری وجود دارد؛ دوباره پیام را بررسی کنید.')
                                value={'id':delivery.enqueue_and_clear_draft(body)};self.draft_versions[key]=params['draft_version']
                                self.enqueued[(self.delivery_identity,value['id'])]=digest
                                if len(self.enqueued)>256:self.enqueued.pop(next(iter(self.enqueued)))
                    elif name=='queue_flush':value=delivery.flush_one()
                    elif name=='draft_get':value=delivery.draft(params['company'],params['room'])
                    elif name=='draft_save':
                        key=(self.delivery_identity,params['company'],params['room'])
                        with self.delivery_lock:
                            if params['version']<=self.draft_versions.get(key,-1):value={'saved':False}
                            else:
                                delivery.save_draft(params['company'],params['room'],params['text'],params['files'],params['reply_to']);self.draft_versions[key]=params['version'];value={'saved':True}
                    elif name in ('queue_retry','queue_cancel'):
                        if not delivery.lock.acquire(False):raise ValueError('ارسال در حال انجام است؛ پس از پایان دوباره بررسی کنید.')
                        try:
                            if name=='queue_retry':delivery.queue.retry(params['id'])
                            else:delivery.acknowledge(params['id'])
                        finally:delivery.lock.release()
                        value={'ok':True}
                    else:
                        with delivery.queue.lock:value=[{'id':x['payload']['request_id'],'text':x['payload'].get('text',''),'company':x['payload'].get('company',''),'room':x['payload'].get('room',''),'status':x['status'],'error':x['error']} for x in delivery.queue.value['outbox']]
                else:
                    from org_client import Client
                    worker=Client(client.url,client.session.verify if isinstance(client.session.verify,str) else None,getattr(client,'fingerprint',None));worker.token=token;worker.user=client.user
                    try:
                        value = worker.request(path, params) if post else worker.request(path, **params)
                        uid = (client.user or {}).get('id', '')
                        if name=='companies':value=[{'id':item['id'],'name':item['name']} for item in value]
                        elif name=='rooms' and isinstance(value,list):value=_filter_rooms(value,uid)
                        elif name=='updates' and isinstance(value,dict) and 'rooms' in value:value=dict(value,rooms=_filter_rooms(value.get('rooms'),uid))
                    finally:worker.session.close()
                result = {'ok':True,'value':value}
            except Exception as exc: result = {'ok':False,'error':str(exc)}
            if not self.closed and self.client_provider() is client and client.token==token:
                try:self.completed.emit(request_id,json.dumps(result,ensure_ascii=False))
                except RuntimeError:pass
        self.pool.submit(run)
    def close(self):
        self.closed = True; self.pool.shutdown(wait=False, cancel_futures=True)
