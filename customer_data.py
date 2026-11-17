"""Customer master data, explicit invoice arithmetic and saved buyer snapshots."""
import copy,re
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP,ROUND_FLOOR
from storage import normalize,parse_j

TYPES=['حقوقی','حقیقی','مشارکت مدنی','اتباع غیرایرانی','نامشخص']
GROUPS=[('هویت', [('title','نام نمایشی / نام مشتری','text'),('customer_type','نوع شخص','type'),('legal_name','نام ثبتی شرکت / کسب‌وکار','text'),('first_name','نام','text'),('last_name','نام خانوادگی','text'),('national_id','شماره / شناسه ملی یا کد فراگیر','digits'),('registration_no','شماره ثبت','text'),('customer_code','کد مشتری در شرکت','text'),('status','وضعیت پرونده','status')]),
 ('اطلاعات مالیاتی',[('economic_code','شماره اقتصادی','digits'),('tax_file_id','شماره پرونده مالیاتی','text'),('tax_office','واحد / اداره مالیاتی','text'),('tax_branch','کد شعبه','text'),('activity','حوزه فعالیت','text'),('tax_status','وضعیت ثبت‌نام مالیاتی','text'),('fiscal_year','سال مالی','text')]),
 ('تماس و نشانی',[('contact','نام رابط / مسئول شرکت','text'),('contact_role','سمت رابط','text'),('phone','تلفن ثابت','text'),('mobile','شماره همراه','text'),('email','ایمیل','text'),('website','وب‌سایت','text'),('country','کشور','text'),('province','استان','text'),('city','شهر','text'),('postal_code','کد پستی','digits'),('address','نشانی کامل','multiline')]),
 ('اطلاعات تکمیلی',[('bank','نام بانک','text'),('account_name','صاحب حساب','text'),('account_no','شماره حساب','text'),('iban','شماره شبا','text'),('assignee_id','مسئول پیگیری','user'),('notes','یادداشت پرونده','multiline')])]
FIELDS={k:(label,kind) for _,fields in GROUPS for k,label,kind in fields}
BUYER_FIELDS=['title','customer_type','legal_name','first_name','last_name','national_id','registration_no','economic_code','tax_file_id','tax_branch','country','province','city','postal_code','address','phone','mobile','email','contact','contact_role','customer_code']

def customer(value):
    if not isinstance(value,dict):raise ValueError('اطلاعات مشتری معتبر نیست.')
    result=copy.deepcopy(value)
    for key,(label,kind) in FIELDS.items():
        raw=result.get(key,'')
        if raw is None:raw=''
        if not isinstance(raw,str):raise ValueError(label+' باید متن باشد.')
        raw=raw.strip()
        if len(raw)>(8000 if key=='notes' else 2000 if key=='address' else 500):raise ValueError(label+' بیش از حد طولانی است.')
        if kind=='digits' and raw:
            raw=normalize(raw).replace(' ','').replace('-','')
            if not re.fullmatch('[0-9]+',raw):raise ValueError(label+' را با عدد وارد کنید.')
        result[key]=raw
    if not result['title']:raise ValueError('نام مشتری را وارد کنید.')
    result['customer_type']=result.get('customer_type') or 'نامشخص';result['status']=result.get('status') or 'active'
    if result['customer_type'] not in TYPES or result['status'] not in ('active','archived'):raise ValueError('نوع یا وضعیت مشتری معتبر نیست.')
    if result['postal_code'] and len(result['postal_code'])!=10:raise ValueError('کد پستی باید ۱۰ رقم باشد؛ اگر هنوز ندارید آن را خالی بگذارید.')
    if result['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',result['email']):raise ValueError('نشانی ایمیل معتبر نیست.')
    return result

def buyer_snapshot(value):return {key:str(value.get(key,'')).strip() for key in BUYER_FIELDS}

def missing_fields(value):
    required=[('title','نام مشتری'),('customer_type','نوع شخص'),('economic_code','شماره اقتصادی'),('postal_code','کد پستی'),('address','نشانی')]
    if value.get('customer_type') in ('حقیقی','حقوقی','اتباع غیرایرانی'):required.append(('national_id','شماره / شناسه ملی'))
    return [label for key,label in required if not value.get(key) or (key=='customer_type' and value[key]=='نامشخص')]

def number(value,name,maximum=Decimal('1000000000000000000')):
    try:
        if isinstance(value,bool):raise ValueError()
        d=Decimal(normalize(str(value)).replace(',','').replace('٬',''))
        if not d.is_finite() or d<0 or d>maximum:raise ValueError()
        return d
    except (ValueError,InvalidOperation):raise ValueError(name+' معتبر نیست.') from None

