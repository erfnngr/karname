"""Evidence-based, bounded context and reminders for the personal assistant."""
from datetime import date, datetime, timezone
import hashlib
from storage import normalize
from reminders import upcoming_date
from weather import weather_kind

OUTDOOR=('سفر','پرواز','ماموریت','مأموریت','بازدید','مراجعه','جلسه حضوری','قرار حضوری','بیرون','گردش')
ADVERSE={45,48,51,53,55,56,57,61,63,65,66,67,71,73,75,77,80,81,82,85,86,95,96,99}

def weather_context(service):
    if not service or not service.enabled or not service.data or not service.checked_at:return None
    try:
        stamp=service.checked_at
        if stamp.tzinfo is None:return None
        age=(datetime.now(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()
        if not 0<=age<=6*3600:return None
        data=service.data;cur=data['current']
        return {'city':data.get('location') or 'تهران','checked_at':stamp.isoformat(),'cached':bool(service.cached),'estimated':bool(data.get('estimated')),'current':{'temperature':cur['temp'],'description':weather_kind(cur.get('symbol'))[1]},'days':[{'date':d['date'].isoformat(),'min':d['min'],'max':d['max'],'description':weather_kind(d.get('symbol'))[1],'code':d.get('symbol',{}).get('code') if isinstance(d.get('symbol'),dict) else None} for d in data.get('days',[])[:7]]}
    except (KeyError,TypeError,ValueError,AttributeError):return None

def alerts(events,weather,history,today=None):
    today=today or date.today();result=[]
    days={d['date']:d for d in (weather or {}).get('days',[])}
    for event in events:
        if not event.get('id') or event.get('done') or event.get('needs_review'):continue
        try:due=upcoming_date(event,today)
        except (ValueError,TypeError):continue
        if not due:continue
        delta=(due-today).days
        title=str(event.get('title') or '')[:80]
        text=normalize(title+' '+str(event.get('notes') or ''))
        forecast=days.get(due.isoformat())
        if delta in (0,1) and forecast and forecast.get('code') in ADVERSE and any(w in text for w in OUTDOOR):
            # A trip may be outside Tehran: explicitly state the forecast location.
            key='weather|'+str(event['id'])+'|'+due.isoformat()+'|'+today.isoformat()
            if key not in history:result.append((key,'پیش‌بینی تهران برای «'+title+'» ('+('امروز' if delta==0 else 'فردا')+'): '+forecast['description']+'؛ پیش از حرکت وضعیت مقصد را بررسی کنید.'))
        if -30<=delta<0 and event.get('recurrence','بدون تکرار')=='بدون تکرار':
            key='overdue|'+str(event['id'])+'|'+today.isoformat()
            if key not in history:result.append((key,'کار باز از موعد گذشته: «'+title+'»؛ وضعیت آن را بررسی کنید.'))
    return result[:4]

def review_items(records,actor,limit=10):
    """Only report observable missing fields from authorized tax cases."""
    from permission_policy import allowed
    result=[]
    for record in records:
        if record.get('kind')!='tax_case' or record.get('deleted'):continue
        company=record.get('company_id');payload=record.get('payload') or {}
        if not company or actor is not None and not allowed(actor,company,'tax','view'):continue
        title=str(payload.get('title') or record.get('title') or 'پرونده مالیاتی')[:100];status=payload.get('status')
        if status not in ('completed','submitted') and not payload.get('due_date'):
            result.append(dict(id=record.get('id',''),company_id=company,issue='موعد در پرونده ثبت نشده است؛ در صورت وجود، از منبع معتبر بررسی کنید.',title=title,kind='missing_due'))
        if status in ('completed','submitted') and not str(payload.get('reference') or '').strip():
            result.append(dict(id=record.get('id',''),company_id=company,issue='شماره پیگیری در پرونده ثبت نشده است؛ در صورت وجود آن را بررسی کنید.',title=title,kind='missing_reference'))
        if len(result)>=limit:break
    return result[:limit]

def review_alerts(records,actor,history,today=None):
    today=today or date.today();result=[]
    for item in review_items(records,actor):
        if not item['id']:continue
        key='review|'+item['id']+'|'+item['kind']+'|'+today.isoformat()
        if key not in history:result.append((key,'«'+item['title']+'»: '+item['issue']))
    return result[:3]
