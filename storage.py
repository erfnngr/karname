"""Local, private data and Jalali date helpers for Tax Calendar FA."""
import os, sys, json, shutil, re, uuid, tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
import jdatetime
from functools import lru_cache

MONTHS = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند']
WEEKDAYS = ['شنبه','یکشنبه','دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه']
FADIGITS = '۰۱۲۳۴۵۶۷۸۹'
TRANS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
DEFAULT_SETTINGS = {'startup': False, 'lead_days': [20,15,10,5,4,3,2,1,0], 'reminder_enabled': True, 'show_startup_popup': True, 'news_enabled': True,
 'theme':'light','theme_preset':'default','font_family':'Vazirmatn','font_size':13,'default_lead_days':[20,15,10,5,4,3,2,1,0],'personal_lead_days':[20,15,10,5,4,3,2,1,0],
 'default_reminders':True,'personal_reminders':True,'overdue_reminders':False,'popup_seconds':5,'popup_opacity':96,'popup_fade_ms':450,'popup_bg':'#153D50','popup_fg':'#FFFFFF',
 'check_reminders':True,'check_lead_days':[20,15,10,5,4,3,2,1,0],
 'monthly_summary':False,'windows_notifications':False,'news_interval':60,'news_proxy':'','daily_quote_enabled':True,'weather_enabled':True,
 'event_insurance_color':'#369ED8','event_insurance_opacity':18,'event_tax_color':'#26B67B','event_tax_opacity':16,'event_personal_color':'#9B68DB','event_personal_opacity':18,
 'home_text_color':'#FFFFFF','home_panel_color':'#12314A','home_panel_opacity':96,'mana_popup_color':'#D8EFF0','airia_popup_color':'#E0EBF6','arka_popup_color':'#DDEBF8','personal_popup_color':'#EEE5FA'}

def fa(number):
    return str(number).translate(str.maketrans('0123456789',FADIGITS))

def normalize(text):
    return str(text or '').translate(TRANS).replace('\u200c',' ').strip()

def jalali_date(year, month, day):
    return jdatetime.date(int(year),int(month),int(day))

@lru_cache(maxsize=12000)
def parse_j(text):
    clean=normalize(text).replace('-', '/').replace('.', '/')
    m=re.fullmatch(r'\s*(1[34]\d\d)/(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])\s*', clean)
    if not m: raise ValueError('تاریخ را به صورت ۱۴۰۵/۰۸/۰۳ وارد کنید.')
    d=jalali_date(*map(int,m.groups()))
    return d

def jformat(d):
    return fa(f'{d.year:04d}/{d.month:02d}/{d.day:02d}')

def gregorian(d):
    return d.togregorian()

def today_j():
    return jdatetime.date.fromgregorian(date=date.today())

@lru_cache(maxsize=2000)
def month_last_day(y,m):
    ny,nm=(y+1,1) if m==12 else (y,m+1)
    return jdatetime.date.fromgregorian(date=jalali_date(ny,nm,1).togregorian()-timedelta(days=1)).day

def extract_jalali(text):
    """Parse explicit Persian date / 'end of month'; never silently rewrite invalid dates."""
    if isinstance(text,date):
        day=text.date() if isinstance(text,datetime) else text
        jd=jdatetime.date.fromgregorian(date=day)
        return f'{jd.year:04d}/{jd.month:02d}/{jd.day:02d}',''
    clean=normalize(text)
    if re.search(r'1[34]\d{2}[/.-]\d{1,2}[/.-]\d{1,2}',clean):
        match=re.search(r'1[34]\d{2}[/.-]\d{1,2}[/.-]\d{1,2}',clean)
        try:
            jd=parse_j(match.group());return f'{jd.year:04d}/{jd.month:02d}/{jd.day:02d}',''
        except ValueError:return '','روز درج‌شده با تقویم شمسی مطابقت ندارد'
    pat='('+'|'.join(MONTHS)+')'
    match=re.search(r'(\d{1,2})\s*'+pat+r'\s*(1[34]\d{2})',clean)
    if match:
        d=int(match.group(1)); m=MONTHS.index(match.group(2))+1; y=int(match.group(3))
        try:return f'{y:04d}/{m:02d}/{d:02d}', '' if jalali_date(y,m,d) else ''
        except (ValueError,OverflowError):return '', 'روز درج‌شده با تقویم شمسی مطابقت ندارد'
    match=re.search('پایان\\s*'+pat+r'\s*(1[34]\d{2})',clean)
    if match:
        m=MONTHS.index(match.group(1))+1;y=int(match.group(2))
        return f'{y:04d}/{m:02d}/{month_last_day(y,m):02d}', ''
    return '', 'روز/ماه/سال از ددلاین استخراج نشد؛ تاریخ را دستی وارد کنید'

