"""Draft monthly insurance lists; no claim of approval or official submission."""
import re
from storage import normalize,parse_j,month_last_day

_FIELDS={'title','workshop_id','period','list_no','list_type','notes','rows','status','revision','copy_from'}
_ROW_FIELDS={'profile_id','payroll_batch_id','benefit_breakdown','days','daily_wage','daily_seniority','spouse_benefit','insured_benefits',
             'non_insured_benefits','unemployment_applies'}
_NUMBERS={'days','daily_wage','daily_seniority','spouse_benefit','insured_benefits','non_insured_benefits'}

def eligible_profiles_for_period(profiles,workshop_id,period):
    """Return overlapping profiles and cases needing human review; never infer wages."""
    value=normalize(period).replace('-','/')
    if not re.fullmatch(r'1[34]\d{2}/(?:0?[1-9]|1[0-2])',value):raise ValueError('ماه را به شکل ۱۴۰۵/۰۸ وارد کنید.')
    start=parse_j(value+'/01');end=parse_j(f'{start.year:04d}/{start.month:02d}/{month_last_day(start.year,start.month):02d}')
    eligible=[];review=[]
    for record in profiles:
        p=record.get('payload',{})
        if p.get('workshop_id')!=workshop_id:continue
        if not p.get('start_date'):
            review.append(record['id']);continue
        try:
            joined=parse_j(p['start_date']);left=parse_j(p['end_date']) if p.get('end_date') else None
            if left and left<joined:review.append(record['id']);continue
            if joined<=end and (left is None or left>=start):eligible.append(record['id'])
        except (ValueError,TypeError):review.append(record['id'])
    return eligible,review

def normalize_draft(payload):
    if not isinstance(payload,dict) or set(payload)-_FIELDS:raise ValueError('اطلاعات لیست ماهانه معتبر نیست.')
    result={}
    for key in ('title','workshop_id','period','list_no','list_type','notes','revision','copy_from'):
        value=payload.get(key,'1' if key=='revision' else '')
        if not isinstance(value,str):raise ValueError('اطلاعات لیست باید به شکل متن باشد.')
        value=normalize(value)
        if len(value)>(2000 if key=='notes' else 150):raise ValueError('متن لیست بیش از حد طولانی است.')
        result[key]=value
    for key in ('title','workshop_id','period','list_no'):
        if not result[key]:raise ValueError('عنوان، کارگاه، ماه و شماره لیست لازم است.')
    period=result['period'].replace('-','/')
    if not re.fullmatch(r'1[34]\d{2}/(?:0?[1-9]|1[0-2])',period):raise ValueError('ماه را به شکل ۱۴۰۵/۰۸ وارد کنید.')
    month=parse_j(period+'/01');result['period']=f'{month.year:04d}/{month.month:02d}'
    if not re.fullmatch(r'[0-9]{1,20}',result['list_no']):raise ValueError('شماره لیست باید فقط از رقم تشکیل شود.')
    if not re.fullmatch(r'[1-9][0-9]{0,5}',result['revision']):raise ValueError('شماره نسخه داخلی معتبر نیست.')
    if result['copy_from'] and not re.fullmatch(r'[0-9a-f]{32}',result['copy_from']):raise ValueError('شناسه نسخه مبنا معتبر نیست.')
    if payload.get('status','draft')!='draft':raise ValueError('این مرحله فقط لیست پیش‌نویس ثبت می‌کند.')
    result['status']='draft';rows=payload.get('rows',[])
    if not isinstance(rows,list) or len(rows)>500:raise ValueError('فهرست کارکنان معتبر نیست.')
    result['rows']=[];seen=set()
    for row in rows:
        if not isinstance(row,dict) or set(row)-_ROW_FIELDS or not isinstance(row.get('profile_id'),str) or not row['profile_id'] or len(row['profile_id'])>100:raise ValueError('ردیف بیمه معتبر نیست.')
        profile=row['profile_id']
        if profile in seen:raise ValueError('یک کارمند بیش از یک بار به لیست اضافه شده است.')
        seen.add(profile);entry={'profile_id':profile}
        batch=row.get('payroll_batch_id','')
        if not isinstance(batch,str) or (batch and not re.fullmatch(r'[0-9a-f]{32}',batch)):raise ValueError('شناسه دوره حقوق معتبر نیست.')
        entry['payroll_batch_id']=batch
        breakdown=row.get('benefit_breakdown',[])
        if not isinstance(breakdown,list) or len(breakdown)>30:raise ValueError('جزئیات مزایا معتبر نیست.')
        entry['benefit_breakdown']=[]
        for item in breakdown:
            if not isinstance(item,dict) or set(item)!={'title','amount','insured'} or not isinstance(item['title'],str) or not item['title'].strip() or len(item['title'])>100 or type(item['insured']) is not bool or not isinstance(item['amount'],str):raise ValueError('هر ردیف مزایا باید عنوان، مبلغ و وضعیت شمول داشته باشد.')
            amount=normalize(item['amount']).replace(',','').replace('٬','')
            if not re.fullmatch(r'[0-9]{1,15}',amount):raise ValueError('مبلغ مزایا باید عدد صحیح غیرمنفی باشد.')
            title=normalize(item['title'])
            if 'تاهل' in title or 'تأهل' in title or 'سنوات' in title:raise ValueError('حق تأهل و سنوات را فقط در ستون جداگانه خود وارد کنید.')
            entry['benefit_breakdown'].append({'title':title,'amount':amount,'insured':item['insured']})
        for key in _NUMBERS:
            value=row.get(key,'')
            if not isinstance(value,str):raise ValueError('ارقام هر ردیف باید به صورت متن باشند.')
            value=normalize(value).replace(',','').replace('٬','')
            if value and not re.fullmatch(r'[0-9]{1,15}',value):raise ValueError('ارقام هر ردیف باید عدد صحیح غیرمنفی باشند.')
            if key=='days' and value and int(value)>month_last_day(month.year,month.month):raise ValueError('روزهای بیمه بیش از روزهای ماه انتخاب‌شده است.')
            entry[key]=value
        unemployment=row.get('unemployment_applies',None)
        if unemployment is not None and type(unemployment) is not bool:raise ValueError('وضعیت بیمه بیکاری معتبر نیست.')
        entry['unemployment_applies']=unemployment;result['rows'].append(entry)
    return result

