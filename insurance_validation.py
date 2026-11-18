"""Actionable preliminary checks; not an official export validation."""
from storage import parse_j,month_last_day
from insurance_monthly import normalize_draft,check_breakdown,eligible_profiles_for_period

def review(payload,workshop,profiles,employees):
    draft=normalize_draft(payload);issues=[]
    def add(severity,profile_id,message):issues.append({'severity':severity,'profile_id':profile_id,'message':message})
    if not workshop or not workshop.get('workshop_code'):add('error',None,'کد کارگاه را تکمیل کنید.')
    if not draft['rows']:add('error',None,'دست‌کم یک کارمند به لیست اضافه کنید.')
    start=parse_j(draft['period']+'/01');end=parse_j(draft['period']+'/'+str(month_last_day(start.year,start.month)))
    labels={'first_name':'نام','last_name':'نام خانوادگی','national_id':'کد ملی','insurance_number':'شماره بیمه','father_name':'نام پدر','birth_date':'تاریخ تولد','job_title':'عنوان شغلی','job_code':'کد شغلی','start_date':'تاریخ شروع همکاری'}
    for row in draft['rows']:
        key=row['profile_id'];p=profiles.get(key)
        if not p:add('error',key,'پرونده بیمه‌ای قابل مشاهده نیست.');continue
        if p.get('workshop_id')!=draft['workshop_id']:add('error',key,'کارگاه پرونده با کارگاه لیست متفاوت است.')
        if p.get('employee_id') not in employees:add('error',key,'پرونده کارمند مرتبط قابل مشاهده نیست.')
        for field,label in labels.items():
            if not p.get(field):add('warning',key,label+' را در پرونده بررسی و تکمیل کنید.')
        for field,label in [('days','روز کارکرد'),('daily_wage','مزد روزانه'),('daily_seniority','سنوات روزانه'),('spouse_benefit','حق تأهل مشمول'),('insured_benefits','سایر مزایای مشمول'),('non_insured_benefits','مزایای غیرمشمول')]:
            if row[field]=='':add('error',key,label+' وارد نشده است؛ مقدار صفر را نیز صریح وارد کنید.')
        if row['unemployment_applies'] is None:add('error',key,'وضعیت بیمه بیکاری مشخص نشده است.')
        mismatch=check_breakdown(row)
        if mismatch:add('error',key,mismatch)
        try:
            joined=parse_j(p['start_date']) if p.get('start_date') else None
            left=parse_j(p['end_date']) if p.get('end_date') else None
            if joined and joined>end or left and left<start:add('warning',key,'بازه همکاری با ماه انتخاب‌شده هم‌پوشانی ندارد؛ حضور فرد را بررسی کنید.')
            elif joined and start<joined<=end or left and start<=left<end:add('warning',key,'شروع یا پایان همکاری در میانه ماه است؛ تعداد روز بیمه را بررسی کنید.')
            if joined and not (left and left<start) and joined<=end and row['days']:
                available=(min(left or end,end).togregorian()-max(joined,start).togregorian()).days+1
                if int(row['days'])>available:add('warning',key,'روزهای ثبت‌شده از روزهای بازه همکاری این ماه بیشتر است؛ تاریخ و کارکرد را بررسی کنید.')
        except ValueError:add('error',key,'تاریخ همکاری معتبر نیست.')
    candidates=[{'id':key,'payload':p} for key,p in profiles.items()]
    eligible,_=eligible_profiles_for_period(candidates,draft['workshop_id'],draft['period'])
    included={row['profile_id'] for row in draft['rows']}
    for key in eligible:
        if key not in included:add('warning',key,'بازه همکاری با این ماه هم‌پوشانی دارد اما فرد در لیست نیست؛ لزوم حضور او را بررسی کنید.')
    return issues