def period_problem(period, date_jalali):
    if not date_jalali:return ''
    match=re.search('('+'|'.join(MONTHS)+r')\s*([۰-۹٠-٩0-9]{4})',str(period))
    if not match:return ''
    month=MONTHS.index(match.group(1))+1
    year=int(normalize(match.group(2)))
    y,m,_=map(int,date_jalali.split('/'))
    if y*12+m < year*12+month:return 'سررسید قبل از ماه درج‌شده در ردیف اکسل است؛ بررسی شود'
    return ''

def next_month(year, month, count=1):
    x=year*12+(month-1)+count
    return x//12,x%12+1

def occurrence(ev, after=None):
    """Next occurrence on or after Gregorian date 'after'."""
    if ev.get('needs_review') or not ev.get('date_jalali') or ev.get('done'):return None
    try: base=parse_j(ev['date_jalali'])
    except Exception:return None
    threshold=after or date.today()
    orig=base.togregorian()
    if orig>=threshold and orig.isoformat() not in ev.get('completed_occurrences',[]):return orig
    repeat=ev.get('recurrence','بدون تکرار')
    step={'ماهانه':1,'سه‌ماهه':3,'سالانه':12}.get(repeat)
    if not step:return None
    target=jdatetime.date.fromgregorian(date=threshold)
    k=max(0, ((target.year-base.year)*12+target.month-base.month)//step)
    for _ in range(len(ev.get('completed_occurrences',[]))+3):
        y,m=next_month(base.year,base.month,k*step)
        d=min(base.day,month_last_day(y,m))
        candidate=jalali_date(y,m,d).togregorian()
        if candidate>=threshold and candidate.isoformat() not in ev.get('completed_occurrences',[]):return candidate
        k+=1
    return None

def due_on(ev, day):
    if ev.get('needs_review') or ev.get('done') or not ev.get('date_jalali'):return False
    try:
        first=parse_j(ev['date_jalali']).togregorian()
        if first>day:return False
        if ev.get('recurrence','بدون تکرار')=='بدون تکرار':return first==day
        return occurrence(ev,day)==day
    except Exception:return False

_PROFILE_DIR=None
def set_profile(folder):
    global _PROFILE_DIR
    _PROFILE_DIR=Path(folder) if folder is not None else None
def app_dir():
    if _PROFILE_DIR is not None:return _PROFILE_DIR
    if os.getenv('TAXCALENDAR_DATA_DIR'):
        return Path(os.environ['TAXCALENDAR_DATA_DIR'])
    root=os.getenv('APPDATA') or str(Path.home()/'.config')
    return Path(root)/'TaghvimMaliatiFA'

def package_file(rel):
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    return root/rel

def data_path():return app_dir()/'calendar.json'

def ensure_data():
    app_dir().mkdir(parents=True,exist_ok=True)
    target=data_path()
    if not target.exists():
        with package_file('data/initial_events.json').open('r',encoding='utf-8') as f: data=json.load(f)
        data['settings']=dict(DEFAULT_SETTINGS)
        save_data(data)
    return target

def load_data():
    ensure_data()
    recovered=False
    try:
        with data_path().open('r',encoding='utf-8') as f:d=json.load(f)
        if not isinstance(d,dict) or not isinstance(d.get('events',[]),list):raise ValueError('ساختار فایل اطلاعات معتبر نیست.')
    except (ValueError,UnicodeError):
        backup=app_dir()/'calendar-backup.json'
        try:
            d=json.loads(backup.read_text(encoding='utf-8'))
            if not isinstance(d,dict) or not isinstance(d.get('events'),list):raise ValueError()
        except (OSError,ValueError,UnicodeError) as exc:
            raise ValueError('فایل اطلاعات و پشتیبان قابل خواندن نیستند؛ فایل‌ها حفظ شده‌اند. از پشتیبان سالم استفاده کنید.') from exc
        shutil.copy2(data_path(),app_dir()/('calendar-damaged-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json'))
        save_data(d,make_backup=False);recovered=True
    d.setdefault('settings',dict(DEFAULT_SETTINGS));d.setdefault('events',[])
    for k,v in DEFAULT_SETTINGS.items():d['settings'].setdefault(k,v)
    old_weather_url='https://f1a494a8c367d2.lhr.life'
    weather_url_changed=str(d['settings'].get('weather_api_base') or '').rstrip('/')==old_weather_url
    if weather_url_changed:d['settings']['weather_api_base']=''
    ui_changed=d.get('ui_version')!=4
    if ui_changed:
        shutil.copy2(data_path(),app_dir()/'calendar-before-v4.json')
        d['settings']['monthly_summary']=False;d['settings']['overdue_reminders']=False;d['ui_version']=4
    from planning import extend_calendar
    from reminders import migrate
    changed=d.get('planning_version')!=3 or d.get('reminders_version')!=3
    if changed:
        if data_path().exists():shutil.copy2(data_path(),app_dir()/'calendar-before-v3.json')
        extend_calendar(d);migrate(d);d['schema_version']=3
    cleanup_changed=d.get('source_cleanup_version')!=1
    if cleanup_changed:
        from data_cleanup import archive_excel_duplicates
        archive_excel_duplicates(d);d['source_cleanup_version']=1
        snapshot=app_dir()/'calendar-before-v4.1.json'
        if not snapshot.exists():shutil.copy2(data_path(),snapshot)
    company_changed=d.get('company_defaults_version')!=1
    if company_changed:
        snapshot=app_dir()/'calendar-before-company-v86.json'
        if not snapshot.exists():shutil.copy2(data_path(),snapshot)
        from company_defaults import migrate_company_defaults
        migrate_company_defaults(d)
    if changed or ui_changed or cleanup_changed or company_changed or weather_url_changed:save_data(d)
    if recovered:d['_recovery_notice']='فایل اطلاعات آسیب دیده بود؛ نسخه پشتیبان سالم بازیابی و اصل فایل آسیب‌دیده حفظ شد.'
    return d

def save_data(data,make_backup=True):
    app_dir().mkdir(parents=True,exist_ok=True)
    dest=data_path()
    if make_backup and dest.exists():shutil.copy2(dest,app_dir()/'calendar-backup.json')
    fd,temp=tempfile.mkstemp(prefix='calendar-',suffix='.tmp',dir=str(app_dir()))
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False,indent=2)
            f.flush();os.fsync(f.fileno())
        os.replace(temp,dest)
    finally:
        if os.path.exists(temp):os.remove(temp)

