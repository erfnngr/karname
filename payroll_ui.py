"""Compact payroll form and a shaped Persian, one-page PDF statement."""
import copy,html
from pathlib import Path
from PySide6.QtCore import Qt,QMarginsF,QSizeF
from PySide6.QtGui import QPdfWriter,QPageSize,QPageLayout,QTextDocument,QFont
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QComboBox,QLabel,QPushButton,QFrame,QDialog,QDialogButtonBox,QTableWidget,QTableWidgetItem,QCheckBox,QMessageBox,QFileDialog,QGridLayout,QScrollArea)
from storage import fa,today_j,jformat,normalize
from payroll import compute_payroll
from ui_icons import iconize

DEFAULTS=dict(base='0',days='30',period_days='30',hours_base='220',overtime_hours='0',overtime_factor='1.4',night_hours='0',night_factor='0.35',housing='0',food='0',children='0',seniority='0',bonus='0',insurance_basis='0',worker_rate='7',employer_rate='23',insurance_override=False,tax_override=False,tax_basis='0',tax_deduction='0',tax_exemption='0',tax_rate='0',tax_amount='0',tax_mode='manual',advance='0',loan='0',other_deductions='0',brackets=[],unit='ریال',name='',code='',company='',period='')
DEFAULTS.update(spouse='0',transport='0',lunch='0',commission='0',other_benefits='0',father_name='',birth_certificate='',birth_date='',education='',employment_date='',employment_type='',department='',cost_center='',job_title='',previous_job='',workplace='',job_group='',grade='',order_type='',order_description='',order_date='',effective_date='',signer='')
LABELS=dict(wage='حقوق کارکرد',overtime='اضافه‌کاری',night='شب‌کاری',benefits='جمع مزایا',gross='حقوق ناخالص',insurance='بیمه سهم فرد',company_insurance='بیمه سهم کارفرما',tax='مالیات',deductions='سایر کسورات',net='خالص پرداختی',employer_cost='هزینه کارفرما')

def payroll_identity(p):
    company=normalize(str(p.get('company',''))).strip().casefold()
    code=normalize(str(p.get('code',''))).strip()
    name=normalize(str(p.get('name',''))).strip().casefold()
    return (company,('code',code) if code else ('name',name),normalize(str(p.get('period',''))).strip())

def payroll_period_key(p):
    from storage import parse_j
    try:
        date=parse_j(normalize(str(p.get('period',''))).strip().replace('-','/')+'/01')
        return (date.year,date.month)
    except ValueError:return (0,0)

def payroll_pdf(path,p,result):
    esc=lambda s:html.escape(str(s));money=lambda x:fa(f'{x:,.0f}')+' '+p.get('unit','ریال')
    writer=QPdfWriter(str(path));writer.setTitle('فیش محاسبه حقوق - '+p.get('name',''));writer.setCreator('کارنامه');writer.setResolution(120);writer.setPageSize(QPageSize(QPageSize.A4));writer.setPageMargins(QMarginsF(16,16,16,16),QPageLayout.Millimeter)
    rows=''.join('<tr><td>'+esc(v)+'</td><td dir="rtl">'+esc(money(result[k]))+'</td></tr>' for k,v in LABELS.items() if k not in ('net','employer_cost'))
    meta=' | '.join(esc(p.get(k,'')) for k in ('company','name','code','period') if p.get(k))
    tax_name={'manual':'مبلغ مالیات ورودی','flat':'نرخ ثابت و معافیت ورودی','progressive':'جدول پلکانی تعریف‌شده توسط کاربر'}[p.get('tax_mode','manual')]
    doc=QTextDocument();doc.setDefaultFont(QFont('Vazirmatn',11));doc.setHtml('''<html dir="rtl"><head><style>body { color:#19354b; font-family:Vazirmatn; } h1 { color:#10766f; } table {border-collapse:collapse; width:100%;} td {padding:9px; border-bottom:1px solid #d8e2eb;} .muted { color:#50657a;font-size:10pt; }</style></head><body><h1>کارنامه | صورت محاسبه حقوق</h1><p>'''+meta+'''</p><p class="muted">تاریخ تهیه: '''+esc(jformat(today_j()))+''' | برآورد بر پایه ورودی‌های ثبت‌شده</p><table width="100%">'''+rows+'''</table><h2 style="background-color:#daf1e9;">خالص پرداختی: '''+esc(money(result['net']))+'''</h2><p>هزینه کارفرما: '''+esc(money(result['employer_cost']))+'''</p><p class="muted">کارکرد: '''+esc(f"{p['days']} / {p['period_days']}")+''' روز | اضافه‌کاری: '''+esc(p['overtime_hours'])+''' ساعت | ضریب: '''+esc(p['overtime_factor'])+''' | ساعات مبنای ماه: '''+esc(p['hours_base'])+'''</p><p class="muted">روش مالیات: '''+esc(tax_name)+''' | بیمه فرد: '''+esc(p['worker_rate'])+'''٪ | کارفرما: '''+esc(p['employer_rate'])+'''٪</p><p class="muted">مبلغ‌ها و نرخ‌ها قابل ویرایش‌اند. این خروجی برای بررسی و تأیید مسئول حقوق و دستمزد تهیه شده است.</p></body></html>''');doc.print_(writer)
    if not Path(path).is_file() or Path(path).stat().st_size<1000:raise ValueError('فایل PDF ساخته نشد.')
    return path

