"""Publication dates only; receipt/modified times never stand in for publication."""
import json,re
from datetime import datetime,timezone,timedelta
from email.utils import parsedate_to_datetime
import jdatetime
from bs4 import BeautifulSoup
from storage import normalize,MONTHS
TEHRAN=timezone(timedelta(hours=3,minutes=30))

def parse_publication(value):
    if isinstance(value,datetime):return value if value.tzinfo else value.replace(tzinfo=TEHRAN)
    value=normalize(value)
    if not value:return None
    try:
        iso=datetime.fromisoformat(value.replace('Z','+00:00'))
        if 1900<=iso.year<=2100:return iso if iso.tzinfo else iso.replace(tzinfo=TEHRAN)
    except ValueError:pass
    try:
        result=parsedate_to_datetime(value)
        if 1900<=result.year<=2100:return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except (ValueError,TypeError,OverflowError):pass
    match=re.search(r'(?<!\d)(1[34]\d{2}|20\d{2})[/-](\d{1,2})[/-](\d{1,2})',value)
    parts=None
    if match:parts=tuple(map(int,match.groups()))
    if not parts:
        match=re.search(r'(\d{1,2})\s+('+'|'.join(MONTHS)+r')\s+(1[34]\d{2})',value)
        if match:parts=(int(match.group(3)),MONTHS.index(match.group(2))+1,int(match.group(1)))
    if parts:
        try:
            y,m,d=parts;day=jdatetime.date(y,m,d).togregorian() if y<1500 else datetime(y,m,d).date();clock=re.search(r'(\d{1,2}):(\d{2})(?::(\d{2}))?',value)
            h,minute,second=map(int,(clock.group(1),clock.group(2),clock.group(3) or '0')) if clock else (0,0,0)
            return datetime(day.year,day.month,day.day,h,minute,second,tzinfo=TEHRAN)
        except (ValueError,OverflowError):pass
    return None

def publication_from_page(html,allow_generic_time=False):
    soup=html if isinstance(html,BeautifulSoup) else BeautifulSoup(html,'html.parser')
    for selector,attribute in [("meta[property='article:published_time']",'content'),("meta[property='og:published_time']",'content'),("[itemprop='datePublished']",'content'),("meta[name='datePublished']",'content'),("meta[name='pubdate']",'content'),("time[pubdate]",'datetime')]:
        tag=soup.select_one(selector)
        if tag and (value:=parse_publication(tag.get(attribute) or tag.get('datetime') or tag.get_text(' ',strip=True))):return value
    def walk(obj):
        if isinstance(obj,dict):
            if (value:=parse_publication(obj.get('datePublished',''))):return value
            for child in obj.values():
                if isinstance(child,(dict,list)) and (value:=walk(child)):return value
        if isinstance(obj,list):
            for child in obj:
                if (value:=walk(child)):return value
        return None
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            if (value:=walk(json.loads(script.string or script.get_text()))):return value
        except (ValueError,TypeError):continue
    selectors=['article time[datetime]','.article-date','.date-publish','.publish_date','[class*="publish-date"]']
    if allow_generic_time:selectors+=['time[datetime]','time','.date']
    for selector in selectors:
        for tag in soup.select(selector):
            if (value:=parse_publication(tag.get('datetime') or tag.get_text(' ',strip=True))):return value
    for node in soup.find_all(string=re.compile(r'(?:زمان|تاریخ)\s*انتشار')):
        value=normalize(node.parent.get_text(' ',strip=True))
        # Only an explicit publication label supplies a date; update dates and
        # dates mentioned in the body are never substitutes.
        value=re.split(r'(?:زمان|تاریخ)\s*(?:به\s*روز\s*رسانی|بروز\s*رسانی|ویرایش)',value)[0]
        if len(value)<=240 and (published:=parse_publication(value)):return published
    return None

def recent(item,now=None):
    now=now or datetime.now(timezone.utc);published=parse_publication(item.get('published_at') or item.get('published',''))
    return bool(published and now-timedelta(days=14)<=published<=now)

def prune_news(state,now=None):
    previous=state.get('items',[]);state['items']=[item for item in previous if recent(item,now)]
    return len(previous)-len(state['items'])
