"""Minimal home weather strip and separated hourly / weekly forecasts."""
from PySide6.QtCore import Qt,QByteArray,QTimer,QRectF,QPointF
from PySide6.QtGui import QPixmap,QPainter,QColor,QPainterPath,QLinearGradient,QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame,QLabel,QVBoxLayout,QHBoxLayout,QWidget,QPushButton,QDialog,QScrollArea,QGridLayout
from storage import fa,package_file
from weather import weather_kind

def icon(name,color,size=23):
    raw=package_file('assets/weather-icons/'+name+'.svg').read_text(encoding='utf-8').replace('currentColor',color)
    pix=QPixmap(size,size);pix.fill(Qt.transparent);p=QPainter(pix);QSvgRenderer(QByteArray(raw.encode())).render(p);p.end();return pix

def clear(layout):
    while layout.count():
        item=layout.takeAt(0)
        if item.widget():item.widget().hide();item.widget().deleteLater()

def picture(symbol,color,size):
    return AnimatedWeatherIcon(symbol,size)

def measurement_caption(data,now=None):
    from datetime import datetime,timezone
    current=data.get('current',{});obs=current.get('observation')
    if isinstance(obs,dict) and obs.get('observed_at'):
        try:
            stamp=datetime.fromisoformat(obs['observed_at']);now=now or datetime.now(timezone.utc)
            if stamp.tzinfo is None:raise ValueError()
            minutes=max(0,int((now.astimezone(timezone.utc)-stamp.astimezone(timezone.utc)).total_seconds()/60))
            return 'اندازه‌گیری '+fa(minutes)+' دقیقه پیش'
        except (ValueError,TypeError,OverflowError):pass
    return 'برآورد فعلی' if data.get('estimated') else 'پیش‌بینی مدل' if current.get('model_temperature') else ''

class AnimatedWeatherIcon(QWidget):
    """Native rendering of the supplied animated sun, cloud and precipitation icons."""
    _timer=None
    def __init__(self,symbol,size=32):
        super().__init__();self.kind=weather_kind(symbol)[0];self.setFixedSize(size,size);self.setToolTip(weather_kind(symbol)[1]);self.setAttribute(Qt.WA_TransparentForMouseEvents)
        if AnimatedWeatherIcon._timer is None:
            from PySide6.QtWidgets import QApplication
            AnimatedWeatherIcon._timer=QTimer(QApplication.instance());AnimatedWeatherIcon._timer.setInterval(200);AnimatedWeatherIcon._timer.start()
        AnimatedWeatherIcon._timer.timeout.connect(self.tick)
    def tick(self):
        if self.isVisible() and not self.window().isMinimized() and not self.visibleRegion().isEmpty():self.update()
    def paintEvent(self,event):
        import math,time
        t=time.monotonic();p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.scale(self.width()/48,self.height()/48);kind=self.kind
        yellow=QColor('#F4AF25');cloud=QColor('#8194AA');blue=QColor('#60A5FA');lunar=QColor('#38BDF8')
        def pen(color,width=2):
            x=QPen(color,width);x.setCapStyle(Qt.RoundCap);x.setJoinStyle(Qt.RoundJoin);p.setPen(x);p.setBrush(Qt.NoBrush)
        if kind in ('sun','cloud-sun'):
            cx,cy=(24,24) if kind=='sun' else (16,15);radius=8 if kind=='sun' else 6;pen(yellow,2);p.drawEllipse(QPointF(cx,cy),radius,radius)
            for i in range(8):
                a=i*math.pi/4+t*math.pi/6;p.drawLine(QPointF(cx+math.cos(a)*(radius+4),cy+math.sin(a)*(radius+4)),QPointF(cx+math.cos(a)*(radius+7),cy+math.sin(a)*(radius+7)))
        if kind in ('moon','cloud-moon'):
            pen(lunar);path=QPainterPath();path.moveTo(28,8);path.cubicTo(8,6,8,39,28,36);path.cubicTo(17,32,17,13,28,8);p.drawPath(path)
            p.setBrush(lunar)
            for i,(x,y) in enumerate(((34,10),(38,18),(31,6))):
                p.setOpacity(.35+.6*(1+math.sin(t*3+i))/2);p.drawEllipse(QPointF(x,y),1.3,1.3)
            p.setOpacity(1)
        if kind not in ('sun','moon'):
            offset=math.sin(t*1.05)*1.2;p.save();p.translate(offset,0);pen(blue if kind=='cloud-rain' else cloud);path=QPainterPath();path.moveTo(36,29);path.lineTo(15,29);path.cubicTo(5,29,5,17,14,16);path.cubicTo(17,6,31,8,34,17);path.cubicTo(42,17,43,27,36,29);p.drawPath(path);p.restore()
            if kind in ('cloud-rain','cloud-snow'):
                pen(blue if kind=='cloud-rain' else cloud,2)
                for i,x in enumerate((15,22,29,36)):
                    y=31+((t*9+i*3)%11);p.setOpacity(max(.2,1-(y-31)/14))
                    if kind=='cloud-rain':p.drawLine(QPointF(x,y),QPointF(x-1,y+3))
                    else:p.drawEllipse(QPointF(x+math.sin(t+i),y),1.1,1.1)
                p.setOpacity(1)
            if kind=='cloud-lightning':
                pen(yellow,2.5);p.setOpacity(.3+.7*(math.sin(t*6)>0));p.drawLine(QPointF(26,27),QPointF(22,35));p.drawLine(QPointF(22,35),QPointF(28,35));p.drawLine(QPointF(28,35),QPointF(24,43));p.setOpacity(1)
            if kind=='cloud-fog':
                pen(cloud,1.5)
                for y in (33,38,43):p.drawLine(QPointF(10+offset,y),QPointF(38+offset,y))
        p.end()

