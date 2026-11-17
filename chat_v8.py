"""Threads, mentions, search, saved messages and durable delivery for native chat."""
import copy,json
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QWidget,QHBoxLayout,QVBoxLayout,QPushButton,QLineEdit,QComboBox,QLabel,QDialog,QListWidget,QDialogButtonBox,QMessageBox,QMenu,QInputDialog
from chat_ui import ChatPanel
from chat_delivery import DeliveryQueue
from storage import app_dir,fa

class ChatPanelV8(ChatPanel):
    def finished(self,result,error):
        super().finished(result,error)
        if getattr(self,'_send_waiting',False) and not error and not self.owner._locking and not self.owner._exit_approved:self.flush()
    def __init__(self,owner):
        self.reply_to=None;self.thread=None;self.delivery=None;self._delivery_identity=None;self._flushing=False;self._draft_room=None;self._draft_loading=False;self._last_render=None;self._revision_seen=-1
        super().__init__(owner);self.search=QLineEdit();self.search.setPlaceholderText('جستجوی پیام و نام پیوست');self.search.setClearButtonEnabled(True);self.search.textChanged.connect(self.filter_changed);self.filter=QComboBox();self.filter.addItem('همه پیام‌ها','');self.filter.addItem('ذخیره‌شده','saved');self.filter.addItem('سنجاق‌شده','pinned');self.filter.currentIndexChanged.connect(self.filter_changed);self.reply_label=QLabel();self.reply_label.setWordWrap(True);self.back_thread=QPushButton('بازگشت به گروه');self.back_thread.clicked.connect(self.close_thread);self.back_thread.hide();self.outbox_label=QPushButton('صف ارسال');self.outbox_label.clicked.connect(self.show_outbox)
        main=self.area.parentWidget();box=main.layout();filters=QHBoxLayout();filters.addWidget(self.search,1);filters.addWidget(self.filter);filters.addWidget(self.back_thread);filters.addWidget(self.outbox_label);self.message_filters=QWidget();self.message_filters.setLayout(filters);box.insertWidget(1,self.message_filters);self.message_filters.hide();find_button=QPushButton();from ui_icons import iconize;iconize(find_button,'search','جستجو در پیام‌ها');find_button.clicked.connect(lambda:self.message_filters.setVisible(not self.message_filters.isVisible()));self.header_layout.addWidget(find_button);box.insertWidget(box.count()-2,self.reply_label);extra=self.actions_layout;mention=QPushButton('@');mention.setToolTip('اشاره به فرد');mention.setAccessibleName('اشاره به فرد');mention.clicked.connect(self.mention);extra.addWidget(mention);cancel=QPushButton('×');cancel.setToolTip('لغو پاسخ');cancel.setAccessibleName('لغو پاسخ');cancel.clicked.connect(self.cancel_reply);extra.addWidget(cancel);self.draft_timer=QTimer(self);self.draft_timer.setSingleShot(True);self.draft_timer.setInterval(500);self.draft_timer.timeout.connect(self.save_draft);self.compose.textChanged.connect(lambda:self.draft_timer.start());self.filter_timer=QTimer(self);self.filter_timer.setSingleShot(True);self.filter_timer.setInterval(250);self.filter_timer.timeout.connect(self.load_filtered)
        self.new_group_button.clicked.disconnect();self.new_group_button.setText('+');self.new_chat_menu=QMenu(self.new_group_button);self.new_chat_menu.addAction('گفتگوی شخصی',self.new_direct);self.new_chat_menu.addAction('گروه جدید',self.create_group);self.new_group_button.setMenu(self.new_chat_menu)
        extra_menu_button=QPushButton('＋');extra_menu_button.setAccessibleName('ابزارهای گفتگو');extra_menu_button.setToolTip('ابزارهای گفتگو');extra_menu=QMenu(extra_menu_button)
        for button,key in self._chat_actions:
            if key not in ('attachment','emoji'):
                extra_menu.addAction(button.accessibleName(),button.click);button.hide()
        extra_menu_button.setMenu(extra_menu);extra.insertWidget(0,extra_menu_button)
        room_options=QPushButton('گزینه‌های گفتگو  ⋯');room_menu=QMenu(room_options);room_menu.addAction('حذف از فهرست / غیرفعال‌سازی گروه',self.archive_room);room_menu.addAction('پاک‌کردن پیام‌ها برای همه',self.clear_chat);room_options.setMenu(room_menu);self.room_list.parentWidget().layout().addWidget(room_options)
    def clear_chat(self):
        if not self.selected:return
        selection=copy.deepcopy(self.selected)
        def preview(value):
            count=value['count']
            if not count:self.status.setText('پیامی برای پاک‌کردن وجود ندارد.');return
            text='متن و پیوست‌های '+fa(count)+' پیام فعلی برای همه اعضای این گفتگو در برنامه غیرقابل دسترس می‌شود. پیام‌های جدید و نسخه‌های پشتیبان قبلی تغییر نمی‌کنند. ادامه می‌دهید؟'
            if QMessageBox.question(self,'پاک‌کردن پیام‌ها برای همه',text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            def done(result):self.status.setText(fa(result['count'])+' پیام پاک شد.');self._last_render=None;self.poll()
            self.run(lambda c:c.request('workspace/chat-clear',dict(company=selection['company'],room=selection['room'],through=value['through'])),done)
        self.run(lambda c:c.request('workspace/chat-clear',dict(company=selection['company'],room=selection['room'])),preview)
    def archive_room(self):
        if not self.selected:return
        selection=copy.deepcopy(self.selected);direct=bool(selection.get('direct'))
        message=('پیام‌های ذخیره‌شده از فهرست شما پنهان می‌شوند و با ساخت دوباره در دسترس خواهند بود.' if selection.get('saved') else 'این گفتگوی شخصی فقط از فهرست شما پنهان می‌شود؛ پیام‌ها برای طرف مقابل باقی می‌مانند و با شروع دوباره گفتگو بازمی‌گردند.' if direct else 'این گروه برای همه اعضای شرکت غیرفعال می‌شود؛ پیام‌ها حذف نمی‌شوند و مدیر می‌تواند گروه را بازگرداند.')
        if QMessageBox.question(self,'تأیید گفتگو',message+'\nادامه می‌دهید؟',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        def done(_):
            self.selected=None;self.messages=[];self._last_render=None;self.clear_bubbles();self.title.setText('یک گروه را انتخاب کنید');self.status.setText('تغییر انجام شد.');self.poll()
        self.run(lambda c:c.request('workspace/chat-hide',dict(company=selection['company'],room=selection['room'])),done)
    def restore_group(self):
        titles=['مدیران','کارکنان','مشترک'];keys=['managers','staff','general'];title,ok=QInputDialog.getItem(self,'بازگرداندن گروه','گروه',titles,0,False)
        if not ok:return
        company='__shared_chat__';room=keys[titles.index(title)]
        actions=['بازگرداندن گروه','غیرفعال‌کردن گروه'];action,ok=QInputDialog.getItem(self,'مدیریت گروه','عملیات',actions,0,False)
        if not ok:return
        message='گروه «'+title+'» '+('دوباره فعال شود؟' if action==actions[0] else 'برای همه غیرفعال شود؟ پیام‌ها حفظ می‌شوند.')
        if QMessageBox.question(self,'تأیید',message,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        path='workspace/chat-restore-group' if action==actions[0] else 'workspace/chat-hide'
        self.run(lambda c:c.request(path,dict(company=company,room=room)),lambda _:(self.status.setText('تغییر گروه انجام شد.'),self.poll()))
    def ensure_delivery(self):
        user=self.owner.session_user or {};c=self.client();origin=('network://'+c.fingerprint if getattr(c,'fingerprint',None) else c.url) if c else self.owner.data.get('settings',{}).get('company_url','local');identity=(origin,user.get('id',''))
        if not identity[1]:return
        if identity!=self._delivery_identity:
            import hashlib
            folder=app_dir()/'secure-drafts'
            for previous_origin in (origin,origin+'#empty-chat-v1'):
                old=hashlib.sha256((previous_origin.rstrip('/')+'\n'+identity[1]).encode()).hexdigest();(folder/('chat-'+old+'.dpapi')).unlink(missing_ok=True)
            self.delivery=DeliveryQueue(folder,origin+'#saved-chat-v2',identity[1]);self._delivery_identity=identity
    def save_draft(self):
        if self._draft_loading or not self.selected:return
        try:
            self.ensure_delivery()
            if self.delivery:self.delivery.save_draft(self.selected['company'],self.selected['room'],self.compose.toPlainText(),self.files,self.reply_to)
        except Exception as e:self.status.setText('پیش‌نویس ذخیره نشد: '+str(e))
    def choose_room(self,index):
        if hasattr(self,'compose'):self.save_draft()
        self.thread=None;self.reply_to=None;super().choose_room(index)
        if not hasattr(self,'search') or not self.selected:return
        self.search.clear();self.filter.setCurrentIndex(0);self.back_thread.hide();self.reply_label.clear();self._last_render=None
        try:
            self.ensure_delivery();draft=self.delivery.draft(self.selected['company'],self.selected['room']) if self.delivery else {};self._draft_loading=True;self.compose.setPlainText(draft.get('text',''));self.files=draft.get('files',[]);self.reply_to=draft.get('reply_to');self.attached.setText('، '.join(f['name'] for f in self.files));self._draft_loading=False
        except Exception as e:self._draft_loading=False;self.status.setText(str(e))
    def poll(self):
        if self.busy or self.owner._locking or self.owner._exit_pending or self.owner._exit_approved:return
        try:self.ensure_delivery()
        except Exception as e:self.status.setText(str(e))
        if self.delivery and self.delivery.pending() and self.client():self.flush();return
        if hasattr(self,'search') and (self.search.text() or self.thread or self.filter.currentData()):
            if not self.client() or self.owner._locking:return
            s=copy.deepcopy(self.selected);after=self.owner.data.get('chat_cursor',0);q=self.search.text();thread=self.thread;mode=self.filter.currentData();self._history=True
            self.run(lambda c:(c.request('chat/updates',after=after),c.request('chat/messages',company=s['company'],room=s['room'],q=q,thread=thread,saved='1' if mode=='saved' else '',pinned='1' if mode=='pinned' else '') if s and self.isVisible() else None,s),self.receive);return
        super().poll()
    def render(self,data,older=False):
        stamp=json.dumps(data['items'],sort_keys=True,ensure_ascii=False)
        if not older and stamp==self._last_render:return
        self._last_render=stamp;super().render(data,older)
    def bubble(self,m):
        frame=super().bubble(m);panel=next((frame.layout().itemAt(i).widget() for i in range(frame.layout().count()) if frame.layout().itemAt(i).widget()),None)
        if panel and not m['deleted']:
            lay=panel.layout()
            if m.get('reply_to'):q=QLabel('↪ '+m.get('reply_excerpt',''));q.setTextFormat(Qt.PlainText);q.setWordWrap(True);lay.insertWidget(1,q)
            row=frame.message_actions;button=QPushButton('...');button.setAccessibleName('گزینه‌های پیام');button.setToolTip('گزینه‌های پیام');button.setFixedSize(34,28);menu=QMenu(button)
            for title,fn in [('پاسخ',lambda:self.reply(m)),('بحث '+fa(m.get('reply_count',0)),lambda:self.open_thread(m)),('ذخیره‌شده' if m.get('saved') else 'ذخیره',lambda:self.message_action(m['id'],'save')),('برداشتن سنجاق' if m.get('pinned') else 'سنجاق',lambda:self.message_action(m['id'],'pin')),('ساخت کار',lambda:self.task(m)),('افزودن یادآور به تقویم',lambda:self.remind(m))]:menu.addAction(title,fn)
            if m.get('can_delete'):
                for old in panel.findChildren(QPushButton):
                    if old.text()=='حذف برای همه':old.hide()
                menu.addAction('حذف برای همه',lambda:self.delete(m['id']))
            button.message_menu=menu;button.clicked.connect(lambda checked=False:menu.exec(button.mapToGlobal(button.rect().bottomLeft())));row.addWidget(button)
            frame.setContextMenuPolicy(Qt.CustomContextMenu);frame.customContextMenuRequested.connect(lambda point:menu.exec(frame.mapToGlobal(point)))
        return frame
    def reply(self,m):self.reply_to=m['id'];self.reply_label.setText('پاسخ به '+m['person']['fullname']+' · '+m['text'][:80]);self.compose.setFocus();self.save_draft()
    def cancel_reply(self):self.reply_to=None;self.reply_label.clear();self.save_draft()
    def open_thread(self,m):self.thread=m.get('thread_root') or m['id'];self.back_thread.show();self.filter_changed();self.reply(m)
    def close_thread(self):self.thread=None;self.back_thread.hide();self.cancel_reply();self.filter_changed()
    def filter_changed(self,*_):
        if hasattr(self,'filter_timer'):self.filter_timer.start()
    def load_filtered(self):
        if not self.selected or self.busy:return
        s=copy.deepcopy(self.selected);q=self.search.text();thread=self.thread;mode=self.filter.currentData();self._history=bool(q or thread or mode)
        self.run(lambda c:c.request('chat/messages',company=s['company'],room=s['room'],q=q,thread=thread,saved='1' if mode=='saved' else '',pinned='1' if mode=='pinned' else ''),lambda data:self.render(data))
    def older(self):
        if not self.messages or not self.selected:return
        s=self.selected;q=self.search.text();thread=self.thread;mode=self.filter.currentData();before=self.messages[0]['seq'];self._history=True;self.run(lambda c:c.request('chat/messages',company=s['company'],room=s['room'],before=before,q=q,thread=thread,saved='1' if mode=='saved' else '',pinned='1' if mode=='pinned' else ''),lambda d:self.render(d,True))
    def mention(self):
        if not hasattr(self,'members') or not self.selected:return
        # Usernames are public only within the current authorized company.
        users={u['id']:u for u in self.owner.org.people};people=[(m,users.get(m['id'])) for m in self.members if users.get(m['id'])];d=QDialog(self);d.setWindowTitle('اشاره به عضو');v=QVBoxLayout(d);lst=QListWidget();lst.addItems([m['fullname']+' · @'+u['username'] for m,u in people]);v.addWidget(lst)
        def selected(item):
            i=lst.row(item)
            if i>=0:self.compose.insertPlainText('@'+people[i][1]['username']+' ');d.accept()
        lst.itemActivated.connect(selected);d.exec()
    def reading(self):
        return not (self.thread or hasattr(self,'search') and (self.search.text() or self.filter.currentData())) and super().reading()
    def new_saved_chat(self):
        if not self.client():return
        def opened(entry):
            user=(self.owner.session_user or {}).get('id','')
            self.owner.data.setdefault('settings',{}).setdefault('explicit_saved_chat',{})[user]=[entry['company'],entry['room']]
            self.owner.persist()
            self.save_draft();self.selected=entry;self.messages=[];self._last_render=None;self.clear_bubbles();self.title.setText(entry['title']);self.poll()
        self.run(lambda c:c.request('workspace/saved-chat',{}),opened)
    def new_direct(self):
        if not self.client():return
        d=QDialog(self);d.setWindowTitle('گفتگوی شخصی');v=QVBoxLayout(d);company=QComboBox();company.addItem('همکاران','__shared_chat__');company.hide()
        people=QListWidget();v.addWidget(people);state=QLabel();v.addWidget(state)
        def loaded(rows):
            people.clear()
            from PySide6.QtWidgets import QListWidgetItem
            for u in rows:item=QListWidgetItem(u['fullname']+' · '+u['username']);item.setData(Qt.UserRole,u['id']);people.addItem(item)
        def load_people():
            if company.currentData():self.run(lambda c:c.request('workspace/direct',company=company.currentData()),loaded)
        def select(item):
            co=company.currentData();person=item.data(Qt.UserRole);d.accept()
            def opened(entry):
                self.save_draft();self._draft_loading=True;self.compose.clear();self.files=[];self.attached.clear();self.reply_to=None;self.thread=None;self._draft_loading=False;self.selected=entry;self.title.setText(entry.get('display_title') or entry['title'].removeprefix('شخصی · '));self.messages=[];self._last_render=None;self.clear_bubbles();self.poll()
            self.run(lambda c:c.request('workspace/direct',dict(company=co,person=person)),opened)
        company.currentIndexChanged.connect(load_people);people.itemActivated.connect(select);v.addWidget(QLabel('فقط دو عضو گفتگو به پیام‌ها و پیوست‌های آن دسترسی دارند.'));QTimer.singleShot(0,load_people);d.exec()

    def task(self,m):
        from workspace_actions import task_draft
        task_draft(self.owner,m['text'].splitlines()[0] if m['text'] else 'پیگیری پیوست',m['text'],m)
    def remind(self,message):
        from ui_permissions import gate
        if not gate(self.owner,'calendar','create'):return
        from app import EventDialog
        from storage import new_event
        dialog=EventDialog(self.owner,self.owner.data['companies'],company='شخصی');body=message.get('text','');dialog.title.setText((body.splitlines()[0] if body else 'پیگیری پیام')[:150]);dialog.notes.setPlainText(body[:3000]);dialog.when.clear();dialog.when.setPlaceholderText('تاریخ یادآور را انتخاب کنید')
        if dialog.exec()!=QDialog.Accepted:return
        p=dialog.payload;event=new_event(p['company'],p['title'],p['date_jalali'],p['notes'],p['priority'],p['recurrence'],p['lead_days']);event.update(category=p['category'],reminder_custom=p['reminder_custom'],reminder_group=p['reminder_group'],source_chat_id=message.get('id',''))
        self.owner.events.append(event)
        try:self.owner.persist();self.owner.refresh();self.status.setText('یادآور در تقویم ثبت شد.')
        except Exception as exc:self.owner.events.remove(event);QMessageBox.warning(self,'ثبت یادآور',str(exc))
    def open_notification(self,target):
        self.owner.tabs.setCurrentWidget(self);message=target['message'];company=target['company'];room=target['room']
        if getattr(self.owner,'ensure_react_view',None):self.owner.ensure_react_view(self)
        if getattr(self,'react_view',None):self.react_view.bridge.open_target(company,room,message.get('thread_root') or message['id'],message['id'])
        def display(rooms):
            self.rooms=rooms;entry=next((r for r in rooms if r['company']==company and r['room']==room),None)
            if not entry:self.status.setText('گفتگو دیگر در دسترس نیست.');return
            self.save_draft();self.selected=entry;self.title.setText(entry.get('display_title') or entry['title']);self.messages=[];self._last_render=None;self.thread=message.get('thread_root') or message['id'];self.back_thread.show();self.search.clear();self.filter.setCurrentIndex(0);self.status.setText('پیام مرتبط با اعلان');self.load_filtered()
        self.run(lambda c:c.request('chat/rooms'),display)
    def attach(self):super().attach();self.save_draft()
    def clear_files(self):super().clear_files();self.save_draft()
    def send(self):
        if not self.selected or not (self.compose.toPlainText().strip() or self.files):return
        try:
            self.ensure_delivery()
            if not self.delivery:raise ValueError('حساب برای صف ارسال مشخص نیست.')
            s=self.selected;body=dict(company=s['company'],room=s['room'],text=self.compose.toPlainText(),attachments=[{k:v for k,v in f.items() if k!='size'} for f in self.files],reply_to=self.reply_to);self.delivery.enqueue(body);self._send_waiting=True;self._draft_loading=True;self.compose.clear();self.files=[];self.attached.clear();self.reply_to=None;self.reply_label.clear();self._draft_loading=False;self.save_draft();self.show_queue_count();self.flush()
        except Exception as e:self.status.setText('پیام در کادر باقی ماند: '+str(e))
    def flush(self):
        if self.busy or not self.client() or not self.delivery:return
        pending=self.delivery.pending()
        if not pending:return
        self._send_waiting=False
        payload=copy.deepcopy(pending['payload']);id=payload['request_id'];delivery=self.delivery
        def sent(_):delivery.acknowledge(id);self.show_queue_count();self.changed();QTimer.singleShot(100,self.poll)
        def work(c):
            try:return c.request('chat/messages',payload)
            except Exception as e:delivery.failed(id,e,getattr(e,'status',503) not in (429,500,502,503,504));raise
        self.run(work,sent)
    def show_queue_count(self):
        if hasattr(self,'outbox_label'):self.outbox_label.setText('صف ارسال · '+fa(len(self.delivery.value['outbox']) if self.delivery else 0))
    def show_outbox(self):
        self.ensure_delivery();d=QDialog(self);d.setWindowTitle('صف ارسال؛ پیام‌ها تا دریافت تأیید مرکز نگه‌داری می‌شوند');d.resize(570,380);v=QVBoxLayout(d);lst=QListWidget();v.addWidget(lst);items=list(self.delivery.value['outbox']) if self.delivery else []
        for x in items:lst.addItem(('نیازمند بررسی' if x['status']=='needs_review' else 'در انتظار ارسال')+' · '+x['payload']['text'][:80]+'\n'+x['error'])
        row=QHBoxLayout()
        def retry():
            i=lst.currentRow()
            if i>=0:self.delivery.retry(items[i]['payload']['request_id']);d.accept();self.flush()
        def remove():
            i=lst.currentRow()
            if i>=0 and QMessageBox.question(d,'حذف از صف','ارسال این پیام لغو شود؟',QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:self.delivery.acknowledge(items[i]['payload']['request_id']);d.accept();self.show_queue_count()
        for title,fn in [('تلاش دوباره',retry),('لغو ارسال',remove),('بستن',d.reject)]:b=QPushButton(title);b.clicked.connect(fn);row.addWidget(b)
        v.addLayout(row);d.exec()
