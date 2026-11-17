"""One sourced quotation per Tehran civil day, available entirely offline."""
import json,re
from functools import lru_cache
from datetime import datetime,timezone,timedelta,date
from urllib.parse import urlsplit
from storage import package_file
TEHRAN=timezone(timedelta(hours=3,minutes=30))

@lru_cache(maxsize=1)
def collection():
    data=json.loads(package_file('data/daily_quotes.json').read_text(encoding='utf-8'))
    items=data['quotes'];seen=set()
    for item in items:
        norm=re.sub(r'[\W\d_]+','',item['text'])
        source=urlsplit(item['source'])
        if not norm or norm in seen or not item['author'] or source.scheme!='https' or source.hostname!='ganjoor.net':raise ValueError('مجموعه سخن روز معتبر نیست.')
        seen.add(norm)
    if len(items)!=300:raise ValueError('مجموعه سخن روز باید ۳۰۰ مورد داشته باشد.')
    return tuple(items)

def daily_quote(day=None):
    day=day or datetime.now(TEHRAN).date()
    if isinstance(day,datetime):day=day.astimezone(TEHRAN).date()
    items=collection()
    # 137 is coprime with 300: no repeat within a complete 300-day cycle;
    # consecutive years do not reset the rotation.
    return dict(items[(day.toordinal()*137)%len(items)])
