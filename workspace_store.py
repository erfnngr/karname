"""Version 8 company workflows. Every entry point checks the authenticated scope."""
import copy,json,re,uuid,calendar,hashlib,sqlite3,time
from datetime import datetime,timezone,date,timedelta
from decimal import Decimal
import jdatetime
from storage import parse_j,normalize
from attendance_reporting import AttendanceMixin,default_policy,normalize_policy
def jformat(d):return f'{d.year:04d}/{d.month:02d}/{d.day:02d}'

REQUEST_TYPES={'mission':'مأموریت','advance':'مساعده','overtime':'اضافه‌کاری','attendance':'اصلاح تردد','purchase':'خرید','expense':'هزینه / تنخواه'}

def now():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def uid():return uuid.uuid4().hex
def dump(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def clean(v):return ' '.join(normalize(str(v)).replace('ي','ی').replace('ك','ک').casefold().split())
def decimal(v,maximum=100000000000000):
    from penalties import number
    n=number(v or 0)
    if n>maximum:raise ValueError('مقدار بیش از حد مجاز است.')
    return n

def init_workspace(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS workspace_requests(id TEXT PRIMARY KEY,company_id TEXT REFERENCES companies(id),user_id TEXT REFERENCES users(id),kind TEXT,payload TEXT,status TEXT,route TEXT,stage INTEGER DEFAULT 0,decisions TEXT DEFAULT '[]',version INTEGER DEFAULT 1,created TEXT,updated TEXT);
    CREATE INDEX IF NOT EXISTS workspace_requests_scope ON workspace_requests(company_id,user_id,status);
    CREATE TABLE IF NOT EXISTS workspace_policy(company_id TEXT,key TEXT,value TEXT,version INTEGER DEFAULT 1,PRIMARY KEY(company_id,key));
    CREATE TABLE IF NOT EXISTS workspace_views(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),name TEXT,payload TEXT,created TEXT);
    CREATE TABLE IF NOT EXISTS workspace_saved(user_id TEXT REFERENCES users(id),kind TEXT,target TEXT,created TEXT,PRIMARY KEY(user_id,kind,target));
    CREATE TABLE IF NOT EXISTS workspace_notifications(id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),company_id TEXT,title TEXT,body TEXT,target TEXT,created TEXT,opened TEXT,shown TEXT);
    CREATE TABLE IF NOT EXISTS workspace_notice_requests(user_id TEXT,request_id TEXT,digest TEXT,record_id TEXT,PRIMARY KEY(user_id,request_id));
    CREATE INDEX IF NOT EXISTS workspace_notifications_owner ON workspace_notifications(user_id,opened,created);
    CREATE TABLE IF NOT EXISTS workspace_chat(message_id TEXT PRIMARY KEY REFERENCES chat_messages(id),reply_to TEXT,root TEXT,mentions TEXT DEFAULT '[]',pinned INTEGER DEFAULT 0);
    CREATE INDEX IF NOT EXISTS workspace_chat_root ON workspace_chat(root);
    CREATE TABLE IF NOT EXISTS workspace_sends(user_id TEXT,request_id TEXT,message_id TEXT REFERENCES chat_messages(id),PRIMARY KEY(user_id,request_id));
    CREATE TABLE IF NOT EXISTS workspace_direct(company_id TEXT REFERENCES companies(id),room TEXT,first_user TEXT REFERENCES users(id),second_user TEXT REFERENCES users(id),created TEXT,PRIMARY KEY(company_id,room),UNIQUE(company_id,first_user,second_user));
    CREATE TABLE IF NOT EXISTS workspace_room_archive(company_id TEXT NOT NULL,room TEXT NOT NULL,actor TEXT NOT NULL,created TEXT NOT NULL,PRIMARY KEY(company_id,room));
    CREATE TABLE IF NOT EXISTS workspace_direct_hidden(company_id TEXT NOT NULL,room TEXT NOT NULL,user_id TEXT NOT NULL,created TEXT NOT NULL,PRIMARY KEY(company_id,room,user_id));
    CREATE TABLE IF NOT EXISTS workspace_groups(company_id TEXT NOT NULL REFERENCES companies(id),room TEXT NOT NULL,title TEXT NOT NULL,created TEXT NOT NULL,actor TEXT NOT NULL REFERENCES users(id),PRIMARY KEY(company_id,room));
    CREATE TABLE IF NOT EXISTS workspace_group_requests(user_id TEXT NOT NULL,request_id TEXT NOT NULL,company_id TEXT NOT NULL,room TEXT NOT NULL,digest TEXT NOT NULL,PRIMARY KEY(user_id,request_id));
    CREATE TABLE IF NOT EXISTS workspace_group_members(company_id TEXT NOT NULL,room TEXT NOT NULL,user_id TEXT NOT NULL REFERENCES users(id),PRIMARY KEY(company_id,room,user_id),FOREIGN KEY(company_id,room) REFERENCES workspace_groups(company_id,room));
    CREATE TABLE IF NOT EXISTS workspace_group_details(room TEXT PRIMARY KEY,company_name TEXT NOT NULL DEFAULT '',avatar TEXT NOT NULL DEFAULT '');
    CREATE TABLE IF NOT EXISTS workspace_message_trash(message_id TEXT PRIMARY KEY REFERENCES chat_messages(id),user_id TEXT NOT NULL REFERENCES users(id),company_id TEXT NOT NULL,room TEXT NOT NULL,text TEXT NOT NULL,payload TEXT NOT NULL,deleted_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS workspace_invoice_requests(user_id TEXT NOT NULL,request_id TEXT NOT NULL,company_id TEXT NOT NULL,digest TEXT NOT NULL,record_id TEXT NOT NULL REFERENCES records(id),PRIMARY KEY(user_id,request_id));
    CREATE INDEX IF NOT EXISTS records_kind_updated ON records(deleted,company_id,kind,updated);
    CREATE INDEX IF NOT EXISTS chat_files_message ON chat_files(message_id);
    ''')
    # Older v8 previews may already have created this table without the digest.
    if 'digest' not in {row[1] for row in c.execute('PRAGMA table_info(workspace_sends)')}:
        c.execute("ALTER TABLE workspace_sends ADD COLUMN digest TEXT DEFAULT ''")

class WorkspaceStoreMixin(AttendanceMixin):
    def reset_chat_once(self):
        """Apply the owner's requested one-time reset when the company server starts."""
        moved=[];count=0
        try:
            with self.db(True) as c:
                for staged in self.files.iterdir():
                    if staged.is_file() and re.fullmatch(r'[0-9a-f]{32}\.chat-reset-[0-9a-f]{32}',staged.name):staged.unlink()
                if c.execute("SELECT 1 FROM meta WHERE key='chat_reset_v9_saved_v2'").fetchone():return {'ok':True,'already_done':True}
                old="SELECT id FROM chat_messages"
                count=c.execute('SELECT COUNT(*) FROM chat_messages').fetchone()[0]
                for file in c.execute('SELECT id FROM chat_files WHERE message_id IN ('+old+')').fetchall():
                    fid=file['id'];self.require(bool(re.fullmatch('[0-9a-f]{32}',fid)),'شناسه پیوست معتبر نیست.')
                    original=self.files/(fid+'.bin');staged=self.files/(fid+'.chat-reset-'+uid())
                    if original.exists():original.replace(staged);moved.append((original,staged))
                for table in ('chat_files','chat_likes','chat_votes','chat_meeting_receipts','workspace_message_trash','workspace_sends','workspace_chat'):
                    c.execute('DELETE FROM '+table+' WHERE message_id IN ('+old+')')
                c.execute("DELETE FROM workspace_saved WHERE kind='message' AND target IN ("+old+")")
                c.execute("DELETE FROM workspace_notifications WHERE target IN (SELECT 'message:'||id FROM chat_messages)")
                c.execute('DELETE FROM chat_messages')
                for table in ('chat_scheduled','chat_reads','workspace_direct_hidden','workspace_group_members','workspace_group_requests','workspace_groups','workspace_direct','workspace_room_archive'):
                    c.execute('DELETE FROM '+table)
                for marker in ('chat_reset_v9_empty','chat_reset_v9_saved_v2'):
                    c.execute('INSERT OR IGNORE INTO meta(key,value) VALUES(?,?)',(marker,now()))
                self.audit(c,None,None,None,'chat_reset',after={'messages':count,'files':len(moved)})
        except Exception:
            for original,staged in reversed(moved):
                if staged.exists():staged.replace(original)
            raise
        failed=[]
        for _,staged in moved:
            try:staged.unlink(missing_ok=True)
            except OSError:failed.append(staged.name)
        if failed:
            from org_store import DomainError
            raise DomainError('پیام‌ها پاک شدند، ولی حذف فیزیکی برخی فایل‌های موقت کامل نشد؛ دسترسی پوشه فایل‌های مرکز را بررسی کنید.',500)
        return {'ok':True,'messages':count,'files':len(moved)}

    def records_revision(self):
        with self.db() as c:audit=c.execute("SELECT COALESCE(MAX(id),0) FROM audit WHERE action IN ('create','edit','archive','trash_restore','deadline_approved','attendance_import','save_user','permissions_update','company_profile','create_company','setup','publish')").fetchone()[0]
        # Scheduled notices can become visible or expire without a database write.
        # A minute bucket triggers an ACL refresh without retransmitting all tasks
        # after every unrelated chat event.
        return audit*100000+int(time.time()//60)%100000

    def workspace_records_delta(self,actor,after=0,known=None):
        self.require(isinstance(known or [],list) and len(known or [])<=20000 and all(isinstance(k,str) and len(k)<=100 for k in (known or [])),'فهرست دریافت معتبر نیست.');known=set(known or []);after=max(0,int(after));revision=self.records_revision();audit_after=after//100000;clock_changed=bool(after and after%100000!=revision%100000)
        with self.db() as c:
            changes=[dict(r) for r in c.execute("SELECT target,action FROM audit WHERE id>? AND action IN ('create','edit','archive','trash_restore','deadline_approved','attendance_import','save_user','permissions_update','company_profile','create_company','setup','publish')",(audit_after,))]
        full=not after or any(r['action'] in ('save_user','permissions_update','company_profile','create_company','setup') for r in changes);items=[];removed=[]
        if full:
            items=self.all_visible(actor);removed=list(known-{r['id'] for r in items})
        else:
            for id in {r['target'] for r in changes if r['target']}:
                try:
                    r=self.record(id)
                    if self.readable(actor,r):items.append(r)
                    elif id in known:removed.append(id)
                except Exception:
                    if id in known:removed.append(id)
            if clock_changed:
                current=self.all_visible(actor,'notice');items.extend(current);visible_ids={r['id'] for r in current}
                # Only IDs supplied by this user can appear in removals.
                with self.db() as c:
                    ids=list(known)
                    for offset in range(0,len(ids),500):
                        part=ids[offset:offset+500]
                        for row in c.execute('SELECT id FROM records WHERE kind=? AND id IN ('+','.join('?' for _ in part)+')',['notice']+part):
                            if row['id'] not in visible_ids:removed.append(row['id'])
        from org_store import public_record_data
        items=[public_record_data(actor,item) for item in items]
        items=list({item['id']:item for item in items}.values());removed=list(set(removed)-{item['id'] for item in items})
        return dict(items=items,removed=removed,full=full,revision=revision)
    def room_access(self,actor,company,room):
        self.require_module(actor,company,'chat','view')
        self.require(company=='__shared_chat__' and (str(room).startswith('dm:') or str(room).startswith('group:') or str(room).startswith('saved:')),'این گفتگو در ساختار جدید وجود ندارد.')
        if str(room).startswith('saved:'):
            self.desk_company(actor,company);self.require(room=='saved:'+actor['id'],'پیام‌های ذخیره‌شده شخصی هستند.')
            return
        if not str(room).startswith('dm:'):
            with self.db() as c:archived=c.execute('SELECT 1 FROM workspace_room_archive WHERE company_id=? AND room=?',(company,room)).fetchone()
            self.require(not archived,'این گروه غیرفعال شده است.')
        if str(room).startswith('group:'):
            self.desk_company(actor,company)
            with self.db() as c:member=c.execute('SELECT 1 FROM workspace_group_members WHERE company_id=? AND room=? AND user_id=?',(company,room,actor['id'])).fetchone()
            self.require(bool(member),'این گروه فقط برای اعضای انتخاب‌شده در دسترس است.');return
        self.require_module(actor,company,'chat','direct')
        self.desk_company(actor,company)
        with self.db() as c:row=c.execute('SELECT * FROM workspace_direct WHERE company_id=? AND room=?',(company,room)).fetchone()
        self.require(row and actor['id'] in (row['first_user'],row['second_user']),'این گفتگوی شخصی فقط در دسترس دو عضو آن است.')

    def workspace_saved_chat(self,actor):
        company='__shared_chat__';self.desk_company(actor,company);self.require_module(actor,company,'chat','view');room='saved:'+actor['id']
        with self.db(True) as c:c.execute("INSERT OR IGNORE INTO workspace_saved(user_id,kind,target,created) VALUES(?,'saved_chat',?,?)",(actor['id'],room,now()))
        return next(r for r in self.chat_rooms(actor) if r['room']==room)

    def workspace_direct(self,actor,company,person=None):
        self.require(company=='__shared_chat__','برای گفتگو نسخه جدید کارنامه را روی همه دستگاه‌ها نصب کنید.');self.desk_company(actor,company);self.require_module(actor,company,'chat','direct' if person else 'view')
        if company=='__shared_chat__':
            with self.db() as c:ids=[r[0] for r in c.execute('SELECT id FROM users WHERE active=1')]
            users=[self.user(id) for id in ids]
        else:users=self.users(actor)
        people=[u for u in users if u['id']!=actor['id'] and u['active'] and self.role(u,company) and self.module_permission(u,company,'chat','direct')]
        if not person:return [dict(id=u['id'],fullname=u['fullname'],username=u['username']) for u in people]
        self.require(any(u['id']==person for u in people),'عضو مجاز همان شرکت را انتخاب کنید.');a,b=sorted((actor['id'],person));import hashlib
        room='dm:'+hashlib.sha256((company+'\n'+a+'\n'+b).encode()).hexdigest()[:40]
        with self.db(True) as c:
            c.execute('INSERT OR IGNORE INTO workspace_direct VALUES(?,?,?,?,?)',(company,room,a,b,now()));c.execute('DELETE FROM workspace_direct_hidden WHERE company_id=? AND room=? AND user_id=?',(company,room,actor['id']));self.audit(c,actor,company,room,'direct_open',after={'participants':[a,b]})
        return next(r for r in self.chat_rooms(actor) if r['company']==company and r['room']==room)

    def workspace_group_people(self,actor,company):
        self.require(company=='__shared_chat__','فضای گفتگو معتبر نیست.');self.desk_company(actor,company);self.require_module(actor,company,'chat','view')
        with self.db() as c:ids=[r[0] for r in c.execute('SELECT id FROM users WHERE active=1')]
        users=[self.user(id) for id in ids]
        return [dict(id=u['id'],fullname=u['fullname'],username=u['username']) for u in users if u['id']!=actor['id'] and self.role(u,company) and self.module_permission(u,company,'chat','view')]

    def chat_group_manage(self,actor,company,room):
        with self.db() as c:group=c.execute('SELECT actor FROM workspace_groups WHERE company_id=? AND room=?',(company,room)).fetchone()
        return bool(group and (group['actor']==actor['id'] or self.desk_manager(actor,company)))

    def workspace_group_create(self,actor,company,title,members,request_id=None,company_name='',avatar=''):
        self.require(company=='__shared_chat__','برای گفتگو نسخه جدید کارنامه را روی همه دستگاه‌ها نصب کنید.');self.desk_company(actor,company);self.require_module(actor,company,'chat','send')
        title=str(title).strip();self.require(1<=len(title)<=100,'نام گروه را وارد کنید.');self.require(isinstance(members,list) and len(members)<=100 and all(isinstance(x,str) for x in members),'اعضای گروه معتبر نیستند.')
        self.require(isinstance(company_name,str) and len(company_name)<=100 and isinstance(avatar,str) and len(avatar)<=400000,'اطلاعات شرکت یا تصویر معتبر نیست.')
        if company=='__shared_chat__':
            with self.db() as c:ids=[r[0] for r in c.execute('SELECT id FROM users WHERE active=1')]
            users=[self.user(id) for id in ids]
        else:users=self.users(actor)
        people={u['id']:u for u in users};chosen=set(members)|{actor['id']}
        self.require(all(user in people and people[user]['active'] and self.role(people[user],company) and self.module_permission(people[user],company,'chat','view') for user in chosen),'همه اعضا باید عضو فعال و دارای دسترسی چت در همین شرکت باشند.')
        if request_id:self.require(isinstance(request_id,str) and bool(re.fullmatch('[0-9a-f]{32}',request_id)),'شناسه درخواست معتبر نیست.')
        digest=hashlib.sha256(dump(dict(company=company,title=title,members=sorted(chosen))).encode()).hexdigest() if request_id else None
        room='group:'+uid()
        with self.db(True) as c:
            if request_id:
                prior=c.execute('SELECT * FROM workspace_group_requests WHERE user_id=? AND request_id=?',(actor['id'],request_id)).fetchone()
                if prior:
                    self.require(prior['company_id']==company and prior['digest']==digest,'شناسه درخواست قبلاً برای گروه دیگری استفاده شده است.');self.require(bool(c.execute('SELECT 1 FROM workspace_groups WHERE company_id=? AND room=?',(company,prior['room'])).fetchone()),'گروه پیشین حذف شده است.');return dict(company=company,room=prior['room'],duplicate=True)
            c.execute('INSERT INTO workspace_groups VALUES(?,?,?,?,?)',(company,room,title,now(),actor['id']))
            c.execute('INSERT INTO workspace_group_details VALUES(?,?,?)',(room,company_name,avatar))
            c.executemany('INSERT INTO workspace_group_members VALUES(?,?,?)',[(company,room,user) for user in chosen]);self.audit(c,actor,company,room,'chat_group_create',after={'title':title,'members':sorted(chosen)})
            if request_id:c.execute('INSERT INTO workspace_group_requests VALUES(?,?,?,?,?)',(actor['id'],request_id,company,room,digest))
        return next(r for r in self.chat_rooms(actor) if r['company']==company and r['room']==room)

    def chat_rooms(self,actor):
        result=[];allowed={'__shared_chat__':'گفتگوها'} if self.module_permission(actor,'__shared_chat__','chat','view') else {}
        with self.db() as c:
            if allowed:
                company='__shared_chat__';room='saved:'+actor['id'];state=c.execute('SELECT * FROM chat_reads WHERE user_id=? AND company_id=? AND room=?',(actor['id'],company,room)).fetchone();last=c.execute('SELECT seq,text,created FROM chat_messages WHERE company_id=? AND room=? AND deleted=0 ORDER BY seq DESC LIMIT 1',(company,room)).fetchone()
                result.append(dict(company=company,company_name=allowed[company],room=room,title='پیام‌های ذخیره‌شده',saved=True,unread=0,muted=bool(state and state['muted']),last=dict(last) if last else None))
            for row in c.execute('SELECT g.* FROM workspace_groups g JOIN workspace_group_members m ON m.company_id=g.company_id AND m.room=g.room WHERE m.user_id=?',(actor['id'],)):
                if row['company_id'] not in allowed:continue
                try:self.room_access(actor,row['company_id'],row['room'])
                except Exception:continue
                state=c.execute('SELECT * FROM chat_reads WHERE user_id=? AND company_id=? AND room=?',(actor['id'],row['company_id'],row['room'])).fetchone();read=state['seq'] if state else 0;last=c.execute('SELECT seq,text,created FROM chat_messages WHERE company_id=? AND room=? AND deleted=0 ORDER BY seq DESC LIMIT 1',(row['company_id'],row['room'])).fetchone();count=c.execute('SELECT COUNT(*) FROM chat_messages WHERE company_id=? AND room=? AND seq>? AND author!=? AND deleted=0',(row['company_id'],row['room'],read,actor['id'])).fetchone()[0]
                details=c.execute('SELECT company_name,avatar FROM workspace_group_details WHERE room=?',(row['room'],)).fetchone()
                result.append(dict(company=row['company_id'],company_name=allowed[row['company_id']],group_company=details['company_name'] if details else '',avatar=details['avatar'] if details else '',room=row['room'],title=row['title'],unread=count,muted=bool(state and state['muted']),last=dict(last) if last else None,can_manage=bool(row['actor']==actor['id'] or self.desk_manager(actor,row['company_id']))))
            for row in c.execute('SELECT * FROM workspace_direct WHERE first_user=? OR second_user=?',(actor['id'],actor['id'])):
                if row['company_id'] not in allowed:continue
                if c.execute('SELECT 1 FROM workspace_direct_hidden WHERE company_id=? AND room=? AND user_id=?',(row['company_id'],row['room'],actor['id'])).fetchone():continue
                try:self.room_access(actor,row['company_id'],row['room'])
                except Exception:continue
                person=row['second_user'] if row['first_user']==actor['id'] else row['first_user'];other=c.execute('SELECT fullname FROM users WHERE id=?',(person,)).fetchone();profile=c.execute('SELECT avatar FROM profiles WHERE user_id=?',(person,)).fetchone();state=c.execute('SELECT * FROM chat_reads WHERE user_id=? AND company_id=? AND room=?',(actor['id'],row['company_id'],row['room'])).fetchone();read=state['seq'] if state else 0;last=c.execute('SELECT seq,text,created FROM chat_messages WHERE company_id=? AND room=? AND deleted=0 ORDER BY seq DESC LIMIT 1',(row['company_id'],row['room'])).fetchone();count=c.execute('SELECT COUNT(*) FROM chat_messages WHERE company_id=? AND room=? AND seq>? AND author!=? AND deleted=0',(row['company_id'],row['room'],read,actor['id'])).fetchone()[0]
                peer_name=other[0] if other else 'عضو پیشین';result.append(dict(company=row['company_id'],company_name=allowed[row['company_id']],room=row['room'],title='شخصی · '+peer_name,display_title=peer_name,avatar=profile[0] if profile else '',direct=True,peer=person,unread=count,muted=bool(state and state['muted']),last=dict(last) if last else None))
        return result

    def workspace_hide_room(self,actor,company,room):
        if str(room).startswith('saved:'):
            self.room_access(actor,company,room)
            with self.db(True) as c:c.execute("DELETE FROM workspace_saved WHERE user_id=? AND kind='saved_chat' AND target=?",(actor['id'],room))
            return {'ok':True,'scope':'self'}
        direct=str(room).startswith('dm:')
        if direct:self.room_access(actor,company,room)
        else:
            from chat_store import ROOMS
            self.require_module(actor,company,'chat','view');self.desk_company(actor,company)
            self.require(self.chat_group_manage(actor,company,room),'فقط سازنده گروه یا مدیر می‌تواند گروه را غیرفعال کند.')
        with self.db(True) as c:
            if direct:c.execute('INSERT OR REPLACE INTO workspace_direct_hidden VALUES(?,?,?,?)',(company,room,actor['id'],now()))
            else:c.execute('INSERT OR REPLACE INTO workspace_room_archive VALUES(?,?,?,?)',(company,room,actor['id'],now()))
            self.audit(c,actor,company,room,'chat_hide' if direct else 'chat_group_archive',after={'direct':direct})
        return {'ok':True,'scope':'self' if direct else 'company'}

    def workspace_restore_group(self,actor,company,room):
        self.require_module(actor,company,'chat','view');self.desk_company(actor,company)
        self.require(self.chat_group_manage(actor,company,room),'فقط سازنده گروه یا مدیر می‌تواند گروه را بازگرداند.')
        with self.db(True) as c:
            c.execute('DELETE FROM workspace_room_archive WHERE company_id=? AND room=?',(company,room));self.audit(c,actor,company,room,'chat_group_restore')
        return {'ok':True}

    def workspace_clear_chat(self,actor,company,room,through=None):
        """Preview, then remove visible message bodies through the reviewed sequence."""
        self.room_access(actor,company,room);self.require_module(actor,company,'chat','delete')
        if str(room).startswith('group:'):
            self.require(self.chat_group_manage(actor,company,room),'پاک‌کردن گروه برای همه فقط با سازنده گروه یا مدیر است.')
        with self.db(True) as c:
            if through is None:
                row=c.execute('SELECT MAX(seq) AS last, COUNT(*) AS n FROM chat_messages WHERE company_id=? AND room=? AND deleted=0',(company,room)).fetchone()
                return {'through':row['last'] or 0,'count':row['n']}
            self.require(isinstance(through,int) and not isinstance(through,bool) and through>=0,'محدوده پیام معتبر نیست.')
            count=c.execute('SELECT COUNT(*) FROM chat_messages WHERE company_id=? AND room=? AND deleted=0 AND seq<=?',(company,room,through)).fetchone()[0]
            c.execute("INSERT OR REPLACE INTO workspace_message_trash SELECT id,?,company_id,room,text,payload,? FROM chat_messages WHERE company_id=? AND room=? AND deleted=0 AND seq<=?",(actor['id'],now(),company,room,through))
            c.execute("UPDATE chat_messages SET deleted=1,text='',payload='{}' WHERE company_id=? AND room=? AND deleted=0 AND seq<=?",(company,room,through))
            self.audit(c,actor,company,room,'chat_clear',after={'through':through,'count':count})
        return {'ok':True,'count':count}

    def workspace_notify(self,c,user,company,title,body='',target=''):
        c.execute('INSERT INTO workspace_notifications(id,user_id,company_id,title,body,target,created) VALUES(?,?,?,?,?,?,?)',(uid(),user,company,str(title)[:200],str(body)[:2000],target,now()))

    def workspace_notifications(self,actor,id=None,action=None):
        if id:
            self.require(action in ('opened','shown'),'وضعیت اعلان معتبر نیست.')
            with self.db(True) as c:
                row=c.execute('SELECT * FROM workspace_notifications WHERE id=? AND user_id=?',(id,actor['id'])).fetchone();self.require(bool(row))
                if row['company_id']:self.desk_company(actor,row['company_id'])
                c.execute('UPDATE workspace_notifications SET '+action+'=COALESCE('+action+',?) WHERE id=?',(now(),id))
            return {'ok':True}
        allowed={x['id'] for x in self.companies(actor)}
        with self.db() as c:rows=[dict(r) for r in c.execute('SELECT * FROM workspace_notifications WHERE user_id=? AND opened IS NULL ORDER BY created DESC LIMIT 200',(actor['id'],))]
        result=[]
        for r in rows:
            kind,sep,target=(r['target'] or '').partition(':')
            if r['company_id']=='__shared_chat__':
                if kind!='message' or not self.module_permission(actor,'__shared_chat__','chat','view'):continue
            elif r['company_id'] and r['company_id'] not in allowed:continue
            try:
                if kind=='message':
                    message=self.chat_message(actor,target)
                    if message['deleted']:continue
                elif kind=='record':
                    if not self.readable(actor,self.record(target)):continue
                elif kind=='request':self.workspace_request_item(actor,target)
            except Exception:continue
            result.append(r)
        return result

    def workspace_target(self,actor,id):
        """Resolve the current notification only after checking the target's ACL."""
        from org_store import DomainError
        with self.db() as c:n=c.execute('SELECT * FROM workspace_notifications WHERE id=? AND user_id=?',(id,actor['id'])).fetchone()
        self.require(bool(n),'اعلان در دسترس نیست.')
        if n['company_id']:self.desk_company(actor,n['company_id'])
        kind,sep,target=(n['target'] or '').partition(':')
        if not sep:raise DomainError('این اعلان پیوندی به مورد ندارد.',404)
        if kind=='record':
            r=self.record(target);self.require(self.readable(actor,r))
            from org_store import public_record_data
            return dict(kind=kind,record=public_record_data(actor,r))
        if kind=='request':return dict(kind=kind,request=self.workspace_request_item(actor,target))
        if kind=='message':
            r=self.chat_message(actor,target);self.require(not r['deleted'],'پیام حذف شده است.')
            data=self.chat_list(actor,r['company_id'],r['room'],before=r['seq']+1,limit=1)
            if not data['items'] or data['items'][0]['id']!=target:raise DomainError('پیام در دسترس نیست.',404)
            return dict(kind=kind,company=r['company_id'],room=r['room'],message=data['items'][0])
        raise DomainError('نوع پیوند اعلان معتبر نیست.',404)

    def workspace_policy(self,actor,company,key,payload=None):
        self.desk_company(actor,company);self.require(key in ('capacity','leave','routes','attendance'),'نوع تنظیم معتبر نیست.')
        if key=='attendance':
            from permission_policy import allowed
            self.require(allowed(actor,company,'attendance','manage_schedule' if payload is not None else 'view'),'دسترسی برنامه تردد را ندارید.')
        elif key in ('capacity','routes'):self.require_module(actor,company,'workspace','approve' if payload is not None else 'view')
        elif key=='leave':self.require_module(actor,company,'attendance','manage_schedule' if payload is not None else 'view')
        if payload is not None:
            self.require(self.desk_manager(actor,company),'تنظیم قواعد با مدیر شرکت است.');self.require(isinstance(payload,dict) and len(dump(payload))<60000)
            if key=='attendance':payload=normalize_policy(self,actor,company,payload)
            if key in ('capacity','leave'):
                decimal(payload.get('daily_hours',8),24);decimal(payload.get('weekly_hours',40),168)
                days=payload.get('working_days',[0,1,2,5,6]);self.require(isinstance(days,list) and days and len(set(days))==len(days) and all(isinstance(d,int) and not isinstance(d,bool) and 0<=d<=6 for d in days),'روزهای کاری معتبر نیستند.')
                for user,value in payload.get('people',{}).items():
                    self.require(self.role(self.user(user),company) is not None,'شخص باید عضو شرکت باشد.')
                    self.require(isinstance(value,dict));decimal(value.get('daily_hours',8),24);decimal(value.get('annual_hours',0),10000);decimal(value.get('opening_hours',0),10000)
                    years=value.get('years',{});self.require(isinstance(years,dict) and len(years)<=200,'سهم مرخصی سالانه معتبر نیست.')
                    for year,entry in years.items():
                        self.require(bool(re.fullmatch(r'1[34]\d\d',str(year))) and isinstance(entry,dict),'سال سهم مرخصی معتبر نیست.');decimal(entry.get('annual_hours',0),10000);decimal(entry.get('opening_hours',0),10000)
            if key=='routes':
                for kind,route in payload.items():
                    self.require(kind in REQUEST_TYPES and isinstance(route,list) and 1<=len(route)<=5 and len(route)==len(set(route)),'مسیر تأیید باید ۱ تا ۵ فرد متفاوت داشته باشد.')
                    for person in route:self.require(self.desk_manager(self.user(person),company),'تأییدکننده باید مدیر همان شرکت باشد.')
            with self.db(True) as c:
                c.execute('INSERT INTO workspace_policy VALUES(?,?,?,1) ON CONFLICT(company_id,key) DO UPDATE SET value=excluded.value,version=version+1',(company,key,dump(payload)));self.audit(c,actor,company,None,'policy_'+key,after=payload)
        with self.db() as c:row=c.execute('SELECT * FROM workspace_policy WHERE company_id=? AND key=?',(company,key)).fetchone()
        value=json.loads(row['value']) if row else (default_policy() if key=='attendance' else {} if key=='routes' else dict(daily_hours='8',weekly_hours='40',working_days=[0,1,2,5,6],exclude_holidays=True,people={}))
        # Staff can inspect only their own balance settings, never colleagues' HR settings.
        if not self.desk_manager(actor,company):value=dict(value,people={actor['id']:value.get('people',{}).get(actor['id'],{})}) if key!='routes' else {}
        return dict(value=value,version=row['version'] if row else 0)

    def workspace_request_item(self,actor,id):
        from org_store import DomainError
        with self.db() as c:row=c.execute('SELECT * FROM workspace_requests WHERE id=?',(id,)).fetchone()
        if not row:raise DomainError('درخواست پیدا نشد.',404)
        r=dict(row,payload=json.loads(row['payload']),route=json.loads(row['route']),decisions=json.loads(row['decisions']));self.desk_company(actor,r['company_id']);self.require_module(actor,r['company_id'],'workspace','view');self.require(r['user_id']==actor['id'] or self.desk_manager(actor,r['company_id']));return r

    def workspace_requests(self,actor,company=None):
        self.require_module(actor,None,'workspace','view');allowed={x['id'] for x in self.companies(actor) if self.module_permission(actor,x['id'],'workspace','view')}
        if company:self.desk_company(actor,company);self.require_module(actor,company,'workspace','view');allowed={company}
        with self.db() as c:
            rows=[dict(r,payload=json.loads(r['payload']),route=json.loads(r['route']),decisions=json.loads(r['decisions'])) for r in c.execute('SELECT * FROM workspace_requests ORDER BY updated DESC')];people={r['id']:r['fullname'] for r in c.execute('SELECT id,fullname FROM users')}
        return [dict(r,person=people.get(r['user_id'],''),can_review=r['status']=='pending' and r['user_id']!=actor['id'] and self.module_permission(actor,r['company_id'],'workspace','approve') and (r['route'][r['stage']]==actor['id'] if r['route'] else self.desk_manager(actor,r['company_id']))) for r in rows if r['company_id'] in allowed and (r['user_id']==actor['id'] or self.desk_manager(actor,r['company_id']))]

    def workspace_request_save(self,actor,company,kind,payload,id=None,version=None):
        from org_store import DomainError
        self.desk_company(actor,company);self.require_module(actor,company,'workspace','edit' if id else 'create');self.require(kind in REQUEST_TYPES and isinstance(payload,dict));title=str(payload.get('title','')).strip();self.require(0<len(title)<=200,'عنوان درخواست لازم است.')
        p=dict(title=title,notes=str(payload.get('notes',''))[:8000],amount=str(decimal(payload.get('amount',0))),hours=str(decimal(payload.get('hours',0),744)))
        for k in ('start_date','end_date'):
            p[k]=jformat(parse_j(payload[k])) if payload.get(k) else ''
        if p['end_date']:self.require(bool(p['start_date']) and parse_j(p['end_date'])>=parse_j(p['start_date']),'بازه تاریخ معتبر نیست.')
        route=self.workspace_policy(actor,company,'routes')['value'].get(kind,[]) if self.desk_manager(actor,company) else None
        if route is None:
            with self.db() as c:r=c.execute("SELECT value FROM workspace_policy WHERE company_id=? AND key='routes'",(company,)).fetchone()
            route=json.loads(r[0]).get(kind,[]) if r else []
        self.require(actor['id'] not in route,'مسیر تأیید شامل خودتان است؛ مدیر دیگری مسیر را اصلاح کند.')
        if route:
            for reviewer in route:self.require(self.desk_manager(self.user(reviewer),company),'مسیر تأیید نیاز به بازبینی مدیر دارد.')
        with self.db(True) as c:
            if id:
                old=self.workspace_request_item(actor,id);self.require(old['user_id']==actor['id'] and old['status']=='pending' and old['stage']==0 and not old['decisions'],'درخواست بررسی‌شده قابل ویرایش نیست.');self.require(old['company_id']==company and old['kind']==kind)
                if old['version']!=int(version or 0):raise DomainError('درخواست تغییر کرده است.',409)
                v=old['version']+1;created=old['created']
            else:id=uid();v=1;created=now()
            c.execute("INSERT INTO workspace_requests VALUES(?,?,?,?,?,'pending',?,0,'[]',?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,route=excluded.route,version=excluded.version,updated=excluded.updated",(id,company,actor['id'],kind,dump(p),dump(route),v,created,now()))
            for person in (route[:1] if route else self.desk_managers(company,actor['id'])):
                if self.module_permission(self.user(person),company,'workspace','approve'):self.workspace_notify(c,person,company,REQUEST_TYPES[kind]+' · '+actor['fullname'],title,'request:'+id)
            self.audit(c,actor,company,id,'request_submit',after={'kind':kind,'version':v})
        return self.workspace_request_item(actor,id)

    def workspace_request_review(self,actor,id,version,status,note=''):
        from org_store import DomainError
        self.require(status in ('approved','rejected','cancelled'));self.require(len(str(note))<=3000)
        with self.db(True) as c:
            r=self.workspace_request_item(actor,id)
            if r['version']!=int(version) or r['status']!='pending':raise DomainError('درخواست تغییر کرده یا بررسی شده است.',409)
            stage=r['stage'];decisions=r['decisions'];final=status
            if status=='cancelled':self.require_module(actor,r['company_id'],'workspace','edit');self.require(actor['id']==r['user_id'],'لغو فقط با درخواست‌کننده است.')
            else:
                self.require_module(actor,r['company_id'],'workspace','approve');self.require(self.desk_manager(actor,r['company_id']) and actor['id']!=r['user_id']);self.require(not r['route'] or r['route'][stage]==actor['id'],'اکنون نوبت تأیید شما نیست.')
                decisions.append(dict(by=actor['id'],name=actor['fullname'],at=now(),status=status,note=str(note)))
                if status=='approved' and r['route'] and stage+1<len(r['route']):stage+=1;final='pending';self.workspace_notify(c,r['route'][stage],r['company_id'],'درخواست منتظر بررسی',r['payload']['title'],'request:'+id)
            c.execute('UPDATE workspace_requests SET status=?,stage=?,decisions=?,version=version+1,updated=? WHERE id=?',(final,stage,dump(decisions),now(),id));self.workspace_notify(c,r['user_id'],r['company_id'],'وضعیت درخواست · '+{'approved':'تأیید شد','rejected':'رد شد','cancelled':'لغو شد','pending':'مرحله بعد'}[final],r['payload']['title'],'request:'+id);self.audit(c,actor,r['company_id'],id,'request_'+status,after={'stage':stage,'note':str(note)})
        return self.workspace_request_item(actor,id)

    def workspace_views(self,actor,payload=None,id=None,delete=False):
        self.require_module(actor,None,'workspace','view')
        if payload is not None:
            self.require(isinstance(payload,dict));name=str(payload.get('name','')).strip();self.require(0<len(name)<=100,'نام نما لازم است.');p={k:str(payload.get(k,''))[:200] for k in ('company','status','category','q','assignee')}
            if p['company']:self.desk_company(actor,p['company'])
            with self.db(True) as c:
                if id:self.require(c.execute('SELECT 1 FROM workspace_views WHERE id=? AND user_id=?',(id,actor['id'])).fetchone())
                else:id=uid()
                c.execute('INSERT INTO workspace_views VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,payload=excluded.payload',(id,actor['id'],name,dump(p),now()))
        if delete:
            with self.db(True) as c:c.execute('DELETE FROM workspace_views WHERE id=? AND user_id=?',(id,actor['id']))
        with self.db() as c:return [dict(r,payload=json.loads(r['payload'])) for r in c.execute('SELECT * FROM workspace_views WHERE user_id=? ORDER BY created',(actor['id'],))]

    def workspace_save(self,actor,kind,target):
        self.require(kind in ('record','message'))
        if kind=='record':self.require(self.readable(actor,self.record(target)))
        else:r=self.chat_message(actor,target);self.require(not r['deleted'])
        with self.db(True) as c:
            old=c.execute('SELECT 1 FROM workspace_saved WHERE user_id=? AND kind=? AND target=?',(actor['id'],kind,target)).fetchone()
            if old:c.execute('DELETE FROM workspace_saved WHERE user_id=? AND kind=? AND target=?',(actor['id'],kind,target))
            else:c.execute('INSERT INTO workspace_saved VALUES(?,?,?,?)',(actor['id'],kind,target,now()))
        return {'saved':not bool(old)}

    def workspace_search(self,actor,q='',limit=50):
        q=clean(q);self.require(len(q)<=200);limit=max(1,min(int(limit),100));items=[]
        for r in self.list_records(actor,q=q,limit=limit)['items']:items.append(dict(kind='record',id=r['id'],title=r['title'],company=r['company_id'],type=r['kind']))
        if q:
            for n in self.desk_snapshot(actor)['notes']:
                if q in clean(n['title']+' '+n['body']):items.append(dict(kind='note',id=n['id'],title=n['title']))
        return items[:limit]

    def workspace_today(self,actor):
        self.require_module(actor,None,'workspace','view');tasks=self.all_visible(actor,'task');today=date.today();items=[]
        with self.db() as c:saved={r[0] for r in c.execute("SELECT target FROM workspace_saved WHERE user_id=? AND kind='record'",(actor['id'],))}
        for r in tasks:
            p=r['payload'];due=parse_j(p['due_date']).togregorian();mine=p.get('assignee_id')==actor['id'] or (r['private'] and r['owner_id']==actor['id']);review=p.get('status')=='review' and self.writable(actor,r) and (not p.get('reviewer_id') or p['reviewer_id']==actor['id'] or self.desk_manager(actor,r['company_id']))
            r=dict(r,saved=r['id'] in saved,mine=mine,review=review,overdue=due<today and p.get('status') not in ('completed','submitted'),due_today=due==today)
            items.append(r)
        desk=self.desk_snapshot(actor);requests=self.workspace_requests(actor);meetings=[]
        with self.db() as c:rows=[dict(r,payload=json.loads(r['payload'])) for r in c.execute("SELECT * FROM chat_messages WHERE kind='meeting' AND deleted=0 ORDER BY created DESC")]
        for m in rows:
            try:
                self.room_access(actor,m['company_id'],m['room']);at=datetime.fromisoformat(m['payload']['at'])
                if datetime.now(timezone.utc)<=at<=datetime.now(timezone.utc)+timedelta(days=7):meetings.append(dict(id=m['id'],company=m['company_id'],room=m['room'],title=m['text'],at=m['payload']['at']))
            except Exception:continue
        return dict(tasks=items,notes=desk['notes'],leaves=desk['leaves'],incoming=desk['incoming'],requests=requests,meetings=sorted(meetings,key=lambda m:m['at']),notifications=self.workspace_notifications(actor),views=self.workspace_views(actor),revision=self.revision())

    def workspace_leave_balance(self,actor,company,year,user=None):
        user=user or actor['id'];self.desk_company(actor,company);self.require_module(actor,company,'attendance','view');self.require(user==actor['id'] or self.desk_manager(actor,company));self.require(self.role(self.user(user),company) is not None);year=int(normalize(year));self.require(1300<=year<=1499,'سال معتبر نیست.');first=jdatetime.date(year,1,1).togregorian();end=jdatetime.date(year+1,1,1).togregorian();policy=self.workspace_policy(actor,company,'leave')['value'];person=policy.get('people',{}).get(user,{});years=person.get('years');entry=years.get(str(year),{}) if years is not None else person;configured='annual_hours' in entry;daily=decimal(person.get('daily_hours',policy.get('daily_hours',8)),24);annual=decimal(entry.get('annual_hours',0),10000);opening=decimal(entry.get('opening_hours',0),10000);days=set(policy.get('working_days',[0,1,2,5,6]));used={};pending={}
        with self.db() as c:rows=[dict(r,payload=json.loads(r['payload'])) for r in c.execute("SELECT * FROM desk_leaves WHERE company_id=? AND requester_id=? AND status IN ('approved','pending') AND deleted=0",(company,user))]
        from occasions import on_date
        for r in rows:
            p=r['payload'];kind=p['leave_type']
            if kind not in ('استحقاقی','ساعتی'):continue
            a=max(first,parse_j(p['start_date']).togregorian());b=min(end-timedelta(days=1),parse_j(p['end_date']).togregorian());target=used if r['status']=='approved' else pending
            while a<=b:
                if a.weekday() in days and (not policy.get('exclude_holidays',True) or not any(x['holiday'] for x in on_date(a))):
                    # Interval union avoids deducting overlapping approved requests twice.
                    intervals=target.setdefault(a,[])
                    if kind=='ساعتی':
                        x=datetime.strptime(p['start_time'],'%H:%M');y=datetime.strptime(p['end_time'],'%H:%M');intervals.append((x.hour*60+x.minute,y.hour*60+y.minute))
                    else:intervals.append((0,int(daily*60)))
                a+=timedelta(days=1)
        def total(values):
            amount=Decimal(0)
            for intervals in values.values():
                merged=[]
                for a,b in sorted(intervals):
                    if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
                    else:merged.append((a,b))
                amount+=min(daily,sum((Decimal(b-a)/60 for a,b in merged),Decimal(0)))
            return amount
        taken=total(used);waiting=total(pending)
        return dict(user=user,year=year,configured=configured,annual=str(annual),opening=str(opening),used=str(taken),pending=str(waiting),remaining=str(annual+opening-taken) if configured else None,policy=policy,holidays_verified_through=1405)

    def workspace_workload(self,actor,company,month):
        self.desk_company(actor,company);self.require_module(actor,company,'workspace','view');self.require(self.desk_manager(actor,company),'نمای ظرفیت کارکنان مخصوص مدیران است.');first=parse_j(normalize(month)+'/01');last=(jdatetime.date(first.year+1,1,1) if first.month==12 else jdatetime.date(first.year,first.month+1,1)).togregorian();start=first.togregorian();policy=self.workspace_policy(actor,company,'capacity')['value'];people=[u for u in self.users(actor) if u.get('active') and self.role(u,company)];tasks=self.all_visible(actor,'task',company)
        with self.db() as c:leaves=[dict(r,payload=json.loads(r['payload'])) for r in c.execute("SELECT * FROM desk_leaves WHERE company_id=? AND status='approved' AND deleted=0",(company,))]
        from occasions import on_date
        result=[];unassigned=[t for t in tasks if not t['payload'].get('assignee_id') and start<=parse_j(t['payload']['due_date']).togregorian()<last and t['payload'].get('status') not in ('completed','submitted')]
        for u in people:
            daily=decimal(policy.get('people',{}).get(u['id'],{}).get('daily_hours',policy.get('daily_hours',8)),24);cells=[];d=start
            while d<last:
                cap=daily if d.weekday() in policy.get('working_days',[0,1,2,5,6]) and (not policy.get('exclude_holidays',True) or not any(x['holiday'] for x in on_date(d))) else Decimal(0);absence=Decimal(0)
                for leave in leaves:
                    p=leave['payload']
                    if leave['requester_id']==u['id'] and parse_j(p['start_date']).togregorian()<=d<=parse_j(p['end_date']).togregorian():absence+=decimal(p.get('hours')) if p.get('leave_type')=='ساعتی' else daily
                assigned=[t for t in tasks if t['payload'].get('assignee_id')==u['id'] and parse_j(t['payload']['due_date']).togregorian()==d and t['payload'].get('status') not in ('completed','submitted')];hours=sum((decimal(t['payload'].get('estimate_hours',1),744) for t in assigned),Decimal(0));available=max(Decimal(0),cap-absence);cells.append(dict(date=jformat(jdatetime.date.fromgregorian(date=d)),capacity=str(available),hours=str(hours),leave=str(min(cap,absence)),tasks=[dict(id=t['id'],title=t['title']) for t in assigned],overloaded=hours>available));d+=timedelta(days=1)
            result.append(dict(user=u['id'],name=u['fullname'],days=cells,total_hours=str(sum((Decimal(x['hours']) for x in cells),Decimal(0))),total_capacity=str(sum((Decimal(x['capacity']) for x in cells),Decimal(0)))))
        return dict(month=month,people=result,unassigned=unassigned,policy=policy)

    def workspace_attendance_issues(self,actor,company,month):
        self.desk_company(actor,company);self.require_module(actor,company,'attendance','view');self.require(self.desk_manager(actor,company));first=parse_j(normalize(month)+'/01');month=jformat(first)[:7];rows=self.all_visible(actor,'attendance',company);people=self.all_visible(actor,'employee',company);issues=[];by={};policy=self.workspace_policy(actor,company,'attendance')['value'];today=date.today()
        for r in rows:
            p=r['payload']
            try:record_day=jformat(parse_j(p.get('date','')))
            except ValueError:continue
            if not record_day.startswith(month):continue
            key=(p.get('employee_code'),record_day);by.setdefault(key,[]).append(r);reasons=[]
            if not p.get('check_in') or not p.get('check_out'):reasons.append('ورود یا خروج ناقص')
            if p.get('status')!='approved':reasons.append('نیازمند بررسی')
            if reasons:issues.append(dict(id=r['id'],code=key[0],date=key[1],reason='، '.join(reasons),title=r['title']))
        for (code,day),items in by.items():
            if len(items)>1:issues.append(dict(id=items[0]['id'],code=code,date=day,reason='چند ردیف برای یک روز؛ بررسی شیفت / تکرار',title=items[0]['title']))
        from occasions import on_date
        next_month=jdatetime.date(first.year+1,1,1) if first.month==12 else jdatetime.date(first.year,first.month+1,1)
        for person in people:
            p=person['payload'];d=first.togregorian()
            while d<min(next_month.togregorian(),today+timedelta(days=1)):
                day=jformat(jdatetime.date.fromgregorian(date=d))
                personal=policy.get('people',{}).get(p.get('user_id',''),{});specific=personal.get('exceptions',{}).get(day);company_exception=policy.get('exceptions',{}).get(day);shift=specific or company_exception or personal.get('week',{}).get(str(d.weekday())) or policy['week'][str(d.weekday())];holiday=policy.get('exclude_official_holidays',True) and any(x['holiday'] for x in on_date(d));working=shift['working'] and (not holiday or bool(specific or company_exception))
                if working and (p['employee_code'],day) not in by:issues.append(dict(id='',code=p['employee_code'],date=day,reason='تردد ثبت نشده؛ غیبت قطعی محسوب نمی‌شود',title=p['title']))
                d+=timedelta(days=1)
        return issues

    def workspace_trash(self,actor,kind=None,id=None,version=None,restore=False,purge=False,company=None):
        from org_store import DomainError
        limit=datetime.now(timezone.utc)-timedelta(days=30)
        self.require(not (restore and purge),'فقط یکی از عملیات را انتخاب کنید.')
        if kind=='group' and (restore or purge):
            with self.db() as c:row=c.execute('SELECT * FROM workspace_room_archive WHERE company_id=? AND room=?',(company,id)).fetchone();self.require(bool(row),'گروه پیدا نشد.');row=dict(row)
            if restore:return self.workspace_restore_group(actor,row['company_id'],id)
            self.require_module(actor,company,'chat','delete');self.desk_company(actor,company)
            from chat_store import ROOMS
            legacy=id in ROOMS
            self.require(self.desk_manager(actor,company) if legacy else self.chat_group_manage(actor,company,id),'فقط مدیر یا سازنده گروه می‌تواند گروه را حذف کند.')
            moved=[]
            try:
                with self.db(True) as c:
                    self.require(legacy or bool(c.execute('SELECT 1 FROM workspace_groups WHERE company_id=? AND room=?',(company,id)).fetchone()),'گروه پیدا نشد.')
                    messages='SELECT id FROM chat_messages WHERE company_id=? AND room=?';scope=(company,id)
                    for file in c.execute('SELECT id FROM chat_files WHERE message_id IN ('+messages+')',scope).fetchall():
                        fid=file['id'];self.require(bool(re.fullmatch(r'[0-9a-f]{32}',fid)),'شناسه پیوست معتبر نیست.')
                        original=self.files/(fid+'.bin');staged=self.files/(fid+'.purging-'+uid())
                        if original.exists():original.replace(staged);moved.append((original,staged))
                    for table in ('chat_files','chat_likes','chat_votes','chat_meeting_receipts','workspace_message_trash','workspace_sends','workspace_chat'):
                        c.execute('DELETE FROM '+table+' WHERE message_id IN ('+messages+')',scope)
                    c.execute("DELETE FROM workspace_saved WHERE kind='message' AND target IN ("+messages+')',scope)
                    c.execute("DELETE FROM workspace_notifications WHERE target IN (SELECT 'message:'||id FROM chat_messages WHERE company_id=? AND room=?)",scope)
                    c.execute('DELETE FROM chat_messages WHERE company_id=? AND room=?',scope)
                    c.execute('DELETE FROM workspace_group_details WHERE room=?',(id,))
                    for table in ('workspace_group_members','workspace_room_archive','chat_reads','chat_scheduled','workspace_group_requests','workspace_groups'):
                        c.execute('DELETE FROM '+table+' WHERE company_id=? AND room=?',scope)
                    self.audit(c,actor,company,id,'trash_purge',after={'kind':'group'})
            except Exception:
                for original,staged in reversed(moved):
                    if staged.exists():staged.replace(original)
                raise
            for _,staged in moved:
                try:staged.unlink(missing_ok=True)
                except OSError:raise DomainError('گروه حذف شد، اما پاک‌کردن فایل موقت پیوست کامل نشد؛ دسترسی پوشه فایل‌های مرکز را بررسی کنید.',500) from None
            return {'ok':True}
        if kind=='message' and (restore or purge):
            moved=[]
            try:
                with self.db(True) as c:
                    row=c.execute('SELECT * FROM workspace_message_trash WHERE message_id=? AND user_id=?',(id,actor['id'])).fetchone();self.require(bool(row),'پیام پیدا نشد.');row=dict(row);self.room_access(actor,row['company_id'],row['room']);self.require_module(actor,row['company_id'],'chat','delete')
                    if restore:
                        self.require(datetime.fromisoformat(row['deleted_at'])>=limit,'مهلت بازیابی تمام شده است.');c.execute('UPDATE chat_messages SET deleted=0,text=?,payload=? WHERE id=? AND deleted=1',(row['text'],row['payload'],id))
                    else:
                        for attachment in c.execute('SELECT id FROM chat_files WHERE message_id=?',(id,)).fetchall():
                            fid=attachment['id'];self.require(bool(re.fullmatch(r'[0-9a-f]{32}',fid)),'شناسه فایل معتبر نیست.')
                            original=self.files/(fid+'.bin');staged=self.files/(fid+'.purging-'+uid())
                            if original.exists():original.replace(staged);moved.append((original,staged))
                        c.execute('DELETE FROM chat_files WHERE message_id=?',(id,));c.execute('DELETE FROM chat_likes WHERE message_id=?',(id,));c.execute('DELETE FROM chat_votes WHERE message_id=?',(id,));c.execute('DELETE FROM chat_meeting_receipts WHERE message_id=?',(id,))
                    c.execute('DELETE FROM workspace_message_trash WHERE message_id=?',(id,));self.audit(c,actor,row['company_id'],id,'chat_trash_restore' if restore else 'chat_trash_purge',after={'room':row['room']})
            except Exception:
                for original,staged in reversed(moved):
                    if staged.exists():staged.replace(original)
                raise
            for _,staged in moved:
                try:staged.unlink(missing_ok=True)
                except OSError:raise DomainError('پیام پاک شد، اما فایل موقت پیوست حذف نشد؛ دسترسی پوشه فایل‌های مرکز شرکت را بررسی کنید.',500) from None
            return {'ok':True}
        if kind=='product' and (purge or restore):
            with self.db(True) as c:
                row=c.execute('SELECT * FROM stock_products WHERE id=? AND active=0',(id,)).fetchone();self.require(bool(row),'کالای بایگانی‌شده پیدا نشد.');row=dict(row);self.require_module(actor,row['company_id'],'clients','delete')
                if int(version or 0)!=row['version']:raise DomainError('کالا تغییر کرده است.',409)
                if purge:
                    linked=any(any(line.get('product_id')==id for line in json.loads(invoice['payload']).get('lines',[])) for invoice in c.execute("SELECT payload FROM records WHERE kind='invoice' AND company_id=?",(row['company_id'],)))
                    linked=linked or bool(c.execute('SELECT 1 FROM stock_movements WHERE product_id=?',(id,)).fetchone()) or bool(c.execute('SELECT 1 FROM stock_request_ids WHERE product_id=?',(id,)).fetchone())
                    self.require(not linked,'این کالا سابقه فاکتور یا گردش دارد و برای حفظ سوابق قابل حذف دائمی نیست.');c.execute('DELETE FROM stock_products WHERE id=?',(id,));self.audit(c,actor,row['company_id'],id,'trash_purge',after={'kind':'product'})
                else:c.execute('UPDATE stock_products SET active=1,version=version+1 WHERE id=?',(id,));self.audit(c,actor,row['company_id'],id,'trash_restore',after={'kind':'product'})
            return {'ok':True}
        if purge:
            self.require(not restore and kind in ('record','note'),'عملیات معتبر نیست.')
            with self.db(True) as c:
                table='records' if kind=='record' else 'desk_notes';entry=c.execute('SELECT * FROM '+table+' WHERE id=? AND deleted=1',(id,)).fetchone();self.require(bool(entry),'مورد حذف‌شده پیدا نشد.');row=dict(entry)
                if int(version or 0)!=row['version']:raise DomainError('مورد تغییر کرده است.',409)
                if kind=='note':self.require_module(actor,None,'desk','delete');self.require(row['user_id']==actor['id'])
                else:
                    row['payload']=json.loads(row['payload']);self.require(self.writable(actor,row,'delete'))
                    self.require(not c.execute('SELECT 1 FROM workspace_invoice_requests WHERE record_id=?',(id,)).fetchone(),'این پرونده شناسه ثبت دستیار دارد و برای حفظ سابقه ثبت تکراری قابل حذف دائمی نیست.')
                    if row['kind']=='invoice':
                        linked=c.execute('SELECT 1 FROM finance_allocations WHERE invoice_id=?',(id,)).fetchone() or c.execute('SELECT 1 FROM finance_check WHERE invoice_id=?',(id,)).fetchone() or c.execute('SELECT 1 FROM finance_check_transfers WHERE invoice_id=?',(id,)).fetchone() or c.execute('SELECT 1 FROM workspace_invoice_requests WHERE record_id=?',(id,)).fetchone()
                        self.require(not linked,'این فاکتور سند یا چک مرتبط دارد و حذف دائمی آن مجاز نیست.')
                    if row['kind']=='client':
                        linked=any(json.loads(item['payload']).get('client_id')==id for item in c.execute("SELECT payload FROM records WHERE kind IN ('invoice','tax_job')")) or c.execute('SELECT 1 FROM finance_transactions WHERE customer_id=?',(id,)).fetchone() or c.execute('SELECT 1 FROM finance_check_transfers WHERE recipient_id=?',(id,)).fetchone()
                        self.require(not linked,'این طرف حساب سابقه مالی مرتبط دارد و حذف دائمی آن مجاز نیست.')
                    self.require(not c.execute('SELECT 1 FROM files WHERE record_id=?',(id,)).fetchone(),'این پرونده مدرک پیوست دارد و حذف دائمی آن نیاز به بررسی دارد.')
                    c.execute('DELETE FROM comments WHERE record_id=?',(id,));c.execute('DELETE FROM receipts WHERE record_id=?',(id,))
                c.execute('DELETE FROM workspace_saved WHERE kind=? AND target=?',(kind,id));c.execute('DELETE FROM '+table+' WHERE id=?',(id,));self.audit(c,actor,row.get('company_id'),id,'trash_purge',after={'kind':kind})
            return {'ok':True}
        if restore:
            self.require(kind in ('record','note'))
            with self.db(True) as c:
                table='records' if kind=='record' else 'desk_notes';row=c.execute('SELECT * FROM '+table+' WHERE id=? AND deleted=1',(id,)).fetchone();self.require(bool(row),'مورد حذف‌شده پیدا نشد.');row=dict(row)
                if kind=='record':row['payload']=json.loads(row['payload']);self.require(self.writable(actor,row,'delete'))
                else:self.require_module(actor,None,'desk','delete');self.require(row['user_id']==actor['id'])
                self.require(datetime.fromisoformat(row['updated'])>=limit,'مهلت بازیابی ۳۰ روزه تمام شده است.')
                if int(version or 0)!=row['version']:raise DomainError('مورد تغییر کرده است.',409)
                if kind=='record' and row['kind']=='invoice':
                    self.inventory_invoice_change(c,actor,row['company_id'],id,row['payload'],row['payload'],before_deleted=True)
                    self.finance_invoice_change(c,actor,row['company_id'],id,row['payload'])
                c.execute('UPDATE '+table+' SET deleted=0,version=version+1,updated=? WHERE id=?',(now(),id));self.audit(c,actor,row.get('company_id'),id,'trash_restore',after={'kind':kind})
            return {'ok':True}
        with self.db() as c:
            notes=[dict(r,trash_kind='note') for r in c.execute('SELECT * FROM desk_notes WHERE user_id=? AND deleted=1',(actor['id'],))] if self.module_permission(actor,None,'desk','delete') else [];rows=[dict(r,payload=json.loads(r['payload']),trash_kind='record') for r in c.execute('SELECT * FROM records WHERE deleted=1')]
            products=[dict(r,trash_kind='product',title=r['name'],updated=r['deleted_at'] or '') for r in c.execute("SELECT p.*, (SELECT MAX(a.created) FROM audit a WHERE a.target=p.id AND a.action='archive') AS deleted_at FROM stock_products p WHERE p.active=0")]
            messages=[dict(r,trash_kind='message',id=r['message_id'],title=r['text'][:80] or 'پیام پیوست‌دار',updated=r['deleted_at'],version=1) for r in c.execute('SELECT * FROM workspace_message_trash WHERE user_id=?',(actor['id'],))]
            groups=[dict(r,trash_kind='group',id=r['room'],title=r['title'] or r['room'],updated=r['created'],version=1) for r in c.execute("SELECT a.*,g.title,g.actor AS creator FROM workspace_room_archive a LEFT JOIN workspace_groups g ON a.company_id=g.company_id AND a.room=g.room")]
        visible_messages=[]
        for message in messages:
            try:self.room_access(actor,message['company_id'],message['room']);self.require_module(actor,message['company_id'],'chat','delete');visible_messages.append(message)
            except DomainError:pass
        from chat_store import ROOMS
        for group in groups:group['title']=ROOMS.get(group['room'],group['title'])
        return notes+[r for r in rows if self.readable(actor,r) and self.writable(actor,r,'delete')]+[r for r in products if self.module_permission(actor,r['company_id'],'clients','delete')]+visible_messages+[r for r in groups if (r['creator']==actor['id'] or self.desk_manager(actor,r['company_id'])) and self.module_permission(actor,r['company_id'],'chat','view')]

    def workspace_task_from_message(self,actor,id,payload):
        m=self.chat_message(actor,id);self.require(not m['deleted']);p=dict(payload);company=p.pop('company_id',None) if m['company_id']=='__shared_chat__' else m['company_id']
        self.require(bool(company) and company!='__shared_chat__','شرکت مربوط به کار را انتخاب کنید.')
        p.update(source_message=id,source_room=m['room'],reference='chat:'+id);return self.save_record(actor,'task',p,company)

    def chat_send(self,actor,company,room,text='',kind='text',payload=None,attachments=None,reply_to=None,mentions=None,request_id=None):
        from org_store import DomainError
        self.room_access(actor,company,room);self.require_module(actor,company,'chat','send')
        if attachments:self.require_module(actor,company,'chat','attach')
        if kind in ('meeting','poll'):self.require_module(actor,company,'chat','meeting')
        mentions=mentions or [];self.require(isinstance(mentions,list) and len(mentions)<=100);people=self.room_people(actor,company,room);allowed={u['id'] for u in people};self.require(all(x in allowed for x in mentions),'فرد اشاره‌شده باید عضو گروه باشد.');root=None
        if reply_to:
            reply=self.chat_message(actor,reply_to);self.require(not reply['deleted'] and reply['company_id']==company and reply['room']==room,'پیام پاسخ باید در همین گروه باشد.')
            with self.db() as c:meta=c.execute('SELECT root FROM workspace_chat WHERE message_id=?',(reply_to,)).fetchone()
            root=(meta['root'] if meta else None) or reply_to
        if request_id:self.require(bool(re.fullmatch(r'[a-zA-Z0-9-]{16,80}',str(request_id))),'شناسه ارسال معتبر نیست.')
        request_digest=hashlib.sha256(dump(dict(company=company,room=room,text=text,kind=kind,payload=payload or {},attachments=attachments or [],reply_to=reply_to,mentions=mentions)).encode('utf-8')).hexdigest()
        def duplicate():
            with self.db() as c:previous=c.execute('SELECT m.id,m.seq,s.digest FROM workspace_sends s JOIN chat_messages m ON m.id=s.message_id WHERE s.user_id=? AND s.request_id=?',(actor['id'],request_id)).fetchone()
            if not previous:return None
            if previous['digest']!=request_digest:raise DomainError('شناسه ارسال قبلاً برای پیام دیگری استفاده شده است.',409)
            return dict(id=previous['id'],seq=previous['seq'],duplicate=True)
        # The host lock covers send+dedup record. Lost responses can be retried safely.
        with self.lock:
            if request_id:
                previous=duplicate()
                if previous:return previous
            with self.db() as c:users={r['username'].casefold():r['id'] for r in c.execute('SELECT id,username FROM users WHERE active=1')}
            mentions=list(dict.fromkeys(mentions+[users[name.casefold()] for name in re.findall(r'@([A-Za-z][A-Za-z0-9._-]{2,63})',str(text)) if users.get(name.casefold()) in allowed]))
            try:value=super().chat_send(actor,company,room,text,kind,payload,attachments,_delivery=dict(reply_to=reply_to,root=root,mentions=mentions,request_id=request_id,digest=request_digest))
            except sqlite3.IntegrityError:
                # Separate Store instances can share the same database. In that
                # case the uniqueness constraint is the final arbiter of races.
                previous=duplicate() if request_id else None
                if not previous:raise
                return previous
        return value

    def chat_list(self,actor,company,room,before=None,limit=50,q='',thread=None,saved=False,pinned=False):
        self.room_access(actor,company,room);limit=max(1,min(int(limit),100));query=clean(q)
        if query or thread or saved or pinned:
            if thread:
                root=self.chat_message(actor,thread);self.require(root['company_id']==company and root['room']==room)
            data=super().chat_list(actor,company,room,before,100);selected=[];cursor=before
            while True:
                for m in reversed(data['items']):
                    with self.db() as c:
                        meta=c.execute('SELECT * FROM workspace_chat WHERE message_id=?',(m['id'],)).fetchone();mark=c.execute("SELECT 1 FROM workspace_saved WHERE user_id=? AND kind='message' AND target=?",(actor['id'],m['id'])).fetchone()
                    if thread and not (m['id']==thread or meta and meta['root']==thread):continue
                    if saved and not mark:continue
                    if pinned and not (meta and meta['pinned']):continue
                    if query and query not in clean(m['text']+' '+' '.join(f['name'] for f in m['files'])):continue
                    selected.append(m)
                    if len(selected)>=limit+1:break
                if len(selected)>limit or not data['has_more'] or not data['items']:break
                data=super().chat_list(actor,company,room,data['items'][0]['seq'],100)
            result=dict(data,items=list(reversed(selected[:limit])),has_more=len(selected)>limit)
        else:result=super().chat_list(actor,company,room,before,limit)
        with self.db() as c:
            for m in result['items']:
                meta=c.execute('SELECT * FROM workspace_chat WHERE message_id=?',(m['id'],)).fetchone();m['thread_root']=(meta['root'] if meta else None) or m['id'];m['reply_to']=meta['reply_to'] if meta else None;m['pinned']=bool(meta and meta['pinned']);m['saved']=bool(c.execute("SELECT 1 FROM workspace_saved WHERE user_id=? AND kind='message' AND target=?",(actor['id'],m['id'])).fetchone());m['mentions']=json.loads(meta['mentions']) if meta else [];m['reply_count']=c.execute('SELECT COUNT(*) FROM workspace_chat x JOIN chat_messages m ON m.id=x.message_id WHERE x.root=? AND m.deleted=0',(m['id'],)).fetchone()[0]
                if m['reply_to']:
                    reply=c.execute('SELECT text,deleted FROM chat_messages WHERE id=?',(m['reply_to'],)).fetchone();m['reply_excerpt']=reply['text'][:100] if reply and not reply['deleted'] else 'پیام حذف‌شده'
        return result

    def chat_action(self,actor,id,action,option=None):
        message=self.chat_message(actor,id);self.require_module(actor,message['company_id'],'chat',{'like':'react','like_set':'react','vote':'react','delete':'delete','pin':'pin'}.get(action,'view'))
        if action=='delete':
            self.require(not message['deleted'],'پیام حذف شده است.');self.require(message['author']==actor['id'] or actor['global_role'] in ('group_admin','system_admin') or self.role(actor,message['company_id'])=='company_manager')
            with self.db(True) as c:
                c.execute('INSERT OR REPLACE INTO workspace_message_trash VALUES(?,?,?,?,?,?,?)',(id,actor['id'],message['company_id'],message['room'],message['text'],message['payload'],now()));c.execute("UPDATE chat_messages SET deleted=1,text='',payload='{}' WHERE id=?",(id,));self.audit(c,actor,message['company_id'],id,'chat_delete',after={'room':message['room']})
            return {'ok':True}
        if action not in ('save','pin'):return super().chat_action(actor,id,action,option)
        if action=='save':return self.workspace_save(actor,'message',id)
        m=self.chat_message(actor,id);self.require(not m['deleted'] and (m['room'].startswith(('dm:','saved:')) or self.desk_manager(actor,m['company_id'])),'سنجاق پیام با مدیر شرکت است.')
        with self.db(True) as c:
            c.execute("INSERT OR IGNORE INTO workspace_chat(message_id) VALUES(?)",(id,));c.execute('UPDATE workspace_chat SET pinned=1-pinned WHERE message_id=?',(id,));self.audit(c,actor,m['company_id'],id,'chat_pin')
        return {'ok':True}
