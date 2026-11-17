"""Bank accounts and checks scoped to one company."""
import uuid,json,hashlib,re
from settlement_logic import amount,validate
from storage import parse_j

def init_finance(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS finance_bank(id TEXT PRIMARY KEY,company_id TEXT NOT NULL REFERENCES companies(id),name TEXT NOT NULL,account_no TEXT NOT NULL,iban TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS finance_check(id TEXT PRIMARY KEY,company_id TEXT NOT NULL REFERENCES companies(id),number TEXT NOT NULL,bank TEXT NOT NULL,amount TEXT NOT NULL,due_date TEXT NOT NULL,description TEXT NOT NULL,invoice_id TEXT,created TEXT NOT NULL,UNIQUE(company_id,number,bank));
    CREATE TABLE IF NOT EXISTS finance_sequence(company_id TEXT NOT NULL REFERENCES companies(id),kind TEXT NOT NULL,last_number INTEGER NOT NULL,PRIMARY KEY(company_id,kind));
    CREATE TABLE IF NOT EXISTS finance_transactions(id TEXT PRIMARY KEY,company_id TEXT NOT NULL REFERENCES companies(id),document_no TEXT NOT NULL,direction TEXT NOT NULL,method TEXT NOT NULL,bank_id TEXT,customer_id TEXT,amount TEXT NOT NULL,date TEXT NOT NULL,reason TEXT NOT NULL,version INTEGER NOT NULL,created TEXT NOT NULL, UNIQUE(company_id,document_no));
    CREATE TABLE IF NOT EXISTS finance_bank_matches(id TEXT PRIMARY KEY,company_id TEXT NOT NULL,bank_id TEXT NOT NULL,external_ref TEXT NOT NULL,transaction_id TEXT NOT NULL,date TEXT NOT NULL,amount TEXT NOT NULL,direction TEXT NOT NULL,created TEXT NOT NULL,actor TEXT NOT NULL,UNIQUE(company_id,bank_id,external_ref),UNIQUE(company_id,transaction_id));
    CREATE TABLE IF NOT EXISTS finance_receipts(id TEXT PRIMARY KEY,company_id TEXT NOT NULL,transaction_id TEXT NOT NULL REFERENCES finance_transactions(id),name TEXT NOT NULL,size INTEGER NOT NULL,sha256 TEXT NOT NULL,created TEXT NOT NULL,actor TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS finance_check_transfers(id TEXT PRIMARY KEY,company_id TEXT NOT NULL,check_id TEXT NOT NULL REFERENCES finance_check(id),recipient_id TEXT NOT NULL,invoice_id TEXT,created TEXT NOT NULL,actor TEXT NOT NULL,UNIQUE(company_id,check_id));
    CREATE TABLE IF NOT EXISTS finance_allocations(transaction_id TEXT NOT NULL REFERENCES finance_transactions(id),invoice_id TEXT NOT NULL REFERENCES records(id),company_id TEXT NOT NULL,amount TEXT NOT NULL,PRIMARY KEY(transaction_id,invoice_id));
    CREATE TABLE IF NOT EXISTS finance_request_ids(user_id TEXT NOT NULL,request_id TEXT NOT NULL,company_id TEXT NOT NULL,digest TEXT NOT NULL,transaction_id TEXT NOT NULL REFERENCES finance_transactions(id),PRIMARY KEY(user_id,request_id));
    CREATE TABLE IF NOT EXISTS finance_check_request_ids(user_id TEXT NOT NULL,request_id TEXT NOT NULL,company_id TEXT NOT NULL,digest TEXT NOT NULL,check_id TEXT NOT NULL REFERENCES finance_check(id),PRIMARY KEY(user_id,request_id));
    CREATE TABLE IF NOT EXISTS finance_bank_request_ids(user_id TEXT NOT NULL,request_id TEXT NOT NULL,company_id TEXT NOT NULL,digest TEXT NOT NULL,bank_id TEXT NOT NULL REFERENCES finance_bank(id),PRIMARY KEY(user_id,request_id));
    ''')
    if 'direction' not in {r[1] for r in c.execute('PRAGMA table_info(finance_check)')}:
        c.execute("ALTER TABLE finance_check ADD COLUMN direction TEXT NOT NULL DEFAULT 'received'")
    if 'document_no' not in {r[1] for r in c.execute('PRAGMA table_info(finance_check)')}:
        c.execute("ALTER TABLE finance_check ADD COLUMN document_no TEXT NOT NULL DEFAULT ''")
    if 'version' not in {r[1] for r in c.execute('PRAGMA table_info(finance_check)')}:
        c.execute('ALTER TABLE finance_check ADD COLUMN version INTEGER NOT NULL DEFAULT 1')
    if 'status' not in {r[1] for r in c.execute('PRAGMA table_info(finance_check)')}:
        c.execute("ALTER TABLE finance_check ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'")
    if 'cleared_date' not in {r[1] for r in c.execute('PRAGMA table_info(finance_check)')}:
        c.execute("ALTER TABLE finance_check ADD COLUMN cleared_date TEXT NOT NULL DEFAULT ''")
    if 'invoice_id' not in {r[1] for r in c.execute('PRAGMA table_info(finance_transactions)')}:
        c.execute('ALTER TABLE finance_transactions ADD COLUMN invoice_id TEXT')
    if 'category' not in {r[1] for r in c.execute('PRAGMA table_info(finance_transactions)')}:
        c.execute("ALTER TABLE finance_transactions ADD COLUMN category TEXT NOT NULL DEFAULT ''")
    if 'cleared_date' not in {r[1] for r in c.execute('PRAGMA table_info(finance_check_transfers)')}:
        c.execute("ALTER TABLE finance_check_transfers ADD COLUMN cleared_date TEXT NOT NULL DEFAULT ''")
    c.execute("INSERT OR IGNORE INTO finance_allocations(transaction_id,invoice_id,company_id,amount) SELECT id,invoice_id,company_id,amount FROM finance_transactions WHERE invoice_id IS NOT NULL AND invoice_id!=''")
    migrate_finance_permissions(c)

def migrate_finance_permissions(c):
    """Preserve effective customer-module finance rights once on upgrade."""
    from permission_policy import baseline_allowed
    inserted=c.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('finance_acl_v1','done')").rowcount
    if not inserted:return
    for row in c.execute('SELECT user_id,company_id,role,permissions FROM memberships').fetchall():
        permissions=json.loads(row['permissions'] or '{}');role=row['role'];changed=False
        old_view=permissions.get('module.clients.view',baseline_allowed(role,'clients','view'))
        for action in ('view','create','edit','export'):
            key='module.finance.'+action
            if key in permissions:continue
            previous=bool(old_view and permissions.get('module.clients.'+action,baseline_allowed(role,'clients',action)))
            default=bool(baseline_allowed(role,'finance','view') and baseline_allowed(role,'finance',action))
            if previous!=default:permissions[key]=previous;changed=True
        if changed:c.execute('UPDATE memberships SET permissions=? WHERE user_id=? AND company_id=?',(json.dumps(permissions,ensure_ascii=False),row['user_id'],row['company_id']))

def proposed_number(c,company,kind):
    """Return the next number without reserving it."""
    row=c.execute('SELECT last_number FROM finance_sequence WHERE company_id=? AND kind=?',(company,kind)).fetchone()
    current=row['last_number'] if row else 99
    for r in c.execute("SELECT payload FROM records WHERE company_id=? AND kind='invoice'",(company,)):
        p=json.loads(r['payload']);value=p.get('document_no','') if kind=='document' else p.get('number','') if p.get('document_type')==kind else ''
        if str(value).isdigit():current=max(current,int(value))
    return current+1

def next_number(c,company,kind):
    """Allocate under the caller's BEGIN IMMEDIATE; preserve legacy numbers."""
    current=proposed_number(c,company,kind)
    c.execute('INSERT INTO finance_sequence VALUES(?,?,?) ON CONFLICT(company_id,kind) DO UPDATE SET last_number=excluded.last_number',(company,kind,current))
    return str(current)

class FinanceStoreMixin:
    def finance_next_invoice_number(self,actor,company,kind):
        self.require_module(actor,company,'clients','invoice')
        self.require(kind in ('پیش‌فاکتور','فاکتور فروش','فاکتور خرید','برگشت از فروش','برگشت از خرید'),'نوع فاکتور معتبر نیست.')
        with self.db() as c:return {'number':str(proposed_number(c,company,kind))}
    def finance_check_alerts(self,actor,company):
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','view')
        with self.db() as c:
            return [dict(r) for r in c.execute("SELECT f.id,f.number,f.due_date,f.direction,f.status,CASE WHEN t.id IS NULL THEN 0 ELSE 1 END AS transferred FROM finance_check f LEFT JOIN finance_check_transfers t ON t.company_id=f.company_id AND t.check_id=f.id WHERE f.company_id=? AND f.status IN ('pending','deposited') ORDER BY f.due_date",(company,))]
    def finance_transfer_check(self,actor,company,check_id,version,recipient_id,invoice_id=None):
        """Endorse one received check, atomically, without duplicating its value."""
        from org_store import DomainError,stamp
        from decimal import Decimal
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','edit')
        if invoice_id:
            visible={r['id'] for r in self.all_visible(actor,'invoice',company)}
            self.require(invoice_id in visible,'فاکتور مقصد در دسترس نیست.')
        with self.db(True) as c:
            check=c.execute('SELECT * FROM finance_check WHERE id=? AND company_id=?',(check_id,company)).fetchone();self.require(bool(check),'چک پیدا نشد.')
            if version is None or int(version)!=check['version']:raise DomainError('چک تغییر کرده است؛ دوباره بارگذاری کنید.',409)
            self.require(check['direction']=='received' and check['status']=='pending','فقط چک دریافتی در انتظار را می‌توان خرج کرد.')
            self.require(not c.execute('SELECT 1 FROM finance_check_transfers WHERE company_id=? AND check_id=?',(company,check_id)).fetchone(),'چک قبلاً خرج شده است.')
            if check['invoice_id']:
                source=c.execute('SELECT * FROM records WHERE id=? AND company_id=? AND deleted=0',(check['invoice_id'],company)).fetchone();self.require(bool(source),'فاکتور مبدأ پیدا نشد.');source=dict(source);source['payload']=json.loads(source['payload']);self.require(self.writable(actor,source),'دسترسی ویرایش فاکتور مبدأ لازم است.')
            recipient=c.execute("SELECT * FROM records WHERE id=? AND company_id=? AND kind='client' AND deleted=0",(recipient_id,company)).fetchone();self.require(bool(recipient),'طرف حساب در این شرکت پیدا نشد.');recipient=dict(recipient);recipient['payload']=json.loads(recipient['payload']);self.require(self.readable(actor,recipient),'طرف حساب در دسترس نیست.')
            if invoice_id:
                record=c.execute("SELECT * FROM records WHERE id=? AND company_id=? AND kind='invoice' AND deleted=0",(invoice_id,company)).fetchone();self.require(bool(record),'فاکتور مقصد پیدا نشد.')
                record=dict(record);record['payload']=json.loads(record['payload']);p=record['payload']
                self.require(self.writable(actor,record) and p.get('client_id')==recipient_id and p.get('document_type') in ('فاکتور خرید','برگشت از فروش') and p.get('status')=='issued','فاکتور مقصد یا طرف حساب معتبر نیست.')
                summary=p.get('settlement_summary');self.require(isinstance(summary,dict),'تسویه فاکتور مقصد نیاز به بررسی دارد.')
                transactions=sum((Decimal(r['amount']) for r in c.execute('SELECT amount FROM finance_allocations WHERE company_id=? AND invoice_id=?',(company,invoice_id))),Decimal(0))
                transfers=sum((Decimal(r['amount']) for r in c.execute("SELECT f.amount FROM finance_check_transfers t JOIN finance_check f ON f.id=t.check_id WHERE t.company_id=? AND t.invoice_id=? AND f.status IN ('pending','deposited','cleared')",(company,invoice_id))),Decimal(0))
                self.require(transactions+transfers+amount(check['amount'])<=amount(summary.get('unallocated','0')),'مبلغ چک از مانده قابل تخصیص فاکتور بیشتر است.')
            id=uuid.uuid4().hex;c.execute('INSERT INTO finance_check_transfers(id,company_id,check_id,recipient_id,invoice_id,created,actor) VALUES(?,?,?,?,?,?,?)',(id,company,check_id,recipient_id,invoice_id or None,stamp(),actor['id']));c.execute('UPDATE finance_check SET version=version+1 WHERE id=?',(check_id,));self.audit(c,actor,company,check_id,'check_transfer',after={'transfer_id':id,'recipient_id':recipient_id,'invoice_id':invoice_id})
        return {'id':id,'version':check['version']+1}

    def finance_untransfer_check(self,actor,company,id,version):
        from org_store import DomainError
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','edit')
        with self.db(True) as c:
            row=c.execute('SELECT t.*,f.version,f.status,f.invoice_id AS source_invoice FROM finance_check_transfers t JOIN finance_check f ON f.id=t.check_id WHERE t.id=? AND t.company_id=?',(id,company)).fetchone();self.require(bool(row),'خرج چک پیدا نشد.')
            if version is None or int(version)!=row['version']:raise DomainError('چک تغییر کرده است؛ دوباره بارگذاری کنید.',409)
            self.require(row['status']=='pending','فقط خرج چک در انتظار قابل برگشت است؛ ابتدا وضعیت آن را بررسی کنید.')
            for invoice_id in (row['source_invoice'],row['invoice_id']):
                if invoice_id:
                    record=c.execute('SELECT * FROM records WHERE id=? AND company_id=? AND deleted=0',(invoice_id,company)).fetchone();self.require(bool(record),'فاکتور متصل پیدا نشد.');record=dict(record);record['payload']=json.loads(record['payload']);self.require(self.writable(actor,record),'دسترسی ویرایش فاکتور متصل لازم است.')
            c.execute('DELETE FROM finance_check_transfers WHERE id=?',(id,));c.execute('UPDATE finance_check SET version=version+1 WHERE id=?',(row['check_id'],));self.audit(c,actor,company,row['check_id'],'check_untransfer',before={'transfer_id':id,'recipient_id':row['recipient_id'],'invoice_id':row['invoice_id']})
        return {'ok':True,'version':row['version']+1}
    def finance_receipt_list(self,actor,company,transaction_id):
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','view')
        with self.db() as c:
            self.require(bool(c.execute('SELECT 1 FROM finance_transactions WHERE id=? AND company_id=?',(transaction_id,company)).fetchone()),'سند مالی پیدا نشد.')
            return [dict(r) for r in c.execute('SELECT id,name,size,created FROM finance_receipts WHERE company_id=? AND transaction_id=? ORDER BY created DESC',(company,transaction_id))]

    def finance_receipt_add(self,actor,company,transaction_id,name,data):
        import base64,hashlib
        from pathlib import Path
        from org_store import stamp,DomainError
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','edit')
        name=Path(str(name).replace('\\','/')).name[:180];self.require(Path(name).suffix.lower() in ('.png','.jpg','.jpeg','.pdf','.xlsx','.csv'),'قالب رسید پشتیبانی نمی‌شود.')
        self.require(isinstance(data,str) and len(data)<=14*1024*1024,'حجم رسید بیش از حد مجاز است.')
        try:raw=base64.b64decode(data,validate=True)
        except (ValueError,TypeError):raise DomainError('فایل رسید معتبر نیست.') from None
        self.require(0<len(raw)<=10*1024*1024,'حجم رسید باید حداکثر ۱۰ مگابایت باشد.')
        id=uuid.uuid4().hex;path=self.files/(id+'.bin');written=False
        try:
            with self.db(True) as c:
                self.require(bool(c.execute('SELECT 1 FROM finance_transactions WHERE id=? AND company_id=?',(transaction_id,company)).fetchone()),'سند مالی پیدا نشد.')
                self.require(c.execute('SELECT COUNT(*) FROM finance_receipts WHERE company_id=? AND transaction_id=?',(company,transaction_id)).fetchone()[0]<20,'حداکثر ۲۰ رسید برای هر سند مجاز است.')
                with path.open('xb') as out:
                    written=True;out.write(raw)
                c.execute('INSERT INTO finance_receipts VALUES(?,?,?,?,?,?,?,?)',(id,company,transaction_id,name,len(raw),hashlib.sha256(raw).hexdigest(),stamp(),actor['id']))
                self.audit(c,actor,company,id,'finance_receipt_add',after={'transaction_id':transaction_id,'name':name,'size':len(raw)})
        except Exception:
            if written:path.unlink(missing_ok=True)
            raise
        return {'id':id,'name':name,'size':len(raw)}

    def finance_receipt_get(self,actor,company,id):
        import base64,hashlib
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','view')
        with self.db() as c:row=c.execute('SELECT * FROM finance_receipts WHERE id=? AND company_id=?',(id,company)).fetchone()
        self.require(bool(row),'رسید پیدا نشد.');raw=(self.files/(id+'.bin')).read_bytes();self.require(len(raw)==row['size'] and hashlib.sha256(raw).hexdigest()==row['sha256'],'فایل رسید آسیب دیده است.')
        return {'name':row['name'],'data':base64.b64encode(raw).decode()}

    def finance_unmatch_bank(self,actor,company,id):
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','edit')
        with self.db(True) as c:
            row=c.execute('SELECT * FROM finance_bank_matches WHERE id=? AND company_id=?',(id,company)).fetchone();self.require(bool(row),'تطبیق پیدا نشد.')
            c.execute('DELETE FROM finance_bank_matches WHERE id=? AND company_id=?',(id,company));self.audit(c,actor,company,id,'bank_unmatch',before={'transaction_id':row['transaction_id'],'external_ref':row['external_ref']})
        return {'ok':True}
    def finance_match_bank(self,actor,company,bank_id,external_ref,transaction_id,date,value,direction):
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','edit')
        from org_store import stamp,DomainError
        from storage import normalize,jformat
        external_ref=normalize(str(external_ref)).strip();self.require(bool(external_ref) and len(external_ref)<=150,'شناسه تراکنش بانکی لازم است.')
        day=normalize(jformat(parse_j(date)));value=amount(value)
        self.require(direction in ('income','expense') and value>0,'اطلاعات تراکنش معتبر نیست.')
        with self.db(True) as c:
            row=c.execute('SELECT * FROM finance_transactions WHERE id=? AND company_id=?',(transaction_id,company)).fetchone()
            self.require(bool(row) and row['bank_id']==bank_id and row['direction']==direction and amount(row['amount'])==value and normalize(jformat(parse_j(row['date'])))==day,'سند با اطلاعات فایل مطابقت ندارد یا تغییر کرده است.')
            self.require(not c.execute('SELECT 1 FROM finance_bank_matches WHERE company_id=? AND (transaction_id=? OR (bank_id=? AND external_ref=?))',(company,transaction_id,bank_id,external_ref)).fetchone(),'این تراکنش بانکی یا سند قبلاً تطبیق داده شده است.')
            id=uuid.uuid4().hex;c.execute('INSERT INTO finance_bank_matches VALUES(?,?,?,?,?,?,?,?,?,?)',(id,company,bank_id,external_ref,transaction_id,day,str(value),direction,stamp(),actor['id']));self.audit(c,actor,company,id,'bank_match',after={'transaction_id':transaction_id,'external_ref':external_ref})
        return {'id':id,'ok':True}
    def finance_check_history(self,actor,company,id):
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','view')
        with self.db() as c:
            self.require(bool(c.execute('SELECT 1 FROM finance_check WHERE id=? AND company_id=?',(id,company)).fetchone()),'چک پیدا نشد.')
            rows=[dict(r) for r in c.execute("SELECT a.created,a.action,a.before_json,a.after_json,COALESCE(u.fullname,'کاربر پیشین') AS actor FROM audit a LEFT JOIN users u ON u.id=a.actor WHERE a.company_id=? AND a.target=? ORDER BY a.id DESC LIMIT 200",(company,id))]
        for row in rows:
            row['before']=json.loads(row.pop('before_json') or '{}');row['after']=json.loads(row.pop('after_json') or '{}')
        return rows
    def finance_list(self,actor,company):
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','view')
        with self.db() as c:
            banks=[dict(r) for r in c.execute('SELECT * FROM finance_bank WHERE company_id=? ORDER BY name',(company,))]
            checks=[dict(r) for r in c.execute('SELECT * FROM finance_check WHERE company_id=? ORDER BY due_date',(company,))]
            transactions=[dict(r) for r in c.execute('SELECT * FROM finance_transactions WHERE company_id=? ORDER BY created DESC',(company,))]
            matches=[dict(r) for r in c.execute('SELECT * FROM finance_bank_matches WHERE company_id=? ORDER BY created DESC',(company,))]
            transfers=[dict(r) for r in c.execute('SELECT t.*,f.amount,f.status,f.number,f.due_date,f.version AS check_version FROM finance_check_transfers t JOIN finance_check f ON f.id=t.check_id WHERE t.company_id=? ORDER BY t.created DESC',(company,))]
            allocations=[dict(r) for r in c.execute('SELECT transaction_id,invoice_id,amount FROM finance_allocations WHERE company_id=?',(company,))]
        from decimal import Decimal
        allocations_by_tx={};allocated_by_invoice={};cleared_by_invoice={};pending_by_invoice={}
        for a in allocations:
            allocations_by_tx.setdefault(a['transaction_id'],[]).append({'invoice_id':a['invoice_id'],'amount':a['amount']});allocated_by_invoice[a['invoice_id']]=allocated_by_invoice.get(a['invoice_id'],Decimal(0))+Decimal(a['amount'])
        for transfer in transfers:
            target=transfer['invoice_id']
            if not target:continue
            mapping=cleared_by_invoice if transfer['status']=='cleared' else pending_by_invoice if transfer['status'] in ('pending','deposited') else None
            if mapping is not None:mapping[target]=mapping.get(target,Decimal(0))+Decimal(transfer['amount'])
        for transaction in transactions:transaction['allocations']=allocations_by_tx.get(transaction['id'],[])
        invoice_documents=self.all_visible(actor,'invoice',company)
        for invoice in invoice_documents:
            linked=allocated_by_invoice.get(invoice['id'],Decimal(0))+cleared_by_invoice.get(invoice['id'],Decimal(0));pending=pending_by_invoice.get(invoice['id'],Decimal(0))
            summary=invoice['payload'].get('settlement_summary')
            if isinstance(summary,dict):invoice['allocated_transactions']=str(linked);invoice['allocated_pending_checks']=str(pending);invoice['remaining_after_allocations']=str(Decimal(summary.get('uncollected','0'))-linked)
        balances={};incomplete=set()
        # A partial employee view must never be presented as a company-wide balance.
        if self.role(actor,company) in ('group_admin','company_manager','finance') and self.permission(actor,company,'work','view'):
            from decimal import Decimal
            for invoice in invoice_documents:
                p=invoice['payload'];kind=p.get('document_type');customer=p.get('client_id');summary=p.get('settlement_summary',{})
                if not customer or p.get('status') not in ('issued','paid') or kind not in ('فاکتور فروش','فاکتور خرید','برگشت از فروش','برگشت از خرید'):continue
                if 'settlement_summary' not in p:incomplete.add(customer);continue
                sign=Decimal(1) if kind in ('فاکتور فروش','برگشت از خرید') else Decimal(-1)
                balance=Decimal(str(p.get('totals',{}).get('total','0')))-Decimal(str(summary.get('received','0')))
                balances[customer]=balances.get(customer,Decimal(0))+sign*balance
            for tx in transactions:
                if tx.get('customer_id'):
                    sign=Decimal(-1) if tx['direction']=='income' else Decimal(1)
                    balances[tx['customer_id']]=balances.get(tx['customer_id'],Decimal(0))+sign*Decimal(tx['amount'])
            for transfer in transfers:
                if transfer['status']=='cleared':balances[transfer['recipient_id']]=balances.get(transfer['recipient_id'],Decimal(0))+Decimal(transfer['amount'])
        return {'banks':banks,'checks':checks,'check_transfers':transfers,'transactions':transactions,'bank_matches':matches,'invoice_documents':invoice_documents,'balances':{k:str(v) for k,v in balances.items()},'incomplete_balances':list(incomplete)}
    def finance_transaction(self,actor,company,payload,id=None,version=None):
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','edit' if id else 'create')
        from org_store import stamp,DomainError
        from decimal import Decimal
        direction=payload.get('direction');method=payload.get('method');value=amount(payload.get('amount'));date=payload.get('date','');reason=str(payload.get('reason','')).strip();category=str(payload.get('category','')).strip();bank=payload.get('bank_id') or None;customer=payload.get('customer_id') or None;legacy_invoice=payload.get('invoice_id') or None
        request_id=payload.get('request_id');digest=None
        if request_id:
            import re,hashlib
            self.require(not id and isinstance(request_id,str) and bool(re.fullmatch('[0-9a-f]{32}',request_id)),'شناسه درخواست معتبر نیست.')
            digest=hashlib.sha256(json.dumps(dict(payload,company=company),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        allocations=payload.get('allocations') if 'allocations' in payload else ([{'invoice_id':legacy_invoice,'amount':str(value)}] if legacy_invoice else [])
        self.require(isinstance(allocations,list) and len(allocations)<=50,'فهرست تخصیص معتبر نیست.');prepared=[];seen=set()
        for part in allocations:
            self.require(isinstance(part,dict) and isinstance(part.get('invoice_id'),str) and bool(part['invoice_id']) and part['invoice_id'] not in seen,'فاکتورهای تخصیص باید معتبر و غیرتکراری باشند.')
            share=amount(part.get('amount'));self.require(share>0,'مبلغ تخصیص باید مثبت باشد.');seen.add(part['invoice_id']);prepared.append((part['invoice_id'],share))
        self.require(sum((share for _,share in prepared),Decimal(0))<=value,'جمع تخصیص‌ها از مبلغ سند بیشتر است.')
        if prepared:
            visible={r['id'] for r in self.all_visible(actor,'invoice',company)}
            self.require(all(key in visible for key,_ in prepared),'فاکتور در دسترس نیست.')
        invoice_id=prepared[0][0] if len(prepared)==1 and prepared[0][1]==value else None
        self.require(direction in ('income','expense') and method in ('cash','card','pos','paya','satna','pol','internal','cash_deposit','other') and value>0 and bool(reason) and len(reason)<=500 and len(category)<=100,'اطلاعات دریافت یا پرداخت معتبر نیست.')
        parse_j(date)
        with self.db(True) as c:
            if request_id:
                prior=c.execute('SELECT r.digest,t.id,t.document_no FROM finance_request_ids r JOIN finance_transactions t ON t.id=r.transaction_id WHERE r.user_id=? AND r.request_id=?',(actor['id'],request_id)).fetchone()
                if prior:
                    self.require(prior['digest']==digest,'شناسه درخواست برای سند دیگری استفاده شده است.')
                    return {'id':prior['id'],'document_no':prior['document_no'],'duplicate':True}
            for target,share in prepared:
                row=c.execute("SELECT payload FROM records WHERE id=? AND company_id=? AND kind='invoice' AND deleted=0",(target,company)).fetchone();self.require(bool(row),'فاکتور پیدا نشد.')
                invoice=json.loads(row['payload']);kind=invoice.get('document_type');expected='income' if kind in ('فاکتور فروش','برگشت از خرید') else 'expense'
                self.require(kind in ('فاکتور فروش','فاکتور خرید','برگشت از فروش','برگشت از خرید') and invoice.get('status') in ('issued','paid') and direction==expected and customer and invoice.get('client_id')==customer,'نوع سند یا طرف حساب با فاکتور مطابقت ندارد.')
                summary=invoice.get('settlement_summary');self.require(isinstance(summary,dict),'تسویه این فاکتور ابتدا باید بررسی شود.')
                linked=sum((Decimal(r['amount']) for r in c.execute('SELECT amount FROM finance_allocations WHERE company_id=? AND invoice_id=? AND transaction_id!=?',(company,target,id or ''))),Decimal(0))
                transfers=sum((Decimal(r['amount']) for r in c.execute("SELECT f.amount FROM finance_check_transfers t JOIN finance_check f ON f.id=t.check_id WHERE t.company_id=? AND t.invoice_id=? AND f.status IN ('pending','deposited','cleared')",(company,target))),Decimal(0))
                self.require(linked+transfers+share<=amount(summary.get('unallocated','0')),'مبلغ از مانده قابل تخصیص فاکتور بیشتر است.')
            if method!='cash':self.require(bool(bank) and bool(c.execute('SELECT 1 FROM finance_bank WHERE id=? AND company_id=?',(bank,company)).fetchone()),'حساب بانکی معتبر را انتخاب کنید.')
            else:bank=None
            if customer:self.require(bool(c.execute("SELECT 1 FROM records WHERE id=? AND company_id=? AND kind='client' AND deleted=0",(customer,company)).fetchone()),'مشتری در این شرکت پیدا نشد.')
            if id:
                old=c.execute('SELECT * FROM finance_transactions WHERE id=? AND company_id=?',(id,company)).fetchone();self.require(bool(old),'سند مالی پیدا نشد.')
                if version is None or int(version)!=old['version']:raise DomainError('سند تغییر کرده است؛ دوباره بارگذاری کنید.',409)
                self.require(not c.execute('SELECT 1 FROM finance_bank_matches WHERE company_id=? AND transaction_id=?',(company,id)).fetchone(),'سند تطبیق‌شده قابل ویرایش نیست؛ ابتدا تطبیق را بردارید.')
                for prior in c.execute('SELECT invoice_id FROM finance_allocations WHERE transaction_id=? AND company_id=?',(id,company)).fetchall():
                    previous=c.execute('SELECT payload FROM records WHERE id=? AND company_id=? AND deleted=0',(prior['invoice_id'],company)).fetchone()
                    self.require(bool(previous) and json.loads(previous['payload']).get('status')!='paid','برای ویرایش پرداخت، ابتدا وضعیت فاکتور را از تسویه‌شده تغییر دهید.')
                doc=old['document_no'];c.execute('UPDATE finance_transactions SET direction=?,method=?,bank_id=?,customer_id=?,amount=?,date=?,reason=?,invoice_id=?,category=?,version=version+1 WHERE id=?',(direction,method,bank,customer,str(value),date,reason,invoice_id,category,id))
            else:
                id=uuid.uuid4().hex;doc=next_number(c,company,'document');c.execute('INSERT INTO finance_transactions(id,company_id,document_no,direction,method,bank_id,customer_id,amount,date,reason,version,created,invoice_id,category) VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?,?)',(id,company,doc,direction,method,bank,customer,str(value),date,reason,stamp(),invoice_id,category))
            c.execute('DELETE FROM finance_allocations WHERE transaction_id=? AND company_id=?',(id,company))
            for target,share in prepared:c.execute('INSERT INTO finance_allocations VALUES(?,?,?,?)',(id,target,company,str(share)))
            self.audit(c,actor,company,id,'edit' if version else 'create',after={'kind':'financial_transaction','document_no':doc,'allocations':[{'invoice_id':target,'amount':str(share)} for target,share in prepared]},reason=reason)
            if request_id:c.execute('INSERT INTO finance_request_ids VALUES(?,?,?,?,?)',(actor['id'],request_id,company,digest,id))
        return {'id':id,'document_no':doc}
    def finance_bank_add(self,actor,company,name,account_no='',iban='',request_id=None):
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','edit');name=str(name).strip();account_no=str(account_no).strip();iban=str(iban).strip()
        self.require(bool(name) and max(map(len,(name,account_no,iban)))<=150,'اطلاعات حساب معتبر نیست.')
        if request_id:self.require(isinstance(request_id,str) and bool(re.fullmatch('[0-9a-f]{32}',request_id)),'شناسه درخواست معتبر نیست.')
        digest=hashlib.sha256(json.dumps(dict(company=company,name=name,account_no=account_no,iban=iban),sort_keys=True,ensure_ascii=False).encode()).hexdigest() if request_id else None
        id=uuid.uuid4().hex
        with self.db(True) as c:
            if request_id:
                prior=c.execute('SELECT r.digest,r.company_id,b.id FROM finance_bank_request_ids r JOIN finance_bank b ON b.id=r.bank_id WHERE r.user_id=? AND r.request_id=?',(actor['id'],request_id)).fetchone()
                if prior:
                    self.require(prior['digest']==digest and prior['company_id']==company,'شناسه درخواست قبلاً برای حساب دیگری استفاده شده است.');return {'id':prior['id'],'duplicate':True}
            c.execute('INSERT INTO finance_bank VALUES(?,?,?,?,?)',(id,company,name,account_no,iban));self.audit(c,actor,company,id,'create',after={'kind':'bank_account','name':name})
            if request_id:c.execute('INSERT INTO finance_bank_request_ids VALUES(?,?,?,?,?)',(actor['id'],request_id,company,digest,id))
        return {'id':id}
    def finance_check_add(self,actor,company,number,bank,value,due_date,description='',direction='received',request_id=None):
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','edit');number=str(number).strip();bank=str(bank).strip();description=str(description).strip();value=amount(value)
        self.require(bool(number) and bool(bank) and value>0 and direction in ('received','issued') and max(map(len,(number,bank,description)))<=500,'اطلاعات چک معتبر نیست.');parse_j(due_date)
        if request_id:self.require(isinstance(request_id,str) and bool(re.fullmatch('[0-9a-f]{32}',request_id)),'شناسه درخواست معتبر نیست.')
        digest=hashlib.sha256(json.dumps(dict(company=company,number=number,bank=bank,value=str(value),due_date=due_date,description=description,direction=direction),sort_keys=True,ensure_ascii=False).encode()).hexdigest() if request_id else None
        from org_store import stamp
        id=uuid.uuid4().hex
        with self.db(True) as c:
            if request_id:
                prior=c.execute('SELECT r.digest,r.company_id,f.id,f.document_no FROM finance_check_request_ids r JOIN finance_check f ON f.id=r.check_id WHERE r.user_id=? AND r.request_id=?',(actor['id'],request_id)).fetchone()
                if prior:
                    self.require(prior['digest']==digest and prior['company_id']==company,'شناسه درخواست قبلاً برای چک دیگری استفاده شده است.');return {'id':prior['id'],'document_no':prior['document_no'],'duplicate':True}
            document_no=next_number(c,company,'document')
            c.execute('INSERT INTO finance_check(id,company_id,number,bank,amount,due_date,description,invoice_id,created,direction,document_no) VALUES(?,?,?,?,?,?,?,NULL,?,?,?)',(id,company,number,bank,str(value),due_date,description,stamp(),direction,document_no));self.audit(c,actor,company,id,'create',after={'kind':'check','number':number,'direction':direction,'document_no':document_no})
            if request_id:c.execute('INSERT INTO finance_check_request_ids VALUES(?,?,?,?,?)',(actor['id'],request_id,company,digest,id))
        return {'id':id,'document_no':document_no}
    def finance_check_edit(self,actor,company,id,version,number,bank,value,due_date,description='',direction='received'):
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','edit')
        from org_store import DomainError
        number=str(number).strip();bank=str(bank).strip();description=str(description).strip();value=amount(value);parse_j(due_date)
        self.require(bool(number) and bool(bank) and value>0 and direction in ('received','issued') and max(map(len,(number,bank,description)))<=500,'اطلاعات چک معتبر نیست.')
        with self.db(True) as c:
            row=c.execute('SELECT * FROM finance_check WHERE id=? AND company_id=?',(id,company)).fetchone();self.require(bool(row),'چک پیدا نشد.')
            if version is None or int(version)!=row['version']:raise DomainError('چک تغییر کرده است؛ فهرست را تازه‌سازی کنید.',409)
            if row['invoice_id']:self.require(value==amount(row['amount']) and direction==row['direction'],'مبلغ و نوع چک متصل به فاکتور قابل تغییر نیست؛ ابتدا تسویه فاکتور را اصلاح کنید.')
            if c.execute('SELECT 1 FROM finance_check_transfers WHERE company_id=? AND check_id=?',(company,id)).fetchone():self.require(value==amount(row['amount']) and direction==row['direction'],'مبلغ و نوع چک خرج‌شده قابل تغییر نیست.')
            c.execute('UPDATE finance_check SET number=?,bank=?,amount=?,due_date=?,description=?,direction=?,version=version+1 WHERE id=?',(number,bank,str(value),due_date,description,direction,id));self.audit(c,actor,company,id,'edit',before={'number':row['number'],'amount':row['amount']},after={'number':number,'amount':str(value)})
        return {'id':id,'document_no':row['document_no'],'version':row['version']+1}
    def finance_check_status(self,actor,company,id,version,status):
        self.require_module(actor,company,'clients','view');self.require_module(actor,company,'finance','edit')
        from org_store import DomainError,packed,stamp
        self.require(status in ('pending','deposited','cleared','returned'),'وضعیت چک معتبر نیست.')
        with self.db(True) as c:
            row=c.execute('SELECT * FROM finance_check WHERE id=? AND company_id=?',(id,company)).fetchone();self.require(bool(row),'چک پیدا نشد.')
            if version is None or int(version)!=row['version']:raise DomainError('چک تغییر کرده است؛ فهرست را تازه‌سازی کنید.',409)
            transfer=c.execute('SELECT * FROM finance_check_transfers WHERE company_id=? AND check_id=?',(company,id)).fetchone()
            if transfer:self.require(status!='deposited','چک خرج‌شده قابل واگذاری به حساب بانک این شرکت نیست.')
            from storage import today_j,jformat,normalize
            check_cleared=normalize(jformat(today_j())) if status=='cleared' and row['status']!='cleared' else row['cleared_date'] if status=='cleared' else ''
            c.execute('UPDATE finance_check SET status=?,cleared_date=?,version=version+1 WHERE id=?',(status,check_cleared,id))
            if transfer:
                cleared=normalize(jformat(today_j())) if status=='cleared' and row['status']!='cleared' else transfer['cleared_date'] if status=='cleared' else ''
                c.execute('UPDATE finance_check_transfers SET cleared_date=? WHERE id=?',(cleared,transfer['id']))
            if row['invoice_id']:
                record=c.execute('SELECT * FROM records WHERE id=? AND deleted=0',(row['invoice_id'],)).fetchone();self.require(bool(record),'فاکتور مرتبط پیدا نشد.')
                invoice=json.loads(record['payload'])
                scoped=dict(record,payload=invoice);self.require(self.writable(actor,scoped),'برای تغییر وضعیت چک متصل، دسترسی ویرایش فاکتور لازم است.')
                if status!='cleared' and invoice.get('status')=='paid':invoice['status']='issued'
                self.finance_invoice_change(c,actor,company,row['invoice_id'],invoice)
                c.execute('UPDATE records SET payload=?,version=version+1,updated=? WHERE id=?',(packed(invoice),stamp(),row['invoice_id']))
            if transfer and transfer['invoice_id']:
                record=c.execute('SELECT * FROM records WHERE id=? AND company_id=? AND deleted=0',(transfer['invoice_id'],company)).fetchone();self.require(bool(record),'فاکتور مقصد پیدا نشد.')
                invoice=json.loads(record['payload']);scoped=dict(record,payload=invoice);self.require(self.writable(actor,scoped),'برای تغییر وضعیت چک خرج‌شده، دسترسی ویرایش فاکتور مقصد لازم است.')
                if status!='cleared' and invoice.get('status')=='paid':invoice['status']='issued'
                self.finance_invoice_change(c,actor,company,transfer['invoice_id'],invoice)
                c.execute('UPDATE records SET payload=?,version=version+1,updated=? WHERE id=?',(packed(invoice),stamp(),transfer['invoice_id']))
            self.audit(c,actor,company,id,'edit',before={'status':row['status']},after={'status':status})
        return {'id':id,'status':status,'version':row['version']+1}
    def finance_invoice_change(self,c,actor,company,id,payload,deleted=False):
        attached=c.execute('SELECT t.customer_id,t.direction,a.amount FROM finance_allocations a JOIN finance_transactions t ON t.id=a.transaction_id WHERE a.company_id=? AND a.invoice_id=?',(company,id)).fetchall()
        transfers=c.execute('SELECT t.recipient_id,f.amount,f.status FROM finance_check_transfers t JOIN finance_check f ON f.id=t.check_id WHERE t.company_id=? AND t.invoice_id=?',(company,id)).fetchall()
        sourced=c.execute('SELECT f.id FROM finance_check f JOIN finance_check_transfers t ON t.check_id=f.id AND t.company_id=f.company_id WHERE f.company_id=? AND f.invoice_id=?',(company,id)).fetchall()
        if sourced:
            line_ids={line.get('check_id') for line in (payload.get('settlement') if isinstance(payload.get('settlement'),list) else []) if isinstance(line,dict) and line.get('kind')=='check'}
            previous=c.execute('SELECT payload FROM records WHERE id=? AND company_id=?',(id,company)).fetchone();old=json.loads(previous['payload']) if previous else {}
            self.require(not deleted and payload.get('client_id')==old.get('client_id') and payload.get('status') in ('issued','paid') and all(r['id'] in line_ids for r in sourced),'ابتدا خرج چک متصل به این فاکتور را بررسی کنید.')
        if transfers:
            self.require(not deleted and payload.get('document_type') in ('فاکتور خرید','برگشت از فروش') and payload.get('status') in ('issued','paid') and all(r['recipient_id']==payload.get('client_id') for r in transfers),'ابتدا خرج چک متصل به فاکتور را بررسی کنید.')
        if attached:
            self.require(not deleted,'ابتدا تخصیص پرداخت‌های متصل را حذف کنید.')
            expected='income' if payload.get('document_type') in ('فاکتور فروش','برگشت از خرید') else 'expense'
            self.require(payload.get('document_type') in ('فاکتور فروش','فاکتور خرید','برگشت از فروش','برگشت از خرید') and payload.get('status') in ('issued','paid') and all(r['customer_id']==payload.get('client_id') and r['direction']==expected for r in attached),'ابتدا پرداخت‌های متصل را اصلاح کنید.')
        lines=[] if deleted else payload.get('settlement',[])
        if not isinstance(lines,list):raise ValueError('تسویه معتبر نیست.')
        oldrow=c.execute('SELECT payload FROM records WHERE id=? AND company_id=?',(id,company)).fetchone();previous=json.loads(oldrow['payload']).get('settlement',[]) if oldrow else []
        if lines!=previous:self.require_module(actor,company,'finance','edit')
        if lines and (payload.get('document_type') not in ('فاکتور فروش','فاکتور خرید','برگشت از فروش','برگشت از خرید') or payload.get('status') not in ('issued','paid')):raise ValueError('تسویه تنها برای فاکتور ثبت‌شده امکان دارد.')
        totals=validate(payload.get('totals',{}).get('total','0'),lines)
        from decimal import Decimal
        paid=Decimal(totals['received']);pending=Decimal(0)
        for line in lines:
            if line['kind']=='bank':
                bank=c.execute('SELECT * FROM finance_bank WHERE id=? AND company_id=?',(line['bank_account_id'],company)).fetchone()
                self.require(bool(bank),'حساب متعلق به شرکت نیست.')
                payload.setdefault('seller_snapshot',{}).update(account_no=bank['account_no'],iban=bank['iban'])
            if line['kind']=='check':
                row=c.execute('SELECT * FROM finance_check WHERE id=? AND company_id=?',(line['check_id'],company)).fetchone()
                self.require(bool(row) and row['invoice_id'] in (None,id),'چک در دسترس نیست یا به فاکتور دیگری متصل است.')
                expected='issued' if payload.get('document_type') in ('فاکتور خرید','برگشت از فروش') else 'received'
                self.require(row['direction']==expected,'نوع چک دریافتی یا پرداختی با نوع فاکتور همخوان نیست.')
                self.require(amount(row['amount'])==amount(line['amount']),'مبلغ چک با مبلغ ثبت‌شده یکسان نیست.')
                self.require(row['status']!='returned' or row['invoice_id']==id,'چک برگشتی برای تسویه جدید قابل انتخاب نیست.')
                if row['status']=='cleared':paid+=amount(line['amount'])
                elif row['status'] in ('pending','deposited'):pending+=amount(line['amount'])
        total=amount(payload.get('totals',{}).get('total','0'))
        totals.update(received=str(paid),pending_checks=str(pending),unallocated=str(total-paid-pending),uncollected=str(total-paid))
        transferred=sum((amount(r['amount']) for r in transfers if r['status'] in ('pending','deposited','cleared')),Decimal(0))
        if attached or transfers:
            self.require(sum((amount(r['amount']) for r in attached),Decimal(0))+transferred<=total-paid-pending,'مبلغ فاکتور از پرداخت‌های متصل کمتر است.')
        allocated=sum((amount(r['amount']) for r in attached),Decimal(0))
        allocated+=sum((amount(r['amount']) for r in transfers if r['status']=='cleared'),Decimal(0))
        if not deleted and 'settlement' in payload and payload.get('status')=='paid' and amount(totals['uncollected'])>allocated:
            raise ValueError('فاکتور فقط پس از وصول کامل قابل ثبت به‌عنوان تسویه‌شده است.')
        selected={line['check_id'] for line in lines if line['kind']=='check'}
        for r in c.execute('SELECT id FROM finance_check WHERE company_id=? AND invoice_id=?',(company,id)).fetchall():
            if r['id'] not in selected:c.execute('UPDATE finance_check SET invoice_id=NULL,version=version+1 WHERE id=?',(r['id'],))
        for line in lines:
            if line['kind']=='check':c.execute('UPDATE finance_check SET invoice_id=?,version=version+1 WHERE id=? AND invoice_id IS NULL',(id,line['check_id']))
        if not deleted:payload['settlement_summary']=totals
