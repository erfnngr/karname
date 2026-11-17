import math
from datetime import date
import jdatetime
from PySide6.QtCore import Qt,QSize,QRectF
from PySide6.QtGui import QPixmap,QPainter,QColor,QLinearGradient,QPen,QIcon
from PySide6.QtWidgets import (QWidget,QFrame,QLabel,QVBoxLayout,QHBoxLayout,QGridLayout,QPushButton,QCheckBox,QScrollArea,QTabWidget,QDialog,QLineEdit)
from storage import package_file,fa,MONTHS,jformat,today_j,due_on
from brand import logo,company_brand,event_type,row_colors

def text(value,name=None):
    w=QLabel(value);w.setTextFormat(Qt.PlainText);w.setWordWrap(True)
    if name:w.setObjectName(name)
    return w

class WatermarkPanel(QFrame):
    def __init__(self,color,company=None,parent=None):
        super().__init__(parent);self.color=QColor(color)
        from brand import company_pixmap
        self.mark=company_pixmap(company);self.setObjectName('WatermarkPanel')
    def paintEvent(self,e):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(Qt.NoPen);p.setBrush(self.color);p.drawRoundedRect(QRectF(self.rect()),16,16)
        if not self.mark.isNull():
            p.save();p.setOpacity(.15);p.setCompositionMode(QPainter.CompositionMode_Multiply)
            pix=self.mark.scaled(int(self.width()*.62),int(self.height()*.9),Qt.KeepAspectRatio,Qt.SmoothTransformation)
            p.drawPixmap(self.width()-pix.width()-12,(self.height()-pix.height())//2,pix);p.restore()

class HomePanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.setLayoutDirection(Qt.LeftToRight);self.owner=owner;self.mark=QPixmap(str(package_file('assets/karname.png')))
        from weather import WeatherService
        self.weather_service=WeatherService(self)
        outer=QVBoxLayout(self);outer.setContentsMargins(25,24,25,20);row=QHBoxLayout();outer.addLayout(row,1);row.setDirection(QHBoxLayout.LeftToRight);row.setContentsMargins(7,11,7,11)
        self.side=QFrame();self.side.setFixedWidth(270);self.side.setLayoutDirection(Qt.RightToLeft);v=QVBoxLayout(self.side);v.setContentsMargins(24,25,24,25);v.setSpacing(15)
        self.day=text('','Hero');self.tasks=text('');self.occasions=text('');v.addWidget(text('امروز'));v.addWidget(self.day);v.addWidget(self.tasks);v.addWidget(self.occasions);v.addStretch();row.addWidget(self.side);row.addStretch(1)
        from weather_ui import WeatherWidget
        self.weather=WeatherWidget(owner,self.weather_service,self);self.weather.setMaximumWidth(390);row.addWidget(self.weather,0,Qt.AlignRight)
        self.quote_panel=QFrame();self.quote_panel.setLayoutDirection(Qt.RightToLeft);q=QVBoxLayout(self.quote_panel);q.setContentsMargins(20,10,20,10);q.setSpacing(4)
        self.quote_text=text('');self.quote_text.setAlignment(Qt.AlignCenter);self.quote_text.setTextInteractionFlags(Qt.TextSelectableByMouse);q.addWidget(self.quote_text)
        caption=QHBoxLayout();self.quote_author=text('');self.quote_author.setAlignment(Qt.AlignCenter);caption.addStretch();caption.addWidget(self.quote_author);self.quote_source=QPushButton('↗');self.quote_source.setToolTip('منبع سخن روز');self.quote_source.setAccessibleName('باز کردن منبع سخن روز');self.quote_source.setFixedSize(30,28);self.quote_source.clicked.connect(self.open_quote_source);caption.addWidget(self.quote_source);caption.addStretch();q.addLayout(caption);outer.addWidget(self.quote_panel);self.current_quote=None
        self.activity_label=text('');self.activity_label.setStyleSheet('font-size:11px;');v.insertWidget(v.count()-1,self.activity_label);self.activity_button=QPushButton('امروز من');self.activity_button.clicked.connect(lambda:(owner.tabs.setCurrentWidget(owner.workspace),owner.workspace.view.setCurrentIndex(2)));v.insertWidget(v.count()-1,self.activity_button)
    def _react_home_active(self):
        stack=getattr(self,'_react_stack',None);rv=getattr(self,'react_view',None)
        return stack is not None and rv is not None and stack.currentWidget() is rv
    def resizeEvent(self,e):
        super().resizeEvent(e)
        if hasattr(self,'theme_dashboard'):self.theme_dashboard.setGeometry(self.rect())
        if hasattr(self,'home_editor'):self.home_editor.setGeometry(self.rect());self.home_editor.raise_()
    def edit_layout(self):
        from ui_permissions import gate
        if not gate(self.owner,'settings','edit'):return
        stack=getattr(self,'_react_stack',None)
        if not hasattr(self,'home_editor'):
            from home_editor import HomeLayoutEditor
            self.home_editor=HomeLayoutEditor(self.owner,self)
            if stack is not None:stack.addWidget(self.home_editor)
        elif stack is not None and stack.indexOf(self.home_editor)==-1:
            stack.addWidget(self.home_editor)
        self.home_editor.setGeometry(self.rect());self.home_editor.begin()
        if stack is not None:stack.setCurrentWidget(self.home_editor)
        self.home_editor.raise_()
    def paintEvent(self,e):
        from appearance import palette_for
        s=self.owner.data['settings'];dark=s.get('theme')=='dark';background=palette_for(s)['bg'] if dark or s.get('theme_preset','default')!='default' else '#FFFFFF'
        p=QPainter(self);p.fillRect(self.rect(),QColor(background))
        if dark and not hasattr(self,'mark_dark'):
            from brand import dark_variant
            self.mark_dark=dark_variant(self.mark)
        mark=self.mark_dark if dark else self.mark
        weather_width=self.weather.width()+24 if self.weather.isVisible() else 0
        width=max(0,self.width()-345-weather_width);height=max(100,self.height()-150)
        if width>40:
            pix=mark.scaled(width-20,height,Qt.KeepAspectRatio,Qt.SmoothTransformation);p.drawPixmap(320+(width-pix.width())//2,(height-pix.height())//2+15,pix)
    def refresh(self):
        from theme_catalog import preset
        s=self.owner.data['settings']
        self.weather.setVisible(s.get('weather_enabled',True));self.weather_service.configure(s.get('weather_enabled',True),s.get('weather_api_base') or self.weather_service.default_base_url)
        prefs=self.owner.data.get('preferences',{});custom_default=prefs.get('home_custom_on_default') and isinstance(prefs.get('home_widgets'),list)
        if self._react_home_active():
            if hasattr(self,'theme_dashboard'):self.theme_dashboard.hide()
        elif preset(s.get('theme_preset','default'))!='default' or custom_default:
            if not hasattr(self,'theme_dashboard'):
                from theme_dashboard import ThemeDashboard
                self.theme_dashboard=ThemeDashboard(self.owner,self)
            self.theme_dashboard.setGeometry(self.rect());self.theme_dashboard.refresh()
        elif hasattr(self,'theme_dashboard'):self.theme_dashboard.hide()
        bg=QColor(s['home_panel_color']);alpha=s['home_panel_opacity']/100
        bg=QColor(round(255*(1-alpha)+bg.red()*alpha),round(255*(1-alpha)+bg.green()*alpha),round(255*(1-alpha)+bg.blue()*alpha)).name();fg=s['home_text_color']
        self.side.setStyleSheet(f'QFrame{{background:{bg};border-radius:18px;}} QLabel{{background:transparent;color:{fg};}} QLabel#Hero{{color:{fg};font-size:23px;font-weight:bold;}}')
        self.quote_panel.setStyleSheet(f'QFrame{{background:{bg};border-radius:14px;}} QLabel{{background:transparent;color:{fg};}} QPushButton{{background:transparent;color:{fg};border:none;padding:0;}}')
        self.update();self.refresh_quote()
        today=today_j();self.day.setText(jformat(today)+'\n'+date.today().isoformat())
        from ui_permissions import allowed
        due=[e for e in self.owner.display_events() if due_on(e,date.today())] if allowed(self.owner,'calendar') else []
        self.tasks.setText('یادآورهای امروز\n'+('\n'.join('• '+e['title'] for e in due[:3]) if due else 'یادآوری برای امروز ثبت نشده است.')+('\n+'+fa(len(due)-3)+' مورد دیگر' if len(due)>3 else ''))
        from occasions import on_date
        occasions=on_date(date.today());self.occasions.setText('مناسبت امروز\n'+('\n'.join('• '+x['title'] for x in occasions[:3]) if occasions else 'مناسبتی در فهرست ثبت نشده است.'))
        if self._react_home_active():self.react_view.bridge.publish()

    def refresh_activity(self,snapshot):
        from ui_permissions import allowed
        self.activity_button.setVisible(allowed(self.owner,'workspace'))
        if not allowed(self.owner,'workspace'):self.activity_label.clear();return
        tasks=snapshot.get('tasks',[]);overdue=sum(t.get('overdue',False) and t.get('mine',False) for t in tasks);review=sum(t.get('review',False) for t in tasks);requests=sum(r.get('can_review',False) for r in snapshot.get('requests',[]));meetings=snapshot.get('meetings',[])
        self.activity_label.setText('معوق من: '+fa(overdue)+'  ·  تأیید کار: '+fa(review)+'\nدرخواست منتظر من: '+fa(requests)+('\nجلسه بعدی: '+meetings[0]['title'][:40] if meetings else ''))
        if hasattr(self,'theme_dashboard') and self.theme_dashboard.isVisible():self.theme_dashboard.refresh()
        if self._react_home_active():self.react_view.bridge.publish()

    def refresh_quote(self):
        self.quote_panel.setVisible(self.owner.data['settings'].get('daily_quote_enabled',True))
        from quotes import daily_quote
        item=daily_quote()
        if item!=self.current_quote:
            self.current_quote=item;self.quote_text.setText(item['text']);self.quote_author.setText(item['author']+' · '+item['work']);self.quote_author.setStyleSheet('font-size:11px;');self.quote_source.setToolTip('منبع: '+item['author']+'، '+item['work']+'، '+item['section'])
    def open_quote_source(self):
        if self.current_quote:
            from features_ui import open_official
            open_official(self.current_quote['source'])

class CompactRow(QFrame):
    def __init__(self,owner,event,reference_date=None):
        super().__init__();self.owner=owner;self.item=event;self.setObjectName('TaskRow');bg,fg,accent=row_colors(event,owner.data['settings'])
        self.reference_date=reference_date or owner.event_reference_date(event)
        self.setStyleSheet(f'QFrame#TaskRow{{background:{bg};border:1px solid {accent};border-radius:10px;}} QFrame#TaskRow QLabel{{background:transparent;color:{fg};}} QFrame#TaskRow QPushButton{{background:transparent;color:{fg};padding:4px 8px;border:none;}} QFrame#TaskRow QCheckBox{{background:transparent;}}')
        row=QHBoxLayout(self);row.setContentsMargins(11,9,11,9);row.setSpacing(9)
        from ui_permissions import allowed
        done=QCheckBox();done.setAccessibleName('انجام شد');done.setChecked(bool(event.get('done') or (self.reference_date and self.reference_date.isoformat() in event.get('completed_occurrences',[]))));done.setEnabled(allowed(owner,'calendar','edit'));done.toggled.connect(lambda value:owner.set_done(event,value,when=self.reference_date));row.addWidget(done)
        content=QVBoxLayout();content.setSpacing(3);title=text(event.get('title',''));title.setStyleSheet('font-weight:600;');content.addWidget(title)
        kind={'insurance':'بیمه','tax':'مالیات','personal':'شخصی'}[event_type(event)];company=event.get('company','شخصی');caption='یادداشت شخصی' if event.get('desk_note_id') else company+' · '+kind
        if event.get('planning_only'):caption+=' · برنامه‌ریزی'
        if event.get('needs_review'):caption+=' · بررسی تاریخ'
        dt=self.reference_date;when=jformat(jdatetime.date.fromgregorian(date=dt)) if dt else 'تاریخ نامشخص';caption+=' · '+when
        subtitle=text(caption);subtitle.setStyleSheet('font-size:11px;');content.addWidget(subtitle);row.addLayout(content,1)
        edit=QPushButton('ویرایش');edit.setAccessibleName('ویرایش '+event.get('title',''));edit.clicked.connect(lambda:owner.edit_event(event));row.addWidget(edit)
        self.setMinimumHeight(72)
    def mouseDoubleClickEvent(self,e):self.owner.drawer.show_event(self.item)

class MonthOverview(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;v=QVBoxLayout(self);v.setContentsMargins(25,16,25,18);v.setSpacing(12)
        top=QHBoxLayout();self.heading=text('','Hero');top.addWidget(self.heading);top.addStretch();add=QPushButton('＋ یادآور');add.clicked.connect(owner.add_event);top.addWidget(add);v.addLayout(top)
        self.sections=QTabWidget();self.sections.setDocumentMode(True);v.addWidget(self.sections,1);self.views={};self._section_names=None;self.sync_sections()

    def sync_sections(self):
        from brand import company_group,company_order
        companies=sorted(dict.fromkeys(name for name in self.owner.data['companies']+[e.get('company') for e in self.owner.display_events()] if company_group(name)),key=company_order)
        names=[('همه اعلان‌ها',None)]+[(name,name) for name in companies]+[('شخصی','__personal__')]
        dark=self.owner.data['settings'].get('theme')=='dark'
        if names==self._section_names and getattr(self,'_brand_dark',None)==dark:return
        self._brand_dark=dark
        selected=self.sections.currentWidget().property('company_key') if self.sections.currentWidget() else None
        while self.sections.count():
            widget=self.sections.widget(0);self.sections.removeTab(0);widget.deleteLater()
        self.views={};self._section_names=names
        for name,key in names:
            shell=QWidget();shell.setProperty('company_key',key);layout=QVBoxLayout(shell);area=QScrollArea();area.setWidgetResizable(True);body=QWidget();grid=QGridLayout(body);grid.setAlignment(Qt.AlignTop);grid.setSpacing(12);area.setWidget(body);layout.addWidget(area);self.sections.addTab(shell,name);self.views[key]=grid
            if key==selected:self.sections.setCurrentWidget(shell)
            brand=company_brand(key)
            if brand:
                from brand import company_pixmap
                self.sections.setTabIcon(self.sections.count()-1,QIcon(company_pixmap(key,dark)))
        self.sections.setIconSize(QSize(25,25))
    def refresh(self):
        from brand import company_group
        self.sync_sections();current=today_j();self.heading.setText('ماه جاری  ·  '+MONTHS[current.month-1]+' '+fa(current.year));groups={name:[] for name in self.views if name is not None}
        for ev in self.owner.display_events():
            dt=self.owner.event_reference_date(ev)
            if not dt or ev.get('done'):continue
            jd=jdatetime.date.fromgregorian(date=dt)
            if (jd.year,jd.month)!=(current.year,current.month):continue
            group=company_group(ev.get('company')) or '__personal__';groups.setdefault(group,[]).append((dt,ev))
        for key,grid in self.views.items():
            while grid.count():
                w=grid.takeAt(0).widget()
                if w:w.hide();w.deleteLater()
            selected=list(groups) if key is None else [key];column=0
            for group in selected:
                values=groups.get(group,[])
                if key is None and group=='__personal__' and not values:continue
                pane=QFrame();pane.setObjectName('Panel');lay=QVBoxLayout(pane);lay.setContentsMargins(13,12,13,12);lay.setSpacing(8)
                h=QHBoxLayout();h.addWidget(logo(group,36));h.addWidget(text(('یادآورهای شخصی' if group=='__personal__' else group)+'  ·  '+fa(len(values))));h.addStretch();lay.addLayout(h)
                if not values:lay.addWidget(text('یادآور فعالی در ماه جاری نیست.','Sub'))
                for dt,event in sorted(values,key=lambda x:x[0]):lay.addWidget(CompactRow(self.owner,event,dt))
                grid.addWidget(pane,column//2,column%2 if key is None else 0,Qt.AlignTop);column+=1
            for col in range(2 if key is None else 1):grid.setColumnStretch(col,1)

class QuickPicker(QDialog):
    def __init__(self,owner,kind):
        super().__init__(owner);self.kind=kind;self.owner=owner;self.start=max(1300,min(1491,owner.year));self.value=None;self.setWindowTitle('انتخاب سال' if kind=='year' else 'انتخاب ماه');self.setMinimumWidth(340)
        outer=QVBoxLayout(self);nav=QHBoxLayout();prev=QPushButton('‹');next_b=QPushButton('›');prev.clicked.connect(lambda:self.page(-9));next_b.clicked.connect(lambda:self.page(9));self.title=text('سال' if kind=='year' else 'ماه');nav.addWidget(prev);nav.addWidget(self.title,1);nav.addWidget(next_b);outer.addLayout(nav)
        prev.setVisible(kind=='year');next_b.setVisible(kind=='year');self.grid=QGridLayout();outer.addLayout(self.grid);self.draw()
    def page(self,delta):self.start=max(1300,min(1491,self.start+delta));self.draw()
    def draw(self):
        while self.grid.count():
            w=self.grid.takeAt(0).widget()
            if w:w.hide();w.deleteLater()
        values=range(self.start,min(self.start+9,1500)) if self.kind=='year' else range(1,13)
        for ix,value in enumerate(values):
            b=QPushButton(fa(value) if self.kind=='year' else MONTHS[value-1]);b.setMinimumHeight(48);b.clicked.connect(lambda checked=False,v=value:self.choose(v));self.grid.addWidget(b,ix//3,ix%3)
    def choose(self,value):self.value=value;self.accept()
