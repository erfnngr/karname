"""Check alerts are sent only on configured days and once per occurrence."""
from datetime import date
from storage import parse_j


def due(rows,settings,shown,user_id,today=None):
    if not settings.get('reminder_enabled',True) or not settings.get('check_reminders',True):return []
    today=today or date.today();leads=settings.get('check_lead_days',[20,15,10,5,4,3,2,1,0]);result=[]
    if not isinstance(leads,list):return []
    for item in rows:
        if item.get('status') not in ('pending','deposited'):continue
        try:deadline=parse_j(item['due_date']).togregorian()
        except (ValueError,TypeError,KeyError):continue
        days=(deadline-today).days
        if days<0 or days not in leads:continue
        key='|'.join((str(user_id),item['company_id'],item['id'],today.isoformat(),deadline.isoformat()))
        if key not in shown:result.append((days,item,key))
    return sorted(result,key=lambda entry:(entry[0],entry[1]['company_id'],entry[1]['id']))
