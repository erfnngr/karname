"""Per-user scheduled assistant requests, protected by the Windows account."""
import hashlib,uuid
from datetime import datetime,timezone
from storage import app_dir
from local_vault import load,save

def path_for(user):
    if not user or user=='standalone':raise ValueError('برای زمان‌بندی وارد حساب خود شوید.')
    return app_dir()/'assistant-schedules'/(hashlib.sha256(user.encode()).hexdigest()+'.dpapi')

def read(user):
    value=load(path_for(user),{'items':[]})
    if not isinstance(value,dict) or not isinstance(value.get('items'),list):raise ValueError('فهرست درخواست‌های زمان‌بندی‌شده قابل خواندن نیست.')
    return value['items']

def write(user,items):save(path_for(user),{'items':items})

def add(user,prompt,mode,due_at):
    if not isinstance(prompt,str) or not 1<=len(prompt.strip())<=6000 or mode not in ('chat','plan','app'):raise ValueError('متن یا نوع درخواست معتبر نیست.')
    try:
        when=datetime.fromisoformat(due_at)
        if when.tzinfo is None or when<=datetime.now(timezone.utc):raise ValueError()
    except (ValueError,TypeError,OverflowError):raise ValueError('زمان ارسال باید در آینده باشد.') from None
    items=read(user)
    if sum(item.get('status') in ('pending','running') for item in items)>=100:raise ValueError('حداکثر ۱۰۰ درخواست در انتظار مجاز است.')
    entry=dict(id=uuid.uuid4().hex,prompt=prompt.strip(),mode=mode,due_at=when.astimezone(timezone.utc).isoformat(timespec='seconds'),status='pending');items.append(entry);write(user,items);return entry

def transition(user,id,old,new):
    items=read(user);item=next((x for x in items if x.get('id')==id),None)
    if not item or item.get('status') not in old:return False
    item['status']=new;write(user,items);return True

def reschedule(user,id,due_at):
    try:
        when=datetime.fromisoformat(due_at)
        if when.tzinfo is None or when<=datetime.now(timezone.utc):raise ValueError()
    except (ValueError,TypeError,OverflowError):raise ValueError('زمان ارسال باید در آینده باشد.') from None
    items=read(user);item=next((x for x in items if x.get('id')==id),None)
    if not item or item.get('status') not in ('pending','failed','interrupted'):raise ValueError('این درخواست قابل زمان‌بندی مجدد نیست.')
    item['due_at']=when.astimezone(timezone.utc).isoformat(timespec='seconds');item['status']='pending';write(user,items)

def recover(user):
    items=read(user);changed=False
    for item in items:
        if item.get('status')=='running':item['status']='interrupted';changed=True
    if changed:write(user,items)

def backup_data(user):
    if not path_for(user).is_file():return None
    return {'user_id':user,'items':read(user)}

def prepare_restore(user,value):
    if not isinstance(value,dict) or value.get('user_id')!=user or not isinstance(value.get('items'),list) or len(value['items'])>10000:raise ValueError('درخواست‌های زمان‌بندی‌شده متعلق به این حساب یا معتبر نیستند.')
    result=[];ids=set();now=datetime.now(timezone.utc)
    for item in value['items']:
        if not isinstance(item,dict) or set(item)!={'id','prompt','mode','due_at','status'}:raise ValueError('درخواست زمان‌بندی‌شده معتبر نیست.')
        id=item['id'];prompt=item['prompt'];mode=item['mode'];status=item['status']
        if not isinstance(id,str) or len(id)!=32 or any(x not in '0123456789abcdef' for x in id) or id in ids or not isinstance(prompt,str) or not 1<=len(prompt.strip())<=6000 or mode not in ('chat','plan','app') or status not in ('pending','running','failed','interrupted','completed','cancelled'):raise ValueError('درخواست زمان‌بندی‌شده معتبر نیست.')
        try:
            when=datetime.fromisoformat(item['due_at'])
            if when.tzinfo is None:raise ValueError()
        except (TypeError,ValueError,OverflowError):raise ValueError('تاریخ درخواست زمان‌بندی‌شده معتبر نیست.') from None
        entry=dict(item)
        if status=='running' or status=='pending' and when<=now:entry['status']='interrupted'
        result.append(entry);ids.add(id)
    return result
