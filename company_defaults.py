"""One-time, reversible migration of the built-in company calendar."""
import copy
import hashlib
from datetime import datetime, timezone

def company_order(name):
    order={'مانا':0,'آیریا':1,'آرکا':2}
    return (order.get(str(name),3),str(name))


def migrate_company_defaults(data):
    from planning import kind_for
    events=data.setdefault('events',[])
    existing={event.get('id') for event in events}
    archive=data.setdefault('company_defaults_archive',[])
    copies=[]
    kept=[]
    for event in events:
        built_in=bool(event.get('created_from_excel') or event.get('generated'))
        if event.get('company')!='آرکا' or not built_in:
            kept.append(event)
            continue
        kind=event.get('template_kind') or kind_for(event)
        if kind and kind!='rent':
            identity='airia-'+hashlib.sha256(str(event.get('id')).encode()).hexdigest()[:24]
            if identity not in existing:
                new=copy.deepcopy(event)
                new.update(id=identity,company='آیریا',source_sheet='آیریا',done=False,last_alerts={},completed_occurrences=[])
                new.pop('snooze_until',None)
                copies.append(new);existing.add(identity)
        if kind in ('vat','books'):
            kept.append(event)
        else:
            archive.append(dict(event=copy.deepcopy(event),reason='حذف تکلیف پیش‌فرض آرکا طبق تنظیم شرکت',archived_at=datetime.now(timezone.utc).isoformat()))
    data['events']=kept+copies
    data['companies']=sorted(set(data.get('companies',[]))|{'مانا','آیریا','آرکا'},key=company_order)
    data['company_defaults_version']=1
