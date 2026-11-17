"""Preview monthly USB exports, with explicit field mapping and idempotent rows."""
import csv,io,json,re,hashlib,zipfile
from pathlib import Path
from datetime import date,datetime,time
import jdatetime
from storage import parse_j,normalize

FIELDS={'employee_code':'کد پرسنلی','date':'روز','check_in':'ورود','check_out':'خروج','minutes':'دقایق کار'}
ALIASES={'employee_code':['کد پرسنلی','کد','شماره پرسنلی','employee_code','employee id','personnel'], 'date':['تاریخ','روز','date'], 'check_in':['ورود','ساعت ورود','in','check_in'], 'check_out':['خروج','ساعت خروج','out','check_out'], 'minutes':['دقایق کار','دقیقه','minutes']}
def read_table(path):
    path=Path(path)
    if path.stat().st_size>20*1024*1024:raise ValueError('فایل تردد باید کوچک‌تر از ۲۰ مگابایت باشد.')
    if path.suffix.lower()=='.xlsx':
        from openpyxl import load_workbook
        with zipfile.ZipFile(path) as z:
            if sum(i.file_size for i in z.infolist())>100*1024*1024:raise ValueError('حجم بازشده فایل بیش از حد مجاز است.')
        book=load_workbook(path,read_only=True,data_only=True)
        try:
            sheet=book.active
            if sheet.max_row>50001 or sheet.max_column>100:raise ValueError('حداکثر ۵۰ هزار ردیف و ۱۰۰ ستون پشتیبانی می‌شود.')
            rows=[]
            for row in sheet.iter_rows():
                values=[]
                for cell in row:
                    value=cell.value
                    if isinstance(value,int) and re.fullmatch('0+',cell.number_format or ''):value=str(value).zfill(len(cell.number_format))
                    values.append(value if value is not None else '')
                rows.append(values)
        finally:book.close()
    else:
        raw=path.read_bytes();content=None
        encodings=['utf-16'] if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else ['utf-8-sig','cp1256']
        for enc in encodings:
            try:content=raw.decode(enc);break
            except UnicodeError:continue
        if content is None:raise ValueError('کدگذاری متن قابل‌خواندن نیست.')
        try:dialect=csv.Sniffer().sniff(content[:8000],delimiters=',;\t|')
        except csv.Error:dialect=csv.excel_tab if '\t' in content else csv.excel
        rows=[]
        for row in csv.reader(io.StringIO(content),dialect):
            if len(rows)>50000 or len(row)>100:raise ValueError('فایل بیش از حد بزرگ است.')
            rows.append(row)
    rows=[r for r in rows if any(str(x).strip() for x in r)]
    if len(rows)<2:raise ValueError('فایل باید ردیف عنوان ستون‌ها و حداقل یک ردیف داده داشته باشد.')
    return [str(x).strip() for x in rows[0]],rows[1:]
def guess_mapping(headers):
    return {key:next((i for i,h in enumerate(headers) if normalize(h).casefold() in [normalize(a).casefold() for a in names]),-1) for key,names in ALIASES.items()}
def day_value(value):
    if isinstance(value,datetime):value=value.date()
    if isinstance(value,date):return jdatetime.date.fromgregorian(date=value)
    text=normalize(value)
    if re.match(r'^(19|20)\d{2}[-/.]',text):return jdatetime.date.fromgregorian(date=date.fromisoformat(text[:10].replace('/','-').replace('.','-')))
    return parse_j(text)
def clock(value):
    if value in ('',None):return '',None
    if isinstance(value,(time,datetime)):value=value.strftime('%H:%M')
    if isinstance(value,(float,int)) and 0<=value<1:value=f'{int(round(value*24*60))//60:02d}:{int(round(value*24*60))%60:02d}'
    match=re.fullmatch(r'(\d{1,2}):(\d{2})(?::\d{2})?',normalize(value))
    if not match:raise ValueError('ساعت باید HH:MM باشد.')
    hour,minute=map(int,match.groups())
    if not 0<=hour<24 or not 0<=minute<60:raise ValueError('ساعت معتبر نیست.')
    return f'{hour:02d}:{minute:02d}',hour*60+minute
def preview(headers,rows,mapping,month):
    match=re.fullmatch(r'(1[34]\d{2})/(0?[1-9]|1[0-2])',normalize(month))
    if not match:raise ValueError('ماه را به صورت ۱۴۰۵/۰۸ وارد کنید.')
    year,mon=map(int,match.groups());result=[];seen=set()
    if any(mapping.get(k,-1)<0 for k in ('employee_code','date')):raise ValueError('ستون کد پرسنلی و تاریخ را انتخاب کنید.')
    for line,row in enumerate(rows,2):
        item={'line':line,'valid':False}
        try:
            value=lambda key:row[mapping[key]] if 0<=mapping.get(key,-1)<len(row) else ''
            code=normalize(value('employee_code'));day=day_value(value('date'))
            if not code:raise ValueError('کد پرسنلی خالی است.')
            if (day.year,day.month)!=(year,mon):raise ValueError('تاریخ خارج از ماه انتخاب‌شده است.')
            start,mins_in=clock(value('check_in'));end,mins_out=clock(value('check_out'))
            if value('minutes') not in ('',None):
                from penalties import number
                mins=number(value('minutes'))
                if mins!=int(mins) or mins>24*60:raise ValueError('دقایق کار باید عدد صحیح تا ۱۴۴۰ باشد.')
                mins=int(mins)
            elif mins_in is not None and mins_out is not None:mins=(mins_out-mins_in)%(24*60)
            elif mins_in is not None or mins_out is not None:mins=0
            else:raise ValueError('دقیقه کار یا دست‌کم یک ساعت ورود / خروج لازم است.')
            incomplete=mins_in is None or mins_out is None
            p=dict(title='تردد '+code+' · '+str(day),employee_code=code,date=day.strftime('%Y/%m/%d'),check_in=start,check_out=end,minutes=str(mins),status='needs_review' if incomplete else 'imported',notes='ورود فایل ماهانه؛ ردیف '+str(line)+(' · ورود یا خروج ناقص است' if incomplete else ''))
            signature=json.dumps([code,p['date'],start,end,mins],ensure_ascii=False)
            p['import_key']=hashlib.sha256(signature.encode()).hexdigest()
            if p['import_key'] in seen:raise ValueError('این ردیف در همین فایل تکراری است.')
            seen.add(p['import_key']);item.update(valid=True,payload=p)
        except (ValueError,TypeError,IndexError) as exc:item['error']=str(exc)
        result.append(item)
    return result
