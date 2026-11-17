"""Monthly attendance reports. All numbers are estimates, never an absence verdict."""
from datetime import date,datetime,timedelta
from decimal import Decimal
import copy,json,re
import jdatetime
from storage import parse_j,normalize
from attendance_import import clock

def canonical(day):return f'{day.year:04d}/{day.month:02d}/{day.day:02d}'
def default_policy():
    return dict(week={str(d):dict(working=d in (0,1,2,5,6),start='09:00',end='17:00',break_minutes=0) for d in range(7)},exceptions={},people={},exclude_official_holidays=True,overtime_rule='daily_excess')

def validate_shift(shift):
    if not isinstance(shift,dict) or not isinstance(shift.get('working',False),bool):raise ValueError('تنظیم روز کاری معتبر نیست.')
    _,start=clock(shift.get('start','09:00'));_,end=clock(shift.get('end','17:00'))
    if start is None or end is None:raise ValueError('ساعت شروع و پایان برنامه لازم است.')
    minutes=(end-start)%(24*60)
    if not minutes:raise ValueError('ساعت شروع و پایان برنامه نمی‌تواند یکسان باشد.')
    try:break_minutes=int(normalize(str(shift.get('break_minutes',0))))
    except (TypeError,ValueError):raise ValueError('مدت استراحت باید عدد صحیح باشد.')
    if not 0<=break_minutes<minutes:raise ValueError('مدت استراحت باید کمتر از طول شیفت باشد.')
    return dict(working=shift['working'],start=clock(shift.get('start','09:00'))[0],end=clock(shift.get('end','17:00'))[0],break_minutes=break_minutes)

def normalize_policy(store,actor,company,payload):
    store.require(isinstance(payload,dict),'برنامه تردد معتبر نیست.');result=default_policy();week=payload.get('week',result['week']);exceptions=payload.get('exceptions',{});people=payload.get('people',{})
    store.require(isinstance(week,dict) and set(week)==set(map(str,range(7))),'برنامه تمام روزهای هفته لازم است.');result['week']={key:validate_shift(week[key]) for key in week}
    def dates(values):
        store.require(isinstance(values,dict) and len(values)<=5000,'استثناهای برنامه معتبر نیستند.');return {canonical(parse_j(day)):validate_shift(shift) for day,shift in values.items()}
    result['exceptions']=dates(exceptions);store.require(isinstance(people,dict) and len(people)<=2000,'فهرست کارکنان معتبر نیست.');result['people']={}
    for user,p in people.items():
        store.require(isinstance(p,dict) and store.role(store.user(user),company) is not None,'فرد برنامه باید عضو شرکت باشد.');week=p.get('week',{});store.require(isinstance(week,dict) and all(k in set(map(str,range(7))) for k in week),'روزهای برنامه فرد معتبر نیستند.');result['people'][user]=dict(week={k:validate_shift(v) for k,v in week.items()},exceptions=dates(p.get('exceptions',{})))
    holidays=payload.get('exclude_official_holidays',True);store.require(isinstance(holidays,bool),'تنظیم تعطیلات معتبر نیست.');result['exclude_official_holidays']=holidays;rule=payload.get('overtime_rule','daily_excess');store.require(rule in ('daily_excess','outside_schedule'),'روش برآورد اضافه‌کاری معتبر نیست.');result['overtime_rule']=rule
    return result

def merge_intervals(intervals):
    result=[]
    for start,end in sorted(intervals):
        if result and start<=result[-1][1]:result[-1]=(result[-1][0],max(end,result[-1][1]))
        else:result.append((start,end))
    return result

def duration(intervals):return sum(b-a for a,b in merge_intervals(intervals))

def outside(intervals,start,end):
    return sum(max(0,min(b,start)-a)+max(0,b-max(a,end)) for a,b in merge_intervals(intervals))

