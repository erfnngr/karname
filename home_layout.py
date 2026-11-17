"""Layout rules for each person's editable home dashboard."""

WIDGET_NAMES={
    'today':'امروز', 'calendar':'تقویم', 'reminders':'یادآورهای امروز',
    'companies':'دستیار کارنامه', 'attendance':'ساعات کاری', 'summary':'خلاصه کارها',
    'timeline':'برنامه امروز', 'weather':'آب‌وهوا', 'quote':'سخن روز',
    'quick_notes':'یادداشت شخصی', 'quick_customers':'مشتریان', 'quick_tasks':'آخرین کارها',
}

BENTO_DEFAULT_MODULES=['workspace','chat','assistant','tax','calendar','clients']

def initial_widgets(theme, weather=True, quote=True):
    graph='weather' if weather else 'attendance'
    defaults={
        'default':['today',graph],
        'emerald_ivory':['reminders','companies','calendar','summary',graph],
        'glass_mist':['reminders','companies','calendar',graph,'summary'],
        'violet_modular':['calendar','companies',graph,'summary','reminders','timeline'],
        'bento_grid':['today',graph,'reminders','companies','calendar'],
    }
    result=list(defaults.get(theme,defaults['default']))
    if quote:result.append('quote')
    return result

def pack_widgets(order,widths,heights,columns):
    """Place items without overlaps while preserving their ordering in reading order."""
    columns=max(2,min(4,int(columns)));occupied=set();row=column=0;result=[]
    for key in order:
        try:width=max(1,min(columns,int(widths.get(key,1))))
        except (TypeError,ValueError):width=1
        try:height=max(1,min(2,int(heights.get(key,1))))
        except (TypeError,ValueError):height=1
        while True:
            if column+width>columns:row+=1;column=0;continue
            cells={(r,c) for r in range(row,row+height) for c in range(column,column+width)}
            if cells.isdisjoint(occupied):break
            column+=1
            if column>=columns:row+=1;column=0
        occupied.update(cells);result.append((key,row,column,height,width));column+=width
        if column>=columns:row+=1;column=0
    return result
