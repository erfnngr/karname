"""Company-scoped tax workbench. Amounts are comparisons, not tax filings."""
from decimal import Decimal,InvalidOperation
from PySide6.QtCore import Qt,QUrl,QPointF,QRectF,Signal
from PySide6.QtGui import QDesktopServices,QPainter,QPainterPath,QColor,QPen,QFont
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QTabWidget,QLabel,QComboBox,QPushButton,QLineEdit,QTableWidget,QTableWidgetItem,QAbstractItemView,QHeaderView,QMessageBox,QFileDialog,QDialog,QInputDialog,QScrollArea,QSizePolicy)
from storage import fa,normalize,parse_j,today_j,jformat,month_last_day
from org_schema import STATUSES
from permission_policy import allowed as company_allowed
from ui_permissions import allowed

def decimal(value):
    try:
        result=Decimal(normalize(str(value or '0')).replace(',','').replace('٬',''))
        if not result.is_finite() or result<0:raise ValueError()
        return result
    except (InvalidOperation,ValueError):raise ValueError('مبلغ فاکتور معتبر نیست.')

def summarize_invoices(records,company,start,end):
    lower=parse_j(start);upper=parse_j(end)
    if lower>upper:raise ValueError('تاریخ شروع بعد از تاریخ پایان است.')
    result={k:dict(count=0,base=Decimal(0),tax=Decimal(0),total=Decimal(0)) for k in ('sales','sales_return','purchase','purchase_return')}
    names={'فاکتور فروش':'sales','برگشت از فروش':'sales_return','فاکتور خرید':'purchase','برگشت از خرید':'purchase_return'}
    skipped=0
    for record in records:
        if record.get('kind')!='invoice' or record.get('company_id')!=company:continue
        p=record.get('payload',{});kind=names.get(p.get('document_type'))
        if not kind or p.get('status') not in ('issued','paid'):continue
        try:
            day=parse_j(p.get('date',''))
            if not lower<=day<=upper:continue
            totals=p['totals'];subtotal=decimal(totals['subtotal']);discount=decimal(totals['discount']);tax=decimal(totals['tax']);total=decimal(totals['total']);charge=decimal(totals.get('additional_charge',0))
            if discount>subtotal:raise ValueError()
            row=result[kind];row['count']+=1;row['base']+=subtotal-discount+charge;row['tax']+=tax;row['total']+=total
        except (ValueError,KeyError,TypeError):skipped+=1
    result['skipped']=skipped
    return result

