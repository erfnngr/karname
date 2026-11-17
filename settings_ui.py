import uuid
from urllib.parse import urlsplit
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QTabWidget,QWidget,QScrollArea,QComboBox,QSpinBox,QLineEdit,QCheckBox,QLabel,QPushButton,QColorDialog,QDialogButtonBox,QTableWidget,QTableWidgetItem,QMessageBox,QAbstractItemView,QListWidget,QListWidgetItem,QGroupBox)
from reminders import parse_leads
from appearance import contrast
from color_wheel import ColorWheelDialog
from official_news import get_sources,validate_source_url,trusted

def page(tabs,name):
    scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();v=QVBoxLayout(body);v.setAlignment(Qt.AlignTop);scroll.setWidget(body);tabs.addTab(scroll,name);return v

class SettingsDialog(QDialog):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.original=dict(owner.data['settings']);s=self.original
        from appearance import flush_pending_qss,palette_for
        flush_pending_qss()
        c=palette_for(s)
        self.setWindowTitle('تنظیمات و شخصی‌سازی');self.resize(1000,700);self.setMinimumSize(850,560);self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet(
            f'QDialog{{background:{c["bg"]};color:{c["text"]};}} '
            f'QScrollArea, QTabWidget::pane{{background:{c["bg"]};color:{c["text"]};border:1px solid {c["border"]};border-radius:10px;}} '
            f'QLabel, QCheckBox, QRadioButton{{background:transparent;color:{c["text"]};}} '
            f'QGroupBox{{background:{c["panel"]};color:{c["text"]};border:1px solid {c["border"]};border-radius:10px;margin-top:12px;padding:12px 10px 10px 10px;font-weight:bold;}} '
            f'QGroupBox::title{{subcontrol-origin:margin;right:12px;padding:0 6px;color:{c["accent"]};}} '
            f'QListWidget{{background:{c["panel"]};color:{c["text"]};border:1px solid {c["border"]};border-radius:9px;}} '
            f'QListWidget::item{{color:{c["text"]};padding:7px 9px;border-radius:6px;}} '
            f'QListWidget::item:selected{{background:{c["selected"]};color:{c["text"]};}}'
        )
        v=QVBoxLayout(self);tabs=QTabWidget();body=QHBoxLayout();v.addLayout(body,1);navigation=QVBoxLayout();navigation_box=QWidget();navigation_box.setFixedWidth(190);navigation_box.setLayout(navigation);navigation.setContentsMargins(0,0,0,0);category_search=QLineEdit();category_search.setPlaceholderText('جستجوی تنظیمات');navigation.addWidget(category_search);categories=QListWidget();navigation.addWidget(categories,1);body.addWidget(navigation_box);body.addWidget(tabs,1);tabs.tabBar().hide()
        from access_ui import AccessPanel
        from ui_permissions import allowed
        if allowed(owner,'access'):self.access_panel=AccessPanel(owner,self);tabs.addTab(self.access_panel,'دسترسی')
        from personalization_ui import PersonalPanel,ServicesSettings,CompaniesSettings,RecoveryPanel
        self.personal=PersonalPanel(owner);personal=page(tabs,'حساب من و راهنما');personal.addWidget(self.personal)
        if allowed(owner,'company') or allowed(owner,'network'):self.company_settings=CompaniesSettings(owner);tabs.addTab(self.company_settings,'شرکت‌ها و شبکه')
        self.services_settings=ServicesSettings(owner);tabs.addTab(self.services_settings,'سامانه‌های من')
        invoice_page=page(tabs,'چاپ فاکتور');invoice_options=owner.data.get('preferences',{}).get('invoice_print',{});invoice_options=invoice_options if isinstance(invoice_options,dict) else {}
        self.invoice_logo=QCheckBox('نمایش نشان شرکت');self.invoice_logo.setChecked(invoice_options.get('show_logo',True));invoice_page.addWidget(self.invoice_logo)
        self.invoice_bank=QCheckBox('نمایش شماره حساب و شبا');self.invoice_bank.setChecked(invoice_options.get('show_bank',True));invoice_page.addWidget(self.invoice_bank)
        self.invoice_flags={}
        for key,label in [('show_seller','نمایش مشخصات فروشنده'),('show_buyer','نمایش مشخصات خریدار'),('show_financial','نمایش جزئیات تسویه'),('show_signature','نمایش بخش امضا'),('show_notes','نمایش توضیحات فاکتور')]:
            box=QCheckBox(label);box.setChecked(invoice_options.get(key,True));self.invoice_flags[key]=box;invoice_page.addWidget(box)
        print_sizes=QFormLayout();self.invoice_font_size=QSpinBox();self.invoice_font_size.setRange(7,11);self.invoice_font_size.setValue(int(invoice_options.get('font_size',8)));print_sizes.addRow('اندازه نوشته چاپ',self.invoice_font_size);self.invoice_padding=QSpinBox();self.invoice_padding.setRange(2,8);self.invoice_padding.setValue(int(invoice_options.get('cell_padding',4)));print_sizes.addRow('فاصله داخل جدول',self.invoice_padding);self.invoice_blank_rows=QSpinBox();self.invoice_blank_rows.setRange(0,12);self.invoice_blank_rows.setValue(int(invoice_options.get('blank_rows',7)));print_sizes.addRow('حداقل ردیف‌های فاکتور',self.invoice_blank_rows);self.invoice_logo_size=QSpinBox();self.invoice_logo_size.setRange(30,100);self.invoice_logo_size.setValue(int(invoice_options.get('logo_size',65)));print_sizes.addRow('اندازه نشان شرکت',self.invoice_logo_size);invoice_page.addLayout(print_sizes)
        invoice_page.addWidget(QLabel('متن پایین فاکتور'));self.invoice_footer=QLineEdit(str(invoice_options.get('footer',''))[:500]);self.invoice_footer.setMaxLength(500);invoice_page.addWidget(self.invoice_footer)
        backup_section=QTabWidget(self)
        if allowed(owner,'backup'):backup_section.addTab(RecoveryPanel(owner),'بازیابی');tabs.addTab(backup_section,'پشتیبان و بازیابی')
        from enhancement_settings import EnhancementSettings
        self.enhancements=EnhancementSettings(owner);tabs.addTab(self.enhancements,'نگهداری و شبکه')
        from ai_chat_ui import LMStudioSettings
        self.lm_settings=LMStudioSettings(owner) if allowed(owner,'assistant','configure') else None
        if self.lm_settings is not None:tabs.addTab(self.lm_settings,'هوش مصنوعی / LM Studio')
        appearance=page(tabs,'ظاهر');form=QFormLayout();appearance.addLayout(form)
        self.theme=QComboBox();self.theme.addItem('روز / روشن','light');self.theme.addItem('شب / تیره','dark');self.theme.setCurrentIndex(self.theme.findData(s['theme']));form.addRow('حالت نرم‌افزار:',self.theme)
        from theme_catalog import THEMES,preset
        self.theme_preset=QComboBox()
        for key,title,mode in THEMES:self.theme_preset.addItem(title,key)
        self.theme_preset.setCurrentIndex(self.theme_preset.findData(preset(s.get('theme_preset','default'))));form.addRow('تم برنامه:',self.theme_preset)
        def choose_preset(index):
            mode=THEMES[index][2];self.theme.setCurrentIndex(self.theme.findData(mode))
        self.theme_preset.currentIndexChanged.connect(choose_preset)
        self.font=QComboBox();self.font.addItem('وزیرمتن','Vazirmatn');self.font.addItem('ایران‌سنس','IRANSans');self.font.addItem('Tahoma','Tahoma');self.font.addItem('Segoe UI','Segoe UI');self.font.setCurrentIndex(max(0,self.font.findData(s['font_family'])));form.addRow('فونت:',self.font)
        self.font_size=QSpinBox();self.font_size.setRange(11,19);self.font_size.setValue(s['font_size']);form.addRow('اندازه نوشته‌ها:',self.font_size)
        appearance.addWidget(QLabel('فونت‌های وزیرمتن و ایران‌سنس برای انتخاب در برنامه آماده‌اند.'))
        self.daily_quote=QCheckBox('نمایش سخن بزرگان در پایین صفحه اصلی؛ روزی یک مورد');self.daily_quote.setChecked(s.get('daily_quote_enabled',True));appearance.addWidget(self.daily_quote)
        self.weather_enabled=QCheckBox('نمایش آب‌وهوای تهران در صفحه اصلی');self.weather_enabled.setChecked(s.get('weather_enabled',True));appearance.addWidget(self.weather_enabled)
        self.weather_hourly=QCheckBox('نمایش پیش‌بینی ساعتی در ویجت');self.weather_hourly.setChecked(s.get('weather_hourly',True));appearance.addWidget(self.weather_hourly)
        self.weather_weekly=QCheckBox('نمایش پیش‌بینی هفتگی در ویجت');self.weather_weekly.setChecked(s.get('weather_weekly',True));appearance.addWidget(self.weather_weekly)
        self.weather_api_base=QLineEdit(s.get('weather_api_base',''));self.weather_api_base.setPlaceholderText('نشانی پیش‌فرض سرویس آب‌وهوا');self.weather_api_base.setLayoutDirection(Qt.LeftToRight);form.addRow('نشانی سرویس آب‌وهوا:',self.weather_api_base)
        widgets_page=page(tabs,'چیدمان صفحه اصلی')
        preferences=owner.data.get('preferences') or {}
        if not isinstance(preferences,dict):preferences={}

        def _move_row(lst, delta):
            row=lst.currentRow()
            nxt=row+delta
            if row<0 or nxt<0 or nxt>=lst.count():return
            it=lst.takeItem(row)
            lst.insertItem(nxt,it)
            lst.setCurrentRow(nxt)

        cards_group=QGroupBox('کارت‌ها و ترتیب نمایش در صفحه اصلی');cards_v=QVBoxLayout(cards_group)
        cards_v.addWidget(QLabel('کارت‌های مورد نظر را فعال/غیرفعال کنید و ترتیب نمایش آن‌ها را با کشیدن یا دکمه‌های بالا/پایین تغییر دهید:'))
        cards_row=QHBoxLayout()
        self.home_cards_list=QListWidget();self.home_cards_list.setDragDropMode(QAbstractItemView.InternalMove);self.home_cards_list.setMinimumHeight(150);cards_row.addWidget(self.home_cards_list,1)
        cards_btns=QVBoxLayout()
        up_card=QPushButton('▲ بالا');up_card.clicked.connect(lambda:_move_row(self.home_cards_list,-1));cards_btns.addWidget(up_card)
        dn_card=QPushButton('▼ پایین');dn_card.clicked.connect(lambda:_move_row(self.home_cards_list,1));cards_btns.addWidget(dn_card)
        cards_btns.addStretch(1);cards_row.addLayout(cards_btns);cards_v.addLayout(cards_row)
        HOME_CARD_NAMES=[
            ('briefing','خلاصه هوشمند روز (هوش مصنوعی)'),
            ('weather','وضعیت آب‌وهوا و پیش‌بینی'),
            ('today_reminders','کارها و یادآورهای امروز و فردا'),
            ('activity_stats','شاخص‌های عملکرد و آمار کارنامه'),
            ('quote','سخن و بیت روز'),
        ]
        card_map=dict(HOME_CARD_NAMES)
        saved_cards=preferences.get('home_cards')
        has_saved_cards=isinstance(saved_cards,list) and any(k in card_map for k in saved_cards)
        card_order=([k for k in saved_cards if k in card_map] if has_saved_cards else [])+[k for k,_ in HOME_CARD_NAMES if not has_saved_cards or k not in saved_cards]
        checked_cards=set(saved_cards) if has_saved_cards else set(card_map.keys())
        for key in card_order:
            item=QListWidgetItem(card_map[key]);item.setData(Qt.UserRole,key)
            item.setFlags(item.flags()|Qt.ItemIsUserCheckable|Qt.ItemIsDragEnabled)
            item.setCheckState(Qt.Checked if key in checked_cards else Qt.Unchecked)
            self.home_cards_list.addItem(item)
        layout_form=QFormLayout()
        self.home_card_columns=QComboBox()
        for label,val in [('خودکار (هماهنگ با اندازه پنجره)','auto'),('۲ ستونی متعادل',2),('۳ ستونی عریض',3)]:
            self.home_card_columns.addItem(label,val)
        self.home_card_columns.setCurrentIndex(max(0,self.home_card_columns.findData(preferences.get('home_card_columns','auto'))))
        layout_form.addRow('ساختار ستون‌های کارت:',self.home_card_columns)
        self.home_density_mode=QComboBox()
        for label,val in [('متعادل (پیشنهادی)','comfortable'),('فشرده','compact'),('گسترده و باز','spacious')]:
            self.home_density_mode.addItem(label,val)
        self.home_density_mode.setCurrentIndex(max(0,self.home_density_mode.findData(preferences.get('home_density_mode','comfortable'))))
        layout_form.addRow('فاصله و اندازه کارت‌ها:',self.home_density_mode)
        cards_v.addLayout(layout_form);widgets_page.addWidget(cards_group)

        from home_layout import WIDGET_NAMES,BENTO_DEFAULT_MODULES
        bento_group=QGroupBox('گزینه‌های دسترسی سریع در تم بنتو گرید (حداکثر ۶ بخش)');bento_v=QVBoxLayout(bento_group)
        bento_hint=QLabel('در تم «بنتو گرید»، تا ۶ بخش انتخاب‌شده از فهرست زیر به‌عنوان کاشی دسترسی سریع وسط صفحه خانه نمایش داده می‌شوند:');bento_hint.setWordWrap(True);bento_v.addWidget(bento_hint)
        bento_row=QHBoxLayout()
        self.bento_modules=QListWidget();self.bento_modules.setDragDropMode(QAbstractItemView.InternalMove);self.bento_modules.setMinimumHeight(155);bento_row.addWidget(self.bento_modules,1)
        bento_btns=QVBoxLayout()
        up_bento=QPushButton('▲ بالا');up_bento.clicked.connect(lambda:_move_row(self.bento_modules,-1));bento_btns.addWidget(up_bento)
        dn_bento=QPushButton('▼ پایین');dn_bento.clicked.connect(lambda:_move_row(self.bento_modules,1));bento_btns.addWidget(dn_bento)
        bento_btns.addStretch(1);bento_row.addLayout(bento_btns);bento_v.addLayout(bento_row)
        from react_home_bridge import MODULE_CATALOG
        bento_catalog=[(k,t) for k,t,_ in MODULE_CATALOG if k in getattr(owner,'modules',{}) and allowed(owner,k)]
        saved_bento=preferences.get('bento_modules')
        saved_bento_list=saved_bento if isinstance(saved_bento,list) else list(BENTO_DEFAULT_MODULES)
        bento_names=dict(bento_catalog)
        bento_order=[k for k in saved_bento_list if k in bento_names]+[k for k,_ in bento_catalog if k not in saved_bento_list]
        checked_bento=set(saved_bento_list if isinstance(saved_bento,list) else BENTO_DEFAULT_MODULES)
        for key in bento_order:
            item=QListWidgetItem(bento_names[key]);item.setData(Qt.UserRole,key);item.setFlags(item.flags()|Qt.ItemIsUserCheckable|Qt.ItemIsDragEnabled)
            item.setCheckState(Qt.Checked if key in checked_bento else Qt.Unchecked);self.bento_modules.addItem(item)
        widgets_page.addWidget(bento_group)

        classic_group=QGroupBox('تنظیمات تکمیلی نمای کلاسیک و ویرایشگر آزاد');classic_v=QVBoxLayout(classic_group)
        raw_saved=preferences.get('home_widgets')
        saved=raw_saved if isinstance(raw_saved,list) else None
        self.widgets_custom=QCheckBox('چیدمان شخصی ویجت‌ها فعال باشد');self.widgets_custom.setChecked(saved is not None);classic_v.addWidget(self.widgets_custom)
        classic_v.addWidget(QLabel('چیدمان کلاسیک را می‌توانید با کشیدن ویجت‌ها ویرایش کنید یا از فهرست زیر تغییر دهید:'))
        self.edit_home_layout=QPushButton('ویرایش مستقیم صفحه اصلی');self.edit_home_layout.setObjectName('EditHomeLayout');self.edit_home_layout.clicked.connect(self.open_home_editor);classic_v.addWidget(self.edit_home_layout)
        self.home_widgets=QListWidget();self.home_widgets.setDragDropMode(QAbstractItemView.InternalMove);self.home_widgets.setMinimumHeight(140);classic_v.addWidget(self.home_widgets)
        names=WIDGET_NAMES
        order=list(saved or [])+[key for key in names if key not in (saved or [])]
        for key in order:
            if key not in names:continue
            item=QListWidgetItem(names[key]);item.setData(Qt.UserRole,key);item.setFlags(item.flags()|Qt.ItemIsUserCheckable|Qt.ItemIsDragEnabled);item.setCheckState(Qt.Checked if (saved is None and not key.startswith('quick_')) or saved is not None and key in saved else Qt.Unchecked);self.home_widgets.addItem(item)
        raw_sizes=preferences.get('home_widget_sizes');sizes=raw_sizes if isinstance(raw_sizes,dict) else {};self.home_widget_sizes={};size_form=QFormLayout()
        for key,name in names.items():
            box=QComboBox();box.addItem('یک ستون',1);box.addItem('دو ستون',2);box.addItem('سه ستون',3);box.addItem('چهار ستون',4);box.setCurrentIndex(max(0,box.findData(sizes.get(key,1))));self.home_widget_sizes[key]=box;size_form.addRow(name,box)
        classic_v.addWidget(QLabel('اندازه ویجت‌ها'));classic_v.addLayout(size_form)
        widget_options=QFormLayout();self.home_columns=QSpinBox();self.home_columns.setRange(2,4);self.home_columns.setValue(max(2,min(4,int(preferences.get('home_widget_columns') or 3))));widget_options.addRow('تعداد ستون‌ها',self.home_columns);self.home_spacing=QSpinBox();self.home_spacing.setRange(3,20);self.home_spacing.setValue(max(3,min(20,int(preferences.get('home_widget_spacing') or 8))));widget_options.addRow('فاصله ویجت‌ها',self.home_spacing);self.home_height=QComboBox()
        for label,value in [('فشرده',70),('معمولی',100),('بلند',130)]:self.home_height.addItem(label,value)
        self.home_height.setCurrentIndex(max(0,self.home_height.findData(preferences.get('home_widget_height',100))));widget_options.addRow('ارتفاع حداقل',self.home_height);classic_v.addLayout(widget_options)
        widgets_page.addWidget(classic_group)
        quote_note=QLabel('۳۰۰ سخن و بیت کوتاهِ مستند، همراه نام گوینده و پیوند متن اصلی. مجموعه بدون اینترنت قابل‌نمایش است. رنگ آن از تنظیم نوشته و زمینه صفحه اصلی پیروی می‌کند.');quote_note.setWordWrap(True);appearance.addWidget(quote_note)
        alert_section=QTabWidget();tabs.addTab(alert_section,'یادآورها و رنگ‌ها');rem=page(alert_section,'زمان‌بندی');rf=QFormLayout();rem.addLayout(rf)
        self.autostart=QCheckBox('اجرای خودکار همراه ورود به ویندوز');self.autostart.setChecked(s['startup']);rem.addWidget(self.autostart)
        self.master=QCheckBox('یادآورها فعال باشند');self.master.setChecked(s['reminder_enabled']);rem.addWidget(self.master)
        self.default_enabled=QCheckBox('یادآورهای کاری و برنامه‌ریزی‌شده');self.default_enabled.setChecked(s['default_reminders']);rf.addRow(self.default_enabled)
        self.default_days=QLineEdit('، '.join(map(str,s['default_lead_days'])));rf.addRow('روزهای قبل از موعد — کاری:',self.default_days)
        self.personal_enabled=QCheckBox('یادآورهای شخصی');self.personal_enabled.setChecked(s['personal_reminders']);rf.addRow(self.personal_enabled)
        self.personal_days=QLineEdit('، '.join(map(str,s['personal_lead_days'])));rf.addRow('روزهای قبل از موعد — شخصی:',self.personal_days)
        self.check_enabled=QCheckBox('یادآوری سررسید چک‌های وصول‌نشده');self.check_enabled.setChecked(s.get('check_reminders',True));rf.addRow(self.check_enabled)
        self.check_days=QLineEdit('، '.join(map(str,s.get('check_lead_days',[20,15,10,5,4,3,2,1,0]))));rf.addRow('روزهای قبل از سررسید چک:',self.check_days)
        info=QLabel('۲۰، ۱۵، ۱۰، ۵، ۴، ۳، ۲، ۱، ۰ یعنی در ۲۰، ۱۵، ۱۰ و ۵ روز مانده و سپس هر روز تا روز موعد. تنظیم اختصاصی هر رویداد در ویرایش آن است.');info.setWordWrap(True);rem.addWidget(info)
        self.summary=QCheckBox('خلاصه کارهای این ماه در شروع روز نمایش داده شود');self.summary.setChecked(s['monthly_summary']);rem.addWidget(self.summary)
        self.splash=QCheckBox('پنجره شروع برنامه نمایش داده شود');self.splash.setChecked(s['show_startup_popup']);rem.addWidget(self.splash)
        self.overdue=QCheckBox('کار معوق تا زمان انجام، روزی یک بار یادآوری شود');self.overdue.setChecked(s['overdue_reminders']);rem.addWidget(self.overdue)
        self.native=QCheckBox('اعلان اضافی مرکز اعلان ویندوز (زمان ماندن آن را ویندوز تعیین می‌کند)');self.native.setChecked(s['windows_notifications']);rem.addWidget(self.native)
        style=page(alert_section,'ظاهر اعلان');sf=QFormLayout();style.addLayout(sf)
        self.seconds=QSpinBox();self.seconds.setRange(1,60);self.seconds.setValue(s['popup_seconds']);sf.addRow('محو کامل پس از چند ثانیه:',self.seconds)
        self.opacity=QSpinBox();self.opacity.setRange(40,100);self.opacity.setSuffix('٪');self.opacity.setValue(s['popup_opacity']);sf.addRow('میزان وضوح اعلان:',self.opacity)
        self.fade=QSpinBox();self.fade.setRange(100,3000);self.fade.setSingleStep(100);self.fade.setValue(s['popup_fade_ms']);sf.addRow('مدت محو شدن (میلی‌ثانیه):',self.fade)
        self.colors={key:s[key] for key in ['popup_bg','popup_fg','event_insurance_color','event_tax_color','event_personal_color','home_text_color','home_panel_color','mana_popup_color','airia_popup_color','arka_popup_color','personal_popup_color']};self.color_buttons={}
        self.preview_company=QComboBox();self.preview_company.addItems(['شخصی','مانا','آیریا','آرکا']);sf.addRow('اعلان آزمایشی:',self.preview_company)
        preview=QPushButton('آزمایش یادآور ۵ ثانیه‌ای');preview.clicked.connect(self.preview);style.addWidget(preview)
        color_page=page(alert_section,'رنگ‌ها');cf=QFormLayout();color_page.addLayout(cf);self.event_opacity={}
        color_labels=[('event_insurance_color','یادآور کاری بیمه'),('event_tax_color','یادآور کاری مالیات'),('event_personal_color','یادآور شخصی'),('home_text_color','نوشته‌های صفحه اصلی'),('home_panel_color','زمینه اطلاعات صفحه اصلی'),('mana_popup_color','زمینه اعلان مانا'),('airia_popup_color','زمینه اعلان آیریا'),('arka_popup_color','زمینه اعلان آرکا'),('personal_popup_color','زمینه اعلان شخصی')]
        for key,title in color_labels:
            b=QPushButton(title);b.setStyleSheet('border-left:14px solid '+self.colors[key]+';');self.color_buttons[key]=b;b.clicked.connect(lambda checked=False,k=key:self.choose_color(k));cf.addRow(b)
            if key.startswith('event_'):
                opacity=QSpinBox();opacity.setRange(5,100);opacity.setSuffix('٪');opacity_key=key.replace('_color','_opacity');opacity.setValue(s[opacity_key]);self.event_opacity[opacity_key]=opacity;cf.addRow('شدت رنگ '+title+':',opacity)
        self.home_opacity=QSpinBox();self.home_opacity.setRange(40,100);self.home_opacity.setSuffix('٪');self.home_opacity.setValue(s['home_panel_opacity']);cf.addRow('وضوح زمینه اطلاعات صفحه اصلی:',self.home_opacity)
        color_page.addWidget(QLabel('برای انتخاب رنگ روی دکمه بزنید؛ دایره طیف رنگ، روشنایی و کد رنگ در دسترس است.'))
        # Unscheduled startup, overdue and summary popups are retired in version 4.
        self.summary.hide();self.splash.hide();self.overdue.hide()
        news=page(tabs,'خبرها و منابع');nf=QFormLayout();news.addLayout(nf)
        self.news_terms=QLineEdit(owner.data.get('preferences',{}).get('news_terms',''));self.news_terms.setPlaceholderText('مثلاً #مالیات، #بیمه، پیوند یا واژه');nf.addRow('فیلتر لینک / هشتگ',self.news_terms);self.news_source_checks={}
        chosen=owner.data.get('preferences',{}).get('news_source_ids')
        for source in get_sources(owner.data):
            check=QCheckBox(source['name']);check.setChecked(chosen is None or source['id'] in chosen);news.addWidget(check);self.news_source_checks[source['id']]=check
        self.news_enabled=QCheckBox('دریافت خودکار اخبار');self.news_enabled.setChecked(s['news_enabled']);news.addWidget(self.news_enabled)
        self.interval=QSpinBox();self.interval.setRange(5,1440);self.interval.setValue(s['news_interval']);nf.addRow('فاصله بررسی موفق (دقیقه):',self.interval)
        self.proxy=QLineEdit(s.get('news_proxy',''));self.proxy.setPlaceholderText('اختیاری: http://127.0.0.1:8080');nf.addRow('پراکسی همین برنامه:',self.proxy)
        note=QLabel('خالی: استفاده از اتصال و پراکسی محیط ویندوز. محدودیت جغرافیایی یا منع دسترسی سایت با تغییر رنگ و تنظیم برنامه برطرف نمی‌شود. حساب کاربری یا رمز در این بخش وارد نکنید.');note.setWordWrap(True);news.addWidget(note)
        self.sources=QTableWidget(0,4);self.sources.setHorizontalHeaderLabels(['نام منبع','صفحه خبر / دسته','خبرخوان اختیاری','فعال']);self.sources.setMinimumHeight(210);self.sources.setSelectionBehavior(QAbstractItemView.SelectRows);self.sources.horizontalHeader().setStretchLastSection(True);news.addWidget(self.sources)
        for source in get_sources(owner.data):self.add_source(source)
        buttons=QHBoxLayout();add=QPushButton('افزودن منبع');add.clicked.connect(lambda:self.add_source());buttons.addWidget(add)
        remove=QPushButton('حذف منبع انتخاب‌شده');remove.clicked.connect(self.remove_source);buttons.addWidget(remove);news.addLayout(buttons)
        news.addWidget(QLabel('نام و نشانی‌ها با دوبار کلیک قابل‌ویرایش‌اند. منابع تکمیلی، مرجع رسمی تغییر مهلت و قانون نیستند.'))
        backups=page(backup_section,'پشتیبان و فایل');tip=QLabel('هنگام خروج کامل، اگر اطلاعات تغییر کرده باشد، ذخیره پشتیبان تأیید می‌شود. لغو یا خطا، برنامه را باز نگه می‌دارد. برای ادامه یادآورها در پس‌زمینه از منوی آیکون کنار ساعت ویندوز استفاده کنید.');tip.setWordWrap(True);backups.addWidget(tip)
        from ui_icons import iconize
        actions_row=QHBoxLayout()
        for title,key,callback in [('ذخیره پشتیبان','backup',owner.backup_now),('بازگردانی پشتیبان','restore',owner.restore_backup),('اشتراک‌گذاری فایل','share',owner.share_data)]:
            action=QPushButton(title);iconize(action,key);action.clicked.connect(callback);actions_row.addWidget(action)
        actions_row.addStretch();backups.addLayout(actions_row)
        actions=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);actions.button(QDialogButtonBox.Save).setText('ذخیره');actions.button(QDialogButtonBox.Save).setEnabled(allowed(owner,'settings','edit'));actions.button(QDialogButtonBox.Cancel).setText('انصراف');actions.accepted.connect(self.validate);actions.rejected.connect(self.reject);v.addWidget(actions)
        categories.addItems([tabs.tabText(i) for i in range(tabs.count())]);categories.currentRowChanged.connect(tabs.setCurrentIndex)
        self.category_search=category_search;self.categories=categories;self.settings_pages=tabs
        # Index labels and control names, not values typed into personal fields.
        searchable=[]
        for index in range(tabs.count()):
            panel=tabs.widget(index);labels=[tabs.tabText(index)]
            for widget_type in (QLabel,QCheckBox,QPushButton):
                for widget in panel.findChildren(widget_type):
                    text=widget.text()
                    if text:labels.append(text)
            searchable.append(' '.join(labels))
        for i in range(categories.count()):
            title=categories.item(i).text()
            denied=title=='پشتیبان و بازیابی' and not allowed(owner,'backup') or title=='خبرها و منابع' and not allowed(owner,'news') or title=='سامانه‌های من' and not allowed(owner,'services');categories.item(i).setData(Qt.UserRole,not denied);categories.item(i).setHidden(denied)
        def filter_categories(value):
            from storage import normalize
            query=normalize(value).casefold().strip();first=None
            for i in range(categories.count()):
                item=categories.item(i);visible=bool(item.data(Qt.UserRole)) and (not query or query in normalize(searchable[i]).casefold());item.setHidden(not visible)
                if visible and first is None:first=i
            current=categories.currentItem()
            if first is not None and (current is None or current.isHidden()):categories.setCurrentRow(first)
        category_search.textChanged.connect(filter_categories)
        categories.setCurrentRow(next((i for i in range(categories.count()) if not categories.item(i).isHidden()),0))

    def open_home_editor(self):
        self.reject();self.owner.tabs.setCurrentWidget(self.owner.home)
        def _launch():
            try:self.owner.home.edit_layout()
            except Exception as exc:QMessageBox.warning(self.owner,'چیدمان صفحه اصلی','بازکردن ویرایشگر چیدمان ناموفق بود: '+str(exc))
        QTimer.singleShot(0,_launch)

    def choose_color(self,key):
        color=ColorWheelDialog.choose(self.colors[key],self)
        if color:self.colors[key]=color;self.color_buttons[key].setStyleSheet('border-left:14px solid '+color+';')

    def add_source(self,source=None):
        source=source or dict(id='custom-'+uuid.uuid4().hex[:10],name='منبع جدید',url='https://',feed='',enabled=True)
        row=self.sources.rowCount();self.sources.insertRow(row)
        for col,key in enumerate(('name','url','feed')):
            item=QTableWidgetItem(source.get(key,''));self.sources.setItem(row,col,item)
            if col==0:item.setData(Qt.UserRole,source['id'])
        enabled=QTableWidgetItem();enabled.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable);enabled.setCheckState(Qt.Checked if source.get('enabled',True) else Qt.Unchecked);self.sources.setItem(row,3,enabled)
        self.sources.setColumnWidth(0,140);self.sources.setColumnWidth(1,260);self.sources.setColumnWidth(2,200)

    def remove_source(self):
        row=self.sources.currentRow()
        if row>=0:self.sources.removeRow(row)

    def values(self):
        result=dict(self.original)
        result.update(self.enhancements.values())
        if self.lm_settings is not None:result['lmstudio']=self.lm_settings.values()
        result['daily_quote_enabled']=self.daily_quote.isChecked()
        result['weather_enabled']=self.weather_enabled.isChecked()
        result['weather_hourly']=self.weather_hourly.isChecked();result['weather_weekly']=self.weather_weekly.isChecked()
        result['weather_api_base']=self.weather_api_base.text().strip().rstrip('/')
        if result['weather_api_base']:
            u=urlsplit(result['weather_api_base'])
            if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:raise ValueError('نشانی سرویس آب‌وهوا باید یک نشانی HTTPS معتبر باشد.')
        result.update(theme=self.theme.currentData(),theme_preset=self.theme_preset.currentData(),font_family=self.font.currentData(),font_size=self.font_size.value(),startup=self.autostart.isChecked(),reminder_enabled=self.master.isChecked(),default_reminders=self.default_enabled.isChecked(),personal_reminders=self.personal_enabled.isChecked(),default_lead_days=parse_leads(self.default_days.text()),personal_lead_days=parse_leads(self.personal_days.text()),check_reminders=self.check_enabled.isChecked(),check_lead_days=parse_leads(self.check_days.text()),monthly_summary=self.summary.isChecked(),show_startup_popup=self.splash.isChecked(),overdue_reminders=self.overdue.isChecked(),windows_notifications=self.native.isChecked(),popup_seconds=self.seconds.value(),popup_opacity=self.opacity.value(),popup_fade_ms=self.fade.value(),news_enabled=self.news_enabled.isChecked(),news_interval=self.interval.value(),news_proxy=self.proxy.text().strip(),**self.colors)
        result.update({key:spin.value() for key,spin in self.event_opacity.items()});result['home_panel_opacity']=self.home_opacity.value()
        bg=QColor(result['home_panel_color']);alpha=result['home_panel_opacity']/100
        blended=QColor(round(255*(1-alpha)+bg.red()*alpha),round(255*(1-alpha)+bg.green()*alpha),round(255*(1-alpha)+bg.blue()*alpha)).name()
        if contrast(result['home_text_color'],blended)<4.5:raise ValueError('رنگ نوشته و زمینه اطلاعات صفحه اصلی خوانایی کافی ندارند؛ رنگ روشن و تیره متفاوت انتخاب کنید.')
        result['monthly_summary']=False;result['overdue_reminders']=False
        if result['news_proxy']:
            p=urlsplit(result['news_proxy'])
            if p.scheme not in ('http','https') or not p.hostname or not p.port or p.username or p.password:raise ValueError('پراکسی را با قالب http://host:port و بدون رمز وارد کنید.')
        return result

    def preview(self):
        try:self.owner.popup('این یک اعلان آزمایشی است.\n۲۰ روز تا موعد یادآور باقی مانده است.',settings=dict(self.values(),popup_seconds=5),title='آزمایش یادآور',company=None if self.preview_company.currentText()=='شخصی' else self.preview_company.currentText())
        except ValueError as e:QMessageBox.warning(self,'تنظیمات',str(e))

    def validate(self):
        from ui_permissions import gate
        if not gate(self.owner,'settings','edit'):return
        try:
            self.result_value=self.values();self.result_sources=[]
            for row in range(self.sources.rowCount()):
                name=self.sources.item(row,0).text().strip();url=self.sources.item(row,1).text().strip();feed=self.sources.item(row,2).text().strip();domain=validate_source_url(url)
                if not name:raise ValueError('نام منبع نمی‌تواند خالی باشد.')
                if feed and not trusted(feed,domain):raise ValueError('خبرخوان باید در همان دامنه منبع باشد و https داشته باشد.')
                self.result_sources.append(dict(id=self.sources.item(row,0).data(Qt.UserRole),name=name,url=url,feed=feed,domain=domain,enabled=self.sources.item(row,3).checkState()==Qt.Checked))
            prefs=self.personal.values();prefs['services']=self.services_settings.items;prefs['news_terms']=self.news_terms.text().strip();prefs['news_source_ids']=[k for k,c in self.news_source_checks.items() if c.isChecked()]
            prefs['invoice_print']=dict(show_logo=self.invoice_logo.isChecked(),show_bank=self.invoice_bank.isChecked(),footer=self.invoice_footer.text().strip(),font_size=self.invoice_font_size.value(),cell_padding=self.invoice_padding.value(),blank_rows=self.invoice_blank_rows.value(),logo_size=self.invoice_logo_size.value(),**{key:box.isChecked() for key,box in self.invoice_flags.items()})
            if self.widgets_custom.isChecked():
                from theme_catalog import preset
                prefs['home_widgets']=[self.home_widgets.item(i).data(Qt.UserRole) for i in range(self.home_widgets.count()) if self.home_widgets.item(i).checkState()==Qt.Checked];prefs['home_customize_v2']=True
                if preset(self.result_value.get('theme_preset','default'))=='default':prefs['home_custom_on_default']=True
            else:prefs.pop('home_widgets',None)
            prefs['home_widget_sizes']={key:box.currentData() for key,box in self.home_widget_sizes.items()}
            prefs['home_widget_columns']=self.home_columns.value();prefs['home_widget_spacing']=self.home_spacing.value();prefs['home_widget_height']=self.home_height.currentData()
            chosen_bento=[self.bento_modules.item(i).data(Qt.UserRole) for i in range(self.bento_modules.count()) if self.bento_modules.item(i).checkState()==Qt.Checked]
            prefs['bento_modules']=chosen_bento[:6] if len(chosen_bento)>6 else chosen_bento
            prefs['home_cards']=[self.home_cards_list.item(i).data(Qt.UserRole) for i in range(self.home_cards_list.count()) if self.home_cards_list.item(i).checkState()==Qt.Checked]
            prefs['home_card_columns']=self.home_card_columns.currentData()
            prefs['home_density_mode']=self.home_density_mode.currentData()
            profile=dict(avatar=self.personal.avatar,color=self.personal.color,preferences=prefs)
            if self.owner.session_user:
                if self.owner.org.client:
                    from personalization_ui import request_wait
                    profile=request_wait(self.owner,'profile',profile)
                    self.owner.data.pop('pending_birthday_sync',None)
                else:
                    self.owner.data['pending_birthday_sync']=True
                self.owner.session_user['profile']=profile
                from access_ui import config,save_config
                cfg=config(self.owner.base_dir);cfg.update(avatar=profile['avatar'],display_name=self.owner.session_user['fullname']);save_config(self.owner.base_dir,cfg)
            self.enhancements.commit()
            if self.lm_settings is not None:self.lm_settings.commit()
            self.owner.data['preferences']=prefs;self.owner.data['account_profile']=profile;self.accept()
        except ValueError as e:QMessageBox.warning(self,'تنظیمات نامعتبر',str(e))
        except Exception as e:QMessageBox.warning(self,'ذخیره تنظیمات',str(e))
