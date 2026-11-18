"""Build review rows for a draft. These are not statutory insurance files."""
from insurance_monthly import normalize_draft
from insurance_validation import review

def tracking_report(lists,workshops,evidence):
    """Summarize user-entered receipts, without asserting acceptance or settlement."""
    by_list={}
    for event in evidence:
        p=event.get('payload',{})
        if event.get('kind')!='insurance_evidence':continue
        by_list.setdefault((event.get('company_id'),p.get('insurance_list_id')),[]).append(p)
    result=[]
    for record in lists:
        p=record['payload'];events=by_list.get((record.get('company_id'),record['id']),[])
        sent=[e for e in events if e.get('kind')=='ارسال دستی']
        paid=[e for e in events if e.get('kind')=='پرداخت دستی']
        amounts=[int(e['amount']) for e in paid if str(e.get('amount','')).isdigit()]
        result.append({'شناسه':record['id'],'عنوان':record['title'],'کارگاه':workshops.get((record.get('company_id'),p['workshop_id']),'غیرقابل مشاهده'),
                       'ماه':p['period'],'شماره لیست':p['list_no'],'نسخه داخلی':p.get('revision','1'),
                       'پیگیری ارسال دستی':'ثبت شده' if sent else 'ثبت نشده',
                       'پیگیری پرداخت دستی':'ثبت شده' if paid else 'ثبت نشده',
                       'تعداد رسید پرداخت':len(paid),'جمع مبالغ رسید ثبت‌شده ریال':str(sum(amounts)),
                       'توضیح':'اطلاعات اظهاری است؛ پذیرش سامانه و تسویه کامل بررسی نشده است.'})
    return result

def draft_report(payload,workshop,profiles,employees,names):
    draft=normalize_draft(payload);issues=review(draft,workshop,profiles,employees)
    common=[i['message'] for i in issues if i['profile_id'] is None];rows=[]
    for row in draft['rows']:
        findings=[('خطا: ' if i['severity']=='error' else 'بررسی: ')+i['message'] for i in issues if i['profile_id']==row['profile_id']]
        rows.append({'نوع گزارش':'پیش‌نویس بررسی؛ فایل ارسال نیست','ماه':draft['period'],'کارگاه':(workshop or {}).get('title',''),'شماره لیست':draft['list_no'],'نسخه داخلی':draft['revision'],
                     'کارمند':names.get(row['profile_id'],'غیرقابل مشاهده'),'منبع پیشنهادی':'برآورد حقوق' if row['payroll_batch_id'] else 'ورود دستی','روز بیمه':row['days'],'مزد روزانه ریال':row['daily_wage'],
                     'سنوات روزانه ریال':row['daily_seniority'],'حق تأهل مشمول ریال':row['spouse_benefit'],'سایر مزایای مشمول ریال':row['insured_benefits'],'مزایای غیرمشمول ریال':row['non_insured_benefits'],
                     'بیمه بیکاری':'نامشخص' if row['unemployment_applies'] is None else 'مشمول' if row['unemployment_applies'] else 'غیرمشمول',
                     'جزئیات مزایا':'؛ '.join(x['title']+' '+x['amount']+' ریال ('+('مشمول' if x['insured'] else 'غیرمشمول')+')' for x in row['benefit_breakdown']),
                     'موارد بررسی':'؛ '.join(common+findings)})
    included={row['profile_id'] for row in draft['rows']}
    for profile_id in dict.fromkeys(i['profile_id'] for i in issues if i['profile_id'] is not None and i['profile_id'] not in included):
        findings=[i['message'] for i in issues if i['profile_id']==profile_id]
        rows.append({'نوع گزارش':'فرد نیازمند بررسی؛ در لیست نیست','ماه':draft['period'],'کارگاه':(workshop or {}).get('title',''),'شماره لیست':draft['list_no'],'نسخه داخلی':draft['revision'],'کارمند':names.get(profile_id,'غیرقابل مشاهده'),'منبع پیشنهادی':'','روز بیمه':'','مزد روزانه ریال':'','سنوات روزانه ریال':'','حق تأهل مشمول ریال':'','سایر مزایای مشمول ریال':'','مزایای غیرمشمول ریال':'','بیمه بیکاری':'','جزئیات مزایا':'','موارد بررسی':'؛ '.join(common+findings)})
    if not rows:rows.append({'نوع گزارش':'پیش‌نویس بررسی؛ فایل ارسال نیست','ماه':draft['period'],'کارگاه':(workshop or {}).get('title',''),'شماره لیست':draft['list_no'],'نسخه داخلی':draft['revision'],'کارمند':'','منبع پیشنهادی':'','روز بیمه':'','مزد روزانه ریال':'','سنوات روزانه ریال':'','حق تأهل مشمول ریال':'','سایر مزایای مشمول ریال':'','مزایای غیرمشمول ریال':'','بیمه بیکاری':'','جزئیات مزایا':'','موارد بررسی':'؛ '.join(common)})
    return rows
