"""Read-only checks on already authorized records; findings are not conclusions."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from storage import normalize,parse_j

def inspect(records,finance,company):
    findings=[];clients=defaultdict(list);transactions=defaultdict(list)
    def add(kind,title,reason,identifier=''):
        findings.append(dict(kind=kind,title=str(title or '')[:150],reason=reason,id=identifier))
    for record in records:
        if record.get('deleted') or record.get('company_id')!=company:continue
        p=record.get('payload') or {};kind=record.get('kind');title=p.get('title') or p.get('number') or record.get('id','')
        if kind=='client':
            for field,label in [('national_id','شناسه ملی'),('national_code','کد ملی'),('phone','تلفن')]:
                value=normalize(p.get(field,'')).replace(' ','').replace('-','')
                if value:clients[(field,value,label)].append((record.get('id'),title))
        if kind=='invoice' and p.get('status') in ('issued','paid'):
            if not p.get('client_id'):add('فاکتور',title,'طرف حساب ثبت نشده است.',record.get('id'))
            totals=p.get('totals') or {};summary=p.get('settlement_summary')
            try:
                if not isinstance(summary,dict):raise ValueError()
                total=Decimal(str(totals['total']));paid=Decimal(str(summary['received']))+Decimal(str(record.get('allocated_transactions','0')))
                if total.is_finite() and paid.is_finite() and paid>total:add('فاکتور',title,'مبلغ پرداخت‌شده بیش از جمع فاکتور است؛ سند را بررسی کنید.',record.get('id'))
            except (KeyError,InvalidOperation,TypeError,ValueError):add('فاکتور',title,'جمع یا اطلاعات تسویه کامل و قابل بررسی نیست.',record.get('id'))
    for (_,_,label),items in clients.items():
        if len(items)>1:
            for id,title in items:add('مشتری',title,label+' در چند پرونده تکرار شده است؛ پیش از ادغام بررسی کنید.',id)
    for check in finance.get('checks',[]):
        if not check.get('number') or not check.get('bank'):add('چک',check.get('number') or check.get('document_no'),'شماره یا بانک چک ناقص است.',check.get('id'))
        try:parse_j(check.get('due_date',''))
        except (ValueError,TypeError):add('چک',check.get('number') or check.get('document_no'),'تاریخ سررسید ثبت نشده یا معتبر نیست.',check.get('id'))
    for item in finance.get('transactions',[]):
        if item.get('source') not in (None,'transaction'):continue
        key=tuple(str(item.get(k) or '') for k in ('date','direction','amount','bank_id','reason'))
        if all(key[:3]):transactions[key].append(item)
    for items in transactions.values():
        if len(items)>1:
            for item in items:add('سند مالی',item.get('document_no'),'سند مشابه دیگری با همین تاریخ و مبلغ وجود دارد؛ ممکن است ثبت تکراری نباشد.',item.get('id'))
    return findings