class TaxRoadmap(QWidget):
    """Scrollable, responsive roadmap; text stays inside its own card."""
    step_clicked=Signal(int)
    def __init__(self,steps,settings,parent=None):
        super().__init__(parent);self.steps=steps;self.settings=settings;self.done=[False]*len(steps);self.setMinimumWidth(320);self.setMinimumHeight(max(200,len(steps)*172+20));self.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
    def set_progress(self,done):self.done=done;self.update()
    def set_steps(self,steps):self.steps=steps;self.done=[False]*len(steps);self.setMinimumHeight(max(200,len(steps)*172+20));self.updateGeometry();self.update()
    def mouseReleaseEvent(self,event):
        w=self.width();card_w=max(260,min(400,w*.68));point=event.position()
        for i in range(len(self.steps)):
            x=w-card_w-12 if i%2==0 else 12
            if QRectF(x,15+i*172,card_w,145).contains(point):self.step_clicked.emit(i);break
        super().mouseReleaseEvent(event)
    def paintEvent(self,event):
        from appearance import palette_for
        from tax_workflows import WORKFLOWS
        titles={'ارزش افزوده':['بررسی فاکتورها','رفع مغایرت','تکمیل پرونده','اظهار و پرداخت'],'عملکرد':['بررسی اسناد','تکمیل مدارک','اظهارنامه عملکرد'],'حقوق':['کارکرد و حقوق','کنترل مالیات','فهرست و پرداخت'],'اجاره':['بررسی قرارداد','محاسبه و مدارک','اظهار و پرداخت'],'سامانه مؤدیان':['کنترل صورتحساب','کارپوشه مؤدیان','ثبت پیگیری'],'دفاتر':['بررسی اسناد','رفع مغایرت','پیگیری تکلیف'],'بیمه کارکنان':['مشخصات کارگاه','فهرست کارکنان','کنترل دستمزد','تهیه فهرست','ثبت نتیجه','پرداخت حق بیمه']}
        category=next((key for key,value in WORKFLOWS.items() if value==self.steps),'');names=titles.get(category,[])
        c=palette_for(self.settings);dark=self.settings.get('theme')=='dark';p=QPainter(self);p.setRenderHint(QPainter.Antialiasing);p.setLayoutDirection(Qt.RightToLeft);w=self.width();card_w=max(260,min(400,w*.68));margin=12;positions=[]
        for i in range(len(self.steps)):
            x=w-card_w-margin if i%2==0 else margin;positions.append((x,15+i*172))
        p.setPen(QPen(QColor(c['muted']),2,Qt.DashLine));p.setBrush(Qt.NoBrush)
        for i in range(len(positions)-1):
            x,y=positions[i];nx,ny=positions[i+1];path=QPainterPath(QPointF(x+card_w/2,y+135));path.cubicTo(x+card_w/2,y+165,nx+card_w/2,ny-25,nx+card_w/2,ny+12);p.drawPath(path)
        for i,(x,y) in enumerate(positions):
            complete=self.done[i];current=i==sum(self.done);light=['#e0f2ff','#f3eaff','#fff2df','#e3f6f5'];night=['#23485e','#44365e','#58452e','#234f4c'];bg=QColor('#28583f' if dark else '#e3f5e8') if complete else QColor((night if dark else light)[i%4]);bg.setAlpha(235 if dark else 240)
            shadow=QColor('#000000');shadow.setAlpha(24);p.setPen(Qt.NoPen);p.setBrush(shadow);p.drawRoundedRect(QRectF(x+3,y+6,card_w,145),20,20)
            outer=QColor(c['panel']);outer.setAlpha(218);p.setPen(QPen(QColor(c['border']),1));p.setBrush(outer);p.drawRoundedRect(QRectF(x,y,card_w,145),20,20)
            bg.setAlpha(190 if dark else 205);p.setPen(Qt.NoPen);p.setBrush(bg);p.drawRoundedRect(QRectF(x+8,y+30,card_w-16,107),14,14)
            ink=QColor('#9ddbbb' if dark and complete else '#194b32' if complete else c['text']);p.setPen(ink);font=QFont(self.font());font.setBold(True);p.setFont(font)
            p.setPen(QColor('#53b5ff' if dark else '#1674c5'));p.setBrush(QColor('#53b5ff' if dark else '#1674c5'));p.drawEllipse(QPointF(x+card_w/2,y+16),5,5);p.setBrush(Qt.NoBrush)
            p.drawText(QRectF(x+15,y+36,card_w-30,30),Qt.AlignLeft|Qt.AlignVCenter,fa(i+1)+'  ·  '+(names[i] if i<len(names) else 'مرحله'));p.setPen(ink)
            if complete:
                p.setPen(QPen(QColor('#53b5ff' if dark else '#1674c5'),3,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin));p.drawLine(QPointF(x+25,y+51),QPointF(x+31,y+57));p.drawLine(QPointF(x+31,y+57),QPointF(x+42,y+45));p.setPen(ink)
            font.setBold(False);p.setFont(font);p.drawText(QRectF(x+20,y+70,card_w-40,60),Qt.AlignLeft|Qt.AlignTop|Qt.TextWordWrap,self.steps[i])
        p.end()

