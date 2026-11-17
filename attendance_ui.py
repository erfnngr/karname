"""Monthly attendance review and a readable line chart, scoped by the server."""
import copy,threading
from datetime import date,datetime
from PySide6.QtCore import Qt,QPointF,QRectF,QObject,Signal,QTimer
from PySide6.QtGui import QPainter,QPen,QColor,QFont,QPolygonF
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QFormLayout,QLabel,QPushButton,QComboBox,QSpinBox,QLineEdit,QCheckBox,QFrame,QTableWidget,QTableWidgetItem,QAbstractItemView,QDialog,QDialogButtonBox,QFileDialog,QMessageBox,QSplitter,QToolTip,QInputDialog,QScrollArea)
from storage import MONTHS,fa,normalize,jformat,today_j,parse_j
from ui_icons import iconize

FLAGS={'incomplete_interval':'ورود یا خروج ناقص','zero_interval':'ساعت‌های یکسان','minutes_exceed_interval':'دقایق بیش از بازه','overlap':'هم‌پوشانی تردد','duration_only_approved':'فقط مدت تأییدشده','no_record':'تردد ثبت نشده','needs_review':'نیازمند بررسی','leave_work_overlap':'تداخل با مرخصی تأییدشده','rejected':'ردشده'}
STATUSES={'imported':'واردشده','needs_review':'نیازمند بررسی','approved':'تأییدشده','rejected':'ردشده'}
WEEK=[(5,'شنبه'),(6,'یکشنبه'),(0,'دوشنبه'),(1,'سه‌شنبه'),(2,'چهارشنبه'),(3,'پنجشنبه'),(4,'جمعه')]

def duration(minutes):
    minutes=int(minutes or 0);return fa(f'{minutes//60:02d}:{minutes%60:02d}')
def flag_text(flags):
    if not isinstance(flags,(tuple,list)):return str(flags or '')
    return '، '.join(FLAGS.get(str(x),str(x)) for x in flags)
def text(value='',hero=False):
    w=QLabel(str(value));w.setTextFormat(Qt.PlainText);w.setWordWrap(True)
    if hero:w.setObjectName('Hero')
    return w
def push(title,callback,key=None):
    w=QPushButton(title);w.setAccessibleName(title);w.setToolTip(title);w.clicked.connect(callback)
    if key:iconize(w,key,title)
    return w

