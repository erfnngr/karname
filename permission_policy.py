"""Central registry for module visibility and operations.

Policies restrict, and do not replace, record ownership, company, room and role
checks. Unknown modules and operations fail closed. A global group manager is
exempt for registered capabilities and cannot be modified through scoped ACLs.
"""
from copy import deepcopy

def module(title,actions,employee=(),finance=(),lead=(),auditor=()):
    """The registry is also used to construct the manager's access editor."""
    return dict(title=title,actions=dict(actions),defaults={
        'employee':tuple(employee),'finance':tuple(finance),
        'team_lead':tuple(lead),'auditor':tuple(auditor)})

MODULE_REGISTRY={
 'home':module('صفحه اصلی',[('view','نمایش')],('view',),('view',),('view',),('view',)),
 'calendar':module('تقویم و یادآورها',[('view','نمایش'),('create','افزودن'),('edit','ویرایش'),('delete','حذف'),('export','خروجی')],('view','create','edit','delete','export'),('view','create','edit','delete','export'),('view','create','edit','delete','export'),('view','export')),
 'occasions':module('مناسبت‌ها',[('view','نمایش')],('view',),('view',),('view',),('view',)),
 'month':module('ماه جاری',[('view','نمایش')],('view',),('view',),('view',),('view',)),
 'calculation':module('محاسبه جرایم و حقوق',[('view','نمایش'),('calculate','محاسبه'),('export','خروجی')],('view','calculate','export'),('view','calculate','export'),('view','calculate','export'),('view','calculate','export')),
 'payroll':module('حقوق گروهی و فیش‌ها',[('view','نمایش'),('create','ثبت دوره'),('export','خروجی فیش')],(),('view','create','export'),(),('view','export')),
 'services':module('سامانه‌ها',[('view','نمایش'),('edit','شخصی‌سازی')],('view','edit'),('view','edit'),('view','edit'),('view','edit')),
 'news':module('خبرها',[('view','نمایش'),('refresh','دریافت خبر'),('propose','پیشنهاد تغییر موعد')],('view','refresh'),('view','refresh','propose'),('view','refresh'),('view','refresh')),
 'company':module('پرونده‌های شرکت',[('view','نمایش'),('create','افزودن'),('edit','ویرایش'),('delete','حذف / بازیابی'),('upload','بارگذاری سند'),('download','دریافت سند'),('export','خروجی شرکت')],('view','create','edit','upload','download'),('view','create','edit','delete','upload','download','export'),('view','create','edit','upload','download','export'),('view','download','export')),
 'workspace':module('کارها و پیگیری‌ها',[('view','نمایش'),('create','افزودن کار'),('edit','ویرایش / تغییر وضعیت'),('approve','تأیید'),('delete','حذف / بازیابی'),('export','خروجی')],('view','create','edit','delete'),('view','create','edit','approve','delete','export'),('view','create','edit','approve','export'),('view','export')),
 'desk':module('کارتابل شخصی',[('view','نمایش'),('create','ثبت یادداشت / درخواست'),('edit','ویرایش'),('delete','حذف / بازیابی'),('approve','بررسی درخواست')],('view','create','edit','delete'),('view','create','edit','delete'),('view','create','edit','delete'),('view','create','edit','delete')),
 'attendance':module('تردد و برنامه کاری',[('view','نمایش مجاز'),('create','ثبت تردد'),('edit','ویرایش تردد'),('import','ورود فایل'),('approve','تأیید تردد'),('manage_schedule','تنظیم برنامه کاری')],('view',),('view',),('view',),('view',)),
 'chat':module('گفتگوی شرکت',[('view','نمایش'),('send','ارسال پیام'),('attach','ارسال فایل'),('react','واکنش و رأی'),('delete','حذف پیام مجاز'),('direct','گفتگوی شخصی'),('pin','سنجاق'),('meeting','جلسه / نظرسنجی')],('view','send','attach','react','delete','direct','pin','meeting'),('view','send','attach','react','delete','direct','pin','meeting'),('view','send','attach','react','delete','direct','pin','meeting'),('view','send','attach','react','delete','direct','pin','meeting')),
 'assistant':module('کارنامه (دستیار محلی)',[('view','نمایش'),('use','گفتگو و ساخت پیشنهاد'),('configure','تنظیم اتصال مدل'),('context','خواندن کارها و تقویم مجاز')],('view','use','configure','context'),('view','use','configure','context'),('view','use','configure','context'),('view','use','configure','context')),
 'clients':module('مشتریان، کار مالیاتی و فاکتور',[('view','نمایش پرونده‌های مجاز'),('create','افزودن مشتری / کار مالیاتی'),('edit','ویرایش'),('invoice','ساخت / ویرایش فاکتور'),('export','خروجی اطلاعات و PDF'),('delete','بایگانی')],(),('view','create','edit','invoice','export','delete'),('view','create','edit','export'),('view','export')),
 'finance':module('امور مالی، بانک و چک',[('view','نمایش مالی'),('create','ثبت دریافت و پرداخت'),('edit','ویرایش بانک، چک و اسناد'),('export','خروجی مالی')],(),('view','create','edit','export'),('view','create','edit','export'),('view','export')),
 'tax':module('مرکز مالیات',[('view','نمایش'),('create','ثبت پرونده مالیاتی'),('edit','ویرایش پرونده'),('delete','حذف / بازیابی'),('export','خروجی')],(),('view','create','edit','delete','export'),(),('view','export')),
 'access':module('مدیریت کاربران و دسترسی‌ها',[('view','نمایش'),('manage','مدیریت حساب و مجوز')],(),(),(),()),
 'network':module('مرکز و شبکه شرکت',[('view','نمایش'),('manage','مدیریت میزبان')],(),(),(),()),
 'backup':module('پشتیبان و بازیابی',[('view','نمایش'),('personal','پشتیبان / بازیابی شخصی'),('full','پشتیبان / بازیابی کامل مرکز')],('view','personal'),('view','personal'),('view','personal'),('view','personal')),
 'settings':module('تنظیمات شخصی',[('view','نمایش'),('edit','ویرایش تنظیمات خود')],('view','edit'),('view','edit'),('view','edit'),('view','edit')),
}

