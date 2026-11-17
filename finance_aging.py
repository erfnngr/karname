"""Overdue invoice report; missing maturity dates remain explicitly unknown."""
from datetime import date
from decimal import Decimal
from storage import parse_j


def aging(invoices, today=None):
    today=today or date.today();rows=[]
    kinds={'فاکتور فروش':'دریافتنی','برگشت از خرید':'دریافتنی','فاکتور خرید':'پرداختنی','برگشت از فروش':'پرداختنی'}
    for item in invoices:
        p=item['payload'];kind=kinds.get(p.get('document_type'))
        if not kind or p.get('status') not in ('issued','paid'):continue
        summary=p.get('settlement_summary')
        if not isinstance(summary,dict):continue
        remaining=Decimal(str(item.get('remaining_after_allocations',summary.get('uncollected','0'))))
        if remaining<=0:continue
        due=p.get('due_date') or ''
        try:days=(today-parse_j(due).togregorian()).days if due else None
        except (ValueError,TypeError):days=None
        bucket='نامشخص' if days is None else 'جاری' if days<=0 else '۱ تا ۳۰ روز' if days<=30 else '۳۱ تا ۶۰ روز' if days<=60 else '۶۱ تا ۹۰ روز' if days<=90 else 'بیش از ۹۰ روز'
        snapshot=p.get('customer_snapshot') if isinstance(p.get('customer_snapshot'),dict) else {};name=str(snapshot.get('legal_name') or snapshot.get('title') or '')[:150]
        rows.append(dict(invoice_id=item.get('id',''),customer=p.get('client_id',''),customer_name=name,number=p.get('number',''),document=p.get('document_no',''),kind=kind,due=due,amount=str(remaining),bucket=bucket,days=days))
    return rows


def check_summary(checks,today=None):
    today=today or date.today();result={'overdue':0,'upcoming':0}
    for check in checks:
        if check.get('status','pending') not in ('pending','deposited'):continue
        try:days=(parse_j(check.get('due_date','')).togregorian()-today).days
        except (ValueError,TypeError):continue
        if days<0:result['overdue']+=1
        elif days<=30:result['upcoming']+=1
    return result
