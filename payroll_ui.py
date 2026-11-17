"""Compact payroll form and a shaped Persian, one-page PDF statement."""
import copy,html
from pathlib import Path
from PySide6.QtCore import Qt,QMarginsF,QSizeF
from PySide6.QtGui import QPdfWriter,QPageSize,QPageLayout,QTextDocument,QFont
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QComboBox,QLabel,QPushButton,QFrame,QDialog,QDialogButtonBox,QTableWidget,QTableWidgetItem,QCheckBox,QMessageBox,QFileDialog,QGridLayout)
from storage import fa,today_j,jformat
from payroll import compute_payroll
from ui_icons import iconize

DEFAULTS=dict(base='0',days='30',period_days='30',hours_base='220',overtime_hours='0',overtime_factor='1.4',night_hours='0',night_factor='0.35',housing='0',food='0',children='0',seniority='0',bonus='0',insurance_basis='0',worker_rate='7',employer_rate='23',insurance_override=False,tax_override=False,tax_basis='0',tax_deduction='0',tax_exemption='0',tax_rate='0',tax_amount='0',tax_mode='manual',advance='0',loan='0',other_deductions='0',brackets=[],unit='ریال',name='',code='',company='',period='')
LABELS=dict(wage='حقوق کارکرد',overtime='اضافه‌کاری',night='شب‌کاری',benefits='جمع مزایا',gross='حقوق ناخالص',insurance='بیمه سهم فرد',company_insurance='بیمه سهم کارفرما',tax='مالیات',deductions='سایر کسورات',net='خالص پرداختی',employer_cost='هزینه کارفرما')

def payroll_pdf(path,p,result):
    esc=lambda s:html.escape(str(s));money=lambda x:fa(f'{x:,.0f}')+' '+p.get('unit','ریال')
    writer=QPdfWriter(str(path));writer.setTitle('فیش محاسبه حقوق - '+p.get('name',''));writer.setCreator('کارنامه');writer.setResolution(120);writer.setPageSize(QPageSize(QPageSize.A4));writer.setPageMargins(QMarginsF(16,16,16,16),QPageLayout.Millimeter)
    rows=''.join('<tr><td>'+esc(v)+'</td><td dir="rtl">'+esc(money(result[k]))+'</td></tr>' for k,v in LABELS.items() if k not in ('net','employer_cost'))
    meta=' | '.join(esc(p.get(k,'')) for k in ('company','name','code','period') if p.get(k))
    tax_name={'manual':'مبلغ مالیات ورودی','flat':'نرخ ثابت و معافیت ورودی','progressive':'جدول پلکانی تعریف‌شده توسط کاربر'}[p.get('tax_mode','manual')]
    doc=QTextDocument();doc.setDefaultFont(QFont('Vazirmatn',11));doc.setHtml('''<html dir="rtl"><head><style>body { color:#19354b; font-family:Vazirmatn; } h1 { color:#10766f; } table {border-collapse:collapse; width:100%;} td {padding:9px; border-bottom:1px solid #d8e2eb;} .muted { color:#50657a;font-size:10pt; }</style></head><body><h1>کارنامه | صورت محاسبه حقوق</h1><p>'''+meta+'''</p><p class="muted">تاریخ تهیه: '''+esc(jformat(today_j()))+''' | برآورد بر پایه ورودی‌های ثبت‌شده</p><table width="100%">'''+rows+'''</table><h2 style="background-color:#daf1e9;">خالص پرداختی: '''+esc(money(result['net']))+'''</h2><p>هزینه کارفرما: '''+esc(money(result['employer_cost']))+'''</p><p class="muted">کارکرد: '''+esc(f"{p['days']} / {p['period_days']}")+''' روز | اضافه‌کاری: '''+esc(p['overtime_hours'])+''' ساعت | ضریب: '''+esc(p['overtime_factor'])+''' | ساعات مبنای ماه: '''+esc(p['hours_base'])+'''</p><p class="muted">روش مالیات: '''+esc(tax_name)+''' | بیمه فرد: '''+esc(p['worker_rate'])+'''٪ | کارفرما: '''+esc(p['employer_rate'])+'''٪</p><p class="muted">مبلغ‌ها و نرخ‌ها قابل ویرایش‌اند. این خروجی برای بررسی و تأیید مسئول حقوق و دستمزد تهیه شده است.</p></body></html>''');doc.print_(writer)
    if not Path(path).is_file() or Path(path).stat().st_size<1000:raise ValueError('فایل PDF ساخته نشد.')
    return path

