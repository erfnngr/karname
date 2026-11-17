"""Fetch public official pages only. No personal calendar data leaves the machine."""
from datetime import datetime, timezone
import hashlib
import re,copy,ipaddress
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlsplit, urlunsplit
import requests
from bs4 import BeautifulSoup
from news_dates import publication_from_page,parse_publication,recent,prune_news

SOURCES = [
    dict(id='tax', name='سازمان امور مالیاتی — اخبار', url='https://www.intamedia.ir/setad-news', domain='intamedia.ir'),
    dict(id='insurance', name='سازمان تأمین اجتماعی — بیمه‌ای', url='https://tamin.ir/news/service/284', feed='https://tamin.ir/News/Feed?catid=223', domain='tamin.ir'),
    dict(id='heyva',name='دینا / هیوا — مالیات',url='https://www.heyvalaw.com/web/articles/subcat/51/مالیات.html',domain='heyvalaw.com',official=False),
    dict(id='donya',name='دنیای اقتصاد — مالیات',url='https://donya-e-eqtesad.com/بخش-مالیات-214',domain='donya-e-eqtesad.com',official=False),
    dict(id='donya-insurance',name='دنیای اقتصاد — بانک و بیمه',url='https://donya-e-eqtesad.com/بخش-بانک-بیمه-16',domain='donya-e-eqtesad.com',official=False),
    dict(id='tax-announcements',name='سازمان امور مالیاتی — اطلاعیه‌ها',url='https://www.intamedia.ir/announcement',domain='intamedia.ir',official=True),
]
KEYWORDS = ('تمدید', 'مهلت', 'سررسید', 'جریمه', 'جرایم', 'بخشودگی', 'اظهارنامه', 'ارزش افزوده', 'مالیات', 'معاملات فصلی', 'مودیان', 'مؤدیان', 'حق بیمه', 'لیست')
CHANGE_WORDS = ('تمدید', 'مهلت', 'جریمه', 'جرایم', 'بخشودگی', 'تغییر', 'سررسید')

def normalized(text):
    return ' '.join(text.replace('ي','ی').replace('ك','ک').replace('\u200c', ' ').split())

def trusted(url, domain):
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower()
    return parsed.scheme == 'https' and (host == domain or host.endswith('.'+domain)) and parsed.port in (None,443) and not parsed.username and not parsed.password

def validate_source_url(url):
    p=urlsplit(url.strip());host=(p.hostname or '').lower()
    if p.scheme!='https' or p.username or p.password or '.' not in host or host.endswith(('.local','.localhost')) or p.port not in (None,443):
        raise ValueError('نشانی کامل عمومی با https وارد کنید؛ نام کاربری، رمز و پورت سفارشی در نشانی منبع مجاز نیست.')
    try:ipaddress.ip_address(host)
    except ValueError:return host.removeprefix('www.')
    raise ValueError('نشانی منبع باید نام دامنه عمومی داشته باشد.')

def get_sources(data):
    result=copy.deepcopy(data.get('news_sources',SOURCES))
    legacy_tax=next((s for s in result if s.get('id')=='tax' and s.get('url','').rstrip('/')=='https://tax.gov.ir/action/do/show/409'),None)
    if legacy_tax:
        legacy_tax['url']=SOURCES[0]['url'];legacy_tax['feed']=''
        if not any(s.get('id')=='tax-announcements' for s in result):result.append(copy.deepcopy(SOURCES[-1]))
    for source in result:
        if source.get('id')=='insurance' and source.get('url','').rstrip('/')=='https://tamin.ir':source['url']=SOURCES[1]['url']
    for source in result:
        source.setdefault('enabled',True)
        source['domain']=validate_source_url(source['url'])
        source['official']=any(source['domain']==domain or source['domain'].endswith('.'+domain) for domain in ('tax.gov.ir','tamin.ir','intamedia.ir'))
    return result

