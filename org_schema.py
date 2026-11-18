"""Shared schemas for the desktop and responsive company portal."""
ROLES={'group_admin':'مدیر گروه','company_manager':'مدیر شرکت','finance':'مسئول مالی','team_lead':'سرپرست واحد','employee':'کارمند','auditor':'ناظر / حسابرس','system_admin':'مدیر فنی'}
STATUSES={'draft':'شروع‌نشده','in_progress':'در حال انجام','review':'منتظر تأیید','submitted':'ارسال‌شده','completed':'تکمیل‌شده','rejected':'نیازمند اصلاح'}
F=lambda key,label,kind='text',required=False,choices=None:dict(key=key,label=label,type=kind,required=required,choices=choices or [])
SCHEMAS={
 'company_profile':dict(label='پرونده شرکت',area='finance',fields=[F('title','نام پرونده',required=True),F('tax_id','شناسه مالیاتی'),F('insurance_code','کد کارگاهی بیمه'),F('fiscal_year','سال مالی'),F('branch','شعبه'),F('contact','مسئول / تماس'),F('notes','توضیحات','multiline')]),
 'commitment':dict(label='تعهدات و پرداخت‌های پیش رو',area='finance',fields=[F('title','عنوان',required=True),F('due_date','موعد شمسی','date',True),F('amount','مبلغ ریال','number'),F('category','نوع','choice',False,['مالیات','بیمه','چک','قرارداد','مجوز','ضمانت‌نامه','بیمه‌نامه','سایر']),F('paid','پرداخت / انجام شد','bool'),F('source','منبع / شماره سند'),F('notes','توضیحات','multiline')]),
 'rate':dict(label='نسخه‌های نرخ جریمه',area='finance',fields=[F('title','نام نرخ',required=True),F('kind','نوع مالیات / بیمه'),F('effective_from','اعتبار از','date',True),F('effective_to','اعتبار تا','date'),F('fixed','درصد ثابت','number'),F('monthly','درصد ماهانه','number'),F('basis','مبنای مبلغ'),F('source','منبع رسمی'),F('notes','شرایط شمول','multiline')]),
 'calculation':dict(label='پرونده محاسبات',area='finance',fields=[F('title','عنوان محاسبه',required=True),F('amount','مبلغ مبنا به ریال','number',True),F('fixed','درصد ثابت','number'),F('monthly','درصد ماهانه','number'),F('months','ماه تأخیر','number'),F('rate_id','شناسه نسخه نرخ'),F('notes','توضیحات','multiline')]),
 'proposal':dict(label='پیشنهاد تغییر موعد از خبر',area='finance',fields=[F('title','عنوان خبر',required=True),F('source','پیوند منبع',required=True),F('published','تاریخ انتشار'),F('task_ids','شناسه کارهای مرتبط؛ با ویرگول'),F('old_date','موعد قبلی','date'),F('new_date','موعد پیشنهادی','date',True),F('reason','علت و شرایط شمول','multiline',True),F('status','وضعیت','choice',False,['pending','approved','rejected'])]),
 'employee':dict(label='پرونده کارکنان',area='hr',fields=[F('title','نام و نام خانوادگی',required=True),F('employee_code','کد پرسنلی',required=True),F('department','واحد'),F('user_id','شناسه حساب کاربری مرتبط'),F('contract_end','پایان قرارداد','date'),F('base_salary','حقوق ثابت ماهانه ریال','number'),F('hourly_rate','نرخ ساعتی ریال','number'),F('daily_minutes','کار موظف روزانه؛ دقیقه','number'),F('notes','یادداشت','multiline')]),
 'attendance':dict(label='تردد و کارکرد ماهانه',area='hr',fields=[F('title','عنوان',required=True),F('employee_code','کد پرسنلی',required=True),F('date','روز شمسی','date',True),F('check_in','ورود HH:MM'),F('check_out','خروج HH:MM'),F('minutes','دقایق کار','number'),F('status','وضعیت','choice',False,['imported','needs_review','approved','rejected']),F('notes','یادداشت','multiline')]),
 'leave':dict(label='مرخصی، مأموریت و اضافه‌کاری',area='hr',fields=[F('title','عنوان درخواست',required=True),F('employee_code','کد پرسنلی',required=True),F('category','نوع','choice',True,['مرخصی','مأموریت','اضافه‌کاری','اصلاح تردد']),F('start_date','از تاریخ','date',True),F('end_date','تا تاریخ','date',True),F('hours','ساعت','number'),F('status','وضعیت','choice',False,['pending','approved','rejected']),F('notes','توضیحات','multiline')]),
 'shift':dict(label='شیفت و جانشینی',area='hr',fields=[F('title','عنوان شیفت',required=True),F('employee_code','کد پرسنلی',required=True),F('date','روز شمسی','date',True),F('start','شروع HH:MM'),F('end','پایان HH:MM'),F('substitute','کد پرسنلی جانشین'),F('notes','توضیحات','multiline')]),
 'request':dict(label='درخواست‌های داخلی',area='work',fields=[F('title','عنوان',required=True),F('category','نوع','choice',True,['درخواست مدرک','خرید','پرداخت','تنخواه','سایر']),F('amount','مبلغ ریال','number'),F('due_date','موعد','date'),F('reviewer_id','شناسه تأییدکننده'),F('status','وضعیت','choice',False,['pending','approved','rejected']),F('notes','شرح درخواست','multiline')]),
 'form':dict(label='فرم‌های قابل تنظیم',area='work',fields=[F('title','نام فرم',required=True),F('fields','نام فیلدها؛ هر خط یک فیلد','multiline',True),F('reviewer_id','شناسه تأییدکننده'),F('instructions','راهنمای تکمیل','multiline')]),
 'form_response':dict(label='پاسخ فرم‌ها',area='work',fields=[F('title','عنوان پاسخ',required=True),F('form_id','شناسه فرم',required=True),F('answers','پاسخ فیلدها','multiline',True),F('status','وضعیت','choice',False,['pending','approved','rejected'])]),
 'knowledge':dict(label='دانش و دستورالعمل شرکت',area='work',fields=[F('title','عنوان',required=True),F('tags','برچسب‌ها'),F('content','متن راهنما','multiline',True),F('source','منبع'),F('review_date','بازبینی بعدی','date')]),
 'automation':dict(label='قوانین پیگیری خودکار',area='work',fields=[F('title','نام قانون',required=True),F('trigger','رویداد','choice',True,['overdue','review','attachment']),F('delay_days','پس از چند روز','number'),F('target_user','شناسه دریافت‌کننده'),F('message','متن اعلان','multiline',True),F('enabled','فعال','bool')]),
 'template':dict(label='الگوهای کار',area='work',fields=[F('title','نام الگو',required=True),F('checklist','چک‌لیست؛ هر خط یک مورد','multiline'),F('notes','راهنما','multiline'),F('category','بخش','choice',False,['مالیات','بیمه','سایر']),F('require_evidence','مدرک الزامی','bool'),F('require_approval','تأیید مدیر الزامی','bool')]),
}
MANAGERS={'group_admin','company_manager'}
APPROVERS=MANAGERS|{'finance','team_lead'}

