"""Company report selection and export using current authorised server data."""
from datetime import timedelta
import jdatetime
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QComboBox,QLineEdit,QLabel,QCheckBox,QPushButton,QFileDialog,QMessageBox,QSpinBox,QFormLayout,QDialogButtonBox)
from storage import normalize,parse_j,today_j,jformat,month_last_day,MONTHS,fa

class JalaliDatePicker(QDialog):
    def __init__(self,value='',parent=None):
        super().__init__(parent);self.setWindowTitle('انتخاب تاریخ شمسی')
        try:date=parse_j(value) if value.strip() else today_j()
        except ValueError:date=today_j()
        layout=QFormLayout(self);self.year=QSpinBox();self.year.setRange(1300,1499);self.year.setValue(date.year);self.month=QComboBox();self.month.addItems(MONTHS);self.month.setCurrentIndex(date.month-1);self.day=QComboBox();layout.addRow('سال',self.year);layout.addRow('ماه',self.month);layout.addRow('روز',self.day);self.refresh_days(date.day);self.month.currentIndexChanged.connect(self.refresh_days);self.year.valueChanged.connect(self.refresh_days);buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addRow(buttons)
    def refresh_days(self,*_):
        previous=self.day.currentData() or (int(_[0]) if _ and isinstance(_[0],int) and self.day.count()==0 else 1);last=month_last_day(self.year.value(),self.month.currentIndex()+1);self.day.blockSignals(True);self.day.clear()
        for n in range(1,last+1):self.day.addItem(fa(n),n)
        self.day.setCurrentIndex(min(previous,last)-1);self.day.blockSignals(False)
    def value(self):return jformat(jdatetime.date(self.year.value(),self.month.currentIndex()+1,self.day.currentData()))

FIELDS={
 'invoice':[('number','شماره فاکتور'),('document_no','شماره سند'),('document_type','نوع فاکتور'),('date','تاریخ'),('buyer','مشتری'),('total','مبلغ ریال'),('status','وضعیت'),('source_quote_number','شماره پیش‌فاکتور مبنا')],
 'client':[('customer_code','شماره مشتری'),('title','نام مشتری'),('national_id','شناسه ملی'),('phone','تلفن')],
 'stock':[('code','کد کالا'),('name','نام کالا'),('unit','واحد'),('balance','موجودی'),('purchase_price','قیمت خرید'),('sale_price','قیمت فروش')],
 'check':[('document_no','شماره سند'),('direction','نوع چک'),('number','شماره چک'),('bank','بانک'),('amount','مبلغ ریال'),('due_date','سررسید'),('status','وضعیت'),('description','توضیحات')],
 'transaction':[('document_no','شماره سند'),('direction','نوع'),('method','روش'),('amount','مبلغ ریال'),('date','تاریخ'),('reason','علت'),('category','دسته‌بندی')],
 'records':[('record_type','نوع پرونده'),('title','عنوان'),('date','تاریخ / موعد'),('status','وضعیت'),('notes','یادداشت')],
}

