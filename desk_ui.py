"""Personal desk: self-service requests, private notes and account preferences."""
import copy,threading,json
from datetime import datetime,timezone
from PySide6.QtCore import Qt,QObject,Signal,QTimer,QTime
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QTabWidget,QTableWidget,QTableWidgetItem,QAbstractItemView,QDialog,QDialogButtonBox,QLineEdit,QPlainTextEdit,QComboBox,QCheckBox,QTimeEdit,QMessageBox,QScrollArea,QHeaderView)
from storage import fa,today_j,jformat,parse_j,normalize
from reminders import parse_leads
from ui_icons import iconize

STATUS={'pending':'منتظر بررسی','approved':'تأیید شده','rejected':'رد شده','cancelled':'لغو شده'}
class DeskSignals(QObject):done=Signal(object,object)

def table(headers):
    w=QTableWidget(0,len(headers));w.setHorizontalHeaderLabels(headers);w.setSelectionBehavior(QAbstractItemView.SelectRows);w.setSelectionMode(QAbstractItemView.SingleSelection);w.setEditTriggers(QAbstractItemView.NoEditTriggers);w.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);w.horizontalHeader().setHighlightSections(False);w.verticalHeader().setDefaultSectionSize(38);w.verticalHeader().hide();w.setShowGrid(False);w.setAlternatingRowColors(True);return w
def icon_button(title,key,fn):
    b=QPushButton(title);iconize(b,key,title);b.clicked.connect(fn);return b

class LeaveDialog(QDialog):
    def __init__(self,owner,companies,record=None):
        super().__init__(owner);self.setWindowTitle('درخواست مرخصی');self.setLayoutDirection(Qt.RightToLeft);self.resize(600,540);self.record=record;p=record['payload'] if record else {};v=QVBoxLayout(self);f=QFormLayout();v.addLayout(f);self.name=QLineEdit((owner.session_user or {}).get('fullname',''));self.name.setReadOnly(True);f.addRow('درخواست‌کننده',self.name);self.company=QComboBox()
        for c in companies:self.company.addItem(c['name'],c['id'])
        if record:self.company.setCurrentIndex(self.company.findData(record['company_id']));self.company.setEnabled(False)
        f.addRow('شرکت',self.company);self.kind=QComboBox();self.kind.addItems(['استحقاقی','استعلاجی','بدون حقوق','ساعتی','سایر']);self.kind.setCurrentText(p.get('leave_type','استحقاقی'));f.addRow('نوع مرخصی',self.kind);self.start=QLineEdit(p.get('start_date',jformat(today_j())));self.end=QLineEdit(p.get('end_date',jformat(today_j())));f.addRow('از تاریخ شمسی',self.start);f.addRow('تا تاریخ شمسی',self.end);self.begin_time=QTimeEdit();self.begin_time.setDisplayFormat('HH:mm');self.end_time=QTimeEdit();self.end_time.setDisplayFormat('HH:mm');self.begin_time.setTime(QTime.fromString(p.get('start_time') or '09:00','HH:mm'));self.end_time.setTime(QTime.fromString(p.get('end_time') or '10:00','HH:mm'));f.addRow('از ساعت',self.begin_time);f.addRow('تا ساعت',self.end_time);self.form=f;self.kind.currentTextChanged.connect(self.toggle);self.toggle();self.reason=QPlainTextEdit(p.get('notes',''));self.reason.setPlaceholderText('توضیح اختیاری برای مدیر');self.reason.setMaximumHeight(135);v.addWidget(self.reason);self.error=QLabel();self.error.setWordWrap(True);v.addWidget(self.error);b=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);b.button(QDialogButtonBox.Ok).setText('ارسال برای مدیران');b.button(QDialogButtonBox.Cancel).setText('انصراف');b.accepted.connect(self.validate);b.rejected.connect(self.reject);v.addWidget(b)
    def toggle(self):
        hourly=self.kind.currentText()=='ساعتی';self.form.setRowVisible(self.begin_time,hourly);self.form.setRowVisible(self.end_time,hourly)
    def validate(self):
        try:
            if not self.company.currentData():raise ValueError('شرکت را انتخاب کنید.')
            a=parse_j(self.start.text());b=parse_j(self.end.text())
            if b<a:raise ValueError('تاریخ پایان قبل از شروع است.')
            if self.kind.currentText()=='ساعتی' and (a!=b or self.end_time.time()<=self.begin_time.time()):raise ValueError('مرخصی ساعتی در یک روز و ساعت پایان بعد از شروع باشد.')
            self.payload=dict(start_date=normalize(jformat(a)),end_date=normalize(jformat(b)),leave_type=self.kind.currentText(),start_time=self.begin_time.time().toString('HH:mm'),end_time=self.end_time.time().toString('HH:mm'),notes=self.reason.toPlainText());self.accept()
        except Exception as e:self.error.setText(str(e))