class PayrollOptions(QDialog):
    def __init__(self,p,parent=None):
        super().__init__(parent);self.setWindowTitle('جزئیات و نرخ‌های حقوق');self.setLayoutDirection(Qt.RightToLeft);self.resize(880,650);v=QVBoxLayout(self);grid=QGridLayout();v.addLayout(grid);self.fields={};self.p=copy.deepcopy(p)
        groups=[ [('housing','مسکن'),('food','بن و خوراک'),('children','فرزند / تأهل'),('seniority','سنوات ماه'),('bonus','پاداش'),('advance','مساعده'),('loan','قسط وام'),('other_deductions','سایر کسورات')], [('hours_base','ساعات مبنای ماه'),('overtime_factor','ضریب اضافه‌کاری'),('night_hours','ساعات شب‌کاری'),('night_factor','ضریب شب‌کاری'),('worker_rate','بیمه فرد (٪)'),('employer_rate','بیمه کارفرما (٪)'),('insurance_basis','مبلغ مشمول بیمه'),('tax_basis','مبلغ مشمول مالیات')], [('tax_amount','مالیات دستی'),('tax_exemption','معافیت نرخ ثابت'),('tax_rate','نرخ ثابت (٪)'),('tax_deduction','کسورات از مبنای مالیات')]]
        for col,items in enumerate(groups):
            form=QFormLayout();form.setSpacing(7);grid.addLayout(form,0,col)
            for key,title in items:w=QLineEdit(str(p.get(key,DEFAULTS.get(key,'0'))));self.fields[key]=w;form.addRow(title,w)
        self.ins=QCheckBox('مبنای بیمه را خودم تعیین می‌کنم');self.ins.setChecked(p['insurance_override']);self.tax=QCheckBox('مبنای مالیات را خودم تعیین می‌کنم');self.tax.setChecked(p['tax_override']);v.addWidget(self.ins);v.addWidget(self.tax)
        row=QHBoxLayout();row.addWidget(QLabel('روش مالیات'));self.mode=QComboBox()
        for title,key in [('مبلغ دستی','manual'),('نرخ ثابت با معافیت','flat'),('جدول پلکانی شخصی','progressive')]:self.mode.addItem(title,key)
        self.mode.setCurrentIndex(self.mode.findData(p['tax_mode']));row.addWidget(self.mode);row.addStretch();v.addLayout(row)
        self.table=QTableWidget(6,2);self.table.setHorizontalHeaderLabels(['سقف تجمعی پله؛ آخرین سقف خالی','نرخ درصد']);self.table.horizontalHeader().setStretchLastSection(True);self.table.setMaximumHeight(175);v.addWidget(self.table)
        for i,b in enumerate(p.get('brackets',[])[:6]):self.table.setItem(i,0,QTableWidgetItem(str(b.get('cap',''))));self.table.setItem(i,1,QTableWidgetItem(str(b['rate'])))
        tip=QLabel('جدول با واحد انتخابی است؛ اولین پله معاف را با نرخ صفر وارد کنید. نرخ‌ها را از بخشنامه معتبر پرونده تعیین کنید.');tip.setWordWrap(True);v.addWidget(tip);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('ذخیره');buttons.button(QDialogButtonBox.Cancel).setText('انصراف');buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);v.addWidget(buttons)
    def validate(self):
        try:
            self.p.update({k:w.text() for k,w in self.fields.items()});self.p.update(insurance_override=self.ins.isChecked(),tax_override=self.tax.isChecked(),tax_mode=self.mode.currentData());self.p['brackets']=[]
            for i in range(self.table.rowCount()):
                rate=self.table.item(i,1);cap=self.table.item(i,0)
                if rate and rate.text().strip():self.p['brackets'].append(dict(cap=cap.text().strip() if cap else '',rate=rate.text().strip()))
            compute_payroll(self.p);self.accept()
        except Exception as e:QMessageBox.warning(self,'حقوق',str(e))

class PayrollPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.p=dict(DEFAULTS,**owner.data.get('payroll_current',{}));self.fields={};v=QVBoxLayout(self);v.setContentsMargins(18,14,18,14);header=QHBoxLayout();title=QLabel('حقوق و دستمزد');title.setObjectName('Hero');header.addWidget(title);header.addStretch();self.saved=QComboBox();self.saved.setMinimumWidth(180);self.saved.addItem('فیش‌های ذخیره‌شده',None)
        for x in owner.data.get('payroll_slips',[]):self.saved.addItem(x.get('name','')+' | '+x.get('period',''),x)
        self.saved.currentIndexChanged.connect(self.load_slip);header.addWidget(self.saved);v.addLayout(header);grid=QGridLayout();v.addLayout(grid)
        groups=[[('name','نام و نام خانوادگی'),('code','شماره پرسنلی'),('company','شرکت'),('period','دوره / ماه')],[('base','حقوق ثابت ماه'),('days','روز کارکرد'),('period_days','روزهای دوره'),('overtime_hours','ساعت اضافه‌کاری')]]
        for col,items in enumerate(groups):
            card=QFrame();card.setObjectName('Panel');form=QFormLayout(card);form.setSpacing(10)
            for key,label in items:w=QLineEdit(str(self.p[key]));w.setAccessibleName(label);self.fields[key]=w;form.addRow(label,w);w.textChanged.connect(self.compute)
            grid.addWidget(card,0,col)
        row=QHBoxLayout();self.unit=QComboBox();self.unit.addItems(['ریال','تومان']);self.unit.setCurrentText(self.p['unit']);self.unit.currentTextChanged.connect(self.compute);row.addWidget(self.unit);row.addWidget(QPushButton('جزئیات و نرخ‌ها',clicked=self.options));row.addStretch()
        for title,key,fn in [('محاسبه','refresh',self.compute),('ذخیره فیش','save',self.save_slip),('خروجی PDF','export',self.export_pdf)]:b=QPushButton(title);iconize(b,key,title);b.clicked.connect(fn);row.addWidget(b)
        v.addLayout(row);self.result=QLabel();self.result.setObjectName('Result');self.result.setWordWrap(True);self.result.setTextInteractionFlags(Qt.TextSelectableByMouse);v.addWidget(self.result);self.detail=QLabel();self.detail.setWordWrap(True);v.addWidget(self.detail);v.addStretch();self.compute()
    def values(self):return dict(self.p,**{k:w.text() for k,w in self.fields.items()},unit=self.unit.currentText())
    def compute(self,*_):
        if not hasattr(self,'result'):return
        try:
            p=self.values();r=compute_payroll(p);self.current=r;money=lambda x:fa(f'{x:,.0f}')+' '+p['unit'];self.result.setText('خالص پرداختی  '+money(r['net'])+'\nناخالص  '+money(r['gross'])+'   |   اضافه‌کاری  '+money(r['overtime']));self.detail.setText('بیمه فرد: '+money(r['insurance'])+'   ·   مالیات: '+money(r['tax'])+'   ·   کسورات: '+money(r['deductions'])+'\nبیمه کارفرما: '+money(r['company_insurance'])+'   ·   مزایا: '+money(r['benefits'])+'   ·   شب‌کاری: '+money(r['night'])+'\n'+{'manual':'مالیات: مبلغ ورودی شما','flat':'مالیات: نرخ ثابت و معافیت ورودی','progressive':'مالیات: جدول پلکانی تعریف‌شده'}[p['tax_mode']])
        except Exception as e:self.current=None;self.result.setText(str(e));self.detail.clear()
    def options(self):
        d=PayrollOptions(self.values(),self)
        if d.exec():self.p=d.p;self.compute()
    def save_slip(self):
        if self.current is None:return
        p=self.values()
        if not p['name'].strip():QMessageBox.warning(self,'حقوق','نام فرد را وارد کنید.');return
        self.owner.data['payroll_current']=p;slips=self.owner.data.setdefault('payroll_slips',[]);key=(p['name'],p['period']);slips[:]=[x for x in slips if (x['name'],x['period'])!=key];slips.append(copy.deepcopy(p));self.owner.persist();self.saved.blockSignals(True);self.saved.clear();self.saved.addItem('فیش‌های ذخیره‌شده',None)
        for x in slips:self.saved.addItem(x['name']+' | '+x['period'],x)
        self.saved.blockSignals(False);self.owner.statusBar().showMessage('فیش ذخیره شد.',5000)
    def load_slip(self):
        p=self.saved.currentData()
        if not p:return
        self.p=copy.deepcopy(p)
        for k,w in self.fields.items():w.setText(str(p[k]))
        self.unit.setCurrentText(p['unit']);self.compute()
    def export_pdf(self):
        if self.current is None:return
        name,_=QFileDialog.getSaveFileName(self,'خروجی فیش حقوق','Karname-Payroll.pdf','PDF (*.pdf)')
        if name:
            try:payroll_pdf(name if name.lower().endswith('.pdf') else name+'.pdf',self.values(),self.current);self.owner.statusBar().showMessage('PDF آماده شد.',5000)
            except Exception as e:QMessageBox.warning(self,'PDF',str(e))
