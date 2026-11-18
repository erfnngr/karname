"""Compare draft inputs across periods; changes require human interpretation."""
from insurance_monthly import normalize_draft

def compare_periods(current,previous):
    current=normalize_draft(current);previous=normalize_draft(previous)
    if current['workshop_id']!=previous['workshop_id']:raise ValueError('فقط لیست‌های یک کارگاه قابل مقایسه‌اند.')
    if current['period']==previous['period']:raise ValueError('دو ماه متفاوت انتخاب کنید.')
    old={r['profile_id']:r for r in previous['rows']};new={r['profile_id']:r for r in current['rows']}
    labels={'days':'روز بیمه','daily_wage':'مزد روزانه','daily_seniority':'سنوات روزانه','spouse_benefit':'حق تأهل مشمول','insured_benefits':'سایر مزایای مشمول','non_insured_benefits':'مزایای غیرمشمول','unemployment_applies':'بیمه بیکاری'}
    changes=[]
    for profile in sorted(set(old)|set(new)):
        if profile not in old:changes.append({'profile_id':profile,'message':'در لیست جدید اضافه شده است.'});continue
        if profile not in new:changes.append({'profile_id':profile,'message':'در لیست جدید وجود ندارد.'});continue
        for key,label in labels.items():
            before,after=old[profile][key],new[profile][key]
            if before!=after:
                def shown(v):return 'نامشخص' if v is None or v=='' else 'مشمول' if v is True else 'غیرمشمول' if v is False else v
                changes.append({'profile_id':profile,'message':label+': '+shown(before)+' ← '+shown(after)})
    return changes