class WeatherWidget(QFrame):
    def __init__(self,owner,service,parent=None):
        super().__init__(parent);self.owner=owner;self.service=service;self.setObjectName('WeatherStrip');self.setLayoutDirection(Qt.RightToLeft);self.setMinimumWidth(185)
        root=QVBoxLayout(self);root.setContentsMargins(10,8,10,8);root.setSpacing(4)
        head=QHBoxLayout();self.title=QLabel('آب‌وهوای تهران');self.title.setObjectName('WeatherTitle');head.addWidget(self.title,1);self.details=QPushButton('جزئیات');self.details.setToolTip('پیش‌بینی کامل و مقایسه دما');self.details.clicked.connect(self.show_details);head.addWidget(self.details);root.addLayout(head)
        self.status=QLabel();self.status.setObjectName('WeatherSmall');root.addWidget(self.status)
        self.current_row=QHBoxLayout();root.addLayout(self.current_row)
        self.hour_label=QLabel('ساعت‌های آینده');self.hour_label.setObjectName('WeatherSmall');root.addWidget(self.hour_label)
        self.hour_host=QScrollArea();self.hour_host.setWidgetResizable(True);self.hour_host.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.hour_host.setMaximumHeight(85);self.hour_host.setMinimumHeight(65);hour_body=QWidget();self.hour_row=QHBoxLayout(hour_body);self.hour_row.setContentsMargins(0,0,0,0);self.hour_row.setSpacing(4);self.hour_host.setWidget(hour_body);root.addWidget(self.hour_host)
        self.week_label=QLabel('پیش‌بینی هفتگی');self.week_label.setObjectName('WeatherSmall');root.addWidget(self.week_label)
        self.week_host=QScrollArea();self.week_host.setWidgetResizable(True);self.week_host.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.week_host.setMinimumHeight(35);week_body=QWidget();self.content=QVBoxLayout(week_body);self.content.setContentsMargins(0,0,0,0);self.content.setSpacing(0);self.week_host.setWidget(week_body);root.addWidget(self.week_host,1)
        service.changed.connect(self.render);self.render()
    def render(self):
        from appearance import palette_for
        c=palette_for(self.owner.data['settings']);dark=self.owner.data['settings'].get('theme')=='dark'
        self.setStyleSheet('QFrame#WeatherStrip{background:transparent;border:0;} QLabel{background:transparent;border:0;color:'+c['text']+';} QLabel#WeatherTitle{font-weight:700;font-size:13px;} QLabel#WeatherSmall{font-size:10px;color:'+c['muted']+';} QScrollArea,QScrollArea > QWidget > QWidget{background:transparent;border:0;} QFrame#WeatherCell{background:'+('rgba(255,255,255,18)' if dark else 'rgba(255,255,255,75)')+';border:0;border-radius:7px;} QPushButton{background:transparent;color:'+c['accent']+';border:0;font-size:11px;padding:2px 5px;}')
        clear(self.content);clear(self.hour_row);clear(self.current_row);data=self.service.data;self.details.setVisible(bool(data));showhour=bool(data and self.owner.data['settings'].get('weather_hourly',True));showweek=bool(data and self.owner.data['settings'].get('weather_weekly',True));self.hour_host.setVisible(showhour);self.hour_label.setVisible(showhour);self.week_host.setVisible(showweek);self.week_label.setVisible(showweek)
        if not data:
            self.current_row.addWidget(QLabel('در حال دریافت آب‌وهوا…' if self.service.busy else self.service.error or 'آب‌وهوا هنوز دریافت نشده است.'));self.status.setText('');return
        current=data['current'];self.title.setText('آب‌وهوای '+data.get('location','تهران'))
        self.hour_label.setText('ساعت‌های آینده · تخمینی' if data.get('estimated') else 'ساعت‌های آینده')
        self.current_row.addWidget(picture(current['symbol'],c['accent'],38));info=QLabel(fa(round(current['temp']))+'°');info.setStyleSheet('font-size:24px;font-weight:700;');self.current_row.addWidget(info);self.current_row.addWidget(QLabel(weather_kind(current['symbol'])[1]),1)
        for hour in data.get('hours',[]):
            cell=QFrame();cell.setObjectName('WeatherCell');cell.setFixedWidth(47);col=QVBoxLayout(cell);col.setContentsMargins(1,1,1,1);col.setSpacing(0);label=QLabel(fa(hour['time'].strftime('%H:%M')));label.setAlignment(Qt.AlignCenter);label.setStyleSheet('font-size:9px;');col.addWidget(label);pic=picture(hour['symbol'],c['accent'],22);col.addWidget(pic,0,Qt.AlignCenter);label=QLabel(fa(round(hour['temp']))+'°');label.setAlignment(Qt.AlignCenter);col.addWidget(label);self.hour_row.addWidget(cell)
        names=['دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه','شنبه','یکشنبه']
        for day in data['days']:
            cell=QFrame();cell.setObjectName('WeatherCell');line=QHBoxLayout(cell);line.setContentsMargins(5,3,5,3);line.setSpacing(3)
            daytitle=QLabel('امروز' if day['date']==current['time'].date() else names[day['date'].weekday()]);line.addWidget(daytitle,1);line.addWidget(picture(day['symbol'],c['accent'],20));line.addWidget(QLabel(fa(round(day['max']))+'° / '+fa(round(day['min']))+'°'));self.content.addWidget(cell)
        stamp=self.service.checked_at.strftime('%H:%M') if self.service.checked_at else ''
        caption=measurement_caption(data) or ('آخرین دریافت '+fa(stamp))
        self.status.setText(caption+(' · ذخیره‌شده' if getattr(self.service,'cached',False) or self.service.error else ''))
        observation=current.get('observation') or {};station=observation.get('station_name','')
        self.status.setToolTip(('ایستگاه: '+station+' · ' if station else '')+'آخرین دریافت: '+fa(stamp))
    def paintEvent(self,event):
        from PySide6.QtCore import QPoint,QRectF
        dark=self.owner.data['settings'].get('theme')=='dark';p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);r=QRectF(self.rect()).adjusted(.5,.5,-.5,-.5);path=QPainterPath();path.addRoundedRect(r,14,14);p.setClipPath(path)
        board=self.parentWidget()
        if board and board.objectName()=='ThemeDashboard':
            board.prepare_backdrop();pos=self.mapTo(board,QPoint(0,0));p.drawPixmap(QRectF(self.rect()),board._blurred_background,QRectF(pos.x(),pos.y(),self.width(),self.height()))
        from appearance import palette_for
        colors=palette_for(self.owner.data['settings']);face=QLinearGradient(0,0,0,self.height());face.setColorAt(0,QColor(colors['panel']));face.setColorAt(1,QColor(colors['bg']));p.fillRect(self.rect(),face);p.setClipping(False);p.setPen(QColor(colors['border']));p.drawPath(path);p.end()
    def show_details(self):
        data=self.service.data
        if not data:return
        from appearance import palette_for
        import jdatetime
        c=palette_for(self.owner.data['settings']);dark=self.owner.data['settings'].get('theme')=='dark'
        dialog=QDialog(self);dialog.setWindowTitle('آب‌وهوا');dialog.resize(820,600);dialog.setMinimumSize(580,460);dialog.setLayoutDirection(Qt.RightToLeft)
        dialog.setStyleSheet('QDialog{background:'+c['bg']+';} QLabel{background:transparent;color:'+c['text']+';border:0;} QFrame#ForecastGlass{background:'+('rgba(36,67,83,220)' if dark else 'rgba(237,247,253,235)')+';border:1px solid '+c['border']+';border-radius:15px;} QScrollArea{border:0;background:transparent;}')
        outer=QVBoxLayout(dialog);outer.setContentsMargins(20,16,20,16);outer.setSpacing(10)
        def card(title):
            frame=QFrame();frame.setObjectName('ForecastGlass');inside=QVBoxLayout(frame);inside.setContentsMargins(15,10,15,10);inside.setSpacing(7);label=QLabel(title);label.setStyleSheet('font-size:13px;font-weight:700;');inside.addWidget(label);return frame,inside
        current=data['current'];now,cv=card('اکنون · '+data.get('location','تهران'));top=QHBoxLayout();cv.addLayout(top);top.addWidget(picture(current['symbol'],c['accent'],42));temp=QLabel(fa(round(current['temp']))+'°');temp.setStyleSheet('font-size:30px;font-weight:700;');top.addWidget(temp);desc=QLabel(weather_kind(current['symbol'])[1]);top.addWidget(desc,1)
        extras=[]
        if current.get('humidity') is not None:extras.append('رطوبت '+fa(current['humidity'])+'٪')
        if current.get('wind') is not None:extras.append('باد '+fa(current['wind'])+' کیلومتر/ساعت')
        if extras:top.addWidget(QLabel('   |   '.join(extras)))
        caption=measurement_caption(data);station=(current.get('observation') or {}).get('station_name','')
        if caption or station:
            info=QLabel(caption+(' · ایستگاه: '+station if station else ''));info.setTextFormat(Qt.PlainText);info.setWordWrap(True);cv.addWidget(info)
        outer.addWidget(now)
        hourly,hv=card('پیش‌بینی ساعتی · تخمینی' if data.get('estimated') else 'پیش‌بینی ساعتی · ۲۴ ساعت آینده');scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);scroll.setMinimumHeight(125);scroll.setMaximumHeight(145);strip=QWidget();strip.setStyleSheet('background:transparent;');hours=QHBoxLayout(strip);hours.setContentsMargins(2,0,2,0);hours.setSpacing(9)
        for item in data.get('hours',[]):
            col=QVBoxLayout();col.setSpacing(3);time=QLabel(fa(item['time'].strftime('%H:%M')));time.setAlignment(Qt.AlignCenter);col.addWidget(time);col.addWidget(picture(item['symbol'],c['accent'],25));value=QLabel(fa(round(item['temp']))+'°');value.setAlignment(Qt.AlignCenter);col.addWidget(value);cell=QWidget();cell.setFixedWidth(65);cell.setLayout(col);hours.addWidget(cell)
        hours.addStretch();scroll.setWidget(strip);hv.addWidget(scroll);outer.addWidget(hourly)
        weekly,wv=card('پیش‌بینی هفتگی');grid=QGridLayout();grid.setHorizontalSpacing(10);grid.setVerticalSpacing(6);wv.addLayout(grid);outer.addWidget(weekly,1)
        names=['دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه','شنبه','یکشنبه']
        for i,day in enumerate(data['days']):
            jd=jdatetime.date.fromgregorian(date=day['date']);label=QLabel(('امروز' if day['date']==current['time'].date() else names[day['date'].weekday()])+'  ·  '+fa(jd.strftime('%m/%d')));grid.addWidget(label,i,0);grid.addWidget(picture(day['symbol'],c['accent'],20),i,1);grid.addWidget(QLabel(weather_kind(day['symbol'])[1]),i,2);grid.addWidget(QLabel(fa(round(day['max']))+'°  /  '+fa(round(day['min']))+'°'),i,3)
        grid.setColumnStretch(0,1);grid.setColumnStretch(2,2)
        footer=QHBoxLayout();comparison=QLabel('');comparison.setTextFormat(Qt.PlainText);comparison.setWordWrap(True);footer.addWidget(comparison,1)
        compare_button=QPushButton('مقایسه با مدل');footer.addWidget(compare_button);close=QPushButton('بستن');close.clicked.connect(dialog.accept);footer.addWidget(close);outer.addLayout(footer)
        has_compare=hasattr(self.service,'comparison_changed') and hasattr(self.service,'compare')
        compare_button.setVisible(has_compare)
        def update_compare():
            compare_button.setEnabled(not self.service.comparison_busy)
            value=self.service.comparison
            if self.service.comparison_busy:comparison.setText('در حال دریافت مقایسه…')
            elif value:
                def fmt(n):return fa(('%+.1f'%n).replace('+','+'))
                comparison.setText('مدل: '+fa('%.1f'%value['model'])+'° · ایستگاه: '+fa('%.1f'%value['observation'])+'° · اختلاف مدل و ایستگاه: '+fmt(value['difference'])+'°')
            elif self.service.comparison_error:comparison.setText(self.service.comparison_error)
        if has_compare:
            self.service.comparison_changed.connect(update_compare);compare_button.clicked.connect(self.service.compare);update_compare()
        try:dialog.exec()
        finally:
            if has_compare:
                try:self.service.comparison_changed.disconnect(update_compare)
                except (RuntimeError,TypeError):pass
