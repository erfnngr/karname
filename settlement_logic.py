"""Validation for a future, transactional invoice settlement workflow."""
from decimal import Decimal, InvalidOperation

def amount(value):
    try:
        value=Decimal(str(value))
        if not value.is_finite() or value<0 or value>Decimal('1000000000000000000') or value!=value.to_integral_value():raise ValueError
        return value
    except (InvalidOperation,ValueError,TypeError):raise ValueError('مبلغ ریالی معتبر نیست.') from None

def validate(total,payments):
    total=amount(total)
    if not isinstance(payments,list) or len(payments)>100:raise ValueError('فهرست تسویه معتبر نیست.')
    received=Decimal(0);pending=Decimal(0);seen=set()
    for entry in payments:
        if not isinstance(entry,dict):raise ValueError('ردیف تسویه معتبر نیست.')
        kind=entry.get('kind');value=amount(entry.get('amount'))
        if value<=0 or kind not in ('cash','bank','check'):raise ValueError('روش یا مبلغ تسویه معتبر نیست.')
        if kind=='bank':
            if not entry.get('bank_account_id'):raise ValueError('حساب بانکی را انتخاب کنید.')
            if entry.get('method','other') not in ('card','pos','paya','satna','pol','internal','cash_deposit','other'):raise ValueError('روش انتقال معتبر نیست.')
        if kind=='check':
            check=entry.get('check_id')
            if not isinstance(check,str) or not check or check in seen:raise ValueError('چک تکراری یا نامعتبر است.')
            seen.add(check);pending+=value
        else:received+=value
    if received+pending>total:raise ValueError('مبلغ تسویه از مبلغ فاکتور بیشتر است.')
    return {'received':str(received),'pending_checks':str(pending),'unallocated':str(total-received-pending),'uncollected':str(total-received)}
