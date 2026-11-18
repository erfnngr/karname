"""Incomplete experimental field projection, not a filing or DBF export.

Only mappings explicitly supported by observed headers and task requirements are
projected. Unresolved fields must never be silently populated with guessed zeros.
"""
from storage import parse_j

def worker_projection(workshop,draft,line,person,amounts):
    profile=person['profile'];period=draft['period'].split('/')
    if len(period)!=2 or not period[0].isdigit() or not period[1].isdigit():raise ValueError('ماه لیست معتبر نیست.')
    def day(value):
        if not value:return ''
        date=parse_j(value);return f'{date.year:04d}{date.month:02d}{date.day:02d}'
    def text(key):return str(profile.get(key) or '')
    projected={
        'DSW_ID':str(workshop.get('workshop_code') or ''),'DSW_YY':int(period[0])%100,'DSW_MM':int(period[1]),'DSW_LISTNO':str(draft['list_no']),
        'DSW_ID1':text('insurance_number'),'DSW_FNAME':text('first_name'),'DSW_LNAME':text('last_name'),'DSW_DNAME':text('father_name'),
        'DSW_IDNO':text('birth_certificate'),'DSW_IDPLC':text('issue_place'),'DSW_IDATE':day(text('issue_date')),'DSW_BDATE':day(text('birth_date')),
        'DSW_SEX':text('gender'),'DSW_NAT':text('nationality'),'DSW_OCP':text('job_title'),'DSW_SDATE':day(text('start_date')),'DSW_EDATE':day(text('end_date')),
        'DSW_DD':int(line['days']),'DSW_ROOZ':int(line['daily_wage']),'DSW_MAH':int(amounts['monthly_wage']),
        'DSW_MASH':int(amounts['insured_total']),'DSW_TOTL':int(amounts['gross_total']),'DSW_BIME':int(amounts['worker']),
        'DSW_JOB':text('job_code'),'PER_NATCOD':text('national_id'),'DSW_INC':int(line['daily_seniority']),'DSW_SPOUSE':str(line['spouse_benefit'])}
    return {'fields':projected,'unresolved':['DSW_MAZ','DSW_PRATE'],
            'missing':[key for key in ('DSW_ID','DSW_LISTNO','DSW_ID1','DSW_FNAME','DSW_LNAME','DSW_DNAME','DSW_IDNO','DSW_IDPLC','DSW_BDATE','DSW_NAT','DSW_OCP','DSW_SDATE','DSW_JOB','PER_NATCOD') if not projected[key]]+(['DSW_SEX'] if projected['DSW_SEX'] not in ('زن','مرد') else [])}

def workshop_projection(workshop,draft,result):
    """Reconcile known totals and leave unsupported values explicitly unresolved."""
    rows=draft.get('rows',[]);calculated=result.get('rows',[]);totals=result.get('totals',{})
    if not rows or not isinstance(calculated,list) or len(rows)!=len(calculated):raise ValueError('تعداد ردیف‌ها و محاسبات برابر نیست.')
    ids=[row['profile_id'] for row in rows];calculated_ids=[row['profile_id'] for row in calculated]
    if len(set(ids))!=len(ids) or len(set(calculated_ids))!=len(calculated_ids) or set(ids)!=set(calculated_ids):raise ValueError('کارکنان محاسبه با لیست تطبیق ندارند.')
    numeric=('monthly_wage','seniority_total','spouse_benefit','insured_total','gross_total','worker','employer','unemployment','insurance_total')
    try:
        for key in numeric:
            total=sum(int(row['amounts'][key]) for row in calculated)
            if total!=int(totals[key]):raise ValueError('جمع '+key+' با جزئیات کارکنان برابر نیست.')
        days=sum(int(row['days']) for row in rows)
        if days!=int(totals['days']):raise ValueError('جمع روزهای بیمه با جزئیات برابر نیست.')
        year,month=map(int,draft['period'].split('/'))
        if not 1300<=year<=1499 or not 1<=month<=12:raise ValueError('ماه معتبر نیست.')
    except (KeyError,TypeError,OverflowError) as exc:raise ValueError('اطلاعات جمع محاسبه کامل نیست.') from exc
    projected={'DSK_ID':str(workshop.get('workshop_code') or ''),'DSK_NAME':str(workshop.get('title') or ''),
               'DSK_FARM':str(workshop.get('employer_name') or ''),'DSK_ADRS':str(workshop.get('address') or ''),
               'DSK_YY':year%100,'DSK_MM':month,'DSK_LISTNO':str(draft['list_no']),'DSK_NUM':len(rows),'DSK_TDD':days,
               'DSK_TMAH':int(totals['monthly_wage']),'DSK_TMASH':int(totals['insured_total']),
               'DSK_TTOTL':int(totals['gross_total']),'DSK_INC':int(totals['seniority_total']),'DSK_SPOUSE':int(totals['spouse_benefit'])}
    return {'fields':projected,'unresolved':['DSK_KIND','DSK_DISC','DSK_TROOZ','DSK_TMAZ','DSK_TBIME','DSK_TKOSO','DSK_BIC','DSK_RATE','DSK_PRATE','DSK_BIMH','MON_PYM'],
            'missing':[key for key in ('DSK_ID','DSK_NAME','DSK_FARM','DSK_ADRS','DSK_LISTNO') if not projected[key]]}
