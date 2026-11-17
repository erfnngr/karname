"""Company rooms, per-account preferences, and attachment ACLs on the host."""
import base64, json, re, hashlib, uuid, sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOMS={'managers':'مدیران','staff':'کارکنان','general':'مشترک'}
MAX_FILE=12*1024*1024

def init_chat(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS profiles(user_id TEXT PRIMARY KEY REFERENCES users(id),avatar TEXT DEFAULT '',color TEXT DEFAULT '#DDEBF8',preferences TEXT DEFAULT '{}');
    CREATE TABLE IF NOT EXISTS company_details(company_id TEXT PRIMARY KEY REFERENCES companies(id),phone TEXT DEFAULT '',address TEXT DEFAULT '',extra TEXT DEFAULT '',logo TEXT DEFAULT '',color TEXT DEFAULT '#187C85');
    CREATE TABLE IF NOT EXISTS chat_messages(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE,company_id TEXT REFERENCES companies(id),room TEXT,author TEXT REFERENCES users(id),kind TEXT,text TEXT,payload TEXT,created TEXT,deleted INTEGER DEFAULT 0);
    CREATE INDEX IF NOT EXISTS chat_room ON chat_messages(company_id,room,seq);
    CREATE TABLE IF NOT EXISTS chat_files(id TEXT PRIMARY KEY,message_id TEXT REFERENCES chat_messages(id),name TEXT,mime TEXT,size INTEGER,sha256 TEXT);
    CREATE TABLE IF NOT EXISTS chat_reads(user_id TEXT REFERENCES users(id),company_id TEXT REFERENCES companies(id),room TEXT,seq INTEGER DEFAULT 0,muted INTEGER DEFAULT 0,PRIMARY KEY(user_id,company_id,room));
    CREATE TABLE IF NOT EXISTS chat_likes(message_id TEXT REFERENCES chat_messages(id),user_id TEXT REFERENCES users(id),PRIMARY KEY(message_id,user_id));
    CREATE TABLE IF NOT EXISTS chat_votes(message_id TEXT REFERENCES chat_messages(id),user_id TEXT REFERENCES users(id),option_no INTEGER,PRIMARY KEY(message_id,user_id));
    CREATE TABLE IF NOT EXISTS chat_meeting_receipts(message_id TEXT REFERENCES chat_messages(id),user_id TEXT REFERENCES users(id),PRIMARY KEY(message_id,user_id));
    CREATE TABLE IF NOT EXISTS chat_scheduled(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,company_id TEXT NOT NULL,room TEXT NOT NULL,text TEXT NOT NULL,due_at TEXT NOT NULL,status TEXT NOT NULL,lease_until TEXT,error TEXT DEFAULT '',message_id TEXT DEFAULT '',request_id TEXT NOT NULL,digest TEXT NOT NULL,created TEXT NOT NULL,UNIQUE(user_id,request_id));
    CREATE INDEX IF NOT EXISTS chat_scheduled_due ON chat_scheduled(status,due_at);
    ''')
    if 'attachments' not in {r[1] for r in c.execute('PRAGMA table_info(chat_scheduled)')}:
        try:c.execute("ALTER TABLE chat_scheduled ADD COLUMN attachments TEXT NOT NULL DEFAULT '[]'")
        except sqlite3.OperationalError:
            if 'attachments' not in {r[1] for r in c.execute('PRAGMA table_info(chat_scheduled)')}:raise

def image_data(value):
    """Decode and normalize an image; no external URLs or active image formats."""
    if not value:return ''
    from PySide6.QtGui import QImage
    from PySide6.QtCore import QBuffer,QIODevice
    from org_store import DomainError
    try:
        raw=base64.b64decode(value,validate=True)
        if len(raw)>1024*1024:raise ValueError()
        image=QImage.fromData(raw)
        if image.isNull() or image.width()>4096 or image.height()>4096:raise ValueError()
        image=image.scaled(256,256,aspectMode=__import__('PySide6.QtCore',fromlist=['Qt']).Qt.KeepAspectRatio)
        buf=QBuffer();buf.open(QIODevice.WriteOnly);image.save(buf,'PNG')
        return base64.b64encode(bytes(buf.data())).decode()
    except Exception:raise DomainError('عکس PNG یا JPG سالم و کمتر از یک مگابایت انتخاب کنید.')

def hex_color(value,default='#DDEBF8'):
    return value if isinstance(value,str) and re.fullmatch(r'#[0-9A-Fa-f]{6}',value) else default

class ChatStoreMixin:
    def own_profile(self,actor):
        with self.db() as c:row=c.execute('SELECT * FROM profiles WHERE user_id=?',(actor['id'],)).fetchone()
        return dict(avatar=row['avatar'],color=row['color'],preferences=json.loads(row['preferences'])) if row else dict(avatar='',color='#DDEBF8',preferences={})

    def save_profile(self,actor,payload):
        from org_store import packed
        self.require_module(actor,None,'settings','edit')
        old=self.own_profile(actor);value=dict(old)
        if 'avatar' in payload:value['avatar']=image_data(payload['avatar'])
        if 'color' in payload:value['color']=hex_color(payload['color'])
        if 'preferences' in payload:
            prefs=payload['preferences']
            self.require(isinstance(prefs,dict),'تنظیمات حساب معتبر نیست.')
            self.require(len(packed(prefs).encode())<150000,'تنظیمات بیش از حد بزرگ است.')
            if 'birthday' in prefs:
                normalized_bday=self.sync_user_birthday(actor,prefs.get('birthday'))
                prefs=dict(prefs)
                if normalized_bday is None:prefs.pop('birthday',None)
                else:prefs['birthday']=normalized_bday
            value['preferences']=prefs
        with self.db(True) as c:
            c.execute('INSERT OR REPLACE INTO profiles VALUES(?,?,?,?)',(actor['id'],value['avatar'],value['color'],packed(value['preferences'])))
            self.audit(c,actor,None,actor['id'],'profile',after={'updated':True})
        return value

    def company_profiles(self,actor):
        values=self.companies(actor)
        with self.db() as c:
            for co in values:
                row=c.execute('SELECT * FROM company_details WHERE company_id=?',(co['id'],)).fetchone()
                if row:co.update(dict(row))
        return values

    def save_company(self,actor,payload):
        from org_store import uid,stamp
        company=payload.get('id');global_admin=actor['global_role'] in ('group_admin','system_admin')
        self.require(global_admin if not company else global_admin or self.role(actor,company)=='company_manager')
        name=str(payload.get('name','')).strip()[:150];self.require(bool(name),'نام شرکت را وارد کنید.')
        if not company:company=uid()
        with self.db(True) as c:
            row=c.execute('SELECT * FROM companies WHERE id=?',(company,)).fetchone()
            if payload.get('id'):self.require(bool(row),'شرکت پیدا نشد.')
            logo=image_data(payload.get('logo',''))
            c.execute('INSERT INTO companies(id,name,created) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name',(company,name,stamp()))
            c.execute('INSERT OR REPLACE INTO company_details VALUES(?,?,?,?,?,?)',(company,str(payload.get('phone',''))[:80],str(payload.get('address',''))[:1000],str(payload.get('extra',''))[:3000],logo,hex_color(payload.get('color'),'#187C85')))
            self.audit(c,actor,company,company,'company_profile',after={'name':name})
        return next(x for x in self.company_profiles(actor) if x['id']==company)

    def room_access(self,actor,company,room):
        self.require(any(x['id']==company for x in self.companies(actor)))
        self.require(room in ROOMS,'گروه گفتگو معتبر نیست.')
        is_manager=actor['global_role'] in ('group_admin','system_admin') or self.role(actor,company)=='company_manager'
        self.require(room=='general' or (room=='managers' and is_manager) or (room=='staff' and not is_manager),'دسترسی به این گروه ندارید.')

    def room_people(self,actor,company,room):
        self.room_access(actor,company,room);result=[]
        with self.db() as c:ids=[r[0] for r in c.execute('SELECT id FROM users WHERE active=1')]
        for user_id in ids:
            person=self.user(user_id)
            try:self.room_access(person,company,room)
            except Exception:continue
            p=self.own_profile(person)
            result.append(dict(id=user_id,fullname=person['fullname'],avatar=p['avatar'],color=p['color']))
        return result

    def chat_rooms(self,actor):
        result=[]
        for company in self.companies(actor):
            for room,title in ROOMS.items():
                try:self.room_access(actor,company['id'],room)
                except Exception:continue
                with self.db() as c:
                    state=c.execute('SELECT * FROM chat_reads WHERE user_id=? AND company_id=? AND room=?',(actor['id'],company['id'],room)).fetchone();read=state['seq'] if state else 0
                    last=c.execute('SELECT seq,text,created FROM chat_messages WHERE company_id=? AND room=? AND deleted=0 ORDER BY seq DESC LIMIT 1',(company['id'],room)).fetchone()
                    count=c.execute('SELECT COUNT(*) FROM chat_messages WHERE company_id=? AND room=? AND author!=? AND seq>? AND deleted=0',(company['id'],room,actor['id'],read)).fetchone()[0]
                result.append(dict(company=company['id'],company_name=company['name'],room=room,title=title,unread=count,muted=bool(state and state['muted']),last=dict(last) if last else None))
        return result

    def chat_message(self,actor,id):
        from org_store import DomainError
        with self.db() as c:row=c.execute('SELECT * FROM chat_messages WHERE id=?',(id,)).fetchone()
        if not row:raise DomainError('پیام پیدا نشد.',404)
        row=dict(row);self.room_access(actor,row['company_id'],row['room']);return row

    def chat_list(self,actor,company,room,before=None,limit=50):
        self.room_access(actor,company,room);limit=max(1,min(int(limit),100));people=self.room_people(actor,company,room);lookup={u['id']:u for u in people}
        with self.db() as c:
            rows=[dict(r) for r in c.execute('SELECT * FROM chat_messages WHERE company_id=? AND room=? AND seq<? ORDER BY seq DESC LIMIT ?',(company,room,int(before or 2**62),limit))]
            reads={r['user_id']:r['seq'] for r in c.execute('SELECT * FROM chat_reads WHERE company_id=? AND room=?',(company,room))}
            for row in rows:
                row['payload']=json.loads(row['payload']);row['person']=lookup.get(row['author'],dict(id=row['author'],fullname='عضو پیشین',avatar='',color='#E0E8F0'))
                row['seen_by']=[p for p in people if p['id']!=row['author'] and reads.get(p['id'],0)>=row['seq']]
                row['likes']=[lookup[r[0]] for r in c.execute('SELECT user_id FROM chat_likes WHERE message_id=?',(row['id'],)) if r[0] in lookup]
                row['files']=[dict(r) for r in c.execute('SELECT id,name,mime,size FROM chat_files WHERE message_id=?',(row['id'],))]
                row['can_delete']=row['author']==actor['id'] or actor['global_role'] in ('group_admin','system_admin') or self.role(actor,company)=='company_manager'
                if row['kind']=='poll':
                    votes=[dict(r) for r in c.execute('SELECT user_id,option_no FROM chat_votes WHERE message_id=?',(row['id'],))];row['votes']=[sum(v['option_no']==i for v in votes) for i in range(len(row['payload'].get('options',[])))];row['my_vote']=next((v['option_no'] for v in votes if v['user_id']==actor['id']),None)
                if row['deleted']:row.update(text='این پیام حذف شده است.',payload={},files=[],likes=[],seen_by=[])
        return dict(items=list(reversed(rows)),has_more=len(rows)==limit,members=people)

    def chat_send(self,actor,company,room,text='',kind='text',payload=None,attachments=None,_delivery=None):
        from org_store import DomainError,uid,stamp,packed
        self.room_access(actor,company,room);payload=payload or {};attachments=attachments or [];text=str(text).strip()
        self.require(kind in ('text','poll','meeting'),'نوع پیام معتبر نیست.')
        self.require(len(text)<=8000 and len(attachments)<=5,'پیام یا تعداد فایل‌ها بیش از حد مجاز است.')
        self.require(bool(text or attachments),'متن یا فایل پیام را انتخاب کنید.')
        if kind=='poll':
            options=[str(x).strip()[:200] for x in payload.get('options',[])];self.require(2<=len(options)<=10 and all(options) and len(set(options))==len(options),'نظرسنجی باید ۲ تا ۱۰ گزینه متفاوت داشته باشد.');payload={'options':options}
        elif kind=='meeting':
            try:
                when=datetime.fromisoformat(str(payload.get('at','')).replace('Z','+00:00'));assert when.tzinfo
            except Exception:raise DomainError('زمان جلسه را با تاریخ و ساعت معتبر تعیین کنید.')
            payload={'at':when.astimezone(timezone.utc).isoformat(),'location':str(payload.get('location',''))[:500]}
        else:payload={}
        files=[];id=uid()
        for f in attachments:
            name=Path(str(f.get('name','')).replace('\\','/')).name[:180];ext=Path(name).suffix.lower()
            self.require(ext in ('.png','.jpg','.jpeg','.pdf','.xlsx','.xls','.csv','.txt','.docx','.zip'),'قالب فایل پشتیبانی نمی‌شود.')
            try:raw=base64.b64decode(f['data'],validate=True)
            except Exception:raise DomainError('فایل پیوست معتبر نیست.')
            self.require(0<len(raw)<=MAX_FILE,'حجم هر فایل باید حداکثر ۱۲ مگابایت باشد.')
            mime={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.pdf':'application/pdf'}.get(ext,'application/octet-stream')
            files.append((uid(),id,name,mime,len(raw),hashlib.sha256(raw).hexdigest(),raw))
        self.require(sum(f[4] for f in files)<=MAX_FILE,'مجموع پیوست‌های هر پیام حداکثر ۱۲ مگابایت است.')
        written=[]
        try:
            with self.db(True) as c:
                cursor=c.execute('INSERT INTO chat_messages(id,company_id,room,author,kind,text,payload,created) VALUES(?,?,?,?,?,?,?,?)',(id,company,room,actor['id'],kind,text,packed(payload),stamp()))
                for f in files:
                    path=self.files/(f[0]+'.bin');path.write_bytes(f[6]);written.append(path);c.execute('INSERT INTO chat_files VALUES(?,?,?,?,?,?)',f[:6])
                self.audit(c,actor,company,id,'chat_send',after={'room':room,'kind':kind})
                seq=cursor.lastrowid
                if _delivery:
                    c.execute('INSERT INTO workspace_chat VALUES(?,?,?,?,0)',(id,_delivery['reply_to'],_delivery['root'],packed(_delivery['mentions'])))
                    if _delivery['request_id']:c.execute('INSERT INTO workspace_sends(user_id,request_id,message_id,digest) VALUES(?,?,?,?)',(actor['id'],_delivery['request_id'],id,_delivery['digest']))
                    for person in _delivery['mentions']:
                        if person!=actor['id']:self.workspace_notify(c,person,company,'اشاره در گفتگو · '+actor['fullname'],text,'message:'+id)
        except Exception:
            for p in written:p.unlink(missing_ok=True)
            raise
        return dict(id=id,seq=seq)

    def chat_action(self,actor,id,action,option=None):
        from org_store import stamp
        row=self.chat_message(actor,id);self.require(not row['deleted'],'پیام حذف شده است.')
        with self.db(True) as c:
            if action=='delete':
                self.require(row['author']==actor['id'] or actor['global_role'] in ('group_admin','system_admin') or self.role(actor,row['company_id'])=='company_manager')
                c.execute("UPDATE chat_messages SET deleted=1,text='',payload='{}' WHERE id=?",(id,));self.audit(c,actor,row['company_id'],id,'chat_delete')
            elif action=='like':
                exists=c.execute('SELECT 1 FROM chat_likes WHERE message_id=? AND user_id=?',(id,actor['id'])).fetchone()
                if exists:c.execute('DELETE FROM chat_likes WHERE message_id=? AND user_id=?',(id,actor['id']))
                else:c.execute('INSERT INTO chat_likes VALUES(?,?)',(id,actor['id']))
            elif action=='like_set':
                self.require(type(option) is bool,'وضعیت پسند معتبر نیست.')
                if option:c.execute('INSERT OR IGNORE INTO chat_likes VALUES(?,?)',(id,actor['id']))
                else:c.execute('DELETE FROM chat_likes WHERE message_id=? AND user_id=?',(id,actor['id']))
            elif action=='vote':
                options=json.loads(row['payload']).get('options',[]);self.require(row['kind']=='poll' and isinstance(option,int) and not isinstance(option,bool) and 0<=option<len(options),'گزینه معتبر نیست.')
                c.execute('INSERT OR REPLACE INTO chat_votes VALUES(?,?,?)',(id,actor['id'],option))
            elif action=='meeting_notified':c.execute('INSERT OR IGNORE INTO chat_meeting_receipts VALUES(?,?)',(id,actor['id']))
            else:self.require(False,'عملیات پیام معتبر نیست.')
            if action in ('like','like_set','vote'):self.audit(c,actor,row['company_id'],id,'chat_'+action)
        return {'ok':True}

    def chat_state(self,actor,company,room,seq=None,muted=None):
        self.room_access(actor,company,room)
        with self.db(True) as c:
            c.execute('INSERT OR IGNORE INTO chat_reads VALUES(?,?,?,0,0)',(actor['id'],company,room))
            if seq is not None:
                previous=c.execute('SELECT seq FROM chat_reads WHERE user_id=? AND company_id=? AND room=?',(actor['id'],company,room)).fetchone()[0]
                last=c.execute('SELECT COALESCE(MAX(seq),0) FROM chat_messages WHERE company_id=? AND room=?',(company,room)).fetchone()[0];seq=max(0,min(int(seq),last));c.execute('UPDATE chat_reads SET seq=MAX(seq,?) WHERE user_id=? AND company_id=? AND room=?',(seq,actor['id'],company,room))
            if seq is not None and seq>previous:self.audit(c,actor,company,None,'chat_read',after={'room':room})
            if muted is not None:c.execute('UPDATE chat_reads SET muted=? WHERE user_id=? AND company_id=? AND room=?',(int(bool(muted)),actor['id'],company,room))
            if muted is not None:self.audit(c,actor,company,None,'chat_mute',after={'room':room,'muted':bool(muted)})
        return {'ok':True}

    def chat_download(self,actor,id):
        from org_store import DomainError
        with self.db() as c:row=c.execute('SELECT * FROM chat_files WHERE id=?',(id,)).fetchone()
        if not row:raise DomainError('فایل پیدا نشد.',404)
        message=self.chat_message(actor,row['message_id']);self.require(not message['deleted'],'پیام حذف شده است.')
        return dict(info=dict(row),data=base64.b64encode((self.files/(id+'.bin')).read_bytes()).decode())

    def chat_schedule(self,actor,company,room,text,due_at,request_id,attachments=None):
        from org_store import DomainError,stamp
        self.room_access(actor,company,room);self.require_module(actor,company,'chat','send')
        self.require(isinstance(text,str) and len(text)<=4000,'متن پیام باید حداکثر ۴۰۰۰ نویسه باشد.')
        attachments=attachments or [];self.require(isinstance(attachments,list) and len(attachments)<=5,'حداکثر پنج پیوست مجاز است.')
        if attachments:self.require_module(actor,company,'chat','attach')
        self.require(bool(text.strip() or attachments),'متن یا فایل پیام را انتخاب کنید.')
        prepared=[];total=0
        for item in attachments:
            self.require(isinstance(item,dict) and isinstance(item.get('name'),str) and isinstance(item.get('data'),str),'پیوست معتبر نیست.')
            name=Path(item['name'].replace('\\','/')).name[:180];self.require(Path(name).suffix.lower() in ('.png','.jpg','.jpeg','.pdf','.xlsx','.xls','.csv','.txt','.docx','.zip'),'قالب فایل پشتیبانی نمی‌شود.')
            try:raw=base64.b64decode(item['data'],validate=True)
            except Exception:raise DomainError('فایل پیوست معتبر نیست.') from None
            self.require(0<len(raw)<=MAX_FILE,'حجم هر فایل باید حداکثر ۱۲ مگابایت باشد.');total+=len(raw);prepared.append(dict(name=name,data=base64.b64encode(raw).decode('ascii')))
        self.require(total<=MAX_FILE,'مجموع پیوست‌ها حداکثر ۱۲ مگابایت است.')
        self.require(isinstance(request_id,str) and bool(re.fullmatch('[a-f0-9]{32}',request_id)),'شناسه درخواست معتبر نیست.')
        try:
            when=datetime.fromisoformat(due_at)
            if when.tzinfo is None:raise ValueError()
            due=when.astimezone(timezone.utc).isoformat(timespec='seconds')
        except (TypeError,ValueError,OverflowError):raise DomainError('تاریخ و ساعت ارسال معتبر نیست.') from None
        text=text.strip();digest_input=[company,room,text,due]+([prepared] if prepared else []);digest=hashlib.sha256(json.dumps(digest_input,ensure_ascii=False).encode()).hexdigest()
        with self.db(True) as c:
            prior=c.execute('SELECT * FROM chat_scheduled WHERE user_id=? AND request_id=?',(actor['id'],request_id)).fetchone()
            if prior:
                self.require(prior['digest']==digest,'شناسه درخواست قبلاً برای پیام دیگری استفاده شده است.');return dict(id=prior['id'],status=prior['status'],duplicate=True)
            self.require(when.astimezone(timezone.utc)>datetime.now(timezone.utc),'زمان ارسال باید در آینده باشد.')
            id=uuid.uuid4().hex;c.execute('INSERT INTO chat_scheduled(id,user_id,company_id,room,text,due_at,status,request_id,digest,created,attachments) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(id,actor['id'],company,room,text,due,'pending',request_id,digest,stamp(),json.dumps(prepared,ensure_ascii=False)));self.audit(c,actor,company,id,'chat_schedule',after={'room':room,'due_at':due,'files':len(prepared)})
        return dict(id=id,status='pending')

    def chat_scheduled_list(self,actor,company,room):
        self.room_access(actor,company,room)
        with self.db() as c:
            rows=[dict(r) for r in c.execute("SELECT id,text,due_at,status,error,attachments FROM chat_scheduled WHERE user_id=? AND company_id=? AND room=? AND status IN ('pending','sending','failed') ORDER BY due_at LIMIT 100",(actor['id'],company,room))]
        for row in rows:row['file_names']=[f['name'] for f in json.loads(row.pop('attachments'))]
        return rows

    def chat_scheduled_cancel(self,actor,id,expected_due_at=None):
        from org_store import DomainError
        with self.db(True) as c:
            row=c.execute('SELECT * FROM chat_scheduled WHERE id=? AND user_id=?',(id,actor['id'])).fetchone()
            if not row:raise DomainError('پیام زمان‌بندی‌شده پیدا نشد.',404)
            if expected_due_at is not None and expected_due_at!=row['due_at']:raise DomainError('زمان پیام تغییر کرده است؛ دوباره بررسی کنید.',409)
            self.require(row['status'] in ('pending','failed'),'ارسال پیام آغاز شده یا قبلاً پایان یافته است.')
            c.execute("UPDATE chat_scheduled SET status='cancelled',error='',attachments='[]' WHERE id=?",(id,));self.audit(c,actor,row['company_id'],id,'chat_schedule_cancel')
        return {'ok':True}

    def chat_scheduled_reschedule(self,actor,id,due_at,expected_due_at=None):
        from org_store import DomainError
        self.require(expected_due_at is None or isinstance(expected_due_at,str),'زمان قبلی معتبر نیست.')
        try:
            when=datetime.fromisoformat(due_at)
            if when.tzinfo is None or when.astimezone(timezone.utc)<=datetime.now(timezone.utc):raise ValueError()
            due=when.astimezone(timezone.utc).isoformat(timespec='seconds')
        except (TypeError,ValueError,OverflowError):raise DomainError('زمان ارسال باید در آینده باشد.') from None
        with self.db() as c:row=c.execute('SELECT * FROM chat_scheduled WHERE id=? AND user_id=?',(id,actor['id'])).fetchone()
        if not row:raise DomainError('پیام زمان‌بندی‌شده پیدا نشد.',404)
        self.room_access(actor,row['company_id'],row['room']);self.require_module(actor,row['company_id'],'chat','send')
        if json.loads(row['attachments']):self.require_module(actor,row['company_id'],'chat','attach')
        with self.db(True) as c:
            changed=c.execute("UPDATE chat_scheduled SET due_at=?,status='pending',error='',lease_until=NULL WHERE id=? AND user_id=? AND status IN ('pending','failed') AND (? IS NULL OR due_at=?)",(due,id,actor['id'],expected_due_at,expected_due_at)).rowcount
            self.require(bool(changed),'ارسال پیام آغاز شده یا قبلاً پایان یافته است.');self.audit(c,actor,row['company_id'],id,'chat_schedule_change',after={'due_at':due})
        return {'ok':True}

    def process_scheduled_chat(self,at=None):
        from org_store import DomainError
        now=(at or datetime.now(timezone.utc)).astimezone(timezone.utc);timestamp=now.isoformat(timespec='seconds');lease=(now+timedelta(minutes=2)).isoformat(timespec='seconds')
        with self.db() as c:ids=[r[0] for r in c.execute("SELECT id FROM chat_scheduled WHERE due_at<=? AND (status='pending' OR (status='sending' AND lease_until<=?)) ORDER BY due_at LIMIT 100",(timestamp,timestamp))]
        sent=0
        for id in ids:
            with self.db(True) as c:
                changed=c.execute("UPDATE chat_scheduled SET status='sending',lease_until=? WHERE id=? AND due_at<=? AND (status='pending' OR (status='sending' AND lease_until<=?))",(lease,id,timestamp,timestamp)).rowcount
                row=c.execute('SELECT * FROM chat_scheduled WHERE id=?',(id,)).fetchone() if changed else None
            if not row:continue
            try:
                actor=self.user(row['user_id']);message=self.chat_send(actor,row['company_id'],row['room'],text=row['text'],attachments=json.loads(row['attachments']),request_id='scheduled-'+id)
                with self.db(True) as c:c.execute("UPDATE chat_scheduled SET status='sent',message_id=?,lease_until=NULL,attachments='[]' WHERE id=?",(message['id'],id))
                sent+=1
            except DomainError:
                with self.db(True) as c:c.execute("UPDATE chat_scheduled SET status='failed',error=?,lease_until=NULL WHERE id=?",('دسترسی یا اطلاعات گفتگو تغییر کرده است.',id))
        return sent

    def chat_updates(self,actor,after=0):
        after=max(0,int(after));rooms=self.chat_rooms(actor);allowed={(r['company'],r['room']):r for r in rooms if not r['muted']};items=[];meetings=[]
        with self.db() as c:
            last=c.execute('SELECT COALESCE(MAX(seq),0) FROM chat_messages').fetchone()[0]
            rows=c.execute('SELECT m.*,u.fullname FROM chat_messages m JOIN users u ON u.id=m.author WHERE m.seq>? AND m.deleted=0 AND m.author!=? ORDER BY m.seq LIMIT 200',(after,actor['id'])).fetchall()
            # Advance only through the fetched batch, so bursts never skip messages.
            cursor=rows[-1]['seq'] if len(rows)==200 else last
            for row in rows:
                room=allowed.get((row['company_id'],row['room']))
                state=c.execute('SELECT seq FROM chat_reads WHERE user_id=? AND company_id=? AND room=?',(actor['id'],row['company_id'],row['room'])).fetchone()
                if room and row['seq']>(state['seq'] if state else 0):items.append(dict(id=row['id'],seq=row['seq'],company=row['company_id'],company_name=room['company_name'],room=row['room'],title=room['title'],author=row['fullname'],text=row['text'][:180] or 'فایل پیوست',kind=row['kind']))
            now=datetime.now(timezone.utc)
            for row in c.execute("SELECT * FROM chat_messages WHERE kind='meeting' AND deleted=0 AND id NOT IN (SELECT message_id FROM chat_meeting_receipts WHERE user_id=?)",(actor['id'],)):
                room=allowed.get((row['company_id'],row['room']));p=json.loads(row['payload']);when=datetime.fromisoformat(p['at'])
                if room and when<=now<when+timedelta(hours=1):meetings.append(dict(id=row['id'],company=row['company_id'],company_name=room['company_name'],room=row['room'],text=row['text'],at=p['at']))
        return dict(cursor=cursor,items=items,meetings=meetings,rooms=rooms)
