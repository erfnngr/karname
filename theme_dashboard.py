"""Three distinct, interactive dashboards based on the approved references."""
from datetime import date
import jdatetime
from PySide6.QtCore import Qt,QPoint,QPointF,QRectF,QVariantAnimation,QEasingCurve
from PySide6.QtGui import QColor,QPainter,QPen,QLinearGradient,QPainterPath,QBrush,QPolygonF,QPixmap
from PySide6.QtWidgets import QWidget,QFrame,QLabel,QPushButton,QGridLayout,QHBoxLayout,QVBoxLayout,QBoxLayout,QSizePolicy,QCheckBox,QLineEdit
from storage import MONTHS,WEEKDAYS,fa,today_j,month_last_day,due_on,next_month
from appearance import palette_for,accent_foreground
from ui_permissions import allowed
from brand import logo

LAYOUTS={'emerald_ivory':'reference_1','glass_mist':'reference_2','violet_modular':'reference_3','bento_grid':'reference_bento'}

def label(value,role='',limit=40):
    full=str(value);w=QLabel(full if len(full)<=limit else full[:limit-1]+'…');w.setToolTip(full);w.setTextFormat(Qt.PlainText);w.setWordWrap(False)
    if role:w.setObjectName(role)
    return w

def clear(layout):
    while layout.count():
        item=layout.takeAt(0)
        if item.widget():item.widget().hide();item.widget().deleteLater()
        elif item.layout():clear(item.layout())

class AttendanceChart(QWidget):
    def __init__(self,owner,style):
        super().__init__();self.owner=owner;self.chart_style=style;self.setMinimumHeight(65);self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding);self.setAccessibleName('نمودار ساعت کار ثبت‌شده')
    def paintEvent(self,event):
        c=palette_for(self.owner.data['settings']);p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);w=self.width();h=self.height();left=22;right=max(left+1,w-9);top=9;bottom=max(top+1,h-23)
        p.setPen(QPen(QColor(c['border']),1))
        for i in range(4):y=top+(bottom-top)*i/3;p.drawLine(QPointF(left,y),QPointF(right,y))
        report=getattr(getattr(self.owner,'attendance',None),'report',None);days=(report or {}).get('days',[]) if allowed(self.owner,'attendance') else []
        rows=[x for x in days if x.get('entries')][-7:]
        if not rows:
            p.setPen(QColor(c['muted']));message=p.fontMetrics().elidedText('تردد ثبت‌شده‌ای برای نمودار انتخاب نشده است',Qt.ElideRight,max(20,w-14));p.drawText(self.rect(),Qt.AlignCenter,message);return
        vals=[max(0,float(x.get('worked_minutes') or 0)/60) for x in rows];mx=max(1,max(vals));space=(right-left)/max(1,len(vals)-1)
        if self.chart_style=='bars':
            p.setPen(Qt.NoPen);p.setBrush(QColor(c['accent']))
            for i,value in enumerate(vals):
                bar=(right-left)/len(vals);height=(bottom-top)*value/mx;p.drawRoundedRect(QRectF(left+i*bar+bar*.25,bottom-height,max(3,bar*.5),height),3,3)
        else:
            points=[QPointF(left+i*space,bottom-(bottom-top)*v/mx) for i,v in enumerate(vals)];p.setPen(QPen(QColor(c['accent']),2));p.drawPolyline(QPolygonF(points))
            p.setBrush(QColor(c['panel']))
            for point in points:p.drawEllipse(point,3,3)
        p.setPen(QColor(c['muted']));p.drawText(QRectF(left,bottom+2,right-left,18),Qt.AlignRight|Qt.AlignVCenter,'روزهای دارای تردد ثبت‌شده')

class ProgressChart(QWidget):
    def __init__(self,owner,done,total):super().__init__();self.owner=owner;self.done=done;self.total=total;self.setMinimumSize(70,70);self.setMaximumSize(130,130);self.setAccessibleName('پیشرفت کارها')
    def paintEvent(self,event):
        c=palette_for(self.owner.data['settings']);p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);s=max(20,min(self.width(),self.height())-18);r=QRectF((self.width()-s)/2,(self.height()-s)/2,s,s);p.setPen(QPen(QColor(c['border']),9));p.drawEllipse(r);p.setPen(QPen(QColor(c['accent']),9,Qt.SolidLine,Qt.RoundCap));p.drawArc(r,90*16,-int(360*16*self.done/max(1,self.total)));p.setPen(QColor(c['text']));p.drawText(r,Qt.AlignCenter,fa(round(100*self.done/self.total))+'٪' if self.total else '—')