class TaxCenter(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.visible=[];self.setLayoutDirection(Qt.RightToLeft)
        root=QVBoxLayout(self);root.setContentsMargins(18,12,18,12);head=QHBoxLayout();title=QLabel('مرکز مالیات');title.setObjectName('Hero');head.addWidget(title);head.addStretch();self.company=QComboBox();self.company.setMinimumWidth(150);self.company.currentIndexChanged.connect(self.company_changed);head.addWidget(self.company);root.addLayout(head)
        self.message=QLabel('');self.message.setWordWrap(True);root.addWidget(self.message)
        self.section_menu=QComboBox();self.section_menu.setMinimumWidth(200);self.section_menu.setToolTip('انتخاب بخش مالیات');head.addWidget(self.section_menu)
        self.tabs=QTabWidget();self.tabs.tabBar().hide();root.addWidget(self.tabs,1)
        from tax_workflows import WORKFLOWS
        guide=QWidget();guide_layout=QVBoxLayout(guide);guide_top=QHBoxLayout();self.workflow=QComboBox();self.workflow.addItems(list(WORKFLOWS));guide_top.addWidget(self.workflow,1);self.map_case=QComboBox();guide_top.addWidget(self.map_case,2);guide_layout.addLayout(guide_top)
        self.map_status=QLabel();self.map_status.setWordWrap(True);guide_layout.addWidget(self.map_status)
        scroll=QScrollArea();scroll.setWidgetResizable(True);self.main_roadmap=TaxRoadmap(WORKFLOWS[self.workflow.currentText()],owner.data['settings']);self.main_roadmap.step_clicked.connect(self.open_map_step);scroll.setWidget(self.main_roadmap);guide_layout.addWidget(scroll,1)
        action_row=QHBoxLayout();guide_layout.addLayout(action_row)
        for label,fn in [('ثبت پرونده',self.add_workflow_case),('ادامه مراحل پرونده',self.open_map_case)]:
            button=QPushButton(label);button.clicked.connect(fn);action_row.addWidget(button)
        self.tabs.addTab(guide,'نقشه مراحل');self.workflow.currentIndexChanged.connect(self.render_workflow);self.map_case.currentIndexChanged.connect(self.update_map_progress)
        obligations=QWidget();v=QVBoxLayout(obligations);tools=QHBoxLayout();self.kind=QComboBox();self.kind.addItems(['همه تکالیف','ارزش افزوده','عملکرد','حقوق','اجاره','سامانه مؤدیان','دفاتر','بیمه کارکنان','سایر']);self.kind.currentIndexChanged.connect(self.render);tools.addWidget(self.kind);self.progress_filter=QComboBox();self.progress_filter.addItems(['همه وضعیت‌ها','کامل','ناقص']);self.progress_filter.currentIndexChanged.connect(self.render);tools.addWidget(self.progress_filter);self.search=QLineEdit();self.search.setPlaceholderText('جستجو در عنوان، دوره یا شماره پیگیری');self.search.textChanged.connect(self.render);tools.addWidget(self.search,1)
        v.addLayout(tools);self.case_summary=QLabel();self.case_summary.setWordWrap(True);v.addWidget(self.case_summary);case_actions=QGridLayout()
        for index,(text,fn) in enumerate([('ثبت تکلیف',self.add_case),('مراحل پرونده',self.case_steps),('بیمه‌شدگان ماه',self.insured_people),('ویرایش',self.edit_case),('مدارک و تاریخچه',self.details),('کنترل پرونده',self.review_case),('اکسل',lambda:self.export_cases('xlsx')),('PDF',lambda:self.export_cases('pdf'))]):
            b=QPushButton(text)
            if text=='ثبت تکلیف':b.setProperty('flowPrimary',True)
            b.clicked.connect(fn);case_actions.addWidget(b,index//4,index%4)
        v.addLayout(case_actions);self.cases=QTableWidget(0,8);self.cases.setHorizontalHeaderLabels(['عنوان','نوع','دوره','موعد','وضعیت','پیشرفت مراحل','اظهارشده','پرداخت‌شده']);self.cases.setSelectionBehavior(QAbstractItemView.SelectRows);self.cases.setEditTriggers(QAbstractItemView.NoEditTriggers);self.cases.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.cases.doubleClicked.connect(self.edit_case);v.addWidget(self.cases,1);self.tabs.addTab(obligations,'نمای همه پرونده‌ها')
        comparison=QWidget();v=QVBoxLayout(comparison);dates=QHBoxLayout();today=today_j();self.start=QLineEdit(jformat(today.replace(day=1)));self.end=QLineEdit(jformat(today.replace(day=month_last_day(today.year,today.month))));self.start.setPlaceholderText('از تاریخ شمسی');self.end.setPlaceholderText('تا تاریخ شمسی');dates.addWidget(QLabel('از'));dates.addWidget(self.start);dates.addWidget(QLabel('تا'));dates.addWidget(self.end);period=QComboBox();period.addItem('ماه جاری','month');period.addItem('فصل جاری','quarter');period.addItem('سال جاری','year');period.activated.connect(lambda _:self.set_period(period.currentData()));dates.addWidget(period);calculate=QPushButton('مقایسه');calculate.clicked.connect(self.compare);dates.addWidget(calculate);v.addLayout(dates);self.comparison=QTableWidget(0,5);self.comparison.setHorizontalHeaderLabels(['نوع سند','تعداد','مبلغ پس از تخفیف','مالیات ثبت‌شده','جمع فاکتور']);self.comparison.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.comparison.setEditTriggers(QAbstractItemView.NoEditTriggers);v.addWidget(self.comparison,1)
        manual=QHBoxLayout();manual.addWidget(QLabel('مالیات فروش طبق کارپوشه (ریال)'));self.portal_sales=QLineEdit();self.portal_sales.setPlaceholderText('اختیاری');manual.addWidget(self.portal_sales);manual.addWidget(QLabel('مالیات خرید طبق کارپوشه (ریال)'));self.portal_purchase=QLineEdit();self.portal_purchase.setPlaceholderText('اختیاری');manual.addWidget(self.portal_purchase);v.addLayout(manual)
        self.comparison_note=QLabel('مقایسه صرفاً از فاکتورهای صادرشده یا پرداخت‌شده همین شرکت است؛ پیش‌فاکتور و اسناد لغوشده حذف می‌شوند. مبالغ اعتبار قابل قبول یا بدهی قطعی نیستند.');self.comparison_note.setWordWrap(True);v.addWidget(self.comparison_note);self.tabs.addTab(comparison,'مقایسه فاکتورها')
        access=QWidget();v=QVBoxLayout(access);note=QLabel('برای ارسال اظهارنامه، مشاهده کارپوشه و پرداخت از درگاه رسمی وارد حساب شرکت شوید. اطلاعات ورود در کارنامه دریافت یا ذخیره نمی‌شود.');note.setWordWrap(True);v.addWidget(note)
        for text,url in [('درگاه ملی خدمات مالیاتی','https://my.tax.gov.ir/'),('کارپوشه سامانه مؤدیان','https://tp.tax.gov.ir/'),('خدمات غیرحضوری تأمین اجتماعی','https://es.tamin.ir/'),('اطلاعیه‌های سازمان مالیاتی','https://tax.gov.ir/action/do/show/409')]:
            b=QPushButton(text+'  ↗');b.clicked.connect(lambda checked=False,u=url:QDesktopServices.openUrl(QUrl(u)));v.addWidget(b)
        for text,target in [('محاسبه جرایم و حقوق','calculation'),('فاکتورها و امور مالی','clients'),('خبرهای مالیاتی','news')]:
            b=QPushButton(text+'  ←');b.clicked.connect(lambda checked=False,k=target:self.open_module(k));v.addWidget(b)
        v.addStretch();self.tabs.addTab(access,'سامانه‌ها و ابزارها')
        self.category_tables={}
        for category,steps in WORKFLOWS.items():
            page=QWidget();layout=QVBoxLayout(page);heading=QLabel(category);heading.setObjectName('Hero');layout.addWidget(heading)
            instructions=QLabel('\n'.join(fa(i+1)+' · '+s for i,s in enumerate(steps)));instructions.setWordWrap(True);layout.addWidget(instructions)
            row=QHBoxLayout();layout.addLayout(row)
            for caption,action in [('ثبت پرونده',lambda c=category:self.category_action(c,'create')),('ادامه مراحل',lambda c=category:self.category_action(c,'steps')),('ویرایش',lambda c=category:self.category_action(c,'edit')),('مدارک',lambda c=category:self.category_action(c,'details'))]:
                b=QPushButton(caption);b.clicked.connect(lambda checked=False,f=action:f());row.addWidget(b)
            if category=='بیمه کارکنان':
                b=QPushButton('بیمه‌شدگان ماه');b.clicked.connect(lambda:self.category_action('بیمه کارکنان','insured'));row.addWidget(b)
            if category=='ارزش افزوده':
                b=QPushButton('مقایسه فاکتورها');b.clicked.connect(lambda:self.tabs.setCurrentIndex(2));row.addWidget(b)
            portal=QPushButton('سامانه رسمی ↗');portal.clicked.connect(lambda checked=False,c=category:QDesktopServices.openUrl(QUrl('https://es.tamin.ir/' if c=='بیمه کارکنان' else 'https://tp.tax.gov.ir/' if c=='سامانه مؤدیان' else 'https://my.tax.gov.ir/')));row.addWidget(portal)
            table=QTableWidget(0,5);table.setHorizontalHeaderLabels(['عنوان','دوره','موعد','وضعیت','پیشرفت مراحل']);table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);table.setSelectionBehavior(QAbstractItemView.SelectRows);table.setEditTriggers(QAbstractItemView.NoEditTriggers);layout.addWidget(table,1);self.category_tables[category]=(table,[]);self.tabs.addTab(page,category)
        for i in range(4):self.section_menu.addItem(self.tabs.tabText(i),i)
        self.section_menu.currentIndexChanged.connect(lambda index:self.tabs.setCurrentIndex(self.section_menu.itemData(index)))
        self.tabs.currentChanged.connect(lambda index:self.section_menu.setCurrentIndex(self.section_menu.findData(index)) if self.section_menu.findData(index)>=0 else None)
        self.tabs.setCurrentIndex(0);self.render_workflow()
    def category_action(self,category,action):
        table,records=self.category_tables[category];row=table.currentRow();record=records[row] if 0<=row<len(records) else None
        self.kind.setCurrentText(category);self.progress_filter.setCurrentIndex(0);self.search.clear();self.render()
        if action=='create':self.add_case();return
        if not record:QMessageBox.information(self,'پرونده','ابتدا یک پرونده را انتخاب کنید.');return
        index=next((i for i,r in enumerate(self.visible) if r['id']==record['id']),-1)
        if index<0:return
        self.cases.setCurrentCell(index,0)
        {'steps':self.case_steps,'edit':self.edit_case,'details':self.details,'insured':self.insured_people}[action]()
    def company_permitted(self,action='view'):
        actor=self.owner.session_user;company=self.company.currentData()
        return bool(company and (actor is None or company_allowed(actor,company,'tax',action)))
    def render_workflow(self,*_):
        from tax_workflows import WORKFLOWS
        self.main_roadmap.set_steps(WORKFLOWS.get(self.workflow.currentText(),()));self.refresh_map_cases()
    def refresh_map_cases(self):
        if not hasattr(self.owner,'org'):return
        old=self.map_case.currentData();self.map_case.blockSignals(True);self.map_case.clear();self.map_case.addItem('انتخاب پرونده برای ثبت پیشرفت',None)
        for r in self.owner.org.records:
            if self.company_permitted() and r.get('company_id')==self.company.currentData() and r.get('kind')=='tax_case' and r['payload'].get('tax_type')==self.workflow.currentText():self.map_case.addItem(r['payload'].get('title','')+' · '+str(r['payload'].get('period','')),r['id'])
        index=self.map_case.findData(old);self.map_case.setCurrentIndex(max(0,index));self.map_case.blockSignals(False);self.update_map_progress()
    def update_map_progress(self,*_):
        from tax_workflows import workflow_progress
        record=next((r for r in self.owner.org.records if r.get('id')==self.map_case.currentData()),None)
        self.main_roadmap.set_progress(workflow_progress(record['payload']) if record else [False]*len(self.main_roadmap.steps));self.map_status.setText(('موعد: '+fa(record['payload'].get('due_date') or 'ثبت نشده')) if record else 'برای ثبت مراحل، یک پرونده انتخاب یا ایجاد کنید.')
    def open_map_case(self):
        self.open_map_step(None)
    def open_map_step(self,step_index):
        record=next((r for r in self.owner.org.records if r.get('id')==self.map_case.currentData()),None)
        if not record:QMessageBox.information(self,'نقشه مراحل','ابتدا پرونده را انتخاب کنید.');return
        self.kind.setCurrentText(self.workflow.currentText());self.progress_filter.setCurrentIndex(0);self.search.clear();self.render();index=next((i for i,r in enumerate(self.visible) if r['id']==record['id']),-1)
        if index>=0:self.cases.setCurrentCell(index,0);self.case_steps(step_index)
    def select_map_case_row(self):
        record=next((r for r in self.owner.org.records if r.get('id')==self.map_case.currentData() and r.get('company_id')==self.company.currentData()),None)
        if not record:return None
        self.kind.setCurrentText(self.workflow.currentText());self.progress_filter.setCurrentIndex(0);self.search.clear();self.render()
        index=next((i for i,r in enumerate(self.visible) if r['id']==record['id']),-1)
        if index>=0:self.cases.setCurrentCell(index,0);return record
        return None
    def set_step_done(self,step_index,done=True):
        if not self.company_permitted('edit') or not getattr(self.owner.org,'client',None):raise ValueError('اتصال به مرکز شرکت و دسترسی ویرایش لازم است.')
        record=next((r for r in self.owner.org.records if r.get('id')==self.map_case.currentData() and r.get('company_id')==self.company.currentData()),None)
        if not record:raise ValueError('ابتدا یک پرونده را برای این بخش انتخاب یا ثبت کنید.')
        from tax_workflows import WORKFLOWS,workflow_progress
        import copy
        from personalization_ui import request_wait
        steps=WORKFLOWS.get(record['payload'].get('tax_type'),())
        if not 0<=step_index<len(steps):raise ValueError('مرحله معتبر نیست.')
        state=copy.deepcopy(record);progress=workflow_progress(state['payload'])
        if done:
            if not all(progress[:step_index]):raise ValueError('ابتدا مراحل قبلی را تکمیل کنید.')
            if progress[step_index]:return True
            progress[step_index]=True
        else:
            for i in range(step_index,len(progress)):progress[i]=False
        payload=copy.deepcopy(state['payload']);payload['workflow_done']=progress
        request_wait(self.owner,'records',dict(kind='tax_case',company=state['company_id'],id=state['id'],version=state['version'],payload=payload))
        self.owner.org.sync();self.render();return True
    def show_workflow_cases(self):
        self.kind.setCurrentText(self.workflow.currentText());self.tabs.setCurrentIndex(1)
    def add_workflow_case(self):
        self.kind.setCurrentText(self.workflow.currentText());self.add_case()
    def set_period(self,period):
        from tax_workflows import period_bounds
        today=today_j();start,end=period_bounds(today.year,today.month,period);self.start.setText(fa(start));self.end.setText(fa(end))
    def sync_companies(self,companies):
        old=self.company.currentData();self.company.blockSignals(True);self.company.clear();actor=self.owner.session_user
        for c in companies:
            if actor is None or company_allowed(actor,c['id'],'tax','view'):self.company.addItem(c['name'],c['id'])
        self.company.setCurrentIndex(max(0,self.company.findData(old)));self.company.blockSignals(False)
        if self.company.currentData()!=old:self.comparison.setRowCount(0)
        self.render()
    def company_changed(self,*_):
        self.comparison.setRowCount(0);self.portal_sales.clear();self.portal_purchase.clear();self.render()
    def render(self,*_):
        from tax_workflows import workflow_progress,WORKFLOWS
        def progress(p):
            done=workflow_progress(p);return (sum(done),len(done))
        org=self.owner.org;company=self.company.currentData();query=normalize(self.search.text()).casefold();kind=self.kind.currentText()
        self.visible=[r for r in org.records if self.company_permitted() and r.get('company_id')==company and r.get('kind')=='tax_case' and (kind=='همه تکالیف' or r['payload'].get('tax_type')==kind) and (not query or query in normalize(' '.join(str(r['payload'].get(k,'')) for k in ('title','period','reference'))).casefold())]
        def is_complete(r):
            done,total=progress(r['payload']);return bool(total and done==total)
        matching=list(self.visible);finished=sum(1 for r in matching if is_complete(r));self.case_summary.setText('پرونده‌های انتخاب‌شده: '+fa(len(matching))+'  ·  مراحل کامل: '+fa(finished)+'  ·  در حال پیگیری: '+fa(len(matching)-finished)+' — وضعیت مراحل، تأیید رسمی ارسال یا پرداخت نیست.')
        if self.progress_filter.currentText()=='کامل':self.visible=[r for r in self.visible if is_complete(r)]
        elif self.progress_filter.currentText()=='ناقص':self.visible=[r for r in self.visible if not is_complete(r)]
        self.cases.setRowCount(len(self.visible))
        for i,r in enumerate(self.visible):
            p=r['payload'];done,total=progress(p)
            for col,value in enumerate([p.get('title',''),p.get('tax_type',''),p.get('period',''),p.get('due_date',''),STATUSES.get(p.get('status'),p.get('status','')),f'{done}/{total}' if total else 'تعریف نشده',p.get('declared_amount',''),p.get('paid_amount','')]):self.cases.setItem(i,col,QTableWidgetItem(fa(value)))
        for category,(table,_) in getattr(self,'category_tables',{}).items():
            records=[r for r in org.records if self.company_permitted() and r.get('company_id')==company and r.get('kind')=='tax_case' and r['payload'].get('tax_type')==category];self.category_tables[category]=(table,records);table.setRowCount(len(records))
            for i,r in enumerate(records):
                p=r['payload'];done,total=progress(p)
                for col,value in enumerate([p.get('title',''),p.get('period',''),p.get('due_date',''),STATUSES.get(p.get('status'),p.get('status','')),f'{done}/{total}']):table.setItem(i,col,QTableWidgetItem(fa(value)))
        if hasattr(self,'main_roadmap'):self.refresh_map_cases()
        self.message.setText('به مرکز شرکت متصل شوید تا پرونده‌ها ثبت و همگام شوند.' if not org.client else 'شرکت را انتخاب کنید؛ موعدها و نرخ‌ها را بر اساس منبع معتبر برای همان دوره وارد کنید.' if company else 'دسترسی مالیاتی برای هیچ شرکتی فعال نیست.')
    def selected(self):
        row=self.cases.currentRow();return self.visible[row] if 0<=row<len(self.visible) else None
    def add_case(self):
        if not self.company_permitted('create') or not self.owner.org.client:QMessageBox.information(self,'مالیات','اتصال مرکز شرکت و دسترسی ثبت لازم است.');return
        from org_ui import RecordDialog
        org=self.owner.org;org.company.setCurrentIndex(org.company.findData(self.company.currentData()));dialog=RecordDialog(org,'tax_case')
        status=dialog.widgets['status'][0];status.setCurrentIndex(status.findData('draft'))
        if self.kind.currentText()!='همه تکالیف':
            widget=dialog.widgets['tax_type'][0];widget.setCurrentText(self.kind.currentText())
        if dialog.exec():org.save_dialog(dialog)
    def edit_case(self,*_):
        r=self.selected()
        if r and self.company_permitted('edit'):self.owner.org.edit(record=r)
    def details(self):
        r=self.selected()
        if r and self.company_permitted():self.owner.org.record_details(r)
    def case_steps(self,step_index=None):
        if isinstance(step_index,bool):step_index=None
        record=self.selected()
        if not record or not self.company_permitted():return
        from tax_workflows import WORKFLOWS,workflow_progress,step_guide
        import copy
        from personalization_ui import request_wait
        state=copy.deepcopy(record);steps=WORKFLOWS.get(state['payload'].get('tax_type'),())
        if not steps:QMessageBox.information(self,'مراحل','برای این نوع، مسیر مرحله‌ای تعریف نشده است.');return
        if step_index is not None and (step_index<0 or step_index>=len(steps) or step_index>sum(workflow_progress(state['payload']))):QMessageBox.information(self,'مرحله بعد','ابتدا مراحل قبلی را تکمیل کنید.');return
        d=QDialog(self);d.setWindowTitle('مراحل · '+state['title']);d.resize(760,720);v=QVBoxLayout(d);progress=QLabel();progress.setObjectName('Hero');v.addWidget(progress)
        scroll=QScrollArea();scroll.setWidgetResizable(True);roadmap=TaxRoadmap(steps,self.owner.data['settings']);scroll.setWidget(roadmap);v.addWidget(scroll,1);scroll.setVisible(step_index is None)
        description=QLabel();description.setWordWrap(True);description.setTextInteractionFlags(Qt.TextSelectableByMouse);description.setMargin(12);v.addWidget(description)
        due=state['payload'].get('due_date');deadline=QLabel('موعد در تقویم: '+fa(due) if due else 'برای نمایش در تقویم، موعد را در ویرایش پرونده وارد کنید.');deadline.setWordWrap(True);v.addWidget(deadline)
        note=QLabel('تأیید مراحل فقط ثبت پیگیری داخلی است و به معنی ارسال یا پرداخت در سامانه رسمی نیست. مهلت و نرخ را از منبع همان دوره بررسی کنید.');note.setWordWrap(True);v.addWidget(note);button=QPushButton('تأیید این مرحله و ادامه');v.addWidget(button)
        back=QPushButton('بازگرداندن آخرین مرحله');v.addWidget(back)
        tools=QHBoxLayout();v.addLayout(tools)
        portal=QPushButton('سامانه رسمی ↗');tools.addWidget(portal)
        portal.clicked.connect(lambda:QDesktopServices.openUrl(QUrl('https://es.tamin.ir/' if state['payload'].get('tax_type')=='بیمه کارکنان' else 'https://my.tax.gov.ir/')))
        compare=QPushButton('مقایسه فاکتورها');tools.addWidget(compare);compare.clicked.connect(lambda:(d.accept(),self.tabs.setCurrentIndex(2)))
        if state['payload'].get('tax_type')=='بیمه کارکنان':
            people=QPushButton('فهرست بیمه‌شدگان');tools.addWidget(people);people.clicked.connect(lambda:(d.accept(),self.insured_people()))
        def show_step():
            done=workflow_progress(state['payload']);next_index=next((i for i,x in enumerate(done) if not x),len(steps));index=step_index if step_index is not None else next_index;progress.setText('مرحله '+fa(min(index+1,len(steps)))+' از '+fa(len(steps)) if index<len(steps) else 'همه مراحل داخلی بررسی شده‌اند');description.setText(steps[index]+'\n\n'+step_guide(state['payload'].get('tax_type'),index) if index<len(steps) else 'برای ثبت رسید و مدارک از «مدارک و تاریخچه» استفاده کنید.');button.setEnabled(index==next_index and index<len(steps) and self.company_permitted('edit') and bool(self.owner.org.client));back.setEnabled(any(done) and self.company_permitted('edit') and bool(self.owner.org.client))
            roadmap.set_progress(done)
        def advance():
            done=workflow_progress(state['payload']);index=next((i for i,x in enumerate(done) if not x),None)
            if index is None:return
            done[index]=True;p=copy.deepcopy(state['payload']);p['workflow_done']=done
            try:
                result=request_wait(self.owner,'records',dict(kind='tax_case',company=state['company_id'],id=state['id'],version=state['version'],payload=p));state.update(result);self.owner.org.sync();show_step()
                if step_index is not None:d.accept()
            except Exception as exc:QMessageBox.warning(d,'ذخیره مرحله',str(exc))
        def undo():
            done=workflow_progress(state['payload']);index=next((i for i in range(len(done)-1,-1,-1) if done[i]),None)
            if index is None:return
            done[index]=False;p=copy.deepcopy(state['payload']);p['workflow_done']=done
            try:
                result=request_wait(self.owner,'records',dict(kind='tax_case',company=state['company_id'],id=state['id'],version=state['version'],payload=p));state.update(result);self.owner.org.sync();show_step()
            except Exception as exc:QMessageBox.warning(d,'ذخیره مرحله',str(exc))
        button.clicked.connect(advance);back.clicked.connect(undo);show_step();d.exec()
    def insured_people(self):
        record=self.selected()
        if not record or not self.company_permitted():return
        if record['payload'].get('tax_type')!='بیمه کارکنان':QMessageBox.information(self,'بیمه‌شدگان','یک پرونده بیمه کارکنان انتخاب کنید.');return
        import copy
        from personalization_ui import request_wait
        p=record['payload'];entries=copy.deepcopy(p.get('insured_entries') or [dict(name=x.strip(),reviewed=False) for x in p.get('insured_names','').splitlines() if x.strip()])
        d=QDialog(self);d.setWindowTitle('بیمه‌شدگان · '+str(p.get('period','')));d.resize(620,430);v=QVBoxLayout(d);note=QLabel('تیک فقط بررسی داخلی این نفر در همین ماه است؛ ارسال فهرست یا پرداخت در تأمین اجتماعی را تأیید نمی‌کند.');note.setWordWrap(True);v.addWidget(note)
        table=QTableWidget(len(entries),2);table.setHorizontalHeaderLabels(['نام و نام خانوادگی','بررسی شد']);table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);v.addWidget(table)
        for i,e in enumerate(entries):
            table.setItem(i,0,QTableWidgetItem(e['name']));check=QTableWidgetItem();check.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);check.setCheckState(Qt.Checked if e['reviewed'] else Qt.Unchecked);table.setItem(i,1,check)
        controls=QHBoxLayout();v.addLayout(controls);add=QPushButton('افزودن نفر');add.clicked.connect(lambda:table.setRowCount(table.rowCount()+1));controls.addWidget(add)
        def choose_employee():
            records=[r for r in self.owner.org.records if r.get('kind')=='employee' and r.get('company_id')==record['company_id']]
            labels=[str(r['payload'].get('title',''))+' · '+str(r['payload'].get('employee_code','')) for r in records]
            if not labels:QMessageBox.information(d,'کارکنان','پرونده کارکنان قابل دسترسی برای این شرکت یافت نشد؛ نام را دستی وارد کنید.');return
            name,ok=QInputDialog.getItem(d,'انتخاب کارمند','کارمند قابل دسترسی:',labels,0,False)
            if ok and name:
                row=table.rowCount();table.insertRow(row);table.setItem(row,0,QTableWidgetItem(name))
        choose=QPushButton('انتخاب از کارکنان');choose.clicked.connect(choose_employee);controls.addWidget(choose)
        remove=QPushButton('حذف ردیف');remove.clicked.connect(lambda:table.removeRow(table.currentRow()) if table.currentRow()>=0 else None);controls.addWidget(remove)
        save=QPushButton('ذخیره فهرست ماه');save.setEnabled(self.company_permitted('edit') and bool(self.owner.org.client));v.addWidget(save)
        def persist():
            rows=[]
            for i in range(table.rowCount()):
                cell=table.item(i,0);name=cell.text().strip() if cell else ''
                if not name:continue
                check=table.item(i,1);rows.append(dict(name=name,reviewed=bool(check and check.checkState()==Qt.Checked)))
            payload=copy.deepcopy(p);payload['insured_entries']=rows
            try:request_wait(self.owner,'records',dict(kind='tax_case',company=record['company_id'],id=record['id'],version=record['version'],payload=payload));self.owner.org.sync();d.accept()
            except Exception as exc:QMessageBox.warning(d,'ذخیره',str(exc))
        def insert_check(row):
            if not table.item(row,1):
                check=QTableWidgetItem();check.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);check.setCheckState(Qt.Unchecked);table.setItem(row,1,check)
        table.cellChanged.connect(lambda row,col:insert_check(row) if col==0 else None);save.clicked.connect(persist);d.exec()
    def review_case(self):
        r=self.selected()
        if not r or not self.company_permitted():return
        from tax_workflows import case_review
        findings=case_review(r.get('payload',{}))
        text='\n'.join('• '+x for x in findings) if findings else 'موارد پایه بررسی‌شده ثبت شده‌اند.'
        QMessageBox.information(self,'کنترل پرونده',text+'\n\nاین کنترل فقط اطلاعات ثبت‌شده را بررسی می‌کند و تأیید قانونی یا ارسال اظهارنامه نیست.')
    def compare(self):
        actor=self.owner.session_user
        if not self.company_permitted() or (actor is not None and not company_allowed(actor,self.company.currentData(),'clients','view')):QMessageBox.information(self,'دسترسی','دسترسی مالیات و فاکتورها برای همین شرکت لازم است.');return
        try:
            totals=summarize_invoices(self.owner.org.records,self.company.currentData(),self.start.text(),self.end.text());self.comparison.setRowCount(4)
            for i,(key,title) in enumerate([('sales','فروش'),('sales_return','برگشت از فروش'),('purchase','خرید'),('purchase_return','برگشت از خرید')]):
                row=totals[key]
                for col,value in enumerate([title,row['count'],row['base'],row['tax'],row['total']]):self.comparison.setItem(i,col,QTableWidgetItem(fa(str(value))))
            sales=totals['sales']['tax']-totals['sales_return']['tax'];purchase=totals['purchase']['tax']-totals['purchase_return']['tax'];message='خالص مالیات ثبت‌شده فروش: '+fa(sales)+' ؛ خرید: '+fa(purchase)+' ریال.'
            if self.portal_sales.text().strip():message+=' اختلاف فروش با کارپوشه: '+fa(sales-decimal(self.portal_sales.text()))+' ریال.'
            if self.portal_purchase.text().strip():message+=' اختلاف خرید با کارپوشه: '+fa(purchase-decimal(self.portal_purchase.text()))+' ریال.'
            self.comparison_note.setText(message+' این اعداد اعتبار یا بدهی قطعی نیستند. اسناد نامعتبر کنارگذاشته‌شده: '+fa(totals['skipped']))
        except ValueError as exc:QMessageBox.warning(self,'مقایسه',str(exc))
    def export_cases(self,format='xlsx'):
        if not self.company_permitted('export') or not self.visible:return
        ext='.xlsx' if format=='xlsx' else '.pdf';path,_=QFileDialog.getSaveFileName(self,'ذخیره گزارش','Tax-Report'+ext,'Excel (*.xlsx)' if format=='xlsx' else 'PDF (*.pdf)')
        if not path:return
        if not path.lower().endswith(ext):path+=ext
        from org_reports import spreadsheet,pdf_report
        rows=[{'عنوان':r['payload'].get('title',''),'نوع':r['payload'].get('tax_type',''),'دوره':r['payload'].get('period',''),'موعد':r['payload'].get('due_date',''),'وضعیت':STATUSES.get(r['payload'].get('status'),''),'مسئول':r['payload'].get('responsible',''),'تاریخ ارسال':r['payload'].get('submitted_date',''),'تاریخ پرداخت':r['payload'].get('payment_date',''),'اظهارشده ریال':r['payload'].get('declared_amount',''),'پرداخت‌شده ریال':r['payload'].get('paid_amount',''),'پیگیری':r['payload'].get('reference',''),'منبع':r['payload'].get('source','')} for r in self.visible]
        try:(spreadsheet if format=='xlsx' else pdf_report)(path,rows,'پرونده‌های مالیاتی');QMessageBox.information(self,'گزارش','گزارش ذخیره شد.')
        except Exception as exc:QMessageBox.warning(self,'گزارش',str(exc))
    def open_module(self,key):
        if allowed(self.owner,key):self.owner.tabs.setCurrentWidget(self.owner.modules[key])
        else:QMessageBox.information(self,'دسترسی','دسترسی این بخش فعال نیست.')