def payroll_order_pdf(path,p):
    """Printable draft order: contractual components, not a paid payslip."""
    from penalties import number
    from storage import package_file
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QFontDatabase
    esc=lambda x:html.escape(str(x or ''))
    unit=esc(p.get('unit','ریال'))
    fields=[('base','حقوق پایه'),('seniority','حق سنوات'),('housing','حق مسکن'),('food','کمک‌هزینه خواربار'),('other_benefits','سایر'),('children','حق اولاد'),('spouse','حق تأهل'),('transport','ایاب و ذهاب'),('lunch','ناهار'),('commission','کارانه'),('bonus','پاداش')]
    values=[number(p.get(key,'0')) for key,_ in fields]
    def money(value):return fa(f'{value:,.0f}')
    def cell(label,key):return '<td align="right"><b>'+esc(label)+':</b> '+esc(p.get(key,''))+'</td>'
    rows=''.join('<tr><td align="right">'+esc(label)+'</td><td align="center">'+esc(money(value))+'</td></tr>' for (_,label),value in zip(fields,values))
    company=str(p.get('company',''));logo='mana.jpg' if 'مانا' in company else 'airia.jpg' if 'آیریا' in company or 'ایریا' in company else 'arka.jpg' if 'آرکا' in company or 'ارکا' in company else 'karname.png'
    img=esc(QUrl.fromLocalFile(str(package_file('assets/'+logo))).toString())
    writer=QPdfWriter(str(path));writer.setTitle('پیش‌نویس حکم حقوقی');writer.setCreator('کارنامه');writer.setResolution(120);writer.setPageSize(QPageSize(QPageSize.A4));writer.setPageMargins(QMarginsF(10,10,10,10),QPageLayout.Millimeter)
    font_id=QFontDatabase.addApplicationFont(str(package_file('assets/Vazirmatn-Regular.ttf')))
    families=QFontDatabase.applicationFontFamilies(font_id) if font_id>=0 else []
    doc=QTextDocument();doc.setDefaultFont(QFont(families[0] if families else 'Arial',9))
    doc.setHtml(('''<html dir="rtl"><head><style>body{color:#172b3b;font-size:9pt} table{border-collapse:collapse;width:100%} td{border:1px solid #71808a;padding:5px} h2{text-align:center;font-size:14pt} .note{font-size:8pt;color:#52616a}</style></head><body>
    <table><tr><td width="18%" align="center"><img src="'''+img+'''" width="62" height="62"></td><td width="52%" align="center"><h2>'''+esc(company)+'''</h2><b>پیش‌نویس حکم حقوقی</b></td><td>کد پرسنلی: '''+esc(p.get('code',''))+'''<br>تاریخ استخدام: '''+esc(p.get('employment_date',''))+'''<br>نوع استخدام: '''+esc(p.get('employment_type',''))+'''</td></tr></table>
    <table><tr>'''+cell('نام و نام خانوادگی','name')+cell('نام پدر','father_name')+'''</tr><tr>'''+cell('شماره شناسنامه','birth_certificate')+cell('تاریخ تولد','birth_date')+cell('مدرک و رشته','education')+'''</tr><tr>'''+cell('واحد','department')+cell('مرکز هزینه','cost_center')+'''</tr><tr>'''+cell('عنوان شغل','job_title')+cell('شغل قبلی','previous_job')+'''</tr><tr>'''+cell('محل خدمت','workplace')+cell('گروه','job_group')+cell('پایه','grade')+'''</tr><tr>'''+cell('دوره','period')+cell('نوع حکم','order_type')+'''</tr></table>
    <table><tr><td width="50%" valign="top"><b>شرح حکم</b><br>'''+esc(p.get('order_description',''))+'''</td><td width="50%" valign="top"><table><tr><td><b>حقوق و مزایا</b></td><td align="center"><b>مبلغ ('''+unit+''')</b></td></tr>'''+rows+'''<tr><td><b>جمع اقلام حکم</b></td><td align="center"><b>'''+esc(money(sum(values)))+'''</b></td></tr></table></td></tr></table>
    <p class="note">جمع اقلام حکم بر مبنای مبالغ واردشده است؛ خالص پرداختی و کسورات ماهانه در فیش محاسباتی جداگانه مشخص می‌شود.</p>
    <table><tr>'''+cell('تاریخ اجرای حکم','effective_date')+cell('تاریخ صدور حکم','order_date')+'''</tr><tr><td colspan="2" height="65" align="right">نام و سمت مسئول: '''+esc(p.get('signer',''))+'''<br><br>امضا و مهر:</td></tr></table></body></html>''').replace('<table>','<table width="100%">'))
    doc.print_(writer)
    if not Path(path).is_file() or Path(path).stat().st_size<1000:raise ValueError('فایل PDF ساخته نشد.')
    return path