def calculate_draft(payload,rules):
    """Calculate only complete drafts with explicitly supplied, confirmed rules."""
    from insurance_preview import calculate_preview
    draft=normalize_draft(payload)
    keys={'worker_rate','employer_rate','unemployment_rate','minimum_daily','maximum_daily','source','rules_version','approved'}
    if not isinstance(rules,dict) or set(rules)!=keys or rules['approved'] is not True:
        raise ValueError('اطلاعات و تأیید قواعد دوره لازم است.')
    if not draft['rows']:raise ValueError('حداقل یک کارمند را انتخاب کنید.')
    results=[];errors=[]
    for row in draft['rows']:
        try:
            breakdown_error=check_breakdown(row)
            if breakdown_error:raise ValueError(breakdown_error)
            data={**rules,**{k:v for k,v in row.items() if k not in ('profile_id','payroll_batch_id','benefit_breakdown')},'period':draft['period']}
            results.append({'profile_id':row['profile_id'],'amounts':calculate_preview(data)})
        except ValueError as exc:errors.append({'profile_id':row['profile_id'],'message':str(exc)})
    if errors:return {'errors':errors,'rows':[],'totals':{}}
    fields=('monthly_wage','seniority_total','spouse_benefit','insured_total','gross_total','worker','employer','unemployment','insurance_total')
    totals={key:str(sum(int(row['amounts'][key]) for row in results)) for key in fields}
    totals['days']=str(sum(int(row['days']) for row in draft['rows']))
    return {'errors':[],'rows':results,'totals':totals}

def check_breakdown(row):
    items=row.get('benefit_breakdown',[])
    if not items:return ''
    for insured,key,label in ((True,'insured_benefits','مشمول'),(False,'non_insured_benefits','غیرمشمول')):
        if not row.get(key) or sum(int(x['amount']) for x in items if x['insured'] is insured)!=int(row[key]):
            return 'جمع جزئیات مزایای '+label+' با ستون مربوط برابر نیست.'
    return ''
