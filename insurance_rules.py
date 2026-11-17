"""Validation for immutable, explicitly sourced insurance rule versions."""
import re
from decimal import Decimal
from storage import normalize,parse_j

def normalize_rules(payload):
    fields={'title','rules_version','source','effective_from','effective_to','worker_rate','employer_rate','unemployment_rate','minimum_daily','maximum_daily','approved'}
    if not isinstance(payload,dict) or set(payload)!=fields:raise ValueError('همه اطلاعات نسخه قواعد لازم است.')
    result={}
    for key in fields-{'approved'}:
        value=payload[key]
        if not isinstance(value,str) or not value.strip() or len(value)>200:raise ValueError('اطلاعات نسخه قواعد کامل نیست.')
        result[key]=normalize(value)
    if type(payload['approved']) is not bool:raise ValueError('وضعیت تأیید قواعد معتبر نیست.')
    result['approved']=payload['approved']
    if parse_j(result['effective_from'])>parse_j(result['effective_to']):raise ValueError('بازه اعتبار قواعد معتبر نیست.')
    for key in ('worker_rate','employer_rate','unemployment_rate'):
        result[key]=result[key].replace('٫','.')
        if not re.fullmatch(r'\d{1,3}(?:\.\d{1,4})?',result[key]) or Decimal(result[key])>100:raise ValueError('نرخ‌ها باید بین صفر و صد باشند.')
    for key in ('minimum_daily','maximum_daily'):
        result[key]=result[key].replace(',','').replace('٬','')
        if not re.fullmatch(r'[0-9]{1,15}',result[key]):raise ValueError('حدود دستمزد باید عدد صحیح ریالی باشند.')
    if not 0<int(result['minimum_daily'])<=int(result['maximum_daily']):raise ValueError('حداقل و حداکثر دستمزد معتبر نیست.')
    return result
