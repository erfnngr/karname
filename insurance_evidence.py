"""Manual references to external submission/payment; not verification by the agency."""
import re
from storage import normalize,parse_j

def normalize_evidence(p):
    keys={'title','insurance_list_id','kind','date','reference','amount','notes'}
    if not isinstance(p,dict) or set(p)!=keys:raise ValueError('اطلاعات پیگیری کامل نیست.')
    q={}
    for k,v in p.items():
        if not isinstance(v,str):raise ValueError('اطلاعات پیگیری باید متن باشد.')
        q[k]=normalize(v)
        if len(q[k])>(2000 if k=='notes' else 200):raise ValueError('اطلاعات پیگیری طولانی است.')
    if any(not q[k] for k in ('title','insurance_list_id','kind','date','reference')):raise ValueError('عنوان، لیست، نوع، تاریخ و شماره پیگیری لازم است.')
    if q['kind'] not in ('ارسال دستی','پرداخت دستی'):raise ValueError('نوع پیگیری معتبر نیست.')
    parse_j(q['date'])
    q['amount']=q['amount'].replace(',','').replace('٬','')
    if q['kind']=='پرداخت دستی' and not re.fullmatch(r'[0-9]{1,15}',q['amount']):raise ValueError('مبلغ پرداخت باید عدد صحیح ریالی باشد.')
    if q['kind']=='ارسال دستی' and q['amount']:raise ValueError('برای ثبت ارسال مبلغ پرداخت وارد نکنید.')
    return q