class AttendanceMixin:
    def attendance_people(self,actor,company):
        self.desk_company(actor,company);self.require_module(actor,company,'attendance','view');manager=self.desk_manager(actor,company);result=[]
        # Use server ACLs for records as well as the owner check; a name or code
        # supplied by a client never establishes that person's identity.
        for r in self.all_visible(actor,'employee',company):
            p=r['payload']
            if not manager and p.get('user_id')!=actor['id']:continue
            result.append(dict(employee_code=p.get('employee_code',''),user_id=p.get('user_id',''),name=p.get('title',r['title'])))
        result.sort(key=lambda x:(x['name'],x['employee_code']))
        return dict(company=company,is_manager=manager,people=result)

    def attendance_report(self,actor,company,month,employee_code):
        from org_store import DomainError
        self.desk_company(actor,company);self.require_module(actor,company,'attendance','view');employee_code=normalize(employee_code);person=next((x for x in self.attendance_people(actor,company)['people'] if normalize(x['employee_code'])==employee_code),None)
        self.require(bool(person),'پرونده تردد این فرد در دسترس نیست.');manager=self.desk_manager(actor,company)
        first=parse_j(normalize(month)+'/01');month=canonical(first)[:7];last=(jdatetime.date(first.year+1,1,1) if first.month==12 else jdatetime.date(first.year,first.month+1,1)).togregorian();start=first.togregorian();policy=self.workspace_policy(actor,company,'attendance')['value'];specific=policy.get('people',{}).get(person['user_id'],{});week=policy['week'];exceptions=policy.get('exceptions',{});holiday_mode=policy.get('exclude_official_holidays',True)
        with self.db() as c:
            records=[dict(r,payload=json.loads(r['payload'])) for r in c.execute("SELECT * FROM records WHERE company_id=? AND kind='attendance' AND deleted=0",(company,))]
            leaves=[dict(r,payload=json.loads(r['payload'])) for r in c.execute("SELECT * FROM desk_leaves WHERE company_id=? AND requester_id=? AND status='approved' AND deleted=0",(company,person['user_id']))] if person['user_id'] else []
        by_date={}
        for r in records:
            p=r['payload']
            if normalize(p.get('employee_code',''))!=employee_code or not self.readable(actor,r):continue
            try:day=canonical(parse_j(p.get('date','')))
            except ValueError:continue
            if not day.startswith(month+'/'):continue
            by_date.setdefault(day,[]).append(r)
        from occasions import on_date
        days=[];totals=dict(worked_minutes=0,approved_minutes=0,overtime_minutes=0,approved_overtime_minutes=0,days_with_records=0,missing_days=0,incomplete_days=0);today=date.today();day=start
        while day<last:
            jalali=canonical(jdatetime.date.fromgregorian(date=day));weekly=week[str(day.weekday())];personal_week=specific.get('week',{}).get(str(day.weekday()));override=specific.get('exceptions',{}).get(jalali);company_override=exceptions.get(jalali);shift=override or company_override or personal_week or weekly;is_exception=bool(override or company_override);holiday=bool(holiday_mode and any(x.get('holiday') for x in on_date(day)));working=bool(shift['working'] and (not holiday or is_exception));_,s=clock(shift['start']);_,e=clock(shift['end']);e+=1440 if e<=s else 0;required=(e-s-int(shift.get('break_minutes',0))) if working else 0;leave=[];full_leave=False;hourly=Decimal(0)
            for item in leaves:
                p=item['payload']
                if parse_j(p['start_date']).togregorian()<=day<=parse_j(p['end_date']).togregorian():
                    leave.append(dict(type=p['leave_type'],hours=p.get('hours','0')))
                    if p['leave_type']=='ساعتی':hourly+=Decimal(p.get('hours','0'))
                    else:full_leave=True
            required=0 if full_leave else max(0,required-int(hourly*60));entries=[];intervals=[];approved=[];extra_recorded=0;approved_recorded=0
            ordered=sorted(by_date.get(jalali,[]),key=lambda r:(normalize(r['payload'].get('check_in','')) or '99:99',normalize(r['payload'].get('check_out','')) or '99:99',r['id']))
            for r in ordered:
                p=r['payload'];flags=[];in_str,in_min=clock(p.get('check_in'));out_str,out_min=clock(p.get('check_out'));minutes=int(Decimal(p.get('minutes') or 0));reported=max(0,min(1440,minutes));interval=None
                if in_min is None or out_min is None:flags.append('incomplete_interval')
                else:
                    end=out_min+(1440 if out_min<in_min else 0);span=end-in_min
                    if not span:flags.append('zero_interval')
                    elif reported>span:flags.append('minutes_exceed_interval')
                    interval=(in_min,end) if span else None
                if interval and any(interval[0]<b and a<interval[1] for a,b in intervals):flags.append('overlap')
                rejected=p.get('status')=='rejected'
                if rejected:flags.append('rejected')
                if interval and not rejected:
                    # Recorded durations can be lower than a clock span (e.g. breaks).
                    # Apply them proportionally to uncovered minutes to avoid double count.
                    uncovered=duration(intervals+[interval])-duration(intervals);extra_recorded+=min(reported,uncovered);intervals.append(interval)
                    if p.get('status')=='approved':uncovered_approved=duration(approved+[interval])-duration(approved);approved_recorded+=min(reported,uncovered_approved);approved.append(interval)
                elif not interval and p.get('status')=='approved':
                    # Duration-only source explicitly reviewed by the manager.
                    extra_recorded+=reported;approved_recorded+=reported;flags.append('duration_only_approved')
                entries.append(dict(id=r['id'],version=r['version'],check_in=in_str,check_out=out_str,minutes=reported,status=p.get('status','imported'),flags=flags))
            entries.sort(key=lambda x:(x['check_in'] or '99:99',x['check_out'] or '99:99',x['id']));flags=[]
            if entries:totals['days_with_records']+=1
            elif working and not leave and day<=today:flags.append('no_record');totals['missing_days']+=1
            if any(x['flags'] for x in entries):flags.append('needs_review');totals['incomplete_days']+=1
            if full_leave and entries:flags.append('leave_work_overlap')
            # Outside-schedule is an estimate of clock time. Bound it by reported
            # worked minutes when source records already deduct breaks.
            if full_leave:overtime=approved_overtime=0
            elif policy['overtime_rule']=='outside_schedule' and working:
                overtime=min(extra_recorded,outside(intervals,s,e));approved_overtime=min(approved_recorded,outside(approved,s,e))
            else:overtime=max(0,extra_recorded-required);approved_overtime=max(0,approved_recorded-required)
            weekday=['دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه','شنبه','یکشنبه'][day.weekday()]
            data=dict(date=jalali,weekday=weekday,weekday_index=day.weekday(),working_day=working,official_holiday=holiday,required_minutes=required,leave=leave,entries=entries,worked_minutes=extra_recorded,approved_minutes=approved_recorded,overtime_minutes=overtime,approved_overtime_minutes=approved_overtime,flags=flags)
            days.append(data)
            for key in ('worked_minutes','approved_minutes','overtime_minutes','approved_overtime_minutes'):totals[key]+=data[key]
            day+=timedelta(days=1)
        chart=[dict(date=d['date'],worked_minutes=d['worked_minutes'],overtime_minutes=d['overtime_minutes']) for d in days]
        return dict(company=company,month=month,is_manager=manager,person=person,days=days,totals=totals,chart=chart,policy=policy,note='برآورد بر اساس تردد ثبت‌شده و برنامه تعریف‌شده است؛ نبود تردد به معنی غیبت قطعی نیست. اضافه‌کاری، تأیید یا محاسبه قانونی حقوق محسوب نمی‌شود.',holidays_verified_through=1405)