class NoteDialog(QDialog):
    def __init__(self,owner,note=None):
        super().__init__(owner);self.setWindowTitle('یادداشت شخصی');self.setLayoutDirection(Qt.RightToLeft);self.resize(650,570);p=note or {};v=QVBoxLayout(self);self.title=QLineEdit(p.get('title',''));self.title.setMaxLength(200);self.title.setPlaceholderText('عنوان یادداشت');v.addWidget(self.title);self.body=QPlainTextEdit(p.get('body',''));self.body.setPlaceholderText('متن شخصی شما');v.addWidget(self.body,1);f=QFormLayout();v.addLayout(f);self.calendar=QCheckBox('در تقویم و یادآورها نمایش داده شود');self.calendar.setChecked(bool(p.get('calendar_enabled')));f.addRow(self.calendar);self.day=QLineEdit(p.get('date_jalali') or jformat(owner.selected));f.addRow('تاریخ شمسی',self.day);self.leads=QLineEdit('، '.join(map(str,(p.get('lead_days') or owner.data['settings']['personal_lead_days']))));f.addRow('روزهای قبل از موعد',self.leads);self.completed_check=QCheckBox('انجام شده');self.completed_check.setChecked(bool(p.get('completed')));f.addRow(self.completed_check);self.calendar.toggled.connect(self.day.setEnabled);self.calendar.toggled.connect(self.leads.setEnabled);self.day.setEnabled(self.calendar.isChecked());self.leads.setEnabled(self.calendar.isChecked());self.error=QLabel();v.addWidget(self.error);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('ذخیره');buttons.button(QDialogButtonBox.Cancel).setText('انصراف');buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);v.addWidget(buttons)
    def validate(self):
        try:
            if not self.title.text().strip():raise ValueError('عنوان یادداشت را وارد کنید.')
            when=normalize(jformat(parse_j(self.day.text()))) if self.calendar.isChecked() else ''
            self.payload=dict(title=self.title.text().strip(),body=self.body.toPlainText(),calendar_enabled=self.calendar.isChecked(),date_jalali=when,lead_days=parse_leads(self.leads.text()) if self.calendar.isChecked() else [],completed=self.completed_check.isChecked());self.accept()
        except Exception as e:self.error.setText(str(e))

def leave_description(row,companies):
    p=row['payload'];names={c['id']:c['name'] for c in companies};lines=[row.get('requester_name') or p.get('requester_name',''),names.get(row['company_id'],''),p['leave_type']+' | '+fa(p['start_date'])+' تا '+fa(p['end_date'])]
    if p.get('start_time'):lines.append(fa(p['start_time'])+' تا '+fa(p['end_time'])+' | '+fa(p.get('hours',''))+' ساعت')
    lines.extend([STATUS[row['status']],p.get('notes','')])
    if row.get('reviewer_name'):lines.extend(['بررسی‌کننده: '+row['reviewer_name'],row.get('review_note','')])
    return '\n\n'.join(x for x in lines if x)

class ReviewDialog(QDialog):
    def __init__(self,owner,row,companies,review=False):
        super().__init__(owner);self.setWindowTitle('بررسی مرخصی' if review else 'جزئیات درخواست');self.setLayoutDirection(Qt.RightToLeft);self.resize(600,570);v=QVBoxLayout(self);body=QPlainTextEdit(leave_description(row,companies));body.setReadOnly(True);v.addWidget(body);self.note=QPlainTextEdit(self);self.note.setPlaceholderText('توضیح تصمیم برای درخواست‌کننده');self.note.setMaximumHeight(100);self.note.setVisible(review);v.addWidget(self.note);buttons=QDialogButtonBox(QDialogButtonBox.Close);buttons.button(QDialogButtonBox.Close).setText('بستن');buttons.rejected.connect(self.reject);v.addWidget(buttons)
        if review:
            for title,status in [('تأیید','approved'),('رد درخواست','rejected')]:b=buttons.addButton(title,QDialogButtonBox.ActionRole);b.clicked.connect(lambda checked=False,status=status:self.decide(status))
    def decide(self,status):self.status=status;self.accept()

