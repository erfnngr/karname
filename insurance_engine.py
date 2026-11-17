"""Insurance calculation primitives; unconfirmed rules cannot produce final figures.

Amounts are integer rials. This module does not create or submit ListDisk files.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class InsuranceRules:
    version: str
    source: str
    effective_from: date
    effective_to: date
    worker_percent: Decimal
    employer_percent: Decimal
    unemployment_percent: Decimal
    minimum_daily: int
    maximum_daily: int
    approved: bool = False


@dataclass(frozen=True)
class InsuranceInput:
    period_start: date
    period_end: date
    calendar_days: int
    insured_days: int
    daily_wage: int
    daily_seniority: int
    insured_benefits: int
    non_insured_benefits: int
    unemployment_applies: bool


def _money(value):
    if type(value) is not int or value < 0:
        raise ValueError('مبالغ باید عدد صحیح غیرمنفی به ریال باشند.')
    return value


def _share(base, percent):
    if not isinstance(percent, Decimal) or not percent.is_finite() or not Decimal(0) <= percent <= Decimal(100):
        raise ValueError('نرخ باید اعشاری معتبر بین صفر و صد باشد.')
    return int((Decimal(base) * percent / Decimal(100)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def calculate_insurance(item: InsuranceInput, rules: InsuranceRules):
    if not rules.approved or not rules.version.strip() or not rules.source.strip():
        raise ValueError('نسخه قوانین بیمه و منبع آن باید توسط حسابدار تأیید شود.')
    if not rules.effective_from <= item.period_start <= item.period_end <= rules.effective_to:
        raise ValueError('قوانین تأییدشده تمام بازه محاسبه را پوشش نمی‌دهند.')
    if type(item.calendar_days) is not int or not 1 <= item.calendar_days <= 31 or item.calendar_days != (item.period_end-item.period_start).days+1 or type(item.insured_days) is not int or not 0 <= item.insured_days <= item.calendar_days:
        raise ValueError('تعداد روزهای بیمه در محدوده ماه نیست.')
    if type(item.unemployment_applies) is not bool:
        raise ValueError('وضعیت بیمه بیکاری باید مشخص باشد.')
    for value in (item.daily_wage,item.daily_seniority,item.insured_benefits,item.non_insured_benefits,rules.minimum_daily,rules.maximum_daily):_money(value)
    if not rules.minimum_daily or rules.maximum_daily < rules.minimum_daily:
        raise ValueError('حداقل و حداکثر دستمزد تأییدشده معتبر نیست.')
    monthly_wage=(item.daily_wage+item.daily_seniority)*item.insured_days
    insured=monthly_wage+item.insured_benefits
    if item.insured_days and not rules.minimum_daily*item.insured_days <= insured <= rules.maximum_daily*item.insured_days:
        raise ValueError('مبلغ مشمول خارج از حدود تأییدشده دوره است؛ وضعیت فرد را بررسی کنید.')
    if not item.insured_days and insured:
        raise ValueError('برای کارکرد صفر مبلغ مشمول ثبت شده است؛ وضعیت فرد را بررسی کنید.')
    worker=_share(insured,rules.worker_percent);employer=_share(insured,rules.employer_percent)
    unemployment=_share(insured,rules.unemployment_percent) if item.unemployment_applies else 0
    return {'monthly_wage':monthly_wage,'seniority_total':item.daily_seniority*item.insured_days,
            'insured_total':insured,'gross_total':insured+item.non_insured_benefits,
            'worker':worker,'employer':employer,'unemployment':unemployment,'insurance_total':worker+employer+unemployment,
            'rules_version':rules.version}