class LineChart(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.data=[];self.points=[];self.setMinimumHeight(190);self.setMouseTracking(True);self.setAccessibleName('نمودار خطی ساعت کار روزانه')
    def set_data(self,days):self.data=days;self.update()
    def paintEvent(self,event):
        from appearance import palette_for
        colors=palette_for(self.owner.data['settings']);p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);background=QColor(colors['panel']);ink=QColor(colors['text']);grid=QColor(colors['border']);line=QColor(colors['accent']);p.fillRect(self.rect(),background);p.setPen(ink);p.drawText(QRectF(12,4,self.width()-24,24),Qt.AlignRight|Qt.AlignVCenter,'ساعت کار ثبت‌شده در هر روز')
        left,right,top,bottom=48,self.width()-20,32,self.height()-32;plot_w=max(1,right-left);plot_h=max(1,bottom-top);values=[float(x.get('worked_minutes') or 0)/60 for x in self.data if x.get('entries')];maximum=max(8,(max(values) if values else 0));maximum=max(8,int((maximum+1.999)//2)*2)
        font=QFont(self.font());font.setPointSize(max(7,font.pointSize()-1));p.setFont(font)
        for i in range(5):
            y=bottom-plot_h*i/4;p.setPen(QPen(grid,1));p.drawLine(QPointF(left,y),QPointF(right,y));p.setPen(ink);p.drawText(QRectF(2,y-9,40,18),Qt.AlignRight|Qt.AlignVCenter,fa(round(maximum*i/4,1)))
        self.points=[];previous=None;n=len(self.data)
        for i,d in enumerate(self.data):
            x=left+plot_w*i/max(1,n-1)
            if i in (0,n-1) or (i+1)%5==0:p.setPen(ink);p.drawText(QRectF(x-12,bottom+5,24,20),Qt.AlignCenter,fa(i+1))
            if not d.get('entries') or all('incomplete_interval' in e.get('flags',[]) for e in d['entries']):
                previous=None;continue
            value=float(d.get('worked_minutes') or 0)/60;y=bottom-plot_h*value/maximum;point=QPointF(x,y)
            if previous is not None:p.setPen(QPen(line,2.4));p.drawLine(previous,point)
            p.setPen(QPen(line,2));p.setBrush(background);p.drawEllipse(point,3.2,3.2);self.points.append((point,d));previous=point
        p.end()
    def mouseMoveEvent(self,event):
        pos=event.position();nearest=min(self.points,key=lambda x:(x[0].x()-pos.x())**2+(x[0].y()-pos.y())**2,default=None)
        if nearest and abs(nearest[0].x()-pos.x())<12:
            day=nearest[1];QToolTip.showText(event.globalPosition().toPoint(),fa(day['date'])+' · '+duration(day.get('worked_minutes'))+' ساعت\n'+flag_text(day.get('flags',[])),self)
        else:QToolTip.hideText()

class Signals(QObject):done=Signal(object,object,object)

class AttendancePanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.busy=False;self.report=None;self.people=[];self.companies=[];self.is_manager=False;self.signals=Signals();self.signals.done.connect(self.finished);self.setLayoutDirection(Qt.RightToLeft);v=QVBoxLayout(self);v.setContentsMargins(16,12,16,12);v.setSpacing(7);header=QHBoxLayout();header.addWidget(text('تردد و ساعت کار',True));header.addStretch();self.status=text('');header.addWidget(self.status);v.addLayout(header)
        filters=QHBoxLayout();self.company=QComboBox();self.company.setMinimumWidth(120);self.company.currentIndexChanged.connect(self.company_changed);filters.addWidget(self.company);self.year=QSpinBox();self.year.setRange(1300,1499);self.year.setValue(today_j().year);self.year.valueChanged.connect(self.load_report);filters.addWidget(self.year);self.month=QComboBox()
        for i,name in enumerate(MONTHS,1):self.month.addItem(name,i)
        self.month.setCurrentIndex(today_j().month-1);self.month.currentIndexChanged.connect(self.load_report);filters.addWidget(self.month);self.person=QComboBox();self.person.setMinimumWidth(175);self.person.currentIndexChanged.connect(self.load_report);filters.addWidget(self.person,1);self.refresh_button=push('بروزرسانی',self.reload,'refresh');filters.addWidget(self.refresh_button);self.import_button=push('ورود فایل تردد ماهانه',self.import_file,'import');filters.addWidget(self.import_button);self.schedule_button=push('برنامه کاری و استثناها',self.edit_policy,'settings');filters.addWidget(self.schedule_button);self.export_button=push('خروجی اکسل گزارش',self.export,'export');filters.addWidget(self.export_button);v.addLayout(filters)
        self.summary=text('');self.summary.setObjectName('Result');v.addWidget(self.summary);self.chart=LineChart(owner);v.addWidget(self.chart,1);tools=QHBoxLayout();self.filter=QComboBox();self.filter.addItem('همه روزها','all');self.filter.addItem('نیازمند بررسی','review');self.filter.addItem('دارای تردد','recorded');self.filter.addItem('روزهای کاری','working');self.filter.addItem('پنجشنبه، جمعه و غیرکاری','nonworking');self.filter.currentIndexChanged.connect(self.render_table);tools.addWidget(self.filter);self.detail=text('');tools.addWidget(self.detail,1);self.correction_button=push('درخواست اصلاح تردد',self.request_correction,'add');tools.addWidget(self.correction_button);self.edit_button=push('بررسی / ویرایش تردد روز',self.edit_entry,'edit');tools.addWidget(self.edit_button);v.addLayout(tools)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(['تاریخ','روز','ورود و خروج','کارکرد','اضافه‌کاری برآوردی','مرخصی','بررسی']);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.SingleSelection);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.verticalHeader().hide();self.table.horizontalHeader().setStretchLastSection(True);self.table.itemSelectionChanged.connect(self.selected_day);self.table.itemDoubleClicked.connect(lambda _:self.edit_entry());v.addWidget(self.table,1);self.note=text('');self.note.setObjectName('Sub');v.addWidget(self.note)
    def client(self):return getattr(self.owner.org,'client',None)
    def run(self,fn,callback):
        original=self.client()
        if self.busy or not original:return False
        from org_client import Client
        c=Client(original.url,original.session.verify if isinstance(original.session.verify,str) else None,getattr(original,'fingerprint',None));c.token=original.token;c.user=original.user;self.busy=True;self.status.setText('در حال دریافت…')
        def work():
            try:self.signals.done.emit(fn(c),None,callback)
            except Exception as e:self.signals.done.emit(None,e,callback)
            finally:c.session.close()
        threading.Thread(target=work,daemon=True).start();return True
    def finished(self,value,error,callback):
        self.busy=False
        if error:
            self.status.setText(str(error))
            if getattr(error,'status',None)==401:QTimer.singleShot(0,self.owner.lock_session)
            return
        self.status.setText('بروزرسانی '+datetime.now().strftime('%H:%M'));callback(value)
    def showEvent(self,event):
        super().showEvent(event);QTimer.singleShot(0,self.reload)
    def month_value(self):return f'{self.year.value():04d}/{self.month.currentData():02d}'
    def reload(self):
        if self.owner._locking or getattr(self.owner,'_exit_pending',False) or getattr(self.owner,'_exit_approved',False):return
        if not self.client():self.status.setText('برای مشاهده تردد، به مرکز شرکت وارد شوید.');return
        self.run(lambda c:c.request('companies'),self.set_companies)
    def set_companies(self,companies):
        self.companies=companies;current=self.company.currentData();self.company.blockSignals(True);self.company.clear()
        for c in companies:self.company.addItem(c['name'],c['id'])
        self.company.setCurrentIndex(max(0,self.company.findData(current)));self.company.blockSignals(False);self.company_changed()
    def company_changed(self,*_):
        co=self.company.currentData()
        if co:self.run(lambda c:c.request('workspace/attendance-people',company=co),self.set_people)
    def set_people(self,data):
        from permission_policy import allowed
        self.people=data['people'];self.is_manager=bool(data['is_manager']);old=self.person.currentData();self.person.blockSignals(True);self.person.clear()
        for item in self.people:self.person.addItem(item['name']+' · '+item['employee_code'],item['employee_code'])
        self.person.setCurrentIndex(max(0,self.person.findData(old)));self.person.blockSignals(False);actor=self.owner.session_user or {};company=self.company.currentData();self.import_button.setVisible(self.is_manager and allowed(actor,company,'attendance','import'));self.schedule_button.setVisible(self.is_manager and allowed(actor,company,'attendance','manage_schedule'));self.edit_button.setVisible(self.is_manager and allowed(actor,company,'attendance','edit'))
        if not self.people:
            self.report=None;self.table.setRowCount(0);self.chart.set_data([]);self.summary.setText('پرونده پرسنلی مرتبط با حساب پیدا نشد.' if not self.is_manager else 'ابتدا برای کارکنان پرونده پرسنلی و کد وارد کنید.');self.note.setText('پیوند حساب و کد پرسنلی از فضای شرکت ← پرونده کارکنان تنظیم می‌شود.');return
        self.load_report()
    def load_report(self,*_):
        co=self.company.currentData();code=self.person.currentData()
        if not co or not code:return
        person=next((p for p in self.people if p['employee_code']==code),{});self.correction_button.setVisible(person.get('user_id')==(self.owner.session_user or {}).get('id'))
        month=self.month_value()
        if not self.run(lambda c:c.request('workspace/attendance-report',company=co,month=month,employee_code=code),self.show_report):
            if self.busy:QTimer.singleShot(350,self.load_report)
    def show_report(self,report):
        if report.get('company')!=self.company.currentData() or report.get('month')!=self.month_value() or report.get('person',{}).get('employee_code')!=self.person.currentData():QTimer.singleShot(0,self.load_report);return
        self.report=report;t=report['totals'];self.summary.setText('ساعت کار: '+duration(t['worked_minutes'])+'   ·   تأییدشده: '+duration(t['approved_minutes'])+'   ·   اضافه‌کاری برآوردی: '+duration(t['overtime_minutes'])+'   ·   روزهای نیازمند بررسی: '+fa(t['missing_days']+t['incomplete_days']));self.chart.set_data(report['days']);self.note.setText(report.get('note',''));self.render_table()
        home=getattr(self.owner,'home',None)
        if home and hasattr(home,'theme_dashboard') and home.theme_dashboard.isVisible():home.theme_dashboard.refresh()
    def render_table(self,*_):
        data=self.report or {};mode=self.filter.currentData();self.visible=[]
        for d in data.get('days',[]):
            if mode=='review' and not d.get('flags') and not any(e.get('flags') or e.get('status') not in ('approved',) for e in d.get('entries',[])):continue
            if mode=='recorded' and not d.get('entries'):continue
            if mode=='working' and not d.get('working_day'):continue
            if mode=='nonworking' and d.get('working_day'):continue
            self.visible.append(d)
        self.table.setRowCount(len(self.visible))
        for i,d in enumerate(self.visible):
            entries=d.get('entries',[]);pairs='  |  '.join((fa(e.get('check_in') or '—')+' ← '+fa(e.get('check_out') or '—')) for e in entries) or '—';leave='، '.join(str(x.get('type','مرخصی'))+(' '+fa(x.get('hours',''))+' ساعت' if x.get('hours') and x['hours']!='0' else '') for x in d.get('leave',[]));flags=list(d.get('flags',[]));flags.extend(f for e in entries for f in e.get('flags',[]) if f not in flags);status=flag_text(flags) or ('، '.join(dict.fromkeys(STATUSES.get(e['status'],e['status']) for e in entries)) if entries else ('غیرکاری' if not d['working_day'] else '—'))
            for col,value in enumerate([fa(d['date']),d.get('weekday',''),pairs,duration(d.get('worked_minutes')),duration(d.get('overtime_minutes')),leave,status]):
                item=QTableWidgetItem(str(value));item.setTextAlignment(Qt.AlignCenter);item.setToolTip(str(value));self.table.setItem(i,col,item)
                if not d['working_day']:
                    item.setBackground(QColor('#FCE9ED'));item.setForeground(QColor('#7A2638'))
        self.table.resizeColumnsToContents();self.detail.clear()
    def selected_day(self):
        i=self.table.currentRow()
        if i<0 or i>=len(self.visible):self.detail.clear();return
        d=self.visible[i];self.detail.setText('موظفی: '+duration(d['required_minutes'])+'  ·  تأییدشده: '+duration(d['approved_minutes'])+'  ·  تعداد بازه‌ها: '+fa(len(d['entries'])))
    def edit_entry(self):
        from permission_policy import allowed
        if not self.is_manager or not allowed(self.owner.session_user or {},self.company.currentData(),'attendance','edit'):return
        i=self.table.currentRow()
        if i<0 or i>=len(self.visible):return
        entries=self.visible[i]['entries']
        if not entries:QMessageBox.information(self,'بررسی تردد','برای این روز ردیف تردد ثبت نشده است.');return
        labels=[(e.get('check_in') or '—')+' ← '+(e.get('check_out') or '—')+' · '+STATUSES.get(e['status'],e['status']) for e in entries];choice,ok=QInputDialog.getItem(self,'انتخاب بازه','کدام بازه بررسی شود؟',labels,0,False)
        if not ok:return
        id=entries[labels.index(choice)]['id'];co=self.company.currentData()
        def show(record):
            ix=self.owner.org.company.findData(co)
            if ix>=0:self.owner.org.company.setCurrentIndex(ix)
            self.owner.org.edit(record=record);QTimer.singleShot(1200,self.load_report)
        self.run(lambda c:c.request('record',id=id),show)
    def import_file(self):
        from permission_policy import allowed
        if not self.is_manager or not allowed(self.owner.session_user or {},self.company.currentData(),'attendance','import'):return
        path,_=QFileDialog.getOpenFileName(self,'فایل تردد ماهانه از فلش یا پوشه','','Attendance (*.xlsx *.csv *.txt *.tsv)')
        if not path:return
        try:
            from org_ui import AttendanceDialog
            d=AttendanceDialog(self.owner.org,path);d.month.setText(self.month_value())
            if d.exec()!=QDialog.Accepted:return
            rows=d.valid;month=d.month_value;company=self.company.currentData()
            if len(rows)>10000:raise ValueError('در هر بار حداکثر ۱۰ هزار ردیف را وارد کنید.')
            def done(result):
                self.owner.data['company_write_at']=datetime.now().isoformat();self.owner.persist();self.owner.org.revision=None;self.owner.org.sync();self.status.setText('واردشده: '+fa(result['added'])+' · تکراری: '+fa(result['duplicates']));QTimer.singleShot(500,self.load_report)
            self.run(lambda c:c.request('attendance',dict(company=company,rows=rows,month=month)),done)
        except Exception as e:QMessageBox.warning(self,'ورود تردد',str(e))
    def request_correction(self):
        from ui_permissions import gate
        if not gate(self.owner,'workspace','create'):return
        from workspace_ui import RequestDialog
        if not self.company.currentData():return
        i=self.table.currentRow();day=self.visible[i]['date'] if 0<=i<len(getattr(self,'visible',[])) else ''
        d=RequestDialog(self,self.companies);d.company.setCurrentIndex(max(0,d.company.findData(self.company.currentData())));d.kind.setCurrentIndex(d.kind.findData('attendance'));d.title.setText('درخواست اصلاح تردد'+(' · '+fa(day) if day else ''));d.start.setText(day);d.end.setText(day)
        if d.exec()==QDialog.Accepted:self.run(lambda c:c.request('workspace/requests',d.payload),lambda _:(self.status.setText('درخواست برای بررسی ثبت شد.'),self.owner.workspace.refresh()))
    def edit_policy(self):
        co=self.company.currentData()
        from permission_policy import allowed
        if not co or not self.is_manager or not allowed(self.owner.session_user or {},co,'attendance','manage_schedule'):return
        self.run(lambda c:c.request('workspace/policy',company=co,key='attendance'),lambda data:AttendancePolicyDialog(self,co,data['value'],self.people).exec())
    def export(self):
        if not self.report:return
        path,_=QFileDialog.getSaveFileName(self,'گزارش ماهانه تردد','Karname-Attendance-'+self.month_value().replace('/','-')+'.xlsx','Excel (*.xlsx)')
        if not path:return
        try:
            from org_reports import spreadsheet
            rows=[]
            for d in self.report['days']:
                entries=d.get('entries',[]);rows.append({'نام':self.report['person']['name'],'کد پرسنلی':self.report['person']['employee_code'],'تاریخ':d['date'],'روز':d.get('weekday',''),'ورود و خروج':' | '.join((e.get('check_in') or '—')+' → '+(e.get('check_out') or '—') for e in entries),'دقایق کار':d.get('worked_minutes',0),'دقایق تأییدشده':d.get('approved_minutes',0),'اضافه‌کاری برآوردی؛ دقیقه':d.get('overtime_minutes',0),'بررسی':flag_text(d.get('flags',[]))})
            spreadsheet(path if path.lower().endswith('.xlsx') else path+'.xlsx',rows,'تردد ماهانه');self.status.setText('گزارش اکسل ذخیره شد.')
        except Exception as e:QMessageBox.warning(self,'گزارش تردد',str(e))

class AttendancePolicyDialog(QDialog):
    def __init__(self,panel,company,policy,people):
        super().__init__(panel);self.panel=panel;self.company=company;self.policy=copy.deepcopy(policy);self.people=people;self.setWindowTitle('برنامه کاری و استثناها');self.resize(760,670);self.setLayoutDirection(Qt.RightToLeft);outer=QVBoxLayout(self);self.scope=QComboBox();self.scope.addItem('برنامه عمومی شرکت','')
        for u in people:
            if u.get('user_id'):self.scope.addItem(u['name']+' · '+u['employee_code'],u['user_id'])
        top=QFormLayout();top.addRow('برنامه برای:',self.scope);outer.addLayout(top);self.inherit=QCheckBox('برای این فرد از برنامه عمومی شرکت استفاده شود');outer.addWidget(self.inherit);self.rule=QComboBox();self.rule.addItem('ساعت بیشتر از موظفی روز','daily_excess');self.rule.addItem('ساعت خارج از بازه برنامه','outside_schedule');self.rule.setCurrentIndex(max(0,self.rule.findData(policy.get('overtime_rule','daily_excess'))));top.addRow('روش برآورد اضافه‌کاری:',self.rule);self.official=QCheckBox('تعطیلات رسمی ثبت‌شده غیرکاری باشند');self.official.setChecked(policy.get('exclude_official_holidays',True));outer.addWidget(self.official);self.week=QTableWidget(7,5);self.week.setHorizontalHeaderLabels(['روز','کاری','شروع HH:MM','پایان HH:MM','استراحت؛ دقیقه']);self.week.verticalHeader().hide();self.week.horizontalHeader().setStretchLastSection(True);outer.addWidget(self.week)
        outer.addWidget(text('استثناهای تاریخ؛ روز کاری یا غیرکاری برای تاریخ مشخص:'));self.exceptions=QTableWidget(0,5);self.exceptions.setHorizontalHeaderLabels(['تاریخ شمسی','کاری','شروع','پایان','استراحت؛ دقیقه']);self.exceptions.horizontalHeader().setStretchLastSection(True);outer.addWidget(self.exceptions,1);buttons=QHBoxLayout();buttons.addWidget(push('افزودن استثنا',self.add_exception,'add'));buttons.addWidget(push('حذف استثنای انتخابی',self.remove_exception,'delete'));buttons.addStretch();outer.addLayout(buttons);note=text('پنجشنبه و جمعه در برنامه عمومی پیش‌فرض غیرکاری‌اند. اضافه‌کاری و روز فاقد تردد برآورد برای بررسی است؛ تأیید نهایی با مسئول شرکت است.');note.setObjectName('Sub');outer.addWidget(note);actions=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);actions.button(QDialogButtonBox.Save).setText('ذخیره برنامه');actions.button(QDialogButtonBox.Cancel).setText('بستن');actions.accepted.connect(self.save);actions.rejected.connect(self.reject);outer.addWidget(actions);self.scope.currentIndexChanged.connect(self.load);self.inherit.toggled.connect(self.toggle_inherit);self.load()
    def _row(self,table,index,first,value):
        for j,val in enumerate((first,'',value.get('start','09:00'),value.get('end','17:00'),str(value.get('break_minutes',0)))):
            item=QTableWidgetItem(str(val))
            if j==1:item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable);item.setCheckState(Qt.Checked if value.get('working',False) else Qt.Unchecked)
            elif table is self.week and j==0:item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)
            table.setItem(index,j,item)
    def load(self):
        id=self.scope.currentData();person=self.policy.get('people',{}).get(id) if id else None;self.inherit.blockSignals(True);self.inherit.setVisible(bool(id));self.inherit.setChecked(bool(id) and not bool(person));self.inherit.blockSignals(False);base=person or self.policy;week=base.get('week',self.policy.get('week',{}));self.week.setRowCount(7)
        for i,(day,name) in enumerate(WEEK):self._row(self.week,i,name,week.get(str(day),{}))
        exceptions=base.get('exceptions',{});self.exceptions.setRowCount(len(exceptions))
        for i,(day,value) in enumerate(sorted(exceptions.items())):self._row(self.exceptions,i,day,value)
        self.toggle_inherit(self.inherit.isChecked())
    def toggle_inherit(self,checked):self.week.setEnabled(not checked);self.exceptions.setEnabled(not checked)
    def add_exception(self):
        if self.inherit.isChecked():return
        i=self.exceptions.rowCount();self.exceptions.insertRow(i);self._row(self.exceptions,i,normalize(jformat(today_j())),dict(working=False,start='09:00',end='17:00',break_minutes=0))
    def remove_exception(self):
        if self.inherit.isChecked():return
        i=self.exceptions.currentRow()
        if i>=0:self.exceptions.removeRow(i)
    def read_row(self,table,i):
        from attendance_import import clock
        checked=table.item(i,1).checkState()==Qt.Checked;start,_=clock(table.item(i,2).text());end,_=clock(table.item(i,3).text());minutes=int(normalize(table.item(i,4).text()))
        if not start or not end or not 0<=minutes<=1440:raise ValueError('ساعت شروع، پایان و استراحت معتبر وارد کنید.')
        return dict(working=checked,start=start,end=end,break_minutes=minutes)
    def save(self):
        try:
            policy=copy.deepcopy(self.policy);id=self.scope.currentData();policy['overtime_rule']=self.rule.currentData();policy['exclude_official_holidays']=self.official.isChecked();policy.setdefault('people',{})
            if id and self.inherit.isChecked():policy['people'].pop(id,None)
            else:
                week={str(day):self.read_row(self.week,i) for i,(day,_) in enumerate(WEEK)};exceptions={}
                for i in range(self.exceptions.rowCount()):
                    d=parse_j(self.exceptions.item(i,0).text());key=f'{d.year:04d}/{d.month:02d}/{d.day:02d}'
                    if key in exceptions:raise ValueError('تاریخ استثنا تکراری است.')
                    exceptions[key]=self.read_row(self.exceptions,i)
                if id:policy['people'][id]=dict(week=week,exceptions=exceptions)
                else:policy.update(week=week,exceptions=exceptions)
            if not self.panel.run(lambda c:c.request('workspace/policy',dict(company=self.company,key='attendance',payload=policy)),lambda _:(self.accept(),self.panel.load_report())):raise ValueError('ارتباط دیگری در حال انجام است؛ دوباره تلاش کنید.')
        except Exception as e:QMessageBox.warning(self,'برنامه کاری',str(e))
