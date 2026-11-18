import copy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLineEdit,QComboBox,QCheckBox,QTableWidget,QTableWidgetItem,QPushButton,QLabel,QFileDialog,QMessageBox,QInputDialog
from storage import today_j,jformat,normalize,fa
from payroll_ui import DEFAULTS,PayrollOptions
from payroll import compute_payroll
from payroll_batch import validate_batch,previous_month,compare,export_collection

class PayrollBatchPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.slips=[];self.previous=[];self.defaults=copy.deepcopy(DEFAULTS);self._loading=False;v=QVBoxLayout(self);top=QHBoxLayout();self.company=QComboBox();self.period=QLineEdit(normalize(jformat(today_j()))[:7]);self.period.setMaximumWidth(110);self.attendance=QCheckBox('کارکرد تأییدشده');self.attendance.setChecked(True);top.addWidget(self.company);top.addWidget(self.period);top.addWidget(self.attendance)
        for title,fn in [('دریافت کارکنان',self.load),('نرخ‌ها و مزایای مشترک',self.options),('جزئیات فرد',self.person_options)]:b=QPushButton(title);b.clicked.connect(fn);top.addWidget(b)
        v.addLayout(top);self.table=QTableWidget(0,8);self.table.setHorizontalHeaderLabels(['نام / کد','حقوق ثابت؛ ریال','روز','اضافه‌کاری؛ ساعت','مالیات دستی؛ ریال','خالص؛ ریال','تفاوت ماه قبل','وضعیت']);self.table.horizontalHeader().setStretchLastSection(True);self.table.itemChanged.connect(self.change);v.addWidget(self.table,1);self.summary=QLabel('دوره به صورت پیش‌نویس محاسبه می‌شود؛ پیش از پرداخت بررسی شود.');self.summary.setWordWrap(True);v.addWidget(self.summary);row=QHBoxLayout()
        for title,fn in [('ذخیره دوره',self.save),('مجموعه PDF',self.pdf),('دوره‌های ذخیره‌شده',self.saved)]:b=QPushButton(title);b.clicked.connect(fn);row.addWidget(b)
        row.addStretch();v.addLayout(row)
    def showEvent(self,e):
        super().showEvent(e);old=self.company.currentData();self.company.clear()
        for i in range(self.owner.org.company.count()):self.company.addItem(self.owner.org.company.itemText(i),self.owner.org.company.itemData(i))
        self.company.setCurrentIndex(max(0,self.company.findData(old)))
    def load(self):
        co=self.company.currentData();period=normalize(self.period.text());use_attendance=self.attendance.isChecked()
        if not co:return
        def fetch(c):return dict(employees=c.records(co,'employee'),work=c.request('payroll',company=co,month=period) if use_attendance else [],batches=c.records(co,'payroll_batch'))
        def ready(d):
            from storage import parse_j
            import jdatetime
            first=parse_j(period+'/01');end=jdatetime.date(first.year+1,1,1) if first.month==12 else jdatetime.date(first.year,first.month+1,1);days=(end.togregorian()-first.togregorian()).days;report={r['کد پرسنلی']:r for r in d['work']};self.slips=[]
            for r in d['employees']:
                p=r['payload'];work=report.get(p['employee_code'],{});s=dict(copy.deepcopy(self.defaults),name=p['title'],code=p['employee_code'],base=p.get('base_salary') or '0',company=self.company.currentText(),period=period,period_days=str(days),days=str(work.get('روز دارای تردد تأییدشده',0)) if self.attendance.isChecked() else str(days),overtime_hours=str(float(work.get('اضافه دقایق نسبت به موظفی روزهای ثبت‌شده',0))/60),unit='ریال');self.slips.append(s)
            old=next((r for r in d['batches'] if normalize(r['payload'].get('period',''))==previous_month(period)),None);self.previous=old['payload'].get('slips',[]) if old else [];self.draw()
        self.owner.workspace.run(fetch,ready)
    def draw(self):
        self._loading=True;self.table.setRowCount(len(self.slips));diff=[];total=0
        for p in self.slips:
            try:diff.append(compare([p],self.previous)[0])
            except (ValueError,KeyError):diff.append(None)
        for i,p in enumerate(self.slips):
            try:r=compute_payroll(p);net=r['net'];total+=net;state='پیش‌نویس' if net>=0 else 'نیازمند بررسی خالص منفی'
            except Exception as e:net=0;state=str(e)
            for j,value in enumerate([p['name']+' / '+p['code'],p['base'],p['days'],p['overtime_hours'],p['tax_amount'],fa(f'{net:,}'),fa(diff[i]) if diff[i] is not None else 'سابقه ندارد',state]):
                item=QTableWidgetItem(str(value))
                if j not in (1,2,3,4):item.setFlags(item.flags()&~Qt.ItemIsEditable)
                self.table.setItem(i,j,item)
        self.table.resizeColumnsToContents();self.summary.setText('تعداد: '+fa(len(self.slips))+'  ·  جمع خالص: '+fa(f'{total:,}')+' ریال · مالیات و مزایا بر اساس تنظیمات مسئول حقوق');self._loading=False
    def change(self,item):
        if self._loading:return
        keys={1:'base',2:'days',3:'overtime_hours',4:'tax_amount'}
        if item.column() in keys:
            self.slips[item.row()][keys[item.column()]]=normalize(item.text())
            try:self.draw()
            except Exception as e:self.summary.setText(str(e))
    def options(self):
        d=PayrollOptions(self.defaults,self)
        if d.exec():
            self.defaults=d.p
            for p in self.slips:
                for k in ('housing','food','children','seniority','bonus','spouse','transport','lunch','commission','other_benefits','hours_base','overtime_factor','worker_rate','employer_rate','insurance_override','insurance_basis','tax_mode','tax_exemption','tax_rate','tax_deduction','brackets'):p[k]=copy.deepcopy(d.p[k])
            self.draw()
    def person_options(self):
        i=self.table.currentRow()
        if i>=0:
            d=PayrollOptions(self.slips[i],self)
            if d.exec():self.slips[i]=d.p;self.draw()
    def payload(self):return validate_batch(dict(title='حقوق '+normalize(self.period.text()),period=self.period.text(),slips=self.slips,notes='پیش‌نویس محاسبه قابل بررسی؛ پرداخت بانکی انجام نشده است.'))
    def save(self):
        try:p=self.payload()
        except Exception as e:QMessageBox.warning(self,'حقوق گروهی',str(e));return
        self.owner.workspace.mutate('records',dict(kind='payroll_batch',company=self.company.currentData(),payload=p),lambda _:self.summary.setText('نسخه دوره ثبت شد. برای اصلاح، نسخه تازه ذخیره کنید.'))
    def pdf(self):
        try:p=self.payload()
        except Exception as e:QMessageBox.warning(self,'حقوق گروهی',str(e));return
        target,_=QFileDialog.getSaveFileName(self,'مجموعه فیش‌های حقوق','Karname-Payroll-'+normalize(self.period.text()).replace('/','-')+'.zip','ZIP (*.zip)')
        if not target:return
        try:export_collection(target if target.lower().endswith('.zip') else target+'.zip',p);self.summary.setText('فیش‌های جداگانه، PDF تجمیعی و اطلاعات محاسبه آماده شدند.')
        except Exception as e:QMessageBox.warning(self,'خروجی',str(e))
    def saved(self):
        def ready(rows):
            if not rows:QMessageBox.information(self,'دوره‌ها','دوره‌ای ثبت نشده است.');return
            names=[r['title']+' · '+r['updated'][:16] for r in rows];name,ok=QInputDialog.getItem(self,'دوره‌های حقوق','دوره:',names,0,False)
            if ok:p=rows[names.index(name)]['payload'];self.period.setText(p['period']);self.slips=copy.deepcopy(p['slips']);self.draw()
        self.owner.workspace.run(lambda c:c.records(self.company.currentData(),'payroll_batch'),ready)
