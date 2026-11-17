"""Action-oriented views and shared details without replacing existing workflows."""
import copy,json,threading
from datetime import date,datetime,timezone
from PySide6.QtCore import Qt,QObject,Signal,QTimer,QMimeData
from PySide6.QtGui import QKeySequence,QShortcut,QDrag,QColor
from PySide6.QtWidgets import (QWidget,QFrame,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QComboBox,QTabWidget,QTableWidget,QTableWidgetItem,QAbstractItemView,QHeaderView,QListWidget,QListWidgetItem,QDialog,QDialogButtonBox,QFormLayout,QPlainTextEdit,QCheckBox,QSpinBox,QDoubleSpinBox,QMessageBox,QScrollArea,QSplitter,QInputDialog)
from storage import fa,today_j,jformat,parse_j,normalize
from org_schema import STATUSES,SCHEMAS
from workspace_store import REQUEST_TYPES
from ui_icons import iconize

class Signals(QObject):done=Signal(object,object,object)

def button(title,fn,key=None):
    b=QPushButton(title);b.setToolTip(title);b.setAccessibleName(title);b.clicked.connect(fn)
    if key:iconize(b,key,title)
    return b

def label(value='',hero=False):
    w=QLabel(str(value));w.setTextFormat(Qt.PlainText);w.setWordWrap(True)
    if hero:w.setObjectName('Hero')
    return w

def table(headers):
    w=QTableWidget(0,len(headers));w.setHorizontalHeaderLabels(headers);w.setSelectionBehavior(QAbstractItemView.SelectRows);w.setSelectionMode(QAbstractItemView.SingleSelection);w.setEditTriggers(QAbstractItemView.NoEditTriggers);w.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents);w.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);w.verticalHeader().hide();w.verticalHeader().setDefaultSectionSize(42);w.setShowGrid(False);w.setAlternatingRowColors(True);return w

def fill(w,rows):
    w.setRowCount(len(rows))
    for i,row in enumerate(rows):
        for j,value in enumerate(row):w.setItem(i,j,QTableWidgetItem(str(value)))
    # Keep the title column stretched; the other columns resize automatically.

class RequestDialog(QDialog):
    def __init__(self,parent,companies,item=None):
        super().__init__(parent);self.setWindowTitle('درخواست اداری');self.resize(510,480);self.setLayoutDirection(Qt.RightToLeft);v=QVBoxLayout(self);f=QFormLayout();v.addLayout(f);self.company=QComboBox()
        for co in companies:self.company.addItem(co['name'],co['id'])
        self.kind=QComboBox()
        for k,name in REQUEST_TYPES.items():self.kind.addItem(name,k)
        self.title=QLineEdit();self.start=QLineEdit(normalize(jformat(today_j())));self.end=QLineEdit();self.amount=QLineEdit('0');self.hours=QLineEdit('0');self.notes=QPlainTextEdit();self.notes.setMaximumHeight(130)
        for title,w in [('شرکت',self.company),('نوع',self.kind),('موضوع',self.title),('از تاریخ شمسی',self.start),('تا تاریخ؛ اختیاری',self.end),('مبلغ؛ ریال',self.amount),('ساعت',self.hours),('توضیحات',self.notes)]:
            if w in (self.start,self.end):
                row=QHBoxLayout();row.addWidget(w);pick=QPushButton();iconize(pick,'calendar','انتخاب تاریخ');pick.clicked.connect(lambda checked=False,field=w:self.pick_date(field));row.addWidget(pick);f.addRow(title,row)
            else:f.addRow(title,w)
        self.item=item
        if item:
            self.company.setCurrentIndex(max(0,self.company.findData(item['company_id'])));self.company.setEnabled(False);self.kind.setCurrentIndex(self.kind.findData(item['kind']));self.kind.setEnabled(False);p=item['payload'];self.title.setText(p['title']);self.start.setText(p['start_date']);self.end.setText(p['end_date']);self.amount.setText(p['amount']);self.hours.setText(p['hours']);self.notes.setPlainText(p['notes'])
        self.error=label();v.addWidget(self.error);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.button(QDialogButtonBox.Save).setText('ثبت درخواست');b.button(QDialogButtonBox.Cancel).setText('انصراف');b.accepted.connect(self.validate);b.rejected.connect(self.reject);v.addWidget(b)
    def pick_date(self,field):
        from report_ui import JalaliDatePicker
        picker=JalaliDatePicker(field.text(),self)
        if picker.exec()==QDialog.Accepted:field.setText(picker.value())
    def validate(self):
        try:
            from workspace_store import decimal
            if not self.title.text().strip():raise ValueError('موضوع درخواست را بنویسید.')
            for w in (self.start,self.end):
                if w.text().strip():parse_j(w.text())
            decimal(self.amount.text());decimal(self.hours.text(),744);self.payload=dict(company=self.company.currentData(),kind=self.kind.currentData(),payload=dict(title=self.title.text(),start_date=self.start.text(),end_date=self.end.text(),amount=self.amount.text(),hours=self.hours.text(),notes=self.notes.toPlainText()))
            if self.item:self.payload.update(id=self.item['id'],version=self.item['version'])
            self.accept()
        except Exception as e:self.error.setText(str(e))