class ReportDialog(QDialog):
    def __init__(self,panel):
        super().__init__(panel);self.panel=panel;self.setWindowTitle('گزارش‌ها');self.resize(600,500);v=QVBoxLayout(self);self.kind=QComboBox()
        for key,title in [('invoice','فاکتورها'),('client','مشتریان'),('stock','کالا و موجودی'),('check','چک‌ها'),('transaction','دریافت و پرداخت'),('records','پرونده‌های شرکت')]:self.kind.addItem(title,key)
        v.addWidget(self.kind);self.period=QComboBox()
        for key,title in [('all','همه تاریخ‌ها'),('month','ماه جاری'),('previous','ماه قبل'),('year','سال جاری'),('last30','۳۰ روز اخیر'),('custom','بازه دلخواه')]:self.period.addItem(title,key)
        v.addWidget(self.period);dates=QHBoxLayout();self.start=QLineEdit();self.start.setPlaceholderText('از تاریخ شمسی؛ اختیاری');self.end=QLineEdit();self.end.setPlaceholderText('تا تاریخ شمسی؛ اختیاری')
        from ui_icons import iconize,symbol
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette
        for field in (self.start,self.end):
            dates.addWidget(field);pick=QPushButton();iconize(pick,'calendar','انتخاب تاریخ شمسی');pick.clicked.connect(lambda checked=False,w=field:self.choose_date(w));dates.addWidget(pick)
        v.addLayout(dates);v.addWidget(QLabel('بازه شامل روز شروع و پایان است. موجودی و مشتریان گزارش لحظه‌ای هستند.'));self.column_box=QVBoxLayout();v.addLayout(self.column_box);v.addStretch();buttons=QHBoxLayout();v.addLayout(buttons)
        ink=QApplication.palette().color(QPalette.ButtonText).name()
        for title,kind in [('اکسل','xlsx'),('PDF','pdf')]:
            b=QPushButton(title);b.setIcon(symbol('export',ink));b.setProperty('karnameIconKey','export');b.clicked.connect(lambda _,k=kind:self.export(k));buttons.addWidget(b)
        self.kind.currentIndexChanged.connect(self.columns);self.period.currentIndexChanged.connect(self.apply_period);self.start.textEdited.connect(self.custom_period);self.end.textEdited.connect(self.custom_period);self.columns()
    def custom_period(self,*_):
        self.period.blockSignals(True);self.period.setCurrentIndex(self.period.findData('custom'));self.period.blockSignals(False)
    def choose_date(self,field):
        picker=JalaliDatePicker(field.text(),self)
        if picker.exec()==QDialog.Accepted:field.setText(picker.value());self.custom_period()
    def apply_period(self,*_):
        key=self.period.currentData();today=today_j()
        if key=='custom':return
        if key=='all':self.start.clear();self.end.clear();return
        if key=='month':start=jdatetime.date(today.year,today.month,1);end=jdatetime.date(today.year,today.month,month_last_day(today.year,today.month))
        elif key=='previous':
            year,month=(today.year-1,12) if today.month==1 else (today.year,today.month-1);start=jdatetime.date(year,month,1);end=jdatetime.date(year,month,month_last_day(year,month))
        elif key=='year':start=jdatetime.date(today.year,1,1);end=jdatetime.date(today.year,12,month_last_day(today.year,12))
        else:start=jdatetime.date.fromgregorian(date=today.togregorian()-timedelta(days=29));end=today
        self.start.setText(jformat(start));self.end.setText(jformat(end))
    def columns(self):
        while self.column_box.count():
            item=self.column_box.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.checks=[]
        for key,label in FIELDS[self.kind.currentData()]:
            box=QCheckBox(label);box.setChecked(True);self.column_box.addWidget(box);self.checks.append((key,label,box))
    def load_rows(self):
        from personalization_ui import request_wait
        kind=self.kind.currentData();company=self.panel.company.currentData();start=normalize(self.start.text());end=normalize(self.end.text());lower=parse_j(start).togregorian() if start else None;upper=parse_j(end).togregorian() if end else None
        if kind in ('check','transaction'):
            from permission_policy import allowed
            actor=self.panel.owner.session_user
            if actor and not allowed(actor,company,'finance','export'):raise PermissionError('اجازه خروجی گزارش مالی برای این شرکت فعال نیست.')
        if lower and upper and lower>upper:raise ValueError('تاریخ شروع بعد از پایان است.')
        if (lower or upper) and kind not in ('invoice','check','transaction','records'):raise ValueError('برای این گزارش فیلتر تاریخ وجود ندارد؛ تاریخ‌ها را پاک کنید.')
        if kind in ('invoice','client','records'):
            page=1;records=[]
            while True:
                batch=request_wait(self.panel.owner,'records',company=company,kind=None if kind=='records' else kind,limit=500,page=page);records.extend(batch['items'])
                if len(records)>=batch['total']:break
                page+=1
            rows=[]
            for record in records:
                p=record['payload'];p=dict(p)
                if kind=='invoice':p.update(buyer=p.get('customer_snapshot',{}).get('title',''),total=p.get('totals',{}).get('total',''))
                elif kind=='records':
                    from org_schema import SCHEMAS
                    p.update(record_type=SCHEMAS.get(record['kind'],{}).get('label',record['kind']),date=p.get('date') or p.get('due_date') or p.get('start_date') or '')
                rows.append(p)
        elif kind=='stock':rows=[p for p in request_wait(self.panel.owner,'inventory',company=company)['products'] if p['active']]
        else:rows=request_wait(self.panel.owner,'finance',company=company)['checks' if kind=='check' else 'transactions']
        if lower or upper:
            field='due_date' if kind=='check' else 'date';filtered=[]
            for row in rows:
                if not row.get(field):continue
                try:day=parse_j(row[field]).togregorian()
                except ValueError:continue
                if (not lower or day>=lower) and (not upper or day<=upper):filtered.append(row)
            rows=filtered
        if kind=='transaction':
            from finance_ui import METHOD_LABELS
            rows=[dict(r,direction='دریافت' if r['direction']=='income' else 'پرداخت',method=METHOD_LABELS.get(r['method'],r['method'])) for r in rows]
        if kind=='check':rows=[dict(r,direction='دریافتی' if r.get('direction','received')=='received' else 'پرداختی',status={'pending':'در انتظار','deposited':'واگذارشده به بانک','cleared':'وصول‌شده','returned':'برگشتی'}.get(r.get('status','pending'))) for r in rows]
        selected=[(key,label) for key,label,box in self.checks if box.isChecked()]
        if not selected:raise ValueError('حداقل یک ستون را انتخاب کنید.')
        return [{label:row.get(key,'') for key,label in selected} for row in rows]
    def export(self,kind):
        try:
            rows=self.load_rows()
            if not rows:QMessageBox.information(self,'گزارش','موردی برای شرایط انتخابی پیدا نشد.');return
            extension='.xlsx' if kind=='xlsx' else '.pdf';path,_=QFileDialog.getSaveFileName(self,'ذخیره گزارش','Karname-Report'+extension,'Excel (*.xlsx)' if kind=='xlsx' else 'PDF (*.pdf)')
            if not path:return
            if not path.lower().endswith(extension):path+=extension
            from org_reports import spreadsheet,pdf_report
            (spreadsheet if kind=='xlsx' else pdf_report)(path,rows,self.kind.currentText());QMessageBox.information(self,'گزارش','گزارش ذخیره شد.')
        except Exception as exc:QMessageBox.warning(self,'گزارش',str(exc))
