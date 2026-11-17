"""Editable estimation rules; bundled rates come from the user's original notes."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import copy

RULES = [
    dict(id='insurance', name='بیمه کارکنان — عدم ارسال لیست و دیرکرد', fixed='10', monthly='2', basis='حق بیمه پرداخت‌نشده', note='یادداشت اولیه شما: ۱۰٪ عدم ارسال لیست و ۲٪ برای هر ماه تأخیر؛ فقط اجزای مربوط به پرونده را فعال کنید.'),
    dict(id='vat', name='مالیات بر ارزش افزوده — دیرکرد', fixed='0', monthly='2', basis='مالیات پرداخت‌نشده', note='بر اساس یادداشت‌های فایل اولیه؛ عدم ارسال اظهارنامه ممکن است جریمه جداگانه داشته باشد.'),
    dict(id='salary_list', name='مالیات حقوق — عدم ارسال فهرست', fixed='2', monthly='0', basis='حقوق پرداختی مشمول تخلف', note='یادداشت اولیه: ۲٪ بر مبنای حقوق پرداختی؛ با جریمه بر مبنای مالیات مخلوط نشود.'),
    dict(id='salary', name='مالیات حقوق — عدم پرداخت', fixed='10', monthly='0', basis='مالیات حقوق پرداخت‌نشده', note='یادداشت اولیه: ۱۰٪ بر مبنای مالیات؛ نرخ ماهانه در یادداشت این مورد تعیین نشده است.'),
    dict(id='rent', name='مالیات تکلیفی اجاره — عدم پرداخت', fixed='10', monthly='2.5', basis='مالیات پرداخت‌نشده', note='یادداشت اولیه: ۱۰٪ ثابت و ۲٫۵٪ در هر ماه بر مبنای مالیات.'),
    dict(id='performance', name='مالیات عملکرد / اظهارنامه', fixed='30', monthly='2.5', basis='مالیات متعلق', note='یادداشت اولیه: عدم ارسال اظهارنامه ۳۰٪ غیرقابل‌بخشودگی و دیرکرد ۲٫۵٪؛ بخشودگی پیش‌فرض صفر است.'),
    dict(id='books', name='دفاتر تجاری — عدم ارسال / پرداخت', fixed='20', monthly='0', basis='مبلغ مبنای پرونده', note='در یادداشت اولیه «جریمه احتمالی ۲۰٪» نوشته شده؛ شمول و مبلغ مبنا باید بررسی شود.'),
    dict(id='seasonal', name='گزارش معاملات فصلی', fixed='0', monthly='0', basis='مبلغ معاملات مشمول تخلف', note='مبنای این جریمه ممکن است مبلغ معامله باشد؛ مبلغ مبنا و نرخ تخلف را خودتان تعیین کنید.'),
    dict(id='custom', name='سایر / قاعده دلخواه', fixed='0', monthly='0', basis='مبلغ مبنای انتخابی', note='قاعده دلخواه؛ قابل ذخیره برای استفاده بعدی.'),
]

def number(value):
    value = str(value).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')).strip()
    value = value.replace(',', '').replace('٬', '').replace('٫', '.')
    if not value or len(value) > 30:
        raise ValueError('عدد معتبر وارد کنید؛ جداکننده هزارگان مجاز است.')
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError('عدد معتبر وارد کنید.')
    if not result.is_finite() or result < 0 or result > Decimal('1e24'):
        raise ValueError('عدد باید مثبت یا صفر و در محدوده مجاز باشد.')
    return result

def get_rules(data):
    saved = data.get('penalty_rules', {})
    return [dict(copy.deepcopy(r), **saved.get(r['id'], {})) for r in RULES]

def calculate(amount, fixed, monthly, months, remission='0', use_fixed=True, use_monthly=True):
    amount, fixed, monthly, months, remission = map(number, (amount, fixed, monthly, months, remission))
    if fixed > 100 or monthly > 100 or remission > 100 or months > 1200:
        raise ValueError('درصد باید بین صفر و ۱۰۰ و ماه تأخیر حداکثر ۱۲۰۰ باشد.')
    one = amount * fixed / 100 if use_fixed else Decimal(0)
    delay = amount * monthly * months / 100 if use_monthly else Decimal(0)
    gross = one + delay
    discount = gross * remission / 100
    rounded = lambda n: n.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return dict(fixed=rounded(one), delay=rounded(delay), gross=rounded(gross), discount=rounded(discount), penalty=rounded(gross-discount), total=rounded(amount+gross-discount))