def invoice(value):
    if not isinstance(value,dict):raise ValueError('اطلاعات فاکتور معتبر نیست.')
    p=copy.deepcopy(value);lines=p.get('lines',[])
    if not isinstance(lines,list) or not 1<=len(lines)<=100:raise ValueError('یک تا صد ردیف کالا یا خدمت وارد کنید.')
    result=[];totals=dict(subtotal=Decimal(0),discount=Decimal(0),tax=Decimal(0),total=Decimal(0));rounding=lambda n:n.quantize(Decimal(1),rounding=ROUND_HALF_UP)
    for line in lines:
        if not isinstance(line,dict):raise ValueError('ردیف فاکتور معتبر نیست.')
        title=str(line.get('description','')).strip()
        if not title or len(title)>1000:raise ValueError('شرح کالا یا خدمت را وارد کنید.')
        qty=number(line.get('quantity',1),'تعداد',Decimal('1000000000'));price=number(line.get('unit_price',0),'مبلغ واحد');discount=number(line.get('discount_fixed',line.get('discount',0)),'تخفیف');discount_rate=number(line.get('discount_rate',0),'درصد تخفیف',Decimal(100));rate=number(line.get('tax_rate',0),'نرخ مالیات',Decimal(100))
        if qty<=0:raise ValueError('تعداد باید بیشتر از صفر باشد.')
        subtotal=rounding(qty*price)
        if discount_rate and discount:raise ValueError('برای هر ردیف تخفیف مبلغی یا درصدی را انتخاب کنید.')
        if discount_rate:discount=rounding(subtotal*discount_rate/100)
        if subtotal>Decimal('1000000000000000000') or discount>subtotal:raise ValueError('مبلغ یا تخفیف ردیف معتبر نیست.')
        discount=rounding(discount);tax=rounding((subtotal-discount)*rate/100);total=subtotal-discount+tax
        item=dict(description=title,quantity=str(qty),unit=str(line.get('unit','عدد'))[:40],unit_price=str(price),discount=str(discount),tax_rate=str(rate),subtotal=str(subtotal),tax=str(tax),total=str(total))
        if discount_rate:item.update(discount_rate=str(discount_rate),discount_fixed='0')
        product_id=line.get('product_id')
        if product_id:
            if not isinstance(product_id,str) or len(product_id)>128:raise ValueError('شناسه کالا معتبر نیست.')
            item['product_id']=product_id
            # These snapshots are recomputed or retained by the server on save;
            # preserving them here also allows saved invoices to render locally.
            for key in ('product_code','unit_cost_snapshot','gross_profit'):
                if key in line:item[key]=str(line[key])[:150]
        result.append(item)
    mode=p.get('invoice_discount_mode','amount');discount_value=number(p.get('invoice_discount_value',0),'تخفیف کل',Decimal(100) if mode=='percent' else Decimal('1000000000000000000'))
    if mode not in ('amount','percent'):raise ValueError('نوع تخفیف کل معتبر نیست.')
    bases=[Decimal(x['subtotal'])-Decimal(x['discount']) for x in result];base=sum(bases,Decimal(0));overall=rounding(base*discount_value/100 if mode=='percent' else discount_value)
    if overall>base:raise ValueError('تخفیف کل از مبلغ پس از تخفیف ردیف‌ها بیشتر است.')
    shares=[Decimal(0)]*len(result)
    if overall and base:
        exact=[overall*b/base for b in bases];shares=[x.to_integral_value(rounding=ROUND_FLOOR) for x in exact];left=int(overall-sum(shares,Decimal(0)))
        for i in sorted(range(len(result)),key=lambda i:(-(exact[i]-shares[i]),i))[:left]:shares[i]+=1
    for item,share in zip(result,shares):
        subtotal=Decimal(item['subtotal']);discount=Decimal(item['discount']);tax=rounding((subtotal-discount-share)*Decimal(item['tax_rate'])/100);total=subtotal-discount-share+tax
        item.update(invoice_discount_share=str(share),tax=str(tax),total=str(total))
        for key,val in [('subtotal',subtotal),('discount',discount+share),('tax',tax),('total',total)]:totals[key]+=val
    charge=rounding(number(p.get('additional_charge',0),'هزینه اضافی'));charge_rate=number(p.get('charge_tax_rate',0),'نرخ مالیات هزینه',Decimal(100));charge_tax=rounding(charge*charge_rate/100)
    totals['tax']+=charge_tax;totals['total']+=charge+charge_tax
    if totals['total']>Decimal('1000000000000000000'):raise ValueError('مبلغ کل فاکتور بیش از حد مجاز است.')
    if charge:totals.update(additional_charge=charge,charge_tax=charge_tax)
    if 'invoice_discount_mode' in p or 'invoice_discount_value' in p:p.update(invoice_discount_mode=mode,invoice_discount_value=str(discount_value),invoice_discount_amount=str(overall))
    if 'additional_charge' in p or 'charge_tax_rate' in p:p.update(additional_charge=str(charge),charge_tax_rate=str(charge_rate))
    p['lines']=result;p['totals']={k:str(v) for k,v in totals.items()};p['number']=str(p.get('number','')).strip()
    if not p['number'] or len(p['number'])>80:raise ValueError('شماره داخلی فاکتور را وارد کنید.')
    parse_j(p.get('date',''))
    if p.get('due_date'):parse_j(p['due_date'])
    p.setdefault('document_type','پیش‌فاکتور');p.setdefault('status','draft');p.setdefault('title',p['document_type']+' '+p['number'])
    if p['document_type'] not in ('پیش‌فاکتور','فاکتور فروش','فاکتور خرید','برگشت از فروش','برگشت از خرید') or p['status'] not in ('draft','issued','paid','cancelled'):raise ValueError('نوع یا وضعیت فاکتور معتبر نیست.')
    return p
