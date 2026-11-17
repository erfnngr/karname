"""Company data lives on one host; every operation enforces server-side scope."""
import base64,copy,hashlib,hmac,json,os,secrets,sqlite3,threading,time,uuid,re
from pathlib import Path
from datetime import datetime,timezone,date,timedelta
from decimal import Decimal
from contextlib import contextmanager
from org_schema import SCHEMAS,ROLES,MANAGERS,APPROVERS,STATUSES
from storage import parse_j,normalize
from chat_store import ChatStoreMixin,init_chat
from desk_store import DeskStoreMixin,init_desk
from workspace_store import WorkspaceStoreMixin,init_workspace
from inventory_store import InventoryStoreMixin,init_inventory
from finance_store import FinanceStoreMixin,init_finance
from permission_policy import allowed as module_allowed,any_allowed,validate_overrides

def public_record_data(actor,record):
    """Remove settlement and margin details when finance access is absent."""
    result=copy.deepcopy(record);payload=result.get('payload',{})
    if result.get('kind')=='notice' and actor['id']!=result.get('owner_id'):payload.pop('recipients',None)
    if result.get('kind')=='invoice' and not module_allowed(actor,result.get('company_id'),'finance','view'):
        payload.pop('settlement',None);payload.pop('settlement_summary',None)
        seller=payload.get('seller_snapshot')
        if isinstance(seller,dict):seller.pop('account_no',None);seller.pop('iban',None)
        for line in payload.get('lines',[]):
            if isinstance(line,dict):line.pop('unit_cost_snapshot',None);line.pop('gross_profit',None)
    return result

def record_module(kind):
    return {'task':'workspace','attendance':'attendance','employee':'attendance','payroll_batch':'payroll','proposal':'news','client':'clients','invoice':'clients','tax_job':'clients','tax_case':'tax','insurance_workshop':'tax','insurance_employee':'payroll','insurance_list':'payroll','insurance_rules':'payroll'}.get(kind,'company')

def record_action(kind,action):
    module=record_module(kind)
    if module=='payroll':return {'view':'view','create':'create','edit':'create','delete':'create'}.get(action,action)
    if module=='news':return 'view' if action=='view' else 'propose'
    if module=='attendance' and action=='delete':return 'edit'
    if kind=='invoice' and action in ('create','edit'):return 'invoice'
    return action

def stamp():return datetime.now(timezone.utc).isoformat(timespec='seconds')
def uid():return uuid.uuid4().hex
def packed(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def password_hash(password,salt=None):
    if not isinstance(password,str) or not password or len(password)>1000:raise DomainError('رمز عبور را وارد کنید؛ حداکثر ۱۰۰۰ نویسه.')
    salt=salt or secrets.token_bytes(16)
    return base64.b64encode(salt).decode()+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt,350000).hex()
def password_ok(password,stored):
    try:
        salt,digest=stored.split(':');actual=hashlib.pbkdf2_hmac('sha256',password.encode(),base64.b64decode(salt),350000).hex();return hmac.compare_digest(actual,digest)
    except (ValueError,TypeError):return False

class DomainError(Exception):
    def __init__(self,message,status=400):super().__init__(message);self.status=status