SCHEMAS.update({
 'client':dict(label='مشتریان و طرف قرارداد',area='work',fields=[F('title','نام مشتری / طرف قرارداد',required=True),F('contact','شخص رابط'),F('phone','تلفن'),F('email','ایمیل'),F('address','نشانی'),F('assignee_id','شناسه مسئول پیگیری'),F('notes','توضیحات','multiline')]),
 'tax_case':dict(label='پرونده تکلیف مالیاتی',area='finance',fields=[F('title','عنوان تکلیف',required=True),F('tax_type','نوع مالیات','choice',True,['ارزش افزوده','عملکرد','حقوق','اجاره','سامانه مؤدیان','دفاتر','سایر']),F('period','دوره / سال مالی',required=True),F('due_date','موعد شمسی تأییدشده','date'),F('status','وضعیت','choice',True,['draft','in_progress','review','submitted','completed']),F('responsible','مسئول پیگیری'),F('submitted_date','تاریخ ارسال شمسی','date'),F('payment_date','تاریخ پرداخت شمسی','date'),F('declared_amount','مبلغ اظهارشده ریال','number'),F('paid_amount','مبلغ پرداخت‌شده ریال','number'),F('reference','شماره پیگیری یا قبض'),F('source','منبع موعد / نرخ'),F('notes','شرح و مدارک موردنیاز','multiline')]),
 'contract':dict(label='قرارداد و تمدید',area='work',fields=[F('title','عنوان قرارداد',required=True),F('client_id','شناسه پرونده مشتری'),F('number','شماره قرارداد'),F('start_date','شروع','date'),F('due_date','تاریخ تمدید / پایان','date',True),F('amount','مبلغ ریال','number'),F('assignee_id','شناسه مسئول'),F('notes','شرایط و توضیحات','multiline')]),
 'installment':dict(label='اقساط قرارداد',area='finance',fields=[F('title','عنوان قسط',required=True),F('contract_id','شناسه قرارداد',required=True),F('due_date','موعد','date',True),F('amount','مبلغ ریال','number',True),F('paid','پرداخت شده','bool'),F('assignee_id','شناسه مسئول'),F('notes','شماره رسید / توضیحات','multiline')]),
 'payroll_batch':dict(label='دوره حقوق گروهی',area='finance',fields=[F('title','عنوان دوره',required=True),F('period','ماه شمسی',required=True),F('notes','یادداشت تأیید','multiline')])
})
from customer_data import GROUPS,TYPES
SCHEMAS['client']['fields']=[F(k,label,'choice' if kind in ('type','status') else 'multiline' if kind=='multiline' else 'text',k=='title',TYPES if kind=='type' else ['active','archived'] if kind=='status' else None) for _,fields in GROUPS for k,label,kind in fields]
SCHEMAS.update({
 'invoice':dict(label='فاکتورها',area='work',fields=[F('title','عنوان',required=True),F('client_id','مشتری',required=True),F('number','شماره داخلی',required=True),F('date','تاریخ شمسی','date',True),F('due_date','سررسید پرداخت','date'),F('notes','توضیحات','multiline')]),
 'tax_job':dict(label='کار مالیاتی مشتری',area='work',fields=[F('title','عنوان کار',required=True),F('client_id','مشتری',required=True),F('tax_kind','نوع کار مالیاتی'),F('period','دوره / سال مالی'),F('due_date','موعد شمسی','date',True),F('status','وضعیت','choice',False,list(STATUSES)),F('assignee_id','مسئول پیگیری'),F('notes','توضیحات','multiline')])
})
next(f for f in SCHEMAS['tax_case']['fields'] if f['key']=='tax_type')['choices'].append('بیمه کارکنان')
SCHEMAS['tax_case']['fields'].extend([F('insurance_workshop','کد کارگاهی بیمه'),F('insured_names','اسامی بیمه‌شدگان ماه؛ هر خط یک نفر','multiline')])
SCHEMAS['insurance_workshop']=dict(label='کارگاه بیمه',area='finance',fields=[
 F('title','نام کارگاه',required=True),F('workshop_code','کد کارگاه',required=True),
 F('employer_name','نام کارفرما'),F('national_id','شناسه ملی شرکت'),
 F('branch','شعبه تأمین اجتماعی'),F('address','نشانی','multiline'),F('contact','اطلاعات تماس'),
 F('contract_row','ردیف پیمان'),F('workshop_type','نوع کارگاه'),F('access_users','افراد مجاز کارگاه','user_scope'),
 F('labor_law','وضعیت شمول قانون کار','choice',False,['نامشخص','مشمول','غیرمشمول']),
 F('unemployment','وضعیت بیمه بیکاری','choice',False,['نامشخص','مشمول','غیرمشمول']),
 F('wage_type','نوع دستمزد','choice',False,['نامشخص','عادی','مقطوع','طبقه‌بندی مشاغل']),
 F('hard_work','وضعیت مشاغل سخت و زیان‌آور','choice',False,['نامشخص','احراز نشده','احراز شده']),
 F('exemptions','مجوزها و معافیت‌های قابل بررسی','multiline'),F('notes','توضیحات','multiline')])
