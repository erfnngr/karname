"""Read-only reconciliation with a payroll estimate, never a finalized payroll."""
from decimal import Decimal, InvalidOperation
from storage import normalize

def payroll_options(records,company,period):
    """Expose internal confirmation status without representing payroll as final."""
    valid={(r['payload'].get('payroll_batch_id'),r['payload'].get('batch_version')) for r in records
           if r.get('kind')=='payroll_confirmation' and r.get('company_id')==company}
    batches=[r for r in records if r.get('kind')=='payroll_batch' and r.get('company_id')==company and normalize(r.get('payload',{}).get('period',''))==normalize(period)]
    return sorted(((r,(r['id'],r.get('version')) in valid) for r in batches),key=lambda x:(not x[1],x[0].get('title',''),x[0]['id']))

def suggestions(slip,calendar_days):
    """Return only exact, unambiguous estimates; never classify benefits."""
    def number(key):
        try:
            value=Decimal(normalize(slip.get(key,'')))
            if not value.is_finite() or value<0:raise ValueError()
            return value
        except (InvalidOperation,ValueError):return None
    days=number('days');period=number('period_days');base=number('base');seniority=number('seniority');out={}
    if period!=calendar_days:return out
    if days is not None and days==days.to_integral_value() and days<=period:out['days']=str(int(days))
    if base is not None and period and base%period==0:out['daily_wage']=str(int(base/period))
    if seniority is not None and days and days==days.to_integral_value() and seniority%days==0:out['daily_seniority']=str(int(seniority/days))
    return out

def compare(draft,batch,profiles,employees):
    if normalize(batch.get('period',''))!=normalize(draft.get('period','')):
        raise ValueError('ماه دوره حقوق با ماه لیست بیمه یکسان نیست.')
    slips=batch.get('slips',[])
    if not isinstance(slips,list):raise ValueError('دوره حقوق معتبر نیست.')
    by_code={}
    for slip in slips:
        code=normalize(slip.get('code',''))
        if not code or code in by_code:raise ValueError('کدهای پرسنلی دوره حقوق ناقص یا تکراری هستند.')
        by_code[code]=slip
    output=[]
    for row in draft.get('rows',[]):
        profile=profiles.get(row['profile_id']);employee=employees.get(profile.get('employee_id')) if profile else None
        if not employee:
            output.append({'profile_id':row['profile_id'],'message':'پرونده کارمند قابل مشاهده نیست.'});continue
        slip=by_code.get(normalize(employee.get('employee_code','')))
        if not slip:
            output.append({'profile_id':row['profile_id'],'message':'فیشی با کد پرسنلی منطبق در این دوره پیدا نشد.'});continue
        try:
            payroll_days=Decimal(normalize(slip.get('days','')));insurance_days=Decimal(row.get('days',''))
            if not payroll_days.is_finite() or not insurance_days.is_finite():raise InvalidOperation
            message='کارکرد برابر است.' if payroll_days==insurance_days else 'کارکرد بیمه و فیش حقوق متفاوت است؛ علت را بررسی کنید.'
        except (InvalidOperation,ValueError):message='کارکرد در یکی از دو بخش ناقص یا نامعتبر است.'
        output.append({'profile_id':row['profile_id'],'message':message,'payroll_days':str(slip.get('days','')),'insurance_days':row.get('days',''),'payroll_base':str(slip.get('base',''))})
    return output