def new_event(company,title,date_jalali,notes='',priority='متوسط',repeat='بدون تکرار',lead=None):
    return dict(id=str(uuid.uuid4()),company=company,source_sheet='دستی',source_row=0,period='',title=title,
      date_jalali=date_jalali,original_deadline=jformat(parse_j(date_jalali)),notes=notes,
      priority=priority,recurrence=repeat,done=False,needs_review=False,review_reason='',created_from_excel=False,
      lead_days=lead if lead is not None else [20,15,10,5,4,3,2,1,0],reminder_custom=lead is not None,reminder_group='personal',snooze_until=None,last_alerts={},completed_occurrences=[])

def import_excel(filename, data):
    """Add only unseen rows, do not overwrite locally edited tasks or annotations."""
    from openpyxl import load_workbook
    book=load_workbook(filename,read_only=True,data_only=True)
    all_imported=data['events']+[entry['event'] for key in ('source_duplicate_archive','company_defaults_archive') for entry in data.get(key,[]) if isinstance(entry,dict) and isinstance(entry.get('event'),dict)]
    def fingerprint(company,row,period,title):return (company,row,normalize(period) or normalize(title))
    fingerprints={fingerprint(e.get('company'),e.get('source_row'),e.get('period'),e.get('source_title',e.get('title'))) for e in all_imported if e.get('created_from_excel')}
    staged=[];companies=[];flagged=0
    try:
        for sheet in book.worksheets:
            if 'راهنما' in sheet.title:continue
            rows=sheet.iter_rows(min_row=2,max_col=4,values_only=True)
            for ix,row in enumerate(rows,2):
                period,title,deadline,notes=(list(row)+[None]*4)[:4]
                if not title:continue
                company=sheet.title
                identity=fingerprint(company,ix,period,title)
                if identity in fingerprints:continue
                d,err=extract_jalali(deadline or '')
                if d and period_problem(str(period),d):err=period_problem(str(period),d)
                if err:d='';flagged+=1
                ev=new_event(company,str(title).strip(),d or jformat(today_j()))
                ev.update(source_sheet=company,source_row=ix,source_title=str(title).strip(),period=str(period or ''),original_deadline=str(deadline or ''),
                    notes=str(notes or ''),date_jalali=d or '',needs_review=bool(err),review_reason=err,
                    created_from_excel=True,reminder_group='default',reminder_custom=False)
                staged.append(ev);fingerprints.add(identity)
                if company not in companies:companies.append(company)
    finally:book.close()
    data['events'].extend(staged)
    for company in companies:
        if company not in data.setdefault('companies',[]):data['companies'].append(company)
    from data_cleanup import archive_excel_duplicates
    archive_excel_duplicates(data)
    return len(staged),flagged