SCHEMAS['insurance_employee']=dict(label='اطلاعات بیمه‌ای کارمند',area='finance',fields=[
 F('title','عنوان پرونده',required=True),F('employee_id','کارمند مرتبط',required=True),F('workshop_id','کارگاه مرتبط',required=True),
 F('first_name','نام'),F('last_name','نام خانوادگی'),
 F('national_id','کد ملی'),F('insurance_number','شماره بیمه'),F('birth_certificate','شماره شناسنامه'),
 F('father_name','نام پدر'),F('birth_date','تاریخ تولد شمسی','date'),F('issue_place','محل صدور'),F('issue_date','تاریخ صدور شناسنامه','date'),
 F('gender','جنسیت','choice',False,['نامشخص','زن','مرد']),F('nationality','تابعیت'),
 F('job_title','عنوان شغلی'),F('job_code','کد شغلی'),F('start_date','شروع همکاری','date'),F('end_date','پایان همکاری','date'),
 F('employment_type','نوع همکاری'),F('insurance_status','وضعیت بیمه'),F('seniority_basis','سابقه قابل بررسی سنوات'),
 F('marital_status','وضعیت تأهل','choice',False,['نامشخص','مجرد','متأهل']),F('marital_changed','تاریخ تغییر تأهل','date'),
 F('exemptions','معافیت‌ها و مدارک','multiline'),F('notes','توضیحات','multiline')])
