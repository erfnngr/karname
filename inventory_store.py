"""Company-scoped inventory storage. Stock is stored as exact decimal text."""
import uuid
from decimal import Decimal
from inventory_logic import quantity

def init_inventory(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS stock_groups(id TEXT PRIMARY KEY,company_id TEXT NOT NULL REFERENCES companies(id),parent_id TEXT REFERENCES stock_groups(id),name TEXT NOT NULL, UNIQUE(company_id,parent_id,name));
    CREATE TABLE IF NOT EXISTS stock_products(id TEXT PRIMARY KEY,company_id TEXT NOT NULL REFERENCES companies(id),group_id TEXT NOT NULL REFERENCES stock_groups(id),code TEXT NOT NULL,name TEXT NOT NULL,unit TEXT NOT NULL,purchase_price TEXT NOT NULL,sale_price TEXT NOT NULL,balance TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,active INTEGER NOT NULL DEFAULT 1, UNIQUE(company_id,code));
    CREATE TABLE IF NOT EXISTS stock_movements(id TEXT PRIMARY KEY,company_id TEXT NOT NULL,product_id TEXT NOT NULL REFERENCES stock_products(id),delta TEXT NOT NULL,balance_after TEXT NOT NULL,reason TEXT NOT NULL,actor TEXT NOT NULL,created TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS stock_movement_product ON stock_movements(company_id,product_id,created);
    CREATE TABLE IF NOT EXISTS stock_request_ids(user_id TEXT NOT NULL,request_id TEXT NOT NULL,company_id TEXT NOT NULL,digest TEXT NOT NULL,product_id TEXT NOT NULL REFERENCES stock_products(id),PRIMARY KEY(user_id,request_id));
    ''')

class InventoryStoreMixin:
    def inventory_archive(self,actor,company,id,version):
        self.require_module(actor,company,'clients','delete')
        with self.db(True) as c:
            row=c.execute('SELECT * FROM stock_products WHERE id=? AND company_id=? AND active=1',(id,company)).fetchone()
            self.require(bool(row),'کالا پیدا نشد.')
            self.require(version is not None and int(version)==row['version'],'کالا تغییر کرده است؛ دوباره بارگذاری کنید.')
            c.execute('UPDATE stock_products SET active=0,version=version+1 WHERE id=?',(id,))
            self.audit(c,actor,company,id,'archive',before={'kind':'stock_product','name':row['name'],'balance':row['balance']})
        return {'ok':True}
    def inventory_invoice_change(self,c,actor,company,invoice_id,before,after,before_deleted=False,after_deleted=False):
        from org_store import stamp
        from inventory_logic import stock_changes
        for product_id,delta in stock_changes(before,after,before_deleted,after_deleted).items():
            row=c.execute('SELECT * FROM stock_products WHERE id=? AND company_id=?',(product_id,company)).fetchone()
            self.require(bool(row),'کالای فاکتور در این شرکت پیدا نشد.')
            value=Decimal(row['balance'])+delta
            self.require(abs(value)<=Decimal('1000000000'),'موجودی از محدوده مجاز خارج است.')
            c.execute('UPDATE stock_products SET balance=?,version=version+1 WHERE id=?',(str(value),product_id))
            c.execute('INSERT INTO stock_movements VALUES(?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,company,product_id,str(delta),str(value),'فاکتور '+invoice_id,actor['id'],stamp()))
    def inventory_list(self,actor,company):
        self.require_module(actor,company,'clients','view')
        with self.db() as c:
            groups=[dict(r) for r in c.execute('SELECT * FROM stock_groups WHERE company_id=? ORDER BY name',(company,))]
            products=[dict(r) for r in c.execute('SELECT * FROM stock_products WHERE company_id=? ORDER BY name',(company,))]
        return {'groups':groups,'products':products}

    def inventory_group(self,actor,company,name,parent_id=None):
        self.require_module(actor,company,'clients','create');name=str(name).strip()
        self.require(bool(name) and len(name)<=150,'نام گروه معتبر نیست.')
        with self.db(True) as c:
            if parent_id:
                parent=c.execute('SELECT * FROM stock_groups WHERE id=? AND company_id=?',(parent_id,company)).fetchone()
                self.require(bool(parent) and parent['parent_id'] is None,'گروه اصلی معتبر نیست.')
            duplicate=c.execute('SELECT 1 FROM stock_groups WHERE company_id=? AND parent_id IS ? AND name=?',(company,parent_id,name)).fetchone()
            self.require(not duplicate,'نام گروه تکراری است.')
            id=uuid.uuid4().hex;c.execute('INSERT INTO stock_groups VALUES(?,?,?,?)',(id,company,parent_id,name));self.audit(c,actor,company,id,'create',after={'kind':'stock_group','name':name})
        return {'id':id}

    def inventory_product(self,actor,company,payload,id=None,version=None):
        self.require_module(actor,company,'clients','edit' if id else 'create')
        from org_store import stamp
        name=str(payload.get('name','')).strip();code=str(payload.get('code','')).strip();unit=str(payload.get('unit','عدد')).strip()
        self.require(bool(name) and bool(code) and bool(unit) and max(map(len,(name,code,unit)))<=150,'نام، کد و واحد کالا لازم است.')
        limit=Decimal('1000000000000000000');purchase=quantity(payload.get('purchase_price','0'),limit);sale=quantity(payload.get('sale_price','0'),limit)
        self.require(purchase==purchase.to_integral_value() and sale==sale.to_integral_value(),'قیمت به ریال باید عدد صحیح باشد.')
        group=payload.get('group_id');request_id=payload.get('request_id');digest=None
        if request_id:
            import re,hashlib,json
            self.require(not id and isinstance(request_id,str) and bool(re.fullmatch('[0-9a-f]{32}',request_id)),'شناسه درخواست معتبر نیست.')
            digest=hashlib.sha256(json.dumps(dict(payload,company=company),ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        with self.db(True) as c:
            if request_id:
                prior=c.execute('SELECT r.digest,p.id,p.code FROM stock_request_ids r JOIN stock_products p ON p.id=r.product_id WHERE r.user_id=? AND r.request_id=?',(actor['id'],request_id)).fetchone()
                if prior:
                    self.require(prior['digest']==digest,'شناسه درخواست قبلاً برای کالای دیگری استفاده شده است.')
                    return {'id':prior['id'],'code':prior['code'],'duplicate':True}
            g=c.execute('SELECT * FROM stock_groups WHERE id=? AND company_id=?',(group,company)).fetchone();self.require(bool(g) and bool(g['parent_id']),'گروه فرعی معتبر را انتخاب کنید.')
            if id:
                old=c.execute('SELECT * FROM stock_products WHERE id=? AND company_id=?',(id,company)).fetchone();self.require(bool(old),'کالا پیدا نشد.')
                self.require(version is not None and int(version)==old['version'],'کالا تغییر کرده است؛ دوباره بارگذاری کنید.')
                c.execute('UPDATE stock_products SET name=?,code=?,unit=?,group_id=?,purchase_price=?,sale_price=?,version=version+1 WHERE id=?',(name,code,unit,group,str(purchase),str(sale),id))
            else:
                if code=='__AUTO__':
                    used=[str(r['code']) for r in c.execute('SELECT code FROM stock_products WHERE company_id=?',(company,))]
                    code=str(max([999]+[int(v) for v in used if v.isascii() and v.isdigit() and len(v)<=18])+1)
                id=uuid.uuid4().hex;c.execute('INSERT INTO stock_products VALUES(?,?,?,?,?,?,?,?,?,1,1)',(id,company,group,code,name,unit,str(purchase),str(sale),'0'))
            self.audit(c,actor,company,id,'edit' if version else 'create',after={'kind':'stock_product','name':name})
            if request_id:c.execute('INSERT INTO stock_request_ids VALUES(?,?,?,?,?)',(actor['id'],request_id,company,digest,id))
        return {'id':id,'code':code}

    def inventory_adjust(self,actor,company,id,version,balance,reason):
        self.require_module(actor,company,'clients','edit')
        from org_store import stamp
        reason=str(reason).strip();self.require(bool(reason) and len(reason)<=500,'دلیل اصلاح موجودی لازم است.')
        try:
            value=Decimal(str(balance));self.require(value.is_finite() and abs(value)<=Decimal('1000000000'),'موجودی معتبر نیست.')
        except Exception:raise ValueError('موجودی معتبر نیست.') from None
        with self.db(True) as c:
            row=c.execute('SELECT * FROM stock_products WHERE id=? AND company_id=?',(id,company)).fetchone();self.require(bool(row),'کالا پیدا نشد.');self.require(version is not None and int(version)==row['version'],'موجودی تغییر کرده است؛ دوباره بارگذاری کنید.')
            delta=value-Decimal(row['balance']);c.execute('UPDATE stock_products SET balance=?,version=version+1 WHERE id=?',(str(value),id));c.execute('INSERT INTO stock_movements VALUES(?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,company,id,str(delta),str(value),reason,actor['id'],stamp()));self.audit(c,actor,company,id,'edit',before={'balance':row['balance']},after={'balance':str(value)},reason=reason)
        return {'balance':str(value),'version':int(version)+1}
