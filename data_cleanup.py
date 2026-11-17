"""Retain complete duplicate source rows in a reversible local archive."""
import copy,json
from datetime import datetime,timezone

def archive_excel_duplicates(data):
    seen={};kept=[];archive=data.setdefault('source_duplicate_archive',[]);count=0
    for event in data['events']:
        if not event.get('created_from_excel') or not event.get('date_jalali'):
            kept.append(event);continue
        signature=json.dumps({k:v for k,v in event.items() if k not in ('id','source_row','last_alerts')},sort_keys=True,ensure_ascii=False)
        canonical=seen.get(signature)
        if canonical is None:
            seen[signature]=event;kept.append(event);continue
        archive.append(dict(event=copy.deepcopy(event),canonical_id=canonical['id'],reason='ردیف کاملاً تکراری فایل اکسل',archived_at=datetime.now(timezone.utc).isoformat()))
        canonical.setdefault('last_alerts',{}).update(event.get('last_alerts',{}));count+=1
    data['events']=kept
    return count