SCHEMAS['insurance_list']=dict(label='پیش‌نویس لیست بیمه ماهانه',area='finance',fields=[
 F('title','عنوان',required=True),F('workshop_id','کارگاه',required=True),F('period','ماه شمسی',required=True),
 F('list_no','شماره لیست',required=True),F('list_type','نوع لیست'),F('notes','توضیحات','multiline')])
SCHEMAS['insurance_rules']=dict(label='نسخه قواعد بیمه',area='finance',fields=[
 F('title','عنوان',required=True),F('rules_version','شناسه نسخه',required=True),F('source','منبع و شماره بخشنامه',required=True),
 F('effective_from','اعتبار از','date',True),F('effective_to','اعتبار تا','date',True),
 F('worker_rate','درصد کارمند',required=True),F('employer_rate','درصد کارفرما',required=True),F('unemployment_rate','درصد بیکاری',required=True),
 F('minimum_daily','حداقل روزانه ریال',required=True),F('maximum_daily','حداکثر روزانه ریال',required=True),F('approved','تأیید اعتبار قواعد','bool')])
SCHEMAS['insurance_evidence']=dict(label='پیگیری دستی بیمه',area='finance',fields=[
 F('title','عنوان',required=True),F('insurance_list_id','لیست مربوط',required=True),F('kind','نوع پیگیری','choice',True,['ارسال دستی','پرداخت دستی']),
 F('date','تاریخ','date',True),F('reference','شماره پیگیری یا رسید',required=True),F('amount','مبلغ پرداخت ریال'),F('notes','توضیحات','multiline')])
SCHEMAS['insurance_calculation']=dict(label='محاسبه آزمایشی ثبت‌شده بیمه',area='finance',fields=[
 F('title','عنوان',required=True),F('insurance_list_id','لیست بیمه',required=True),F('rules_id','نسخه قواعد',required=True)])
SCHEMAS['insurance_review']=dict(label='بررسی داخلی محاسبه بیمه',area='finance',fields=[
 F('title','عنوان',required=True),F('calculation_id','محاسبه',required=True),F('notes','توضیح بررسی هشدارها','multiline')])
SCHEMAS['payroll_confirmation']=dict(label='تأیید داخلی دوره حقوق',area='finance',fields=[
 F('title','عنوان',required=True),F('payroll_batch_id','دوره حقوق',required=True),F('reference','مرجع یا شماره تأیید حقوق',required=True),F('notes','توضیحات','multiline')])
