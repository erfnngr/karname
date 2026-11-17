"""Calculator, service directory and public official notices panels."""
import threading
from datetime import datetime, timezone
from decimal import Decimal
import jdatetime
from PySide6.QtCore import Qt, QTimer, QObject, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox, QCheckBox, QScrollArea, QFrame, QMessageBox,QGridLayout
from storage import fa, new_event, jformat, today_j, parse_j
from penalties import get_rules, calculate, number
from official_news import SOURCES, fetch_source, merge_news, trusted,get_sources,validate_source_url
from news_dates import prune_news,parse_publication,TEHRAN

def text(value):
    w=QLabel(str(value));w.setTextFormat(Qt.PlainText);w.setWordWrap(True)
    return w

def button(title, callback):
    b=QPushButton(title);b.setCursor(Qt.PointingHandCursor);b.clicked.connect(callback)
    return b

def display_stamp(stamp):
    parsed=parse_publication(stamp)
    if not parsed:return 'ثبت نشده'
    local=parsed.astimezone(TEHRAN)
    return jformat(jdatetime.date.fromgregorian(date=local.date()))+' · '+fa(local.strftime('%H:%M'))

def open_official(url):
    try:
        validate_source_url(url)
        # Use the Windows URL association directly in packaged desktop builds.
        import os,webbrowser
        if os.name=='nt':
            os.startfile(url);return True
        if QDesktopServices.openUrl(QUrl(url)):return True
        if webbrowser.open(url):return True
        raise OSError('مرورگر پیش‌فرض مشخص نشده است.')
    except Exception:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(url)
        QMessageBox.information(None,'باز کردن سایت','باز کردن مرورگر انجام نشد. نشانی در کلیپ‌بورد کپی شد؛ آن را در مرورگر وارد کنید.\n'+url)
        return False

def scroll_page():
    outer=QWidget();lay=QVBoxLayout(outer);scroll=QScrollArea();scroll.setWidgetResizable(True)
    body=QWidget();body_layout=QVBoxLayout(body);body_layout.setAlignment(Qt.AlignTop);body_layout.setSpacing(15)
    scroll.setWidget(body);lay.addWidget(scroll)
    return outer,body_layout