class DetailDrawer(QFrame):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.setObjectName('Panel');self.setMinimumWidth(285);self.setMaximumWidth(410);v=QVBoxLayout(self);top=QHBoxLayout();self.title=label('',True);top.addWidget(self.title,1);top.addWidget(button('بستن جزئیات',self.hide,'close'));v.addLayout(top);self.body=QPlainTextEdit();self.body.setReadOnly(True);v.addWidget(self.body,1);self.actions=QHBoxLayout();v.addLayout(self.actions);self.hide()
    def show_item(self,title,text,actions=()):
        self.title.setText(title);self.body.setPlainText(text)
        while self.actions.count():
            w=self.actions.takeAt(0).widget()
            if w:w.deleteLater()
        for title,fn,key in actions:self.actions.addWidget(button(title,fn,key))
        self.show()
    def record(self,r):
        if r.get('local_event'):
            self.show_event(r['local_event']);self.actions.addWidget(button('علاقه‌مندی',lambda:self.owner.workspace.favorite_event(r['local_event']),'save'));return
        p=r['payload'];fields={f['key']:f['label'] for f in SCHEMAS.get(r['kind'],{}).get('fields',[])};fields.update(title='عنوان',due_date='موعد',status='وضعیت',notes='توضیحات',estimate_hours='برآورد ساعت',reference='مرجع',deadline_source='منبع موعد',source_message='پیام مرتبط');parts=[]
        names={u['id']:u['fullname'] for u in self.owner.org.people}
        for k,value in p.items():
            if value in ('',None,[],{}):continue
            if k in ('assignee_id','reviewer_id','substitute_id'):value=names.get(value,'عضو پیشین');key={'assignee_id':'مسئول','reviewer_id':'تأییدکننده','substitute_id':'جانشین'}[k]
            else:key=fields.get(k)
            if not key:continue
            if k=='status':value=STATUSES.get(value,value)
            parts.append(key+'\n'+str(value))
        self.show_item(r['title'],'\n\n'.join(parts),[('ویرایش',lambda:self.owner.org.edit(record=r),'edit'),('مدارک و تاریخچه',lambda:self.owner.org.record_details(r),'attachment'),('علاقه‌مندی',lambda:self.owner.workspace.mutate('workspace/save',dict(kind='record',target=r['id'])),'save')])
    def show_event(self,e):
        self.show_item(e['title'],e.get('date_jalali','')+'\n'+e.get('company','')+'\n\n'+e.get('notes',''),[('ویرایش',lambda:self.owner.edit_event(e),'edit')])

class BoardColumn(QListWidget):
    def __init__(self,panel,status):
        super().__init__();self.setObjectName('TaskBoard');self.panel=panel;self.status=status;self.setDragEnabled(True);self.setAcceptDrops(True);self.setDefaultDropAction(Qt.MoveAction);self.setSpacing(6);self.setMinimumWidth(150);self.itemClicked.connect(lambda item:panel.owner.drawer.record(item.data(Qt.UserRole)))
    def startDrag(self,actions):
        item=self.currentItem()
        if item:
            mime=QMimeData();mime.setData('application/x-karname-task',item.data(Qt.UserRole)['id'].encode());drag=QDrag(self);drag.setMimeData(mime);drag.exec(Qt.MoveAction)
    def dragEnterEvent(self,e):
        if e.mimeData().hasFormat('application/x-karname-task'):e.acceptProposedAction()
    def dragMoveEvent(self,e):self.dragEnterEvent(e)
    def dropEvent(self,e):
        if e.mimeData().hasFormat('application/x-karname-task'):self.panel.move_task(bytes(e.mimeData().data('application/x-karname-task')).decode(),self.status);e.acceptProposedAction()

class WorkspacePanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.busy=False;self.signals=Signals();self.signals.done.connect(self.finished);self.snapshot={};self.companies=[];self._notifications=set();self._revision=-1;self._loading=False;self._page=0;v=QVBoxLayout(self);v.setContentsMargins(16,12,16,12);top=QHBoxLayout();top.addWidget(label('کارها و پیگیری‌ها',True));self.state=label();top.addWidget(self.state,1);v.addLayout(top);tools=QHBoxLayout();self.company=QComboBox();self.company.addItem('همه شرکت‌ها','');self.company.currentIndexChanged.connect(self.render);tools.addWidget(self.company);self.query=QLineEdit();self.query.setPlaceholderText('عنوان کار یا پرونده');self.query.setClearButtonEnabled(True);self.query.textChanged.connect(self.render);tools.addWidget(self.query,1);self.view=QComboBox();self.view.addItem('امروز',{'status':'today'});self.view.currentIndexChanged.connect(self.render);tools.addWidget(self.view);v.addLayout(tools)
        self.paging=QWidget();paging=QHBoxLayout(self.paging);paging.setContentsMargins(0,0,0,0);paging.addWidget(button('صفحه قبل',lambda:self.change_page(-1)));self.page_count=label();paging.addWidget(self.page_count,1);paging.addWidget(button('صفحه بعد',lambda:self.change_page(1)));v.addWidget(self.paging)
        self.pages=QTabWidget();v.addWidget(self.pages,1)
        self.today_table=table(['عنوان','شرکت','موعد','وضعیت']);self.today_table.itemSelectionChanged.connect(self.select_today);self.pages.addTab(self.today_table,'امروز و پیگیری')
        board=QWidget();row=QHBoxLayout(board);self.columns={}
        for status,title in [('draft','شروع‌نشده'),('in_progress','در حال انجام'),('review','منتظر تأیید'),('completed','تمام‌شده')]:
            pane=QFrame();pane.setObjectName('BoardColumnPanel');col=QVBoxLayout(pane);col.setContentsMargins(6,4,6,6);heading=label(title);heading.setObjectName('BoardColumnTitle');col.addWidget(heading);items=BoardColumn(self,status);self.columns[status]=items;col.addWidget(items);row.addWidget(pane)
        self.pages.addTab(board,'نمای ستونی')
        self.requests=QWidget();rv=QVBoxLayout(self.requests);bar=QHBoxLayout();bar.addWidget(button('درخواست تازه',self.new_request,'add'));bar.addWidget(button('ویرایش درخواست',self.edit_request,'edit'));bar.addWidget(button('تأیید',lambda:self.review_request('approved'),'save'));bar.addWidget(button('رد',lambda:self.review_request('rejected'),'delete'));bar.addWidget(button('لغو درخواست',lambda:self.review_request('cancelled'),'delete'));bar.addWidget(button('مسیر تأیید',self.routes,'settings'));rv.addLayout(bar);self.request_table=table(['موضوع','نوع','درخواست‌کننده','وضعیت','مرحله']);self.request_table.itemSelectionChanged.connect(self.select_request);rv.addWidget(self.request_table,1);self.pages.addTab(self.requests,'درخواست‌های اداری')
        team=QWidget();tv=QVBoxLayout(team);tr=QHBoxLayout();self.month=QLineEdit(normalize(jformat(today_j()))[:7]);self.month.setMaximumWidth(110);tr.addWidget(label('ماه شمسی'));tr.addWidget(self.month)
        for title,fn in [('ظرفیت کارکنان',self.workload),('بررسی تردد',self.attendance),('مانده مرخصی',self.balance),('قواعد مرخصی / ظرفیت',self.policy)]:tr.addWidget(button(title,fn))
        tv.addLayout(tr);self.team_table=table(['نام','اطلاعات']);tv.addWidget(self.team_table,1);self.pages.addTab(team,'کارکنان')
        self.favorite_table=table(['عنوان','موعد','وضعیت']);self.favorite_table.itemSelectionChanged.connect(self.select_favorite);self.pages.addTab(self.favorite_table,'علاقه‌مندی‌ها')
        recycle=QDialog(owner);recycle.setWindowTitle('سطل بازیافت');recycle.resize(750,500);self.recycle=recycle;rr=QVBoxLayout(recycle);rr.addWidget(label('برای انتخاب، روی هر ردیف یا مربع کنار آن کلیک کنید.'));trash_actions=QHBoxLayout();self.trash_mode=QComboBox();self.trash_mode.addItem('انتخاب برای بازیابی','restore');self.trash_mode.addItem('انتخاب برای پاک کردن','purge');self.trash_mode.currentIndexChanged.connect(self.color_trash);trash_actions.addWidget(self.trash_mode);trash_actions.addWidget(button('اجرای موارد انتخاب‌شده',self.apply_trash));trash_actions.addStretch();rr.addLayout(trash_actions);self.trash_table=table(['انتخاب','عنوان','بخش','تاریخ حذف']);self.trash_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeToContents);self.trash_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch);self.trash_table.itemChanged.connect(self.color_trash);self.trash_table.cellClicked.connect(self.select_trash_row);rr.addWidget(self.trash_table,1);self.trash_status=label();rr.addWidget(self.trash_status)
        from local_assistant import AssistantPanel
        self.assistant=AssistantPanel(owner);self.pages.addTab(self.assistant,'دستیار')
        self.trash=[];self.include_local();self.render();self.owner.home.refresh_activity(self.snapshot)
        self.timer=QTimer(self);self.timer.setInterval(15000);self.timer.timeout.connect(self.refresh);self.timer.start();QTimer.singleShot(1200,self.refresh);self.pages.currentChanged.connect(lambda _:self.render())
    def client(self):return getattr(self.owner.org,'client',None)
    def run(self,fn,callback):
        original=self.client()
        if self.busy or not original:return False
        from org_client import Client
        self.busy=True;self.state.setText('در حال دریافت…');client=Client(original.url,original.session.verify if isinstance(original.session.verify,str) else None,getattr(original,'fingerprint',None));client.token=original.token;client.user=original.user
        def work():
            try:self.signals.done.emit(fn(client),None,callback)
            except Exception as e:self.signals.done.emit(None,e,callback)
            finally:client.session.close()
        threading.Thread(target=work,daemon=True).start();return True
    def finished(self,value,error,callback):
        self.busy=False
        if error:
            self.state.setText(str(error))
            if getattr(error,'status',None)==401:QTimer.singleShot(0,self.owner.lock_session)
            return
        self.state.setText('بروزرسانی '+datetime.now().strftime('%H:%M'));callback(value)
    def mutate(self,path,payload,done=None):
        def ready(v):
            self.owner.data['company_write_at']=datetime.now(timezone.utc).isoformat();self.owner.persist();self.owner.org.revision=None
            if done:done(v)
            self.refresh()
        return self.run(lambda c:c.request(path,payload),ready)
    def refresh(self):
        if self.owner._locking or self.owner._exit_pending or self.owner._exit_approved:return
        def fetch(c):return dict(snapshot=c.request('workspace/today'),companies=c.request('companies'),trash=c.request('workspace/trash'))
        self.run(fetch,self.received)
    def received(self,v):
        self.snapshot=v['snapshot'];self.companies=v['companies'];self.trash=v['trash'];self.include_local();old=self.company.currentData();self.company.blockSignals(True);self.company.clear();self.company.addItem('همه شرکت‌ها','')
        for co in self.companies:self.company.addItem(co['name'],co['id'])
        self.company.setCurrentIndex(max(0,self.company.findData(old)));self.company.blockSignals(False);old=self.view.currentText();self.view.blockSignals(True);self.view.clear()
        for name,p in [('همه کارها',{}),('کارهای من',{'assignee':'me'}),('امروز',{'status':'today'}),('معوق',{'status':'overdue'}),('منتظر تأیید من',{'status':'review_me'})]:self.view.addItem(name,p)
        for x in self.snapshot.get('views',[]):self.view.addItem(x['name'],dict(x['payload'],view_id=x['id']))
        self.view.setCurrentIndex(max(0,self.view.findText(old)));self.view.blockSignals(False);self.render()
        self.owner.home.refresh_activity(self.snapshot)
        for n in self.snapshot.get('notifications',[]):
            if n.get('shown') or n['id'] in self._notifications:continue
            self._notifications.add(n['id']);self.owner.popup(n['body'],title=n['title'],company=next((co['name'] for co in self.companies if co['id']==n['company_id']),None),on_click=lambda item=n:self.open_notice(item),on_shown=lambda item=n:self.mark_notice(item,'shown'))
    def include_local(self):
        from datetime import timedelta
        from workspace_store import now
        user=(self.owner.session_user or {}).get('id','');names={co['name']:co['id'] for co in self.companies};today=date.today()
        from ui_permissions import allowed
        for e in self.owner.events if allowed(self.owner,'calendar') else []:
            due=self.owner.event_reference_date(e)
            if not due:continue
            from storage import due_on
            p=dict(title=e['title'],due_date=normalize(jformat(__import__('jdatetime').date.fromgregorian(date=due))),notes=e.get('notes',''),category=e.get('category','سایر'),status='completed' if e.get('done') else e.get('progress_status','draft'))
            self.snapshot.setdefault('tasks',[]).append(dict(id='local-'+e['id'],kind='task',company_id=names.get(e.get('company')),owner_id=user,private=True,department='',payload=p,title=e['title'],version=1,mine=True,review=False,overdue=due<today and not e.get('done'),due_today=due==today,saved=e['id'] in self.owner.data.get('favorite_events',[]),local_event=e))
        for x in self.owner.data.get('event_trash',[]):
            try:
                datetime.fromisoformat(x['deleted_at']);self.trash.append(dict(id=x['event']['id'],title=x['event']['title'],trash_kind='event',updated=x['deleted_at'],version=1))
            except (ValueError,KeyError):pass

    def mark_notice(self,n,action):
        original=self.client()
        if not original:return
        from org_client import Client
        def work():
            c=Client(original.url,original.session.verify if isinstance(original.session.verify,str) else None,getattr(original,'fingerprint',None));c.token=original.token
            try:c.request('workspace/notifications',dict(id=n['id'],action=action))
            except Exception:self._notifications.discard(n['id'])
            finally:c.session.close()
        threading.Thread(target=work,daemon=True).start()
    def open_notice(self,n):
        self.owner.show_main()
        def opened(target):
            self.mark_notice(n,'opened')
            if target['kind']=='message':self.owner.chat.open_notification(target)
            elif target['kind']=='record':self.owner.tabs.setCurrentWidget(self);self.owner.drawer.record(target['record'])
            elif target['kind']=='request':
                r=target['request'];self.owner.tabs.setCurrentWidget(self);self.pages.setCurrentWidget(self.requests);self.owner.drawer.show_item(r['payload']['title'],REQUEST_TYPES.get(r['kind'],'درخواست')+'\n'+r['payload'].get('notes','')+'\n'+r['status']);self.refresh()
        if not self.run(lambda c:c.request('workspace/target',id=n['id']),opened):QTimer.singleShot(400,lambda:self.open_notice(n))
    def filtered(self):
        view=self.view.currentData() or {};q=(self.query.text() or view.get('q','')).strip();co=self.company.currentData() or view.get('company');status=view.get('status');assignee=view.get('assignee');result=[]
        from workspace_store import clean
        for t in self.snapshot.get('tasks',[]):
            p=t['payload']
            if co and t['company_id']!=co:continue
            if q and clean(q) not in clean(t['title']+' '+p.get('notes','')):continue
            if view.get('category') and p.get('category')!=view['category']:continue
            if assignee and not (t['mine'] if assignee=='me' else p.get('assignee_id')==assignee):continue
            if status and not (t.get('due_today') if status=='today' else t.get('overdue') if status=='overdue' else t.get('review') if status=='review_me' else p.get('status')==status):continue
            result.append(t)
        return sorted(result,key=lambda t:(not t['overdue'],t['payload'].get('due_date','')))
    def render(self,*_):
        if not hasattr(self,'trash_table'):return
        self.visible_tasks=self.filtered();companies={c['id']:c['name'] for c in self.companies};self._page=max(0,min(self._page,max(0,(len(self.visible_tasks)-1)//50)));start=self._page*50;self.page_tasks=self.visible_tasks[start:start+50];self.page_count.setText(fa(start+1 if self.page_tasks else 0)+'–'+fa(start+len(self.page_tasks))+' از '+fa(len(self.visible_tasks)));self.paging.setVisible(self.pages.currentIndex()==0)
        if self.pages.currentIndex()==0:fill(self.today_table,[(t['title'],companies.get(t['company_id'],'شخصی'),fa(t['payload'].get('due_date','')),STATUSES.get(t['payload'].get('status'),'شروع‌نشده')) for t in self.page_tasks])
        if self.pages.currentIndex()==1:
            for col in self.columns.values():col.clear()
            for t in self.visible_tasks:
                status=t['payload'].get('status','draft');key='completed' if status=='submitted' else 'review' if status=='rejected' else status;item=QListWidgetItem(t['title']+'\n'+fa(t['payload']['due_date']));item.setData(Qt.UserRole,t);item.setToolTip(t['payload'].get('notes',''));self.columns.get(key,self.columns['draft']).addItem(item)
        co=self.company.currentData();self.visible_requests=[r for r in self.snapshot.get('requests',[]) if not co or r['company_id']==co];fill(self.request_table,[(r['payload']['title'],REQUEST_TYPES[r['kind']],r['person'],{'pending':'منتظر بررسی','approved':'تأییدشده','rejected':'ردشده','cancelled':'لغوشده'}[r['status']],fa(r['stage']+1)+' / '+fa(len(r['route']) or 1)) for r in self.visible_requests]);self.favorites=[t for t in self.snapshot.get('tasks',[]) if t.get('saved')];fill(self.favorite_table,[(t['title'],fa(t['payload']['due_date']),STATUSES.get(t['payload'].get('status'),'')) for t in self.favorites]);self.render_trash()
    def render_trash(self):
        selected={self.trash_table.item(i,0).data(Qt.UserRole) for i in range(self.trash_table.rowCount()) if self.trash_table.item(i,0) and self.trash_table.item(i,0).checkState()==Qt.Checked};self.trash_table.blockSignals(True);self.trash_table.setRowCount(len(self.trash))
        for i,r in enumerate(self.trash):
            key=str(r.get('company_id') or '')+'|'+r['trash_kind']+'|'+r['id'];check=QTableWidgetItem('');check.setFlags(check.flags()|Qt.ItemIsUserCheckable);check.setData(Qt.UserRole,key);check.setCheckState(Qt.Checked if key in selected else Qt.Unchecked);self.trash_table.setItem(i,0,check)
            for j,value in enumerate((r['title'],'یادداشت' if r['trash_kind']=='note' else 'یادآور' if r['trash_kind']=='event' else 'کالا' if r['trash_kind']=='product' else 'پیام' if r['trash_kind']=='message' else 'گروه' if r['trash_kind']=='group' else 'پرونده',r['updated'][:10]),1):self.trash_table.setItem(i,j,QTableWidgetItem(str(value)))
        self.trash_table.blockSignals(False);self.color_trash()
    def select_trash_row(self,row,column):
        if column==0:return
        item=self.trash_table.item(row,0)
        if item:item.setCheckState(Qt.Unchecked if item.checkState()==Qt.Checked else Qt.Checked)
    def refresh_local_trash(self):
        self.trash=[r for r in self.trash if r.get('trash_kind')!='event']
        for item in self.owner.data.get('event_trash',[]):
            try:
                datetime.fromisoformat(item['deleted_at']);event=item['event'];self.trash.append(dict(id=event['id'],title=event['title'],trash_kind='event',updated=item['deleted_at'],version=1))
            except (ValueError,KeyError):pass
        self.render_trash()
    def color_trash(self,*_):
        if not hasattr(self,'trash_table'):return
        self.trash_table.blockSignals(True)
        for row in range(self.trash_table.rowCount()):
            selected=self.trash_table.item(row,0).checkState()==Qt.Checked;color=QColor('#fbe3e7' if self.trash_mode.currentData()=='purge' else '#dff2e5') if selected else QColor('transparent')
            for col in range(self.trash_table.columnCount()):
                item=self.trash_table.item(row,col)
                if item:item.setBackground(color);item.setForeground(QColor('#19354b') if selected else self.palette().text().color())
        self.trash_table.blockSignals(False)
    def apply_trash(self):
        selected=[r for i,r in enumerate(self.trash) if self.trash_table.item(i,0) and self.trash_table.item(i,0).checkState()==Qt.Checked]
        if not selected:self.trash_status.setText('ابتدا حداقل یک ردیف را انتخاب کنید.');return
        purge=self.trash_mode.currentData()=='purge'
        if purge and QMessageBox.question(self,'پاک کردن دائمی','موارد انتخاب‌شده پاک شوند؟ این کار قابل بازگردانی از سطل نیست.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        local=[r for r in selected if r['trash_kind']=='event'];remote=[r for r in selected if r['trash_kind']!='event']
        def work(client):
            results=[]
            for r in remote:
                payload=dict(kind=r['trash_kind'],id=r['id'],version=r['version'],restore=not purge)
                if r['trash_kind']=='group':payload['company']=r.get('company_id')
                if purge:payload['purge']=True
                try:client.request('workspace/trash',payload);results.append((r['id'],''))
                except Exception as exc:
                    error=str(exc)
                    if 'workspace_trash()' in error and 'unexpected keyword argument' in error:error='مرکز شرکت از عملیات جدید سطل بازیافت پشتیبانی نمی‌کند. برنامه و مرکز شرکت را روی رایانه میزبان به‌روزرسانی و دوباره اجرا کنید.'
                    results.append((r['id'],error))
            return results
        def done(results):
            errors=[error for _,error in results if error]
            succeeded={(r['trash_kind'],r['id'],str(r.get('company_id') or '')) for r in remote if any(r['id']==item_id and not error for item_id,error in results)}
            previous_events=list(self.owner.events);previous_trash=list(self.owner.data.get('event_trash',[]))
            local_succeeded=[]
            for r in local:
                item=next((x for x in self.owner.data.get('event_trash',[]) if x['event']['id']==r['id']),None)
                if not item:continue
                if not purge:
                    if datetime.fromisoformat(item['deleted_at']).astimezone(timezone.utc)<datetime.now(timezone.utc)-__import__('datetime').timedelta(days=30):errors.append('مهلت بازیابی یادآور تمام شده است.');continue
                    if not any(e['id']==r['id'] for e in self.owner.events):self.owner.events.append(item['event'])
                self.owner.data['event_trash'].remove(item)
                local_succeeded.append(r)
            if local:
                try:self.owner.persist();self.owner.refresh();succeeded.update((r['trash_kind'],r['id'],str(r.get('company_id') or '')) for r in local_succeeded)
                except Exception as exc:self.owner.events[:]=previous_events;self.owner.data['event_trash']=previous_trash;errors.append(str(exc))
            self.trash=[r for r in self.trash if (r['trash_kind'],r['id'],str(r.get('company_id') or '')) not in succeeded];self.render_trash();self.trash_status.setText(fa(len(succeeded))+' مورد انجام شد.' if succeeded else 'عملی انجام نشد.')
            if errors:QMessageBox.warning(self,'برخی موارد انجام نشد','\n'.join(errors[:5]))
            if remote:self.owner.org.revision=None;self.owner.org.sync()
            self.refresh()
        if remote:
            if not self.run(work,done):QMessageBox.warning(self,'سطل بازیافت','اتصال یا عملیات دیگری در حال انجام است.')
        else:done([])
    def change_page(self,delta):self._page+=delta;self.render()
    def select_today(self):
        i=self.today_table.currentRow()
        if 0<=i<len(self.page_tasks):self.owner.drawer.record(self.page_tasks[i])
    def select_favorite(self):
        i=self.favorite_table.currentRow()
        if 0<=i<len(getattr(self,'favorites',[])):self.owner.drawer.record(self.favorites[i])
    def select_request(self):
        r=self.selected_request()
        if r:self.owner.drawer.show_item(r['payload']['title'],'\n'.join([r['person'],REQUEST_TYPES[r['kind']],r['payload'].get('start_date','')+' تا '+r['payload'].get('end_date',''),r['payload'].get('notes','')]+[d['name']+' · '+d['status']+'\n'+d['note'] for d in r['decisions']]))
    def favorite_event(self,e):
        saved=self.owner.data.setdefault('favorite_events',[])
        if e['id'] in saved:saved.remove(e['id'])
        else:saved.append(e['id'])
        self.owner.persist();self.refresh()
    def move_task(self,id,status):
        from ui_permissions import gate
        if not gate(self.owner,'workspace','edit'):return
        t=next((t for t in self.snapshot.get('tasks',[]) if t['id']==id),None)
        if t and t.get('local_event'):
            e=t['local_event'];e['progress_status']=status;self.owner.set_done(e,status=='completed');self.refresh();return
        if t:self.mutate('records',dict(kind='task',company=t['company_id'],id=id,version=t['version'],private=bool(t['private']),department=t['department'],payload=dict(t['payload'],status=status)))
    def save_view(self):
        name,ok=QInputDialog.getText(self,'ذخیره نما','نام نما:')
        if ok and name.strip():self.mutate('workspace/views',dict(payload=dict(self.view.currentData() or {},name=name,q=self.query.text(),company=self.company.currentData())))
    def delete_view(self):
        id=(self.view.currentData() or {}).get('view_id')
        if id:self.mutate('workspace/views',dict(id=id,delete=True))
    def selected_request(self):
        i=self.request_table.currentRow();return self.visible_requests[i] if 0<=i<len(getattr(self,'visible_requests',[])) else None
    def new_request(self):
        if not self.companies:return
        d=RequestDialog(self,self.companies)
        if d.exec():self.mutate('workspace/requests',d.payload)
    def edit_request(self):
        r=self.selected_request()
        if not r:return
        d=RequestDialog(self,self.companies,r)
        if d.exec():self.mutate('workspace/requests',d.payload)
    def review_request(self,status):
        r=self.selected_request()
        if not r:return
        note,ok=QInputDialog.getMultiLineText(self,'بررسی درخواست','توضیح تصمیم:')
        if ok:self.mutate('workspace/review',dict(id=r['id'],version=r['version'],status=status,note=note))
    def chosen_company(self):
        co=self.company.currentData()
        if not co:QMessageBox.information(self,'انتخاب شرکت','یک شرکت را از فهرست بالای صفحه انتخاب کنید.')
        return co
    def workload(self):
        co=self.chosen_company()
        if co:self.run(lambda c:c.request('workspace/workload',company=co,month=self.month.text()),self.show_workload)
    def show_workload(self,data):
        days=[x['date'][-2:] for x in data['people'][0]['days']] if data['people'] else [];self.team_table.setColumnCount(len(days)+2);self.team_table.setHorizontalHeaderLabels(['نام','ساعت / ظرفیت']+list(map(fa,days)));rows=[]
        for p in data['people']:rows.append([p['name'],fa(p['total_hours']+' / '+p['total_capacity'])]+[('مرخصی '+fa(d['leave'])+'h\n' if float(d['leave']) else '')+fa(d['hours']+' / '+d['capacity']) for d in p['days']])
        fill(self.team_table,rows)
        from PySide6.QtGui import QColor
        for i,p in enumerate(data['people']):
            for j,d in enumerate(p['days']):
                item=self.team_table.item(i,j+2);item.setToolTip('\n'.join(t['title'] for t in d['tasks']))
                if d['overloaded']:item.setBackground(QColor('#FFE1E5'));item.setForeground(QColor('#7A1834'))
        self.state.setText('برآورد ساعت کارها در روز موعد؛ بدون برآورد، هر کار ۱ ساعت · بدون مسئول: '+fa(len(data['unassigned'])))
    def attendance(self):
        co=self.chosen_company()
        if co:self.run(lambda c:c.request('workspace/attendance',company=co,month=self.month.text()),lambda rows:self.team_rows(['نام','کد','تاریخ','بررسی'],[(r['title'],r['code'],fa(r['date']),r['reason']) for r in rows]))
    def team_rows(self,headers,rows):self.team_table.setColumnCount(len(headers));self.team_table.setHorizontalHeaderLabels(headers);fill(self.team_table,rows)
    def balance(self):
        co=self.chosen_company()
        if not co:return
        self.run(lambda c:c.request('workspace/balance',company=co,year=normalize(self.month.text()).split('/')[0]),lambda d:self.team_rows(['سال','سهم سال؛ ساعت','انتقالی','مصرف‌شده','در انتظار','مانده'],[[fa(d['year']),fa(d['annual']) if d['configured'] else 'قواعد تعیین نشده',fa(d['opening']),fa(d['used']),fa(d['pending']),fa(d['remaining']) if d['remaining'] is not None else '—']]))
    def policy(self):
        co=self.chosen_company()
        if not co:return
        self.run(lambda c:dict(capacity=c.request('workspace/policy',company=co,key='capacity')['value'],leave=c.request('workspace/policy',company=co,key='leave')['value'],users=c.request('users')),lambda d:PolicyDialog(self,co,d).exec())
    def routes(self):
        co=self.chosen_company()
        if not co:return
        self.run(lambda c:dict(routes=c.request('workspace/policy',company=co,key='routes')['value'],users=c.request('users')),lambda d:RoutesDialog(self,co,d).exec())
    def restore_trash(self):
        i=self.trash_table.currentRow()
        if 0<=i<len(getattr(self,'trash',[])):
            r=self.trash[i]
            if r['trash_kind']=='event':
                item=next((x for x in self.owner.data.get('event_trash',[]) if x['event']['id']==r['id']),None)
                if item:
                    if not any(e['id']==r['id'] for e in self.owner.events):self.owner.events.append(item['event'])
                    self.owner.data['event_trash'].remove(item);self.owner.persist();self.owner.refresh();self.refresh()
                return
            self.mutate('workspace/trash',dict(kind=r['trash_kind'],id=r['id'],version=r['version'],restore=True))

class PolicyDialog(QDialog):
    def __init__(self,panel,company,data):
        super().__init__(panel);self.panel=panel;self.company=company;self.data=data;self.setWindowTitle('قواعد شرکت؛ مرخصی و ظرفیت');self.resize(600,560);v=QVBoxLayout(self);f=QFormLayout();v.addLayout(f);self.person=QComboBox()
        for u in data['users']:
            if u.get('active') and (u['global_role']=='group_admin' or any(m['company_id']==company for m in u['memberships'])):self.person.addItem(u['fullname'],u['id'])
        self.year=QLineEdit(normalize(panel.month.text()).split('/')[0]);self.year.setMaxLength(4);self.daily=QDoubleSpinBox();self.daily.setRange(.25,24);self.daily.setSingleStep(.5);self.annual=QDoubleSpinBox();self.annual.setRange(0,10000);self.opening=QDoubleSpinBox();self.opening.setRange(0,10000)
        for title,w in [('فرد',self.person),('سال شمسی قواعد مرخصی',self.year),('ظرفیت روزانه؛ ساعت',self.daily),('سهم مرخصی سال؛ ساعت',self.annual),('مانده انتقالی؛ ساعت',self.opening)]:f.addRow(title,w)
        self.days=[];row=QHBoxLayout()
        for day,name in [(5,'شنبه'),(6,'یکشنبه'),(0,'دوشنبه'),(1,'سه‌شنبه'),(2,'چهارشنبه'),(3,'پنجشنبه'),(4,'جمعه')]:w=QCheckBox(name);w.setChecked(day in data['capacity'].get('working_days',[0,1,2,5,6]));self.days.append((day,w));row.addWidget(w)
        v.addLayout(row);self.holidays=QCheckBox('تعطیلات رسمی موجود در تقویم از ظرفیت و مصرف مرخصی کنار گذاشته شوند');self.holidays.setChecked(data['capacity'].get('exclude_holidays',True));v.addWidget(self.holidays);v.addWidget(label('مقادیر توسط مسئول شرکت برای هر سال تعیین می‌شوند. مانده قانونی خودکار حدس زده نمی‌شود. تعطیلات متغیر سال‌های آینده پس از تأیید تقویم همان سال نیاز به تکمیل دارند.'));self.person.currentIndexChanged.connect(self.load);self.year.editingFinished.connect(self.load);self.load();b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.button(QDialogButtonBox.Save).setText('ذخیره قواعد');b.button(QDialogButtonBox.Cancel).setText('بستن');b.accepted.connect(self.save);b.rejected.connect(self.reject);v.addWidget(b)
    def load(self):
        id=self.person.currentData();a=self.data['capacity'].get('people',{}).get(id,{});b=self.data['leave'].get('people',{}).get(id,{});annual=b.get('years',{}).get(normalize(self.year.text()),{});self.daily.setValue(float(a.get('daily_hours',8)));self.annual.setValue(float(annual.get('annual_hours',0)));self.opening.setValue(float(annual.get('opening_hours',0)))
    def save(self):
        days=[day for day,w in self.days if w.isChecked()]
        if not days:QMessageBox.warning(self,'قواعد','حداقل یک روز کاری انتخاب کنید.');return
        year=normalize(self.year.text())
        try:parse_j(year+'/01/01')
        except ValueError:QMessageBox.warning(self,'قواعد','سال شمسی معتبر وارد کنید.');return
        id=self.person.currentData();capacity=copy.deepcopy(self.data['capacity']);leave=copy.deepcopy(self.data['leave'])
        for p in (capacity,leave):p['working_days']=days;p['exclude_holidays']=self.holidays.isChecked();p.setdefault('people',{}).setdefault(id,{})['daily_hours']=str(self.daily.value())
        leave['people'][id].setdefault('years',{})[year]=dict(annual_hours=str(self.annual.value()),opening_hours=str(self.opening.value()))
        self.panel.run(lambda c:[c.request('workspace/policy',dict(company=self.company,key=k,payload=p)) for k,p in [('capacity',capacity),('leave',leave)]],lambda _:(self.accept(),self.panel.refresh()))

class RoutesDialog(QDialog):
    def __init__(self,panel,company,data):
        super().__init__(panel);self.setWindowTitle('مسیر تأیید درخواست‌ها');self.resize(620,480);self.panel=panel;self.company=company;v=QVBoxLayout(self);v.addWidget(label('هر درخواست می‌تواند تا سه مرحله تأیید داشته باشد؛ خالی یعنی بررسی توسط یکی از مدیران دیگر شرکت.'));f=QFormLayout();v.addLayout(f);self.choices={};managers=[u for u in data['users'] if u['active'] and (u['global_role']=='group_admin' or any(m['company_id']==company and m['role']=='company_manager' for m in u['memberships']))]
        for kind,name in REQUEST_TYPES.items():
            row=QHBoxLayout();choices=[];old=data['routes'].get(kind,[])
            for i in range(3):
                w=QComboBox();w.addItem('—','')
                for u in managers:w.addItem(u['fullname'],u['id'])
                if i<len(old):w.setCurrentIndex(max(0,w.findData(old[i])))
                row.addWidget(w);choices.append(w)
            self.choices[kind]=choices;f.addRow(name,row)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.button(QDialogButtonBox.Save).setText('ذخیره مسیر');b.button(QDialogButtonBox.Cancel).setText('بستن');b.accepted.connect(self.save);b.rejected.connect(self.reject);v.addWidget(b)
    def save(self):
        p={k:[w.currentData() for w in row if w.currentData()] for k,row in self.choices.items()};p={k:v for k,v in p.items() if v};self.panel.run(lambda c:c.request('workspace/policy',dict(company=self.company,key='routes',payload=p)),lambda _:(self.accept(),self.panel.refresh()))

class CommandPalette(QDialog):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.setWindowTitle('دسترسی سریع');self.resize(620,470);v=QVBoxLayout(self);self.query=QLineEdit();self.query.setPlaceholderText('نام بخش، کار، یادداشت یا یک فرمان…');v.addWidget(self.query);self.list=QListWidget();v.addWidget(self.list,1);self.list.itemActivated.connect(self.activate);self.query.returnPressed.connect(lambda:self.activate(self.list.currentItem()));self.query.textChanged.connect(self.search);self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(250);self.timer.timeout.connect(self.remote);self.remote_signals=Signals();self.remote_signals.done.connect(self.remote_ready);self.search('');self.query.setFocus()
    def search(self,q):
        from workspace_store import clean
        from ui_permissions import allowed
        self.list.clear();self.local=[];names=dict(home='خانه',month='ماه جاری',calendar='تقویم',occasions='مناسبت‌ها',calculation='محاسبه',tax='مالیات',services='سامانه‌ها',news='خبرها',company='فضای شرکت',chat='چت',desk='کارتابل من',workspace='کارها و پیگیری‌ها',attendance='تردد و ساعت کار',assistant='کارنامه',clients='مشتریان');visible=self.owner.data.get('preferences',{}).get('visible_modules',list(names))
        for key,w in self.owner.modules.items():
            if (key in visible or key in ('home','workspace') and self.owner.data.get('preferences',{}).get('preferences_schema',0)<8 or key=='clients' and self.owner.data.get('preferences',{}).get('preferences_schema',0)<11) and allowed(self.owner,key):
                title='رفتن به '+names.get(key,key)
                if not q or clean(q) in clean(title):self.add(title,lambda w=w:self.owner.tabs.setCurrentWidget(w))
        for title,fn,mod,action in [('افزودن یادآور',self.owner.add_event,'calendar','create'),('تنظیمات',self.owner.settings,'settings','view'),('یادداشت شخصی',lambda:(self.owner.tabs.setCurrentWidget(self.owner.desk),self.owner.desk.new_note()),'desk','create')]:
            if allowed(self.owner,mod,action) and (not q or clean(q) in clean(title)):self.add(title,fn)
        if q and allowed(self.owner,'calendar'):
            for e in self.owner.display_events():
                if clean(q) in clean(e['title']):self.add('یادآور · '+e['title'],lambda e=e:self.owner.drawer.show_event(e))
        if self.list.count():self.list.setCurrentRow(0)
        self.timer.start()
    def add(self,title,fn):
        self.local.append(fn);item=QListWidgetItem(title);item.setData(Qt.UserRole,len(self.local)-1);self.list.addItem(item)
    def remote(self):
        client=self.owner.org.client;q=self.query.text()
        from ui_permissions import allowed
        if not client or not q or not allowed(self.owner,'workspace'):return
        from org_client import Client
        def work():
            c=Client(client.url,client.session.verify if isinstance(client.session.verify,str) else None,getattr(client,'fingerprint',None));c.token=client.token
            try:self.remote_signals.done.emit(c.request('workspace/search',q=q),None,q)
            except Exception as e:self.remote_signals.done.emit(None,e,q)
            finally:c.session.close()
        threading.Thread(target=work,daemon=True).start()
    def remote_ready(self,data,error,q):
        if error or q!=self.query.text():return
        for r in data:self.add(('پرونده · ' if r['kind']=='record' else 'یادداشت · ')+r['title'],lambda r=r:self.open_result(r))
    def open_result(self,r):
        if r['kind']=='record':self.owner.workspace.run(lambda c:c.request('record',id=r['id']),self.owner.drawer.record)
        else:self.owner.tabs.setCurrentWidget(self.owner.desk)
    def activate(self,item):
        if item:
            fn=self.local[item.data(Qt.UserRole)];self.accept();fn()

