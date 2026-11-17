"""Short, editable starting points for application work; never auto-send."""
TEMPLATES=[
 dict(key='today',title='کارهای امروز',primary=True,text='کارهای امروز و کارهای عقب‌افتاده‌ام را نشان بده و سه اولویت پیشنهاد کن.',needs=[]),
 dict(key='missing_information',title='بررسی موارد نیازمند پیگیری',text='پرونده‌های مجاز من را برای اطلاعات ثبت‌نشده بررسی کن و موارد نیازمند پیگیری را نشان بده؛ نتیجه را قطعی فرض نکن.',needs=[]),
 dict(key='tax',title='موعدهای مالیات و بیمه',primary=True,text='تکالیف مالیاتی و بیمه‌ای این ماه را بر اساس موعد مرتب کن. موعدهای نیازمند بررسی را جدا نشان بده.',needs=[('calendar','view')]),
 dict(key='tax_center_review',title='بررسی تکالیف مالیاتی',text='پرونده‌های مالیاتی شرکت [نام شرکت] را بر اساس موعد و وضعیت بررسی کن و موارد نیازمند اقدام و تأیید را جدا کن.',needs=[('tax','view')]),
 dict(key='tax_center_open',title='باز کردن مرکز مالیات',text='بخش مالیات را باز کن تا تکالیف و مقایسه فاکتورها را بررسی کنم.',needs=[('tax','view')]),
 dict(key='tax_case_create',title='ثبت تکلیف مالیاتی',text='برای شرکت [نام شرکت] تکلیف مالیاتی با عنوان [عنوان دقیق]، نوع [نوع مالیات]، دوره [دوره دقیق] و موعد [تاریخ شمسی] ثبت کن.',needs=[('tax','create')]),
 dict(key='tax_compare',title='مقایسه مالیات فاکتورها',text='فاکتورهای مالیاتی شرکت [نام شرکت] را از [تاریخ شروع شمسی] تا [تاریخ پایان شمسی] بررسی و مقایسه کن.',needs=[('tax','view'),('clients','view')]),
 dict(key='schedule',title='تنظیم یادآوری',primary=True,text='برای یادآور «[عنوان کار]» اعلان را ۵ روز، ۱ روز قبل و روز موعد تنظیم کن. تاریخ اصلی تغییر نکند.',needs=[('calendar','edit')]),
 dict(key='create_reminder',title='یادآور جدید',text='یک یادآور شخصی با عنوان «[عنوان کار]» برای تاریخ شمسی [تاریخ موعد] بساز؛ ۳ روز، ۱ روز قبل و روز موعد یادآوری شود.',needs=[('calendar','create')]),
 dict(key='work_alert',title='اعلان شخصی کار شرکت',text='برای کار شرکت «[عنوان کار]» اعلان شخصی ۳ روز و ۱ روز قبل و روز موعد تنظیم کن؛ موعد شرکت و تنظیمات همکاران تغییر نکند.',needs=[('calendar','edit'),('workspace','view')]),
 dict(key='fade',title='مدت نمایش اعلان',text='مدت نمایش اعلان‌های من را ۵ ثانیه تنظیم کن؛ بقیه تنظیمات تغییر نکنند.',needs=[('settings','edit')]),
 dict(key='create_task',title='ساخت کار شرکت',text='برای شرکت «[نام شرکت]» یک کار با عنوان «[عنوان کار]» و موعد شمسی [تاریخ موعد] در حالت پیش‌نویس بساز.',needs=[('workspace','create')]),
 dict(key='assign_task',title='واگذاری کار',text='برای شرکت «[نام شرکت]» کار «[عنوان کار]» با موعد شمسی [تاریخ موعد] را به «[نام همکار]» واگذار کن.',needs=[('workspace','create')],manager=True),
 dict(key='review',title='آماده بررسی مدیر',text='وضعیت کار «[عنوان کار]» را آماده بررسی مدیر قرار بده؛ تأیید نهایی توسط مسئول مجاز انجام شود.',needs=[('workspace','edit')]),
 dict(key='weekly',title='برنامه این هفته',text='بر اساس کارها و موعدهای مجاز من، یک برنامه پیشنهادی برای این هفته بده. پنجشنبه و جمعه را در حالت عادی غیرکاری در نظر بگیر.',needs=[]),
 dict(key='attendance_self',title='کارکرد ماهانه من',text='تردد و کارکرد من در شرکت «[نام شرکت]» در ماه [سال/ماه شمسی] را بررسی کن و اضافه‌کاری تأییدشده و روزهای نیازمند بررسی را جدا نشان بده.',needs=[('attendance','view')]),
 dict(key='attendance_team',title='کارکرد کارکنان',text='کارکرد همه کارکنان شرکت «[نام شرکت]» در ماه [سال/ماه شمسی] را مقایسه کن؛ غیبت قطعی را از نبود ثبت تردد تفکیک کن.',needs=[('attendance','view')]),
 dict(key='attendance_import',title='ورود تردد از فایل',text='فایل تردد [مسیر کامل فایل] را برای شرکت «[نام شرکت]» و ماه [سال/ماه شمسی] وارد کن.',needs=[('attendance','import')]),
 dict(key='attendance_review',title='بررسی تردد همکار',text='تردد «[نام کامل همکار]» در شرکت «[نام شرکت]» تاریخ [تاریخ شمسی] را [تایید یا رد] کن.',needs=[('attendance','edit'),('attendance','approve')]),
 dict(key='attendance_update',title='ویرایش ساعت تردد',text='تردد «[نام کامل همکار]» در شرکت «[نام شرکت]» تاریخ [تاریخ شمسی] را اصلاح کن؛ ورود را به [ساعت ورود] و خروج را به [ساعت خروج] و دقایق کار را به [دقیقه کار] تغییر بده.',needs=[('attendance','edit')]),
 dict(key='permission_set',title='تنظیم دسترسی همکار',text='در شرکت «[نام شرکت]» دسترسی «[عنوان عملیات]» از بخش «[عنوان کامل بخش]» را برای «[نام کامل همکار]» [فعال کن یا غیرفعال کن].',needs=[('access','view'),('access','manage')]),
 dict(key='notice_publish',title='اطلاعیه به اعضای شرکت',text='برای همه اعضای شرکت «[نام شرکت]» اطلاعیه با عنوان «[عنوان اطلاعیه]» و متن «[متن اطلاعیه]» منتشر کن.',needs=[('company','create')]),
 dict(key='backup_create',title='ساخت پشتیبان',text='از اطلاعات مجاز من یک نسخه پشتیبان تهیه کن.',needs=[('backup','personal')]),
 dict(key='reminder_delete',title='حذف یادآور',text='یادآور «[عنوان دقیق یادآور]» را حذف کن.',needs=[('calendar','delete')]),
 dict(key='reminder_restore',title='بازیابی یادآور',text='یادآور «[عنوان دقیق یادآور]» را از سطل بازیافت بازیابی کن.',needs=[('calendar','delete')]),
 dict(key='message',title='پیشنهاد پیام',text='برای گروه «[نام گروه]» در شرکت «[نام شرکت]» این پیام را برای بازبینی آماده کن: [متن پیام]',needs=[('chat','send')]),
 dict(key='calendar',title='بازکردن تقویم',text='بخش تقویم را باز کن.',needs=[('calendar','view')]),
 dict(key='invoice_open',title='بازکردن فاکتورها',text='بخش فاکتورها را باز کن.',needs=[('clients','view')]),
 dict(key='finance_draft',title='پیش‌نویس دریافت یا پرداخت',text='برای شرکت [نام شرکت] فرم پیش‌نویس [دریافت یا پرداخت] به مبلغ [مبلغ دقیق ریال] در تاریخ [تاریخ شمسی] بابت [علت] آماده کن. ثبت نهایی را به من بسپار.',needs=[('clients','view'),('finance','create')]),
 dict(key='invoice_explain',title='راهنمای ثبت فاکتور',mode='chat',text='برای ثبت فاکتور فروش در کارنامه، مراحل انتخاب شرکت، مشتری، کالا، مالیات، تأیید مالی و پیش‌نمایش را توضیح بده. اگر از عملکرد بخشی مطمئن نیستی، آن را صریح بگو.',needs=[]),
 dict(key='invoice_calc',title='محاسبه مبلغ فاکتور',mode='chat',text='با اطلاعات زیر جمع قبل از تخفیف، تخفیف، مالیات و مبلغ نهایی فاکتور را مرحله‌به‌مرحله حساب کن. نرخ مالیات را حدس نزن: [متن تعداد، قیمت، تخفیف و نرخ مالیات هر ردیف]',needs=[]),
 dict(key='profit_calc',title='برآورد سود کالا',mode='chat',text='با اطلاعات زیر سود ناخالص تقریبی را بدون مالیات و هزینه‌های دیگر محاسبه کن و فرض‌ها را مشخص کن: [متن قیمت خرید، قیمت فروش، تعداد و تخفیف]',needs=[]),
 dict(key='payment_split',title='بررسی تسویه فاکتور',mode='chat',text='با اطلاعات زیر سهم پرداخت نقدی، بانکی و چک، و مانده تسویه‌نشده را حساب کن. چک وصول‌نشده را از وجه وصول‌شده جدا نشان بده: [متن مبلغ فاکتور و مبالغ تسویه]',needs=[]),
 dict(key='check_planning',title='برنامه‌ریزی سررسید چک',mode='chat',text='با اطلاعاتی که می‌دهم، سررسید چک‌ها را مرتب کن و یک برنامه پیگیری پیشنهاد بده؛ هیچ چکی را وصول‌شده فرض نکن: [متن مبلغ، وضعیت و تاریخ هر چک]',needs=[]),
 dict(key='financial_reconcile',title='بررسی اختلاف مالی',mode='chat',text='اختلاف اعداد مالی زیر را بررسی کن و موارد لازم برای تطبیق اسناد را به من بگو؛ چیزی در برنامه تغییر نده: [متن اطلاعات فاکتور، دریافت و پرداخت]',needs=[]),
 dict(key='personal_note',title='یادداشت شخصی در تقویم',text='یادداشت شخصی با عنوان «[عنوان یادداشت]» و متن «[متن یادداشت]» برای تاریخ [تاریخ شمسی] ثبت کن و در تقویم نمایش بده.',needs=[('desk','create')]),
 dict(key='personal_note_update',title='ویرایش یادداشت شخصی',text='متن یادداشت «[عنوان یادداشت]» را به «[متن جدید]» تغییر بده.',needs=[('desk','edit')]),
 dict(key='personal_note_rename',title='تغییر عنوان یادداشت',text='عنوان یادداشت «[عنوان فعلی]» را به «[عنوان جدید]» تغییر بده.',needs=[('desk','edit')]),
 dict(key='personal_note_delete',title='حذف یادداشت شخصی',text='یادداشت «[عنوان یادداشت]» را حذف کن.',needs=[('desk','delete')]),
 dict(key='personal_note_restore',title='بازیابی یادداشت شخصی',text='یادداشت «[عنوان یادداشت]» را از سطل بازیافت بازیابی کن.',needs=[('desk','delete')]),
 dict(key='personal_note_purge',title='حذف دائمی یادداشت',text='یادداشت «[عنوان یادداشت]» را از سطل بازیافت دائمی حذف کن.',needs=[('desk','delete')]),
 dict(key='personal_note_alert',title='زمان اعلان یادداشت',text='برای یادداشت «[عنوان یادداشت]» اعلان را ۳ روز قبل و روز موعد تنظیم کن.',needs=[('desk','edit')]),
 dict(key='customer_create',title='ثبت مشتری',text='برای شرکت «[نام شرکت]» مشتری [حقیقی یا حقوقی] با نام «[نام مشتری]» و شناسه ملی [شماره ملی] و تلفن [شماره تلفن] ثبت کن.',needs=[('clients','create')]),
 dict(key='customer_update_phone',title='تغییر تلفن مشتری',text='در شرکت «[نام شرکت]» تلفن مشتری «[نام مشتری]» را به [شماره تلفن] تغییر بده.',needs=[('clients','edit')]),
 dict(key='customer_update_name',title='تغییر نام نمایشی مشتری',text='در شرکت «[نام شرکت]» نام نمایشی مشتری «[نام فعلی مشتری]» را به «[نام جدید]» تغییر بده.',needs=[('clients','edit')]),
 dict(key='leave_request',title='درخواست مرخصی',text='درخواست مرخصی استحقاقی برای شرکت «[نام شرکت]» از تاریخ [تاریخ شروع] تا تاریخ [تاریخ پایان] ثبت کن.',needs=[('desk','create')]),
 dict(key='leave_cancel',title='لغو مرخصی من',text='درخواست مرخصی خودم در شرکت «[نام شرکت]» از تاریخ [تاریخ شروع] را لغو کن.',needs=[('desk','edit')]),
 dict(key='leave_review',title='بررسی مرخصی همکار',text='درخواست مرخصی «[نام همکار]» در شرکت «[نام شرکت]» از تاریخ [تاریخ شروع] را [تایید یا رد] کن.',needs=[('desk','approve')]),
 dict(key='message_send',title='ارسال پیام',text='در گروه «[نام گروه]» شرکت «[نام شرکت]» پیام «[متن پیام]» را ارسال کن.',needs=[('chat','send')]),
 dict(key='message_schedule',title='ارسال زمان‌بندی‌شده پیام',text='در گروه «[نام گروه]» شرکت «[نام شرکت]» پیام «[متن پیام]» را در تاریخ [تاریخ شمسی] ساعت [ساعت به شکل 09:30] ارسال کن.',needs=[('chat','send')]),
 dict(key='file_schedule',title='ارسال زمان‌بندی‌شده فایل',text='در گروه «[نام گروه]» شرکت «[نام شرکت]» فایل [مسیر کامل فایل] را در تاریخ [تاریخ شمسی] ساعت [ساعت به شکل 09:30] ارسال کن.',needs=[('chat','send'),('chat','attach')]),
 dict(key='message_schedule_cancel',title='لغو پیام زمان‌بندی‌شده',text='پیام زمان‌بندی‌شده «[متن پیام]» در گروه «[نام گروه]» شرکت «[نام شرکت]» برای تاریخ [تاریخ شمسی] ساعت [ساعت به شکل 09:30] را لغو کن.',needs=[('chat','view')]),
 dict(key='message_schedule_change',title='تغییر زمان پیام',text='زمان پیام «[متن پیام]» در گروه «[نام گروه]» شرکت «[نام شرکت]» را از تاریخ [تاریخ قبلی] ساعت [ساعت قبلی] به تاریخ [تاریخ جدید] ساعت [ساعت جدید] تغییر بده.',needs=[('chat','send')]),
 dict(key='chat_poll',title='ساخت نظرسنجی',text='در شرکت «[نام شرکت]» گروه «[نام گروه]» نظرسنجی «[موضوع]» با گزینه «[گزینه اول]» و «[گزینه دوم]» ایجاد کن.',needs=[('chat','send'),('chat','meeting')]),
 dict(key='chat_group',title='ساخت گروه چت',text='برای شرکت «[نام شرکت]» گروه «[نام گروه]» با اعضای «[نام همکار اول]» و «[نام همکار دوم]» ایجاد کن.',needs=[('chat','send')]),
 dict(key='chat_file',title='ارسال فایل در چت',text='در شرکت «[نام شرکت]» گروه «[نام گروه]» فایل [مسیر کامل فایل] را ارسال کن.',needs=[('chat','send'),('chat','attach')]),
 dict(key='chat_mute',title='تنظیم اعلان گروه',text='گروه «[نام گروه]» شرکت «[نام شرکت]» را برای من بی‌صدا کن.',needs=[('chat','view')]),
 dict(key='chat_unmute',title='فعال‌کردن اعلان گروه',text='گروه «[نام گروه]» شرکت «[نام شرکت]» را برای من با صدا تنظیم کن.',needs=[('chat','view')]),
 dict(key='chat_like',title='پسندیدن پیام',text='پیام «[متن کامل پیام]» را در گروه «[نام گروه]» شرکت «[نام شرکت]» لایک کن.',needs=[('chat','react')]),
 dict(key='chat_unlike',title='برداشتن پسند پیام',text='لایک را از پیام «[متن کامل پیام]» در گروه «[نام گروه]» شرکت «[نام شرکت]» بردار.',needs=[('chat','react')]),
 dict(key='chat_vote',title='رأی در نظرسنجی',text='در گروه «[نام گروه]» شرکت «[نام شرکت]» در نظرسنجی «[موضوع کامل]» به گزینه «[متن گزینه]» رأی بده.',needs=[('chat','react')]),
 dict(key='chat_delete',title='حذف پیام برای همه',text='پیام «[متن کامل پیام]» در گروه «[نام گروه]» شرکت «[نام شرکت]» را برای همه حذف کن.',needs=[('chat','delete')]),
 dict(key='chat_restore',title='بازیابی پیام',text='پیام «[متن کامل پیام]» در گروه «[نام گروه]» شرکت «[نام شرکت]» را از سطل بازیافت بازیابی کن.',needs=[('chat','delete')]),
 dict(key='chat_meeting',title='اعلان جلسه در چت',text='در شرکت «[نام شرکت]» گروه «[نام گروه]» جلسه «[موضوع]» در تاریخ [تاریخ شمسی] ساعت [ساعت به شکل 09:30] مکان «[مکان]» ایجاد کن.',needs=[('chat','send'),('chat','meeting')]),
 dict(key='product_create',title='ثبت کالا',text='در شرکت «[نام شرکت]» کالای «[نام کالا]» را در گروه اصلی «[نام گروه اصلی]» و گروه فرعی «[نام گروه فرعی]» با واحد [واحد]، قیمت خرید [مبلغ خرید] ریال و قیمت فروش [مبلغ فروش] ریال ثبت کن.',needs=[('clients','create')]),
 dict(key='group_main',title='گروه اصلی کالا',text='در شرکت «[نام شرکت]» گروه اصلی کالا با نام «[نام گروه]» بساز.',needs=[('clients','create')]),
 dict(key='group_sub',title='گروه فرعی کالا',text='در شرکت «[نام شرکت]» گروه فرعی «[نام گروه فرعی]» را زیر گروه اصلی «[نام گروه اصلی]» بساز.',needs=[('clients','create')]),
 dict(key='product_adjust',title='اصلاح موجودی کالا',text='در شرکت «[نام شرکت]» موجودی نهایی را به [مقدار نهایی] برای کالای «[نام کالا]» به دلیل «[علت اصلاح]» تغییر بده.',needs=[('clients','edit')]),
 dict(key='product_price_edit',title='تغییر قیمت کالا',text='در شرکت «[نام شرکت]» قیمت فروش را به [مبلغ ریال] ریال برای کالا «[نام کالا]» تغییر بده.',needs=[('clients','edit')]),
 dict(key='credit_invoice',title='فاکتور فروش نسیه',text='برای شرکت «[نام شرکت]» فاکتور فروش نسیه به مشتری «[نام مشتری]» برای [تعداد] عدد «[نام کالا]» با مالیات [درصد مالیات] درصد به تاریخ [تاریخ شمسی] ثبت کن.',needs=[('clients','invoice')]),
 dict(key='credit_invoice_discount',title='فاکتور فروش با تخفیف',text='برای شرکت «[نام شرکت]» فاکتور فروش نسیه به مشتری «[نام مشتری]» برای [تعداد] عدد «[نام کالا]» با مالیات [درصد مالیات] درصد و تخفیف کل [مبلغ تخفیف] ریال به تاریخ [تاریخ شمسی] ثبت کن.',needs=[('clients','invoice')]),
 dict(key='purchase_invoice',title='فاکتور خرید نسیه',text='فاکتور خرید نسیه شرکت «[نام شرکت]» مشتری «[نام مشتری]» برای [تعداد] عدد «[نام کالا]» تاریخ [تاریخ شمسی] با مالیات [درصد مالیات] درصد ثبت کن.',needs=[('clients','invoice')]),
 dict(key='preinvoice',title='پیش‌فاکتور',text='پیش فاکتور شرکت «[نام شرکت]» مشتری «[نام مشتری]» برای [تعداد] عدد «[نام کالا]» تاریخ [تاریخ شمسی] با مالیات [درصد مالیات] درصد ثبت کن.',needs=[('clients','invoice')]),
 dict(key='return_invoice',title='فاکتور برگشت',text='فاکتور برگشت از [خرید یا فروش] نسیه شرکت «[نام شرکت]» مشتری «[نام مشتری]» برای [تعداد] عدد «[نام کالا]» تاریخ [تاریخ شمسی] با مالیات [درصد مالیات] درصد ثبت کن.',needs=[('clients','invoice')]),
 dict(key='settle_invoice_cash',title='تسویه نقدی فاکتور',text='در شرکت «[نام شرکت]» [دریافت یا پرداخت] نقد فاکتور [فروش یا خرید] شماره [شماره فاکتور] مشتری «[نام مشتری]» به مبلغ [مبلغ ریال] ریال در تاریخ [تاریخ شمسی] بابت «[علت]» ثبت کن.',needs=[('finance','create')]),
 dict(key='settle_invoice_bank',title='تسویه بانکی فاکتور',text='در شرکت «[نام شرکت]» [دریافت یا پرداخت] [روش انتقال] حساب «[نام حساب]» فاکتور [فروش یا خرید] شماره [شماره فاکتور] مشتری «[نام مشتری]» به مبلغ [مبلغ ریال] ریال در تاریخ [تاریخ شمسی] بابت «[علت]» ثبت کن.',needs=[('finance','create')]),
 dict(key='cash_transaction',title='دریافت یا پرداخت نقدی',text='برای شرکت «[نام شرکت]» یک [دریافت یا پرداخت] نقدی مستقل به مبلغ [مبلغ ریال] ریال بابت «[علت]» به تاریخ [تاریخ شمسی] ثبت کن.',needs=[('finance','create')]),
 dict(key='bank_transaction',title='دریافت یا پرداخت بانکی',text='برای شرکت «[نام شرکت]» یک [دریافت یا پرداخت] از طریق [روش انتقال] از حساب «[نام حساب]» به مبلغ [مبلغ ریال] ریال بابت «[علت]» به تاریخ [تاریخ شمسی] ثبت کن.',needs=[('finance','create')]),
 dict(key='check_create',title='ثبت چک مستقل',text='در شرکت «[نام شرکت]» چک [دریافتی یا پرداختی] شماره چک [شماره چک] بانک «[نام بانک]» به مبلغ [مبلغ ریال] ریال با سررسید [تاریخ شمسی] ثبت کن.',needs=[('finance','edit')]),
 dict(key='check_status',title='ثبت وضعیت چک',text='در شرکت «[نام شرکت]» وضعیت چک شماره [شماره چک] بانک «[نام بانک]» را به [وضعیت مورد نظر] تغییر بده.',needs=[('finance','edit')]),
 dict(key='bank_create',title='ثبت حساب بانکی',text='در شرکت «[نام شرکت]» حساب بانکی «[نام بانک]» با شماره حساب [شماره حساب] و شماره شبا [شماره شبا] ثبت کن.',needs=[('finance','edit')]),
 dict(key='report_transactions',title='گزارش دریافت و پرداخت',text='گزارش دریافت و پرداخت شرکت «[نام شرکت]» از [تاریخ شروع] تا [تاریخ پایان] را به صورت اکسل بساز.',needs=[('clients','export'),('finance','export')]),
 dict(key='report_invoice',title='گزارش فاکتورها',text='گزارش فاکتور شرکت «[نام شرکت]» از [تاریخ شروع] تا [تاریخ پایان] را به صورت PDF بساز.',needs=[('clients','export')]),
 dict(key='open_desk',title='بازکردن کارتابل',text='کارتابل من را باز کن.',needs=[('desk','view')]),
 dict(key='open_chat',title='بازکردن گفتگوها',text='بخش چت را باز کن.',needs=[('chat','view')]),
 dict(key='open_services',title='بازکردن سامانه‌ها',text='بخش سامانه‌ها را باز کن.',needs=[('services','view')]),
 dict(key='open_customers',title='بازکردن مشتریان',text='بخش مشتریان را باز کن.',needs=[('clients','view')]),
 dict(key='open_products',title='بازکردن کالاها',text='بخش کالا و موجودی را باز کن.',needs=[('clients','view')]),
 dict(key='open_finance',title='بازکردن امور مالی',text='بخش امور مالی را باز کن.',needs=[('finance','view')]),
 dict(key='open_notes',title='بازکردن یادداشت‌ها',text='بخش یادداشت‌های من را باز کن.',needs=[('desk','view')]),
 dict(key='open_leave',title='بازکردن مرخصی‌ها',text='بخش درخواست‌های من را باز کن.',needs=[('desk','view')]),
]