class Calculator(QWidget):
    def __init__(self, owner):
        super().__init__();self.owner=owner
        v=QVBoxLayout(self);v.setContentsMargins(22,16,22,16);v.setSpacing(10)
        title=text('جرایم مالیات و بیمه');title.setObjectName('Hero');v.addWidget(title)
        self.setToolTip('برآورد بر اساس نرخ‌های قابل‌ویرایش شما؛ با پرونده و بخشنامه جاری تطبیق دهید.')
        form=QFormLayout();form.setSpacing(12);v.addLayout(form)
        self.kind=QComboBox();self.rules=get_rules(owner.data)
        for r in self.rules:self.kind.addItem(r['name'],r['id'])
        form.addRow('نوع مالیات / بیمه:',self.kind)
        self.basis=text('');form.addRow('مبنای مبلغ:',self.basis)
        self.amount=QLineEdit('100,000,000');self.amount.setAccessibleName('مبلغ مبنای محاسبه')
        form.addRow('مبلغ مبنا:',self.amount)
        self.unit=QComboBox();self.unit.addItems(['ریال','تومان']);form.addRow('واحد همه مبالغ:',self.unit)
        self.fixed=QLineEdit();self.monthly=QLineEdit();self.months=QLineEdit('1')
        self.use_fixed=QCheckBox('جریمه ثابت (درصد)');self.use_fixed.setChecked(True)
        self.use_monthly=QCheckBox('جریمه ماهانه (درصد)');self.use_monthly.setChecked(True)
        form.addRow(self.use_fixed,self.fixed);form.addRow(self.use_monthly,self.monthly)
        self.fixed.setAccessibleName('درصد جریمه ثابت');self.monthly.setAccessibleName('درصد ماهانه')
        form.addRow('ماه تأخیر (قابل‌ویرایش):',self.months)

        self.note=QLabel(self);self.note.hide()
        actions=QHBoxLayout();actions.addWidget(button('محاسبه',self.compute));actions.addWidget(button('ذخیره نرخ‌های این نوع',self.save_rule));v.addLayout(actions)
        self.result=text('');self.result.setObjectName('Result');self.result.setTextInteractionFlags(Qt.TextSelectableByMouse);v.addWidget(self.result)
        self.status=text('');v.addWidget(self.status);v.addStretch()
        self.kind.currentIndexChanged.connect(self.select_rule)
        for w in (self.amount,self.fixed,self.monthly,self.months):w.textChanged.connect(self.compute)
        self.use_fixed.toggled.connect(self.compute);self.use_monthly.toggled.connect(self.compute);self.unit.currentIndexChanged.connect(self.compute)
        self.select_rule()

    def select_rule(self,*_):
        r=self.rules[self.kind.currentIndex()]
        self.basis.setText(r['basis']);self.note.setText(r['note'])
        self.fixed.setText(r['fixed']);self.monthly.setText(r['monthly']);self.status.setText('');self.compute()

    def compute(self,*_):
        try:
            result=calculate(self.amount.text(),self.fixed.text(),self.monthly.text(),self.months.text(),use_fixed=self.use_fixed.isChecked(),use_monthly=self.use_monthly.isChecked())
            money=lambda value:fa(f'{value:,.0f}')+' '+self.unit.currentText()
            amount=number(self.amount.text());unit=self.unit.currentText()
            self.result.setText('جریمه ثابت: '+money(result['fixed'])+'\nجریمه تأخیر: '+money(result['delay'])+'\nمجموع جرایم: '+money(result['penalty'])+'\nاصل مبلغ و جریمه: '+money(result['total']))
            self.result.setToolTip('مبلغ مبنا × درصد ثابت + مبلغ مبنا × درصد ماهانه × تعداد ماه؛ بخشودگی اعمال نشده است.'+('\nمعادل مجموع جریمه به ریال: '+fa(f"{result['penalty']*10:,.0f}") if unit=='تومان' else ''))
        except ValueError as exc:self.result.setText(str(exc))

    def save_rule(self):
        try:
            calculate('0',self.fixed.text(),self.monthly.text(),'0')
        except ValueError as exc:
            self.status.setText(str(exc));return
        r=self.rules[self.kind.currentIndex()];r.update(fixed=str(number(self.fixed.text())),monthly=str(number(self.monthly.text())))
        self.owner.data.setdefault('penalty_rules',{})[r['id']]={'fixed':r['fixed'],'monthly':r['monthly']}
        self.owner.persist();self.status.setText('نرخ‌های انتخاب‌شده روی همین رایانه ذخیره شدند.')

    def select_for_event(self,event):
        title=event.get('title','');category=event.get('category','')
        key='insurance' if 'بیمه' in title+category else 'vat' if 'ارزش افزوده' in title else 'salary' if 'حقوق' in title else 'rent' if 'اجاره' in title else 'performance' if 'عملکرد' in title else 'books' if 'دفاتر' in title else 'seasonal' if 'فصلی' in title else 'custom'
        self.kind.setCurrentIndex(self.kind.findData(key))
        self.status.setText('رویداد: '+title+' — یادداشت اولیه: '+event.get('notes',''))