class GlassCard(QFrame):
    """Paint the blurred sea beneath this card, then its glass highlights."""
    def __init__(self,board):
        super().__init__();self.board=board;self.setObjectName('DashboardCard')
    def paintEvent(self,event):
        from theme_catalog import preset
        if preset(self.board.owner.data['settings'].get('theme_preset','default'))=='default':
            c=palette_for(self.board.owner.data['settings']);p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(QColor(c['border']),1));p.setBrush(QColor(c['panel']));p.drawRoundedRect(QRectF(self.rect()).adjusted(.5,.5,-.5,-.5),12,12);return
        self.board.prepare_backdrop();p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        rect=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5);path=QPainterPath();path.addRoundedRect(rect,15,15);p.setClipPath(path)
        pos=self.mapTo(self.board,QPoint(0,0));source=QRectF(pos.x(),pos.y(),self.width(),self.height())
        p.drawPixmap(QRectF(self.rect()),self.board._blurred_background,source)
        dark=self.board.owner.data['settings'].get('theme')=='dark'
        face=QLinearGradient(0,0,0,self.height());face.setColorAt(0,QColor(12,38,53,160) if dark else QColor(249,253,255,170));face.setColorAt(1,QColor(8,31,45,175) if dark else QColor(236,247,252,155));p.fillRect(self.rect(),face)
        p.save();p.setOpacity(.12);p.drawPixmap(self.board._mark_x-pos.x(),self.board._mark_y-pos.y(),self.board._mark);p.restore()
        p.setClipping(False);p.setPen(QPen(QColor(255,255,255,100 if dark else 165),1));p.setBrush(Qt.NoBrush);p.drawPath(path)
        p.setPen(QPen(QColor(255,255,255,28 if dark else 55),2));p.drawRoundedRect(rect.adjusted(2,2,-2,-2),13,13)

class DashboardDay(QPushButton):
    """Keep Qt's themed text intact while gently highlighting the cell edge."""
    def __init__(self,text,color):
        super().__init__(text);self.setProperty('flowNative',True);self.accent=QColor(color)
        self.motion=QVariantAnimation(self);self.motion.setDuration(160);self.motion.setEasingCurve(QEasingCurve.OutCubic);self.motion.valueChanged.connect(self.update)
    def animate(self,value):
        current=self.motion.currentValue();self.motion.stop();self.motion.setStartValue(float(current or 0));self.motion.setEndValue(value);self.motion.start()
    def enterEvent(self,event):super().enterEvent(event);self.animate(1.0)
    def leaveEvent(self,event):super().leaveEvent(event);self.animate(0.0)
    def paintEvent(self,event):
        super().paintEvent(event);amount=float(self.motion.currentValue() or 0)
        if amount<=0:return
        painter=QPainter(self);painter.setRenderHint(QPainter.Antialiasing);color=QColor(self.accent);color.setAlpha(round(150*amount));painter.setPen(QPen(color,1.2));painter.setBrush(Qt.NoBrush);painter.drawRoundedRect(QRectF(self.rect()).adjusted(1,1,-1,-1),7,7)