def schema():
    return [dict(key=key,title=value['title'],actions=[dict(key=k,title=v) for k,v in value['actions'].items()],defaults=deepcopy(value['defaults'])) for key,value in MODULE_REGISTRY.items()]

def baseline_allowed(role,module_key,action):
    mod=MODULE_REGISTRY.get(module_key)
    if not mod or action not in mod['actions']:return False
    if role in ('group_admin','company_manager','system_admin'):return True
    return action in mod['defaults'].get(role,())

def membership(actor,company):
    return next((m for m in actor.get('memberships',[]) if m.get('company_id')==company),None)

def allowed(actor,company,module_key,action='view'):
    mod=MODULE_REGISTRY.get(module_key)
    if not mod or action not in mod['actions']:return False
    if actor.get('global_role')=='group_admin':return True
    member=membership(actor,company)
    if not member:
        if actor.get('global_role')=='system_admin':return baseline_allowed('system_admin',module_key,action)
        return False
    role=member.get('role','employee');overrides=member.get('permissions') or {}
    def effective(op):
        key='module.'+module_key+'.'+op
        value=overrides.get(key)
        return value if isinstance(value,bool) else baseline_allowed(role,module_key,op)
    return effective('view') and effective(action)

def any_allowed(actor,module_key,action='view'):
    if actor.get('global_role') in ('group_admin','system_admin'):return baseline_allowed(actor['global_role'],module_key,action)
    return any(allowed(actor,m.get('company_id'),module_key,action) for m in actor.get('memberships',[]))

def validate_overrides(overrides):
    if not isinstance(overrides,dict):raise ValueError('قالب دسترسی معتبر نیست.')
    for key,value in overrides.items():
        if not isinstance(key,str):raise ValueError('نام دسترسی معتبر نیست.')
        if not key.startswith('module.'):continue  # Preserve established area-level permissions.
        parts=key.split('.')
        if len(parts)!=3 or parts[1] not in MODULE_REGISTRY or parts[2] not in MODULE_REGISTRY[parts[1]]['actions'] or not isinstance(value,bool):raise ValueError('نوع یا مقدار دسترسی معتبر نیست: '+key)
    return deepcopy(overrides)

