"""Inventory arithmetic used by the sales workflow under development.

Database writes must apply the returned differences in the same transaction as
the invoice update. An untracked historical invoice never creates a movement.
"""
from decimal import Decimal, InvalidOperation

def quantity(value,maximum=Decimal('1000000000')):
    try:
        result=Decimal(str(value))
        if not result.is_finite() or result < 0 or result > maximum:
            raise ValueError
        return result
    except (InvalidOperation,ValueError,TypeError):
        raise ValueError('تعداد کالا معتبر نیست.') from None

def invoice_quantities(invoice, deleted=False):
    """Return quantities only for an issued or paid sales invoice."""
    if deleted or not invoice or invoice.get('document_type') not in ('فاکتور فروش','فاکتور خرید','برگشت از فروش','برگشت از خرید') or invoice.get('status') not in ('issued','paid'):
        return {}
    sign=Decimal(-1) if invoice.get('document_type') in ('فاکتور خرید','برگشت از فروش') else Decimal(1)
    totals={}
    for line in invoice.get('lines',[]):
        product=line.get('product_id')
        if not product:continue
        if not isinstance(product,str) or len(product)>128:raise ValueError('شناسه کالا معتبر نیست.')
        q=quantity(line.get('quantity'))
        if q<=0:raise ValueError('تعداد کالا باید مثبت باشد.')
        totals[product]=totals.get(product,Decimal(0))+q*sign
    return totals

def stock_changes(before,after, before_deleted=False,after_deleted=False):
    """Signed changes to stock for creation, edit, void, delete or restore."""
    old=invoice_quantities(before,before_deleted);new=invoice_quantities(after,after_deleted)
    return {key:old.get(key,Decimal(0))-new.get(key,Decimal(0)) for key in old.keys()|new.keys() if old.get(key,Decimal(0))!=new.get(key,Decimal(0))}

def gross_profit(quantity_value,unit_sale,unit_cost,discount='0'):
    """Estimated margin, excluding tax, using an explicit unit cost snapshot."""
    q=quantity(quantity_value);limit=Decimal('1000000000000000000');sale=quantity(unit_sale,limit);cost=quantity(unit_cost,limit);off=quantity(discount,limit)
    if off>q*sale:raise ValueError('تخفیف از مبلغ کالا بیشتر است.')
    return q*(sale-cost)-off
