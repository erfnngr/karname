"""Search hints for informal Persian; never rewrite the original instruction."""
import re
from datetime import timedelta
from storage import normalize,parse_j

GROUPS=(('فاکتور','صورتحساب','صورت حساب','فکتور','پیش فاکتور'),('مشتری','طرف حساب','خریدار'),('کالا','محصول','جنس'),('تردد','حضور و غیاب','ورود و خروج','ساعت کاری','کارکرد','ساعت زنی'),('مرخصی','استراحت'),('یادآور','یاداور','یادآوری','یاد اور','ریمایندر','یادم بنداز','یاد م بنداز','یادم بیار','یادم بینداز'),('مالیات','مالیاتی','اظهارنامه'),('پرداخت','واریز','بدهکاری','بدهی'),('دریافت','وصول','بستانکاری','طلب'),('چک','چکها','چک های'),('گفتگو','چت','پیام','پیغام','پی وی','پیوی'),('کار','تکلیف','وظیفه'),('حقوق','دستمزد','حقوق و دستمزد'))
def clean(text):
    text=normalize(text).casefold().replace('ي','ی').replace('ك','ک').replace('ۀ','ه')
    text=re.sub(r'[\u064b-\u065f\u0670\u0640]','',text)
    return ' '.join(text.split())

def search_query(text):
    original=clean(text);expanded=[]
    for group in GROUPS:
        if any(word in original for word in group[1:]) and group[0] not in original:expanded.append(group[0])
    return original+' '+ ' '.join(expanded) if expanded else original

def terms(text):
    stop={'برای','برام','لطفا','میشه','میخوام','میخواهم','کارنامه','کارهای','وضعیت','بگو','کنم','بده','نشون','ببین','کدوم','چیه','چیست','هایی','های'}
    return {w for w in re.findall(r'[\w]{3,}',search_query(text)) if w not in stop}

def explicit_message_request(text):
    q=clean(text)
    return any(word in q for word in ('ارسال','بفرست','بفرستید','پیام بده','پیام بدید','پیام بکن','پیغام بده','پیغام بدید','پیغام بکن'))

def domain_hint(text):
    """Give the model a conservative hint; ambiguous multi-step requests stay open."""
    q=clean(text)
    chat=any(x in q for x in ('چت','گفتگو','گروه','پیام','پیغام'))
    reminder=any(x in q for x in ('یادآور','یاداور','یادآوری','یاد اور','یادم بنداز','یاد م بنداز','یادم بیار','یادم بینداز','یادم باشه','ریمایندر','یادداشت تقویم','آلارم'))
    send=any(x in q for x in ('بفرست','ارسال','پیام بده','پیغام بده','پیام بدید','پیغام بدید'))
    create=any(x in q for x in ('ثبت','بساز','بذار','بگذار','اضافه','تنظیم','یادم بنداز','یاد م بنداز','یادم بیار','یادم بینداز','یادم باشه','یادآوری کن'))
    if chat and reminder:
        if send and not create:return 'chat'
        if create and not send:return 'reminder'
        return None
    return 'chat' if chat and send else 'reminder' if reminder and create else None

def domain_instruction(text):
    hint=domain_hint(text)
    if hint=='chat':return 'کاربر درخواست ارسال یا اقدام در گفتگو دارد؛ صرف اشاره به یادآوری را ثبت رویداد تقویم تلقی نکن. مقصد و متن صریح و مجاز لازم است.'
    if hint=='reminder':return 'کاربر درباره ساخت یا تنظیم یادآور تقویم درخواست دارد؛ بدون دستور مستقل او پیامی در گفتگو ارسال نکن.'
    return 'گفتگو، یادآور و بقیه بخش‌ها مستقل‌اند. فقط اعمالی را انتخاب کن که کاربر صریحاً برای همان بخش خواسته است؛ در ابهام سؤال کن.'

def time_window(query,today):
    q=clean(query);match=re.search(r'(?<!\d)(1[34]\d{2})[/.\-](\d{1,2})(?:[/.\-](\d{1,2}))?(?!\d)',q)
    if match:
        try:
            year,month,day=match.groups();start=parse_j(f'{year}/{int(month):02d}/{int(day or 1):02d}').togregorian()
            if day:return start,start
            import jdatetime
            y=int(year);m=int(month);end=(jdatetime.date(y+int(m==12),1 if m==12 else m+1,1).togregorian()-timedelta(days=1));return start,end
        except ValueError:pass
    if re.search(r'(?<!\w)پس\s*فردا(?:ست)?(?!\w)',q):return today+timedelta(days=2),today+timedelta(days=2)
    if 'فردا' in q:return today+timedelta(days=1),today+timedelta(days=1)
    if 'دیروز' in q:return today-timedelta(days=1),today-timedelta(days=1)
    if 'امروز' in q:return today,today
    weekdays={'شنبه':5,'یکشنبه':6,'دوشنبه':0,'سه شنبه':1,'چهارشنبه':2,'پنجشنبه':3,'جمعه':4}
    q=q.replace('سه‌شنبه','سه شنبه').replace('یک شنبه','یکشنبه').replace('دو شنبه','دوشنبه').replace('چهار شنبه','چهارشنبه').replace('پنج شنبه','پنجشنبه')
    matches=[weekday for name,weekday in weekdays.items() if re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)',q)]
    if len(set(matches))==1:
        days=(matches[0]-today.weekday())%7
        if any(x in q for x in ('هفته بعد','هفته آینده','هفته دیگه')):days=days%7+7
        day=today+timedelta(days=days);return day,day
    if any(x in q for x in ('گذشته','قبلی','عقب افتاده','عقب مانده','سررسید شده')):return None,today-timedelta(days=1)
    if any(x in q for x in ('آینده','بعدی','پیش رو','پیشرو')):return today,None
    return None,None
