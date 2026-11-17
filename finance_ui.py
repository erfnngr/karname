"""Company bank and check registry and invoice settlement dialog."""
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QMessageBox,QDialog,QFormLayout,QLineEdit,QDialogButtonBox,QComboBox,QLabel,QTabWidget,QInputDialog,QFileDialog,QMenu)
from PySide6.QtCore import Qt
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from storage import normalize,jformat,today_j,fa
METHOD_LABELS={'cash':'نقد','card':'کارت به کارت','pos':'کارتخوان','paya':'پایا','satna':'ساتنا','pol':'پل','internal':'حساب به حساب','cash_deposit':'واریز بانکی','other':'سایر','check':'چک'}

def request(panel,path,payload=None,**query):
    from personalization_ui import request_wait
    return request_wait(panel.owner,path,payload,**query)

class FinancePanel(QWidget):
    def __init__(self,panel):
        super().__init__(panel);self.panel=panel;self.data={'banks':[],'checks':[]};layout=QVBoxLayout(self);bar=QHBoxLayout();layout.addLayout(bar)
        menus=[('بانک',[('حساب بانکی جدید',self.add_bank),('تطبیق فایل بانک',self.reconcile),('تطبیق‌های ثبت‌شده',self.manage_bank_matches)]),('چک',[('چک جدید',self.add_check),('ویرایش چک',self.edit_check),('وضعیت چک',self.check_status),('خرج چک',self.transfer_check),('برگشت خرج چک',self.untransfer_check),('سابقه چک',self.check_history)]),('دریافت و پرداخت',[('ثبت دریافت / پرداخت',lambda:self.transaction(False)),('ویرایش سند',lambda:self.transaction(True)),('رسیدهای سند',self.receipts)]),('گزارش',[('سررسید فاکتورها',self.show_aging),('بررسی سلامت اطلاعات',self.show_data_quality)])]
        for title,items in menus:
            button=QPushButton(title);menu=QMenu(button)
            for label,fn in items:menu.addAction(label,fn)
            button.setMenu(menu);bar.addWidget(button)
        bar.addStretch()
        self.check_summary=QLabel('');self.check_summary.setWordWrap(True);layout.addWidget(self.check_summary)
        self.search=QLineEdit();self.search.setPlaceholderText('جستجوی شماره سند، فاکتور یا دسته‌بندی');layout.addWidget(self.search);self.search.textChanged.connect(self.render_documents);self.visible_documents=[]
        self.tabs=QTabWidget();layout.addWidget(self.tabs);self.tables={}
        for key,title,headers in [('banks','حساب‌ها',['نام حساب','شماره حساب','شبا']),('checks','چک‌ها',['شماره سند','نوع','شماره چک','بانک','مبلغ ریال','سررسید','وضعیت','توضیحات','خرج به']),('transactions','دریافت و پرداخت',['شماره سند','نوع','روش','مبلغ ریال','تاریخ','علت','فاکتور مرتبط','دسته‌بندی']),('balances','مانده طرف‌حساب',['مشتری','طلب شرکت؛ ریال','بدهی شرکت؛ ریال'])]:
            table=QTableWidget(0,len(headers));table.setHorizontalHeaderLabels(headers);table.setSelectionBehavior(QAbstractItemView.SelectRows);table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);self.tabs.addTab(table,title);self.tables[key]=table
        self.tables['balances'].doubleClicked.connect(self.show_statement)
    def ready(self,action='view'):
        if not self.panel.ready('view'):return False
        from permission_policy import allowed
        actor=self.panel.owner.session_user
        if actor and not allowed(actor,self.panel.company.currentData(),'finance',action):QMessageBox.information(self,'دسترسی','دسترسی مالی این عملیات فعال نیست.');return False
        return True
    def reload(self,quiet=False):
        company=self.panel.company.currentData()
        if not company or not self.panel.owner.org.client:return
        from permission_policy import allowed
        actor=self.panel.owner.session_user
        if actor and (not allowed(actor,company,'clients','view') or not allowed(actor,company,'finance','view')):return
        try:
            self.data=request(self.panel,'finance',company=company,_quiet=quiet)
            from finance_aging import check_summary
            summary=check_summary(self.data['checks']);self.check_summary.setText('چک‌های وصول‌نشده: '+fa(summary['overdue'])+' سررسید گذشته · '+fa(summary['upcoming'])+' در ۳۰ روز آینده')
            standalone=[dict(row,source='transaction') for row in self.data['transactions']]
            linked=[]
            for invoice in self.data.get('invoice_documents',[]):
                p=invoice['payload']
                if p.get('document_no'):
                    linked.append(dict(source='invoice',id=invoice['id'],document_no=p['document_no'],direction='income',method='invoice',amount=p.get('totals',{}).get('total','0'),date=p.get('date',''),reason=p.get('title',''),record=invoice))
            checks=[dict(source='check',id=ch['id'],document_no=ch['document_no'],direction='income' if ch['direction']=='received' else 'expense',method='check',amount=ch['amount'],date=ch['due_date'],reason='چک '+ch['number'],check_number=ch['number']) for ch in self.data['checks'] if ch.get('document_no')]
            self.data['transactions']=standalone+linked+checks
            for key in ('banks','checks','transactions'):
                table=self.tables[key];table.setRowCount(len(self.data[key]))
                for i,row in enumerate(self.data[key]):
                    values=[row['name'],row['account_no'],row['iban']] if key=='banks' else [row.get('document_no',''),'دریافتی' if row.get('direction','received')=='received' else 'پرداختی',row['number'],row['bank'],row['amount'],row['due_date'],{'pending':'در انتظار','deposited':'واگذارشده به بانک','cleared':'وصول‌شده','returned':'برگشتی'}.get(row.get('status','pending')),row['description']] if key=='checks' else [row['document_no'],'فاکتور' if row.get('source')=='invoice' else 'دریافت' if row['direction']=='income' else 'پرداخت',METHOD_LABELS.get(row['method'],'فاکتور' if row['method']=='invoice' else row['method']),row['amount'],row['date'],row['reason']]
                    if key=='checks':
                        transfer=next((t for t in self.data.get('check_transfers',[]) if t['check_id']==row['id']),None);values.append(self.panel.customer_payload(transfer['recipient_id']).get('title','طرف حساب') if transfer else '')
                    for j,value in enumerate(values):table.setItem(i,j,QTableWidgetItem(str(value)))
            self.render_documents()
        except Exception as exc:
            if not quiet:QMessageBox.warning(self,'امور مالی',str(exc))
        else:
            from decimal import Decimal
            raw=self.data.get('balances',{});incomplete=set(self.data.get('incomplete_balances',[]));values=[(k,raw.get(k,'0')) for k in set(raw)|incomplete];table=self.tables['balances'];table.setRowCount(len(values))
            self.balance_customers=[]
            for i,(customer,balance) in enumerate(values):
                self.balance_customers.append(customer)
                amount=Decimal(balance);name=self.panel.customer_payload(customer).get('title',customer)
                amounts=('نیاز به بررسی','نیاز به بررسی') if customer in incomplete else (str(max(amount,0)),str(max(-amount,0)))
                for j,value in enumerate((name,*amounts)):table.setItem(i,j,QTableWidgetItem(value))
            table.setToolTip('مانده براساس اسناد ثبت‌شده و قابل مشاهده است؛ چک در انتظار وصول تسویه نقدی محسوب نمی‌شود.')
    def receipts(self):
        from pathlib import Path
        import base64
        index=self.tables['transactions'].currentRow()
        if not 0<=index<len(self.visible_documents) or self.visible_documents[index].get('source')!='transaction':QMessageBox.information(self,'رسید','ابتدا یک سند مستقل دریافت یا پرداخت را انتخاب کنید.');return
        transaction=self.visible_documents[index];company=self.panel.company.currentData();dialog=QDialog(self);dialog.setWindowTitle('رسیدهای سند '+transaction['document_no']);dialog.resize(650,420);layout=QVBoxLayout(dialog);table=QTableWidget(0,3);table.setHorizontalHeaderLabels(['نام فایل','حجم بایت','زمان ثبت']);table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.setSelectionBehavior(QAbstractItemView.SelectRows);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);layout.addWidget(table);actions=QHBoxLayout();add=QPushButton('افزودن رسید');save=QPushButton('ذخیره فایل انتخاب‌شده');actions.addWidget(add);actions.addWidget(save);layout.addLayout(actions);items=[]
        def refresh():
            nonlocal items
            try:items=request(self.panel,'finance/receipts',company=company,transaction_id=transaction['id'])
            except Exception as exc:QMessageBox.warning(dialog,'رسید',str(exc));return
            table.setRowCount(len(items))
            for i,item in enumerate(items):
                for j,value in enumerate((item['name'],item['size'],item['created'])):table.setItem(i,j,QTableWidgetItem(str(value)))
        def upload():
            if not self.ready('edit'):return
            path,_=QFileDialog.getOpenFileName(dialog,'انتخاب رسید','','رسید (*.pdf *.png *.jpg *.jpeg *.xlsx *.csv)')
            if not path:return
            try:
                file=Path(path)
                if file.stat().st_size>10*1024*1024:raise ValueError('حجم رسید حداکثر ۱۰ مگابایت است.')
                request(self.panel,'finance/receipt',dict(company=company,transaction_id=transaction['id'],name=file.name,data=base64.b64encode(file.read_bytes()).decode('ascii')));refresh()
            except Exception as exc:QMessageBox.warning(dialog,'رسید',str(exc))
        def download():
            row=table.currentRow()
            if not 0<=row<len(items):QMessageBox.information(dialog,'رسید','ابتدا فایل را انتخاب کنید.');return
            try:
                result=request(self.panel,'finance/receipt',company=company,id=items[row]['id']);path,_=QFileDialog.getSaveFileName(dialog,'ذخیره رسید',result['name'])
                if path:Path(path).write_bytes(base64.b64decode(result['data'],validate=True))
            except Exception as exc:QMessageBox.warning(dialog,'رسید',str(exc))
        add.clicked.connect(upload);save.clicked.connect(download);refresh();dialog.exec()
    def manage_bank_matches(self):
        matches=self.data.get('bank_matches',[])
        if not matches:QMessageBox.information(self,'تطبیق','تطبیقی ثبت نشده است.');return
        names={b['id']:b['name'] for b in self.data.get('banks',[])};choices=[names.get(m['bank_id'],'حساب')+' · '+m['external_ref']+' · '+m['date']+' · '+m['amount'] for m in matches]
        chosen,ok=QInputDialog.getItem(self,'تطبیق‌های ثبت‌شده','انتخاب برای برداشتن تطبیق',choices,0,False)
        if not ok or QMessageBox.question(self,'برداشتن تطبیق','تطبیق انتخاب‌شده برداشته شود؟',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:request(self.panel,'finance/bank-unmatch',dict(company=self.panel.company.currentData(),id=matches[choices.index(chosen)]['id']));self.reload()
        except Exception as exc:QMessageBox.warning(self,'تطبیق',str(exc))
    def reconcile(self):
        banks=self.data.get('banks',[])
        if not banks:QMessageBox.information(self,'تطبیق بانک','ابتدا یک حساب بانکی ثبت کنید.');return
        labels=[b['name']+' · '+b['account_no'] for b in banks];choice,ok=QInputDialog.getItem(self,'تطبیق بانک','حساب بانکی',labels,0,False)
        if not ok:return
        path,_=QFileDialog.getOpenFileName(self,'فایل گردش حساب','','Excel / CSV (*.xlsx *.csv)')
        if not path:return
        try:
            from bank_reconcile import read_rows,read_table,suggestions
            try: imported=read_rows(path)
            except ValueError as original:
                if 'ستون' not in str(original):raise
                headers=read_table(path)[0];mapping=QDialog(self);mapping.setWindowTitle('انتخاب ستون‌های فایل بانک');form=QFormLayout(mapping);form.addRow(QLabel('تاریخ و یکی از دو روش «مبلغ و نوع» یا «واریز و برداشت» را انتخاب کنید. مبلغ‌ها باید ریال باشند.'));choices={}
                for key,title in [('date','تاریخ شمسی'),('amount','مبلغ'),('direction','نوع'),('income','واریز'),('expense','برداشت'),('reference','شماره پیگیری'),('description','شرح')]:
                    box=QComboBox();box.addItem('انتخاب نشده',None)
                    for i,header in enumerate(headers):box.addItem(str(header or ('ستون '+str(i+1))),i)
                    choices[key]=box;form.addRow(title,box)
                buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(mapping.accept);buttons.rejected.connect(mapping.reject);form.addRow(buttons)
                if mapping.exec()!=QDialog.Accepted:return
                imported=read_rows(path,{k:v.currentData() for k,v in choices.items()})
            rows=suggestions(imported,self.data.get('transactions',[]),banks[labels.index(choice)]['id'])
        except Exception as exc:QMessageBox.warning(self,'فایل گردش حساب',str(exc));return
        dialog=QDialog(self);dialog.setWindowTitle('پیشنهاد تطبیق بانک');dialog.resize(940,540);layout=QVBoxLayout(dialog)
        note=QLabel('تاریخ شمسی و مبالغ ریال هستند. پیشنهادها بر اساس تاریخ، مبلغ و نوع یکسان‌اند و تا تأیید شما ثبت نمی‌شوند. برای ثبت، شناسه تراکنش یا شماره پیگیری لازم است.');note.setWordWrap(True);layout.addWidget(note)
        table=QTableWidget(len(rows),6);table.setHorizontalHeaderLabels(['ردیف فایل','تاریخ','نوع','مبلغ ریال','شرح','سندهای احتمالی']);table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.horizontalHeader().setSectionResizeMode(4,QHeaderView.Stretch)
        for i,row in enumerate(rows):
            match='، '.join(m['document_no'] for m in row['matches']) or 'بدون تطابق';values=(row['row'],row['date'],'دریافت' if row['direction']=='income' else 'پرداخت',row['amount'],row['description'],match)
            for j,value in enumerate(values):table.setItem(i,j,QTableWidgetItem(str(value)))
        layout.addWidget(table);actions=QHBoxLayout();confirm=QPushButton('تأیید تطبیق ردیف انتخابی');undo=QPushButton('برداشتن تطبیق');actions.addWidget(confirm);actions.addWidget(undo);layout.addLayout(actions);bank_id=banks[labels.index(choice)]['id']
        def match_selected():
            index=table.currentRow()
            if not 0<=index<len(rows):QMessageBox.information(dialog,'تطبیق','یک ردیف را انتخاب کنید.');return
            row=rows[index]
            if not row['reference']:QMessageBox.information(dialog,'شناسه تراکنش','برای ثبت تطبیق، شناسه تراکنش در فایل لازم است.');return
            if not row['matches']:QMessageBox.information(dialog,'تطبیق','سند مشابهی پیدا نشد.');return
            choices=[m['document_no'] for m in row['matches']];document,ok=QInputDialog.getItem(dialog,'انتخاب سند','شماره سند',choices,0,False)
            if not ok:return
            if QMessageBox.question(dialog,'تأیید تطبیق','ردیف بانکی به سند '+document+' متصل شود؟',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            match=row['matches'][choices.index(document)]
            try:request(self.panel,'finance/bank-match',dict(company=self.panel.company.currentData(),bank_id=bank_id,external_ref=row['reference'],transaction_id=match['id'],date=row['date'],value=row['amount'],direction=row['direction']));self.reload();QMessageBox.information(dialog,'تطبیق','تطبیق ثبت شد.')
            except Exception as exc:QMessageBox.warning(dialog,'تطبیق',str(exc))
        def remove_match():
            matches=[m for m in self.data.get('bank_matches',[]) if m['bank_id']==bank_id]
            if not matches:QMessageBox.information(dialog,'تطبیق','تطبیقی برای این حساب ثبت نشده است.');return
            choices=[m['external_ref']+' · '+m['date']+' · '+m['amount'] for m in matches];chosen,ok=QInputDialog.getItem(dialog,'برداشتن تطبیق','تراکنش بانکی',choices,0,False)
            if not ok or QMessageBox.question(dialog,'برداشتن تطبیق','تطبیق انتخاب‌شده برداشته شود؟',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            try:request(self.panel,'finance/bank-unmatch',dict(company=self.panel.company.currentData(),id=matches[choices.index(chosen)]['id']));self.reload();QMessageBox.information(dialog,'تطبیق','تطبیق برداشته شد.')
            except Exception as exc:QMessageBox.warning(dialog,'تطبیق',str(exc))
        confirm.clicked.connect(match_selected);undo.clicked.connect(remove_match);dialog.exec()
    def show_data_quality(self):
        if not self.ready('view'):return
        from data_quality import inspect
        company=self.panel.company.currentData()
        records=[r for r in self.panel.records if r.get('kind')!='invoice']+list(self.data.get('invoice_documents',[]))
        findings=inspect(records,self.data,company)
        dialog=QDialog(self);dialog.setWindowTitle('بررسی سلامت اطلاعات');dialog.resize(900,480);layout=QVBoxLayout(dialog)
        note=QLabel('این موارد فقط احتمال خطا یا نقص‌اند و از داده‌های قابل مشاهده همین شرکت بررسی شده‌اند؛ هیچ اطلاعاتی تغییر نمی‌کند.');note.setWordWrap(True);layout.addWidget(note)
        table=QTableWidget(len(findings),3);table.setHorizontalHeaderLabels(['بخش','مورد','نیازمند بررسی']);table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch)
        for row,item in enumerate(findings):
            for col,key in enumerate(('kind','title','reason')):table.setItem(row,col,QTableWidgetItem(str(item[key])))
        layout.addWidget(table);layout.addWidget(QLabel('تعداد موارد: '+fa(len(findings))))
        edit=QPushButton('باز کردن مورد انتخابی');layout.addWidget(edit)
        def open_finding():
            index=table.currentRow()
            if not 0<=index<len(findings):QMessageBox.information(dialog,'بررسی','ابتدا یک مورد را انتخاب کنید.');return
            finding=findings[index];kind={'مشتری':'client','فاکتور':'invoice'}.get(finding['kind'])
            record=next((r for r in self.panel.records if r.get('id')==finding['id'] and r.get('company_id')==company and r.get('kind')==kind),None)
            if not record:QMessageBox.information(dialog,'بررسی','برای این مورد از زبانه چک‌ها یا دریافت و پرداخت استفاده کنید.');return
            self.panel.edit_record(kind,record)
        edit.clicked.connect(open_finding);dialog.exec()
    def show_aging(self):
        from finance_aging import aging
        rows=aging(self.data.get('invoice_documents',[]));dialog=QDialog(self);dialog.setWindowTitle('سررسید فاکتورها');dialog.resize(980,520);layout=QVBoxLayout(dialog)
        note=QLabel('مانده بر اساس فاکتورهای قابل مشاهده است؛ سررسید ثبت‌نشده نامشخص نمایش داده می‌شود. چک در انتظار وصول جزء مانده است. فاکتورهای فاقد اطلاعات کامل تسویه در این فهرست محاسبه نمی‌شوند و نیاز به بررسی دارند.');note.setWordWrap(True);layout.addWidget(note)
        filters=QHBoxLayout();customer_filter=QLineEdit();customer_filter.setPlaceholderText('جستجوی طرف حساب');filters.addWidget(customer_filter);kind_filter=QComboBox();kind_filter.addItems(['همه','دریافتنی','پرداختنی']);filters.addWidget(kind_filter);bucket_filter=QComboBox();bucket_filter.addItems(['همه سررسیدها','جاری','۱ تا ۳۰ روز','۳۱ تا ۶۰ روز','۶۱ تا ۹۰ روز','بیش از ۹۰ روز','نامشخص']);filters.addWidget(bucket_filter);layout.addLayout(filters)
        table=QTableWidget(0,7);table.setHorizontalHeaderLabels(['طرف حساب','نوع','شماره فاکتور','شماره سند','سررسید','مانده ریال','وضعیت']);table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.setSelectionBehavior(QAbstractItemView.SelectRows);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);visible=[]
        def draw(*_):
            visible.clear();needle=normalize(customer_filter.text()).casefold()
            for row in rows:
                name=self.panel.customer_payload(row['customer']).get('title') or row.get('customer_name') or row['customer']
                if needle not in normalize(name).casefold() or kind_filter.currentText()!='همه' and row['kind']!=kind_filter.currentText() or bucket_filter.currentIndex() and row['bucket']!=bucket_filter.currentText():continue
                visible.append((row,name))
            table.setRowCount(len(visible))
            for i,(row,name) in enumerate(visible):
                for j,value in enumerate((name,row['kind'],row['number'],row['document'],row['due'] or 'نامشخص',row['amount'],row['bucket'])):table.setItem(i,j,QTableWidgetItem(str(value)))
        customer_filter.textChanged.connect(draw);kind_filter.currentIndexChanged.connect(draw);bucket_filter.currentIndexChanged.connect(draw);draw();layout.addWidget(table)
        copy=QPushButton('کپی متن یادآوری برای ردیف انتخابی');layout.addWidget(copy)
        def copy_reminder():
            index=table.currentRow()
            if not 0<=index<len(visible):QMessageBox.information(dialog,'یادآوری','ابتدا یک فاکتور را انتخاب کنید.');return
            row,name=visible[index]
            if row['kind']!='دریافتنی':QMessageBox.information(dialog,'یادآوری','این ردیف پرداختنی است؛ یک دریافتنی انتخاب کنید.');return
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText('سلام، بابت فاکتور شماره '+str(row['number'])+' مبلغ '+str(row['amount'])+' ریال باقی مانده است. لطفاً زمان پرداخت را اعلام فرمایید. سپاسگزاریم.')
            QMessageBox.information(dialog,'یادآوری','متن برای بازبینی و ارسال توسط شما کپی شد.')
        copy.clicked.connect(copy_reminder)
        followup=QPushButton('ثبت پیگیری / قول پرداخت');layout.addWidget(followup)
        def add_followup():
            index=table.currentRow()
            if not 0<=index<len(visible):QMessageBox.information(dialog,'پیگیری','ابتدا یک فاکتور را انتخاب کنید.');return
            from ui_permissions import allowed
            if not allowed(self.panel.owner,'workspace','create'):QMessageBox.information(dialog,'دسترسی','دسترسی ثبت کار شرکت لازم است.');return
            row,name=visible[index];org=self.panel.owner.org
            from org_ui import RecordDialog
            org.company.setCurrentIndex(org.company.findData(self.panel.company.currentData()));form=RecordDialog(org,'task')
            form.widgets['title'][0].setText('پیگیری پرداخت · '+name)
            form.widgets['notes'][0].setPlainText('طرف حساب: '+name+'\nشماره فاکتور: '+str(row['number'])+'\nشماره سند: '+str(row['document'])+'\nمانده هنگام ثبت: '+str(row['amount'])+' ریال\nتوضیح قول پرداخت:')
            if row['due']:form.widgets['due_date'][0].setText(row['due'])
            if form.exec():
                form.payload['related_customer_id']=row['customer'];form.payload['related_invoice_id']=row.get('invoice_id','');form.payload['related_invoice_document']=str(row['document'])
                org.save_dialog(form)
        followup.clicked.connect(add_followup);dialog.exec()
    def show_statement(self):
        index=self.tables['balances'].currentRow()
        if not 0<=index<len(getattr(self,'balance_customers',[])):return
        customer=self.balance_customers[index]
        from finance_ledger import statement
        rows,incomplete=statement(customer,self.data.get('invoice_documents',[]),self.data.get('transactions',[]),self.data.get('check_transfers',[]),self.data.get('checks',[]))
        dialog=QDialog(self);dialog.setWindowTitle('گردش طرف حساب · '+self.panel.customer_payload(customer).get('title',''));dialog.resize(900,520);layout=QVBoxLayout(dialog)
        note=QLabel('مانده مثبت: طلب شرکت · مانده منفی: بدهی شرکت. چک‌ها با وضعیت فعلی نمایش داده می‌شوند؛ تاریخ تسویه داخل فاکتور همان تاریخ سند است. تاریخ وصول قدیمی نامشخص جدا نشان داده می‌شود.'+(' · برخی اسناد قدیمی نیاز به بررسی دارند' if incomplete else ''));note.setWordWrap(True);layout.addWidget(note)
        table=QTableWidget(len(rows),6);table.setHorizontalHeaderLabels(['تاریخ شمسی','شماره سند','شرح','افزایش طلب','کاهش طلب','مانده']);table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.setSelectionBehavior(QAbstractItemView.SelectRows);table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch)
        for i,row in enumerate(rows):
            for j,key in enumerate(('date','document','description','debit','credit','balance')):table.setItem(i,j,QTableWidgetItem(row[key]))
        layout.addWidget(table)
        company=self.panel.company.currentData();related=[r for r in self.panel.owner.org.records if r.get('kind')=='task' and r.get('company_id')==company and r.get('payload',{}).get('related_customer_id')==customer and not r.get('deleted')]
        if related:
            layout.addWidget(QLabel('پیگیری‌های مرتبط قابل مشاهده'))
            followups=QTableWidget(len(related),3);followups.setHorizontalHeaderLabels(['عنوان','موعد','وضعیت']);followups.setEditTriggers(QAbstractItemView.NoEditTriggers);followups.setSelectionBehavior(QAbstractItemView.SelectRows);followups.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
            from org_schema import STATUSES
            for i,item in enumerate(related):
                p=item.get('payload',{})
                for j,value in enumerate((p.get('title',''),p.get('due_date',''),STATUSES.get(p.get('status'),p.get('status','')))):followups.setItem(i,j,QTableWidgetItem(str(value)))
            layout.addWidget(followups)
        dialog.exec()
    def form(self,title,fields):
        d=QDialog(self);d.setWindowTitle(title);f=QFormLayout(d);inputs={}
        for key,label,default in fields:
            inputs[key]=QLineEdit(default)
            if key in ('value','number','due_date'):
                pattern='[0-9۰-۹٠-٩/]*' if key=='due_date' else '[0-9۰-۹٠-٩]*'
                inputs[key].setValidator(QRegularExpressionValidator(QRegularExpression(pattern),inputs[key]))
            f.addRow(label,inputs[key])
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);f.addRow(buttons)
        if d.exec()!=QDialog.Accepted:return None
        return {k:normalize(v.text().strip()) for k,v in inputs.items()}
    def add_bank(self):
        if not self.ready('edit'):return
        values=self.form('حساب بانکی',[('name','نام بانک / حساب',''),('account_no','شماره حساب',''),('iban','شماره شبا','')])
        if values is None:return
        try:request(self.panel,'finance/bank',dict(company=self.panel.company.currentData(),**values));self.reload()
        except Exception as exc:QMessageBox.warning(self,'ثبت حساب',str(exc))
    def add_check(self):
        if not self.ready('edit'):return
        direction,ok=QInputDialog.getItem(self,'نوع چک','نوع چک',['دریافتی','پرداختی'],0,False)
        if not ok:return
        values=self.form('چک '+direction,[('number','شماره چک',''),('bank','بانک',''),('value','مبلغ؛ ریال',''),('due_date','سررسید شمسی',jformat(today_j())),('description','توضیحات','')])
        if values is None:return
        values['direction']='received' if direction=='دریافتی' else 'issued'
        try:request(self.panel,'finance/check',dict(company=self.panel.company.currentData(),**values));self.reload()
        except Exception as exc:QMessageBox.warning(self,'ثبت چک',str(exc))
    def edit_check(self):
        if not self.ready('edit'):return
        index=self.tables['checks'].currentRow();checks=self.data['checks']
        if not 0<=index<len(checks):QMessageBox.information(self,'چک','ابتدا یک چک را انتخاب کنید.');return
        old=checks[index];direction,ok=QInputDialog.getItem(self,'نوع چک','نوع چک',['دریافتی','پرداختی'],0 if old.get('direction','received')=='received' else 1,False)
        if not ok:return
        values=self.form('ویرایش چک',[('number','شماره چک',old['number']),('bank','بانک',old['bank']),('value','مبلغ؛ ریال',old['amount']),('due_date','سررسید شمسی',old['due_date']),('description','توضیحات',old['description'])])
        if values is None:return
        values['direction']='received' if direction=='دریافتی' else 'issued'
        try:request(self.panel,'finance/check/edit',dict(company=self.panel.company.currentData(),id=old['id'],version=old['version'],**values));self.reload()
        except Exception as exc:QMessageBox.warning(self,'ویرایش چک',str(exc))
    def transfer_check(self):
        if not self.ready('edit'):return
        index=self.tables['checks'].currentRow();checks=self.data.get('checks',[])
        if not 0<=index<len(checks):QMessageBox.information(self,'خرج چک','ابتدا چک دریافتی را انتخاب کنید.');return
        check=checks[index];dialog=QDialog(self);dialog.setWindowTitle('خرج چک '+check['number']);form=QFormLayout(dialog);customer=self.panel.customer_picker();form.addRow('طرف حساب دریافت‌کننده',customer);invoice=QComboBox();form.addRow('فاکتور مقصد (اختیاری)',invoice)
        def fill(*_):
            invoice.clear();invoice.addItem('بدون تخصیص به فاکتور','')
            for record in self.data.get('invoice_documents',[]):
                p=record['payload']
                if p.get('client_id')==customer.currentData() and p.get('document_type') in ('فاکتور خرید','برگشت از فروش') and p.get('status')=='issued':invoice.addItem(p['document_type']+' · '+str(p.get('number',''))+' · مانده '+str(record.get('remaining_after_allocations','نامشخص')),record['id'])
        customer.currentIndexChanged.connect(fill);fill();form.addRow(QLabel('تا هنگام وصول، چک در انتظار می‌ماند و پرداخت نقدی محسوب نمی‌شود.'));buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        if dialog.exec()!=QDialog.Accepted:return
        if not customer.currentData():QMessageBox.warning(self,'خرج چک','طرف حساب را انتخاب کنید.');return
        if QMessageBox.question(self,'تأیید خرج چک','چک به «'+customer.currentText()+'» منتقل شود؟',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:request(self.panel,'finance/check-transfer',dict(company=self.panel.company.currentData(),check_id=check['id'],version=check['version'],recipient_id=customer.currentData(),invoice_id=invoice.currentData() or None));self.reload();self.panel.owner.org.revision=None;self.panel.owner.org.sync()
        except Exception as exc:QMessageBox.warning(self,'خرج چک',str(exc))
    def untransfer_check(self):
        if not self.ready('edit'):return
        index=self.tables['checks'].currentRow();checks=self.data.get('checks',[])
        if not 0<=index<len(checks):QMessageBox.information(self,'برگشت خرج چک','ابتدا چک را انتخاب کنید.');return
        check=checks[index];transfer=next((t for t in self.data.get('check_transfers',[]) if t['check_id']==check['id']),None)
        if not transfer:QMessageBox.information(self,'برگشت خرج چک','برای این چک انتقالی ثبت نشده است.');return
        if QMessageBox.question(self,'تأیید برگشت','خرج این چک در انتظار برداشته شود؟',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:request(self.panel,'finance/check-untransfer',dict(company=self.panel.company.currentData(),id=transfer['id'],version=check['version']));self.reload();self.panel.owner.org.revision=None;self.panel.owner.org.sync()
        except Exception as exc:QMessageBox.warning(self,'برگشت خرج چک',str(exc))
    def check_history(self):
        index=self.tables['checks'].currentRow();checks=self.data.get('checks',[])
        if not 0<=index<len(checks):QMessageBox.information(self,'سابقه چک','ابتدا چک را انتخاب کنید.');return
        try:rows=request(self.panel,'finance/check-history',company=self.panel.company.currentData(),id=checks[index]['id'])
        except Exception as exc:QMessageBox.warning(self,'سابقه چک',str(exc));return
        status={'pending':'در انتظار','deposited':'واگذارشده به بانک','cleared':'وصول‌شده','returned':'برگشتی'}
        dialog=QDialog(self);dialog.setWindowTitle('سابقه چک '+checks[index]['number']);dialog.resize(700,400);layout=QVBoxLayout(dialog);table=QTableWidget(len(rows),4);table.setHorizontalHeaderLabels(['زمان ثبت','کاربر','عملیات','تغییر']);table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.horizontalHeader().setSectionResizeMode(3,QHeaderView.Stretch)
        for i,row in enumerate(rows):
            before=row.get('before') or {};after=row.get('after') or {};change=(status.get(before.get('status'),before.get('status',''))+' ← '+status.get(after.get('status'),after.get('status',''))) if 'status' in before or 'status' in after else 'ثبت یا ویرایش اطلاعات چک'
            for j,value in enumerate((row['created'],row['actor'],{'create':'ثبت','edit':'ویرایش','check_transfer':'خرج چک','check_untransfer':'برگشت خرج چک'}.get(row['action'],row['action']),change)):table.setItem(i,j,QTableWidgetItem(str(value)))
        layout.addWidget(table);dialog.exec()
    def check_status(self):
        if not self.ready('edit'):return
        index=self.tables['checks'].currentRow();checks=self.data['checks']
        if not 0<=index<len(checks):QMessageBox.information(self,'چک','ابتدا یک چک را انتخاب کنید.');return
        old=checks[index];labels=['در انتظار','واگذارشده به بانک','وصول‌شده','برگشتی'];keys=['pending','deposited','cleared','returned'];choice,ok=QInputDialog.getItem(self,'وضعیت چک','وضعیت جدید',labels,max(0,keys.index(old.get('status','pending'))),False)
        if not ok:return
        if QMessageBox.question(self,'تأیید وضعیت','وضعیت چک به «'+choice+'» تغییر کند؟',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:request(self.panel,'finance/check/status',dict(company=self.panel.company.currentData(),id=old['id'],version=old['version'],status=keys[labels.index(choice)]));self.reload();self.panel.owner.org.revision=None;self.panel.owner.org.sync()
        except Exception as exc:QMessageBox.warning(self,'وضعیت چک',str(exc))
    def transaction(self,edit,prefill=None):
        if not self.ready('edit' if edit else 'create'):return
        i=self.tables['transactions'].currentRow();rows=self.visible_documents;old=rows[i] if edit and 0<=i<len(rows) else None
        initial=old or (prefill if isinstance(prefill,dict) else {})
        if edit and not old:QMessageBox.information(self,'سند مالی','ابتدا سند را در فهرست دریافت و پرداخت انتخاب کنید.');return
        if old and old.get('source')=='invoice':self.panel.edit_record('invoice',old['record']);self.reload();return
        if old and old.get('source')=='check':
            idx=next((i for i,row in enumerate(self.data['checks']) if row['id']==old['id']),-1)
            if idx>=0:self.tabs.setCurrentWidget(self.tables['checks']);self.tables['checks'].setCurrentCell(idx,0);self.edit_check()
            return
        d=QDialog(self);d.setWindowTitle('ویرایش سند' if old else 'پیش‌نویس مالی کارنامه' if prefill else 'ثبت دریافت / پرداخت');f=QFormLayout(d);direction=QComboBox();direction.addItem('دریافت','income');direction.addItem('پرداخت','expense');direction.setCurrentIndex(max(0,direction.findData(initial.get('direction','income'))));f.addRow('نوع',direction)
        method=QComboBox()
        if prefill and not old:method.addItem('انتخاب روش پرداخت','')
        for key,label in [('cash','نقد'),('card','کارت به کارت'),('pos','کارتخوان'),('paya','شبا · پایا'),('satna','شبا · ساتنا'),('pol','شبا · پل'),('internal','حساب به حساب'),('cash_deposit','واریز بانکی'),('other','سایر')]:method.addItem(label,key)
        method.setCurrentIndex(max(0,method.findData(initial.get('method','' if prefill else 'cash'))));f.addRow('روش',method);bank=QComboBox();bank.addItem('انتخاب حساب','')
        for b in self.data['banks']:bank.addItem(b['name']+' · '+b['account_no'],b['id'])
        bank.setCurrentIndex(max(0,bank.findData((old or {}).get('bank_id'))));f.addRow('حساب بانکی',bank)
        customer=self.panel.customer_picker((old or {}).get('customer_id'));customer.setObjectName('FinanceCustomer');f.addRow('مشتری / طرف حساب',customer)
        allocations=[dict(part) for part in (old or {}).get('allocations',[])];allocation_button=QPushButton('تخصیص به فاکتورها');allocation_button.setObjectName('FinanceAllocate');allocation_note=QLabel('');allocation_note.setWordWrap(True);allocation_row=QHBoxLayout();allocation_row.addWidget(allocation_button);allocation_row.addWidget(allocation_note,1);f.addRow('فاکتورهای مرتبط',allocation_row)
        def show_allocation_count():allocation_note.setText(fa(len(allocations))+' فاکتور انتخاب شده' if allocations else 'بدون تخصیص')
        def choose_allocations():
            from decimal import Decimal
            from settlement_logic import amount
            if not customer.currentData():QMessageBox.information(d,'تخصیص','ابتدا طرف حساب را انتخاب کنید.');return
            choices=[]
            for item in self.data.get('invoice_documents',[]):
                p=item['payload'];kind=p.get('document_type');expected='income' if kind in ('فاکتور فروش','برگشت از خرید') else 'expense'
                if p.get('client_id')==customer.currentData() and p.get('status') in ('issued','paid') and kind in ('فاکتور فروش','فاکتور خرید','برگشت از فروش','برگشت از خرید') and direction.currentData()==expected and isinstance(p.get('settlement_summary'),dict):choices.append(item)
            existing={a['invoice_id']:str(a['amount']) for a in allocations}
            if not set(existing).issubset({item['id'] for item in choices}):QMessageBox.warning(d,'تخصیص','فاکتور تخصیص‌یافته در انتخاب فعلی در دسترس نیست. ابتدا طرف حساب و نوع سند را بررسی کنید.');return
            choose=QDialog(d);choose.setWindowTitle('تخصیص مبلغ به فاکتورها');choose.resize(750,480);layout=QVBoxLayout(choose);hint=QLabel('مبلغ هر فاکتور را وارد کنید؛ قسمت تخصیص‌نیافته در حساب طرف مقابل باقی می‌ماند.');hint.setWordWrap(True);layout.addWidget(hint);table=QTableWidget(len(choices),3);table.setObjectName('FinanceAllocationTable');table.setHorizontalHeaderLabels(['فاکتور','مانده قابل تخصیص','مبلغ تخصیص ریال']);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);editors=[]
            for i,item in enumerate(choices):
                p=item['payload'];prior=Decimal(existing.get(item['id'],'0'));available=max(Decimal(0),Decimal(item.get('remaining_after_allocations','0'))-Decimal(item.get('allocated_pending_checks','0'))+prior)
                table.setItem(i,0,QTableWidgetItem(p['document_type']+' · '+str(p.get('number',''))));table.setItem(i,1,QTableWidgetItem(str(available)));editor=QLineEdit(existing.get(item['id'],''));editor.setValidator(QRegularExpressionValidator(QRegularExpression('[0-9۰-۹٠-٩]*'),editor));table.setCellWidget(i,2,editor);editors.append((item,editor,available))
            layout.addWidget(table);error=QLabel('');error.setWordWrap(True);layout.addWidget(error);buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);layout.addWidget(buttons);buttons.rejected.connect(choose.reject)
            def accept_allocations():
                nonlocal allocations
                try:
                    parts=[]
                    for item,editor,available in editors:
                        share=amount(normalize(editor.text() or '0'))
                        if share>available:raise ValueError('مبلغ یک فاکتور از مانده قابل تخصیص آن بیشتر است.')
                        if share:parts.append({'invoice_id':item['id'],'amount':str(share)})
                    if len(parts)>50:raise ValueError('حداکثر ۵۰ فاکتور را انتخاب کنید.')
                    if sum((Decimal(part['amount']) for part in parts),Decimal(0))>amount(normalize(value.text() or '0')):raise ValueError('جمع تخصیص‌ها از مبلغ سند بیشتر است.')
                    allocations=parts;show_allocation_count();choose.accept()
                except ValueError as exc:error.setText(str(exc))
            buttons.accepted.connect(accept_allocations);choose.exec()
        allocation_button.clicked.connect(choose_allocations);show_allocation_count()
        category=QComboBox();category.setEditable(True);category.addItems(['','اجاره','حمل','اینترنت و ارتباطات','حقوق و دستمزد','خدمات','سایر']);category.setCurrentText(initial.get('category',''));category.lineEdit().setMaxLength(100);f.addRow('دسته‌بندی اختیاری',category)
        value=QLineEdit(str(initial.get('amount','')));value.setObjectName('FinanceAmount');value.setValidator(QRegularExpressionValidator(QRegularExpression('[0-9۰-۹٠-٩]*'),value));f.addRow('مبلغ ریال',value);date=QLineEdit(initial.get('date',jformat(today_j())));date.setValidator(QRegularExpressionValidator(QRegularExpression('[0-9۰-۹٠-٩/]*'),date));f.addRow('تاریخ شمسی',date);reason=QLineEdit(initial.get('reason',''));reason.setObjectName('FinanceReason');f.addRow('علت',reason)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        def accept_form():
            from settlement_logic import amount
            from storage import parse_j
            try:
                if not method.currentData():raise ValueError('روش دریافت یا پرداخت را انتخاب کنید.')
                if method.currentData()!='cash' and not bank.currentData():raise ValueError('حساب بانکی را انتخاب کنید.')
                if amount(normalize(value.text() or '0'))<=0:raise ValueError('مبلغ باید بیشتر از صفر باشد.')
                parse_j(normalize(date.text()))
                if not reason.text().strip():raise ValueError('علت دریافت یا پرداخت را وارد کنید.')
            except ValueError as exc:QMessageBox.warning(d,'اطلاعات مالی',str(exc));return
            d.accept()
        buttons.accepted.connect(accept_form);buttons.rejected.connect(d.reject);f.addRow(buttons)
        if d.exec()!=QDialog.Accepted:return
        payload=dict(direction=direction.currentData(),method=method.currentData(),bank_id=bank.currentData(),customer_id=customer.currentData(),allocations=allocations,category=category.currentText(),amount=normalize(value.text()),date=normalize(date.text()),reason=reason.text())
        try:request(self.panel,'finance/transaction',dict(company=self.panel.company.currentData(),payload=payload,id=old['id'] if old else None,version=old['version'] if old else None));self.reload()
        except Exception as exc:QMessageBox.warning(self,'سند مالی',str(exc))
    def render_documents(self,*_):
        query=normalize(self.search.text()).casefold();self.visible_documents=[]
        for row in self.data.get('transactions',[]):
            invoice=row.get('record',{}).get('payload',{});hay=normalize(str(row.get('document_no',''))+' '+str(invoice.get('number',''))+' '+str(row.get('reason',''))+' '+str(row.get('category',''))).casefold()
            if not query or query in hay:self.visible_documents.append(row)
        table=self.tables['transactions'];table.setRowCount(len(self.visible_documents))
        for i,row in enumerate(self.visible_documents):
            refs=[]
            for part in row.get('allocations',[]):
                linked=next((x['payload'] for x in self.data.get('invoice_documents',[]) if x['id']==part['invoice_id']),None)
                if linked:refs.append(linked.get('document_type','')+' '+str(linked.get('number',''))+' ('+str(part['amount'])+')')
            invoice_title='، '.join(refs)
            values=[row['document_no'],'فاکتور' if row.get('source')=='invoice' else 'دریافت' if row['direction']=='income' else 'پرداخت',METHOD_LABELS.get(row['method'],'فاکتور' if row['method']=='invoice' else row['method']),row['amount'],row['date'],row['reason'],invoice_title,row.get('category','')]
            for j,value in enumerate(values):table.setItem(i,j,QTableWidgetItem(str(value)))

