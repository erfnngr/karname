"""Company-scoped, explicit draft editor for monthly insurance."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,
 QComboBox,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QDialogButtonBox,QMessageBox,QCheckBox)
from storage import today_j
from insurance_monthly import normalize_draft
from personalization_ui import request_wait
from permission_policy import allowed


class InsuranceListEditor(QDialog):
    def __init__(self,panel,company,record=None):
        super().__init__(panel);self.panel=panel;self.company_id=company;self.record=record;self.payload=None
        self.setWindowTitle('ویرایش پیش‌نویس بیمه' if record else 'پیش‌نویس لیست بیمه');self.resize(1080,650)
        root=QVBoxLayout(self);notice=QLabel('پیش‌نویس فقط اطلاعات واردشده را نگه می‌دارد. حقوق نهایی، محاسبه قانونی، تأیید، ارسال و پرداخت در این مرحله انجام نمی‌شوند.');notice.setWordWrap(True);root.addWidget(notice)
        p=record['payload'] if record else {};form=QFormLayout();root.addLayout(form)
        self.title=QLineEdit(p.get('title',''));self.period=QLineEdit(p.get('period',f'{today_j().year:04d}/{today_j().month:02d}'));self.number=QLineEdit(p.get('list_no',''));self.list_type=QLineEdit(p.get('list_type',''));self.notes=QLineEdit(p.get('notes',''))
        self.workshop=QComboBox();self.workshop.addItem('انتخاب کارگاه',None)
        for r in panel.owner.org.records:
            if r.get('company_id')==company and r.get('kind')=='insurance_workshop':self.workshop.addItem(r['title'],r['id'])
        self.workshop.setCurrentIndex(max(0,self.workshop.findData(p.get('workshop_id'))));self.workshop.setEnabled(record is None);self.period.setReadOnly(record is not None)
        for label,w in [('عنوان',self.title),('کارگاه',self.workshop),('ماه شمسی',self.period),('شماره لیست',self.number),('نوع لیست',self.list_type),('توضیحات',self.notes)]:form.addRow(label,w)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(['انتخاب کارمند','روز بیمه','مزد روزانه','سنوات روزانه','مزایای مشمول','مزایای غیرمشمول','بیمه بیکاری']);self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive);root.addWidget(self.table,1)
        self.saved={row['profile_id']:row for row in p.get('rows',[])}
        self.workshop.currentIndexChanged.connect(self.populate);self.populate()
        calculate=QPushButton('محاسبه و کنترل آزمایشی');calculate.clicked.connect(self.calculate);root.addWidget(calculate)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('ذخیره پیش‌نویس');buttons.accepted.connect(self.validate_and_accept);buttons.rejected.connect(self.reject);root.addWidget(buttons)

    def populate(self):
        workshop=self.workshop.currentData();records=self.panel.owner.org.records
        profiles=[r for r in records if r.get('kind')=='insurance_employee' and r.get('company_id')==self.company_id and r['payload'].get('workshop_id')==workshop]
        present={r['id'] for r in profiles}
        for profile_id in self.saved:
            if profile_id not in present:profiles.append({'id':profile_id,'title':'پرونده در دسترس نیست','payload':{}})
        self.table.setRowCount(len(profiles))
        for i,profile in enumerate(profiles):
            row=self.saved.get(profile['id'],{});person=QTableWidgetItem(profile['title']);person.setData(Qt.UserRole,profile['id']);person.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);person.setCheckState(Qt.Checked if row else Qt.Unchecked);self.table.setItem(i,0,person)
            for col,key in enumerate(('days','daily_wage','daily_seniority','insured_benefits','non_insured_benefits'),1):self.table.setItem(i,col,QTableWidgetItem(str(row.get(key,''))))
            choice=QComboBox();choice.addItem('نامشخص',None);choice.addItem('مشمول',True);choice.addItem('غیرمشمول',False)
            value=row.get('unemployment_applies');choice.setCurrentIndex(1 if value is True else 2 if value is False else 0);self.table.setCellWidget(i,6,choice)

    def draft_values(self):
        rows=[]
        for i in range(self.table.rowCount()):
            person=self.table.item(i,0)
            if person.checkState()!=Qt.Checked:continue
            row={'profile_id':person.data(Qt.UserRole),'unemployment_applies':self.table.cellWidget(i,6).currentData()}
            for col,key in enumerate(('days','daily_wage','daily_seniority','insured_benefits','non_insured_benefits'),1):
                item=self.table.item(i,col);row[key]=item.text() if item else ''
            rows.append(row)
        return normalize_draft(dict(title=self.title.text(),period=self.period.text(),list_no=self.number.text(),list_type=self.list_type.text(),notes=self.notes.text(),workshop_id=self.workshop.currentData() or '',rows=rows,status='draft'))

    def validate_and_accept(self):
        try:
            self.payload=self.draft_values()
        except ValueError as exc:QMessageBox.warning(self,'بررسی پیش‌نویس',str(exc));return
        self.accept()

    def calculate(self):
        from insurance_monthly import calculate_draft
        try:draft=self.draft_values()
        except ValueError as exc:QMessageBox.warning(self,'بررسی پیش‌نویس',str(exc));return
        d=QDialog(self);d.setWindowTitle('قواعد تأییدشده برای محاسبه آزمایشی');layout=QVBoxLayout(d);note=QLabel('نرخ‌ها و حدود را از منبع معتبر برای همین دوره و شرایط کارکنان وارد کنید. نتیجه صرفاً آزمایشی است و ذخیره یا ارسال نمی‌شود.');note.setWordWrap(True);layout.addWidget(note);form=QFormLayout();layout.addLayout(form)
        fields={}
        for key,label in [('worker_rate','درصد سهم کارمند'),('employer_rate','درصد سهم کارفرما'),('unemployment_rate','درصد بیمه بیکاری'),('minimum_daily','حداقل روزانه به ریال'),('maximum_daily','حداکثر روزانه به ریال'),('rules_version','شناسه نسخه قواعد'),('source','منبع و تاریخ اعتبار')]:
            fields[key]=QLineEdit();form.addRow(label,fields[key])
        versions=QComboBox();versions.addItem('ورود دستی قواعد',None)
        for record in self.panel.owner.org.records:
            if record.get('kind')=='insurance_rules' and record.get('company_id')==self.company_id:
                p=record['payload'];versions.addItem(p['title']+' · '+p['rules_version'],p)
        form.insertRow(0,'نسخه ثبت‌شده',versions)
        def select_version():
            p=versions.currentData()
            if not p:return
            from storage import parse_j,month_last_day
            start=parse_j(draft['period']+'/01');end=parse_j(draft['period']+'/'+str(month_last_day(start.year,start.month)))
            if not p.get('approved') or parse_j(p['effective_from'])>start or parse_j(p['effective_to'])<end:
                QMessageBox.warning(d,'نسخه قواعد','این نسخه تأیید نشده یا تمام ماه را پوشش نمی‌دهد.');versions.setCurrentIndex(0);return
            for key,w in fields.items():w.setText(p[key])
        versions.currentIndexChanged.connect(select_version)
        approved=QCheckBox('اعتبار این قواعد را برای دوره و تمام افراد انتخاب‌شده بررسی کرده‌ام');layout.addWidget(approved)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('محاسبه');buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);layout.addWidget(buttons)
        if d.exec()!=QDialog.Accepted:return
        try:result=calculate_draft(draft,{**{key:w.text() for key,w in fields.items()},'approved':approved.isChecked()})
        except ValueError as exc:QMessageBox.warning(self,'محاسبه',str(exc));return
        names={self.table.item(i,0).data(Qt.UserRole):self.table.item(i,0).text() for i in range(self.table.rowCount())}
        if result['errors']:
            QMessageBox.warning(self,'ردیف‌های نیازمند اصلاح','\n'.join(names.get(e['profile_id'],'کارمند')+': '+e['message'] for e in result['errors']));return
        totals=result['totals'];labels=[('days','جمع روزهای بیمه'),('insured_total','حقوق مشمول'),('worker','سهم کارمند'),('employer','سهم کارفرما'),('unemployment','سهم بیکاری'),('insurance_total','جمع حق بیمه')]
        QMessageBox.information(self,'نتیجه آزمایشی','\n'.join(label+': '+format(int(totals[key]),',')+(' روز' if key=='days' else ' ریال') for key,label in labels)+'\n\nاین نتیجه تأیید یا ارسال رسمی نیست.')


def show_insurance_lists(panel):
    company=panel.company.currentData();org=panel.owner.org;actor=panel.owner.session_user
    if not org.client or not actor or not panel.company_permitted() or not allowed(actor,company,'payroll','view'):
        QMessageBox.information(panel,'لیست بیمه','اتصال مرکز و دسترسی مالیات و حقوق برای این شرکت لازم است.');return
    rows=[r for r in org.records if r.get('kind')=='insurance_list' and r.get('company_id')==company]
    dialog=QDialog(panel);dialog.setWindowTitle('لیست‌های بیمه ماهانه · '+panel.company.currentText());dialog.resize(780,500);layout=QVBoxLayout(dialog)
    label=QLabel('لیست‌های این صفحه پیش‌نویس هستند و به معنی ارسال یا پرداخت حق بیمه نیستند.');label.setWordWrap(True);layout.addWidget(label)
    table=QTableWidget(0,5);table.setHorizontalHeaderLabels(['عنوان','کارگاه','ماه','شماره','وضعیت']);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);table.setSelectionBehavior(QAbstractItemView.SelectRows);table.setEditTriggers(QAbstractItemView.NoEditTriggers);layout.addWidget(table)
    def refresh():
        names={r['id']:r['title'] for r in org.records if r.get('kind')=='insurance_workshop' and r.get('company_id')==company};table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            p=r['payload']
            for col,value in enumerate((r['title'],names.get(p['workshop_id'],'غیرقابل مشاهده'),p['period'],p['list_no'],'پیش‌نویس')):table.setItem(i,col,QTableWidgetItem(str(value)))
    def edit(index=None):
        if not allowed(actor,company,'payroll','create'):return
        record=rows[index] if index is not None and 0<=index<len(rows) else None;editor=InsuranceListEditor(panel,company,record)
        if editor.exec()!=QDialog.Accepted:return
        try:
            result=request_wait(panel.owner,'records',dict(kind='insurance_list',company=company,id=record['id'] if record else None,version=record['version'] if record else None,payload=editor.payload))
            if record:rows[index]=result
            else:rows.append(result)
            refresh();org.sync()
        except Exception as exc:QMessageBox.warning(dialog,'ذخیره پیش‌نویس',str(exc))
    def add_rules():
        if not allowed(actor,company,'payroll','create'):return
        from org_ui import RecordDialog
        form=RecordDialog(org,'insurance_rules',company_id=company);form.setWindowTitle('ثبت نسخه جدید قواعد بیمه')
        if form.exec()!=QDialog.Accepted:return
        try:
            request_wait(panel.owner,'records',dict(kind='insurance_rules',company=company,payload=form.payload));org.sync()
            QMessageBox.information(dialog,'قواعد بیمه','نسخه ثبت شد؛ پس از همگام‌سازی در محاسبه قابل انتخاب است.')
        except Exception as exc:QMessageBox.warning(dialog,'ثبت قواعد',str(exc))
    buttons=QHBoxLayout();layout.addLayout(buttons);add=QPushButton('لیست جدید');add.setEnabled(allowed(actor,company,'payroll','create'));add.clicked.connect(lambda:edit());buttons.addWidget(add)
    change=QPushButton('ویرایش لیست انتخاب‌شده');change.setEnabled(allowed(actor,company,'payroll','create'));change.clicked.connect(lambda:edit(table.currentRow()) if table.currentRow()>=0 else None);buttons.addWidget(change)
    rules=QPushButton('ثبت نسخه قواعد');rules.setEnabled(allowed(actor,company,'payroll','create'));rules.clicked.connect(add_rules);buttons.addWidget(rules)
    refresh();dialog.exec()
