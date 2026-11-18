"""Company-scoped, explicit draft editor for monthly insurance."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,
 QComboBox,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QDialogButtonBox,QMessageBox,QCheckBox,QFileDialog)
from storage import today_j
from insurance_monthly import normalize_draft
from personalization_ui import request_wait
from permission_policy import allowed


class InsuranceListEditor(QDialog):
    def __init__(self,panel,company,record=None):
        super().__init__(panel);self.panel=panel;self.company_id=company;self.record=record;self.payload=None
        self.setWindowTitle('ویرایش پیش‌نویس بیمه' if record else 'پیش‌نویس لیست بیمه');self.resize(1080,650)
        root=QVBoxLayout(self);notice=QLabel('پیش‌نویس فقط اطلاعات واردشده را نگه می‌دارد. حقوق نهایی، محاسبه قانونی، تأیید، ارسال و پرداخت در این مرحله انجام نمی‌شوند.');notice.setWordWrap(True);root.addWidget(notice)
        p=record['payload'] if record else {};self.revision=p.get('revision','1');self.copy_from=p.get('copy_from','');form=QFormLayout();root.addLayout(form)
        self.title=QLineEdit(p.get('title',''));self.period=QLineEdit(p.get('period',f'{today_j().year:04d}/{today_j().month:02d}'));self.number=QLineEdit(p.get('list_no',''));self.list_type=QLineEdit(p.get('list_type',''));self.notes=QLineEdit(p.get('notes',''))
        self.workshop=QComboBox();self.workshop.addItem('انتخاب کارگاه',None)
        for r in panel.owner.org.records:
            if r.get('company_id')==company and r.get('kind')=='insurance_workshop':self.workshop.addItem(r['title'],r['id'])
        self.workshop.setCurrentIndex(max(0,self.workshop.findData(p.get('workshop_id'))));self.workshop.setEnabled(record is None);self.period.setReadOnly(record is not None)
        for label,w in [('عنوان',self.title),('کارگاه',self.workshop),('ماه شمسی',self.period),('شماره لیست',self.number),('نوع لیست',self.list_type),('توضیحات',self.notes)]:form.addRow(label,w)
        self.search=QLineEdit();self.search.setPlaceholderText('جست‌وجوی نام کارمند');root.addWidget(self.search)
        self.table=QTableWidget(0,8);self.table.setHorizontalHeaderLabels(['انتخاب کارمند','روز بیمه','مزد روزانه','سنوات روزانه','حق تأهل مشمول','سایر مزایای مشمول','مزایای غیرمشمول','بیمه بیکاری']);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive);self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);root.addWidget(self.table,1)
        self.search.textChanged.connect(self.filter_people)
        self.saved={row['profile_id']:row for row in p.get('rows',[])}
        self._displayed_workshop=self.workshop.currentData();self._drafts_by_workshop={self._displayed_workshop:self.saved}
        self.workshop.currentIndexChanged.connect(self.workshop_changed);self.populate()
        tools1=QHBoxLayout();root.addLayout(tools1);tools2=QHBoxLayout();root.addLayout(tools2)
        calculate=QPushButton('محاسبه آزمایشی');calculate.clicked.connect(self.calculate);tools1.addWidget(calculate)
        select_active=QPushButton('انتخاب کارکنان ماه');select_active.clicked.connect(self.select_period_people);tools1.addWidget(select_active)
        compare=QPushButton('مقایسه با حقوق');compare.clicked.connect(self.compare_payroll);tools1.addWidget(compare)
        suggest=QPushButton('پیشنهاد از حقوق');suggest.clicked.connect(self.suggest_payroll);tools2.addWidget(suggest)
        previous=QPushButton('مقایسه ماه‌ها');previous.clicked.connect(self.compare_period);tools1.addWidget(previous)
        review=QPushButton('کنترل اطلاعات');review.clicked.connect(self.review_data);tools2.addWidget(review)
        benefits=QPushButton('جزئیات مزایا');benefits.clicked.connect(self.edit_benefits);tools2.addWidget(benefits)
        report=QPushButton('گزارش پیش‌نویس Excel / PDF');report.setEnabled(bool(panel.owner.session_user and allowed(panel.owner.session_user,company,'payroll','export')));report.clicked.connect(self.export_report);tools2.addWidget(report)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('ذخیره پیش‌نویس');buttons.accepted.connect(self.validate_and_accept);buttons.rejected.connect(self.reject);root.addWidget(buttons)

    def populate(self):
        workshop=self.workshop.currentData();records=self.panel.owner.org.records
        profiles=[r for r in records if r.get('kind')=='insurance_employee' and r.get('company_id')==self.company_id and r['payload'].get('workshop_id')==workshop]
        present={r['id'] for r in profiles}
        for profile_id in self.saved:
            if profile_id not in present:profiles.append({'id':profile_id,'title':'پرونده در دسترس نیست','payload':{}})
        self.table.setRowCount(len(profiles))
        for i,profile in enumerate(profiles):
            row=self.saved.get(profile['id'],{});person=QTableWidgetItem(profile['title']);person.setData(Qt.UserRole,profile['id']);person.setData(Qt.UserRole+1,row.get('payroll_batch_id',''));person.setData(Qt.UserRole+2,row.get('benefit_breakdown',[]));person.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);person.setCheckState(Qt.Checked if row and row.get('_selected',True) else Qt.Unchecked);self.table.setItem(i,0,person)
            for col,key in enumerate(('days','daily_wage','daily_seniority','spouse_benefit','insured_benefits','non_insured_benefits'),1):self.table.setItem(i,col,QTableWidgetItem(str(row.get(key,''))))
            choice=QComboBox();choice.addItem('نامشخص',None);choice.addItem('مشمول',True);choice.addItem('غیرمشمول',False)
            value=row.get('unemployment_applies');choice.setCurrentIndex(1 if value is True else 2 if value is False else 0);self.table.setCellWidget(i,7,choice)
        self.filter_people()

    def workshop_changed(self):
        # A new draft may contain unsaved entries for the previous workshop.
        # Preserve them in memory instead of silently discarding them.
        old=getattr(self,'_displayed_workshop',None)
        if old is not None:
            saved={}
            for i in range(self.table.rowCount()):
                person=self.table.item(i,0);row={'profile_id':person.data(Qt.UserRole),'payroll_batch_id':person.data(Qt.UserRole+1) or '', 'benefit_breakdown':person.data(Qt.UserRole+2) or [], 'unemployment_applies':self.table.cellWidget(i,7).currentData(),'_selected':person.checkState()==Qt.Checked}
                for col,key in enumerate(('days','daily_wage','daily_seniority','spouse_benefit','insured_benefits','non_insured_benefits'),1):row[key]=self.table.item(i,col).text()
                saved[row['profile_id']]=row
            self._drafts_by_workshop[old]=saved
        self.saved=self._drafts_by_workshop.get(self.workshop.currentData(),{})
        self._displayed_workshop=self.workshop.currentData();self.populate()

    def filter_people(self):
        from storage import normalize
        query=normalize(self.search.text()).replace('ي','ی').replace('ك','ک').casefold()
        for i in range(self.table.rowCount()):
            name=normalize(self.table.item(i,0).text()).replace('ي','ی').replace('ك','ک').casefold()
            self.table.setRowHidden(i,bool(query and query not in name))

    def select_period_people(self):
        from insurance_monthly import eligible_profiles_for_period
        workshop=self.workshop.currentData()
        if not workshop:QMessageBox.warning(self,'انتخاب کارکنان','ابتدا کارگاه را انتخاب کنید.');return
        profiles=[r for r in self.panel.owner.org.records if r.get('kind')=='insurance_employee' and r.get('company_id')==self.company_id]
        try:eligible,review=eligible_profiles_for_period(profiles,workshop,self.period.text())
        except ValueError as exc:QMessageBox.warning(self,'انتخاب کارکنان',str(exc));return
        count=0
        for i in range(self.table.rowCount()):
            item=self.table.item(i,0)
            if item.data(Qt.UserRole) in eligible and item.checkState()!=Qt.Checked:item.setCheckState(Qt.Checked);count+=1
        QMessageBox.information(self,'انتخاب کارکنان',f'{count} نفر بر اساس تاریخ همکاری به انتخاب اضافه شد. {len(review)} پرونده تاریخ نامشخص یا نامعتبر دارد و باید بررسی شود. انتخاب‌های قبلی و مقادیر واردشده حفظ شدند؛ کارکرد و مبالغ باید جداگانه بررسی شوند.')

    def draft_values(self):
        rows=[]
        for i in range(self.table.rowCount()):
            person=self.table.item(i,0)
            if person.checkState()!=Qt.Checked:continue
            row={'profile_id':person.data(Qt.UserRole),'payroll_batch_id':person.data(Qt.UserRole+1) or '', 'benefit_breakdown':person.data(Qt.UserRole+2) or [], 'unemployment_applies':self.table.cellWidget(i,7).currentData()}
            for col,key in enumerate(('days','daily_wage','daily_seniority','spouse_benefit','insured_benefits','non_insured_benefits'),1):
                item=self.table.item(i,col);row[key]=item.text() if item else ''
            rows.append(row)
        return normalize_draft(dict(title=self.title.text(),period=self.period.text(),list_no=self.number.text(),list_type=self.list_type.text(),notes=self.notes.text(),workshop_id=self.workshop.currentData() or '',rows=rows,status='draft',revision=self.revision,copy_from=self.copy_from))

    def validate_and_accept(self):
        try:
            self.payload=self.draft_values()
        except ValueError as exc:QMessageBox.warning(self,'بررسی پیش‌نویس',str(exc));return
        self.accept()

    def edit_benefits(self):
        index=self.table.currentRow()
        if index<0:QMessageBox.information(self,'مزایا','ابتدا ردیف کارمند را انتخاب کنید.');return
        person=self.table.item(index,0);d=QDialog(self);d.setWindowTitle('جزئیات مزایا · '+person.text());d.resize(650,430);layout=QVBoxLayout(d)
        note=QLabel('وضعیت مشمول‌بودن هر قلم را بر اساس مقررات و شرایط فرد مشخص کنید. حق تأهل و سنوات در ستون جداگانه خود ثبت می‌شوند. جمع جزئیات باید با ستون‌های مزایا برابر باشد.');note.setWordWrap(True);layout.addWidget(note)
        table=QTableWidget(0,3);table.setHorizontalHeaderLabels(['عنوان قلم','مبلغ ریال','وضعیت بیمه']);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);layout.addWidget(table)
        def add_row(item=None):
            item=item or {};i=table.rowCount();table.insertRow(i);table.setItem(i,0,QTableWidgetItem(item.get('title','')));table.setItem(i,1,QTableWidgetItem(item.get('amount','')))
            box=QComboBox();box.addItem('انتخاب وضعیت',None);box.addItem('مشمول',True);box.addItem('غیرمشمول',False);box.setCurrentIndex(1 if item.get('insured') is True else 2 if item.get('insured') is False else 0);table.setCellWidget(i,2,box)
        for item in person.data(Qt.UserRole+2) or []:add_row(item)
        controls=QHBoxLayout();layout.addLayout(controls);add=QPushButton('افزودن قلم');add.clicked.connect(lambda:add_row());controls.addWidget(add);remove=QPushButton('حذف قلم');remove.clicked.connect(lambda:table.removeRow(table.currentRow()) if table.currentRow()>=0 else None);controls.addWidget(remove)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('ثبت جزئیات');buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);layout.addWidget(buttons)
        if d.exec()!=QDialog.Accepted:return
        items=[]
        for i in range(table.rowCount()):
            title=table.item(i,0).text() if table.item(i,0) else '';amount=table.item(i,1).text() if table.item(i,1) else '';insured=table.cellWidget(i,2).currentData()
            if not title.strip() or not amount.strip() or insured is None:QMessageBox.warning(self,'مزایا','عنوان، مبلغ و وضعیت همه اقلام را کامل کنید.');return
            items.append({'title':title,'amount':amount,'insured':insured})
        # Use the same validation as saving; do not overwrite the existing table on error.
        try:
            candidate=self.draft_values();row=next((r for r in candidate['rows'] if r['profile_id']==person.data(Qt.UserRole)),None)
            if row is None:raise ValueError('ابتدا کارمند را در لیست انتخاب کنید.')
            row['benefit_breakdown']=items;normalize_draft(candidate)
        except ValueError as exc:QMessageBox.warning(self,'مزایا',str(exc));return
        person.setData(Qt.UserRole+2,items)

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
        totals=result['totals'];labels=[('days','جمع روزهای بیمه'),('spouse_benefit','حق تأهل مشمول'),('insured_total','حقوق مشمول'),('worker','سهم کارمند'),('employer','سهم کارفرما'),('unemployment','سهم بیکاری'),('insurance_total','جمع حق بیمه')]
        result_dialog=QDialog(self);result_dialog.setWindowTitle('جزئیات محاسبه آزمایشی');result_dialog.resize(950,520);result_layout=QVBoxLayout(result_dialog)
        summary=QLabel('  |  '.join(label+': '+format(int(totals[key]),',')+(' روز' if key=='days' else ' ریال') for key,label in labels));summary.setWordWrap(True);result_layout.addWidget(summary)
        note=QLabel('نتیجه آزمایشی است و تأیید یا ارسال رسمی نیست.');note.setWordWrap(True);result_layout.addWidget(note)
        table=QTableWidget(len(result['rows']),7);table.setHorizontalHeaderLabels(['کارمند','حق تأهل','مبلغ مشمول','سهم کارمند','سهم کارفرما','بیکاری','جمع حق بیمه']);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);table.setEditTriggers(QAbstractItemView.NoEditTriggers);result_layout.addWidget(table)
        for i,item in enumerate(result['rows']):
            values=[names.get(item['profile_id'],'کارمند')]+[format(int(item['amounts'][key]),',') for key in ('spouse_benefit','insured_total','worker','employer','unemployment','insurance_total')]
            for j,value in enumerate(values):table.setItem(i,j,QTableWidgetItem(value))
        close=QDialogButtonBox(QDialogButtonBox.Close);close.rejected.connect(result_dialog.reject);result_layout.addWidget(close);result_dialog.exec()

    def compare_payroll(self):
        from insurance_payroll_compare import compare,payroll_options
        try:draft=self.draft_values()
        except ValueError as exc:QMessageBox.warning(self,'مقایسه حقوق',str(exc));return
        records=self.panel.owner.org.records
        options=payroll_options(records,self.company_id,draft['period'])
        if not options:QMessageBox.information(self,'مقایسه حقوق','دوره حقوق قابل مشاهده برای این ماه پیدا نشد.');return
        from PySide6.QtWidgets import QInputDialog
        labels=[r['title']+' · '+('تأیید داخلی دارد' if confirmed else 'بدون تأیید داخلی')+' · '+r['id'] for r,confirmed in options];label,ok=QInputDialog.getItem(self,'دوره حقوق','دوره برآورد حقوق:',labels,0,False)
        if not ok:return
        batch=options[labels.index(label)][0]['payload']
        profiles={r['id']:r['payload'] for r in records if r.get('kind')=='insurance_employee' and r.get('company_id')==self.company_id}
        employees={r['id']:r['payload'] for r in records if r.get('kind')=='employee' and r.get('company_id')==self.company_id}
        names={self.table.item(i,0).data(Qt.UserRole):self.table.item(i,0).text() for i in range(self.table.rowCount())}
        try:items=compare(draft,batch,profiles,employees)
        except ValueError as exc:QMessageBox.warning(self,'مقایسه حقوق',str(exc));return
        details=['دوره حقوق موجود برآورد است؛ مقایسه، تأیید نهایی حقوق یا تشخیص اقلام مشمول بیمه نیست.']
        for item in items:
            text=names.get(item['profile_id'],'کارمند')+': '+item['message']
            if 'payroll_days' in item:text+=' کارکرد فیش: '+item['payroll_days']+'؛ کارکرد بیمه: '+item['insurance_days']+'؛ حقوق پایه ماه فیش: '+item['payroll_base']+' ریال.'
            details.append(text)
        QMessageBox.information(self,'مقایسه حقوق و بیمه','\n'.join(details))

    def suggest_payroll(self):
        from PySide6.QtWidgets import QInputDialog
        from storage import parse_j,month_last_day,normalize
        from insurance_payroll_compare import suggestions,payroll_options
        try:draft=self.draft_values();month=parse_j(draft['period']+'/01')
        except ValueError as exc:QMessageBox.warning(self,'پیشنهاد حقوق',str(exc));return
        records=self.panel.owner.org.records
        options=payroll_options(records,self.company_id,draft['period'])
        if not options:QMessageBox.information(self,'پیشنهاد حقوق','دوره حقوق قابل مشاهده برای این ماه وجود ندارد.');return
        labels=[r['title']+' · '+('تأیید داخلی دارد' if confirmed else 'بدون تأیید داخلی')+' · '+r['id'] for r,confirmed in options];label,ok=QInputDialog.getItem(self,'پیشنهاد حقوق','دوره برآورد حقوق:',labels,0,False)
        if not ok:return
        batch,confirmed=options[labels.index(label)];profiles={r['id']:r['payload'] for r in records if r.get('kind')=='insurance_employee' and r.get('company_id')==self.company_id};employees={r['id']:r['payload'] for r in records if r.get('kind')=='employee' and r.get('company_id')==self.company_id}
        slips={}
        for slip in batch['payload'].get('slips',[]):slips.setdefault(normalize(slip.get('code','')),[]).append(slip)
        filled=0;linked=0;unmatched=0
        for i in range(self.table.rowCount()):
            person=self.table.item(i,0)
            if person.checkState()!=Qt.Checked or person.data(Qt.UserRole+1) not in ('',None,batch['id']):continue
            profile=profiles.get(person.data(Qt.UserRole),{});employee=employees.get(profile.get('employee_id'),{});matches=slips.get(normalize(employee.get('employee_code','')),[])
            if not normalize(employee.get('employee_code','')) or len(matches)!=1:unmatched+=1;continue
            proposed=suggestions(matches[0],month_last_day(month.year,month.month))
            for key,col in (('days',1),('daily_wage',2),('daily_seniority',3)):
                if key in proposed and not self.table.item(i,col).text().strip():self.table.item(i,col).setText(proposed[key]);filled+=1
            person.setData(Qt.UserRole+1,batch['id']);linked+=1
        status='تأیید داخلی ثبت شده است' if confirmed else 'تأیید داخلی برای این نسخه ثبت نشده است'
        QMessageBox.information(self,'پیشنهاد حقوق',f'{filled} خانه خالی پر شد و دوره حقوق به {linked} نفر پیوند خورد؛ {unmatched} نفر فیش یکتا نداشتند. {status}. اطلاعات موجود تغییر نکرد؛ اقلام مشمول، حق تأهل و وضعیت بیمه باید جداگانه بررسی شوند. این دوره برآورد است و به معنی حقوق نهایی نیست.')

    def compare_period(self):
        from insurance_period_compare import compare_periods
        from PySide6.QtWidgets import QInputDialog
        try:draft=self.draft_values()
        except ValueError as exc:QMessageBox.warning(self,'مقایسه ماه‌ها',str(exc));return
        records=self.panel.owner.org.records
        candidates=[r for r in records if r.get('kind')=='insurance_list' and r.get('company_id')==self.company_id and r['payload'].get('workshop_id')==draft['workshop_id'] and r['payload'].get('period')!=draft['period']]
        if not candidates:QMessageBox.information(self,'مقایسه ماه‌ها','لیست ماه دیگر برای این کارگاه پیدا نشد.');return
        labels=[r['title']+' · '+r['payload']['period']+' · '+r['id'] for r in candidates]
        label,ok=QInputDialog.getItem(self,'مقایسه ماه‌ها','لیست مبنا:',labels,0,False)
        if not ok:return
        names={r['id']:r['title'] for r in records if r.get('kind')=='insurance_employee' and r.get('company_id')==self.company_id}
        try:changes=compare_periods(draft,candidates[labels.index(label)]['payload'])
        except ValueError as exc:QMessageBox.warning(self,'مقایسه ماه‌ها',str(exc));return
        text=['تغییرات ورودی پیش‌نویس هستند و باید بررسی شوند.']+[names.get(x['profile_id'],'کارمند غیرقابل مشاهده')+': '+x['message'] for x in changes]
        if not changes:text.append('تغییری در ردیف‌های واردشده دیده نشد.')
        QMessageBox.information(self,'مقایسه ماه‌ها','\n'.join(text))

    def review_data(self):
        from insurance_validation import review
        try:draft=self.draft_values()
        except ValueError as exc:QMessageBox.warning(self,'کنترل اطلاعات',str(exc));return
        records=[r for r in self.panel.owner.org.records if r.get('company_id')==self.company_id]
        workshop=next((r['payload'] for r in records if r.get('kind')=='insurance_workshop' and r['id']==draft['workshop_id']),None)
        profiles={r['id']:r['payload'] for r in records if r.get('kind')=='insurance_employee'}
        employees={r['id']:r['payload'] for r in records if r.get('kind')=='employee'}
        names={self.table.item(i,0).data(Qt.UserRole):self.table.item(i,0).text() for i in range(self.table.rowCount())}
        issues=review(draft,workshop,profiles,employees)
        d=QDialog(self);d.setWindowTitle('کنترل اولیه لیست بیمه');d.resize(800,500);layout=QVBoxLayout(d)
        count=sum(i['severity']=='error' for i in issues);note=QLabel('خطا: '+str(count)+' · نیازمند بررسی: '+str(len(issues)-count)+' — این کنترل جایگزین تأیید سازمان نیست.');note.setWordWrap(True);layout.addWidget(note)
        filters=QComboBox();filters.addItem('همه موارد','all');filters.addItem('خطاها','error');filters.addItem('نیازمند بررسی','warning');layout.addWidget(filters)
        table=QTableWidget(0,3);table.setHorizontalHeaderLabels(['نوع','کارمند','شرح']);table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch);table.setEditTriggers(QAbstractItemView.NoEditTriggers);layout.addWidget(table)
        def show_issues():
            selected=filters.currentData();visible=[i for i in issues if selected=='all' or i['severity']==selected];table.setRowCount(len(visible))
            for row,item in enumerate(visible):
                for col,value in enumerate(('خطا' if item['severity']=='error' else 'نیازمند بررسی',names.get(item['profile_id'],'لیست'),item['message'])):table.setItem(row,col,QTableWidgetItem(value))
        filters.currentIndexChanged.connect(show_issues);show_issues();close=QDialogButtonBox(QDialogButtonBox.Close);close.rejected.connect(d.reject);layout.addWidget(close);d.exec()

    def export_report(self):
        from insurance_reports import draft_report
        from org_reports import spreadsheet,pdf_report
        actor=self.panel.owner.session_user
        if not actor or not allowed(actor,self.company_id,'payroll','export'):
            QMessageBox.warning(self,'گزارش','دسترسی تهیه گزارش حقوق لازم است.');return
        try:draft=self.draft_values()
        except ValueError as exc:QMessageBox.warning(self,'گزارش',str(exc));return
        records=[r for r in self.panel.owner.org.records if r.get('company_id')==self.company_id]
        workshop=next((r['payload'] for r in records if r.get('kind')=='insurance_workshop' and r['id']==draft['workshop_id']),None)
        profiles={r['id']:r['payload'] for r in records if r.get('kind')=='insurance_employee'};employees={r['id']:r['payload'] for r in records if r.get('kind')=='employee'}
        names={self.table.item(i,0).data(Qt.UserRole):self.table.item(i,0).text() for i in range(self.table.rowCount())}
        path,selected=QFileDialog.getSaveFileName(self,'گزارش پیش‌نویس بیمه','Insurance-Draft.xlsx','Excel (*.xlsx);;PDF (*.pdf)')
        if not path:return
        pdf=selected.startswith('PDF');ext='.pdf' if pdf else '.xlsx'
        if not path.lower().endswith(ext):path+=ext
        try:(pdf_report if pdf else spreadsheet)(path,draft_report(draft,workshop,profiles,employees,names),'گزارش پیش‌نویس بیمه؛ فایل ارسال نیست');QMessageBox.information(self,'گزارش','گزارش پیش‌نویس ذخیره شد.')
        except Exception as exc:QMessageBox.warning(self,'گزارش',str(exc))


def show_insurance_lists(panel):
    company=panel.company.currentData();org=panel.owner.org;actor=panel.owner.session_user
    if not org.client or not actor or not panel.company_permitted() or not allowed(actor,company,'payroll','view'):
        QMessageBox.information(panel,'لیست بیمه','اتصال مرکز و دسترسی مالیات و حقوق برای این شرکت لازم است.');return
    rows=[r for r in org.records if r.get('kind')=='insurance_list' and r.get('company_id')==company]
    dialog=QDialog(panel);dialog.setWindowTitle('لیست‌های بیمه ماهانه · '+panel.company.currentText());dialog.resize(780,500);layout=QVBoxLayout(dialog)
    label=QLabel('اطلاعات ارسال و پرداخت، رسیدهای ثبت‌شده توسط کاربر هستند و تأیید سامانه یا تسویه کامل را نشان نمی‌دهند.');label.setWordWrap(True);layout.addWidget(label)
    tracking=[r for r in org.records if r.get('kind')=='insurance_evidence' and r.get('company_id')==company]
    filter_box=QComboBox();filter_box.addItem('همه لیست‌ها','all');filter_box.addItem('بدون رسید ارسال','no_submission');filter_box.addItem('بدون رسید پرداخت','no_payment');layout.addWidget(filter_box)
    table=QTableWidget(0,7);table.setHorizontalHeaderLabels(['عنوان','کارگاه','ماه','شماره','نسخه داخلی','رسید ارسال','رسید پرداخت']);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);table.setSelectionBehavior(QAbstractItemView.SelectRows);table.setEditTriggers(QAbstractItemView.NoEditTriggers);layout.addWidget(table)
    def refresh():
        from insurance_reports import tracking_report
        names={(r['company_id'],r['id']):r['title'] for r in org.records if r.get('kind')=='insurance_workshop' and r.get('company_id')==company};table.setRowCount(len(rows))
        for i,r in enumerate(tracking_report(rows,names,tracking)):
            for col,key in enumerate(('عنوان','کارگاه','ماه','شماره لیست','نسخه داخلی','پیگیری ارسال دستی','پیگیری پرداخت دستی')):table.setItem(i,col,QTableWidgetItem(str(r[key])))
            mode=filter_box.currentData();table.setRowHidden(i,(mode=='no_submission' and r['پیگیری ارسال دستی']=='ثبت شده') or (mode=='no_payment' and r['پیگیری پرداخت دستی']=='ثبت شده'))
    def filter_changed():
        table.clearSelection();table.setCurrentCell(-1,-1);refresh()
    filter_box.currentIndexChanged.connect(filter_changed)
    def edit(index=None):
        if not allowed(actor,company,'payroll','create'):return
        record=rows[index] if index is not None and 0<=index<len(rows) else None;editor=InsuranceListEditor(panel,company,record)
        if editor.exec()!=QDialog.Accepted:return
        reason=''
        if record and editor.payload!=record['payload']:
            from PySide6.QtWidgets import QInputDialog
            reason,ok=QInputDialog.getText(dialog,'علت اصلاح','علت اصلاح لیست را بنویسید:')
            if not ok:return
            if not reason.strip():QMessageBox.warning(dialog,'علت اصلاح','علت اصلاح الزامی است؛ تغییری ذخیره نشد.');return
        try:
            result=request_wait(panel.owner,'records',dict(kind='insurance_list',company=company,id=record['id'] if record else None,version=record['version'] if record else None,payload=editor.payload,reason=reason))
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
    def confirm_payroll():
        from PySide6.QtWidgets import QInputDialog
        index=table.currentRow()
        if not 0<=index<len(rows):QMessageBox.information(dialog,'تأیید حقوق','ابتدا لیست ماه را انتخاب کنید.');return
        batches=[r for r in org.records if r.get('kind')=='payroll_batch' and r.get('company_id')==company and r['payload'].get('period')==rows[index]['payload']['period']]
        if not batches:QMessageBox.information(dialog,'تأیید حقوق','دوره حقوق قابل مشاهده برای این ماه پیدا نشد.');return
        labels=[r['title']+' · '+r['id'] for r in batches];label,ok=QInputDialog.getItem(dialog,'تأیید داخلی حقوق','دوره بررسی‌شده:',labels,0,False)
        if not ok:return
        reference,ok=QInputDialog.getText(dialog,'مرجع تأیید حقوق','شماره یا مرجع تأیید حقوق بررسی‌شده را وارد کنید:')
        if not ok or not reference.strip():return
        if QMessageBox.question(dialog,'تأیید داخلی حقوق','تأیید می‌کنید اطلاعات این دوره حقوق را بررسی کرده‌اید؟ این تأیید به معنی تأیید اقلام مشمول بیمه یا ارسال نیست.',QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        try:
            request_wait(panel.owner,'records',dict(kind='payroll_confirmation',company=company,payload={'title':'تأیید حقوق · '+batches[labels.index(label)]['title'],'payroll_batch_id':batches[labels.index(label)]['id'],'reference':reference,'notes':''}));org.sync();QMessageBox.information(dialog,'تأیید حقوق','تأیید داخلی حقوق ثبت شد.')
        except Exception as exc:QMessageBox.warning(dialog,'تأیید حقوق',str(exc))
    def clone_version():
        import copy
        index=table.currentRow()
        if not 0<=index<len(rows):QMessageBox.information(dialog,'نسخه اصلاحی','ابتدا لیست مبنا را انتخاب کنید.');return
        source=rows[index];p=copy.deepcopy(source['payload'])
        siblings=[r for r in rows if all(r['payload'].get(k)==p.get(k) for k in ('workshop_id','period','list_no'))]
        p['revision']=str(max(int(r['payload'].get('revision','1')) for r in siblings)+1);p['copy_from']=source['id']
        editor=InsuranceListEditor(panel,company,{'payload':p});editor.setWindowTitle('نسخه اصلاحی لیست بیمه')
        editor.number.setReadOnly(True)
        if editor.exec()!=QDialog.Accepted:return
        from PySide6.QtWidgets import QInputDialog
        reason,ok=QInputDialog.getText(dialog,'علت نسخه اصلاحی','علت ایجاد نسخه اصلاحی را بنویسید:')
        if not ok:return
        if not reason.strip():QMessageBox.warning(dialog,'علت نسخه اصلاحی','علت اصلاح الزامی است؛ نسخه ثبت نشد.');return
        try:
            result=request_wait(panel.owner,'records',dict(kind='insurance_list',company=company,payload=editor.payload,reason=reason));rows.append(result);refresh();org.sync()
        except Exception as exc:QMessageBox.warning(dialog,'نسخه اصلاحی',str(exc))
    def save_calculation():
        from PySide6.QtWidgets import QInputDialog
        index=table.currentRow()
        if not 0<=index<len(rows):QMessageBox.information(dialog,'محاسبه','ابتدا یک لیست ذخیره‌شده انتخاب کنید.');return
        selected=rows[index]
        rules=[r for r in org.records if r.get('kind')=='insurance_rules' and r.get('company_id')==company and r['payload'].get('approved')]
        if not rules:QMessageBox.information(dialog,'محاسبه','ابتدا نسخه تأییدشده قواعد را ثبت و همگام کنید.');return
        labels=[r['title']+' · '+r['payload']['rules_version']+' · '+r['id'] for r in rules]
        label,ok=QInputDialog.getItem(dialog,'نسخه قواعد','قواعد مورد استفاده:',labels,0,False)
        if not ok:return
        try:
            result=request_wait(panel.owner,'records',dict(kind='insurance_calculation',company=company,payload={'title':'محاسبه آزمایشی · '+selected['title'],'insurance_list_id':selected['id'],'rules_id':rules[labels.index(label)]['id']}))
            total=result['payload']['result']['totals']['insurance_total']
            QMessageBox.information(dialog,'محاسبه ثبت‌شده','جمع آزمایشی حق بیمه: '+format(int(total),',')+' ریال\nمحاسبه و نسخه‌های مبنا ثبت شدند؛ این نتیجه تأیید یا ارسال رسمی نیست.')
            org.sync()
        except Exception as exc:QMessageBox.warning(dialog,'محاسبه ثبت‌شده',str(exc))
    def calculation_history():
        from PySide6.QtWidgets import QInputDialog
        index=table.currentRow()
        if not 0<=index<len(rows):QMessageBox.information(dialog,'محاسبات','ابتدا یک لیست انتخاب کنید.');return
        calculations=[r for r in org.records if r.get('kind')=='insurance_calculation' and r.get('company_id')==company and r['payload'].get('insurance_list_id')==rows[index]['id']]
        if not calculations:QMessageBox.information(dialog,'محاسبات','محاسبه ثبت‌شده‌ای برای این لیست پیدا نشد.');return
        labels=[r['title']+' · '+r['payload'].get('calculated_at','')+' · '+r['id'] for r in calculations]
        label,ok=QInputDialog.getItem(dialog,'محاسبات ثبت‌شده','محاسبه:',labels,0,False)
        if ok:org.record_details(calculations[labels.index(label)])
    def projection_check():
        from PySide6.QtWidgets import QInputDialog
        from insurance_dbf_projection import worker_projection,workshop_projection
        index=table.currentRow()
        if not 0<=index<len(rows):QMessageBox.information(dialog,'آمادگی اطلاعات','ابتدا لیست را انتخاب کنید.');return
        calculations=[r for r in org.records if r.get('kind')=='insurance_calculation' and r.get('company_id')==company and r['payload'].get('insurance_list_id')==rows[index]['id']]
        if not calculations:QMessageBox.information(dialog,'آمادگی اطلاعات','ابتدا محاسبه آزمایشی را ثبت کنید.');return
        labels=[r['title']+' · '+r['payload'].get('calculated_at','')+' · '+r['id'] for r in calculations]
        label,ok=QInputDialog.getItem(dialog,'آمادگی اطلاعات','محاسبه:',labels,0,False)
        if not ok:return
        p=calculations[labels.index(label)]['payload'];draft=p['draft_snapshot'];result=p['result']
        if rows[index]['version']!=p.get('list_version'):
            QMessageBox.warning(dialog,'آمادگی اطلاعات','لیست پس از این محاسبه تغییر کرده است؛ ابتدا محاسبه تازه ثبت کنید.');return
        try:
            workshop=workshop_projection(p['workshop_snapshot'],draft,result)
            people={person['profile_id']:person for person in p['people_snapshot']};amounts={item['profile_id']:item['amounts'] for item in result['rows']}
            projections=[(people[line['profile_id']],worker_projection(p['workshop_snapshot'],draft,line,people[line['profile_id']],amounts[line['profile_id']])) for line in draft['rows']]
            details=['این بررسی آزمایشی بر اساس اطلاعات زمان محاسبه است و به معنی تأیید فرمت یا امکان ارسال نیست.']
            if workshop['missing']:details.append('اطلاعات ناقص کارگاه: '+', '.join(workshop['missing']))
            details.append('ستون‌های کارگاه نیازمند تأیید نگاشت: '+', '.join(workshop['unresolved']))
            for person,projection in projections:
                if projection['missing']:details.append(person['employee'].get('title','کارمند')+': '+', '.join(projection['missing']))
            details.append('ستون‌های کارکنان نیازمند تأیید نگاشت: DSW_MAZ, DSW_PRATE')
            QMessageBox.information(dialog,'آمادگی آزمایشی اطلاعات','\n'.join(details))
        except (KeyError,ValueError,TypeError) as exc:QMessageBox.warning(dialog,'آمادگی اطلاعات',str(exc))
    def review_calculation():
        from PySide6.QtWidgets import QInputDialog
        index=table.currentRow()
        if not 0<=index<len(rows):QMessageBox.information(dialog,'بررسی داخلی','ابتدا لیست را انتخاب کنید.');return
        calculations=[r for r in org.records if r.get('kind')=='insurance_calculation' and r.get('company_id')==company and r['payload'].get('insurance_list_id')==rows[index]['id']]
        if not calculations:QMessageBox.information(dialog,'بررسی داخلی','ابتدا محاسبه آزمایشی ثبت کنید.');return
        labels=[r['title']+' · '+r['payload'].get('calculated_at','')+' · '+r['id'] for r in calculations]
        label,ok=QInputDialog.getItem(dialog,'بررسی داخلی','محاسبه مورد بررسی:',labels,0,False)
        if not ok:return
        notes,ok=QInputDialog.getMultiLineText(dialog,'توضیح بررسی داخلی','توضیح بررسی هشدارها را بنویسید. این تأیید به معنی ارسال یا تأیید سازمان نیست:')
        if not ok:return
        try:
            result=request_wait(panel.owner,'records',dict(kind='insurance_review',company=company,payload={'title':'بررسی داخلی · '+rows[index]['title'],'calculation_id':calculations[labels.index(label)]['id'],'notes':notes}))
            count=len(result['payload']['issues']);QMessageBox.information(dialog,'بررسی داخلی','بررسی اولیه ثبت شد. تعداد هشدارهای بررسی‌شده: '+str(count)+'\nاین نتیجه تأیید سازمان یا مجوز ارسال نیست.');org.sync()
        except Exception as exc:QMessageBox.warning(dialog,'بررسی داخلی',str(exc))
    def evidence():
        index=table.currentRow()
        if not 0<=index<len(rows):QMessageBox.information(dialog,'پیگیری','ابتدا یک لیست انتخاب کنید.');return
        record=rows[index]
        events=[r for r in org.records if r.get('kind')=='insurance_evidence' and r.get('company_id')==company and r['payload'].get('insurance_list_id')==record['id']]
        win=QDialog(dialog);win.setWindowTitle('پیگیری دستی · '+record['title']);lay=QVBoxLayout(win)
        note=QLabel('شماره‌های ثبت‌شده اظهاری هستند و توسط سامانه تأمین اجتماعی به‌صورت خودکار بررسی نمی‌شوند.');note.setWordWrap(True);lay.addWidget(note)
        grid=QTableWidget(0,4);grid.setHorizontalHeaderLabels(['نوع','تاریخ','شماره رسید','مبلغ ریال']);grid.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);grid.setEditTriggers(QAbstractItemView.NoEditTriggers);lay.addWidget(grid)
        def refresh_events():
            grid.setRowCount(len(events))
            for i,r in enumerate(events):
                for j,key in enumerate(('kind','date','reference','amount')):grid.setItem(i,j,QTableWidgetItem(str(r['payload'].get(key,''))))
        def add_event():
            from org_ui import RecordDialog
            form=RecordDialog(org,'insurance_evidence',company_id=company);form.setWindowTitle('ثبت پیگیری دستی برای '+record['title'])
            form.widgets['insurance_list_id'][0].setText(record['id']);form.widgets['insurance_list_id'][0].setReadOnly(True)
            if form.exec()!=QDialog.Accepted:return
            try:
                saved=request_wait(panel.owner,'records',dict(kind='insurance_evidence',company=company,payload=form.payload));events.append(saved);tracking.append(saved);refresh_events();refresh();org.sync()
            except Exception as exc:QMessageBox.warning(win,'ثبت پیگیری',str(exc))
        button=QPushButton('ثبت شماره ارسال یا رسید پرداخت');button.setEnabled(allowed(actor,company,'payroll','create'));button.clicked.connect(add_event);lay.addWidget(button)
        def open_documents():
            index=grid.currentRow()
            if not 0<=index<len(events):QMessageBox.information(win,'مدارک','ابتدا یک ردیف پیگیری انتخاب کنید.');return
            org.record_details(events[index])
        documents=QPushButton('مدارک و تاریخچه ردیف انتخاب‌شده');documents.clicked.connect(open_documents);lay.addWidget(documents)
        refresh_events();win.resize(700,440);win.exec()
    def compare_dbf_structure():
        from insurance_dbf_reference import inspect_schema,compare_schemas,field_evolution
        reference,_=QFileDialog.getOpenFileName(dialog,'انتخاب فایل مرجع DBF با اطلاعات آزمایشی','','DBF (*.dbf *.DBF)')
        if not reference:return
        candidate,_=QFileDialog.getOpenFileName(dialog,'انتخاب فایل DBF برای مقایسه','','DBF (*.dbf *.DBF)')
        if not candidate:return
        try:
            expected=inspect_schema(reference);actual=inspect_schema(candidate);differences=compare_schemas(expected,actual)
            evolution=field_evolution(expected,actual)
            message=('\n'.join(differences) if differences else 'تفاوتی در ساختار ستون‌ها و سرآیندهای بررسی‌شده دیده نشد.')
            if evolution['added']:message+='\nستون‌های اضافه‌شده: '+', '.join(evolution['added'])
            if evolution['removed']:message+='\nستون‌های حذف‌شده: '+', '.join(evolution['removed'])
            if evolution['changed']:message+='\nنوع یا اندازه تغییریافته: '+', '.join(evolution['changed'])
            if not evolution['common_order_equal']:message+='\nترتیب ستون‌های مشترک تغییر کرده است.'
            message+='\n\nفقط ساختار فیزیکی مقایسه شد؛ متن فارسی، صحت اطلاعات و پذیرش سامانه با این بررسی تأیید نمی‌شوند.'
            QMessageBox.information(dialog,'مقایسه ساختار DBF',message)
        except (ValueError,OSError) as exc:QMessageBox.warning(dialog,'مقایسه ساختار DBF',str(exc))
    def check_reference_pair():
        from insurance_dbf_reference import inspect_schema,assess_reference_pair
        workshop,_=QFileDialog.getOpenFileName(dialog,'انتخاب فایل مرجع کارگاه DSKKAR00','','DBF (*.dbf *.DBF)')
        if not workshop:return
        employees,_=QFileDialog.getOpenFileName(dialog,'انتخاب فایل مرجع کارکنان DSKWOR00','','DBF (*.dbf *.DBF)')
        if not employees:return
        try:
            issues=assess_reference_pair(inspect_schema(workshop),inspect_schema(employees))
            message='\n'.join('• '+issue for issue in issues) if issues else 'در کنترل ستون‌های شناخته‌شده کمبودی دیده نشد.'
            QMessageBox.information(dialog,'بررسی اولیه مرجع',message+'\n\nاین کنترل، نسخه رسمی، کدگذاری، محتوای فایل یا پذیرش آن را تأیید نمی‌کند.')
        except (ValueError,OSError) as exc:QMessageBox.warning(dialog,'بررسی مرجع',str(exc))
    buttons=QHBoxLayout();layout.addLayout(buttons);add=QPushButton('لیست جدید');add.setEnabled(allowed(actor,company,'payroll','create'));add.clicked.connect(lambda:edit());buttons.addWidget(add)
    change=QPushButton('ویرایش لیست انتخاب‌شده');change.setEnabled(allowed(actor,company,'payroll','create'));change.clicked.connect(lambda:edit(table.currentRow()) if table.currentRow()>=0 else None);buttons.addWidget(change)
    clone=QPushButton('نسخه اصلاحی');clone.setEnabled(allowed(actor,company,'payroll','create'));clone.clicked.connect(clone_version);buttons.addWidget(clone)
    rules=QPushButton('ثبت نسخه قواعد');rules.setEnabled(allowed(actor,company,'payroll','create'));rules.clicked.connect(add_rules);buttons.addWidget(rules)
    payroll_confirmation=QPushButton('تأیید داخلی حقوق');payroll_confirmation.setEnabled(allowed(actor,company,'payroll','create'));payroll_confirmation.clicked.connect(confirm_payroll);layout.addWidget(payroll_confirmation)
    calculations=QHBoxLayout();layout.addLayout(calculations)
    calc=QPushButton('ثبت محاسبه آزمایشی');calc.setEnabled(allowed(actor,company,'payroll','create'));calc.clicked.connect(save_calculation);calculations.addWidget(calc)
    calc_history=QPushButton('محاسبات ثبت‌شده');calc_history.clicked.connect(calculation_history);calculations.addWidget(calc_history)
    readiness=QPushButton('کنترل آمادگی اطلاعات');readiness.clicked.connect(projection_check);layout.addWidget(readiness)
    review=QPushButton('ثبت بررسی داخلی');review.setEnabled(allowed(actor,company,'payroll','create'));review.clicked.connect(review_calculation);calculations.addWidget(review)
    history=QPushButton('پیگیری ارسال و پرداخت');history.clicked.connect(evidence);buttons.addWidget(history)
    def export_tracking():
        from insurance_reports import tracking_report
        from org_reports import spreadsheet,pdf_report
        selected=[r for i,r in enumerate(rows) if not table.isRowHidden(i)]
        if not selected:QMessageBox.information(dialog,'گزارش پیگیری','لیستی برای گزارش وجود ندارد.');return
        path,choice=QFileDialog.getSaveFileName(dialog,'گزارش پیگیری بیمه','Insurance-Tracking.xlsx','Excel (*.xlsx);;PDF (*.pdf)')
        if not path:return
        pdf=choice.startswith('PDF');extension='.pdf' if pdf else '.xlsx'
        if not path.lower().endswith(extension):path+=extension
        names={(r['company_id'],r['id']):r['title'] for r in org.records if r.get('kind')=='insurance_workshop' and r.get('company_id')==company}
        try:
            report=tracking_report(selected,names,tracking)
            for item in report:item.pop('شناسه',None)
            (pdf_report if pdf else spreadsheet)(path,report,'پیگیری اظهاری بیمه؛ تأیید سامانه نیست')
            QMessageBox.information(dialog,'گزارش پیگیری','گزارش ذخیره شد.')
        except Exception as exc:QMessageBox.warning(dialog,'گزارش پیگیری',str(exc))
    export=QPushButton('گزارش پیگیری Excel / PDF');export.setEnabled(allowed(actor,company,'payroll','export'));export.clicked.connect(export_tracking);layout.addWidget(export)
    def list_history():
        index=table.currentRow()
        if not 0<=index<len(rows):QMessageBox.information(dialog,'تاریخچه','ابتدا یک لیست انتخاب کنید.');return
        org.record_details(rows[index])
    log=QPushButton('مدارک و تاریخچه لیست');log.clicked.connect(list_history);buttons.addWidget(log)
    structure=QPushButton('مقایسه ساختار DBF');structure.setEnabled(allowed(actor,company,'payroll','export'));structure.clicked.connect(compare_dbf_structure);layout.addWidget(structure)
    reference=QPushButton('بررسی اولیه دو فایل مرجع');reference.setEnabled(allowed(actor,company,'payroll','export'));reference.clicked.connect(check_reference_pair);layout.addWidget(reference)
    refresh();dialog.exec()
