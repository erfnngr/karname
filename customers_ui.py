"""Company-scoped customer files reused by tax work and itemized invoices."""
import copy,json,secrets
from pathlib import Path
from PySide6.QtCore import Qt,QRegularExpression,QTimer,QEvent
from PySide6.QtGui import QRegularExpressionValidator,QKeySequence,QShortcut
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QGridLayout,QFormLayout,QTabWidget,QLabel,QLineEdit,QPlainTextEdit,QTextBrowser,QComboBox,QPushButton,QDialogButtonBox,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QFileDialog,QMessageBox,QStyledItemDelegate,QFrame)
from customer_data import GROUPS,TYPES,FIELDS,customer,invoice,buyer_snapshot,missing_fields
from storage import jformat,today_j,fa,normalize
from ui_icons import iconize

def text(value):
    w=QLabel(str(value));w.setWordWrap(True);w.setTextFormat(Qt.PlainText);return w

def button(title,key,fn):
    from ui_icons import ICONS,symbol
    b=QPushButton(title);iconize(b,key if key in ICONS else 'open',title)
    if key not in ICONS:b.setIcon(symbol(key))
    b.clicked.connect(fn);return b

def customer_summary(value):
    return '\n'.join(filter(None,[value.get('legal_name') or value.get('title',''),' · '.join(label+': '+value[key] for key,label in [('national_id','شناسه / کد ملی'),('economic_code','شماره اقتصادی'),('postal_code','کد پستی')] if value.get(key)),value.get('address','')]))

class LiveInvoiceDelegate(QStyledItemDelegate):
    def createEditor(self,parent,option,index):
        editor=super().createEditor(parent,option,index)
        if isinstance(editor,QLineEdit):
            editor.setStyleSheet('QLineEdit { padding: 1px 4px; border-width: 1px; border-radius: 2px; }')
            if index.column() in (1,3,4,5,10):editor.setValidator(QRegularExpressionValidator(QRegularExpression('[0-9۰-۹٠-٩]*(\\.[0-9۰-۹٠-٩]*)?'),editor))
            editor.textEdited.connect(lambda _text:self.commitData.emit(editor))
        return editor
    def setEditorData(self,editor,index):
        if editor.property('invoice_loaded'):return
        super().setEditorData(editor,index);editor.setProperty('invoice_loaded',True)
    def eventFilter(self,editor,event):
        if isinstance(editor,QLineEdit) and event.type()==QEvent.KeyPress and event.key() in (Qt.Key_Return,Qt.Key_Enter):
            table=self.parent();row=table.currentRow();column=table.currentColumn();self.commitData.emit(editor);self.closeEditor.emit(editor);QTimer.singleShot(0,lambda:table.advance_from(row,column));return True
        return super().eventFilter(editor,event)

class InvoiceTable(QTableWidget):
    def keyPressEvent(self,event):
        item=self.item(self.currentRow(),0)
        if event.key() in (Qt.Key_Return,Qt.Key_Enter) and item and not item.data(Qt.UserRole+2):
            self.advance_from(self.currentRow(),self.currentColumn());event.accept();return
        if item and item.data(Qt.UserRole+2) and event.text() and event.text().isprintable() and not event.modifiers() & (Qt.ControlModifier|Qt.AltModifier|Qt.MetaModifier):
            self.window().choose_product(event.text());event.accept();return
        super().keyPressEvent(event)
    def advance_from(self,row,column):
        header=self.horizontalHeader();columns=[header.logicalIndex(i) for i in range(header.count())];columns=[i for i in columns if not self.isColumnHidden(i) and self.item(row,i) and self.item(row,i).flags() & Qt.ItemIsEditable]
        current=header.visualIndex(column)
        for col in columns:
            if header.visualIndex(col)>current:
                self.setCurrentCell(row,col);self.setFocus();self.editItem(self.item(row,col));return
        self.window().ensure_empty_row();self.go_to_empty_row()
    def go_to_empty_row(self):
        for row in range(self.rowCount()):
            item=self.item(row,0)
            if item and item.data(Qt.UserRole+2):self.setCurrentCell(row,0);self.setFocus();return


class ProductPicker(QDialog):
    """Search registered products and add one or more without typing a new item."""
    def __init__(self,parent,data,query=''):
        super().__init__(parent);self.setWindowTitle('انتخاب کالا و خدمت');self.resize(780,520);self.setLayoutDirection(Qt.RightToLeft)
        self.products=[p for p in data.get('products',[]) if p.get('active')];self.groups={g['id']:g for g in data.get('groups',[])};self.filtered=[]
        layout=QVBoxLayout(self);layout.setContentsMargins(18,18,18,18);layout.setSpacing(10)
        title=text('انتخاب کالا و خدمت');title.setObjectName('Hero');layout.addWidget(title)
        hint=text('نام یا کد کالا را جست‌وجو کنید؛ می‌توانید چند کالا را هم‌زمان انتخاب کنید.');hint.setObjectName('Sub');layout.addWidget(hint)
        filters=QHBoxLayout();self.search=QLineEdit();self.search.setObjectName('ProductSearch');self.search.setPlaceholderText('جست‌وجو بر اساس نام یا کد کالا');filters.addWidget(self.search,1)
        self.group=QComboBox();self.group.addItem('همه گروه‌ها','')
        for group in sorted(self.groups.values(),key=lambda g:g.get('name','')):
            self.group.addItem(group.get('name',''),group['id'])
        filters.addWidget(self.group);layout.addLayout(filters)
        self.table=QTableWidget(0,5);self.table.setObjectName('ProductPickerTable');self.table.setHorizontalHeaderLabels(['کد','نام کالا / خدمت','گروه','قیمت فروش؛ ریال','موجودی']);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.ExtendedSelection);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.verticalHeader().setVisible(False);self.table.setAlternatingRowColors(True);self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch);self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.Stretch);layout.addWidget(self.table,1)
        self.count=text('');self.count.setObjectName('Sub');layout.addWidget(self.count)
        actions=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);actions.button(QDialogButtonBox.Ok).setText('افزودن به فاکتور');actions.button(QDialogButtonBox.Ok).setObjectName('Primary');actions.button(QDialogButtonBox.Cancel).setText('بازگشت');actions.accepted.connect(self.accept_selection);actions.rejected.connect(self.reject);layout.addWidget(actions)
        self.search.textChanged.connect(self.render);self.group.currentIndexChanged.connect(self.render);self.table.doubleClicked.connect(lambda *_:self.accept_selection());self.search.setText(query);self.render();self.search.setFocus();self.search.setCursorPosition(len(query))
    def render(self,*_):
        query=normalize(self.search.text()).strip().casefold();group_id=self.group.currentData();self.filtered=[]
        for product in self.products:
            group=self.groups.get(product.get('group_id'),{});parent=group.get('parent_id')
            if group_id and group_id not in (product.get('group_id'),parent):continue
            if query and query not in normalize(str(product.get('name',''))+' '+str(product.get('code',''))).casefold():continue
            self.filtered.append(product)
        self.table.setRowCount(len(self.filtered))
        for row,product in enumerate(self.filtered):
            group=self.groups.get(product.get('group_id'),{});parent=self.groups.get(group.get('parent_id'),{});group_name=' / '.join(filter(None,[parent.get('name',''),group.get('name','')]))
            for col,value in enumerate((product.get('code',''),product.get('name',''),group_name,product.get('sale_price',''),product.get('balance',''))):self.table.setItem(row,col,QTableWidgetItem(str(value)))
        self.count.setText(fa(len(self.filtered))+' کالا در فهرست')
    def accept_selection(self):
        rows=sorted({index.row() for index in self.table.selectionModel().selectedRows()})
        if not rows:self.count.setText('ابتدا حداقل یک کالا را انتخاب کنید.');return
        self.selected_products=[self.filtered[row] for row in rows];self.accept()

