"""Validated workshop metadata, separate for each company and contract row."""
import re
from storage import normalize

_TEXT_FIELDS={'title','workshop_code','employer_name','national_id','branch','address',
              'contact','contract_row','workshop_type','labor_law','unemployment',
              'wage_type','hard_work','exemptions','notes'}
_MULTILINE={'address','exemptions','notes'}
_CHOICES={'labor_law':{'نامشخص','مشمول','غیرمشمول'},
          'unemployment':{'نامشخص','مشمول','غیرمشمول'},
          'wage_type':{'نامشخص','عادی','مقطوع','طبقه‌بندی مشاغل'},
          'hard_work':{'نامشخص','احراز نشده','احراز شده'}}

def normalize_workshop(payload):
    if not isinstance(payload,dict) or set(payload)-(_TEXT_FIELDS|{'access_users'}):
        raise ValueError('اطلاعات کارگاه معتبر نیست.')
    result={}
    for key,value in payload.items():
        if key=='access_users':
            if value is not None and (not isinstance(value,list) or len(value)>500 or any(not isinstance(x,str) or not re.fullmatch(r'[0-9a-f]{32}',x) for x in value) or len(set(value))!=len(value)):
                raise ValueError('فهرست دسترسی کارگاه معتبر نیست.')
            result[key]=sorted(value) if value is not None else None
            continue
        if not isinstance(value,str):raise ValueError('اطلاعات کارگاه باید به صورت متن وارد شود.')
        value=normalize(value)
        if len(value)>(2000 if key in _MULTILINE else 200):raise ValueError('متن اطلاعات کارگاه بیش از حد طولانی است.')
        result[key]=value
    for key in ('title','workshop_code'):
        if not result.get(key):raise ValueError('نام و کد کارگاه لازم است.')
    for key in ('workshop_code','national_id','contract_row'):
        if result.get(key) and not re.fullmatch(r'[0-9]{1,20}',result[key]):
            raise ValueError('کد کارگاه، شناسه ملی و ردیف پیمان باید فقط از رقم تشکیل شوند.')
    for key,choices in _CHOICES.items():
        if result.get(key) and result[key] not in choices:raise ValueError('وضعیت انتخاب‌شده برای کارگاه معتبر نیست.')
    return result

def validate_workshop(payload):
    normalize_workshop(payload)
