"""Temporary, user-supplied insurance estimate. No submission or persisted rules."""
import re
from decimal import Decimal, InvalidOperation
from insurance_engine import InsuranceInput, InsuranceRules, calculate_insurance
from storage import normalize, parse_j, month_last_day, jalali_date


def calculate_preview(data):
    fields={'period','days','daily_wage','daily_seniority','insured_benefits',
            'non_insured_benefits','worker_rate','employer_rate','unemployment_rate',
            'minimum_daily','maximum_daily','source','rules_version','approved','unemployment_applies'}
    if not isinstance(data,dict) or set(data)!=fields:
        raise ValueError('اطلاعات محاسبه کامل نیست.')
    if data['approved'] is not True or type(data['unemployment_applies']) is not bool:
        raise ValueError('منبع و اعتبار نرخ‌ها را تأیید کنید و وضعیت بیمه بیکاری را مشخص کنید.')
    def text(key, length=150):
        value=data[key]
        if not isinstance(value,str) or not value.strip() or len(value)>length:
            raise ValueError('مقدار معتبر برای «'+key+'» لازم است.')
        return normalize(value)
    def integer(key):
        value=text(key,18).replace(',','').replace('٬','')
        if not re.fullmatch(r'\d{1,15}',value):raise ValueError('مبالغ و روزها باید عدد صحیح غیرمنفی باشند.')
        return int(value)
    def rate(key):
        value=text(key,10).replace('٫','.')
        if not re.fullmatch(r'\d{1,3}(?:\.\d{1,4})?',value):raise ValueError('نرخ باید عددی بین صفر و صد باشد.')
        try:return Decimal(value)
        except InvalidOperation as exc:raise ValueError('نرخ معتبر نیست.') from exc
    period=text('period',10).replace('-','/')
    if not re.fullmatch(r'1[34]\d{2}/(?:0?[1-9]|1[0-2])',period):raise ValueError('ماه را به شکل ۱۴۰۵/۰۸ وارد کنید.')
    year,month=map(int,period.split('/'))
    start=parse_j(f'{year}/{month}/1').togregorian()
    end=jalali_date(year,month,month_last_day(year,month)).togregorian()
    days=(end-start).days+1
    rules=InsuranceRules(text('rules_version'),text('source'),start,end,
                         rate('worker_rate'),rate('employer_rate'),rate('unemployment_rate'),
                         integer('minimum_daily'),integer('maximum_daily'),True)
    item=InsuranceInput(start,end,days,integer('days'),integer('daily_wage'),integer('daily_seniority'),
                        integer('insured_benefits'),integer('non_insured_benefits'),data['unemployment_applies'])
    result=calculate_insurance(item,rules)
    return {key: str(value) if type(value) is int else value for key,value in result.items()}
