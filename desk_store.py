"""Private notes and identity-bound leave requests with manager review."""
import json,copy,re,uuid,hashlib
from datetime import datetime,timezone
from decimal import Decimal

def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def uid():return uuid.uuid4().hex
def dump(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def init_desk(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS desk_notes(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),title TEXT,body TEXT,date_jalali TEXT,calendar_enabled INTEGER DEFAULT 0,lead_days TEXT DEFAULT '[]',completed INTEGER DEFAULT 0,version INTEGER DEFAULT 1,created TEXT,updated TEXT,deleted INTEGER DEFAULT 0);
    CREATE INDEX IF NOT EXISTS desk_notes_owner ON desk_notes(user_id,deleted);
    CREATE TABLE IF NOT EXISTS desk_leaves(id TEXT PRIMARY KEY,company_id TEXT REFERENCES companies(id),requester_id TEXT REFERENCES users(id),payload TEXT,status TEXT DEFAULT 'pending',version INTEGER DEFAULT 1,created TEXT,updated TEXT,reviewer_id TEXT REFERENCES users(id),reviewed_at TEXT,review_note TEXT DEFAULT '',deleted INTEGER DEFAULT 0);
    CREATE INDEX IF NOT EXISTS desk_leaves_scope ON desk_leaves(company_id,requester_id,status);
    CREATE TABLE IF NOT EXISTS desk_notifications(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),leave_id TEXT REFERENCES desk_leaves(id),version INTEGER,title TEXT,body TEXT,created TEXT,shown TEXT,opened TEXT,UNIQUE(user_id,leave_id,version));
    CREATE TABLE IF NOT EXISTS desk_ai_requests(user_id TEXT NOT NULL,request_id TEXT NOT NULL,kind TEXT NOT NULL,digest TEXT NOT NULL,target_id TEXT NOT NULL,PRIMARY KEY(user_id,request_id));
    ''')

class DeskStoreMixin:
    def desk_manager(self,actor,company):
        return actor['global_role'] in ('group_admin','system_admin') or self.role(actor,company)=='company_manager'
    def desk_company(self,actor,company):
        if company=='__shared_chat__':self.require(self.module_permission(actor,company,'chat','view'));return
        self.require(any(c['id']==company for c in self.companies(actor)),'به این شرکت دسترسی ندارید.')
    def desk_leave(self,actor,id):
        from org_store import DomainError
        with self.db() as c:row=c.execute('SELECT * FROM desk_leaves WHERE id=? AND deleted=0',(id,)).fetchone()
        if not row:raise DomainError('درخواست پیدا نشد.',404)
        item=dict(row,payload=json.loads(row['payload']));self.desk_company(actor,item['company_id']);self.require_module(actor,item['company_id'],'desk','view');self.require(item['requester_id']==actor['id'] or self.desk_manager(actor,item['company_id']));return item
    def desk_notify(self,c,person,leave,version,title,body):
        c.execute('INSERT OR IGNORE INTO desk_notifications(id,user_id,leave_id,version,title,body,created) VALUES(?,?,?,?,?,?,?)',(uid(),person,leave,version,title[:200],body[:1000],now()))
    def desk_managers(self,company,exclude=None):
        with self.db() as c:ids=[r[0] for r in c.execute("SELECT DISTINCT u.id FROM users u LEFT JOIN memberships m ON u.id=m.user_id WHERE u.active=1 AND (u.global_role IN ('group_admin','system_admin') OR (m.company_id=? AND m.role='company_manager'))",(company,))]
        return [x for x in ids if x!=exclude]
    def desk_leave_save(self,actor,company,payload,id=None,version=None,request_id=None):
        from storage import parse_j,normalize
        from org_store import DomainError
        self.desk_company(actor,company);self.require_module(actor,company,'desk','edit' if id else 'create');self.require(isinstance(payload,dict),'اطلاعات درخواست معتبر نیست.')
        start=parse_j(payload.get('start_date',''));end=parse_j(payload.get('end_date',''));self.require(end>=start,'پایان مرخصی قبل از شروع است.')
        kind=payload.get('leave_type','استحقاقی');self.require(kind in ('استحقاقی','استعلاجی','بدون حقوق','ساعتی','سایر'),'نوع مرخصی معتبر نیست.');hours='0';start_time='';end_time=''
        if kind=='ساعتی':
            self.require(start==end,'برای مرخصی ساعتی، شروع و پایان در یک روز باشند.')
            start_time=normalize(payload.get('start_time',''));end_time=normalize(payload.get('end_time',''))
            try:
                a=datetime.strptime(start_time,'%H:%M');b=datetime.strptime(end_time,'%H:%M');minutes=int((b-a).total_seconds()/60);assert minutes>0
            except Exception:raise DomainError('ساعت پایان باید بعد از شروع و با قالب 09:30 باشد.')
            hours=str((Decimal(minutes)/60).quantize(Decimal('0.01')))
        notes=str(payload.get('notes','')).strip();self.require(len(notes)<=8000,'توضیحات حداکثر ۸۰۰۰ نویسه باشد.')
        # Identity and status are always supplied by the authenticated host.
        p=dict(requester_id=actor['id'],requester_name=actor['fullname'],leave_type=kind,start_date=f'{start.year:04d}/{start.month:02d}/{start.day:02d}',end_date=f'{end.year:04d}/{end.month:02d}/{end.day:02d}',start_time=start_time,end_time=end_time,hours=hours,notes=notes)
        if request_id:self.require(not id and isinstance(request_id,str) and bool(re.fullmatch('[0-9a-f]{32}',request_id)),'شناسه درخواست معتبر نیست.')
        digest=hashlib.sha256(dump(dict(company=company,payload=p)).encode()).hexdigest() if request_id else None
        managers=[u for u in self.desk_managers(company,actor['id']) if self.module_permission(self.user(u),company,'desk','approve')];created=now()
        with self.db(True) as c:
            if request_id:
                prior=c.execute('SELECT * FROM desk_ai_requests WHERE user_id=? AND request_id=?',(actor['id'],request_id)).fetchone()
                if prior:
                    self.require(prior['kind']=='leave' and prior['digest']==digest,'شناسه درخواست قبلاً استفاده شده است.');return dict(item=self.desk_leave(actor,prior['target_id']),managers_notified=0,duplicate=True)
            if id:
                old=self.desk_leave(actor,id);self.require(old['requester_id']==actor['id'],'فقط درخواست خودتان قابل ویرایش است.');self.require(old['company_id']==company,'شرکت درخواست قابل تغییر نیست.');self.require(old['status']=='pending','درخواست بررسی‌شده را با درخواست تازه اصلاح کنید.')
                if version is None or int(version)!=old['version']:raise DomainError('درخواست تغییر کرده است؛ تازه‌سازی کنید.',409)
                version=old['version']+1;created=old['created'];c.execute('UPDATE desk_notifications SET opened=COALESCE(opened,?) WHERE leave_id=?',(now(),id))
            else:id=uid();version=1
            c.execute("INSERT INTO desk_leaves(id,company_id,requester_id,payload,status,version,created,updated) VALUES(?,?,?,?,'pending',?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,version=excluded.version,updated=excluded.updated",(id,company,actor['id'],dump(p),version,created,now()))
            for person in managers:self.desk_notify(c,person,id,version,'درخواست مرخصی · '+actor['fullname'],kind+' | '+p['start_date']+' تا '+p['end_date'])
            if request_id:c.execute('INSERT INTO desk_ai_requests VALUES(?,?,?,?,?)',(actor['id'],request_id,'leave',digest,id))
            self.audit(c,actor,company,id,'desk_leave_submit',after={'requester_id':actor['id'],'version':version})
        return dict(item=self.desk_leave(actor,id),managers_notified=len(managers))
    def desk_leave_review(self,actor,id,version,status,note=''):
        from org_store import DomainError
        self.require(status in ('approved','rejected'),'تصمیم معتبر نیست.');note=str(note).strip();self.require(len(note)<=3000,'توضیح بررسی حداکثر ۳۰۰۰ نویسه باشد.')
        with self.db(True) as c:
            row=self.desk_leave(actor,id);self.require(self.desk_manager(actor,row['company_id']),'بررسی مرخصی فقط با مدیر شرکت است.');self.require_module(actor,row['company_id'],'desk','approve');self.require(actor['id']!=row['requester_id'],'درخواست خودتان را مدیر دیگری بررسی می‌کند.')
            if row['version']!=int(version) or row['status']!='pending':raise DomainError('درخواست قبلاً بررسی یا ویرایش شده است؛ تازه‌سازی کنید.',409)
            v=row['version']+1;c.execute('UPDATE desk_leaves SET status=?,version=?,updated=?,reviewer_id=?,reviewed_at=?,review_note=? WHERE id=?',(status,v,now(),actor['id'],now(),note,id));c.execute('UPDATE desk_notifications SET opened=COALESCE(opened,?) WHERE leave_id=?',(now(),id));title='نتیجه مرخصی · '+('تأیید شد' if status=='approved' else 'رد شد');p=row['payload'];self.desk_notify(c,row['requester_id'],id,v,title,p['start_date']+' تا '+p['end_date']+' | '+actor['fullname']);self.audit(c,actor,row['company_id'],id,'desk_leave_'+status,after={'version':v,'reviewer_id':actor['id']})
        return self.desk_leave(actor,id)
    def desk_leave_cancel(self,actor,id,version):
        from org_store import DomainError
        with self.db(True) as c:
            row=self.desk_leave(actor,id);self.require_module(actor,row['company_id'],'desk','edit');self.require(row['requester_id']==actor['id'] and row['status']=='pending','فقط درخواست بررسی‌نشده خودتان قابل لغو است.')
            if row['version']!=int(version):raise DomainError('درخواست تغییر کرده است؛ تازه‌سازی کنید.',409)
            c.execute("UPDATE desk_leaves SET status='cancelled',version=version+1,updated=? WHERE id=?",(now(),id));c.execute('UPDATE desk_notifications SET opened=COALESCE(opened,?) WHERE leave_id=?',(now(),id));self.audit(c,actor,row['company_id'],id,'desk_leave_cancel')
        return {'ok':True}
    def desk_note_payload(self,p):
        from storage import parse_j
        from org_store import DomainError
        self.require(isinstance(p,dict),'یادداشت معتبر نیست.');title=str(p.get('title','')).strip();body=str(p.get('body',''));self.require(bool(title) and len(title)<=200 and len(body)<=30000,'عنوان لازم است؛ متن حداکثر ۳۰ هزار نویسه باشد.');when=str(p.get('date_jalali','')).strip();enabled=bool(p.get('calendar_enabled',False))
        if when:
            d=parse_j(when);when=f'{d.year:04d}/{d.month:02d}/{d.day:02d}'
        self.require(not enabled or bool(when),'برای افزودن به تقویم، تاریخ را وارد کنید.');leads=p.get('lead_days',[0]);self.require(isinstance(leads,list) and len(leads)<=40 and all(isinstance(x,int) and not isinstance(x,bool) and 0<=x<=365 for x in leads),'روزهای یادآوری معتبر نیستند.');return dict(title=title,body=body,date_jalali=when,calendar_enabled=enabled,lead_days=sorted(set(leads),reverse=True),completed=bool(p.get('completed',False)))
    def desk_note_save(self,actor,payload,id=None,version=None,request_id=None):
        from org_store import DomainError
        self.require_module(actor,None,'desk','edit' if id else 'create')
        p=self.desk_note_payload(payload);created=now()
        if request_id:self.require(not id and isinstance(request_id,str) and bool(re.fullmatch('[0-9a-f]{32}',request_id)),'شناسه درخواست معتبر نیست.')
        digest=hashlib.sha256(dump(p).encode()).hexdigest() if request_id else None
        with self.db(True) as c:
            if request_id:
                prior=c.execute('SELECT * FROM desk_ai_requests WHERE user_id=? AND request_id=?',(actor['id'],request_id)).fetchone()
                if prior:
                    self.require(prior['kind']=='note' and prior['digest']==digest,'شناسه درخواست قبلاً استفاده شده است.');row=c.execute('SELECT * FROM desk_notes WHERE id=? AND user_id=? AND deleted=0',(prior['target_id'],actor['id'])).fetchone();self.require(bool(row),'یادداشت قبلی حذف شده است.');return {'id':row['id'],'version':row['version'],'duplicate':True}
            if id:
                row=c.execute('SELECT * FROM desk_notes WHERE id=? AND deleted=0',(id,)).fetchone();self.require(row and row['user_id']==actor['id'],'یادداشت شخصی در دسترس نیست.')
                if version is None or int(version)!=row['version']:raise DomainError('یادداشت در دستگاه دیگری تغییر کرده است؛ تازه‌سازی کنید.',409)
                created=row['created'];v=row['version']+1
            else:id=uid();v=1
            c.execute('INSERT INTO desk_notes VALUES(?,?,?,?,?,?,?,?,?,?,?,0) ON CONFLICT(id) DO UPDATE SET title=excluded.title,body=excluded.body,date_jalali=excluded.date_jalali,calendar_enabled=excluded.calendar_enabled,lead_days=excluded.lead_days,completed=excluded.completed,version=excluded.version,updated=excluded.updated',(id,actor['id'],p['title'],p['body'],p['date_jalali'],int(p['calendar_enabled']),dump(p['lead_days']),int(p['completed']),v,created,now()));self.audit(c,actor,None,id,'desk_note_save',after={'private':True,'version':v})
            if request_id:c.execute('INSERT INTO desk_ai_requests VALUES(?,?,?,?,?)',(actor['id'],request_id,'note',digest,id))
        return {'id':id,'version':v}
    def desk_note_delete(self,actor,id,version):
        from org_store import DomainError
        self.require_module(actor,None,'desk','delete')
        with self.db(True) as c:
            row=c.execute('SELECT * FROM desk_notes WHERE id=? AND deleted=0',(id,)).fetchone();self.require(row and row['user_id']==actor['id'],'یادداشت شخصی در دسترس نیست.')
            if row['version']!=int(version):raise DomainError('یادداشت تغییر کرده است؛ تازه‌سازی کنید.',409)
            c.execute('UPDATE desk_notes SET deleted=1,version=version+1,updated=? WHERE id=?',(now(),id));self.audit(c,actor,None,id,'desk_note_archive')
        return {'ok':True}
    def desk_restore_notes(self,actor,notes):
        self.require_module(actor,None,'desk','create');self.require_module(actor,None,'desk','edit')
        self.require(isinstance(notes,list) and len(notes)<=10000,'فهرست یادداشت‌ها معتبر نیست.');prepared=[]
        for item in notes:
            self.require(isinstance(item,dict) and item.get('user_id')==actor['id'],'پشتیبان یادداشت متعلق به این حساب نیست.');id=item.get('id','');self.require(bool(re.fullmatch('[0-9a-f]{32}',id)),'شناسه یادداشت معتبر نیست.');prepared.append((id,self.desk_note_payload(item)))
        self.require(len({id for id,_ in prepared})==len(prepared),'شناسه یادداشت تکراری است.')
        with self.db(True) as c:
            for id,p in prepared:
                old=c.execute('SELECT * FROM desk_notes WHERE id=?',(id,)).fetchone();self.require(not old or old['user_id']==actor['id'],'شناسه یادداشت متعلق به حساب دیگری است.');v=old['version']+1 if old else 1
                c.execute('INSERT INTO desk_notes VALUES(?,?,?,?,?,?,?,?,?,?,?,0) ON CONFLICT(id) DO UPDATE SET title=excluded.title,body=excluded.body,date_jalali=excluded.date_jalali,calendar_enabled=excluded.calendar_enabled,lead_days=excluded.lead_days,completed=excluded.completed,version=excluded.version,updated=excluded.updated,deleted=0',(id,actor['id'],p['title'],p['body'],p['date_jalali'],int(p['calendar_enabled']),dump(p['lead_days']),int(p['completed']),v,old['created'] if old else now(),now()))
            if prepared:self.audit(c,actor,None,None,'desk_notes_restore',after={'count':len(prepared)})
        return {'restored':len(prepared)}
    def desk_notification(self,actor,id,action='opened'):
        self.require(action in ('opened','shown'),'وضعیت اعلان معتبر نیست.')
        with self.db(True) as c:
            row=c.execute('SELECT * FROM desk_notifications WHERE id=?',(id,)).fetchone();self.require(row and row['user_id']==actor['id']);self.desk_leave(actor,row['leave_id']);c.execute('UPDATE desk_notifications SET '+action+'=COALESCE('+action+',?) WHERE id=?',(now(),id))
        return {'ok':True}
    def desk_snapshot(self,actor):
        companies=[c for c in self.companies(actor) if self.module_permission(actor,c['id'],'desk','view')];allowed={c['id'] for c in companies};managed={c['id'] for c in companies if self.desk_manager(actor,c['id'])};notes_allowed=self.module_permission(actor,None,'desk','view')
        with self.db() as c:
            notes=[dict(r,lead_days=json.loads(r['lead_days']),calendar_enabled=bool(r['calendar_enabled']),completed=bool(r['completed'])) for r in c.execute('SELECT * FROM desk_notes WHERE user_id=? AND deleted=0 ORDER BY updated DESC',(actor['id'],))] if notes_allowed else []
            rows=[dict(r,payload=json.loads(r['payload'])) for r in c.execute('SELECT * FROM desk_leaves WHERE deleted=0 ORDER BY updated DESC')]
            people={r['id']:r['fullname'] for r in c.execute('SELECT id,fullname FROM users')};notifications=[]
            for n in c.execute('SELECT * FROM desk_notifications WHERE user_id=? AND opened IS NULL ORDER BY created DESC',(actor['id'],)):
                row=next((r for r in rows if r['id']==n['leave_id']),None)
                if row and row['company_id'] in allowed and (row['requester_id']==actor['id'] or row['company_id'] in managed):notifications.append(dict(n))
        for row in rows:row['requester_name']=people.get(row['requester_id'],row['payload'].get('requester_name',''));row['reviewer_name']=people.get(row['reviewer_id'],'')
        mine=[r for r in rows if r['requester_id']==actor['id'] and r['company_id'] in allowed];incoming=[r for r in rows if r['company_id'] in managed and r['requester_id']!=actor['id']]
        return dict(format='karname-desk-v1',user_id=actor['id'],companies=companies,managed_companies=sorted(managed),notes=notes,leaves=mine,incoming=incoming,notifications=notifications)
