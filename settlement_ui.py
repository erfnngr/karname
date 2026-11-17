"""Editable list of cash, bank and check allocations for one invoice."""
from decimal import Decimal
from PySide6.QtCore import Qt,QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QComboBox,QLineEdit,QDialogButtonBox,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QMessageBox,QFrame)
from storage import normalize,fa
from settlement_logic import amount,validate
from finance_ui import request,METHOD_LABELS

class SettlementDialog(QDialog):
    def __init__(self,panel,payload,record=None,parent=None):
        super().__init__(parent or panel);self.setWindowTitle('امور مالی فاکتور');self.setLayoutDirection(Qt.RightToLeft);self.resize(820,560);self.panel=panel;self.payload=payload;self.record=record;self.lines=[dict(x) for x in payload.get('settlement',[])];self.data=request(panel,'finance',company=panel.company.currentData());v=QVBoxLayout(self);v.setContentsMargins(18,16,18,16);v.setSpacing(10)
        heading=QHBoxLayout();title=QLabel('تسویه فاکتور');title.setObjectName('Hero');heading.addWidget(title);heading.addStretch();step=QLabel('۲  امور مالی    ←    ۳  پیش‌نمایش');step.setObjectName('Sub');heading.addWidget(step);v.addLayout(heading)
        summary=QFrame();summary.setObjectName('Panel');metrics=QHBoxLayout(summary);self.metrics={}
        for key,label in [('total','مبلغ فاکتور'),('received','نقد و بانک / وصول‌شده'),('pending_checks','چک در انتظار'),('uncollected','مانده تسویه‌نشده')]:
            block=QVBoxLayout();caption=QLabel(label);caption.setObjectName('Sub');value=QLabel('—');value.setObjectName('DayNumber');block.addWidget(caption);block.addWidget(value);metrics.addLayout(block,1);self.metrics[key]=value
        v.addWidget(summary);bar=QHBoxLayout();subtitle=QLabel('روش‌های تسویه');subtitle.setObjectName('Hero');bar.addWidget(subtitle);bar.addStretch();add=QPushButton('＋  افزودن روش تسویه');add.setObjectName('Primary');bar.addWidget(add);add.clicked.connect(self.add);v.addLayout(bar)
        self.table=QTableWidget(0,3);self.table.setObjectName('SettlementLines');self.table.setHorizontalHeaderLabels(['روش','حساب / چک','مبلغ؛ ریال']);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.setAlternatingRowColors(True);self.table.verticalHeader().setVisible(False);self.table.verticalHeader().setDefaultSectionSize(40);self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch);v.addWidget(self.table,1)
        self.hint=QLabel('در صورت باقی‌ماندن مبلغ، مانده در حساب طرف حساب ثبت می‌شود.');self.hint.setWordWrap(True);self.hint.setObjectName('Sub');v.addWidget(self.hint);self.error=QLabel();self.error.setWordWrap(True);self.error.setObjectName('Warning');v.addWidget(self.error);buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('ادامه و پیش‌نمایش');buttons.button(QDialogButtonBox.Ok).setObjectName('Primary');buttons.button(QDialogButtonBox.Cancel).setText('بازگشت');buttons.accepted.connect(self.confirm);buttons.rejected.connect(self.reject);v.addWidget(buttons);self.render()
    def render(self):
        banks={x['id']:x['name'] for x in self.data['banks']};checks={x['id']:x for x in self.data['checks']};self.table.setRowCount(len(self.lines))
        for i,line in enumerate(self.lines):
            kind=line['kind'];detail=banks.get(line.get('bank_account_id'),'') if kind=='bank' else checks.get(line.get('check_id'),{}).get('number','') if kind=='check' else ''
            values=[METHOD_LABELS.get(line.get('method'), 'چک' if kind=='check' else 'نقد' if kind=='cash' else 'بانکی'),detail,line['amount']]
            for j,value in enumerate(values):self.table.setItem(i,j,QTableWidgetItem(str(value)))
        try:
            summary=self.current_summary();summary['total']=self.payload['totals']['total']
            for key,label in self.metrics.items():label.setText(fa(f"{int(Decimal(summary[key])):,}")+' ریال')
            self.error.clear()
        except ValueError as exc:self.error.setText(str(exc))
    def current_summary(self):
        summary=validate(self.payload['totals']['total'],self.lines);checks={c['id']:c for c in self.data['checks']}
        for line in self.lines:
            if line['kind']!='check':continue
            check=checks.get(line['check_id'])
            if not check:raise ValueError('چک پیدا نشد؛ فهرست را تازه‌سازی کنید.')
            value=Decimal(line['amount']);status=check.get('status','pending')
            if status in ('cleared','returned'):
                summary['pending_checks']=str(Decimal(summary['pending_checks'])-value)
                if status=='cleared':summary['received']=str(Decimal(summary['received'])+value);summary['uncollected']=str(Decimal(summary['uncollected'])-value)
                else:summary['unallocated']=str(Decimal(summary['unallocated'])+value)
        return summary
    def add(self):
        d=QDialog(self);d.setWindowTitle('روش تسویه');f=QFormLayout(d);method=QComboBox()
        for key,label in [('cash','نقد'),('card','کارت به کارت'),('pos','کارتخوان'),('paya','شبا · پایا'),('satna','شبا · ساتنا'),('pol','شبا · پل'),('internal','حساب به حساب'),('cash_deposit','واریز بانکی'),('check','چک'),('other','سایر بانکی')]:method.addItem(label,key)
        f.addRow('روش',method);bank=QComboBox();bank.addItem('انتخاب حساب','')
        for b in self.data['banks']:bank.addItem(b['name']+' · '+b['account_no'],b['id'])
        f.addRow('حساب بانکی',bank);checks=QComboBox();checks.addItem('انتخاب چک',None);expected='issued' if self.payload.get('document_type') in ('فاکتور خرید','برگشت از فروش') else 'received';used={x.get('check_id') for x in self.lines if x['kind']=='check'}
        for c in self.data['checks']:
            if c['id'] not in used and c.get('direction','received')==expected and ((not c['invoice_id'] and c.get('status','pending')!='returned') or (self.record and c['invoice_id']==self.record['id'])):checks.addItem(c['number']+' · '+c['bank']+' · '+c['amount'],c)
        f.addRow('چک',checks);value=QLineEdit();value.setValidator(QRegularExpressionValidator(QRegularExpression('[0-9۰-۹٠-٩]*'),value));f.addRow('مبلغ ریال',value)
        def update(*_):
            k=method.currentData();was_readonly=value.isReadOnly();bank.setEnabled(k not in ('cash','check'));checks.setEnabled(k=='check');value.setReadOnly(k=='check')
            if k=='check' and checks.currentData():value.setText(str(checks.currentData()['amount']))
            elif k=='check':value.clear()
            elif was_readonly:value.clear()
        method.currentIndexChanged.connect(update);checks.currentIndexChanged.connect(update);update();buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);f.addRow(buttons)
        if d.exec()!=QDialog.Accepted:return
        try:
            key=method.currentData();value_number=amount(normalize(value.text()))
            if value_number<=0:raise ValueError('مبلغ را وارد کنید.')
            if key=='check':
                check=checks.currentData()
                if not check:raise ValueError('چک را انتخاب کنید.')
                line={'kind':'check','amount':str(value_number),'check_id':check['id']}
            elif key=='cash':line={'kind':'cash','amount':str(value_number)}
            else:
                if not bank.currentData():raise ValueError('حساب بانکی را انتخاب کنید.')
                line={'kind':'bank','amount':str(value_number),'bank_account_id':bank.currentData(),'method':key}
            validate(self.payload['totals']['total'],self.lines+[line]);self.lines.append(line);self.render()
        except Exception as exc:QMessageBox.warning(self,'روش تسویه',str(exc))
    def remove(self):
        row=self.table.currentRow()
        if 0<=row<len(self.lines):self.lines.pop(row);self.render()
    def confirm(self):
        try:
            summary=self.current_summary()
            message='نقد و بانک / چک وصول‌شده: '+summary['received']+' ریال\nچک در انتظار: '+summary['pending_checks']+' ریال\nمانده بدون روش تسویه: '+summary['unallocated']+' ریال\nمانده تسویه‌نشده: '+summary['uncollected']+' ریال\n\nادامه می‌دهید؟'
            if QMessageBox.question(self,'تأیید امور مالی',message,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            self.summary=summary;self.accept()
        except Exception as exc:self.error.setText(str(exc))
