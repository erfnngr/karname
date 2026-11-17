"""Selected annual UN/UNESCO/WHO observances, rendered in both calendars."""
from datetime import date,timedelta
from functools import lru_cache
import jdatetime
UN='https://www.un.org/en/observances/list-days-weeks'
UNESCO='https://www.unesco.org/en/days'
WHO='https://www.who.int/campaigns'
# Fixed Gregorian observances. No moving lunar holiday or public-holiday prediction.
DAYS=[
 (1,24,'روز جهانی آموزش',UN),(1,27,'روز یادبود قربانیان هولوکاست',UN),
 (2,4,'روز جهانی سرطان',WHO),(2,11,'روز جهانی زنان و دختران در علم',UN),(2,21,'روز جهانی زبان مادری',UNESCO),
 (3,8,'روز جهانی زنان',UN),(3,20,'روز جهانی شادی',UN),(3,21,'روز جهانی نوروز',UN),(3,21,'روز جهانی شعر',UNESCO),(3,21,'روز جهانی سندرم داون',UN),
 (3,22,'روز جهانی آب',UN),(3,23,'روز جهانی هواشناسی',UN),
 (4,2,'روز جهانی آگاهی درباره اوتیسم',UN),(4,6,'روز جهانی ورزش برای توسعه و صلح',UN),(4,7,'روز جهانی بهداشت',WHO),(4,22,'روز جهانی زمین مادر',UN),(4,23,'روز جهانی کتاب و حق مؤلف',UNESCO),
 (5,3,'روز جهانی آزادی مطبوعات',UN),(5,15,'روز جهانی خانواده',UN),(5,16,'روز جهانی زندگی با هم در صلح',UN),(5,17,'روز جهانی ارتباطات و جامعه اطلاعاتی',UN),(5,21,'روز جهانی تنوع فرهنگی',UNESCO),(5,22,'روز جهانی تنوع زیستی',UN),(5,29,'روز جهانی حافظان صلح سازمان ملل',UN),(5,31,'روز جهانی بدون دخانیات',WHO),
 (6,5,'روز جهانی محیط زیست',UN),(6,8,'روز جهانی اقیانوس‌ها',UN),(6,12,'روز جهانی مبارزه با کار کودکان',UN),(6,14,'روز جهانی اهداکنندگان خون',WHO),(6,17,'روز جهانی مبارزه با بیابان‌زایی و خشکسالی',UN),(6,20,'روز جهانی پناهندگان',UN),(6,26,'روز جهانی مبارزه با سوءمصرف و قاچاق مواد مخدر',UN),
 (7,11,'روز جهانی جمعیت',UN),(7,18,'روز جهانی نلسون ماندلا',UN),(7,30,'روز جهانی دوستی',UN),
 (8,9,'روز جهانی مردمان بومی',UN),(8,12,'روز جهانی جوانان',UN),(8,19,'روز جهانی بشردوستی',UN),
 (9,5,'روز جهانی خیریه',UN),(9,8,'روز جهانی سوادآموزی',UNESCO),(9,15,'روز جهانی دموکراسی',UN),(9,16,'روز جهانی حفاظت از لایه ازن',UN),(9,21,'روز جهانی صلح',UN),(9,27,'روز جهانی گردشگری',UN),
 (10,1,'روز جهانی سالمندان',UN),(10,2,'روز جهانی پرهیز از خشونت',UN),(10,5,'روز جهانی معلم',UNESCO),(10,9,'روز جهانی پست',UN),(10,10,'روز جهانی سلامت روان',WHO),(10,11,'روز جهانی دختران',UN),(10,13,'روز جهانی کاهش خطر بلایا',UN),(10,16,'روز جهانی غذا',UN),(10,17,'روز جهانی ریشه‌کنی فقر',UN),(10,24,'روز سازمان ملل متحد',UN),(10,27,'روز جهانی میراث دیداری و شنیداری',UNESCO),(10,29,'روز جهانی کدنویسی',UNESCO),
 (11,2,'روز جهانی پایان دادن به مصونیت از مجازات جرایم علیه روزنامه‌نگاران',UNESCO),(11,3,'روز جهانی ذخیره‌گاه‌های زیست‌کره',UNESCO),(11,5,'روز جهانی آگاهی از سونامی',UNESCO),(11,10,'روز جهانی علم در خدمت صلح و توسعه',UNESCO),(11,14,'روز جهانی دیابت',WHO),(11,16,'روز جهانی مدارا',UN),(11,20,'روز جهانی کودک',UN),(11,25,'روز جهانی منع خشونت علیه زنان',UN),
 (12,1,'روز جهانی ایدز',WHO),(12,3,'روز جهانی افراد دارای معلولیت',UN),(12,5,'روز جهانی داوطلبان',UN),(12,9,'روز جهانی مبارزه با فساد',UN),(12,10,'روز حقوق بشر',UN),(12,11,'روز جهانی کوهستان',UN),(12,18,'روز جهانی مهاجران',UN)
]

def on_date(day):
    from iran_calendar import iran_on_date
    return iran_on_date(day)+[dict(title=t,date=day,source=s,kind='جهانی',holiday=False) for m,d,t,s in DAYS if (m,d)==(day.month,day.day)]

def for_month(year,month):
    first=jdatetime.date(year,month,1).togregorian()
    ny,nm=(year+1,1) if month==12 else (year,month+1)
    end=jdatetime.date(ny,nm,1).togregorian();items=[];cursor=first
    while cursor<end:
        items.extend(on_date(cursor));cursor+=timedelta(days=1)
    return items

@lru_cache(maxsize=100)
def for_year(year):
    return tuple(item for month in range(1,13) for item in for_month(year,month))

def search_text(value):
    from storage import normalize
    return ' '.join(normalize(value).replace('ي','ی').replace('ك','ک').casefold().split())

def find_occasions(year,month,query=''):
    from storage import MONTHS,jformat
    query=search_text(query)
    items=for_year(year) if query else for_month(year,month)
    if not query:return list(items)
    result=[]
    for item in items:
        jd=jdatetime.date.fromgregorian(date=item['date']);haystack=item['title']+' '+MONTHS[jd.month-1]+' '+jformat(jd)+' '+item['date'].isoformat()
        if query in search_text(haystack):result.append(item)
    return result