class CustomerDialog(QDialog):
    def __init__(self,panel,record=None,read_only=False):
        super().__init__(panel);self.panel=panel;self.record=record;self.read_only=read_only;self.fields={};self.setWindowTitle('پرونده مشتری' if record else 'مشتری جدید');self.setLayoutDirection(Qt.RightToLeft);self.resize(790,650);v=QVBoxLayout(self);tabs=QTabWidget();v.addWidget(tabs,1);old=(record or {}).get('payload',{})
        for title,fields in GROUPS:
            page=QWidget();grid=QGridLayout(page);grid.setColumnStretch(0,1);grid.setColumnStretch(1,1);row=0;column=0
            for key,label,kind in fields:
                block=QWidget();b=QVBoxLayout(block);b.setContentsMargins(3,4,3,4);b.setSpacing(5);b.addWidget(text(label+(' *' if key=='title' else '')));value=old.get(key,'حقوقی' if key=='customer_type' else 'active' if key=='status' else 'ایران' if key=='country' else '')
                if kind in ('type','status','user'):
                    w=QComboBox()
                    if kind=='type':
                        for name in TYPES:w.addItem(name,name)
                    elif kind=='status':w.addItem('فعال','active');w.addItem('بایگانی','archived')
                    else:
                        w.addItem('انتخاب نشده','')
                        for person in panel.owner.org.people:
                            if person['global_role']=='group_admin' or any(m['company_id']==panel.company.currentData() for m in person['memberships']):w.addItem(person['fullname'],person['id'])
                    w.setCurrentIndex(max(0,w.findData(value)))
                elif kind=='multiline':w=QPlainTextEdit(str(value));w.setMaximumHeight(90)
                else:
                    w=QLineEdit(str(value))
                    if kind=='digits' or key in ('email','website','iban','phone','mobile','account_no'):w.setLayoutDirection(Qt.LeftToRight)
                w.setAccessibleName(label);w.setEnabled(not read_only);self.fields[key]=(w,kind);b.addWidget(w)
                if kind=='multiline':
                    if column:row+=1;column=0
                    grid.addWidget(block,row,0,1,2);row+=1
                else:
                    grid.addWidget(block,row,column);column+=1
                    if column==2:row+=1;column=0
            grid.setRowStretch(row+1,1);tabs.addTab(page,title)
        self.delete_requested=False;self.error=text('اطلاعات مشتری در فاکتورها قابل استفاده است. شماره مشتری جدید در مرکز شرکت از ۱۰۰ تخصیص می‌یابد.');v.addWidget(self.error);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('ذخیره مشتری');buttons.button(QDialogButtonBox.Save).setVisible(not read_only);buttons.button(QDialogButtonBox.Cancel).setText('بستن');buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);v.addWidget(buttons)
        if record and panel.can('delete'):
            delete=QPushButton('حذف مشتری');delete.clicked.connect(self.delete_customer);v.addWidget(delete)
    def delete_customer(self):
        if self.panel.confirm_customer_delete(self,self.record):
            self.delete_requested=True;self.accept()
    def values(self):
        p=copy.deepcopy((self.record or {}).get('payload',{}))
        for key,(w,kind) in self.fields.items():p[key]=w.currentData() if kind in ('type','status','user') else w.toPlainText() if kind=='multiline' else w.text()
        return customer(p)
    def validate(self):
        try:self.payload=self.values();self.accept()
        except ValueError as exc:self.error.setText(str(exc))

class TaxJobDialog(QDialog):
    def __init__(self,panel,record=None,selected=None):
        super().__init__(panel);self.panel=panel;self.record=record;self.setWindowTitle('کار مالیاتی مشتری');self.resize(650,610);v=QVBoxLayout(self);f=QFormLayout();v.addLayout(f);p=(record or {}).get('payload',{});self.client=panel.customer_picker(p.get('client_id') or (selected or {}).get('id'));f.addRow('مشتری',self.client);self.preview=text('');v.addWidget(self.preview);self.title=QLineEdit(p.get('title',''));f.addRow('عنوان کار',self.title);self.kind=QComboBox();self.kind.setEditable(True);self.kind.addItems(['اظهارنامه عملکرد','ارزش افزوده','مالیات حقوق','سامانه مؤدیان','سایر']);self.kind.setCurrentText(p.get('tax_kind','اظهارنامه عملکرد'));f.addRow('نوع کار',self.kind);self.period=QLineEdit(p.get('period',''));f.addRow('دوره / سال مالی',self.period);self.due=QLineEdit(p.get('due_date',jformat(today_j())));f.addRow('موعد شمسی',self.due);self.status=QComboBox();from org_schema import STATUSES
        for k,label in STATUSES.items():self.status.addItem(label,k)
        self.status.setCurrentIndex(max(0,self.status.findData(p.get('status','draft'))));f.addRow('وضعیت',self.status);self.notes=QPlainTextEdit(p.get('notes',''));self.notes.setMaximumHeight(100);f.addRow('توضیحات',self.notes);self.error=text('موعد این کار پس از ثبت در تقویم و یادآورها نمایش داده می‌شود.');v.addWidget(self.error);self.client.currentIndexChanged.connect(self.prefill);self.prefill();buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);buttons.button(QDialogButtonBox.Save).setText('ثبت کار');buttons.button(QDialogButtonBox.Cancel).setText('بستن');v.addWidget(buttons)
    def prefill(self):
        value=self.panel.customer_payload(self.client.currentData());self.preview.setText(customer_summary(value))
        if not self.record:
            if not self.title.text():self.title.setText(self.kind.currentText()+' · '+value.get('title',''))
            if not self.period.text():self.period.setText(value.get('fiscal_year',''))
    def validate(self):
        try:
            from storage import parse_j
            parse_j(self.due.text());self.payload=dict((self.record or {}).get('payload',{}),title=self.title.text().strip(),client_id=self.client.currentData(),tax_kind=self.kind.currentText(),period=self.period.text(),due_date=normalize(self.due.text()),status=self.status.currentData(),notes=self.notes.toPlainText(),category='مالیات')
            if not self.payload['title'] or not self.payload['client_id']:raise ValueError('عنوان و مشتری را انتخاب کنید.')
            self.accept()
        except ValueError as exc:self.error.setText(str(exc))