class PayrollOptions(QDialog):
    def __init__(self,p,parent=None):
        super().__init__(parent);self.setWindowTitle('جزئیات و نرخ‌های حقوق');self.setLayoutDirection(Qt.RightToLeft);self.resize(880,650);v=QVBoxLayout(self);grid=QGridLayout();v.addLayout(grid);self.fields={};self.p=copy.deepcopy(p)
        groups=[ [('housing','مسکن'),('food','بن و خوراک'),('children','حق اولاد'),('spouse','حق تأهل'),('seniority','سنوات ماه'),('bonus','پاداش'),('transport','ایاب و ذهاب'),('lunch','ناهار'),('commission','کارانه'),('other_benefits','سایر مزایا'),('advance','مساعده'),('loan','قسط وام'),('other_deductions','سایر کسورات')], [('hours_base','ساعات مبنای ماه'),('overtime_factor','ضریب اضافه‌کاری'),('night_hours','ساعات شب‌کاری'),('night_factor','ضریب شب‌کاری'),('worker_rate','بیمه فرد (٪)'),('employer_rate','بیمه کارفرما (٪)'),('insurance_basis','مبلغ مشمول بیمه'),('tax_basis','مبلغ مشمول مالیات')], [('tax_amount','مالیات دستی'),('tax_exemption','معافیت نرخ ثابت'),('tax_rate','نرخ ثابت (٪)'),('tax_deduction','کسورات از مبنای مالیات')]]
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
        row=QHBoxLayout();self.unit=QComboBox();self.unit.addItems(['ریال','تومان']);self.unit.setCurrentText(self.p['unit']);self.unit.currentTextChanged.connect(self.compute);row.addWidget(self.unit);row.addWidget(QPushButton('جزئیات و نرخ‌ها',clicked=self.options));row.addWidget(QPushButton('مشخصات حکم',clicked=self.order_details));row.addWidget(QPushButton('بازیابی اطلاعات فرد',clicked=self.load_person_defaults));row.addStretch()
        for title,key,fn in [('محاسبه','refresh',self.compute),('ذخیره فیش','save',self.save_slip),('خروجی PDF','export',self.export_pdf)]:b=QPushButton(title);iconize(b,key,title);b.clicked.connect(fn);row.addWidget(b)
        row.addWidget(QPushButton('PDF حکم حقوقی',clicked=self.export_order_pdf))
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
    def order_details(self):
        d=QDialog(self);d.setWindowTitle('مشخصات حکم حقوقی');d.resize(560,600);layout=QVBoxLayout(d);scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();form=QFormLayout(body);scroll.setWidget(body);layout.addWidget(scroll);fields={}
        for key,label in [('father_name','نام پدر'),('birth_certificate','شماره شناسنامه'),('birth_date','تاریخ تولد'),('education','مدرک و رشته تحصیلی'),('employment_date','تاریخ استخدام'),('employment_type','نوع استخدام'),('department','واحد'),('cost_center','مرکز هزینه'),('job_title','عنوان شغل'),('previous_job','شغل قبلی'),('workplace','محل خدمت'),('job_group','گروه'),('grade','پایه'),('order_type','نوع حکم'),('order_description','شرح حکم'),('order_date','تاریخ صدور حکم'),('effective_date','تاریخ اجرای حکم'),('signer','نام و سمت مسئول')]:
            fields[key]=QLineEdit(str(self.p.get(key,'')));form.addRow(label,fields[key])
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);layout.addWidget(buttons)
        if d.exec()==QDialog.Accepted:self.p.update({key:widget.text().strip() for key,widget in fields.items()})
    def load_person_defaults(self):
        code=self.fields['code'].text().strip();company=self.fields['company'].text().strip();period=self.fields['period'].text()
        if not code or not company:QMessageBox.information(self,'بازیابی اطلاعات','ابتدا شرکت و شماره پرسنلی را وارد کنید.');return
        identity=payroll_identity(dict(code=code,company=company))[:2]
        matches=[x for x in self.owner.data.get('payroll_slips',[]) if payroll_identity(x)[:2]==identity]
        if not matches:QMessageBox.information(self,'بازیابی اطلاعات','فیش ذخیره‌شده‌ای برای این فرد و شرکت پیدا نشد.');return
        matches.sort(key=payroll_period_key);self.p=dict(DEFAULTS,**copy.deepcopy(matches[-1]));self.p['period']=period
        for key,widget in self.fields.items():widget.setText(str(self.p.get(key,'')))
        self.unit.setCurrentText(self.p['unit']);self.compute()
    def save_slip(self):
        if self.current is None:return
        p=self.values()
        if not p['name'].strip():QMessageBox.warning(self,'حقوق','نام فرد را وارد کنید.');return
        self.owner.data['payroll_current']=p;slips=self.owner.data.setdefault('payroll_slips',[]);key=payroll_identity(p);slips[:]=[x for x in slips if payroll_identity(x)!=key];slips.append(copy.deepcopy(p));self.owner.persist();self.saved.blockSignals(True);self.saved.clear();self.saved.addItem('فیش‌های ذخیره‌شده',None)
        for x in slips:self.saved.addItem(x['name']+' | '+x['period'],x)
        self.saved.blockSignals(False);self.owner.statusBar().showMessage('فیش ذخیره شد.',5000)
    def load_slip(self):
        p=self.saved.currentData()
        if not p:return
        self.p=dict(DEFAULTS,**copy.deepcopy(p))
        for k,w in self.fields.items():w.setText(str(self.p.get(k,'')))
        self.unit.setCurrentText(p['unit']);self.compute()
    def export_pdf(self):
        if self.current is None:return
        name,_=QFileDialog.getSaveFileName(self,'خروجی فیش حقوق','Karname-Payroll.pdf','PDF (*.pdf)')
        if name:
            try:payroll_pdf(name if name.lower().endswith('.pdf') else name+'.pdf',self.values(),self.current);self.owner.statusBar().showMessage('PDF آماده شد.',5000)
            except Exception as e:QMessageBox.warning(self,'PDF',str(e))
    def export_order_pdf(self):
        if self.current is None:return
        name,_=QFileDialog.getSaveFileName(self,'خروجی حکم حقوقی','Karname-Payroll-Order.pdf','PDF (*.pdf)')
        if name:
            try:payroll_order_pdf(name if name.lower().endswith('.pdf') else name+'.pdf',self.values());self.owner.statusBar().showMessage('پیش‌نویس حکم حقوقی آماده شد.',5000)
            except Exception as e:QMessageBox.warning(self,'PDF حکم',str(e))