SERVICES = [
    ('مالیات — اظهارنامه و پرداخت','اظهارنامه عملکرد، ارزش افزوده، بدهی و پرداخت: ورود به درگاه ملی خدمات مالیاتی و انتخاب پرونده مربوط.','https://my.tax.gov.ir/'),
    ('مالیات — اطلاعات و راهنمای سامانه‌ها','برای انتخاب مسیر جاری اظهارنامه، حقوق، معاملات فصلی و سایر تکالیف، فهرست خدمات سازمان را باز کنید.','https://tax.gov.ir/'),
    ('بیمه — ارسال لیست و خدمات کارفرمایان','ورود به خدمات غیرحضوری؛ پس از ورود، خدمات کارفرمایان و ارسال لیست را انتخاب کنید.','https://es.tamin.ir/'),
    ('بیمه — پرداخت و مدیریت بدهی','درگاه خدمات غیرحضوری معرفی‌شده در سایت تأمین اجتماعی؛ برای پرداخت و بدهی وارد حساب شوید.','https://es.tamin.ir/'),
]

class Services(QWidget):
    def __init__(self,owner=None):
        super().__init__();self.owner=owner;self._cols=2;self.v=QVBoxLayout(self);self.v.setContentsMargins(22,16,22,16);self.v.setSpacing(12)
        head=QFrame();head.setObjectName('ServicesToolbar');hl=QHBoxLayout(head);hl.setContentsMargins(16,12,16,12)
        title_box=QVBoxLayout();title_box.setSpacing(2);title=text('سامانه‌ها و درگاه‌های کاربردی');title.setObjectName('Hero');title_box.addWidget(title)
        sub=text('دسترسی سریع و امن به سامانه‌های مالیاتی، بیمه و درگاه‌های برخط');sub.setObjectName('Sub');title_box.addWidget(sub)
        hl.addLayout(title_box,1);self.v.addWidget(head)
        self.shell=QWidget();self.grid=QGridLayout(self.shell);self.grid.setAlignment(Qt.AlignTop);self.grid.setSpacing(12);self.area=QScrollArea();self.area.setWidgetResizable(True);self.area.setWidget(self.shell);self.v.addWidget(self.area,1);self.refresh()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        cols=3 if self.width()>=1260 else 2
        if cols!=self._cols:
            self._cols=cols;self.refresh()
    def refresh(self):
        from personalization_ui import default_services
        from PySide6.QtGui import QColor
        from urllib.parse import urlsplit
        from appearance import palette_for,contrast
        while self.grid.count():
            w=self.grid.takeAt(0).widget()
            if w:w.hide();w.deleteLater()
        prefs=self.owner.data.get('preferences',{}) if self.owner else {};items=prefs.get('services',default_services());settings=self.owner.data['settings'] if self.owner else {};palette=palette_for(settings);base=QColor(palette['panel']);index=0;cols=max(2,self._cols)
        for item in items:
            if not item.get('enabled',True):continue
            color=QColor(item.get('color','#258B87'));alpha=max(8,min(38,int(item.get('opacity',15))))/100;bg=QColor(round(base.red()*(1-alpha)+color.red()*alpha),round(base.green()*(1-alpha)+color.green()*alpha),round(base.blue()*(1-alpha)+color.blue()*alpha)).name();fg=max((palette['text'],'#FFFFFF'),key=lambda c:contrast(c,bg));muted=palette['muted'] if contrast(palette['muted'],bg)>=4.0 else fg
            card=QFrame();card.setObjectName('ServiceCard');card.setStyleSheet(f'QFrame#ServiceCard {{background:{bg};border:1px solid {palette["border"]};border-right:4px solid {color.name()};border-radius:14px;}} QFrame#ServiceCard:hover {{border:1px solid {color.name()};border-right:4px solid {color.name()};}} QLabel {{background:transparent;color:{fg};}}')
            row=QHBoxLayout(card);row.setContentsMargins(16,14,16,14);row.setSpacing(12);names=QVBoxLayout();names.setSpacing(4)
            host=urlsplit(item.get('url','')).netloc
            if host:
                badge=text(host);badge.setStyleSheet(f'color:{color.name()};font-size:11px;font-weight:bold;background:transparent;');names.addWidget(badge)
            name=text(item['name']);name.setStyleSheet('font-weight:bold;font-size:14px;background:transparent;');names.addWidget(name)
            if item.get('topic') and item['topic']!=item['name']:
                topic=text(item['topic']);topic.setStyleSheet(f'color:{muted};font-size:12px;background:transparent;');names.addWidget(topic)
            if item.get('notes'):name.setToolTip(item['notes'])
            row.addLayout(names,1);go=button('ورود',lambda checked=False,u=item['url']:open_official(u));go.setObjectName('Primary');row.addWidget(go);self.grid.addWidget(card,index//cols,index%cols);index+=1
        for col in range(cols):self.grid.setColumnStretch(col,1)

class NewsSignals(QObject):
    result=Signal(object)

class NewsPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.state=owner.data.setdefault('official_news',{});self.busy=set();self.sources=get_sources(owner.data)
        self.bridge=NewsSignals(self);self.bridge.result.connect(self.received)
        v=QVBoxLayout(self);v.setContentsMargins(22,16,22,16);v.setSpacing(12)
        toolbar=QFrame();toolbar.setObjectName('NewsToolbar');tb=QVBoxLayout(toolbar);tb.setContentsMargins(16,12,16,12);tb.setSpacing(8)
        top_row=QHBoxLayout();title=text('خبرها و اطلاعیه‌های مالیات و بیمه');title.setObjectName('Hero');top_row.addWidget(title,1)
        self.enabled=QCheckBox('بررسی خودکار هنگام اجرای برنامه و اتصال اینترنت');self.enabled.setChecked(owner.data['settings'].get('news_enabled',True));self.enabled.hide();self.enabled.toggled.connect(self.toggle);top_row.addWidget(self.enabled)
        self.check=button('بروزرسانی',lambda:self.refresh_sources(force=True));self.check.hide();top_row.addWidget(self.check)
        read_btn=button('همه خوانده شد',self.read_all);top_row.addWidget(read_btn);tb.addLayout(top_row)
        filters=QHBoxLayout();filters.setSpacing(8);self.source_filter=QComboBox();self.source_filter.addItem('همه منابع',None)
        for source in self.sources:self.source_filter.addItem(source['name'],source['id'])
        filters.addWidget(self.source_filter)
        self.unread=QCheckBox('فقط خوانده‌نشده');filters.addWidget(self.unread);self.query=QLineEdit();self.query.setPlaceholderText('جست‌وجو در خبرها، هشتگ یا عنوان…');self.query.setClearButtonEnabled(True);filters.addWidget(self.query,1);tb.addLayout(filters)
        self.status=text('');self.status.setObjectName('Sub');tb.addWidget(self.status);v.addWidget(toolbar)
        self.source_filter.currentIndexChanged.connect(self.render);self.unread.toggled.connect(self.render);self.query.textChanged.connect(self.render)
        self.source_labels={}
        self.source_host=QWidget(self);self.source_area=QVBoxLayout(self.source_host);self.source_host.hide()
        for source in self.sources:
            r=QHBoxLayout();l=text('');self.source_labels[source['id']]=l;r.addWidget(l,1);self.source_area.addLayout(r)
        area=QScrollArea();area.setWidgetResizable(True);shell=QWidget();self.items_layout=QVBoxLayout(shell);self.items_layout.setContentsMargins(2,2,2,2);self.items_layout.setSpacing(10);self.items_layout.setAlignment(Qt.AlignTop);area.setWidget(shell);v.addWidget(area,1)
        self.timer=QTimer(self);self.timer.setInterval(60_000);self.timer.timeout.connect(self.auto_refresh);self.timer.start()
        self.render();QTimer.singleShot(2500,self.auto_refresh)

    def reload_sources(self):
        self.sources=get_sources(self.owner.data)
        self.source_filter.blockSignals(True);self.source_filter.clear();self.source_filter.addItem('همه منابع',None)
        for source in self.sources:self.source_filter.addItem(source['name'],source['id'])
        self.source_filter.blockSignals(False)
        def clear(layout):
            while layout.count():
                item=layout.takeAt(0)
                if item.widget():item.widget().hide();item.widget().deleteLater()
                elif item.layout():clear(item.layout())
        clear(self.source_area);self.source_labels={}
        for source in self.sources:
            row=QHBoxLayout();l=text('');self.source_labels[source['id']]=l;row.addWidget(l,1);self.source_area.addLayout(row)
        self.enabled.blockSignals(True);self.enabled.setChecked(self.owner.data['settings']['news_enabled']);self.enabled.blockSignals(False);self.render()

    def toggle(self,value):
        self.owner.data['settings']['news_enabled']=value;self.owner.persist()

    def auto_refresh(self):
        if prune_news(self.state):self.owner.persist();self.render()
        if self.enabled.isChecked():self.refresh_sources()

    def refresh_sources(self,force=False):
        now=datetime.now(timezone.utc)
        for source in self.sources:
            if not source.get('enabled',True):continue
            if source['id'] in self.busy:continue
            previous=self.state.get('sources',{}).get(source['id'],{})
            try:
                age=(now-datetime.fromisoformat(previous['checked_at'])).total_seconds()
                if not force and age < (self.owner.data['settings'].get('news_interval',60)*60 if previous.get('ok') else 300):continue
            except (KeyError,ValueError,TypeError):pass
            self.busy.add(source['id'])
            def run(s=dict(source,_proxy=self.owner.data['settings'].get('news_proxy','')),bridge=self.bridge):
                result=fetch_source(s)
                try:bridge.result.emit(result)
                except RuntimeError:pass
            threading.Thread(target=run,daemon=True).start()
        self.check.setEnabled(not self.busy);self.status.setText('در حال بررسی منابع…' if self.busy else 'زمان بررسی بعدی هنوز نرسیده است.')

    def received(self,result):
        self.busy.discard(result['source_id']);fresh=merge_news(self.state,result);self.owner.persist();self.render()
        self.check.setEnabled(not self.busy)
        self.status.setText('در حال بررسی منبع دیگر…' if self.busy else 'بروزرسانی پایان یافت.')
        # News updates stay inside the app; desktop popups follow reminder dates only.

    def read_all(self):
        for item in self.state.get('items',[]):item['read']=True
        self.owner.persist();self.render()

    def open_item(self,item):
        if open_official(item['url']):item['read']=True;self.owner.persist();self.render()

    def add_reminder(self,item):
        from ui_permissions import gate
        if not gate(self.owner,'calendar','create'):return
        from app import EventDialog
        payload=dict(company=self.owner.data['companies'][0],title=item['title'],date_jalali=jformat(today_j()),notes='منبع خبر: '+item['url']+'\nتاریخ موعد را از متن خبر بررسی و سپس ثبت کنید.',priority='مهم',recurrence='بدون تکرار',reminder_group='personal',reminder_custom=False,lead_days=self.owner.data['settings']['personal_lead_days'])
        dialog=EventDialog(self.owner,self.owner.data['companies'],item=payload)
        # No deadline is inferred from a headline or receipt date.
        dialog.when.clear();dialog.when.setPlaceholderText('موعد معتبر را از متن منبع وارد کنید')
        if dialog.exec():
            p=dialog.payload;ev=new_event(p['company'],p['title'],p['date_jalali'],p['notes'],p['priority'],p['recurrence'],p['lead_days']);ev.update(official_source=item['url'],category=p['category'],reminder_group=p['reminder_group'],reminder_custom=p['reminder_custom']);self.owner.events.append(ev)
            if p['company'] not in self.owner.data['companies']:self.owner.data['companies'].append(p['company']);self.owner.update_companies()
            self.owner.persist();self.owner.refresh();QMessageBox.information(self,'ثبت شد','یادآور در تقویم ثبت شد. برای تمدید یک تکلیف قبلی، تاریخ همان رویداد را در تقویم ویرایش کنید.')

    def render(self,*_):
        prune_news(self.state)
        for source in self.sources:
            s=self.state.get('sources',{}).get(source['id'],{})
            self.source_labels[source['id']].setText(source['name']+' | '+('غیرفعال' if not source.get('enabled',True) else 'دریافت موفق' if s.get('ok') else 'نیازمند بررسی اتصال / منبع')+' | آخرین تلاش: '+display_stamp(s.get('checked_at'))+'\n'+s.get('message','')+'\nآخرین دریافت موفق: '+display_stamp(s.get('last_success')))
        while self.items_layout.count():
            w=self.items_layout.takeAt(0).widget()
            if w:w.hide();w.deleteLater()
        items=sorted(self.state.get('items',[]),key=lambda item:parse_publication(item.get('published_at') or item.get('published','')),reverse=True);selected=self.source_filter.currentData();query=self.query.text().strip()
        count=0
        prefs=self.owner.data.get('preferences',{});terms=[t.strip().lstrip('#').replace('_',' ') for t in prefs.get('news_terms','').replace('،',',').replace('\n',',').split(',') if t.strip()];allowed=prefs.get('news_source_ids')
        for item in items:
            if item['source_id'] not in {s['id'] for s in self.sources}:continue
            if selected and item['source_id']!=selected:continue
            if self.unread.isChecked() and item.get('read'):continue
            haystack=(item['title']+' '+item.get('url','')+' '+item.get('summary','')).replace('ي','ی').replace('ك','ک').replace('_',' ').lower()
            if query and query.lower().lstrip('#').replace('_',' ') not in haystack:continue
            if allowed is not None and item['source_id'] not in allowed:continue
            if terms and not any(t.lower() in haystack for t in terms):continue
            count+=1;card=QFrame();card.setObjectName('NewsCard');c=QVBoxLayout(card);c.setContentsMargins(16,13,16,13);c.setSpacing(6)
            published=parse_publication(item.get('published_at') or item.get('published',''))
            publication_text=jformat(jdatetime.date.fromgregorian(date=published.astimezone(TEHRAN).date())) if published else ''
            heading=text(('● ' if not item.get('read') else '')+item['title']);heading.setStyleSheet('font-weight:bold;font-size:14px;background:transparent;');c.addWidget(heading);meta=text(item['source']+' · '+publication_text);meta.setObjectName('Sub');c.addWidget(meta)
            actions=QHBoxLayout();actions.setSpacing(8);read_btn=button('خواندن خبر',lambda checked=False,it=item:self.open_item(it));read_btn.setObjectName('Primary');actions.addWidget(read_btn);actions.addWidget(button('یادآور',lambda checked=False,it=item:self.add_reminder(it)));actions.addWidget(button('پیشنهاد تغییر موعد',lambda checked=False,it=item:self.propose_deadline(it)));actions.addStretch()
            c.addLayout(actions);self.items_layout.addWidget(card)
        if not count:self.items_layout.addWidget(text('خبری برای این انتخاب در ۱۴ روز اخیر موجود نیست.'))
        index=self.owner.tabs.indexOf(self)
        if index>=0:self.owner.tabs.setTabText(index,'خبرها')
        if hasattr(self.owner,'news_button'):self.owner.news_button.setText('خبرها')
        if hasattr(self.owner,'sidebar'):self.owner.sidebar.apply()

    def propose_deadline(self,item):
        from ui_permissions import gate
        if not gate(self.owner,'news','propose'):return
        from org_ui import RecordDialog
        from PySide6.QtWidgets import QDialog
        panel=self.owner.org;dialog=RecordDialog(panel,'proposal');dialog.widgets['title'][0].setText(item['title']);dialog.widgets['source'][0].setText(item['url']);dialog.widgets['published'][0].setText(item.get('published_at',''))
        if dialog.exec()==QDialog.Accepted:panel.save_dialog(dialog)