def manager_capable(owner):
    from permission_policy import any_allowed
    actor=owner.session_user
    if not actor:return False
    return (actor.get('global_role') in ('group_admin','system_admin') or any(m.get('role') in ('company_manager','finance','team_lead') for m in actor.get('memberships',[]))) and any_allowed(actor,'workspace','create')

def available(owner,template):
    from ui_permissions import allowed
    return all(allowed(owner,m,a) for m,a in template['needs']) and (not template.get('manager') or manager_capable(owner))

def suggest(query,owner,limit=3):
    """Rank a few permitted examples from typed terms and common Persian synonyms."""
    import re
    from storage import normalize
    q=normalize(query).casefold().replace('ي','ی').replace('ك','ک')
    words=[w for w in re.findall(r'[\w]{2,}',q) if w not in ('برای','برام','میشه','میخوام','میخواهم','لطفا','کردن','کارنامه','خودم')]
    if not words:return []
    synonyms=(('فاکتور','صورتحساب','پیش فاکتور'),('مرخصی','تعطیلات','استراحت'),('چک','چکها','چک های'),('یادآوری','یاداور','یادآور','ریمایندر','اعلان'),('کالا','محصول','جنس'),('مشتری','طرف حساب','خریدار'),('حقوق','دستمزد','کارکرد'),('حضور','تردد','ورود','خروج'),('مالیات','مالیاتی','مالیاتها'),('پیام','چت','گفتگو'),('پرداخت','واریز','بدهی'),('دریافت','وصول','طلب'))
    terms=set(words)
    for group in synonyms:
        if any(x in q for x in group):terms.update(group)
    scored=[]
    for index,item in enumerate(TEMPLATES):
        if not available(owner,item):continue
        title=normalize(item['title']).casefold();body=normalize(item['text']).casefold()
        score=sum((4 if word in title else 1 if word in body else 0) for word in terms)
        if score:scored.append((-score,index,item))
    return [item for _,_,item in sorted(scored)[:limit]]
