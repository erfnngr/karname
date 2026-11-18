"""Validated insurance supplement linked to an existing HR employee."""
import re
from storage import normalize,parse_j

_FIELDS={'title','employee_id','workshop_id','first_name','last_name','national_id','insurance_number','birth_certificate',
         'father_name','birth_date','issue_place','issue_date','gender','nationality','job_title','job_code',
         'start_date','end_date','employment_type','insurance_status','seniority_basis',
         'marital_status','marital_changed','exemptions','notes'}

def normalize_profile(payload):
    if not isinstance(payload,dict) or set(payload)-_FIELDS:raise ValueError('اطلاعات بیمه‌ای معتبر نیست.')
    result={}
    for key,value in payload.items():
        if not isinstance(value,str):raise ValueError('اطلاعات بیمه‌ای باید به صورت متن باشد.')
        value=normalize(value)
        if len(value)>(2000 if key in ('notes','exemptions') else 200):raise ValueError('اطلاعات بیمه‌ای بیش از حد طولانی است.')
        result[key]=value
    for key in ('title','employee_id','workshop_id'):
        if not result.get(key):raise ValueError('عنوان، کارمند و کارگاه مرتبط لازم هستند.')
    for key in ('national_id','insurance_number','birth_certificate','job_code'):
        if result.get(key) and not re.fullmatch(r'[0-9]{1,25}',result[key]):raise ValueError('شناسه‌های بیمه‌ای باید فقط شامل رقم باشند.')
    for key,choices in (('gender',('نامشخص','زن','مرد')),('marital_status',('نامشخص','مجرد','متأهل'))):
        if result.get(key) and result[key] not in choices:raise ValueError('وضعیت فرد معتبر نیست.')
    for key in ('birth_date','issue_date','start_date','end_date','marital_changed'):
        if result.get(key):parse_j(result[key])
    if result.get('start_date') and result.get('end_date') and parse_j(result['end_date'])<parse_j(result['start_date']):
        raise ValueError('پایان همکاری نمی‌تواند پیش از شروع همکاری باشد.')
    return result

def validate_profile(payload):
    normalize_profile(payload)
