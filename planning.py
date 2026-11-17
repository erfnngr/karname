"""Deterministic future planning, separate from confirmed statutory deadlines."""
import hashlib
import json
from storage import package_file,normalize,MONTHS,next_month,month_last_day,jalali_date,new_event

def kind_for(event):
    t=event.get('title','')
    for key,word in (('insurance','بیمه'),('vat','ارزش افزوده'),('salary','حقوق'),('rent','اجاره'),('books','دفاتر'),('performance','عملکرد')):
        if word in t:return key
    return None

def extend_calendar(data):
    if data.get('planning_version')==3:return 0
    seed=json.loads(package_file('data/initial_events.json').read_text(encoding='utf-8'))
    templates={}
    for event in seed['events']:
        kind=kind_for(event)
        if kind:templates.setdefault(event['company'],{}).setdefault(kind,event)
    ids={e['id'] for e in data['events']};added=0
    # Original workbook covers through Mehr 1406. Generate after that horizon.
    for year in range(1406,1426):
        for month in range(1,13):
            if (year,month)<(1406,8):continue
            for company,kinds in templates.items():
                for kind,template in kinds.items():
                    if kind=='vat' and month not in (1,4,7,10):continue
                    if kind=='books' and month not in (2,5,8,11):continue
                    if kind=='performance' and month!=4:continue
                    if kind in ('insurance','salary','rent'):
                        py,pm=next_month(year,month,-1);period=MONTHS[pm-1]+' '+str(py)
                        title={'insurance':'بیمه کارکنان','salary':'مالیات حقوق','rent':'مالیات تکلیفی اجاره'}[kind]+' '+period
                        day=month_last_day(year,month)
                    elif kind in ('vat','books'):
                        py,pm=next_month(year,month,-(1 if kind=='vat' else 2))
                        season=['بهار','تابستان','پاییز','زمستان'][(pm-1)//3]
                        title=('اظهارنامه و پرداخت مالیات بر ارزش افزوده ' if kind=='vat' else 'ارسال دفاتر تجاری الکترونیکی ')+season+' '+str(py)
                        day=min(30,month_last_day(year,month)) if kind=='vat' else month_last_day(year,month)
                    else:
                        title='اظهارنامه و مالیات عملکرد سال مالی منتهی به اسفند '+str(year-1);day=31
                    identity='plan-'+hashlib.sha256(f'{company}|{kind}|{year}|{month}'.encode()).hexdigest()[:20]
                    if identity in ids:continue
                    ev=new_event(company,title,f'{year:04}/{month:02}/{day:02}',template.get('notes',''))
                    ev.update(id=identity,generated=True,planning_only=True,category='بیمه' if kind=='insurance' else 'مالیات',reminder_group='default',reminder_custom=False,template_kind=kind,
                              planning_note='موعد برنامه‌ریزی بر اساس الگوی اکسل؛ نیازمند تطبیق با قانون و اطلاعیه‌های همان دوره.')
                    data['events'].append(ev);ids.add(identity);added+=1
    data['planning_version']=3;data['planning_end']='1425/12/29'
    return added