def download(url, domain, proxy=''):
    # Validate every redirect before contacting it; keep TLS certificate verification on.
    for _ in range(5):
        if not trusted(url, domain):
            raise ValueError('نشانی یا تغییر مسیر خارج از دامنه رسمی است.')
        options=dict(timeout=(6,12),allow_redirects=False,stream=True,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Karname/4.0','Accept':'text/html,application/rss+xml,application/xml;q=0.9,*/*;q=0.5','Accept-Language':'fa,en;q=0.7'})
        if proxy:options['proxies']={'http':proxy,'https':proxy}
        with requests.get(url, **options) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers.get('Location',''))
                continue
            if response.status_code==403:
                raise ValueError('سایت دسترسی را مسدود کرده است (۴۰۳)؛ ممکن است محدودیت جغرافیایی یا شبکه باشد. اتصال دستگاه و باز شدن منبع در مرورگر را بررسی کنید.')
            response.raise_for_status()
            if not any(t in response.headers.get('Content-Type','').lower() for t in ('html','xml')):
                raise ValueError('پاسخ دریافتی صفحه خبر نیست.')
            chunks=[]; size=0
            for chunk in response.iter_content(32768):
                size += len(chunk)
                if size > 4_000_000:
                    raise ValueError('اندازه پاسخ بیش از حد مجاز است.')
                chunks.append(chunk)
            raw = b''.join(chunks)
            if b'Transferring to the website' in raw or b'Just a moment...' in raw:
                raise ValueError('سایت صفحه بررسی مرورگر فرستاده است؛ دریافت خودکار خبر فعلاً ممکن نیست. منبع را در مرورگر باز کنید یا از خبرخوان معتبر همان سایت استفاده کنید.')
            return raw, url
    raise ValueError('تعداد تغییر مسیر بیش از حد مجاز است.')

def extract(html, source, base_url=None):
    soup = BeautifulSoup(html, 'html.parser')
    for block in soup.select('script,style,noscript,header,footer,nav'):
        block.decompose()
    result={}
    for a in soup.find_all('a', href=True):
        heading=a.find(['h1','h2','h3','h4'])
        title=normalized((heading.get_text(' ',strip=True) if heading else a.get('title','') or a.get_text(' ',strip=True)))
        if len(title)<12 or not any(k in title for k in KEYWORDS):
            continue
        url=urljoin(base_url or source['url'], a['href'])
        try:
            if not trusted(url,source['domain']):continue
        except ValueError:
            continue
        parts=urlsplit(url)
        url=urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ''))
        # Menus linking to services are not announcements.
        if parts.hostname and parts.hostname.split('.')[0] in ('es','eservices','my','account'):continue
        if not (any(token in (parts.path+'?'+parts.query).lower() for token in ('news','/show/','/view/','/detail','/id/','/item/','/page/','/content/','article')) or re.search(r'\d{4,}',parts.path)):continue
        identity=hashlib.sha256(url.encode()).hexdigest()[:24]
        if source['domain']=='intamedia.ir' and not any(token in parts.path.lower() for token in ('/news/','/announcement/')):continue
        if identity in result and len(result[identity]['title'])<=len(title):continue
        result[identity]=dict(id=identity,title=title[:700],url=url,source=source['name'],source_id=source['id'],official=source.get('official',source['id'] in ('tax','insurance')),important=any(k in title for k in CHANGE_WORDS))
        parent=a.find_parent('article') or a.parent
        if parent and len(parent.find_all('a'))<=12:
            if (published:=publication_from_page(str(parent),allow_generic_time=True)):result[identity]['published_at']=published.isoformat()
    return list(result.values())[:100]

def extract_feed(raw, source):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('قالب خبرخوان قابل پردازش نیست.')
    root=ET.fromstring(raw)
    items=[]
    for node in root.iter('item'):
        title=normalized(node.findtext('title',''))
        url=node.findtext('link','').strip()
        if url.startswith('http://'):url='https://'+url[7:]
        try:
            if not trusted(url,source['domain']):continue
        except ValueError:continue
        if not any(k in title for k in KEYWORDS):continue
        identity=hashlib.sha256(url.encode()).hexdigest()[:24]
        items.append(dict(id=identity,title=title[:700],url=url,source=source['name'],source_id=source['id'],official=source.get('official',source['id'] in ('tax','insurance')),published=node.findtext('pubDate',''),important=any(k in title for k in CHANGE_WORDS)))
    return items[:100]

def filter_published(items,source):
    from concurrent.futures import ThreadPoolExecutor
    missing=sorted((item for item in items if not parse_publication(item.get('published_at') or item.get('published',''))),key=lambda item:not item.get('important'))[:15]
    def enrich(item):
        try:
            raw,url=download(item['url'],source['domain'],source.get('_proxy',''))
            if (published:=publication_from_page(raw)):item['published_at']=published.isoformat()
        except Exception:pass
    if missing:
        with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(enrich,missing))
    result=[]
    for item in items:
        published=parse_publication(item.get('published_at') or item.get('published',''))
        if published:item['published_at']=published.isoformat()
        if recent(item):result.append(item)
    return result

def fetch_source(source):
    stamp=datetime.now(timezone.utc).isoformat(timespec='seconds')
    try:
        if source.get('feed'):
            try:
                raw,base=download(source['feed'],source['domain'],source.get('_proxy',''))
                items=extract_feed(raw,source)
                if items:
                    items=filter_published(items,source)
                    return dict(source_id=source['id'],checked_at=stamp,ok=True,items=items,message=f'{len(items)} خبر با تاریخ انتشار معتبر در ۱۴ روز اخیر دریافت شد.')
            except Exception:pass
        html, base = download(source['url'], source['domain'],source.get('_proxy',''))
        items=extract(html,source,base)
        items=filter_published(items,source)
        if not items:
            return dict(source_id=source['id'],checked_at=stamp,ok=True,items=[],message='اتصال برقرار شد؛ خبر مرتبط با تاریخ انتشار قابل تأیید در ۱۴ روز اخیر پیدا نشد.')
        return dict(source_id=source['id'],checked_at=stamp,ok=True,items=items,message=f'{len(items)} خبر مربوط به ۱۴ روز اخیر دریافت شد.')
    except Exception as exc:
        explanation=str(exc) if isinstance(exc,ValueError) else 'زمان اتصال تمام شد؛ اینترنت یا دسترسی به این سایت را بررسی کنید.' if isinstance(exc,requests.Timeout) else 'ارتباط شبکه با این منبع برقرار نشد.'
        return dict(source_id=source['id'],checked_at=stamp,ok=False,items=[],message=explanation+' اخبار قبلی حفظ شده‌اند.')

def merge_news(state, result):
    state.setdefault('items',[]); state.setdefault('sources',{})
    prune_news(state)
    previous=state['sources'].get(result['source_id'],{})
    known={x['id'] for x in state['items']}
    fresh=[dict(x,first_seen=result['checked_at'],read=False) for x in result['items'] if x['id'] not in known and recent(x)]
    # First successful read is a baseline, not a claim that old headlines are breaking news.
    notify=[x for x in fresh if x['important']] if previous.get('last_success') else []
    state['items']=(fresh+state['items'])[:500]
    state['sources'][result['source_id']]=dict(checked_at=result['checked_at'],ok=result['ok'],message=result['message'],last_success=result['checked_at'] if result['ok'] else previous.get('last_success'))
    return notify