class InvoiceDialog(QDialog):
    def __init__(self,panel,record=None,selected=None):
        super().__init__(panel);self.panel=panel;self.record=record;self.refresh_customer=False;self.delete_requested=False;self.setWindowTitle('صدور و ویرایش فاکتور');self.setLayoutDirection(Qt.RightToLeft);self.resize(1120,760);v=QVBoxLayout(self);v.setContentsMargins(16,12,16,12);v.setSpacing(8)
        heading=QHBoxLayout();title=text('فاکتور');title.setObjectName('Hero');heading.addWidget(title);subtitle=text('اطلاعات سند، اقلام و تسویه');subtitle.setObjectName('Sub');heading.addWidget(subtitle);heading.addStretch();step=text('۱ اقلام  •  ۲ مالی  •  ۳ پیش‌نمایش');step.setWordWrap(False);step.setObjectName('Sub');heading.addWidget(step);v.addLayout(heading)
        info=QFrame();info.setObjectName('Panel');head=QGridLayout(info);head.setContentsMargins(12,9,12,9);head.setHorizontalSpacing(12);head.setVerticalSpacing(5);v.addWidget(info);p=(record or {}).get('payload',{});self.client=panel.customer_picker(p.get('client_id') or (selected or {}).get('id'));self.kind=QComboBox();self.kind.addItems(['پیش‌فاکتور','فاکتور فروش']);self.kind.setCurrentText(p.get('document_type','فاکتور فروش'));self.number=QLineEdit(p.get('number',normalize(jformat(today_j())).replace('/','')+'-'+secrets.token_hex(3).upper()));self.date=QLineEdit(p.get('date',jformat(today_j())));self.due=QLineEdit(p.get('due_date',''));self.status=QComboBox()
        self.kind.setItemText(0,'پیش‌فروش / پیش‌فاکتور');self.kind.setItemData(0,'پیش‌فاکتور');self.kind.setItemData(1,'فاکتور فروش')
        for kind in ('فاکتور خرید','برگشت از فروش','برگشت از خرید'):self.kind.addItem(kind,kind)
        if record:self.kind.setCurrentIndex(max(0,self.kind.findData(p.get('document_type','پیش‌فاکتور'))));self.kind.setEnabled(False)
        if not record:self.number.setText('—');self.number.setToolTip('شماره هنگام ثبت قطعی می‌شود؛ اگر هم‌زمان فاکتور دیگری ثبت شود ممکن است تغییر کند.')
        self.number.setReadOnly(True)
        for field in (self.date,self.due):field.setValidator(QRegularExpressionValidator(QRegularExpression('[0-9۰-۹٠-٩/]*'),field))
        for k,label in [('draft','پیش‌نویس'),('issued','ثبت‌شده'),('paid','تسویه‌شده'),('cancelled','لغوشده')]:self.status.addItem(label,k)
        self.status.setCurrentIndex(max(0,self.status.findData(p.get('status','draft' if record else 'issued'))))
        for i,(label,w) in enumerate([('طرف حساب',self.client),('نوع فاکتور',self.kind),('شماره فاکتور',self.number),('تاریخ شمسی',self.date),('سررسید',self.due),('وضعیت',self.status)]):
            block=QVBoxLayout();block.setSpacing(2);caption=text(label);caption.setObjectName('Sub');block.addWidget(caption)
            if w in (self.date,self.due):
                row=QHBoxLayout();row.addWidget(w,1);pick=QPushButton();iconize(pick,'calendar','انتخاب تاریخ');pick.clicked.connect(lambda checked=False,field=w:self.pick_date(field));row.addWidget(pick);block.addLayout(row)
            else:block.addWidget(w)
            head.addLayout(block,i//3,i%3)
        buyer=QHBoxLayout();self.preview=text('');self.preview.setObjectName('Sub');self.preview.setMaximumHeight(40);buyer.addWidget(self.preview,1);self.refresh_button=QPushButton('به‌روزرسانی اطلاعات طرف حساب');self.refresh_button.setObjectName('Small');self.refresh_button.clicked.connect(self.refresh_buyer);buyer.addWidget(self.refresh_button);v.addLayout(buyer)
        rowbar=QHBoxLayout();section=text('اقلام فاکتور');section.setObjectName('Hero');rowbar.addWidget(section);rowbar.addStretch();self.more_columns=QPushButton('ستون‌های بیشتر');self.more_columns.setObjectName('Small');self.more_columns.setCheckable(True);self.more_columns.toggled.connect(self.show_extra_columns);rowbar.addWidget(self.more_columns);add_product=QPushButton('＋  انتخاب کالا');add_product.setObjectName('Primary');add_product.clicked.connect(self.choose_product);rowbar.addWidget(add_product);remove=QPushButton('حذف ردیف');remove.setObjectName('Small');remove.clicked.connect(self.remove_line);rowbar.addWidget(remove);v.addLayout(rowbar)
        self.table=InvoiceTable(0,11);self.table.setObjectName('InvoiceItems');self.table.setItemDelegate(LiveInvoiceDelegate(self.table));self.table.setHorizontalHeaderLabels(['شرح کالا / خدمت','تعداد','واحد','مبلغ واحد؛ ریال','تخفیف؛ ریال','مالیات ٪','جمع؛ ریال','کد کالا','موجودی فعلی','سود تقریبی','تخفیف ٪']);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive);self.table.setAlternatingRowColors(True);self.table.setSelectionBehavior(QAbstractItemView.SelectItems);self.table.verticalHeader().setDefaultSectionSize(38);self.table.setMinimumHeight(150);self.table.cellDoubleClicked.connect(lambda row,col:self.choose_product() if self.is_empty_row(row) else None)
        self.table.horizontalHeader().moveSection(10,5)
        settings=panel.owner.data.setdefault('settings',{});saved=settings.get('invoice_column_widths',[]);defaults=[230,95,85,155,135,100,155,110,110,140,100];minimums=[200,85,75,135,115,90,130,90,90,110,90]
        for i,width in enumerate(defaults):self.table.setColumnWidth(i,max(minimums[i],saved[i]) if isinstance(saved,list) and i<len(saved) and isinstance(saved[i],int) and 50<=saved[i]<=1000 else width)
        self._ever_visible=False;self.width_timer=QTimer(self);self.width_timer.setSingleShot(True);self.width_timer.setInterval(500);self.width_timer.timeout.connect(self.save_widths);self.table.horizontalHeader().sectionResized.connect(lambda *_:self.width_timer.start());self.finished.connect(lambda _result:self.save_widths(force=True))
        v.addWidget(self.table,1);self._extra_widths={i:self.table.columnWidth(i) for i in (7,8,9,10)};self._legacy_percent_lines=bool(record and any(line.get('discount_rate') not in (None,'','0',0) for line in p.get('lines',[])));self.show_extra_columns(False);shortcut=QShortcut(QKeySequence('Insert'),self);shortcut.activated.connect(self.choose_product);self.product_shortcut=shortcut
        adjustment=QHBoxLayout();self.discount_caption=QLabel('تخفیف کل (ریال)');adjustment.addWidget(self.discount_caption);self.discount_mode=QComboBox();self.discount_mode.addItem('ریال','amount');self.discount_mode.addItem('درصد قبلی','percent')
        self.discount_mode.setCurrentIndex(max(0,self.discount_mode.findData(p.get('invoice_discount_mode','amount'))));self.discount_mode.setVisible(p.get('invoice_discount_mode')=='percent');adjustment.addWidget(self.discount_mode);self.discount_value=QLineEdit(str(p.get('invoice_discount_value','0')));self.discount_value.setMaximumWidth(130);adjustment.addWidget(self.discount_value);adjustment.addWidget(QLabel('هزینه اضافی ریال'));self.additional_charge=QLineEdit(str(p.get('additional_charge','0')));self.additional_charge.setMaximumWidth(130);adjustment.addWidget(self.additional_charge);adjustment.addWidget(QLabel('مالیات هزینه ٪'));self.charge_tax_rate=QLineEdit(str(p.get('charge_tax_rate','0')));self.charge_tax_rate.setMaximumWidth(75);adjustment.addWidget(self.charge_tax_rate);v.addLayout(adjustment)
        for field in (self.discount_value,self.additional_charge,self.charge_tax_rate):field.setValidator(QRegularExpressionValidator(QRegularExpression('[0-9۰-۹٠-٩]*(\\.[0-9۰-۹٠-٩]*)?'),field));field.textChanged.connect(self.compute)
        self.discount_mode.currentIndexChanged.connect(self.discount_mode_changed);self.discount_mode_changed();self.total=text('');self.total.setObjectName('Result');v.addWidget(self.total);self.notes=QLineEdit(p.get('notes',''));self.notes.setPlaceholderText('توضیحات فاکتور (اختیاری)');v.addWidget(self.notes);self.error=text('');self.error.setObjectName('Warning');v.addWidget(self.error);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);self.next_button=buttons.button(QDialogButtonBox.Save);self.next_button.setObjectName('Primary');buttons.button(QDialogButtonBox.Cancel).setText('بستن');v.addWidget(buttons)
        self.table.cellChanged.connect(self.compute)
        for line in p.get('lines',[]):self.add_line(line)
        if not self.table.rowCount():self.ensure_empty_row()
        self.client.currentIndexChanged.connect(self.refresh_buyer);self.kind.currentIndexChanged.connect(self.default_status_for_kind);self.status.currentIndexChanged.connect(self.update_next_button);self.update_next_button();self.show_buyer(p.get('customer_snapshot'));self.compute()
        if not record:self.refresh_invoice_number()
        if record and panel.can('delete') and panel.owner.org.client:
            delete=QPushButton('حذف فاکتور');delete.clicked.connect(self.delete_invoice);v.addWidget(delete)
    def save_widths(self,*_,force=False):
        if force:self.width_timer.stop()
        if not self.isVisible() and not (force and self._ever_visible):return
        widths=[self._extra_widths.get(i,self.table.columnWidth(i)) if self.table.isColumnHidden(i) else self.table.columnWidth(i) for i in range(self.table.columnCount())]
        settings=self.panel.owner.data.setdefault('settings',{})
        if settings.get('invoice_column_widths')==widths:return
        old=settings.get('invoice_column_widths');settings['invoice_column_widths']=widths
        try:self.panel.owner.persist()
        except OSError:
            if old is None:settings.pop('invoice_column_widths',None)
            else:settings['invoice_column_widths']=old
            if self.isVisible():self.error.setText('ذخیره اندازه ستون‌ها انجام نشد؛ دسترسی پوشه اطلاعات را بررسی کنید.')
            else:self.panel.owner.statusBar().showMessage('ذخیره اندازه ستون‌های فاکتور انجام نشد.',10000)
    def show_extra_columns(self,visible):
        for column in (7,8,9,10):
            if not visible and not self.table.isColumnHidden(column):self._extra_widths[column]=self.table.columnWidth(column)
            show=visible and (column!=10 or self._legacy_percent_lines)
            self.table.setColumnHidden(column,not show)
            if show:self.table.setColumnWidth(column,self._extra_widths[column])
    def discount_mode_changed(self,*_):
        percent=self.discount_mode.currentData()=='percent';self.discount_mode.setVisible(percent);self.discount_caption.setText('تخفیف کل (درصد قبلی)' if percent else 'تخفیف کل (ریال)');self.compute()
    def pick_date(self,field):
        from report_ui import JalaliDatePicker
        picker=JalaliDatePicker(field.text(),self)
        if picker.exec()==QDialog.Accepted:field.setText(picker.value())
    def showEvent(self,event):
        self._ever_visible=True;super().showEvent(event);QTimer.singleShot(0,self.fit_visible_columns)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'table'):QTimer.singleShot(0,self.fit_visible_columns)
    def fit_visible_columns(self):
        # Keep the user's widths and permit horizontal scrolling on narrow screens.
        return
    def delete_invoice(self):
        if self.panel.confirm_invoice_delete(self,self.record):self.delete_requested=True;self.accept()
    def default_status_for_kind(self,*_):
        if not self.record:self.status.setCurrentIndex(self.status.findData('draft' if self.kind.currentData()=='پیش‌فاکتور' else 'issued'));self.refresh_invoice_number()
        self.update_next_button()
    def update_next_button(self,*_):
        financial=self.kind.currentData()!='پیش‌فاکتور' and self.status.currentData() in ('issued','paid')
        self.next_button.setText('ادامه و امور مالی  ←' if financial else 'ادامه و پیش‌نمایش  ←')
        self.next_button.setToolTip('پیش‌فاکتور و پیش‌نویس بدون ثبت دریافت یا پرداخت به پیش‌نمایش می‌روند.' if not financial else 'روش‌های دریافت یا پرداخت در مرحله بعد انتخاب می‌شوند.')
    def refresh_invoice_number(self):
        try:
            from personalization_ui import request_wait
            result=request_wait(self.panel.owner,'invoice/next-number',company=self.panel.company.currentData(),kind=self.kind.currentData());self.number.setText(fa(result['number']))
        except Exception:self.number.setText('—')
    def show_buyer(self,snapshot=None):
        summary=customer_summary(snapshot or self.panel.customer_payload(self.client.currentData()));self.preview.setText(summary);self.preview.setVisible(bool(summary));self.refresh_button.setVisible(bool(summary))
    def refresh_buyer(self,*_):self.refresh_customer=True;self.show_buyer()
    def add_line(self,line=None):
        if sum(not self.is_empty_row(row) for row in range(self.table.rowCount()))>=100:return
        line=line if isinstance(line,dict) else {};i=self.table.rowCount();self.table.blockSignals(True)
        if i and self.is_empty_row(i-1):i-=1
        else:self.table.insertRow(i)
        if line.get('discount_rate') not in (None,'','0',0):self._legacy_percent_lines=True
        for j,(key,default) in enumerate([('description',''),('quantity','1'),('unit','عدد'),('unit_price','0'),('discount','0'),('tax_rate','0'),('total','0'),('product_code',''),('balance',''),('gross_profit',''),('discount_rate','0')]):
            value=line.get('discount_fixed','0') if key=='discount' and line.get('discount_rate') else line.get(key,default);cell=QTableWidgetItem(str(value))
            if j==0 and line.get('product_id'):cell.setData(Qt.UserRole,line['product_id'])
            if j==0 and line.get('unit_cost_snapshot') is not None:cell.setData(Qt.UserRole+1,line.get('unit_cost_snapshot'))
            if j in (0,2,6,7,8,9):cell.setFlags(cell.flags()&~Qt.ItemIsEditable)
            self.table.setItem(i,j,cell)
        self.table.blockSignals(False)
        if hasattr(self,'total'):self.compute()
    def is_empty_row(self,row):
        item=self.table.item(row,0);return bool(item and item.data(Qt.UserRole+2))
    def ensure_empty_row(self):
        if self.table.rowCount() and self.is_empty_row(self.table.rowCount()-1):return
        self.table.blockSignals(True);row=self.table.rowCount();self.table.insertRow(row)
        for col in range(self.table.columnCount()):
            cell=QTableWidgetItem('');cell.setFlags(cell.flags()&~Qt.ItemIsEditable)
            if col==0:cell.setData(Qt.UserRole+2,True);cell.setToolTip('برای جست‌وجوی کالا تایپ یا دوبار کلیک کنید.')
            self.table.setItem(row,col,cell)
        self.table.blockSignals(False)
    def choose_product(self,query=''):
        from personalization_ui import request_wait
        try:
            data=request_wait(self.panel.owner,'inventory',company=self.panel.company.currentData());products=[p for p in data['products'] if p['active']]
            if not products:QMessageBox.information(self,'انتخاب کالا','ابتدا کالا را در بخش کالا و موجودی ثبت کنید.');return
            picker=ProductPicker(self,data,query if isinstance(query,str) else '')
            if picker.exec()!=QDialog.Accepted:return
            for p in picker.selected_products:
                price=p['purchase_price'] if self.kind.currentData() in ('فاکتور خرید','برگشت از خرید') else p['sale_price']
                self.add_line(dict(description=p['name'],unit=p['unit'],unit_price=price,product_id=p['id'],product_code=p['code'],balance=p['balance'],unit_cost_snapshot=p['purchase_price']))
            self.table.setCurrentCell(max(0,self.table.rowCount()-len(picker.selected_products)),1);self.table.setFocus()
        except Exception as exc:QMessageBox.warning(self,'انتخاب کالا',str(exc))
    def remove_line(self):
        i=self.table.currentRow()
        if i>=0 and not self.is_empty_row(i):
            self.table.removeRow(i)
            if not self.table.rowCount():self.ensure_empty_row()
            self.compute()
    def values(self,preview=False):
        lines=[]
        for i in range(self.table.rowCount()):
            if self.is_empty_row(i):continue
            line={key:self.table.item(i,j).text() for j,key in enumerate(['description','quantity','unit','unit_price','discount','tax_rate'])};line['discount_rate']=self.table.item(i,10).text() or '0';product_id=self.table.item(i,0).data(Qt.UserRole)
            if product_id:line['product_id']=product_id
            lines.append(line)
        if preview:
            for line in lines:
                if not line['description'].strip():line['description']='ردیف در حال تکمیل'
        p=copy.deepcopy((self.record or {}).get('payload',{}));p.update(client_id=self.client.currentData(),number=self.number.text() if self.record else '__AUTO__',date=normalize(self.date.text()),due_date=normalize(self.due.text()),document_type=self.kind.currentData(),status=self.status.currentData(),notes=self.notes.text(),lines=lines,refresh_customer=self.refresh_customer,invoice_discount_mode=self.discount_mode.currentData(),invoice_discount_value=normalize(self.discount_value.text() or '0'),additional_charge=normalize(self.additional_charge.text() or '0'),charge_tax_rate=normalize(self.charge_tax_rate.text() or '0'))
        if not self.record and getattr(self,'source_quote_id',None):p.update(source_quote_id=self.source_quote_id,source_quote_number=getattr(self,'source_quote_number',''))
        p['title']=p['document_type']+' '+p['number'];return invoice(p)
    def compute(self,*_):
        if not hasattr(self,'total'):return
        try:
            p=self.values(preview=True);self.table.blockSignals(True)
            from inventory_logic import gross_profit
            for i,line in enumerate(p['lines']):
                self.table.item(i,6).setText(fa(f"{int(line['total']):,}"));cost=self.table.item(i,0).data(Qt.UserRole+1)
                if cost is not None:
                    from decimal import Decimal
                    self.table.item(i,9).setText(fa(f"{int(gross_profit(line['quantity'],line['unit_price'],cost,Decimal(line['discount'])+Decimal(line.get('invoice_discount_share','0')))):,}"))
            self.table.blockSignals(False);t=p['totals'];self.total.setText('قابل پرداخت: '+fa(f"{int(t['total']):,}")+' ریال   ·   مالیات: '+fa(f"{int(t['tax']):,}")+'   ·   تخفیف: '+fa(f"{int(t['discount']):,}"));self.error.setText('')
        except ValueError as exc:self.total.setText('جمع پس از تکمیل ردیف‌ها محاسبه می‌شود.');self.error.setText(str(exc))
    def validate(self):
        try:
            self.payload=self.values()
            if not self.payload.get('client_id'):raise ValueError('مشتری را انتخاب کنید.')
            if not self.record and any(not line.get('product_id') for line in self.payload['lines']):raise ValueError('کالا را از فهرست کالاهای ثبت‌شده انتخاب کنید.')
            if self.payload['document_type'] in ('فاکتور فروش','فاکتور خرید','برگشت از فروش','برگشت از خرید') and self.payload['status'] in ('issued','paid'):
                from settlement_ui import SettlementDialog
                settlement=SettlementDialog(self.panel,self.payload,self.record,parent=self)
                if settlement.exec()!=QDialog.Accepted:return
                self.payload['settlement']=settlement.lines
                from settlement_logic import validate as settlement_summary
                self.payload['settlement_summary']=getattr(settlement,'summary',None) or settlement_summary(self.payload['totals']['total'],settlement.lines)
            elif self.payload.get('settlement'):
                if QMessageBox.question(self,'حذف تسویه','با تغییر وضعیت، تخصیص‌های تسویه از این فاکتور برداشته می‌شود. ادامه می‌دهید؟',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
                self.payload['settlement']=[]
            from invoice_pdf import InvoicePreview
            preview=copy.deepcopy(self.payload);old=(self.record or {}).get('payload',{})
            if not self.record:
                self.refresh_invoice_number();preview['number']=normalize(self.number.text()) if self.number.text()!='—' else 'پس از ثبت'
            preserve=bool(self.record and not self.refresh_customer and old.get('client_id')==self.client.currentData())
            preview['customer_snapshot']=copy.deepcopy(old.get('customer_snapshot',{})) if preserve else buyer_snapshot(self.panel.customer_payload(self.client.currentData()))
            preview['seller_name']=old.get('seller_name',self.panel.company.currentText()) if preserve else self.panel.company.currentText()
            preview['seller_snapshot']=copy.deepcopy(old.get('seller_snapshot',{})) if preserve else {}
            if not preserve:
                from personalization_ui import request_wait
                companies=request_wait(self.panel.owner,'companies')
                seller=next((c for c in companies if c['id']==self.panel.company.currentData()),None)
                if seller:preview['seller_snapshot']={k:seller.get(k,'') for k in ('phone','address','logo')}
            selected_banks=[line['bank_account_id'] for line in self.payload.get('settlement',[]) if line.get('kind')=='bank']
            if selected_banks:
                from personalization_ui import request_wait
                financial=request_wait(self.panel.owner,'finance',company=self.panel.company.currentData());bank=next((b for b in financial['banks'] if b['id']==selected_banks[-1]),None)
                if bank:preview['seller_snapshot'].update(account_no=bank.get('account_no',''),iban=bank.get('iban',''))
            if self.record and preview.get('document_type')!='پیش‌فاکتور' and preview.get('status') not in ('draft','cancelled'):
                from personalization_ui import request_wait
                from invoice_pdf import with_allocated_payments
                from decimal import Decimal
                financial=request_wait(self.panel.owner,'finance',company=self.panel.company.currentData());item=next((r for r in financial.get('invoice_documents',[]) if r['id']==self.record['id']),None)
                if item is None:raise ValueError('اطلاعات مالی فاکتور در دسترس نیست.')
                allocation=Decimal(item.get('allocated_transactions','0'));pending=Decimal(item.get('allocated_pending_checks','0'));summary=preview.get('settlement_summary') or {}
                if allocation+pending and (not summary or Decimal(summary.get('unallocated','0'))<allocation+pending):raise ValueError('ابتدا پرداخت‌های متصل به فاکتور را بررسی کنید.')
                preview=with_allocated_payments(preview,allocation,pending)
            dialog=QDialog(self);dialog.setWindowTitle('پیش‌نمایش و تأیید فاکتور');dialog.resize(1020,700);layout=QVBoxLayout(dialog);view=InvoicePreview(preview,self.panel.owner.data.get('preferences',{}).get('invoice_print'),dialog);layout.addWidget(view,1);actions=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);actions.button(QDialogButtonBox.Ok).setText('تأیید و ثبت فاکتور');actions.button(QDialogButtonBox.Cancel).setText('بازگشت و ویرایش');actions.accepted.connect(dialog.accept);actions.rejected.connect(dialog.reject);layout.addWidget(actions)
            if dialog.exec()!=QDialog.Accepted:return
            self.accept()
        except Exception as exc:
            message=str(exc) or 'خطای نامشخص؛ اطلاعات فاکتور را بررسی کنید.';self.error.setText(message);QMessageBox.warning(self,'ادامه فاکتور ممکن نیست',message)

class CustomersPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.records=[];self.companies=[];self.visible={};v=QVBoxLayout(self);row=QHBoxLayout();title=text('مشتریان');title.setObjectName('Hero');row.addWidget(title);self.company=QComboBox();row.addWidget(self.company);self.search=QLineEdit();self.search.setPlaceholderText('نام، شناسه، شماره اقتصادی یا تلفن…');row.addWidget(self.search,1);row.addWidget(button('تازه‌سازی','refresh',owner.org.sync));v.addLayout(row);self.pages=QTabWidget();v.addWidget(self.pages,1);self.tables={};self.buttons=[]
        self.search.setPlaceholderText('جستجوی شماره سند، فاکتور یا مشتری…');self.invoice_filter=QComboBox();self.invoice_filter.addItem('همه نوع‌های فاکتور','')
        for kind in ('پیش‌فاکتور','فاکتور فروش','فاکتور خرید','برگشت از فروش','برگشت از خرید'):self.invoice_filter.addItem(kind,kind)
        row.addWidget(self.invoice_filter);self.invoice_filter.currentIndexChanged.connect(self.render)
        for kind,title,headers in [('client','مشتریان',['مشتری','شماره مشتری','نوع شخص','شناسه / کد ملی','شماره اقتصادی','تماس','پرونده']),('invoice','فاکتورها',['شماره فاکتور','شماره سند','نوع فاکتور','مشتری','تاریخ','مبلغ؛ ریال','وضعیت'])]:
            page=QWidget();body=QVBoxLayout(page);tools=QHBoxLayout();tools.addWidget(button('افزودن','add',lambda _=False,k=kind:self.new_record(k)));tools.addWidget(button('بازکردن / ویرایش','edit',lambda _=False,k=kind:self.edit_record(k)))
            if kind=='client':
                tools.addWidget(button('فاکتور','calculator',lambda:self.new_record('invoice',self.selected('client'))));tools.addWidget(button('گزارش‌ها','export',self.reports))
            if kind=='invoice':
                self.invoice_delete_button=button('حذف فاکتور','delete',self.delete_selected_invoice);self.invoice_delete_button.setText('حذف فاکتور');tools.addWidget(self.invoice_delete_button)
                tools.addWidget(button('تبدیل پیش‌فاکتور به فروش','add',self.convert_quote))
                tools.addWidget(button('گزارش‌ها','export',self.reports))
            tools.addStretch();body.addLayout(tools);table=QTableWidget(0,len(headers));table.setHorizontalHeaderLabels(headers);table.setSelectionBehavior(QAbstractItemView.SelectRows);table.setSelectionMode(QAbstractItemView.SingleSelection);table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);table.horizontalHeader().setStretchLastSection(True);table.doubleClicked.connect(lambda _=None,k=kind:self.edit_record(k));body.addWidget(table,1);self.tables[kind]=table;self.pages.addTab(page,title)
        from inventory_ui import InventoryPanel
        self.inventory=InventoryPanel(self);self.pages.addTab(self.inventory,'کالا و موجودی')
        from finance_ui import FinancePanel
        self.finance=FinancePanel(self);self.finance_index=self.pages.addTab(self.finance,'امور مالی')
        self.pages.currentChanged.connect(lambda _:self.inventory.reload() if self.pages.currentWidget() is self.inventory else None)
        self.company.currentIndexChanged.connect(lambda _:self.inventory.reload() if self.pages.currentWidget() is self.inventory else None)
        self.pages.currentChanged.connect(lambda _:self.finance.reload() if self.pages.currentWidget() is self.finance else None)
        self.company.currentIndexChanged.connect(lambda _:self.finance.reload() if self.pages.currentWidget() is self.finance else None)
        self.company.currentIndexChanged.connect(self.sync_finance_access)
        self.pages.setCurrentIndex(1)
        self.detail=text('');v.addWidget(self.detail);self.tables['client'].itemSelectionChanged.connect(self.show_detail);self.search.textChanged.connect(self.render);self.company.currentIndexChanged.connect(self.render)
    def can(self,action):
        from permission_policy import allowed
        user=self.owner.session_user
        return not user or allowed(user,self.company.currentData(),'clients',action)
    def sync_finance_access(self,*_):
        from permission_policy import allowed
        actor=self.owner.session_user;company=self.company.currentData();visible=bool(company) and (not actor or allowed(actor,company,'clients','view') and allowed(actor,company,'finance','view'))
        self.pages.setTabVisible(self.finance_index,visible)
        if not visible:
            self.finance.data={'banks':[],'checks':[],'transactions':[]};self.finance.visible_documents=[];self.finance.balance_customers=[];self.finance.check_summary.clear()
            for table in self.finance.tables.values():table.setRowCount(0)
    def showEvent(self,event):super().showEvent(event);self.refresh_data()
    def refresh_data(self,companies=None):
        self.records=list(self.owner.org.records);old=self.company.currentData();values=companies or [dict(id=self.owner.org.company.itemData(i),name=self.owner.org.company.itemText(i)) for i in range(self.owner.org.company.count())];self.company.blockSignals(True);self.company.clear()
        for company in values:self.company.addItem(company['name'],company['id'])
        self.company.setCurrentIndex(max(0,self.company.findData(old)));self.company.blockSignals(False);self.sync_finance_access();self.render()
    def customer_payload(self,id):return next((r['payload'] for r in self.records if r['kind']=='client' and r['id']==id),{})
    def customer_picker(self,selected=None):
        box=QComboBox();box.addItem('انتخاب مشتری','')
        for record in self.records:
            if record['kind']=='client' and record['company_id']==self.company.currentData() and (record['payload'].get('status')!='archived' or record['id']==selected):box.addItem(record['title'],record['id'])
        box.setCurrentIndex(max(0,box.findData(selected)));return box
    def selected(self,kind):
        i=self.tables[kind].currentRow();return self.visible.get(kind,[])[i] if 0<=i<len(self.visible.get(kind,[])) else None
    def render(self,*_):
        query=normalize(self.search.text()).casefold();company=self.company.currentData()
        for kind,table in self.tables.items():
            rows=[r for r in self.records if r['kind']==kind and r['company_id']==company and self.can('view') and (kind!='invoice' or not self.invoice_filter.currentData() or r['payload'].get('document_type')==self.invoice_filter.currentData()) and (not query or query in normalize(json.dumps(r['payload'],ensure_ascii=False)).casefold())];self.visible[kind]=rows[:500];table.setRowCount(min(len(rows),500))
            for i,r in enumerate(rows[:500]):
                p=r['payload'];name=self.customer_payload(p.get('client_id')).get('title',p.get('customer_snapshot',{}).get('title',''))
                if kind=='client':cells=[p['title'],fa(p.get('customer_code','')),p.get('customer_type','نامشخص'),p.get('national_id',''),p.get('economic_code',''),p.get('mobile') or p.get('phone',''),'بایگانی' if p.get('status')=='archived' else 'اطلاعات پایه: '+('نیازمند تکمیل' if missing_fields(p) else 'تکمیل‌شده')]
                elif kind=='tax_job':
                    from org_schema import STATUSES
                    cells=[p['title'],name,p.get('period',''),p.get('due_date',''),STATUSES.get(p.get('status'),'')]
                else:cells=[p.get('number',''),p.get('document_no',''),p.get('document_type',''),p.get('customer_snapshot',{}).get('title',name),p.get('date',''),fa(f"{int(p.get('totals',{}).get('total',0)):,}"),dict(draft='پیش‌نویس',issued='ثبت‌شده',paid='تسویه‌شده',cancelled='لغوشده').get(p.get('status'),'')]
                for j,value in enumerate(cells):table.setItem(i,j,QTableWidgetItem(str(value)))
        self.show_detail()
    def show_detail(self):
        r=self.selected('client')
        if not r:self.detail.setText('اطلاعات مشتری یک‌بار ثبت و در فاکتورها استفاده می‌شود.');return
        missing=missing_fields(r['payload']);self.detail.setText('اطلاعات پایه قابل تکمیل: '+ '، '.join(missing) if missing else customer_summary(r['payload']))
    def new_record(self,kind,selected=None):
        if not self.ready('invoice' if kind=='invoice' else 'create'):return
        dialog=CustomerDialog(self) if kind=='client' else InvoiceDialog(self,selected=selected) if kind=='invoice' else TaxJobDialog(self,selected=selected)
        if dialog.exec()==QDialog.Accepted:
            saved=self.save(kind,dialog.payload)
            if saved and kind=='invoice':self.invoice_output(saved['payload'],saved['id'])
    def convert_quote(self):
        if not self.ready('invoice'):return
        record=self.selected('invoice')
        if not record or record['payload'].get('document_type')!='پیش‌فاکتور':QMessageBox.information(self,'تبدیل پیش‌فاکتور','ابتدا یک پیش‌فاکتور انتخاب کنید.');return
        p=record['payload'];dialog=InvoiceDialog(self,selected={'id':p.get('client_id')});dialog.source_quote_id=record['id'];dialog.source_quote_number=p.get('number','');dialog.client.setEnabled(False);dialog.kind.setCurrentIndex(dialog.kind.findData('فاکتور فروش'));dialog.kind.setEnabled(False);dialog.due.setText(p.get('due_date',''));dialog.notes.setText(p.get('notes',''))
        dialog.discount_mode.setCurrentIndex(max(0,dialog.discount_mode.findData(p.get('invoice_discount_mode','amount'))));dialog.discount_value.setText(str(p.get('invoice_discount_value','0')));dialog.additional_charge.setText(str(p.get('additional_charge','0')));dialog.charge_tax_rate.setText(str(p.get('charge_tax_rate','0')))
        for line in p.get('lines',[]):dialog.add_line(line)
        if dialog.exec()==QDialog.Accepted:
            saved=self.save('invoice',dialog.payload)
            if saved:self.invoice_output(saved['payload'],saved['id'])
    def ready(self,action):
        if not self.owner.org.client and not self.owner.reconnect_company():return False
        if not self.company.currentData():
            QMessageBox.information(self,'انتخاب شرکت','شرکت مربوط را انتخاب کنید. اگر فهرست خالی است، پس از اتصال آن را تازه‌سازی کنید.');return False
        if not self.can(action):QMessageBox.information(self,'دسترسی','مدیر می‌تواند دسترسی این بخش را تنظیم کند.');return False
        return True
    def edit_record(self,kind,record=None):
        record=record or self.selected(kind)
        if not record:return
        if kind=='client':
            editable=self.can('edit') and bool(self.owner.org.client);d=CustomerDialog(self,record,not editable)
            if d.exec()==QDialog.Accepted:
                if d.delete_requested:self.delete_customer(record,confirmed=True)
                else:self.save(kind,d.payload,record)
        else:
            if not self.ready('invoice' if kind=='invoice' else 'edit'):return
            d=InvoiceDialog(self,record) if kind=='invoice' else TaxJobDialog(self,record)
            if d.exec()==QDialog.Accepted:
                if kind=='invoice' and d.delete_requested:self.delete_invoice(record,confirmed=True)
                else:
                    saved=self.save(kind,d.payload,record)
                    if saved and kind=='invoice':self.invoice_output(saved['payload'],saved['id'])
    def confirm_customer_delete(self,parent,record):
        return QMessageBox.question(parent,'حذف مشتری','مشتری «'+record['title']+'» از فهرست حذف شود؟\nفاکتورها حفظ می‌شوند و مشتری تا ۳۰ روز در سطل بازیافت قابل بازیابی است.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes
    def delete_selected_customer(self):
        record=self.selected('client')
        if not record:QMessageBox.information(self,'حذف مشتری','ابتدا یک مشتری را از فهرست انتخاب کنید.');return
        self.delete_customer(record)
    def delete_customer(self,record,confirmed=False):
        if not self.ready('delete') or (not confirmed and not self.confirm_customer_delete(self,record)):return
        self.archive_record(record,'مشتری')
    def confirm_invoice_delete(self,parent,record):
        return QMessageBox.question(parent,'حذف فاکتور','فاکتور «'+record['title']+'» از فهرست حذف شود؟\nتا ۳۰ روز در سطل بازیافت قابل بازیابی است.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes
    def delete_selected_invoice(self):
        record=self.selected('invoice')
        if not record:QMessageBox.information(self,'حذف فاکتور','ابتدا یک فاکتور را از فهرست انتخاب کنید.');return
        self.delete_invoice(record)
    def delete_invoice(self,record,confirmed=False):
        if not self.ready('delete') or (not confirmed and not self.confirm_invoice_delete(self,record)):return
        self.archive_record(record,'فاکتور')
    def archive_record(self,record,kind):
        from personalization_ui import request_wait
        try:
            request_wait(self.owner,'archive',dict(id=record['id'],version=record['version']));self.records=[r for r in self.records if r['id']!=record['id']];self.render();self.owner.org.revision=None;self.owner.org.sync();self.detail.setText(kind+' از فهرست حذف شد؛ بازیابی از سطل بازیافت تا ۳۰ روز امکان‌پذیر است.')
        except Exception as exc:QMessageBox.warning(self,'حذف انجام نشد',str(exc))
    def invoice_output(self,payload,record_id=None):
        from invoice_pdf import set_invoice_document,export,with_allocated_payments,InvoicePreview
        if record_id and payload.get('document_type')!='پیش‌فاکتور' and payload.get('status') not in ('draft','cancelled'):
            try:
                from personalization_ui import request_wait
                data=request_wait(self.owner,'finance',company=self.company.currentData());item=next((r for r in data.get('invoice_documents',[]) if r['id']==record_id),None)
                if item is None:raise ValueError('اطلاعات مالی فاکتور در دسترس نیست.')
                payload=with_allocated_payments(payload,item.get('allocated_transactions','0'),item.get('allocated_pending_checks','0'))
            except Exception as exc:QMessageBox.warning(self,'چاپ فاکتور','برای نمایش مانده دقیق، ابتدا اتصال مالی را بررسی کنید.\n'+str(exc));return
        from PySide6.QtGui import QTextDocument
        from PySide6.QtPrintSupport import QPrinter,QPrintPreviewDialog
        options=self.owner.data.get('preferences',{}).get('invoice_print');dialog=QDialog(self);dialog.setWindowTitle('فاکتور ثبت شد · چاپ یا ذخیره');dialog.resize(1020,700);layout=QVBoxLayout(dialog);view=InvoicePreview(payload,options,dialog);layout.addWidget(view,1);actions=QHBoxLayout();pdf=QPushButton('ذخیره PDF');printer=QPushButton('چاپ');close=QPushButton('بستن');actions.addWidget(pdf);actions.addWidget(printer);actions.addWidget(close);layout.addLayout(actions)
        def save_pdf():
            path,_=QFileDialog.getSaveFileName(dialog,'ذخیره فاکتور','Karname-Invoice.pdf','PDF (*.pdf)')
            if path:
                try:export(path if path.lower().endswith('.pdf') else path+'.pdf',payload,options)
                except Exception as exc:QMessageBox.warning(dialog,'ذخیره PDF',str(exc))
        def print_invoice():
            from PySide6.QtGui import QPageLayout
            device=QPrinter(QPrinter.HighResolution);device.setPageOrientation(QPageLayout.Landscape);preview=QPrintPreviewDialog(device,dialog);doc=QTextDocument();set_invoice_document(doc,payload,options);preview.paintRequested.connect(doc.print_);preview.exec()
        pdf.clicked.connect(save_pdf);printer.clicked.connect(print_invoice);close.clicked.connect(dialog.accept);dialog.exec()
    def save(self,kind,payload,record=None):
        from personalization_ui import request_wait
        try:
            saved=request_wait(self.owner,'records',dict(kind=kind,payload=payload,company=self.company.currentData(),id=record['id'] if record else None,version=record['version'] if record else None));self.owner.org.revision=None;self.owner.org.sync();self.detail.setText('اطلاعات ذخیره شد.');return saved
        except Exception as exc:QMessageBox.warning(self,'ذخیره انجام نشد',str(exc));return None
    def export_customers(self):
        if not self.ready('export'):return
        target,_=QFileDialog.getSaveFileName(self,'خروجی مشتریان','Karname-Customers.xlsx','Excel (*.xlsx)')
        if target:
            from org_reports import spreadsheet
            rows=[{label:r['payload'].get(k,'') for k,(label,_) in FIELDS.items() if k!='assignee_id'} for r in self.visible.get('client',[])];spreadsheet(target if target.endswith('.xlsx') else target+'.xlsx',rows,'مشتریان')
    def reports(self):
        if not self.ready('export'):return
        from report_ui import ReportDialog
        ReportDialog(self).exec()
    def export_invoice(self):
        if not self.ready('export'):return
        record=self.selected('invoice')
        if not record:return
        target,_=QFileDialog.getSaveFileName(self,'فاکتور PDF','Karname-Invoice.pdf','PDF (*.pdf)')
        if target:
            try:
                from invoice_pdf import export
                export(target if target.lower().endswith('.pdf') else target+'.pdf',record['payload']);self.detail.setText('PDF فاکتور آماده شد.')
            except Exception as exc:QMessageBox.warning(self,'PDF',str(exc))