class Store(FinanceStoreMixin,InventoryStoreMixin,WorkspaceStoreMixin,ChatStoreMixin,DeskStoreMixin):
    def __init__(self,folder):
        self.root=Path(folder);self.root.mkdir(parents=True,exist_ok=True);self.files=self.root/'files';self.files.mkdir(exist_ok=True);self.path=self.root/'company.sqlite';self.lock=threading.RLock()
        with self.db() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,username TEXT UNIQUE COLLATE NOCASE,fullname TEXT,password TEXT,global_role TEXT DEFAULT 'employee',active INTEGER DEFAULT 1,created TEXT);
            CREATE TABLE IF NOT EXISTS companies(id TEXT PRIMARY KEY,name TEXT UNIQUE,created TEXT);
            CREATE TABLE IF NOT EXISTS memberships(user_id TEXT REFERENCES users(id),company_id TEXT REFERENCES companies(id),role TEXT,department TEXT DEFAULT '',permissions TEXT DEFAULT '{}',PRIMARY KEY(user_id,company_id));
            CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),expires REAL);
            CREATE TABLE IF NOT EXISTS login_limits(username TEXT PRIMARY KEY,failures INTEGER,blocked_until REAL);
            CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,kind TEXT,company_id TEXT REFERENCES companies(id),owner_id TEXT REFERENCES users(id),private INTEGER DEFAULT 0,department TEXT DEFAULT '',title TEXT,payload TEXT,version INTEGER DEFAULT 1,created TEXT,updated TEXT,deleted INTEGER DEFAULT 0);
            CREATE INDEX IF NOT EXISTS records_scope ON records(company_id,kind,deleted);
            CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY,record_id TEXT REFERENCES records(id),name TEXT,sha256 TEXT,size INTEGER,mime TEXT,version INTEGER,created TEXT,author TEXT REFERENCES users(id),extracted TEXT DEFAULT '');
            CREATE TABLE IF NOT EXISTS comments(id TEXT PRIMARY KEY,record_id TEXT REFERENCES records(id),author TEXT REFERENCES users(id),text TEXT,created TEXT);
            CREATE TABLE IF NOT EXISTS receipts(record_id TEXT REFERENCES records(id),user_id TEXT REFERENCES users(id),delivered TEXT,opened TEXT,acknowledged TEXT,PRIMARY KEY(record_id,user_id));
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT,company_id TEXT,target TEXT,action TEXT,before_json TEXT,after_json TEXT,reason TEXT,created TEXT);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
            CREATE TABLE IF NOT EXISTS automation_runs(rule_id TEXT,target TEXT,day TEXT,PRIMARY KEY(rule_id,target,day));
            CREATE TABLE IF NOT EXISTS user_birthdays(user_id TEXT PRIMARY KEY REFERENCES users(id),birth_year INTEGER,birth_month INTEGER,birth_day INTEGER,missing_policy TEXT DEFAULT 'last_day_of_month',updated TEXT);
            CREATE TABLE IF NOT EXISTS birthday_reminders(id TEXT PRIMARY KEY,birthday_user_id TEXT NOT NULL REFERENCES users(id),recipient_id TEXT NOT NULL REFERENCES users(id),birthday_year INTEGER NOT NULL,birthday_date_j TEXT NOT NULL,target_g TEXT NOT NULL,title TEXT NOT NULL,body TEXT NOT NULL,cancelled INTEGER DEFAULT 0,shown TEXT,opened TEXT,created TEXT,updated TEXT,UNIQUE(birthday_user_id,recipient_id,birthday_year));
            ''')
            columns={r[1] for r in c.execute('PRAGMA table_info(users)')}
            for field in ('first_name','last_name'):
                if field not in columns:c.execute('ALTER TABLE users ADD COLUMN '+field+" TEXT DEFAULT ''")
            for key,name in [('mana','مانا'),('airia','آیریا'),('arka','آرکا')]:c.execute('INSERT OR IGNORE INTO companies VALUES(?,?,?)',(key,name,stamp()))
            c.execute('INSERT OR IGNORE INTO companies VALUES(?,?,?)',('__shared_chat__','فضای مشترک گفتگو',stamp()))
            init_chat(c)
            init_desk(c)
            init_workspace(c)
            init_inventory(c)
            init_finance(c)

    @contextmanager
    def db(self,write=False):
        with self.lock:
            c=sqlite3.connect(self.path,timeout=15);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=15000')
            try:
                if write:c.execute('BEGIN IMMEDIATE')
                yield c;c.commit()
            except Exception:c.rollback();raise
            finally:c.close()

    def revision(self):
        with self.db() as c:return c.execute('SELECT COALESCE(MAX(id),0) FROM audit').fetchone()[0]
    def initialized(self):
        with self.db() as c:return bool(c.execute('SELECT 1 FROM users LIMIT 1').fetchone())
    def audit(self,c,actor,company,target,action,before=None,after=None,reason=''):
        c.execute('INSERT INTO audit(actor,company_id,target,action,before_json,after_json,reason,created) VALUES(?,?,?,?,?,?,?,?)',(actor['id'] if actor else 'system',company,target,action,packed(before),packed(after),reason,stamp()))
    def bootstrap(self,username,password,fullname,first_name='',last_name=''):
        with self.db(True) as c:
            if c.execute('SELECT 1 FROM users').fetchone():raise DomainError('مدیر اولیه قبلاً ساخته شده است.',409)
            user_id=uid();c.execute('INSERT INTO users(id,username,fullname,password,global_role,active,created,first_name,last_name) VALUES(?,?,?,?,?,?,?,?,?)',(user_id,self.clean_username(username),fullname.strip() or username,password_hash(password),'group_admin',1,stamp(),first_name,last_name));self.audit(c,None,None,user_id,'setup')
        return self.user(user_id)
    @staticmethod
    def clean_username(value):
        value=value.strip()
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9._-]{2,63}',value):raise DomainError('نام کاربری با حرف انگلیسی شروع شود و ۳ تا ۶۴ حرف انگلیسی، عدد یا . _ - داشته باشد.')
        return value
    def user(self,user_id):
        with self.db() as c:
            row=c.execute('SELECT id,username,fullname,first_name,last_name,global_role,active FROM users WHERE id=?',(user_id,)).fetchone()
            if not row or not row['active']:raise DomainError('حساب غیرفعال یا نامعتبر است.',401)
            result=dict(row);result['memberships']=[dict(x,permissions=json.loads(x['permissions'])) for x in c.execute('SELECT m.*,c.name AS company_name FROM memberships m JOIN companies c ON c.id=m.company_id WHERE user_id=?',(user_id,))]
        result['profile']=self.own_profile(result);return result
    def login(self,username,password):
        with self.db(True) as c:
            limit=c.execute('SELECT * FROM login_limits WHERE username=?',(username.lower(),)).fetchone()
            if limit and limit['blocked_until']>time.time():raise DomainError('تلاش‌های ناموفق زیاد بود؛ چند دقیقه دیگر امتحان کنید.',429)
            row=c.execute('SELECT * FROM users WHERE username=? COLLATE NOCASE',(username,)).fetchone()
            valid=bool(row and row['active'] and password_ok(password,row['password']))
            if not valid:
                failures=(limit['failures'] if limit else 0)+1;c.execute('INSERT OR REPLACE INTO login_limits VALUES(?,?,?)',(username.lower(),failures,time.time()+300 if failures>=8 else 0));c.commit();raise DomainError('نام کاربری یا رمز عبور درست نیست.',401)
            c.execute('DELETE FROM login_limits WHERE username=?',(username.lower(),));token=secrets.token_urlsafe(36);c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),row['id'],time.time()+12*3600));user_id=row['id']
        return dict(token=token,user=self.user(user_id))
    def authenticate(self,token):
        if not token:raise DomainError('ابتدا وارد شوید.',401)
        with self.db() as c:row=c.execute('SELECT user_id FROM sessions WHERE hash=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        if not row:raise DomainError('نشست پایان یافته است؛ دوباره وارد شوید.',401)
        return self.user(row['user_id'])
    def logout(self,token):
        with self.db(True) as c:c.execute('DELETE FROM sessions WHERE hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
    def role(self,actor,company):
        if actor['global_role']=='group_admin':return 'group_admin'
        if company=='__shared_chat__':
            if actor['global_role']=='system_admin':return 'company_manager'
            if any(m.get('role')=='company_manager' for m in actor.get('memberships',[])):return 'company_manager'
            return 'employee' if actor.get('memberships') else None
        return next((m['role'] for m in actor['memberships'] if m['company_id']==company),None)
    def permission(self,actor,company,area,action='view'):
        if actor['global_role']=='group_admin':return True
        membership=next((m for m in actor['memberships'] if m['company_id']==company),None)
        if not membership:return False
        override=membership.get('permissions',{}).get(area+'.'+action)
        if override is not None:return bool(override)
        role=membership['role']
        if role=='company_manager':return True
        if role=='auditor':return action in ('view','export')
        if role=='finance':return area in ('finance','work') and action!='manage_users'
        if role=='team_lead':return area in ('hr','work') and action!='manage_users'
        return action in ('view','create','edit') and area in ('work','hr')
    def require(self,condition,message='دسترسی این عملیات را ندارید.'):
        if not condition:raise DomainError(message,403)
    def module_permission(self,actor,company,module,action='view'):
        if company=='__shared_chat__':return module=='chat' and any_allowed(actor,module,action)
        return module_allowed(actor,company,module,action) if company else any_allowed(actor,module,action)
    def require_module(self,actor,company,module,action='view'):
        self.require(self.module_permission(actor,company,module,action),'دسترسی این بخش یا عملیات را ندارید.')
    def companies(self,actor):
        with self.db() as c:rows=[dict(x) for x in c.execute("SELECT * FROM companies WHERE id!='__shared_chat__' ORDER BY name")]
        from company_defaults import company_order
        rows.sort(key=lambda row:company_order(row['name']))
        return rows if actor['global_role'] in ('group_admin','system_admin') else [x for x in rows if self.role(actor,x['id'])]
    def create_company(self,actor,name):
        self.require(actor['global_role'] in ('group_admin','system_admin'))
        if not name.strip():raise DomainError('نام شرکت را وارد کنید.')
        with self.db(True) as c:
            id=uid();c.execute('INSERT INTO companies VALUES(?,?,?)',(id,name.strip(),stamp()));self.audit(c,actor,id,id,'create_company',after={'name':name})
        return {'id':id,'name':name.strip()}
    def users(self,actor):
        with self.db() as c:rows=[dict(x) for x in c.execute('SELECT id,username,fullname,first_name,last_name,global_role,active FROM users ORDER BY fullname')]
        if actor['global_role'] in ('group_admin','system_admin'):return [self._with_memberships(row) for row in rows]
        scope={x['id'] for x in self.companies(actor)}
        result=[]
        for row in rows:
            person=self._with_memberships(row);person['memberships']=[m for m in person['memberships'] if m['company_id'] in scope]
            if person['memberships'] or person['id']==actor['id']:result.append(person)
        return result
    def _with_memberships(self,row):
        with self.db() as c:row['memberships']=[dict(x,permissions=json.loads(x['permissions'])) for x in c.execute('SELECT * FROM memberships WHERE user_id=?',(row['id'],))]
        return row
    def save_user(self,actor,payload):
        managed={m['company_id'] for m in actor['memberships'] if m['role']=='company_manager' and module_allowed(actor,m['company_id'],'access','manage')};is_global=actor['global_role'] in ('group_admin','system_admin')
        self.require(is_global or bool(managed));user_id=payload.get('id') or uid();role=payload.get('global_role','employee')
        if role not in ('group_admin','system_admin','employee'):raise DomainError('نقش عمومی معتبر نیست.')
        if actor['global_role']!='group_admin' and role!='employee':raise DomainError('فقط مدیر گروه نقش مدیر کل می‌دهد.',403)
        if user_id==actor['id'] and (not payload.get('active',True) or role!=actor['global_role']):raise DomainError('نقش یا فعالیت حساب فعلی را از حساب مدیر دیگری تغییر دهید.')
        memberships=payload.get('memberships',[])
        for m in memberships:validate_overrides(m.get('permissions',{}))
        if any(m.get('role') not in ROLES or m.get('role') in ('group_admin','system_admin') for m in memberships):raise DomainError('نقش شرکت معتبر نیست.')
        if not is_global:
            self.require(role=='employee' and bool(memberships) and all(m['company_id'] in managed for m in memberships),'مدیر شرکت فقط حساب‌های همان شرکت را مدیریت می‌کند.')
            with self.db() as c:old_scopes=[r[0] for r in c.execute('SELECT company_id FROM memberships WHERE user_id=?',(user_id,))]
            self.require(all(co in managed for co in old_scopes),'این حساب به شرکت‌های دیگری نیز دسترسی دارد؛ مدیر کل باید آن را تغییر دهد.')
        with self.db(True) as c:
            old=c.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone();pw=password_hash(payload['password']) if payload.get('password') else old['password'] if old else None
            if not pw:raise DomainError('برای حساب جدید رمز تعیین کنید.')
            if old and old['global_role']=='group_admin' and user_id!=actor['id']:raise DomainError('حساب مدیر کل توسط حساب دیگری قابل تغییر نیست.',403)
            if old and old['global_role'] in ('group_admin','system_admin') and actor['global_role']!='group_admin':raise DomainError('تغییر مدیر مجاز نیست.',403)
            previous=[dict(x,permissions=json.loads(x['permissions'])) for x in c.execute('SELECT company_id,role,department,permissions FROM memberships WHERE user_id=?',(user_id,))]
            if old and user_id==actor['id']:
                normalized=lambda values:sorted([dict(company_id=m['company_id'],role=m['role'],department=m.get('department',''),permissions=m.get('permissions',{})) for m in values],key=lambda m:m['company_id'])
                self.require(normalized(memberships)==normalized(previous),'سطح دسترسی و عضویت خودتان را مدیر دیگری تغییر می‌دهد.')
            if not is_global:
                for m in memberships:
                    former=next((x['permissions'] for x in previous if x['company_id']==m['company_id']),{})
                    incoming={k:v for k,v in m.get('permissions',{}).items() if not k.startswith('module.')}
                    self.require(incoming=={k:former[k] for k in incoming if k in former},'مجوزهای قدیمی را نمی‌توان از این فرم تغییر داد.')
            first=str(payload.get('first_name',old['first_name'] if old else '')).strip()[:80];last=str(payload.get('last_name',old['last_name'] if old else '')).strip()[:100];fullname=(first+' '+last).strip() or payload.get('fullname','').strip() or payload['username']
            c.execute('INSERT INTO users(id,username,fullname,password,global_role,active,created,first_name,last_name) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET username=excluded.username,fullname=excluded.fullname,password=excluded.password,global_role=excluded.global_role,active=excluded.active,first_name=excluded.first_name,last_name=excluded.last_name',(user_id,self.clean_username(payload['username']),fullname,pw,role,int(payload.get('active',True)),stamp(),first,last))
            c.execute('DELETE FROM memberships WHERE user_id=?',(user_id,))
            for m in memberships:c.execute('INSERT INTO memberships VALUES(?,?,?,?,?)',(user_id,m['company_id'],m['role'],m.get('department',''),packed(m.get('permissions',{}))))
            c.execute('DELETE FROM sessions WHERE user_id=?',(user_id,));self.audit(c,actor,None,user_id,'save_user',after={'username':payload['username'],'role':role,'memberships':memberships})
        return {'id':user_id}
    def save_permissions(self,actor,user_id,company,permissions,expected_permissions=None):
        self.desk_company(actor,company);self.require(actor['global_role']=='group_admin' or self.role(actor,company)=='company_manager');self.require_module(actor,company,'access','manage');self.require(user_id!=actor['id'],'دسترسی حساب خود را مدیر دیگری تغییر می‌دهد.')
        permissions=validate_overrides(permissions)
        with self.db(True) as c:
            user=c.execute('SELECT global_role FROM users WHERE id=? AND active=1',(user_id,)).fetchone();self.require(bool(user),'حساب فعال پیدا نشد.');self.require(user['global_role'] not in ('group_admin','system_admin'),'دسترسی مدیر کل یا فنی از این قسمت قابل تغییر نیست.')
            member=c.execute('SELECT permissions FROM memberships WHERE user_id=? AND company_id=?',(user_id,company)).fetchone();self.require(bool(member),'این حساب عضو شرکت انتخابی نیست.');old=json.loads(member['permissions'])
            if expected_permissions is not None and (not isinstance(expected_permissions,dict) or expected_permissions!=old):raise DomainError('دسترسی این فرد تغییر کرده است؛ درخواست را دوباره ارسال کنید.',409)
            legacy={k:v for k,v in old.items() if not k.startswith('module.')};incoming_legacy={k:v for k,v in permissions.items() if not k.startswith('module.')};self.require(incoming_legacy=={k:legacy[k] for k in incoming_legacy if k in legacy},'دسترسی‌های قدیمی با این فرم قابل تغییر نیستند.');new=dict(legacy,**{k:v for k,v in permissions.items() if k.startswith('module.')});c.execute('UPDATE memberships SET permissions=? WHERE user_id=? AND company_id=?',(packed(new),user_id,company));self.audit(c,actor,company,user_id,'permissions_update',after={'updated':True})
        return {'ok':True}
    def record(self,id):
        with self.db() as c:row=c.execute('SELECT * FROM records WHERE id=? AND deleted=0',(id,)).fetchone()
        if not row:raise DomainError('پرونده پیدا نشد.',404)
        return dict(row,payload=json.loads(row['payload']))
    def readable(self,actor,record):
        p=record['payload']
        if record['kind']=='notice':
            if not any(self.module_permission(actor,co,'company','view') for co in p.get('companies',[])):return False
            if actor['id']==record['owner_id']:return True
            now=datetime.now(timezone.utc)
            active=(not p.get('publish_at') or datetime.fromisoformat(p['publish_at']).astimezone(timezone.utc)<=now) and (not p.get('expires_at') or datetime.fromisoformat(p['expires_at']).astimezone(timezone.utc)>=now)
            return active and actor['id'] in p.get('recipients',[]) and (actor['global_role']=='group_admin' or any(self.role(actor,co) for co in p.get('companies',[])))
        if not self.module_permission(actor,record['company_id'],record_module(record['kind']),'view'):return False
        if record['private']:return actor['id']==record['owner_id']
        kind=record['kind'];area=SCHEMAS.get(kind,{}).get('area','work');role=self.role(actor,record['company_id'])
        if not self.permission(actor,record['company_id'],area):return False
        if role=='employee':
            return record['owner_id']==actor['id'] or p.get('assignee_id')==actor['id'] or p.get('substitute_id')==actor['id'] or p.get('user_id')==actor['id'] or kind in ('knowledge','form','template') or (kind in ('attendance','leave','shift') and self.employee_owned(actor,record['company_id'],p.get('employee_code')))
        if role=='team_lead':
            department=next((m.get('department') for m in actor['memberships'] if m['company_id']==record['company_id']),'')
            return bool(department and department==record.get('department')) or record['owner_id']==actor['id']
        return True
    def employee_owned(self,actor,company,code):
        if not code:return False
        with self.db() as c:
            rows=c.execute("SELECT payload FROM records WHERE kind='employee' AND company_id=? AND deleted=0",(company,)).fetchall()
        return any((p:=json.loads(row[0])).get('employee_code')==code and p.get('user_id')==actor['id'] for row in rows)
    def writable(self,actor,record,action='edit'):
        if not self.readable(actor,record):return False
        if not self.module_permission(actor,record['company_id'],record_module(record['kind']),record_action(record['kind'],action)):return False
        if record['private']:return actor['id']==record['owner_id']
        area=SCHEMAS.get(record['kind'],{}).get('area','work')
        if not self.permission(actor,record['company_id'],area,action):return False
        if self.role(actor,record['company_id'])=='employee':return record['owner_id']==actor['id'] or (record['kind'] in ('task','tax_job') and actor['id'] in (record['payload'].get('assignee_id'),record['payload'].get('substitute_id'))) or (record['kind']=='attendance' and self.employee_owned(actor,record['company_id'],record['payload'].get('employee_code')))
        return True
    def list_records(self,actor,kind=None,company=None,q='',limit=100,page=1):
        with self.db() as c:
            clauses=['deleted=0'];args=[]
            if kind:clauses.append('kind=?');args.append(kind)
            if company:clauses.append('company_id=?');args.append(company)
            rows=[dict(r,payload=json.loads(r['payload'])) for r in c.execute('SELECT * FROM records WHERE '+' AND '.join(clauses)+' ORDER BY updated DESC',args)]
            extracted=[(r['record_id'],r['extracted']) for r in c.execute("SELECT record_id,extracted FROM files WHERE extracted<>''")] if q else []
        query=normalize(q).replace('ي','ی').replace('ك','ک').casefold()
        matched_files={id for id,text in extracted if query in normalize(text).replace('ي','ی').replace('ك','ک').casefold()}
        result=[r for r in rows if (not kind or r['kind']==kind) and (not company or r['company_id']==company) and self.readable(actor,r) and (not query or r['id'] in matched_files or query in normalize(r['title']+' '+packed(public_record_data(actor,r)['payload'])).replace('ي','ی').replace('ك','ک').casefold())]
        limit=max(1,min(int(limit),500));page=max(1,int(page));return dict(items=result[(page-1)*limit:page*limit],total=len(result),page=page)
    def all_visible(self,actor,kind=None,company=None):
        page=1;result=[]
        while True:
            data=self.list_records(actor,kind,company,limit=500,page=page);result+=data['items']
            if len(result)>=data['total']:return result
            page+=1
    def validate(self,kind,payload):
        if not isinstance(payload,dict):raise DomainError('اطلاعات پرونده معتبر نیست.')
        if kind=='task':
            if not str(payload.get('title','')).strip():raise DomainError('عنوان را وارد کنید.')
            parse_j(payload.get('due_date',''))
            from workspace_store import decimal
            decimal(payload.get('estimate_hours',1),744)
            if payload.get('status','draft') not in STATUSES:raise DomainError('وضعیت معتبر نیست.')
            if not isinstance(payload.get('checklist',[]),list) or len(payload.get('checklist',[]))>100 or any(not isinstance(x,dict) or not isinstance(x.get('text'),str) or not isinstance(x.get('done',False),bool) for x in payload.get('checklist',[])):raise DomainError('چک‌لیست معتبر نیست.')
            if not isinstance(payload.get('dependencies',[]),list) or len(payload.get('dependencies',[]))>100:raise DomainError('وابستگی‌ها معتبر نیستند.')
            return
        if kind=='document':
            if not payload.get('title','').strip():raise DomainError('عنوان سند را وارد کنید.')
            return
        if kind not in SCHEMAS:raise DomainError('نوع پرونده معتبر نیست.')
        if kind=='tax_case' and 'workflow_done' in payload:
            from tax_workflows import workflow_progress
            try:workflow_progress(payload)
            except ValueError as exc:raise DomainError(str(exc)) from exc
        if kind=='tax_case' and 'insured_entries' in payload:
            entries=payload['insured_entries']
            if payload.get('tax_type')!='بیمه کارکنان' or not isinstance(entries,list) or len(entries)>500 or any(not isinstance(e,dict) or set(e)!={'name','reviewed'} or not isinstance(e['name'],str) or not 1<=len(e['name'].strip())<=120 or type(e['reviewed']) is not bool for e in entries):raise DomainError('فهرست بیمه‌شدگان معتبر نیست.')
        if kind=='insurance_workshop':
            from insurance_workshop import validate_workshop
            try:validate_workshop(payload)
            except ValueError as exc:raise DomainError(str(exc)) from exc
        if kind=='insurance_employee':
            from insurance_employee import validate_profile
            try:validate_profile(payload)
            except ValueError as exc:raise DomainError(str(exc)) from exc
        if kind=='insurance_list':
            from insurance_monthly import normalize_draft
            try:normalize_draft(payload)
            except ValueError as exc:raise DomainError(str(exc)) from exc
        if kind=='insurance_rules':
            from insurance_rules import normalize_rules
            try:normalize_rules(payload)
            except ValueError as exc:raise DomainError(str(exc)) from exc
        from penalties import number
        for field in SCHEMAS[kind]['fields']:
            value=payload.get(field['key'])
            if field['required'] and (value is None or str(value).strip()==''):raise DomainError(field['label']+' لازم است.')
            if value not in (None,''):
                if field['type']=='date':parse_j(str(value))
                elif field['type']=='number':number(value)
                elif field['type']=='choice' and value not in field['choices']:raise DomainError(field['label']+' معتبر نیست.')
        if kind=='rate':
            from penalties import calculate
            calculate('0',payload.get('fixed') or '0',payload.get('monthly') or '0','0')
        if kind in ('leave',) and parse_j(payload['end_date'])<parse_j(payload['start_date']):raise DomainError('پایان بازه قبل از شروع است.')
    def save_record(self,actor,kind,payload,company,id=None,version=None,private=False,department='',reason=''):
        p=copy.deepcopy(payload)
        request_id=p.pop('assistant_request_id',None);request_digest=None
        if request_id:
            self.require(kind in ('invoice','client','tax_case') and not id and isinstance(request_id,str) and bool(re.fullmatch('[0-9a-f]{32}',request_id)),'شناسه درخواست معتبر نیست.')
            request_digest=hashlib.sha256(packed(dict(payload=p,company=company)).encode('utf-8')).hexdigest()
        if kind in ('client','invoice'):
            from customer_data import customer,invoice
            try:p=customer(p) if kind=='client' else invoice(p)
            except ValueError as exc:raise DomainError(str(exc)) from exc
        if kind=='task':
            for key,value in dict(status='draft',require_approval=True,require_evidence=False,category='سایر',notes='',assignee_id='',reviewer_id='',substitute_id='',reference='',deadline_source='',dependencies=[],checklist=[],priority='مهم').items():p.setdefault(key,value)
        if kind=='payroll_batch':
            from payroll_batch import validate_batch
            p=validate_batch(p)
        if kind=='insurance_workshop':
            from insurance_workshop import normalize_workshop
            try:p=normalize_workshop(p)
            except ValueError as exc:raise DomainError(str(exc)) from exc
        if kind=='insurance_employee':
            from insurance_employee import normalize_profile
            try:p=normalize_profile(p)
            except ValueError as exc:raise DomainError(str(exc)) from exc
        if kind=='insurance_list':
            from insurance_monthly import normalize_draft
            try:p=normalize_draft(p)
            except ValueError as exc:raise DomainError(str(exc)) from exc
        if kind=='insurance_rules':
            from insurance_rules import normalize_rules
            try:p=normalize_rules(p)
            except ValueError as exc:raise DomainError(str(exc)) from exc
        self.validate(kind,p)
        if len(packed(p))>(1000000 if kind=='payroll_batch' else 200000):raise DomainError('متن پرونده بیش از حد بزرگ است.')
        area=SCHEMAS.get(kind,{}).get('area','work')
        with self.db(True) as c:
            oldrow=c.execute('SELECT * FROM records WHERE id=? AND deleted=0',(id,)).fetchone() if id else None
            if id and not oldrow:raise DomainError('پرونده پیدا نشد.',404)
            old=dict(oldrow,payload=json.loads(oldrow['payload'])) if oldrow else None
            if old:
                self.require(old['kind']==kind,'نوع پرونده قابل تغییر نیست.')
                self.require(self.writable(actor,old));company=old['company_id'];private=old['private'];department=old['department']
                if version is None or int(version)!=old['version']:raise DomainError('این پرونده توسط فرد دیگری تغییر کرده است؛ تازه‌سازی و سپس ویرایش کنید.',409)
                if self.role(actor,company)=='employee' and old['owner_id']!=actor['id']:
                    allowed=('status','checklist')
                    if any(p.get(k)!=old['payload'].get(k) for k in set(p)|set(old['payload']) if k not in allowed):raise DomainError('فقط وضعیت و چک‌لیست کار واگذارشده قابل تغییر است.',403)
            else:
                self.require(bool(private) or self.permission(actor,company,area,'create'));id=uid()
                if private:company=None
                self.require_module(actor,company,record_module(kind),record_action(kind,'create'))
                if request_id:
                    prior=c.execute('SELECT * FROM workspace_invoice_requests WHERE user_id=? AND request_id=?',(actor['id'],request_id)).fetchone()
                    if prior:
                        self.require(prior['digest']==request_digest and prior['company_id']==company,'شناسه درخواست برای فاکتور دیگری استفاده شده است.')
                        previous=self.record(prior['record_id']);self.require(previous['kind']==kind and self.readable(actor,previous),'پرونده قبلی در دسترس نیست.');return previous
                if self.role(actor,company)=='employee' and kind not in ('task','leave','request','form_response','document','attendance','client','invoice','tax_job'):raise DomainError('ایجاد این نوع پرونده برای کارمند مجاز نیست.',403)
                if self.role(actor,company)=='employee' and kind in ('leave',) and not self.employee_owned(actor,company,p.get('employee_code')):raise DomainError('درخواست فقط برای خودتان ثبت می‌شود.',403)
                if self.role(actor,company)=='employee' and kind=='attendance':self.require(self.employee_owned(actor,company,p.get('employee_code')),'تردد فقط برای خودتان ثبت می‌شود.')
                if kind=='task' and self.role(actor,company)=='employee':p['assignee_id']=actor['id']
            if kind=='payroll_batch' and old:raise DomainError('دوره ثبت‌شده ثابت است؛ نسخه تازه ایجاد کنید.',409)
            if kind=='insurance_rules':
                if old:raise DomainError('قواعد ثبت‌شده تغییر نمی‌کند؛ نسخه تازه بسازید.',409)
                if p['approved']:self.require(self.role(actor,company) in MANAGERS|{'finance'},'تأیید قواعد فقط توسط مدیر یا مسئول مالی مجاز است.')
                duplicate=any(json.loads(row['payload']).get('rules_version')==p['rules_version'] for row in c.execute("SELECT payload FROM records WHERE company_id=? AND kind='insurance_rules'",(company,)))
                self.require(not duplicate,'شناسه این نسخه قواعد قبلاً در شرکت ثبت شده است.')
            if kind=='tax_case':
                from tax_workflows import workflow_progress
                if old and old['payload'].get('tax_type')!=p.get('tax_type') and (any(old['payload'].get('workflow_done',[])) or old['payload'].get('insured_entries')):raise DomainError('برای تغییر نوع، پرونده جدید ثبت کنید؛ مراحل و فهرست بیمه پرونده قبلی محفوظ می‌ماند.')
                previous=workflow_progress(old['payload']) if old else []
                current=workflow_progress(p)
                if sum(current)>sum(previous)+1:raise DomainError('هر بار فقط مرحله بعد قابل تأیید است.')
            if kind=='insurance_workshop':
                duplicate=any(row['id']!=id and json.loads(row['payload']).get('workshop_code')==p['workshop_code'] and json.loads(row['payload']).get('contract_row','')==p.get('contract_row','') for row in c.execute("SELECT id,payload FROM records WHERE company_id=? AND kind='insurance_workshop' AND deleted=0",(company,)))
                self.require(not duplicate,'این کد کارگاه و ردیف پیمان قبلاً در همین شرکت ثبت شده است.')
            if kind=='insurance_employee':
                for field,expected in (('employee_id','employee'),('workshop_id','insurance_workshop')):
                    linkedrow=c.execute('SELECT * FROM records WHERE id=? AND company_id=? AND kind=? AND deleted=0',(p[field],company,expected)).fetchone()
                    self.require(bool(linkedrow),'کارمند و کارگاه باید در همین شرکت ثبت شده باشند.')
                    linked=dict(linkedrow,payload=json.loads(linkedrow['payload']))
                    self.require(self.readable(actor,linked),'برای ارتباط پرونده، دسترسی مشاهده کارمند و کارگاه لازم است.')
                if old:self.require(old['payload']['employee_id']==p['employee_id'],'کارمند پرونده قابل تغییر نیست؛ برای فرد دیگر پرونده جدید بسازید.')
                if old and old['payload'].get('workshop_id')!=p['workshop_id']:
                    linked=any(any(line.get('profile_id')==id for line in json.loads(item['payload']).get('rows',[])) for item in c.execute("SELECT payload FROM records WHERE company_id=? AND kind='insurance_list'",(company,)))
                    if linked:raise DomainError('پرونده در لیست بیمه استفاده شده است؛ کارگاه آن قابل تغییر نیست.',409)
                for row in c.execute("SELECT id,payload FROM records WHERE company_id=? AND kind='insurance_employee' AND deleted=0",(company,)):
                    if row['id']==id:continue
                    existing=json.loads(row['payload'])
                    if existing.get('employee_id')==p['employee_id'] or any(p.get(field) and p.get(field)==existing.get(field) for field in ('national_id','insurance_number')):
                        raise DomainError('کارمند یا شناسه بیمه‌ای او قبلاً در همین شرکت ثبت شده است.')
            if kind=='insurance_list':
                workshoprow=c.execute("SELECT * FROM records WHERE id=? AND company_id=? AND kind='insurance_workshop' AND deleted=0",(p['workshop_id'],company)).fetchone()
                self.require(bool(workshoprow),'کارگاه باید در همین شرکت ثبت شده باشد.')
                workshop=dict(workshoprow,payload=json.loads(workshoprow['payload']));self.require(self.readable(actor,workshop),'دسترسی مشاهده کارگاه لازم است.')
                if old:self.require(old['payload']['workshop_id']==p['workshop_id'] and old['payload']['period']==p['period'],'کارگاه و ماه لیست قابل تغییر نیست؛ لیست جدید بسازید.')
                for row in p['rows']:
                    profilerow=c.execute("SELECT * FROM records WHERE id=? AND company_id=? AND kind='insurance_employee' AND deleted=0",(row['profile_id'],company)).fetchone()
                    self.require(bool(profilerow),'پرونده بیمه‌ای یکی از کارکنان پیدا نشد.')
                    profile=dict(profilerow,payload=json.loads(profilerow['payload']));self.require(self.readable(actor,profile) and profile['payload'].get('workshop_id')==p['workshop_id'],'پرونده کارکنان باید متعلق به همین کارگاه و قابل مشاهده باشد.')
                duplicate=any(row['id']!=id and (q:=json.loads(row['payload'])).get('workshop_id')==p['workshop_id'] and q.get('period')==p['period'] and q.get('list_no')==p['list_no'] for row in c.execute("SELECT id,payload FROM records WHERE company_id=? AND kind='insurance_list' AND deleted=0",(company,)))
                self.require(not duplicate,'این شماره لیست برای کارگاه و ماه انتخاب‌شده قبلاً ثبت شده است.')
            for link,expected in [('client_id','client'),('contract_id','contract')]:
                if p.get(link):
                    linked=self.record(p[link]);self.require(linked['kind']==expected and linked['company_id']==company and self.readable(actor,linked),'پرونده مرتبط باید در همین شرکت و قابل دسترسی باشد.')
            if kind in ('invoice','tax_job'):
                self.require(bool(p.get('client_id')),'مشتری را انتخاب کنید.')
                from customer_data import buyer_snapshot
                linked=self.record(p['client_id']);refresh=bool(p.pop('refresh_customer',False))
                p['customer_snapshot']=buyer_snapshot(linked['payload']) if not old or p['client_id']!=old['payload'].get('client_id') or refresh else copy.deepcopy(old['payload'].get('customer_snapshot') or buyer_snapshot(linked['payload']))
                if kind=='invoice':
                    from finance_store import next_number
                    if old:self.require(p['document_type']==old['payload'].get('document_type','پیش‌فاکتور'),'نوع فاکتور ثبت‌شده قابل تغییر نیست؛ سند جدید ایجاد کنید.')
                    if old:
                        for field in ('source_quote_id','source_quote_number'):
                            if field in old['payload']:p[field]=old['payload'][field]
                            else:p.pop(field,None)
                    elif p.get('source_quote_id'):
                        quote=c.execute("SELECT * FROM records WHERE id=? AND company_id=? AND kind='invoice' AND deleted=0",(p['source_quote_id'],company)).fetchone()
                        self.require(bool(quote),'پیش‌فاکتور مبنا پیدا نشد.');quote=dict(quote);quote['payload']=json.loads(quote['payload']);qp=quote['payload']
                        self.require(self.readable(actor,quote) and qp.get('document_type')=='پیش‌فاکتور' and qp.get('status')!='cancelled' and p.get('document_type')=='فاکتور فروش' and qp.get('client_id')==p.get('client_id'),'پیش‌فاکتور مبنا یا طرف حساب معتبر نیست.')
                        p['source_quote_number']=str(qp.get('number',''))
                    else:p.pop('source_quote_number',None)
                    if p['number']=='__AUTO__':
                        self.require(not old,'شماره فاکتور موجود به شکل خودکار تغییر نمی‌کند.')
                        p['number']=next_number(c,company,p['document_type']);p['title']=p['document_type']+' '+p['number']
                    p['document_no']=old['payload'].get('document_no') if old else next_number(c,company,'document')
                    if not p['document_no']:p['document_no']=next_number(c,company,'document')
                    seller=c.execute('SELECT * FROM companies WHERE id=?',(company,)).fetchone();detail=c.execute('SELECT phone,address,logo FROM company_details WHERE company_id=?',(company,)).fetchone()
                    p['seller_name']=old['payload'].get('seller_name','') if old and not refresh else dict(seller).get('name','') if seller else ''
                    p['seller_snapshot']=copy.deepcopy(old['payload'].get('seller_snapshot',{})) if old and not refresh else dict(detail) if detail else {}
                    duplicate=any(row['id']!=id and json.loads(row['payload']).get('number')==p['number'] and json.loads(row['payload']).get('document_type','پیش‌فاکتور')==p['document_type'] for row in c.execute("SELECT id,payload FROM records WHERE company_id=? AND kind='invoice'",(company,)))
                    self.require(not duplicate,'این شماره فاکتور در همین شرکت از قبل ثبت شده است.')
            if kind in ('client','tax_job','invoice') and p.get('assignee_id'):
                person=self.user(p['assignee_id']);self.require(bool(person) and bool(self.role(person,company)),'مسئول پیگیری باید عضو همین شرکت باشد.')
            if kind=='client':
                if not old and not p.get('customer_code'):
                    used=[]
                    for row in c.execute("SELECT payload FROM records WHERE company_id=? AND kind='client'",(company,)):
                        code=str(json.loads(row['payload']).get('customer_code',''))
                        if code.isdecimal():used.append(int(code))
                    p['customer_code']=str(max([99]+used)+1)
                for field in ('national_id','economic_code','customer_code'):
                    if p.get(field) and (not old or p[field]!=old['payload'].get(field)):
                        duplicate=any(row['id']!=id and json.loads(row['payload']).get(field)==p[field] for row in c.execute("SELECT id,payload FROM records WHERE company_id=? AND kind='client' AND deleted=0",(company,)))
                        self.require(not duplicate,'مشتری با این شناسه / کد از قبل در همین شرکت وجود دارد.')
            role=self.role(actor,company)
            if role=='employee' and not private:
                if kind in ('leave','request','form_response') and old and old['payload'].get('status') in ('approved','rejected'):raise DomainError('درخواست بررسی‌شده را تغییر ندهید؛ درخواست تازه ثبت کنید.',403)
                if kind=='leave':self.require(self.employee_owned(actor,company,p.get('employee_code')),'درخواست فقط برای خودتان ثبت می‌شود.')
                if kind=='attendance':
                    self.require(self.employee_owned(actor,company,p.get('employee_code')),'تردد فقط برای خودتان ثبت می‌شود.')
                    self.require(not old or old['payload'].get('status')!='approved','تردد تأییدشده فقط توسط مدیر مجاز اصلاح می‌شود.')
                    self.require(p.get('status','imported') in ('imported','needs_review'),'تأیید تردد فقط توسط مدیر انجام می‌شود.')
                if kind=='task':
                    protected=('assignee_id','reviewer_id','substitute_id','require_approval','require_evidence','dependencies')
                    if old and any(p.get(k)!=old['payload'].get(k) for k in protected):raise DomainError('مسئول و شرایط تأیید کار فقط توسط مسئول مجاز تغییر می‌کند.',403)
                    if not old:p.update(assignee_id=actor['id'],require_approval=True)
            if private:
                if kind!='task':raise DomainError('فقط کار شخصی در بخش خصوصی ثبت می‌شود.')
                p.update(assignee_id=actor['id'],reviewer_id='',substitute_id='',require_approval=False,dependencies=[])
            if kind=='task':self.validate_task_transition(c,actor,old,p,company)
            elif kind in ('leave','request','form_response','attendance','proposal'):
                oldstatus=old['payload'].get('status') if old else None
                if p.get('status') in ('approved','rejected') and p.get('status')!=oldstatus:self.require(self.role(actor,company) in APPROVERS,'تأیید فقط توسط مسئول مجاز انجام می‌شود.')
                if kind=='attendance' and p.get('status') in ('approved','rejected') and p.get('status')!=oldstatus:
                    self.require(self.desk_manager(actor,company),'تأیید تردد فقط توسط مدیر شرکت است.');self.require_module(actor,company,'attendance','approve')
            if kind=='calculation':
                from penalties import calculate
                if old:raise DomainError('محاسبه ذخیره‌شده ثابت است؛ برای اصلاح نسخه تازه ثبت کنید.',409)
                if p.get('rate_id'):
                    rate=self.record(p['rate_id']);self.require(rate['kind']=='rate' and rate['company_id']==company and self.readable(actor,rate));p.update(fixed=rate['payload'].get('fixed') or '0',monthly=rate['payload'].get('monthly') or '0');p['rate_snapshot']=rate['payload']
                result=calculate(p.get('amount') or '0',p.get('fixed') or '0',p.get('monthly') or '0',p.get('months') or '0');p['result']={k:str(v) for k,v in result.items()};p['calculated_at']=stamp()
            if kind=='rate' and old and p!=old['payload']:raise DomainError('نرخ ثبت‌شده تغییر نمی‌کند؛ نسخه تازه بسازید تا محاسبات قبلی معتبر بمانند.',409)
            created=old['created'] if old else stamp();owner=old['owner_id'] if old else actor['id'];v=old['version']+1 if old else 1
            if kind=='proposal' and p.get('status')=='approved' and (not old or old['payload'].get('status')!='approved'):self._apply_proposal(c,actor,p,company)
            if kind=='invoice':
                for index,line in enumerate(p['lines']):
                    if not line.get('product_id'):continue
                    product=c.execute('SELECT * FROM stock_products WHERE id=? AND company_id=?',(line['product_id'],company)).fetchone()
                    self.require(bool(product),'کالای فاکتور در این شرکت پیدا نشد.')
                    previous=old['payload'].get('lines',[]) if old else []
                    self.require(bool(product['active']) or any(x.get('product_id')==line['product_id'] for x in previous),'کالای حذف‌شده برای فاکتور تازه قابل انتخاب نیست.')
                    prior=previous[index] if index<len(previous) and previous[index].get('product_id')==line['product_id'] else {}
                    cost=prior.get('unit_cost_snapshot',product['purchase_price']);line['unit_cost_snapshot']=cost;line['product_code']=product['code']
                    from inventory_logic import gross_profit
                    line['gross_profit']=str(gross_profit(line['quantity'],line['unit_price'],cost,Decimal(line['discount'])+Decimal(line.get('invoice_discount_share','0'))))
                self.inventory_invoice_change(c,actor,company,id,old['payload'] if old else None,p)
                self.finance_invoice_change(c,actor,company,id,p)
            c.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,0) ON CONFLICT(id) DO UPDATE SET title=excluded.title,payload=excluded.payload,version=excluded.version,updated=excluded.updated',(id,kind,company,owner,int(private),department,p.get('title',''),packed(p),v,created,stamp()));self.audit(c,actor,company,id,'edit' if old else 'create',old['payload'] if old else None,p,reason)
            if request_id:c.execute('INSERT INTO workspace_invoice_requests VALUES(?,?,?,?,?)',(actor['id'],request_id,company,request_digest,id))
            if kind in ('task','tax_job') and (not old or p.get('due_date')!=old['payload'].get('due_date') or p.get('assignee_id')!=old['payload'].get('assignee_id')):
                for person in set(filter(None,[p.get('assignee_id'),p.get('substitute_id')])):
                    if person!=actor['id']:self.workspace_notify(c,person,company,'کار / موعد تازه',p['title']+' | '+p['due_date'],'record:'+id)
        return self.record(id)
    def validate_task_transition(self,c,actor,old,p,company):
        role=self.role(actor,company)
        for field in ('assignee_id','reviewer_id','substitute_id'):
            user=p.get(field)
            if user and company:
                u=self.user(user);self.require(self.role(u,company) is not None,'فرد انتخاب‌شده به این شرکت دسترسی ندارد.')
        deps=p.get('dependencies',[])
        if old and old['id'] in deps:raise DomainError('کار نمی‌تواند وابسته به خودش باشد.')
        for dep in deps:
            record=self.record(dep);self.require(record['kind']=='task' and record['company_id']==company and self.readable(actor,record),'وابستگی باید به کار مجاز همان شرکت باشد.')
            if p.get('status') in ('in_progress','review','submitted','completed') and record['payload'].get('status')!='completed':raise DomainError('کار پیش‌نیاز هنوز تکمیل نشده است.')
            visited=set()
            def walk(key):
                if old and key==old['id']:raise DomainError('وابستگی حلقه‌ای مجاز نیست.')
                if key in visited:return
                visited.add(key);node=c.execute('SELECT payload FROM records WHERE id=? AND deleted=0',(key,)).fetchone()
                if node:
                    for child in json.loads(node[0]).get('dependencies',[]):walk(child)
            walk(dep)
        status=p.get('status','draft');previous=old['payload'].get('status','draft') if old else 'draft'
        if status in ('submitted','completed') and status!=previous:
            if p.get('require_approval',True):self.require_module(actor,company,'workspace','approve');self.require(role in APPROVERS and (not p.get('reviewer_id') or p['reviewer_id']==actor['id'] or role in MANAGERS),'این کار منتظر تأیید مسئول مجاز است.')
            if p.get('require_evidence') and (not old or not c.execute('SELECT 1 FROM files WHERE record_id=?',(old['id'],)).fetchone()):raise DomainError('رسید یا مدرک انجام را پیوست کنید.')
            if any(not item.get('done') for item in p.get('checklist',[])):raise DomainError('چک‌لیست کامل نشده است.')
    def delete_record(self,actor,id,version):
        old=self.record(id);self.require(self.writable(actor,old,'delete'))
        with self.db(True) as c:
            if old['kind'] in ('employee','insurance_workshop'):
                field='employee_id' if old['kind']=='employee' else 'workshop_id'
                linked=any(json.loads(row['payload']).get(field)==id for row in c.execute("SELECT payload FROM records WHERE company_id=? AND kind='insurance_employee'",(old['company_id'],)))
                if linked:raise DomainError('این کارمند یا کارگاه در پرونده بیمه‌ای، از جمله پرونده‌های بایگانی‌شده، استفاده شده است؛ ابتدا ارتباط آن را تعیین تکلیف کنید.',409)
            if old['kind'] in ('insurance_employee','insurance_workshop'):
                linked=any((q.get('workshop_id')==id if old['kind']=='insurance_workshop' else any(line.get('profile_id')==id for line in q.get('rows',[]))) for q in (json.loads(row['payload']) for row in c.execute("SELECT payload FROM records WHERE company_id=? AND kind='insurance_list'",(old['company_id'],))))
                if linked:raise DomainError('این پرونده در لیست بیمه استفاده شده است؛ ابتدا لیست‌های مرتبط را تعیین تکلیف کنید.',409)
            result=c.execute('UPDATE records SET deleted=1,version=version+1,updated=? WHERE id=? AND version=? AND deleted=0',(stamp(),id,int(version)))
            if not result.rowcount:raise DomainError('پرونده تغییر کرده است؛ تازه‌سازی کنید.',409)
            if old['kind']=='invoice':
                self.inventory_invoice_change(c,actor,old['company_id'],id,old['payload'],old['payload'],after_deleted=True)
                self.finance_invoice_change(c,actor,old['company_id'],id,old['payload'],deleted=True)
            self.audit(c,actor,old['company_id'],id,'archive',old['payload'])
        return {'ok':True}
    def comments(self,actor,id):
        self.require(self.readable(actor,self.record(id)))
        with self.db() as c:return [dict(x) for x in c.execute('SELECT c.*,u.fullname FROM comments c JOIN users u ON u.id=c.author WHERE record_id=? ORDER BY created',(id,))]
    def add_comment(self,actor,id,text):
        r=self.record(id);self.require(self.readable(actor,r));self.require(self.writable(actor,r));self.require(self.role(actor,r['company_id'])!='auditor')
        if not text.strip() or len(text)>10000:raise DomainError('متن نظر معتبر نیست.')
        with self.db(True) as c:c.execute('INSERT INTO comments VALUES(?,?,?,?,?)',(uid(),id,actor['id'],text.strip(),stamp()));self.audit(c,actor,r['company_id'],id,'comment',after={'text':text.strip()})
        return {'ok':True}
    def add_file(self,actor,record_id,name,data,mime='application/octet-stream'):
        record=self.record(record_id);self.require(self.writable(actor,record));self.require_module(actor,record['company_id'],'company','upload');name=Path(name.replace('\\','/')).name
        if not name or len(data)>12*1024*1024 or not data:raise DomainError('فایل خالی یا بزرگ‌تر از ۱۲ مگابایت است.')
        if Path(name).suffix.lower() not in ('.pdf','.png','.jpg','.jpeg','.txt','.csv','.xlsx','.docx','.zip'):raise DomainError('قالب فایل پشتیبانی نمی‌شود.')
        id=uid();target=self.files/(id+'.bin');target.write_bytes(data)
        try:
            with self.db(True) as c:
                version=c.execute('SELECT COALESCE(MAX(version),0)+1 FROM files WHERE record_id=? AND name=?',(record_id,name)).fetchone()[0]
                c.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?,?,?,?)',(id,record_id,name,hashlib.sha256(data).hexdigest(),len(data),mime,version,stamp(),actor['id'],''));self.audit(c,actor,record['company_id'],record_id,'attachment',after={'file':id,'name':name,'version':version})
        except Exception:target.unlink(missing_ok=True);raise
        return {'id':id,'name':name,'version':version}
    def file_info(self,actor,id):
        with self.db() as c:row=c.execute('SELECT * FROM files WHERE id=?',(id,)).fetchone()
        if not row:raise DomainError('فایل پیدا نشد.',404)
        record=self.record(row['record_id']);self.require(self.readable(actor,record));self.require_module(actor,record['company_id'],'company','download');return dict(row)
    def file_list(self,actor,record_id):
        record=self.record(record_id);self.require(self.readable(actor,record));self.require_module(actor,record['company_id'],'company','download')
        with self.db() as c:return [dict(x) for x in c.execute('SELECT * FROM files WHERE record_id=? ORDER BY created DESC',(record_id,))]
    def read_file(self,actor,id):return self.file_info(actor,id),(self.files/(id+'.bin')).read_bytes()
    def publish(self,actor,payload):
        companies=list(dict.fromkeys(payload.get('companies',[])));requested=payload.get('users',[]);department=payload.get('department','')
        request_id=payload.get('request_id')
        if request_id:self.require(isinstance(request_id,str) and bool(re.fullmatch('[0-9a-f]{32}',request_id)),'شناسه درخواست معتبر نیست.')
        if not companies:
            self.require(actor['global_role']=='group_admin');companies=[x['id'] for x in self.companies(actor)]
        for company in companies:self.require(self.role(actor,company) in APPROVERS and self.permission(actor,company,'work','publish') and self.module_permission(actor,company,'company','create'))
        people=self.users(actor);recipients=[]
        for person in people:
            if not person['active']:continue
            memberships=[m for m in person['memberships'] if m['company_id'] in companies and (not department or m.get('department')==department)]
            eligible=bool(memberships or person['global_role']=='group_admin')
            if eligible and (not requested or person['id'] in requested):recipients.append(person['id'])
        if not payload.get('title','').strip() or not payload.get('body','').strip():raise DomainError('عنوان و متن اطلاعیه لازم است.')
        for field in ('publish_at','expires_at'):
            if payload.get(field):
                try:datetime.fromisoformat(payload[field]).astimezone(timezone.utc)
                except ValueError:raise DomainError('زمان انتشار یا انقضا معتبر نیست.')
        p={k:payload.get(k) for k in ('title','body','importance','require_ack','publish_at','expires_at')};digest=hashlib.sha256(packed(dict(companies=companies,users=requested,department=department,**p)).encode('utf-8')).hexdigest() if request_id else None;p['companies']=companies;p['recipients']=recipients;p['author_name']=actor['fullname'];id=uid()
        with self.db(True) as c:
            if request_id:
                prior=c.execute('SELECT digest,record_id FROM workspace_notice_requests WHERE user_id=? AND request_id=?',(actor['id'],request_id)).fetchone()
                if prior:
                    self.require(prior['digest']==digest,'شناسه درخواست پیش‌تر برای اطلاعیه دیگری استفاده شده است.');return self.record(prior['record_id'])
            c.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,0)',(id,'notice',companies[0] if len(companies)==1 else None,actor['id'],0,department,p['title'],packed(p),1,stamp(),stamp()));self.audit(c,actor,companies[0] if len(companies)==1 else None,id,'publish',after={'title':p['title'],'recipient_count':len(recipients)})
            for user_id in recipients:c.execute('INSERT INTO receipts VALUES(?,?,NULL,NULL,NULL)',(id,user_id))
            if request_id:c.execute('INSERT INTO workspace_notice_requests VALUES(?,?,?,?)',(actor['id'],request_id,digest,id))
        return self.record(id)
    def inbox(self,actor):
        now=datetime.now(timezone.utc);items=[]
        for r in self.all_visible(actor,'notice'):
            p=r['payload']
            if actor['id'] not in p.get('recipients',[]):continue
            if p.get('publish_at') and datetime.fromisoformat(p['publish_at']).astimezone(timezone.utc)>now:continue
            if p.get('expires_at') and datetime.fromisoformat(p['expires_at']).astimezone(timezone.utc)<now:continue
            with self.db(True) as c:
                c.execute('UPDATE receipts SET delivered=COALESCE(delivered,?) WHERE record_id=? AND user_id=?',(stamp(),r['id'],actor['id']));receipt=c.execute('SELECT * FROM receipts WHERE record_id=? AND user_id=?',(r['id'],actor['id'])).fetchone()
            view=copy.deepcopy(r);view['payload'].pop('recipients',None);view['receipt']=dict(receipt);items.append(view)
        return items
    def acknowledge(self,actor,id,action):
        r=self.record(id);self.require(self.readable(actor,r) and actor['id'] in r['payload'].get('recipients',[]))
        field={'open':'opened','ack':'acknowledged'}.get(action)
        if not field:raise DomainError('عملیات معتبر نیست.')
        with self.db(True) as c:c.execute(f'UPDATE receipts SET {field}=COALESCE({field},?),opened=COALESCE(opened,?) WHERE record_id=? AND user_id=?',(stamp(),stamp(),id,actor['id']))
        return {'ok':True}
    def receipt_report(self,actor,id):
        r=self.record(id);self.require(r['kind']=='notice' and (r['owner_id']==actor['id'] or actor['global_role']=='group_admin'))
        with self.db() as c:return [dict(x) for x in c.execute('SELECT r.*,u.fullname FROM receipts r JOIN users u ON u.id=r.user_id WHERE record_id=?',(id,))]
    def history(self,actor,id=None):
        target_record=self.record(id) if id else None
        if target_record:self.require(self.readable(actor,target_record))
        with self.db() as c:rows=[dict(x) for x in c.execute('SELECT a.*,u.fullname FROM audit a LEFT JOIN users u ON u.id=a.actor ORDER BY a.id DESC LIMIT 2000')]
        result=[]
        for row in rows:
            # Private chat metadata is visible only to the two participants,
            # including when a manager views the general company audit feed.
            if row['action'].startswith('chat_') or row['action']=='direct_open':
                room=None
                if row['action']=='direct_open' or str(row.get('target') or '').startswith(('dm:','saved:','group:')):room=row['target']
                if not room:
                    try:room=json.loads(row['after_json'] or '{}').get('room')
                    except (ValueError,TypeError):pass
                if not room and row['target']:
                    with self.db() as c:chat=c.execute('SELECT room FROM chat_messages WHERE id=?',(row['target'],)).fetchone()
                    room=chat['room'] if chat else None
                if room and room.startswith(('dm:','saved:','group:')):
                    try:self.room_access(actor,row['company_id'],room)
                    except DomainError:continue
            if id and row['target']!=id:continue
            if not id:
                if row['company_id'] and self.role(actor,row['company_id']) not in APPROVERS|{'auditor'}:continue
                if not row['company_id'] and actor['global_role'] not in ('group_admin','system_admin'):continue
                with self.db() as c:record=c.execute('SELECT * FROM records WHERE id=?',(row['target'],)).fetchone()
                if record and not self.readable(actor,dict(record,payload=json.loads(record['payload']))):continue
                if not record and actor['global_role'] not in ('group_admin','system_admin'):continue
            current=target_record if id else dict(record) if record else None
            if current and current.get('kind')=='invoice' and not self.module_permission(actor,current.get('company_id'),'finance','view'):
                row['before_json']=None;row['after_json']=None;row['reason']=''
            result.append(row)
        return result
    def dashboard(self,actor,company=None):
        rows=self.all_visible(actor,company=company);tasks=[r for r in rows if r['kind']=='task'];today=date.today()
        def overdue(r):
            try:return parse_j(r['payload']['due_date']).togregorian()<today and r['payload'].get('status')!='completed'
            except (ValueError,KeyError):return False
        amounts=[]
        for r in rows:
            if r['kind']=='commitment' and not r['payload'].get('paid'):
                try:
                    if today<=parse_j(r['payload']['due_date']).togregorian()<=today+timedelta(days=30):
                        from penalties import number
                        amounts.append(number(r['payload'].get('amount') or '0'))
                except (ValueError,KeyError):pass
        workload={}
        for task in tasks:
            if task['payload'].get('status')!='completed':
                person=task['payload'].get('assignee_id') or 'unassigned';workload[person]=workload.get(person,0)+1
        return dict(total=len(tasks),overdue=sum(map(overdue,tasks)),review=sum(t['payload'].get('status')=='review' for t in tasks),completed=sum(t['payload'].get('status')=='completed' for t in tasks),unassigned=sum(not t['payload'].get('assignee_id') for t in tasks),workload=workload,upcoming_amount=str(sum(amounts)),revision=self.records_revision())
    def apply_proposal(self,actor,id):
        proposal=self.record(id);p=proposal['payload'];self.require(self.role(actor,proposal['company_id']) in APPROVERS)
        # One transaction changes all selected tasks or none; an unrelated company
        # or stale old date cannot be silently overwritten by a headline.
        with self.db(True) as c:
            return self._apply_proposal(c,actor,p,proposal['company_id'])
    def _apply_proposal(self,c,actor,p,company):
        self.require(self.role(actor,company) in APPROVERS)
        ids=list(dict.fromkeys(s.strip() for s in p.get('task_ids','').split(',') if s.strip()));changed=[]
        for task_id in ids:
            row=c.execute('SELECT * FROM records WHERE id=? AND deleted=0',(task_id,)).fetchone()
            if not row:raise DomainError('یکی از کارهای پیشنهاد پیدا نشد.',404)
            task=dict(row,payload=json.loads(row['payload']));self.require(task['kind']=='task' and task['company_id']==company and self.writable(actor,task))
            if p.get('old_date') and parse_j(task['payload']['due_date'])!=parse_j(p['old_date']):raise DomainError('موعد فعلی یکی از کارها با موعد قبلی پیشنهاد یکسان نیست.',409)
            new=copy.deepcopy(task['payload']);new.update(due_date=p['new_date'],deadline_source=p['source'],deadline_reason=p['reason']);c.execute('UPDATE records SET payload=?,version=version+1,updated=? WHERE id=?',(packed(new),stamp(),task_id));self.audit(c,actor,company,task_id,'deadline_approved',task['payload'],new,p['reason']);changed.append(task_id)
            for person in set(filter(None,[new.get('assignee_id'),new.get('substitute_id'),new.get('reviewer_id')])):
                self.workspace_notify(c,person,company,'تغییر موعد تأییدشده',task['title']+' | '+p['new_date']+'\n'+p['source'],'record:'+task_id)
        return changed
    def export_scope(self,actor,company=None):
        companies=self.companies(actor)
        for comp in companies:
            if (not company or company==comp['id']) and self.role(actor,comp['id'])!='employee':self.require(self.permission(actor,comp['id'],'work','export'),'اجازه دریافت خروجی این شرکت را ندارید.')
        rows=self.all_visible(actor,company=company);attachments=[]
        for row in rows:
            if self.module_permission(actor,row['company_id'],'company','download'):attachments.extend(self.file_list(actor,row['id']))
        chats=[]
        for room in self.chat_rooms(actor):
            if company and room['company']!=company:continue
            before=None
            while True:
                page=self.chat_list(actor,room['company'],room['room'],before,100)
                if not page['items']:break
                chats.extend(page['items'])
                for message in page['items']:attachments.extend(dict(f,record_id=message['id'],chat=True) for f in message['files'])
                if not page['has_more']:break
                before=page['items'][0]['seq']
        desk=self.desk_snapshot(actor)
        if company:
            desk=dict(desk,companies=[x for x in desk['companies'] if x['id']==company],managed_companies=[x for x in desk['managed_companies'] if x==company],notes=[],leaves=[x for x in desk['leaves'] if x['company_id']==company],incoming=[x for x in desk['incoming'] if x['company_id']==company],notifications=[])
        rows=[public_record_data(actor,row) for row in rows]
        inventory={};finance={}
        for comp in companies:
            cid=comp['id']
            if (not company or cid==company) and self.module_permission(actor,cid,'clients','view'):
                inventory[cid]=self.inventory_list(actor,cid)
                if self.module_permission(actor,cid,'finance','export'):finance[cid]=self.finance_list(actor,cid)
        return dict(format='karname-company-export-v3',exported_at=stamp(),user={k:actor[k] for k in ('id','username','fullname')},profile=self.own_profile(actor),companies=companies,records=rows,chat_messages=chats,files=attachments,personal_desk=desk,inventory=inventory,finance=finance)
    def backup_database(self,target):
        with self.lock,self.db() as source:
            destination=sqlite3.connect(target)
            try:source.backup(destination)
            finally:destination.close()

    def import_attendance(self,actor,company,rows,month):
        self.desk_company(actor,company);self.require(self.desk_manager(actor,company) and self.permission(actor,company,'hr','create'));self.require_module(actor,company,'attendance','import')
        from attendance_import import preview
        if not isinstance(rows,list) or len(rows)>10000:raise DomainError('هر بار حداکثر ۱۰ هزار ردیف وارد کنید.')
        # Repeat date/minute/dedup validation on the server, never trust client preview.
        converted=[[p.get(k,'') for k in ('employee_code','date','check_in','check_out','minutes')] for p in rows]
        validated=preview(list(('employee_code','date','check_in','check_out','minutes')),converted,dict(employee_code=0,date=1,check_in=2,check_out=3,minutes=4),month)
        if any(not x['valid'] for x in validated):raise DomainError('ردیف نامعتبر یا تکراری در فایل وجود دارد؛ پیش‌نمایش را اصلاح کنید.')
        people={r['payload']['employee_code']:r for r in self.all_visible(actor,'employee',company)};added=0;duplicate=0
        with self.db(True) as c:
            existing={json.loads(r[0]).get('import_key') for r in c.execute("SELECT payload FROM records WHERE kind='attendance' AND company_id=? AND deleted=0",(company,))}
            for item in validated:
                p=item['payload'];person=people.get(p['employee_code'])
                if not person:raise DomainError('کد پرسنلی ثبت‌شده یا مجاز نیست: '+p['employee_code'])
                if p['import_key'] in existing:duplicate+=1;continue
                existing.add(p['import_key']);id=uid();c.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,0)',(id,'attendance',company,actor['id'],0,person['department'],p['title'],packed(p),1,stamp(),stamp()));self.audit(c,actor,company,id,'attendance_import',after=p);added+=1
        return dict(added=added,duplicates=duplicate)

    def payroll(self,actor,company,month):
        self.require_module(actor,company,'payroll','view');self.require(self.permission(actor,company,'hr','view'))
        try:parse_j(month+'/01')
        except ValueError:raise DomainError('ماه به صورت ۱۴۰۵/۰۸ باشد.')
        month=normalize(month);rows=self.all_visible(actor,company=company);result=[]
        from penalties import number
        for employee in [r for r in rows if r['kind']=='employee']:
            person=employee['payload'];code=person['employee_code'];att=[r['payload'] for r in rows if r['kind']=='attendance' and r['payload'].get('employee_code')==code and normalize(r['payload'].get('date','')).startswith(month+'/')];approved=[a for a in att if a.get('status')=='approved'];minutes=sum((number(a.get('minutes') or 0) for a in approved),Decimal(0));days=len({a['date'] for a in approved});rate=number(person.get('hourly_rate') or 0);required=number(person.get('daily_minutes') or 480)*days
            leaves=[r['payload'] for r in rows if r['kind']=='leave' and r['payload'].get('employee_code')==code and r['payload'].get('status')=='approved' and normalize(r['payload'].get('start_date','')).startswith(month+'/')]
            result.append({'کد پرسنلی':code,'نام':person['title'],'ماه':month,'روز دارای تردد تأییدشده':days,'دقایق تأییدشده':str(minutes),'اضافه دقایق نسبت به موظفی روزهای ثبت‌شده':str(max(Decimal(0),minutes-required)),'دقایق در انتظار بررسی':str(sum((number(a.get('minutes') or 0) for a in att if a.get('status')!='approved'),Decimal(0))),'ساعت درخواست تأییدشده':str(sum((number(x.get('hours') or 0) for x in leaves),Decimal(0))),'برآورد دستمزد ساعتی ریال':str((minutes*rate/60).quantize(Decimal('1'))),'روش':'فقط کارکرد تأییدشده × نرخ ساعتی؛ بدون کسورات، مزایا و محاسبه قانونی حقوق'})
        return result

    def extract_document(self,actor,file_id):
        info=self.file_info(actor,file_id);record=self.record(info['record_id']);self.require(self.writable(actor,record));path=self.files/(file_id+'.bin');suffix=Path(info['name']).suffix.lower()
        if suffix=='.pdf':
            from pypdf import PdfReader
            reader=PdfReader(path)
            if len(reader.pages)>200:raise DomainError('حداکثر ۲۰۰ صفحه در هر سند پشتیبانی می‌شود.')
            text='\n'.join((p.extract_text() or '') for p in reader.pages)[:1000000]
        elif suffix in ('.txt','.csv'):
            raw=path.read_bytes()
            try:text=raw.decode('utf-8-sig')
            except UnicodeError:text=raw.decode('cp1256',errors='replace')
        elif suffix in ('.png','.jpg','.jpeg'):
            # Local-only optional OCR. This executable path is set by the host
            # administrator in an OS-local file, never received from an API call.
            config=self.root/'ocr-settings.json'
            try:
                settings=json.loads(config.read_text(encoding='utf-8'));exe=Path(settings['executable']).resolve()
                if exe.name.lower()!='tesseract.exe' or not exe.is_file():raise ValueError()
            except (OSError,ValueError,KeyError):raise DomainError('برای تصویر، موتور محلی Tesseract و زبان فارسی را روی میزبان نصب و در تنظیمات سرور معرفی کنید. PDF متنی بدون موتور جداگانه خوانده می‌شود.',422)
            import subprocess
            run=subprocess.run([str(exe),str(path),'stdout','-l',settings.get('language','fas+eng')],capture_output=True,timeout=90,creationflags=0x08000000 if os.name=='nt' else 0)
            if run.returncode:raise DomainError('خواندن تصویر انجام نشد؛ زبان OCR یا کیفیت تصویر را بررسی کنید.',422)
            text=run.stdout.decode('utf-8',errors='replace')[:1000000]
        else:raise DomainError('استخراج متن برای PDF، تصویر و متن پشتیبانی می‌شود.')
        if not text.strip():raise DomainError('متن قابل‌خواندن پیدا نشد؛ برای PDF اسکن‌شده از موتور OCR محلی استفاده کنید.',422)
        import re
        dates=list(dict.fromkeys(re.findall(r'[۱۲12][۰-۹0-9]{3}[/.-][۰-۹0-9]{1,2}[/.-][۰-۹0-9]{1,2}',text)))[:30]
        numbers=list(dict.fromkeys(re.findall(r'[۰-۹0-9][۰-۹0-9,٬]{4,}',text)))[:30]
        with self.db(True) as c:c.execute('UPDATE files SET extracted=? WHERE id=?',(text,file_id));self.audit(c,actor,record['company_id'],record['id'],'extract_document',after={'file':file_id})
        return dict(text=text,dates=dates,numbers=numbers,draft=True,source_file=file_id)

    def knowledge_search(self,actor,query,company=None):
        tokens=[normalize(t).casefold() for t in query.split() if len(t)>1][:20]
        if not tokens:raise DomainError('واژه یا پرسش را وارد کنید.')
        results=[]
        for row in self.all_visible(actor,company=company):
            pieces=[row['title'],packed(row['payload'])];files=self.file_list(actor,row['id'])
            pieces.extend(f.get('extracted','') for f in files)
            hay=normalize('\n'.join(pieces)).casefold();score=sum(hay.count(t) for t in tokens)
            if score:
                pos=min((hay.find(t) for t in tokens if t in hay),default=0);results.append(dict(id=row['id'],title=row['title'],kind=row['kind'],score=score,snippet=hay[max(0,pos-80):pos+400],files=[{'id':f['id'],'name':f['name']} for f in files if f.get('extracted')]))
        return sorted(results,key=lambda r:r['score'],reverse=True)[:30]

    def run_automations(self):
        today=date.today();ran=0
        with self.db() as c:rules=[dict(r,payload=json.loads(r['payload'])) for r in c.execute("SELECT * FROM records WHERE kind='automation' AND deleted=0")]
        for rule in rules:
            p=rule['payload']
            if not p.get('enabled'):continue
            try:
                actor=self.user(rule['owner_id']);company=rule['company_id'];self.require(self.role(actor,company) in APPROVERS)
                for task in self.all_visible(actor,'task',company):
                    tp=task['payload'];trigger=p.get('trigger');delay=int(Decimal(str(p.get('delay_days') or 0)));matched=False
                    if trigger=='overdue':matched=tp.get('status')!='completed' and (today-parse_j(tp['due_date']).togregorian()).days>=delay+1
                    elif trigger=='review':matched=tp.get('status')=='review' and (datetime.now(timezone.utc)-datetime.fromisoformat(task['updated'])).days>=delay
                    elif trigger=='attachment':matched=bool(self.file_list(actor,task['id'])) and (datetime.now(timezone.utc)-datetime.fromisoformat(task['updated'])).days>=delay
                    if not matched:continue
                    with self.db() as c:exists=c.execute('SELECT 1 FROM automation_runs WHERE rule_id=? AND target=? AND day=?',(rule['id'],task['id'],today.isoformat())).fetchone()
                    if exists:continue
                    receiver=p.get('target_user') or tp.get('assignee_id')
                    if not receiver:continue
                    self.publish(actor,dict(companies=[company],users=[receiver],title=p['title']+' · '+tp['title'],body=p['message'],require_ack=False))
                    with self.db(True) as c:c.execute('INSERT OR IGNORE INTO automation_runs VALUES(?,?,?)',(rule['id'],task['id'],today.isoformat()))
                    ran+=1
            except (DomainError,ValueError,KeyError):continue
        return ran

    def _teammate_ids(self,c,birthday_user):
        if birthday_user['global_role'] in ('group_admin','system_admin'):
            rows=c.execute('SELECT id FROM users WHERE active=1 AND id!=?',(birthday_user['id'],)).fetchall()
            return [r[0] for r in rows]
        cos={m['company_id'] for m in birthday_user.get('memberships',[]) if m['company_id']!='__shared_chat__'}
        if not cos:return []
        marks=','.join('?' for _ in cos)
        rows=c.execute(f"SELECT DISTINCT u.id FROM users u LEFT JOIN memberships m ON m.user_id=u.id WHERE u.active=1 AND u.id!=? AND (u.global_role IN ('group_admin','system_admin') OR m.company_id IN ({marks}))",(birthday_user['id'],*sorted(cos))).fetchall()
        return [r[0] for r in rows]

    def sync_user_birthday(self,actor,birthday_data,today_g=None):
        from birthday_service import parse_birthday
        try:parsed=parse_birthday(birthday_data)
        except ValueError as exc:raise DomainError(str(exc),400) from exc
        with self.db(True) as c:
            if parsed is None:
                c.execute('DELETE FROM user_birthdays WHERE user_id=?',(actor['id'],))
                c.execute('UPDATE birthday_reminders SET cancelled=1,updated=? WHERE birthday_user_id=? AND target_g>=?',(stamp(),actor['id'],(today_g or date.today()).isoformat()))
                self.audit(c,actor,None,actor['id'],'birthday_clear',after={'cleared':True})
            else:
                c.execute('INSERT OR REPLACE INTO user_birthdays VALUES(?,?,?,?,?,?)',(actor['id'],parsed['year'],parsed['month'],parsed['day'],parsed['missing_day_policy'],stamp()))
                self.audit(c,actor,None,actor['id'],'birthday_save',after=parsed)
        self.reconcile_birthday_reminders(today_g=today_g)
        return parsed

    def reconcile_birthday_reminders(self,today_g=None):
        from birthday_service import next_birthday_occurrence,build_reminder_copy
        today_g=today_g or date.today();ts=stamp()
        with self.db(True) as c:
            rows=[dict(r) for r in c.execute("SELECT b.*,u.fullname,u.global_role FROM user_birthdays b JOIN users u ON u.id=b.user_id WHERE u.active=1")]
            active_users=set()
            for r in rows:
                active_users.add(r['user_id'])
                b_user=self.user(r['user_id'])
                birth=dict(year=r['birth_year'],month=r['birth_month'],day=r['birth_day'],missing_day_policy=r['missing_policy'])
                occ=next_birthday_occurrence(birth,today_g=today_g,default_policy=r['missing_policy'])
                if not occ:
                    c.execute('UPDATE birthday_reminders SET cancelled=1,updated=? WHERE birthday_user_id=? AND target_g>=?',(ts,r['user_id'],today_g.isoformat()))
                    continue
                resolved_jd,target_g,days_until,celeb_year=occ
                if 1<=days_until<=3:
                    date_str=f'{resolved_jd.year:04d}/{resolved_jd.month:02d}/{resolved_jd.day:02d}'
                    title,body=build_reminder_copy(r['fullname'],birth,days_until)
                    recipients=self._teammate_ids(c,b_user)
                    recipient_set=set(recipients)
                    existing=[dict(x) for x in c.execute('SELECT * FROM birthday_reminders WHERE birthday_user_id=? AND birthday_year=?',(r['user_id'],celeb_year))]
                    for old in existing:
                        if old['recipient_id'] not in recipient_set or old['recipient_id']==r['user_id']:
                            c.execute('UPDATE birthday_reminders SET cancelled=1,updated=? WHERE id=?',(ts,old['id']))
                    for rec_id in recipients:
                        if rec_id==r['user_id']:continue
                        prev=next((x for x in existing if x['recipient_id']==rec_id),None)
                        if prev is None:
                            c.execute('INSERT INTO birthday_reminders(id,birthday_user_id,recipient_id,birthday_year,birthday_date_j,target_g,title,body,cancelled,shown,opened,created,updated) VALUES(?,?,?,?,?,?,?,?,0,NULL,NULL,?,?)',(uid(),r['user_id'],rec_id,celeb_year,date_str,target_g.isoformat(),title,body,ts,ts))
                        else:
                            date_changed=prev['birthday_date_j']!=date_str or bool(prev['cancelled'])
                            c.execute('UPDATE birthday_reminders SET birthday_date_j=?,target_g=?,title=?,body=?,cancelled=0,shown=?,opened=?,updated=? WHERE id=?',(date_str,target_g.isoformat(),title,body,None if date_changed else prev['shown'],None if date_changed else prev['opened'],ts,prev['id']))
                    c.execute('UPDATE birthday_reminders SET cancelled=1,updated=? WHERE birthday_user_id=? AND birthday_year!=? AND target_g>=?',(ts,r['user_id'],celeb_year,today_g.isoformat()))
                else:
                    c.execute('UPDATE birthday_reminders SET cancelled=1,updated=? WHERE birthday_user_id=? AND target_g>=?',(ts,r['user_id'],today_g.isoformat()))
            if active_users:
                marks=','.join('?' for _ in active_users)
                c.execute(f'UPDATE birthday_reminders SET cancelled=1,updated=? WHERE birthday_user_id NOT IN ({marks}) AND target_g>=?',(ts,*active_users,today_g.isoformat()))
            else:
                c.execute('UPDATE birthday_reminders SET cancelled=1,updated=? WHERE target_g>=?',(ts,today_g.isoformat()))

    def birthdays_snapshot(self,actor,today_g=None):
        from birthday_service import next_birthday_occurrence,format_birthday_day_month_fa
        today_g=today_g or date.today()
        self.reconcile_birthday_reminders(today_g=today_g)
        with self.db() as c:
            own_row=c.execute('SELECT * FROM user_birthdays WHERE user_id=?',(actor['id'],)).fetchone()
            own_birthday=dict(year=own_row['birth_year'],month=own_row['birth_month'],day=own_row['birth_day'],date_jalali=f"{own_row['birth_year']:04d}/{own_row['birth_month']:02d}/{own_row['birth_day']:02d}",missing_day_policy=own_row['missing_policy']) if own_row else None
            teammate_ids={u['id']:u for u in self.users(actor)}
            b_rows=[dict(r) for r in c.execute('SELECT b.*,u.fullname FROM user_birthdays b JOIN users u ON u.id=b.user_id WHERE u.active=1')]
            reminders=[dict(r) for r in c.execute('SELECT * FROM birthday_reminders WHERE recipient_id=? AND birthday_user_id!=? AND cancelled=0 AND opened IS NULL ORDER BY target_g ASC',(actor['id'],actor['id']))]
        birthdays=[]
        for r in b_rows:
            if r['user_id'] not in teammate_ids and r['user_id']!=actor['id']:continue
            birth=dict(year=r['birth_year'],month=r['birth_month'],day=r['birth_day'],missing_day_policy=r['missing_policy'])
            occ=next_birthday_occurrence(birth,today_g=today_g,default_policy=r['missing_policy'])
            if not occ:continue
            resolved_jd,target_g,days_until,celeb_year=occ
            birthdays.append(dict(user_id=r['user_id'],fullname=r['fullname'],birth_month=r['birth_month'],birth_day=r['birth_day'],label_fa=format_birthday_day_month_fa(birth),missing_day_policy=r['missing_policy'],next_date_j=f'{resolved_jd.year:04d}/{resolved_jd.month:02d}/{resolved_jd.day:02d}',next_date_g=target_g.isoformat(),days_until=days_until,celebration_year=celeb_year,is_self=(r['user_id']==actor['id'])))
        birthdays.sort(key=lambda x:x['days_until'])
        return dict(own_birthday=own_birthday,birthdays=birthdays,reminders=reminders)

    def birthday_ack(self,actor,id,action='opened'):
        self.require(action in ('shown','opened'),'وضعیت یادآور تولد معتبر نیست.')
        ts=stamp()
        with self.db(True) as c:
            row=c.execute('SELECT * FROM birthday_reminders WHERE id=? AND recipient_id=?',(id,actor['id'])).fetchone()
            self.require(bool(row),'یادآور تولد پیدا نشد.')
            if action=='opened':
                c.execute('UPDATE birthday_reminders SET opened=COALESCE(opened,?),shown=COALESCE(shown,?),updated=? WHERE id=?',(ts,ts,ts,id))
            else:
                c.execute('UPDATE birthday_reminders SET shown=COALESCE(shown,?),updated=? WHERE id=?',(ts,ts,id))
        return {'ok':True}
