"""Reminder schedules independent of desktop UI, with occurrence-aware deduplication."""
from datetime import date,timedelta
from storage import normalize,parse_j,occurrence

DEFAULT_LEADS=[20,15,10,5,4,3,2,1,0]

def parse_leads(value):
    import re
    clean=normalize(value).replace('،',',')
    parts=[p.strip() for p in clean.split(',') if p.strip()]
    if not parts or any(not re.fullmatch(r'\d{1,3}',p) for p in parts):
        raise ValueError('فاصله‌ها را با ویرگول جدا کنید؛ مانند ۲۰، ۱۵، ۱۰، ۵، ۴، ۳، ۲، ۱، ۰')
    values=sorted(set(map(int,parts)),reverse=True)
    if values[0]>365:raise ValueError('فاصله یادآوری حداکثر ۳۶۵ روز است.')
    return values

def group_of(event):
    return event.get('reminder_group') or ('default' if event.get('created_from_excel') or event.get('generated') else 'personal')

def effective_leads(event,settings):
    if event.get('reminder_custom'):return event.get('lead_days',DEFAULT_LEADS)
    return settings.get(group_of(event)+'_lead_days',DEFAULT_LEADS)

def upcoming_date(event,today):
    if event.get('needs_review') or not event.get('date_jalali') or event.get('done'):return None
    if event.get('recurrence','بدون تکرار')!='بدون تکرار':return occurrence(event,today)
    return parse_j(event['date_jalali']).togregorian()

def due_reminders(events,settings,today=None):
    today=today or date.today();items=[]
    for event in events:
        if not settings.get(group_of(event)+'_reminders',True):continue
        try:
            dt=upcoming_date(event,today)
            if not dt:continue
            diff=(dt-today).days
            # Show popups only on explicitly configured reminder dates.
            if diff<0 or diff not in effective_leads(event,settings):continue
            if event.get('snooze_until') and date.fromisoformat(event['snooze_until'])>today:continue
            key=today.isoformat()+'|'+dt.isoformat()
            if event.get('last_alerts',{}).get(key) or event.get('last_alerts',{}).get(today.isoformat()):continue
            items.append((diff,event,dt,key))
        except (ValueError,TypeError):continue
    return sorted(items,key=lambda x:x[0])

def migrate(data):
    if data.get('reminders_version')==3:return
    for event in data['events']:
        event.setdefault('reminder_group',group_of(event))
        # Preserve previously edited per-event schedules, migrate the old default only.
        event.setdefault('reminder_custom',event.get('lead_days',[7,3,1,0]) not in ([7,3,1,0],DEFAULT_LEADS))
    data['reminders_version']=3