class PersonalEditor(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;v=QVBoxLayout(self);self.tabs=QTabWidget();v.addWidget(self.tabs,1);self.loaded=False;self.original=None;self.reload();actions=QHBoxLayout();save=QPushButton('ذخیره تغییرات من');save.setObjectName('Primary');save.clicked.connect(self.save);actions.addWidget(save);advanced=QPushButton('رنگ‌ها و یادآورها');advanced.clicked.connect(lambda:owner.settings());actions.addWidget(advanced);actions.addStretch();v.addLayout(actions)
    def reload(self):
        from personalization_ui import PersonalPanel,ServicesSettings
        from official_news import get_sources
        while self.tabs.count():w=self.tabs.widget(0);self.tabs.removeTab(0);w.deleteLater()
        self.personal=PersonalPanel(self.owner);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(self.personal);self.tabs.addTab(scroll,'حساب و نمایش');self.services=ServicesSettings(self.owner);self.tabs.addTab(self.services,'سامانه‌های من');news=QWidget();lay=QVBoxLayout(news);self.terms=QLineEdit(self.owner.data.get('preferences',{}).get('news_terms',''));self.terms.setPlaceholderText('لینک، واژه یا #هشتگ؛ جداشده با ویرگول');lay.addWidget(self.terms);self.sources={};chosen=self.owner.data.get('preferences',{}).get('news_source_ids')
        for s in get_sources(self.owner.data):c=QCheckBox(s['name']);c.setChecked(chosen is None or s['id'] in chosen);lay.addWidget(c);self.sources[s['id']]=c
        lay.addStretch();self.tabs.addTab(news,'خبرهای من');self.original=copy.deepcopy(self.owner.data.get('preferences',{}))
    def save(self):
        try:
            from personalization_ui import request_wait
            prefs=self.personal.values();prefs.update(services=copy.deepcopy(self.services.items),news_terms=self.terms.text().strip(),news_source_ids=[key for key,c in self.sources.items() if c.isChecked()]);profile=dict(avatar=self.personal.avatar,color=self.personal.color,preferences=prefs)
            if self.owner.session_user:
                if self.owner.org.client:profile=request_wait(self.owner,'profile',profile)
                self.owner.session_user['profile']=profile
                from access_ui import config,save_config
                cfg=config(self.owner.base_dir);cfg.update(avatar=profile['avatar'],display_name=self.owner.session_user['fullname']);save_config(self.owner.base_dir,cfg)
            self.owner.data.update(preferences=prefs,account_profile=profile);self.owner.persist();from main_ui import apply_preferences
            apply_preferences(self.owner);self.owner.news_panel.reload_sources();self.owner.refresh();self.owner.statusBar().showMessage('تنظیمات حساب شما ذخیره شد.',5000);self.original=copy.deepcopy(prefs)
        except Exception as e:QMessageBox.warning(self,'تنظیمات شخصی',str(e))

class PersonalDesk(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.busy=False;self.signals=DeskSignals();self.signals.done.connect(self.finished);self.snapshot={};self.my_rows=[];self.review_rows=[];self.note_rows=[];self.queued=set();v=QVBoxLayout(self);v.setContentsMargins(18,14,18,14);header=QHBoxLayout();self.heading=QLabel('کارتابل من');self.heading.setObjectName('Hero');header.addWidget(self.heading);header.addStretch();header.addWidget(icon_button('تازه‌سازی','refresh',self.sync));v.addLayout(header);self.status=QLabel('');self.status.setWordWrap(True);v.addWidget(self.status);self.tabs=QTabWidget();v.addWidget(self.tabs,1)
        mine=QWidget();a=QVBoxLayout(mine);row=QHBoxLayout();row.addWidget(QPushButton('درخواست مرخصی',clicked=self.new_leave));row.addWidget(icon_button('ویرایش درخواست','edit',self.edit_leave));row.addWidget(icon_button('جزئیات درخواست','open',self.view_leave));row.addWidget(icon_button('لغو درخواست','delete',self.cancel_leave));row.addStretch();a.addLayout(row);self.leaves=table(['نوع','از تاریخ','تا تاریخ','شرکت','وضعیت','بررسی‌کننده']);self.leaves.doubleClicked.connect(self.view_leave);a.addWidget(self.leaves);self.tabs.addTab(mine,'درخواست‌های من')
        notes=QWidget();n=QVBoxLayout(notes);row=QHBoxLayout()
        for title,key,fn in [('یادداشت تازه','add',self.new_note),('ویرایش یادداشت','edit',self.edit_selected_note),('نمایش در تقویم','open',self.note_calendar),('حذف یادداشت','delete',self.delete_note)]:row.addWidget(icon_button(title,key,fn))
        self.note_query=QLineEdit();self.note_query.setPlaceholderText('جستجو در یادداشت‌های من');self.note_query.textChanged.connect(self.render_notes);row.addWidget(self.note_query,1);n.addLayout(row);self.notes=table(['عنوان','تاریخ تقویم','یادآوری','وضعیت']);self.notes.doubleClicked.connect(self.edit_selected_note);n.addWidget(self.notes);self.tabs.addTab(notes,'یادداشت‌های من');self.personal_page=QWidget();self.personal_layout=QVBoxLayout(self.personal_page);self.personal_layout.setContentsMargins(0,0,0,0);self.editor=None;self.tabs.addTab(self.personal_page,'شخصی‌سازی');self.tabs.currentChanged.connect(self.open_personal)
        self.review_page=QWidget();r=QVBoxLayout(self.review_page);row=QHBoxLayout();self.pending=QCheckBox('فقط منتظر بررسی');self.pending.setChecked(True);self.pending.toggled.connect(self.render_requests);row.addWidget(self.pending);row.addStretch();review=QPushButton('بررسی درخواست');review.clicked.connect(self.review);row.addWidget(review);r.addLayout(row);self.incoming=table(['درخواست‌کننده','نوع','از تاریخ','تا تاریخ','شرکت','وضعیت']);self.incoming.doubleClicked.connect(self.review);r.addWidget(self.incoming);self.review_index=self.tabs.addTab(self.review_page,'بررسی مدیر');self.tabs.setTabVisible(self.review_index,False)
        cache=owner.data.get('desk_cache',{});identity=(owner.session_user or {}).get('id')
        if identity and cache.get('user_id')==identity:self.apply_snapshot(cache,initial=True,offline=True)
        self.timer=QTimer(self);self.timer.setInterval(12000);self.timer.timeout.connect(self.sync);self.timer.start();self.start_timer=QTimer(self);self.start_timer.setSingleShot(True);self.start_timer.timeout.connect(self.startup_sync);self.start_timer.start(1250)
    def startup_sync(self):
        if self.timer.isActive():self.sync()
    def open_personal(self,index):
        if self.tabs.widget(index) is self.personal_page and self.editor is None:self.editor=PersonalEditor(self.owner);self.personal_layout.addWidget(self.editor)
    def run(self,fn,callback):
        source=self.owner.org.client
        if self.busy:return False
        if not source:self.status.setText('برای ارسال درخواست یا ذخیره یادداشت، به مرکز شرکت وارد شوید.');return False
        from org_client import Client
        client=Client(source.url,source.session.verify if isinstance(source.session.verify,str) else None,getattr(source,'fingerprint',None));client.token=source.token;self.callback=callback;self.busy=True
        def work():
            try:self.signals.done.emit(fn(client),None)
            except Exception as e:self.signals.done.emit(None,e)
            finally:client.session.close()
        threading.Thread(target=work,daemon=True).start();return True
    def finished(self,value,error):
        self.busy=False;callback=self.callback;self.callback=None
        if error:
            self.status.setText(str(error))
            if getattr(error,'status',None)==401:QTimer.singleShot(0,self.owner.lock_session)
            return
        self.status.clear();callback(value)
    def sync(self):
        if self.owner._locking or self.owner._exit_pending or self.owner._exit_approved or not self.owner.org.client:return
        pending=self.owner.data.get('pending_desk_restore');restoring='pending_desk_restore' in self.owner.data
        def fetch(c):
            if restoring:c.request('desk/restore',dict(notes=pending))
            return c.request('desk')
        def received(value):
            if restoring:self.owner.data.pop('pending_desk_restore',None)
            self.apply_snapshot(value)
        self.run(fetch,received)
    def apply_snapshot(self,value,initial=False,offline=False):
        if value.get('user_id')!=(self.owner.session_user or {}).get('id'):return
        changed=self.snapshot!=value
        if changed:
            self.snapshot=value;self.heading.setText('کارتابل '+(self.owner.session_user or {}).get('fullname','من'));self.tabs.setTabVisible(self.review_index,bool(value.get('managed_companies')));self.render_notes();self.render_requests();self.note_events()
        if not initial and changed:
            if self.owner.data.get('desk_cache')!=value:self.owner.data['desk_cache']=copy.deepcopy(value);self.owner.persist()
            self.owner.refresh()
        if not offline:
            for notice in value.get('notifications',[]):
                if notice.get('shown') or notice['id'] in self.queued:continue
                self.queued.add(notice['id']);company=next((c['name'] for c in value.get('companies',[]) if any(r['id']==notice['leave_id'] and r['company_id']==c['id'] for r in value.get('leaves',[])+value.get('incoming',[]))),None);self.owner.popup(notice['body'],title=notice['title'],company=company,on_click=lambda n=notice:self.open_notice(n),on_shown=lambda n=notice:self.mark_notice(n,'shown'))
    def mark_notice(self,notice,action):
        source=self.owner.org.client
        if not source:return
        from org_client import Client
        def work():
            c=Client(source.url,source.session.verify if isinstance(source.session.verify,str) else None,getattr(source,'fingerprint',None));c.token=source.token
            try:c.request('desk/notification',dict(id=notice['id'],action=action))
            except Exception:self.queued.discard(notice['id'])
            finally:c.session.close()
        threading.Thread(target=work,daemon=True).start()
    def open_notice(self,notice):
        self.owner.show_main();self.owner.tabs.setCurrentWidget(self);self.mark_notice(notice,'opened');row=next((r for r in self.snapshot.get('leaves',[])+self.snapshot.get('incoming',[]) if r['id']==notice['leave_id']),None)
        if row:
            incoming=row['requester_id']!=self.owner.session_user['id'];self.tabs.setCurrentIndex(self.review_index if incoming else 0);dialog=ReviewDialog(self.owner,row,self.snapshot.get('companies',[]),incoming and row['status']=='pending')
            if dialog.exec():self.mutation('desk/review',dict(id=row['id'],version=row['version'],status=dialog.status,note=dialog.note.toPlainText()))
    def note_events(self):
        events=[]
        for n in self.snapshot.get('notes',[]):
            if not n['calendar_enabled'] or not n.get('date_jalali'):continue
            events.append(dict(id='desk-note-'+n['id'],desk_note_id=n['id'],title=n['title'],company='شخصی',date_jalali=n['date_jalali'],category='سایر',notes=n['body'],done=n['completed'],needs_review=False,recurrence='بدون تکرار',priority='متوسط',reminder_group='personal',reminder_custom=True,lead_days=n['lead_days'],last_alerts=self.owner.data.get('desk_alerts',{}).get(n['id'],{})))
        self.owner.desk_events=events
    def render_requests(self):
        names={c['id']:c['name'] for c in self.snapshot.get('companies',[])};self.my_rows=self.snapshot.get('leaves',[]);self.review_rows=[r for r in self.snapshot.get('incoming',[]) if not self.pending.isChecked() or r['status']=='pending']
        for widget,rows,manager in [(self.leaves,self.my_rows,False),(self.incoming,self.review_rows,True)]:
            old=widget.currentRow();widget.setRowCount(len(rows))
            for i,row in enumerate(rows):
                p=row['payload'];items=[p['leave_type'],fa(p['start_date']),fa(p['end_date']),names.get(row['company_id'],''),STATUS[row['status']]]
                items=([row.get('requester_name','')]+items) if manager else (items+[row.get('reviewer_name','')])
                for j,text in enumerate(items):widget.setItem(i,j,QTableWidgetItem(text))
            if rows:widget.setCurrentCell(min(max(0,old),len(rows)-1),0)
    def render_notes(self):
        previous=self.selected_note();previous_id=previous['id'] if previous else None;query=normalize(self.note_query.text()).casefold();self.note_rows=[n for n in self.snapshot.get('notes',[]) if not query or query in normalize(n['title']+' '+n['body']).casefold()];old=self.notes.currentRow();self.notes.setRowCount(len(self.note_rows))
        for i,n in enumerate(self.note_rows):
            for j,value in enumerate([n['title'],fa(n['date_jalali']) if n['calendar_enabled'] else '—','فعال' if n['calendar_enabled'] else '—','انجام‌شده' if n['completed'] else 'باز']):self.notes.setItem(i,j,QTableWidgetItem(value))
        if self.note_rows:
            current=next((i for i,n in enumerate(self.note_rows) if n['id']==previous_id),min(max(0,old),len(self.note_rows)-1));self.notes.setCurrentCell(current,0)
    def mutation(self,path,payload):
        def work(c):result=c.request(path,payload);return result,c.request('desk')
        def done(value):
            result,snapshot=value;self.owner.data['company_write_at']=datetime.now(timezone.utc).isoformat();self.apply_snapshot(snapshot)
            if isinstance(result,dict) and result.get('managers_notified')==0:self.status.setText('درخواست ثبت شد؛ برای بررسی آن، مدیر دیگری باید به این شرکت دسترسی داشته باشد.')
        return self.run(work,done)
    def new_leave(self):
        if not self.snapshot.get('companies'):
            if self.owner.org.client:self.run(lambda c:c.request('desk'),lambda value:(self.apply_snapshot(value),self.new_leave() if value['companies'] else None))
            return
        d=LeaveDialog(self.owner,self.snapshot['companies'])
        if d.exec():self.mutation('desk/leave',dict(company=d.company.currentData(),payload=d.payload))
    def selected_leave(self,review=False):
        i=(self.incoming if review else self.leaves).currentRow();rows=self.review_rows if review else self.my_rows;return rows[i] if 0<=i<len(rows) else None
    def edit_leave(self):
        row=self.selected_leave()
        if not row:return
        if row['status']!='pending':self.view_leave();return
        d=LeaveDialog(self.owner,self.snapshot['companies'],row)
        if d.exec():self.mutation('desk/leave',dict(company=row['company_id'],payload=d.payload,id=row['id'],version=row['version']))
    def view_leave(self,*_):
        row=self.selected_leave()
        if row:ReviewDialog(self.owner,row,self.snapshot['companies']).exec()
    def cancel_leave(self):
        row=self.selected_leave()
        if row and row['status']=='pending' and QMessageBox.question(self,'لغو درخواست','درخواست مرخصی لغو شود؟',QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:self.mutation('desk/cancel',dict(id=row['id'],version=row['version']))
    def review(self,*_):
        row=self.selected_leave(True)
        if not row:return
        d=ReviewDialog(self.owner,row,self.snapshot['companies'],row['status']=='pending')
        if d.exec():self.mutation('desk/review',dict(id=row['id'],version=row['version'],status=d.status,note=d.note.toPlainText()))
    def new_note(self):
        d=NoteDialog(self.owner)
        if d.exec():self.mutation('desk/note',dict(payload=d.payload))
    def selected_note(self):
        i=self.notes.currentRow();return self.note_rows[i] if 0<=i<len(self.note_rows) else None
    def edit_selected_note(self,*_):
        note=self.selected_note()
        if note:self.edit_note(note['id'])
    def edit_note(self,id):
        note=next((n for n in self.snapshot.get('notes',[]) if n['id']==id),None)
        if not note:return
        d=NoteDialog(self.owner,note)
        if d.exec():self.mutation('desk/note',dict(id=id,version=note['version'],payload=d.payload))
    def complete_note(self,id,done):
        note=next((n for n in self.snapshot.get('notes',[]) if n['id']==id),None)
        if note:self.mutation('desk/note',dict(id=id,version=note['version'],payload=dict(note,completed=done)))
    def delete_note(self):
        note=self.selected_note()
        if note and QMessageBox.question(self,'حذف یادداشت','یادداشت شخصی و نمایش آن در تقویم حذف شود؟',QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:self.mutation('desk/delete-note',dict(id=note['id'],version=note['version']))
    def note_calendar(self):
        note=self.selected_note()
        if not note:return
        if not note['calendar_enabled']:self.edit_note(note['id']);return
        self.owner.selected=parse_j(note['date_jalali']);self.owner.year=self.owner.selected.year;self.owner.month=self.owner.selected.month;self.owner.mode_filter.setCurrentText('موعدهای روز انتخابی');self.owner.company_filter.setCurrentIndex(0);self.owner.category_filter.setCurrentIndex(0);self.owner.search.clear();self.owner.refresh();self.owner.tabs.setCurrentWidget(self.owner.calendar_page)