class ThemeDashboard(QWidget):
    def __init__(self,owner,parent):
        super().__init__(parent);self.owner=owner;self.setObjectName('ThemeDashboard');self.setLayoutDirection(Qt.LeftToRight);self.view_year=None;self.view_month=None
        self._compact_height=None;self.root=QVBoxLayout(self);self.root.setContentsMargins(16,10,16,9);self.root.setSpacing(8)
    def resizeEvent(self,event):
        super().resizeEvent(event);compact=self.height()<490
        if self._compact_height is not None and compact!=self._compact_height:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0,self.refresh)
        self._compact_height=compact
    def prepare_backdrop(self):
        from storage import package_file
        from brand import dark_variant
        from theme_catalog import preset
        settings=self.owner.data['settings'];dark=settings.get('theme')=='dark';theme_key=preset(settings.get('theme_preset','default'));default=theme_key=='default';key=(self.width(),self.height(),dark,theme_key)
        if getattr(self,'_backdrop_key',None)==key:return
        self._backdrop_key=key;self._sea_background=QPixmap(max(1,self.width()),max(1,self.height()));p=QPainter(self._sea_background);p.setRenderHint(QPainter.Antialiasing)
        if not hasattr(self,'ocean'):self.ocean=QPixmap(str(package_file('assets/ocean.png')))
        if default:p.fillRect(self.rect(),QColor(palette_for(settings)['bg']))
        elif not self.ocean.isNull():p.drawPixmap(self.rect(),self.ocean,self.ocean.rect())
        else:p.fillRect(self.rect(),QColor('#12394D' if dark else '#C4DFE8'))
        if not default:
            tint=QColor(10,30,45,140) if dark and theme_key=='bento_grid' else QColor(14,22,42,145) if dark and theme_key=='violet_modular' else QColor(5,25,39,130) if dark else QColor(232,248,252,72) if theme_key=='bento_grid' else QColor(238,242,252,75) if theme_key=='violet_modular' else QColor(246,245,236,80) if theme_key=='emerald_ivory' else QColor(239,248,251,65)
            p.fillRect(self.rect(),tint)
        if not hasattr(self,'background_mark'):
            self.background_mark=dark_variant(QPixmap(str(package_file('assets/karname.png'))))
            self.background_mark_dark=QPixmap(self.background_mark.size());self.background_mark_dark.fill(Qt.transparent);ink=QPainter(self.background_mark_dark);ink.drawPixmap(0,0,self.background_mark);ink.setCompositionMode(QPainter.CompositionMode_SourceIn);ink.fillRect(self.background_mark_dark.rect(),QColor('#17445B'));ink.end()
        mark=(self.background_mark if dark else self.background_mark_dark).scaled(int(self.width()*.32),int(self.height()*.34),Qt.KeepAspectRatio,Qt.SmoothTransformation);self._mark=mark;self._mark_x=(self.width()-mark.width())//2;self._mark_y=(self.height()-mark.height())//2;p.setOpacity(.45 if dark else .4);p.drawPixmap(self._mark_x,self._mark_y,mark);p.end()
        tiny=self._sea_background.scaled(max(1,self.width()//24),max(1,self.height()//24),Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
        self._blurred_background=tiny.scaled(self.size(),Qt.IgnoreAspectRatio,Qt.SmoothTransformation)
    def paintEvent(self,event):
        self.prepare_backdrop();p=QPainter(self);p.drawPixmap(0,0,self._sea_background)
    def go(self,key):
        if allowed(self.owner,key) and key in self.owner.modules:self.owner.tabs.setCurrentWidget(self.owner.modules[key])
    def card(self,title,action=None,action_title=''):
        frame=GlassCard(self);frame.setLayoutDirection(Qt.RightToLeft);lay=QVBoxLayout(frame);lay.setContentsMargins(12,9,12,9);lay.setSpacing(6);head=QHBoxLayout();head.addWidget(label(title,'DashboardTitle'),1)
        if action:
            button=QPushButton(action_title or 'مشاهده');button.setObjectName('DashboardAction');button.clicked.connect(action);head.addWidget(button)
        lay.addLayout(head);return frame,lay
    def open_date(self,day):
        o=self.owner;o.year=day.year;o.month=day.month;o.selected_changed(day);self.go('calendar')
    def change_month(self,delta):self.view_year,self.view_month=next_month(self.view_year,self.view_month,delta);self.refresh()
    def calendar(self,variant,marked,compact=False):
        today=today_j();y=self.view_year or today.year;m=self.view_month or today.month;self.view_year=y;self.view_month=m
        frame=GlassCard(self);frame.setLayoutDirection(Qt.RightToLeft);v=QVBoxLayout(frame);v.setContentsMargins(12,9,12,9);v.setSpacing(3);head=QHBoxLayout();title=QPushButton(MONTHS[m-1]+' '+fa(y));title.setObjectName('CalendarTitle');title.setToolTip('باز کردن تقویم');title.clicked.connect(lambda:self.go('calendar'));head.addWidget(title,1)
        for sym,delta in [('›',1),('‹',-1)]:b=QPushButton(sym);b.setObjectName('CalendarArrow');b.setAccessibleName('ماه بعد' if delta==1 else 'ماه قبل');b.clicked.connect(lambda checked=False,d=delta:self.change_month(d));head.addWidget(b)
        v.addLayout(head);grid=QGridLayout();grid.setSpacing(0 if variant=='emerald_ivory' else 3);v.addLayout(grid,1)
        for i,name in enumerate(WEEKDAYS):
            x=label(name if variant=='emerald_ivory' and not compact else name[:1],'CalendarWeekday');x.setAlignment(Qt.AlignCenter);grid.addWidget(x,0,i)
        grid.setRowStretch(0,0)
        for r in range(1,7):grid.setRowStretch(r,1)
        first=jdatetime.date(y,m,1);offset=(first.togregorian().weekday()+2)%7
        for n in range(1,month_last_day(y,m)+1):
            d=jdatetime.date(y,m,n);value=fa(n)+(' ·' if d.togregorian() in marked else '');b=DashboardDay(value,palette_for(self.owner.data['settings'])['accent']);b.setObjectName('DashboardDay');b.setProperty('today',(d.year,d.month,d.day)==(today.year,today.month,today.day));b.setAccessibleName('باز کردن '+fa(n)+' '+MONTHS[m-1]);b.setMinimumHeight(19);b.setMinimumWidth(0);b.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding);b.clicked.connect(lambda checked=False,d=d:self.open_date(d))
            if variant!='emerald_ivory':b.setMaximumSize(34,34)
            grid.addWidget(b,1+(offset+n-1)//7,(offset+n-1)%7,Qt.AlignCenter if variant!='emerald_ivory' else Qt.Alignment())
        return frame
    def reminder_row(self,event):
        from brand import row_colors
        bg,fg,border=row_colors(event,self.owner.data['settings']);frame=QFrame();frame.setObjectName('ReminderRow');frame.setStyleSheet('QFrame#ReminderRow {background:'+bg+';border:0;border-radius:9px;} QFrame#ReminderRow QLabel {background:transparent;color:'+fg+';} QFrame#ReminderRow QPushButton {background:transparent;color:'+fg+';border:0;text-align:right;padding:1px;}')
        line=QHBoxLayout(frame);line.setContentsMargins(8,5,8,5);done=QCheckBox();done.setToolTip('انجام شد');done.setAccessibleName('انجام شد '+event.get('title',''));done.setEnabled(allowed(self.owner,'calendar','edit'));done.setChecked(bool(event.get('done') or date.today().isoformat() in event.get('completed_occurrences',[])));done.toggled.connect(lambda value:self.owner.set_done(event,value,when=date.today()));line.addWidget(done)
        col=QVBoxLayout();col.setSpacing(1);title=event.get('title','');button=QPushButton(title if len(title)<=32 else title[:31]+'…');button.setToolTip(title);button.clicked.connect(lambda:self.owner.edit_event(event));col.addWidget(button);col.addWidget(label(event.get('company','شخصی'),'DashboardMuted'));line.addLayout(col,1);return frame
    def reminders(self,events,limit=3,with_companies=False):
        frame,v=self.card('یادآورهای امروز',lambda:self.go('month'),'همه موارد');due=[e for e in events if not e.get('done') and due_on(e,date.today())]
        for e in due[:limit]:v.addWidget(self.reminder_row(e))
        if not due:v.addWidget(label('یادآوری برای امروز ثبت نشده است.','DashboardMuted'))
        if with_companies:
            v.addWidget(self.companies())
        v.addStretch();return frame
    def companies(self):
        frame,v=self.card('کارنامه',lambda:self.go('assistant'),'گفتگو')
        row=QHBoxLayout();row.addWidget(logo('کارنامه',32));field=QLineEdit(getattr(self.owner,'_home_ai_draft',''));field.setPlaceholderText('پیام…');field.textChanged.connect(lambda value:setattr(self.owner,'_home_ai_draft',value));row.addWidget(field,1);send=QPushButton('ارسال');send.setObjectName('Primary');send.setProperty('flowCompact',True)
        field.setEnabled(allowed(self.owner,'assistant','use'));send.setEnabled(allowed(self.owner,'assistant','use'))
        def submit():
            message=field.text().strip();assistant=getattr(self.owner,'ai',None)
            if not message or not assistant:return
            self.go('assistant');assistant.mode.setCurrentIndex(assistant.mode.findData('app'));assistant.prompt.setPlainText(message);assistant.send()
            if getattr(assistant,'busy',False):self.owner._home_ai_draft='';field.clear()
        send.clicked.connect(submit);field.returnPressed.connect(submit);row.addWidget(send);v.addLayout(row)
        v.addStretch();return frame
    def graph(self,style,replace_weather=True):
        if replace_weather and self.owner.data['settings'].get('weather_enabled',True):
            from weather_ui import WeatherWidget
            return WeatherWidget(self.owner,self.owner.home.weather_service,self)
        frame,v=self.card('ساعات کاری',lambda:self.go('attendance'),'گزارش');v.addWidget(AttendanceChart(self.owner,style),1);return frame
    def counts(self,today_only=False):
        tasks=getattr(getattr(self.owner,'workspace',None),'snapshot',{}).get('tasks',[]) if allowed(self.owner,'workspace') else []
        # Only count tasks with a due date in the current Jalali month.
        today=today_j();prefix=(f'{today.year:04d}/{today.month:02d}/{today.day:02d}' if today_only else f'{today.year:04d}/{today.month:02d}/')
        tasks=[t for t in tasks if str(t.get('payload',{}).get('due_date','')).replace('-','/').startswith(prefix)]
        done=sum(t.get('payload',{}).get('status') in ('completed','submitted') for t in tasks);pending=sum(t.get('payload',{}).get('status') not in ('completed','submitted','cancelled') for t in tasks)
        return done,pending
    def summary(self,progress=False):
        done,pending=self.counts(not progress);frame,v=self.card('پیشرفت کارهای ماه جاری' if progress else 'خلاصه امروز',lambda:self.go('workspace'),'کارها');row=QHBoxLayout()
        if progress:row.addWidget(ProgressChart(self.owner,done,done+pending),1)
        details=QVBoxLayout();details.addWidget(label('انجام شده   '+fa(done)));details.addWidget(label('در انتظار   '+fa(pending)));details.addStretch();row.addLayout(details,1);v.addLayout(row,1);return frame
    def glass_summary(self,events):
        done,pending=self.counts();due=sum(1 for e in events if not e.get('done') and due_on(e,date.today()));companies=len(self.owner.data.get('companies',[]));frame,v=self.card('خلاصه ماه جاری',lambda:self.go('workspace'),'کارها');grid=QGridLayout();grid.setSpacing(6)
        for i,(title,value) in enumerate([('کارهای انجام‌شده',done),('کارهای در انتظار',pending),('یادآورهای امروز',due),('شرکت‌ها',companies)]):
            tile=QFrame();tile.setObjectName('SummaryTile');layout=QVBoxLayout(tile);layout.setContentsMargins(9,6,9,6);layout.setSpacing(2);layout.addWidget(label(title,'DashboardMuted'));layout.addWidget(label(fa(value),'DashboardTitle'));grid.addWidget(tile,i//2,i%2)
        v.addLayout(grid,1);return frame
    def timeline(self,events):
        frame,v=self.card('برنامه کاری امروز',lambda:self.owner.add_event() if allowed(self.owner,'calendar','create') else None,'کار جدید +')
        due=[e for e in events if not e.get('done') and due_on(e,date.today())]
        for e in due[:7]:v.addWidget(self.reminder_row(e))
        if not due:v.addWidget(label('کاری برای امروز ثبت نشده است.','DashboardMuted'))
        v.addStretch();return frame
    def box(self):
        w=QWidget();w.setObjectName('DashboardColumn');w.setLayoutDirection(Qt.RightToLeft);v=QVBoxLayout(w);v.setContentsMargins(0,0,0,0);v.setSpacing(8);return w,v
    def quick_link(self,title,key):
        frame,layout=self.card(title,lambda:self.go(key),'باز کردن');layout.addStretch();return frame
    def today_card(self,events):
        from occasions import on_date
        today=today_j();frame,v=self.card('امروز',lambda:self.go('calendar'),'تقویم');v.addWidget(label(fa(today.day)+' '+MONTHS[today.month-1]+' '+fa(today.year),'DashboardTitle'))
        occasions=on_date(date.today());v.addWidget(label(occasions[0]['title'] if occasions else 'مناسبتی ثبت نشده است.','DashboardMuted',70))
        due=[e for e in events if not e.get('done') and due_on(e,date.today())]
        v.addWidget(label('یادآور امروز: '+(due[0]['title'] if due else 'موردی ثبت نشده است.'),'DashboardMuted',70));v.addStretch();return frame
    def quote_card(self):
        from quotes import daily_quote
        from features_ui import open_official
        q=daily_quote();frame,v=self.card('سخن روز',lambda:open_official(q['source']),'منبع');item=label('«'+q['text']+'»','DashboardTitle',140);item.setWordWrap(True);v.addWidget(item,1);v.addWidget(label(q['author'],'DashboardMuted'));return frame
    def widget_factories(self,key,events,marked):
        from weather_ui import WeatherWidget
        o=self.owner;s=o.data['settings'];widgets={'today':lambda:self.today_card(events),'calendar':lambda:self.calendar(key,marked,True),'reminders':lambda:self.reminders(events),'companies':self.companies,'attendance':lambda:self.graph('line',False),'summary':self.summary,'timeline':lambda:self.timeline(events)}
        for widget_key,title,target in [('quick_notes','یادداشت شخصی','desk'),('quick_customers','مشتریان','clients'),('quick_tasks','آخرین کارها','workspace')]:
            if allowed(o,target):widgets[widget_key]=lambda title=title,target=target:self.quick_link(title,target)
        if s.get('weather_enabled',True):widgets['weather']=lambda:WeatherWidget(o,o.home.weather_service,self)
        if s.get('daily_quote_enabled',True):widgets['quote']=self.quote_card
        return widgets
    def refresh(self):
        from theme_catalog import preset
        o=self.owner;s=o.data['settings'];key=preset(s.get('theme_preset','default'))
        if key not in LAYOUTS and key!='default':self.hide();return
        self.show();self.raise_();clear(self.root);c=palette_for(s);on=accent_foreground(c['accent']);radius=16 if key=='glass_mist' else 11 if key=='violet_modular' else 9
        self.setStyleSheet('''QWidget#ThemeDashboard,QWidget#DashboardColumn {background:transparent;}
          QFrame#DashboardCard {background:transparent;border:0;border-radius:%dpx;}
          QFrame#DashboardCard QLabel {background:transparent;color:%s;border:0;} QFrame#SummaryTile {background:%s;border:0;border-radius:9px;}
          QLabel#DashboardTitle {font-size:15px;font-weight:bold;} QLabel#DashboardMuted,QLabel#CalendarWeekday {color:%s;font-size:11px;}
          QLabel#Greeting {color:%s;font-size:28px;font-weight:bold;}
          QLabel#GreetingSpark {background:transparent;border:0;font-size:18px;font-weight:bold;}
          QPushButton#DashboardAction,QPushButton#CalendarTitle {background:transparent;border:0;color:%s;padding:3px;font-weight:bold;}
          QPushButton#CalendarArrow {background:%s;border:0;border-radius:8px;padding:3px;min-width:25px;}
          QPushButton#DashboardDay {background:transparent;border:0;border-radius:7px;padding:2px;font-weight:normal;color:%s;}
          QPushButton#DashboardDay:hover {background:%s;color:%s;} QPushButton#DashboardDay[today="true"], QPushButton#DashboardDay[today="true"]:hover {background:%s;color:%s;font-weight:bold;}
          QPushButton#DashboardRow {background:%s;color:%s;border:1px solid %s;border-radius:9px;text-align:right;padding:6px;}
        '''%(radius,c['text'],c['button'],c['muted'],c['text'],c['accent'],c['button'],c['text'],c['hover'],c['text'],c['accent'],on,c['field'],c['text'],c['border']))
        today=today_j();events=o.display_events() if allowed(o,'calendar') else [];marked=set()
        for ev in events:
            d=o.event_reference_date(ev)
            if d and not ev.get('done'):marked.add(d)
        if key in ('emerald_ivory','glass_mist'):
            header=QHBoxLayout();header.setDirection(QBoxLayout.RightToLeft);header.setAlignment(Qt.AlignTop)
            greeting=QVBoxLayout();greeting.setSpacing(1);greeting.addWidget(label('روزتان بخیر' if key=='emerald_ivory' else 'سلام، به کارنامه خوش آمدید','Greeting',45));greeting.addWidget(label(fa(today.day)+' '+MONTHS[today.month-1]+' '+fa(today.year),'DashboardMuted'));header.addLayout(greeting,1)
            if key=='glass_mist':
                from datetime import datetime
                from ui_icons import symbol
                hour=datetime.now().hour;greet='صبح قشنگت بخیر!' if 5<=hour<12 else 'عصرت پرانرژی!' if 12<=hour<18 else 'شبت آروم و قشنگ!';greeting_line=QLabel(greet);greeting_line.setObjectName('GreetingSpark');greeting_line.setStyleSheet('color:'+c['text']+';background:transparent;border:0;');greeting_line.setAlignment(Qt.AlignLeft|Qt.AlignVCenter);header.addWidget(greeting_line,0);greeting_icon=QLabel();greeting_icon.setPixmap(symbol('sun' if 5<=hour<18 else 'moon',c['accent']).pixmap(23,23));header.addWidget(greeting_icon,0)
            self.root.addLayout(header,0)
        row=QHBoxLayout();row.setDirection(QBoxLayout.LeftToRight);row.setSpacing(8);self.root.addLayout(row,1)
        custom=o.data.get('preferences',{}).get('home_widgets')
        if isinstance(custom,list):
            from home_layout import pack_widgets
            widgets=self.widget_factories(key,events,marked)
            preferences=o.data.get('preferences',{});columns=max(2,min(4,int(preferences.get('home_widget_columns',3))));spacing=max(3,min(20,int(preferences.get('home_widget_spacing',8))));height=preferences.get('home_widget_height',100);height=height if height in (70,100,130) else 100
            grid=QGridLayout();grid.setSpacing(spacing);row.addLayout(grid,1)
            selected=list(dict.fromkeys(k for k in custom if k in widgets));sizes=preferences.get('home_widget_sizes',{});sizes=sizes if isinstance(sizes,dict) else {};heights=preferences.get('home_widget_row_sizes',{});heights=heights if isinstance(heights,dict) else {}
            placements=pack_widgets(selected,sizes,heights,columns)
            for widget_key,grid_row,column,row_span,col_span in placements:
                widget=widgets[widget_key]();widget.setMinimumHeight(height*row_span);grid.addWidget(widget,grid_row,column,row_span,col_span)
            for grid_row in range(max((r+h for _,r,_,h,_ in placements),default=0)):grid.setRowStretch(grid_row,1)
            for column in range(columns):grid.setColumnStretch(column,1)
        elif key=='emerald_ivory':
            left,lv=self.box();lv.addWidget(self.reminders(events),3);lv.addWidget(self.companies(),2);row.addWidget(left,1)
            right,rv=self.box();rv.addWidget(self.calendar(key,marked),3);bottom=QHBoxLayout();bottom.setDirection(QBoxLayout.LeftToRight);bottom.addWidget(self.summary(),1);bottom.addWidget(self.graph('line'),2);rv.addLayout(bottom,2);row.addWidget(right,2)
        elif key=='bento_grid':
            left,lv=self.box();lv.addWidget(self.reminders(events,3,True));row.addWidget(left,1)
            row.addWidget(self.calendar(key,marked),1)
            right,rv=self.box();rv.addWidget(self.graph('line'),2)
            if self.height()>=490:rv.addWidget(self.glass_summary(events),1)
            row.addWidget(right,1)
        elif key=='glass_mist':
            left,lv=self.box();lv.addWidget(self.reminders(events,3,True));row.addWidget(left,1)
            row.addWidget(self.calendar(key,marked),1)
            if self.height()>=490 or s.get('weather_enabled',True):
                right,rv=self.box();rv.addWidget(self.graph('line'),2)
                if self.height()>=490:rv.addWidget(self.glass_summary(events),1)
                row.addWidget(right,1)
        else:
            left,lv=self.box();lv.addWidget(self.calendar(key,marked),3);lv.addWidget(self.companies(),2);row.addWidget(left,7)
            center,cv=self.box();cv.addWidget(self.graph('bars'),2);cv.addWidget(self.summary(True),2);cv.addWidget(self.reminders(events),2);row.addWidget(center,8)
            row.addWidget(self.timeline(events),10)
        if s.get('daily_quote_enabled',True) and not (isinstance(custom,list) and o.data.get('preferences',{}).get('home_customize_v2')):
            from quotes import daily_quote
            q=daily_quote();quote=label('«'+q['text']+'» · '+q['author'],'DashboardMuted',95);quote.setObjectName('DashboardQuote');quote.setAlignment(Qt.AlignCenter);self.root.addWidget(quote)
        # New children added to an already visible layout must be shown now;
        # old children removed by clear() remain hidden until Qt deletes them.
        def show_layout(layout):
            for i in range(layout.count()):
                item=layout.itemAt(i);widget=item.widget()
                if widget:
                    widget.show()
                    if widget.layout() and widget.objectName()!='WeatherStrip':show_layout(widget.layout())
                elif item.layout():show_layout(item.layout())
        show_layout(self.root)

