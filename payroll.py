"""Decimal payroll estimates. Tax schedules are explicitly supplied by the user."""
from decimal import Decimal,ROUND_HALF_UP
from penalties import number

def progressive(income,brackets):
    total=Decimal(0);lower=Decimal(0)
    if not brackets:raise ValueError('ابتدا جدول پلکانی مالیات را تعریف کنید.')
    for i,b in enumerate(brackets):
        rate=number(b['rate']);cap=number(b['cap']) if str(b.get('cap','')).strip() else None
        if rate>100 or (cap is not None and cap<=lower) or (cap is None and i!=len(brackets)-1):raise ValueError('سقف پله‌ها صعودی و نرخ‌ها بین صفر و ۱۰۰ باشند؛ پله آخر بدون سقف است.')
        portion=max(Decimal(0),min(income,cap) - lower) if cap is not None else max(Decimal(0),income-lower)
        total+=portion*rate/100
        if cap is not None:lower=cap
    if cap is not None:raise ValueError('سقف آخرین پله را خالی بگذارید.')
    return total

def compute_payroll(p):
    n=lambda key,default='0':number(p.get(key,default))
    base=n('base');days=n('days','30');period_days=n('period_days','30');divisor=n('hours_base','220');factor=n('overtime_factor','1.4')
    if not period_days or not divisor or days>period_days or period_days>31 or n('overtime_hours')>744 or factor>10:raise ValueError('کارکرد باید بین صفر و روزهای ماه باشد؛ ساعات مبنا و روزهای ماه بزرگ‌تر از صفر باشند.')
    wage=base*days/period_days;overtime=base/divisor*n('overtime_hours')*factor
    night=base/divisor*n('night_hours')*n('night_factor','0.35')
    benefits=sum((n(k) for k in ('housing','food','children','seniority','bonus','spouse','transport','lunch','commission','other_benefits')),Decimal(0))
    gross=wage+overtime+night+benefits
    insured=n('insurance_basis') if p.get('insurance_override') else gross
    worker=n('worker_rate','7');employer=n('employer_rate','23')
    if max(worker,employer,n('tax_rate'))>100 or n('night_hours')>744 or n('night_factor','0.35')>10:raise ValueError('درصدها باید بین صفر و ۱۰۰ باشند.')
    insurance=insured*worker/100;company_insurance=insured*employer/100
    taxable=max(Decimal(0),(n('tax_basis') if p.get('tax_override') else gross)-n('tax_deduction'))
    mode=p.get('tax_mode','manual')
    if mode=='manual':tax=n('tax_amount')
    elif mode=='flat':tax=max(Decimal(0),taxable-n('tax_exemption'))*n('tax_rate')/100
    elif mode=='progressive':tax=progressive(taxable,p.get('brackets',[]))
    else:raise ValueError('روش مالیات معتبر نیست.')
    deductions=n('advance')+n('loan')+n('other_deductions')
    round_money=lambda v:v.quantize(Decimal('1'),rounding=ROUND_HALF_UP)
    result={k:round_money(v) for k,v in dict(wage=wage,overtime=overtime,night=night,benefits=benefits,gross=gross,insurance=insurance,company_insurance=company_insurance,tax=tax,deductions=deductions).items()}
    # Totals reconcile exactly with the displayed, rounded rows.
    result['gross']=sum(result[k] for k in ('wage','overtime','night','benefits'))
    result['net']=result['gross']-result['insurance']-result['tax']-result['deductions'];result['employer_cost']=result['gross']+result['company_insurance']
    return result
