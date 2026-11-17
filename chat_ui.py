"""A room list, message bubbles, emoji, attachments, polls and meetings."""
import base64,threading,copy
from pathlib import Path
from datetime import datetime,timezone,timedelta
from PySide6.QtCore import Qt,QObject,Signal,QTimer,QTime
from PySide6.QtGui import QPixmap,QColor,QFont,QPainter,QPainterPath,QIcon
from PySide6.QtWidgets import (QWidget,QFrame,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QListWidget,QListWidgetItem,QScrollArea,QPlainTextEdit,QDialog,QDialogButtonBox,QFormLayout,QLineEdit,QComboBox,QTimeEdit,QCheckBox,QMessageBox,QFileDialog,QMenu,QSplitter,QBoxLayout,QInputDialog)
from storage import fa,today_j,jformat,parse_j,normalize
from ui_icons import iconize
from appearance import contrast

class Bridge(QObject):done=Signal(object,object)

def room_labels(rooms):
    """Disambiguate repeated names before a user selects a message destination."""
    from collections import Counter
    names=[r.get('display_title') or r['title'] for r in rooms];keys=[normalize(name).strip().casefold() for name in names];counts=Counter(keys);used=set();result=[]
    for i,(name,key) in enumerate(zip(names,keys)):
        candidate=name+' · '+fa(i+1) if counts[key]>1 else name
        while candidate in used:candidate+=' · '+fa(i+1)
        used.add(candidate);result.append(candidate)
    return result

def circular_avatar(pix,size):
    from PySide6.QtCore import QRectF
    if pix.isNull():return QPixmap()
    result=QPixmap(size,size);result.fill(Qt.transparent);p=QPainter(result);p.setRenderHint(QPainter.Antialiasing);path=QPainterPath();path.addEllipse(QRectF(0,0,size,size));p.setClipPath(path)
    scaled=pix.scaled(size,size,Qt.KeepAspectRatioByExpanding,Qt.SmoothTransformation);p.drawPixmap((size-scaled.width())//2,(size-scaled.height())//2,scaled);p.end();return result

def avatar_label(data,name,size=34):
    label=QLabel();label.setFixedSize(size,size);label.setAlignment(Qt.AlignCenter);label.setStyleSheet('background:#E4EBF2;color:#19354B;border-radius:'+str(size//2)+'px;')
    pix=QPixmap()
    if data:
        try:pix.loadFromData(base64.b64decode(data))
        except (ValueError,TypeError):pass
    if not pix.isNull():label.setPixmap(circular_avatar(pix,size))
    else:label.setText((name or 'ک')[:1]);label.setFont(QFont('Vazirmatn',max(11,size//3)))
    label.setToolTip(name);return label

class MessageDialog(QDialog):
    def __init__(self,kind,parent=None):
        super().__init__(parent);self.kind=kind;self.setLayoutDirection(Qt.RightToLeft);self.setWindowTitle('نظرسنجی' if kind=='poll' else 'جلسه تازه');self.resize(480,450);v=QVBoxLayout(self);f=QFormLayout();v.addLayout(f);self.title=QLineEdit();f.addRow('پرسش' if kind=='poll' else 'موضوع',self.title);self.options=QPlainTextEdit();self.options.setPlaceholderText('هر گزینه در یک خط');self.day=QLineEdit(jformat(today_j()));self.time=QTimeEdit(QTime.currentTime());self.time.setDisplayFormat('HH:mm');self.location=QLineEdit()
        if kind=='poll':v.addWidget(self.options)
        else:
            date_row=QHBoxLayout();date_row.addWidget(self.day);pick=QPushButton();iconize(pick,'calendar','انتخاب تاریخ');pick.clicked.connect(self.pick_date);date_row.addWidget(pick);f.addRow('تاریخ شمسی',date_row);f.addRow('ساعت تهران',self.time);f.addRow('محل / پیوند جلسه',self.location)
        self.error=QLabel();self.error.setWordWrap(True);v.addWidget(self.error);b=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);b.button(QDialogButtonBox.Ok).setText('ارسال');b.button(QDialogButtonBox.Cancel).setText('انصراف');b.accepted.connect(self.validate);b.rejected.connect(self.reject);v.addWidget(b)
    def pick_date(self):
        from report_ui import JalaliDatePicker
        picker=JalaliDatePicker(self.day.text(),self)
        if picker.exec()==QDialog.Accepted:self.day.setText(picker.value())
    def validate(self):
        try:
            if not self.title.text().strip():raise ValueError('موضوع را وارد کنید.')
            if self.kind=='poll':
                options=[x.strip() for x in self.options.toPlainText().splitlines() if x.strip()]
                if not 2<=len(options)<=10 or len(set(options))!=len(options):raise ValueError('۲ تا ۱۰ گزینه متفاوت بنویسید.')
                self.payload=dict(options=options)
            else:
                day=parse_j(self.day.text()).togregorian();tm=self.time.time();when=datetime(day.year,day.month,day.day,tm.hour(),tm.minute(),tzinfo=timezone(timedelta(hours=3,minutes=30)));self.payload=dict(at=when.isoformat(),location=self.location.text())
            self.accept()
        except Exception as e:self.error.setText(str(e))

class ScheduleDialog(QDialog):
    def __init__(self,parent=None):
        import jdatetime
        super().__init__(parent);self.setLayoutDirection(Qt.RightToLeft);self.setWindowTitle('زمان ارسال پیام');self.setLayout(QVBoxLayout());form=QFormLayout();self.layout().addLayout(form);row=QHBoxLayout();default=datetime.now(timezone(timedelta(hours=3,minutes=30)))+timedelta(hours=1);self.day=QLineEdit(jdatetime.date.fromgregorian(date=default.date()).strftime('%Y/%m/%d'));self.day.setLayoutDirection(Qt.LeftToRight);row.addWidget(self.day);picker=QPushButton();iconize(picker,'calendar','انتخاب تاریخ شمسی');picker.clicked.connect(self.pick_date);row.addWidget(picker);form.addRow('تاریخ شمسی',row);self.time=QTimeEdit(QTime(default.hour,default.minute));self.time.setLayoutDirection(Qt.LeftToRight);self.time.setDisplayFormat('HH:mm');form.addRow('ساعت تهران',self.time);self.error=QLabel();self.error.setWordWrap(True);self.layout().addWidget(self.error);buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('زمان‌بندی');buttons.button(QDialogButtonBox.Cancel).setText('انصراف');buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);self.layout().addWidget(buttons)
    def pick_date(self):
        from report_ui import JalaliDatePicker
        picker=JalaliDatePicker(self.day.text(),self)
        if picker.exec()==QDialog.Accepted:self.day.setText(picker.value())
    def validate(self):
        try:
            day=parse_j(self.day.text()).togregorian();tm=self.time.time();when=datetime(day.year,day.month,day.day,tm.hour(),tm.minute(),tzinfo=timezone(timedelta(hours=3,minutes=30)))
            if when<=datetime.now(timezone.utc):raise ValueError('زمان ارسال باید در آینده باشد.')
            self.due_at=when.isoformat();self.accept()
        except ValueError as exc:self.error.setText(str(exc))

class ChatPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.setObjectName('ChatPanel');self.owner=owner;self._chat_theme_key=None;self._chat_actions=[];self.busy=False;self.signals=Bridge();self.signals.done.connect(self.finished);self.rooms=[];self.selected=None;self.messages=[];self.files=[];self._notification_pending=set();self._meeting_pending=set();self._loaded=False;self._history=False
        v=QVBoxLayout(self);v.setContentsMargins(14,12,14,12);split=QSplitter(Qt.Horizontal);v.addWidget(split,1);aside=QWidget();a=QVBoxLayout(aside);a.setContentsMargins(0,0,0,0);headrow=QHBoxLayout();head=QLabel('گفتگوها');head.setObjectName('Hero');headrow.addWidget(head,1);new_group=QPushButton('+');new_group.setAccessibleName('گفتگوی جدید');new_group.setToolTip('گفتگوی جدید');new_group.setFixedSize(60,38);new_group.setProperty('flowNative',True);new_group.clicked.connect(self.create_group);self.new_group_button=new_group;headrow.addWidget(new_group);a.addLayout(headrow);self.room_search=QLineEdit();self.room_search.setPlaceholderText('جستجوی گفتگوها');self.room_search.setClearButtonEnabled(True);self.room_search.textChanged.connect(self.filter_rooms);a.addWidget(self.room_search);self.room_list=QListWidget();self.room_list.setObjectName('ChatRooms');self.room_list.setMinimumWidth(190);self.room_list.setIconSize(__import__('PySide6.QtCore',fromlist=['QSize']).QSize(38,38));self.room_list.currentRowChanged.connect(self.choose_room);a.addWidget(self.room_list);split.addWidget(aside)
        main=QWidget();box=QVBoxLayout(main);box.setContentsMargins(8,0,0,0);top=QHBoxLayout();self.header_layout=top;self.room_avatar=avatar_label('','گ',38);top.addWidget(self.room_avatar);self.title=QLabel('یک گفتگو را انتخاب کنید');self.title.setObjectName('Hero');top.addWidget(self.title,1);self.mute=QCheckBox('بی‌صدا');self.mute.toggled.connect(self.set_mute);top.addWidget(self.mute);members=QPushButton('اعضا');members.clicked.connect(self.show_members);top.addWidget(members);box.addLayout(top);self.status=QLabel('');self.status.setWordWrap(True);box.addWidget(self.status)
        self.area=QScrollArea();self.area.setObjectName('ChatHistory');self.area.setWidgetResizable(True);self.shell=QWidget();self.shell.setObjectName('ChatCanvas');self.bubbles=QVBoxLayout(self.shell);self.bubbles.setAlignment(Qt.AlignTop);self.bubbles.setSpacing(7);self.area.setWidget(self.shell);box.addWidget(self.area,1)
        self.attached=QLabel();self.attached.setWordWrap(True);box.addWidget(self.attached);composer_card=QFrame();composer_card.setObjectName('ChatComposerCard');composer_layout=QVBoxLayout(composer_card);composer_layout.setContentsMargins(8,6,8,6);composer_layout.setSpacing(2);box.addWidget(composer_card);row=QHBoxLayout();self.compose=QPlainTextEdit();self.compose.setObjectName('ChatComposer');self.compose.setPlaceholderText('پیام بنویسید…');self.compose.setMaximumHeight(52);self.compose.setMinimumHeight(44);row.addWidget(self.compose,1);send=QPushButton('ارسال');send.setObjectName('Primary');send.clicked.connect(self.send);row.addWidget(send);actions=QHBoxLayout();self.actions_layout=actions
        for title,key,fn in [('پیوست فایل یا عکس','attachment',self.attach),('اموجی','emoji',self.emoji),('نظرسنجی','poll',lambda:self.special('poll')),('جلسه','meeting',lambda:self.special('meeting')),('زمان‌بندی ارسال پیام','schedule',self.schedule_message),('پیام‌های زمان‌بندی‌شده','schedule_list',self.scheduled_messages),('پاک کردن پیوست‌ها','delete',self.clear_files)]:b=QPushButton(title);iconize(b,key,title);b.clicked.connect(fn);actions.addWidget(b);self._chat_actions.append((b,key))
        row.insertLayout(0,actions);composer_layout.addLayout(row);split.addWidget(main);split.setStretchFactor(0,0);split.setStretchFactor(1,1);split.setSizes([270,760]);self.timer=QTimer(self);self.timer.setInterval(30000);self.timer.timeout.connect(self.poll);self.timer.start();QTimer.singleShot(1000,self.poll)
    def filter_rooms(self,*_):
        query=normalize(self.room_search.text()).casefold().strip()
        for i in range(self.room_list.count()):
            item=self.room_list.item(i);item.setHidden(bool(query and query not in normalize(item.text()).casefold()))
    def apply_theme(self):
        from appearance import palette_for
        from ui_icons import symbol
        settings=self.owner.data['settings'];key=(settings.get('theme_preset','default'),settings.get('theme','light'))
        if key==self._chat_theme_key:return
        self._chat_theme_key=key;c=palette_for(settings)
        c.update(dict(bg='#111111',panel='#191919',text='#f2f2f2',border='#343434',selected='#303030') if settings.get('theme')=='dark' else dict(bg='#ffffff',panel='#ffffff',text='#1d2228',border='#e5e7eb',selected='#edf1f4'))
        self.setStyleSheet('''QWidget#ChatPanel, QWidget#ChatCanvas {background:%s;}
            QListWidget#ChatRooms {background:%s;color:%s;border:1px solid %s;border-radius:6px;padding:3px;outline:0;}
            QListWidget#ChatRooms::item {padding:12px 9px;border-radius:7px;margin:1px;}
            QListWidget#ChatRooms::item:selected {background:%s;color:%s;}
            QFrame#ChatComposerCard {background:%s;border:1px solid %s;border-radius:6px;}
            QPlainTextEdit#ChatComposer {background:%s;color:%s;border:1px solid %s;border-radius:6px;padding:8px;}
            QScrollArea#ChatHistory {background:%s;border:0;}'''%(c['bg'],c['panel'],c['text'],c['border'],c['selected'],c['text'],c['panel'],c['border'],c['panel'],c['text'],c['border'],c['bg']))
        for button,icon in self._chat_actions:
            if icon in ('attachment','emoji','poll','meeting','schedule','schedule_list'):button.setIcon(symbol(icon,c['text']))
    def client(self):return getattr(self.owner.org,'client',None)
    def run(self,fn,done):
        if self.busy or not self.client():return False
        from org_client import Client
        original=self.client();client=Client(original.url,original.session.verify if isinstance(original.session.verify,str) else None,getattr(original,'fingerprint',None));client.token=original.token;client.user=original.user;self.busy=True;self.callback=done
        def work():
            try:self.signals.done.emit(fn(client),None)
            except Exception as e:self.signals.done.emit(None,e)
            finally:client.session.close()
        threading.Thread(target=work,daemon=True).start();return True
    def finished(self,result,error):
        self.busy=False;done=self.callback;self.callback=None
        if error:
            self.status.setText(str(error))
            if getattr(error,'status',None)==401:QTimer.singleShot(0,self.owner.lock_session)
            return
        self.status.clear();done(result)
    def poll(self):
        if not self.client() or self.owner._locking:return
        selection=copy.deepcopy(self.selected);after=self.owner.data.get('chat_cursor',0);visible=self.isVisible() and selection and not self._history
        def fetch(c):
            updates=c.request('chat/updates',after=after);data=c.request('chat/messages',company=selection['company'],room=selection['room']) if visible else None
            return updates,data,selection
        self.run(fetch,self.receive)
    def receive(self,value):
        updates,data,selection=value
        user=(self.owner.session_user or {}).get('id','')
        def visible_room(r):
            name=normalize(r.get('title','')).replace('\u200c',' ').replace(' ','')
            saved=r.get('saved') or str(r.get('room','')).startswith('saved:') or 'پیامهایذخیرهشده' in name
            return not saved or (r.get('company')=='__shared_chat__' and r.get('room')=='saved:'+user)
        self.rooms=[r for r in updates['rooms'] if visible_room(r)];old=(self.selected['company'],self.selected['room']) if self.selected else None;room_scroll=self.room_list.verticalScrollBar().value();self.room_list.blockSignals(True);self.room_list.clear()
        for r,name in zip(self.rooms,room_labels(self.rooms)):
            last=(r.get('last') or {}).get('text','').replace('\n',' ').strip();preview=(last[:45]+'…') if len(last)>45 else last;item=QListWidgetItem(name+('  '+fa(r['unread']) if r['unread'] else '')+('  ◌' if r['muted'] else '')+('\n'+preview if preview else ''));pix=QPixmap()
            if r.get('avatar'):
                try:pix.loadFromData(base64.b64decode(r['avatar']))
                except (ValueError,TypeError):pass
            if not pix.isNull():item.setIcon(QIcon(circular_avatar(pix,32)))
            else:
                from ui_icons import symbol
                key='company' if r.get('room')=='managers' else 'check' if r.get('room')=='staff' else 'chat';item.setIcon(symbol(key,'#518BAA'))
            item.setData(Qt.UserRole,r);self.room_list.addItem(item)
        self.filter_rooms();index=next((i for i,r in enumerate(self.rooms) if (r['company'],r['room'])==old),-1);self.room_list.setCurrentRow(index);self.room_list.verticalScrollBar().setValue(room_scroll);self.room_list.blockSignals(False)
        if index>=0:
            self.selected=self.rooms[index];self.mute.blockSignals(True);self.mute.setChecked(self.selected['muted']);self.mute.blockSignals(False)
        elif self.selected and selection and (selection['company'],selection['room'])==old:
            # This response actually checked the current room: if access was
            # revoked, clear its cached messages. An older response for a
            # previous selection must never replace a newly opened dialogue.
            self.selected=None;self.messages=[];self.clear_bubbles()
            if self.rooms:self.room_list.setCurrentRow(0)
        elif self.rooms and self.selected is None:self.room_list.setCurrentRow(0)
        if data and self.selected and (selection['company'],selection['room'])==(self.selected['company'],self.selected['room']):self.render(data);QTimer.singleShot(30,self.mark_visible_read)
        current=(self.selected['company'],self.selected['room']) if self.reading() and self.selected else None
        for m in updates['items'] if self.owner.data.get('preferences',{}).get('chat_notifications',True) else []:
            if (m['company'],m['room'])==current:continue
            self.owner.popup(m['author']+'\n'+m['text'],title=m['company_name']+' · '+m['title'],company=m['company_name'],on_click=lambda entry=m:self.open_room(entry))
        if self.owner.data.get('chat_cursor')!=updates['cursor']:self.owner.data['chat_cursor']=updates['cursor'];self.owner.persist()
        for m in updates['meetings'] if self.owner.data.get('preferences',{}).get('chat_notifications',True) else []:
            if m['id'] in self._meeting_pending:continue
            self._meeting_pending.add(m['id']);self.owner.popup(m['text'],title='زمان جلسه · '+m['company_name'],company=m['company_name'],on_click=lambda entry=m:self.open_room(entry),on_shown=lambda entry=m:self.mark_meeting(entry))
        self._loaded=True
    def reading(self):
        return self.isVisible() and self.owner.isActiveWindow() and not self.owner.isMinimized() and self.area.verticalScrollBar().value()>=self.area.verticalScrollBar().maximum()-25
    def mark_visible_read(self):
        if not self.reading() or not self.selected or not self.messages:return
        selection=self.selected;seq=self.messages[-1]['seq'];key=(selection['company'],selection['room'],seq)
        if getattr(self,'_read_key',None)==key:return
        self.run(lambda c:c.request('chat/state',dict(company=selection['company'],room=selection['room'],seq=seq)),lambda _:setattr(self,'_read_key',key))
    def mark_meeting(self,m):
        # Dedicated client: queued popups may be shown during a regular sync.
        original=self.client()
        if not original:return
        from org_client import Client
        def work():
            c=Client(original.url,original.session.verify if isinstance(original.session.verify,str) else None,getattr(original,'fingerprint',None));c.token=original.token
            try:c.request('chat/action',dict(id=m['id'],action='meeting_notified'))
            except Exception:self._meeting_pending.discard(m['id'])
            finally:c.session.close()
        threading.Thread(target=work,daemon=True).start()
    def choose_room(self,index):
        if index<0 or index>=len(self.rooms):return
        self.selected=self.rooms[index];self._history=False;self.messages=[];self.title.setText(self.selected.get('display_title') or (self.selected['title'].removeprefix('شخصی · ') if self.selected.get('direct') else self.selected['title']));self.room_avatar.setPixmap(QPixmap());avatar=QPixmap()
        try:avatar.loadFromData(base64.b64decode(self.selected.get('avatar') or ''))
        except (ValueError,TypeError):pass
        if not avatar.isNull():self.room_avatar.setPixmap(circular_avatar(avatar,38))
        else:self.room_avatar.setText(self.title.text()[:1])
        self.mute.blockSignals(True);self.mute.setChecked(self.selected['muted']);self.mute.blockSignals(False);self.clear_bubbles();QTimer.singleShot(0,self.poll)
    def open_room(self,entry):
        self.owner.show_main();self.owner.tabs.setCurrentWidget(self)
        if getattr(self.owner,'ensure_react_view',None):self.owner.ensure_react_view(self)
        if getattr(self,'react_view',None):self.react_view.bridge.open_target(entry['company'],entry['room'],entry.get('thread_root'),entry.get('id'))
        index=next((i for i,r in enumerate(self.rooms) if r['company']==entry['company'] and r['room']==entry['room']),-1)
        if index>=0:self.room_list.setCurrentRow(index)
    def clear_bubbles(self):
        while self.bubbles.count():
            item=self.bubbles.takeAt(0);w=item.widget()
            if w:w.hide();w.deleteLater()
    def render(self,data,older=False):
        scroll=self.area.verticalScrollBar();position=scroll.value();old_max=scroll.maximum();at_end=position>=old_max-25;self.messages=(data['items']+self.messages) if older else data['items'];self.members=data['members'];self.clear_bubbles();self._scroll_generation=getattr(self,'_scroll_generation',0)+1;generation=self._scroll_generation;selected=(self.selected['company'],self.selected['room']) if self.selected else None
        if data['has_more']:
            b=QPushButton('پیام‌های پیشین');b.clicked.connect(self.older);self.bubbles.addWidget(b)
        for m in self.messages:self.bubbles.addWidget(self.bubble(m))
        self.bubbles.addStretch();self.bubbles.activate();self.shell.adjustSize()
        def restore_scroll():
            current=(self.selected['company'],self.selected['room']) if self.selected else None
            if generation!=self._scroll_generation or selected!=current:return
            target=position+max(0,scroll.maximum()-old_max) if older else scroll.maximum() if at_end else position
            scroll.setValue(min(scroll.maximum(),target))
        # Let the layout calculate the new message heights before restoring.
        QTimer.singleShot(40,restore_scroll)
    def bubble(self,m):
        frame=QFrame();frame.setLayoutDirection(Qt.LeftToRight);line=QHBoxLayout(frame);line.setDirection(QBoxLayout.LeftToRight);line.setContentsMargins(4,0,4,0);me=self.client() and m['author']==self.client().user['id'];panel=QFrame();panel.setLayoutDirection(Qt.RightToLeft);p=QVBoxLayout(panel);p.setContentsMargins(10,7,10,7);p.setSpacing(4);color=m['person']['color'];fg=max(('#142C42','#FFFFFF'),key=lambda x:contrast(x,color));panel.setStyleSheet('QFrame{background:'+color+';border-radius:16px;} QLabel{color:'+fg+';background:transparent;} QPushButton{color:'+fg+';background:transparent;border:1px solid '+fg+';padding:4px 7px;}');head=QHBoxLayout();head.addWidget(avatar_label(m['person']['avatar'],m['person']['fullname'],28));name=QLabel(m['person']['fullname']);name.setTextFormat(Qt.PlainText);head.addWidget(name);head.addStretch();stamp=datetime.fromisoformat(m['created']).astimezone(timezone(timedelta(hours=3,minutes=30)));p.addLayout(head);body=QLabel(m['text']);body.setWordWrap(True);body.setTextFormat(Qt.PlainText);body.setTextInteractionFlags(Qt.TextSelectableByMouse);p.addWidget(body)
        if not m['deleted']:
            if m['kind']=='meeting':
                t=datetime.fromisoformat(m['payload']['at']).astimezone(timezone(timedelta(hours=3,minutes=30)));import jdatetime
                l=QLabel(jformat(jdatetime.date.fromgregorian(date=t.date()))+' · '+fa(t.strftime('%H:%M'))+'\n'+m['payload'].get('location',''));l.setTextFormat(Qt.PlainText);l.setWordWrap(True);p.addWidget(l)
            if m['kind']=='poll':
                for i,option in enumerate(m['payload']['options']):
                    b=QPushButton(('✓ ' if m.get('my_vote')==i else '')+option+'  '+fa(m['votes'][i]));b.clicked.connect(lambda checked=False,id=m['id'],i=i:self.message_action(id,'vote',i));p.addWidget(b)
            for file in m['files']:
                b=QPushButton('▧ '+file['name']+'  · '+fa(round(file['size']/1024))+' KB');b.clicked.connect(lambda checked=False,f=file:self.download(f));p.addWidget(b)
            actions=QHBoxLayout();frame.message_actions=actions;like=QPushButton(fa(len(m['likes'])) if m['likes'] else '');from ui_icons import symbol;like.setIcon(symbol('like',fg));like.setStyleSheet('QPushButton{border:0;border-radius:10px;padding:2px 5px;background:rgba(128,128,128,35);color:'+fg+';}');like.setToolTip('، '.join(u['fullname'] for u in m['likes']) or 'پسندیدن');like.clicked.connect(lambda:self.message_action(m['id'],'like'));actions.addWidget(like);seen=QPushButton(fa(len(m['seen_by'])) if m['seen_by'] else '');seen.setIcon(symbol('seen',fg));seen.setStyleSheet('QPushButton{border:0;border-radius:10px;padding:2px 5px;background:rgba(128,128,128,35);color:'+fg+';}');seen.setToolTip('، '.join(u['fullname'] for u in m['seen_by']) or 'هنوز دیده نشده');seen.clicked.connect(lambda:QMessageBox.information(self,'دیده‌شده توسط','\n'.join(u['fullname'] for u in m['seen_by']) or 'هنوز دیده نشده'));actions.addWidget(seen);actions.addStretch();time_label=QLabel(fa(stamp.strftime('%H:%M')));time_label.setToolTip(fa(stamp.strftime('%Y/%m/%d %H:%M')));time_label.setStyleSheet('font-size:10px;');actions.addWidget(time_label)
            if m['can_delete']:
                delete=QPushButton('حذف برای همه');delete.clicked.connect(lambda:self.delete(m['id']));actions.addWidget(delete)
            forward=QPushButton('↗');forward.setToolTip('ارسال به گفتگو یا پیام‌های ذخیره‌شده');forward.setAccessibleName('ارسال به گفتگو');forward.clicked.connect(lambda:self.forward_message(m));actions.addWidget(forward)
            p.addLayout(actions)
        width=max(220,min(520,body.fontMetrics().horizontalAdvance((m.get('text') or '')[:65])+75));panel.setMaximumWidth(max(width,300) if m.get('files') or m.get('kind') in ('poll','meeting') else width)
        if me:line.addStretch();line.addWidget(panel,4)
        else:line.addWidget(panel,4);line.addStretch()
        return frame
    def older(self):
        if not self.selected or not self.messages:return
        s=self.selected;before=self.messages[0]['seq'];self._history=True;self.run(lambda c:c.request('chat/messages',company=s['company'],room=s['room'],before=before),lambda d:self.render(d,True))
    def changed(self):
        self.owner.data['company_write_at']=datetime.now(timezone.utc).isoformat();self.owner.persist();self._history=False;QTimer.singleShot(0,self.poll)
    def message_action(self,id,action,option=None):self.run(lambda c:c.request('chat/action',dict(id=id,action=action,option=option)),lambda _:self.changed())
    def delete(self,id):
        if QMessageBox.question(self,'حذف پیام','این پیام برای همه اعضای گروه حذف شود؟',QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:self.message_action(id,'delete')
    def set_mute(self,value):
        if not self.selected:return
        s=self.selected
        if not self.run(lambda c:c.request('chat/state',dict(company=s['company'],room=s['room'],muted=value)),lambda _:self.poll()):self.mute.blockSignals(True);self.mute.setChecked(not value);self.mute.blockSignals(False)
    def show_members(self):
        if hasattr(self,'members'):QMessageBox.information(self,'اعضای گروه','\n'.join(x['fullname'] for x in self.members))
    def forward_message(self,message):
        choices=list(self.rooms)
        if not choices:return
        labels=room_labels(choices);selected,ok=QInputDialog.getItem(self,'ارسال پیام','مقصد',labels,0,False)
        if not ok:return
        target=choices[labels.index(selected)];body=message.get('text','') or 'پیام ارسالی'
        if message.get('kind')=='poll':body+='\n'+'\n'.join(message.get('payload',{}).get('options',[]))
        if message.get('kind')=='meeting':body+='\n'+str(message.get('payload',{}).get('at',''))
        def send(client):
            attachments=[]
            for file in message.get('files',[]):
                download=client.request('chat/file',id=file['id']);attachments.append({'name':file['name'],'data':download['data']})
            return client.request('chat/messages',dict(company=target['company'],room=target['room'],text=body,attachments=attachments))
        self.run(send,lambda _:self.changed())
    def create_group(self):
        if not self.client():return
        company='__shared_chat__'
        if not company:QMessageBox.information(self,'گروه جدید','ابتدا شرکت را انتخاب کنید.');return
        dialog=QDialog(self);dialog.setWindowTitle('گروه جدید');dialog.resize(420,500);layout=QVBoxLayout(dialog);layout.addWidget(QLabel('نام گروه'));title=QLineEdit();layout.addWidget(title)
        layout.addWidget(QLabel('شرکت مرتبط'));group_company=QComboBox();group_company.addItem('بدون شرکت');group_company.addItems(self.owner.data.get('companies',[]));layout.addWidget(group_company)
        avatar={'data':''};photo=QPushButton('انتخاب عکس گروه');layout.addWidget(photo)
        def choose_photo():
            name,_=QFileDialog.getOpenFileName(dialog,'انتخاب عکس گروه','','Images (*.png *.jpg *.jpeg *.webp)')
            if not name:return
            from PySide6.QtCore import QByteArray,QBuffer,QIODevice
            pix=QPixmap(name)
            if pix.isNull():QMessageBox.warning(dialog,'عکس گروه','تصویر قابل خواندن نیست.');return
            raw=QByteArray();buffer=QBuffer(raw);buffer.open(QIODevice.WriteOnly);pix.scaled(256,256,Qt.KeepAspectRatio,Qt.SmoothTransformation).save(buffer,'PNG');avatar['data']=base64.b64encode(bytes(raw)).decode();photo.setText('عکس انتخاب شد')
        photo.clicked.connect(choose_photo);layout.addWidget(QLabel('اعضای این گروه را انتخاب کنید'));people=QListWidget();layout.addWidget(people,1)
        try:
            from personalization_ui import request_wait
            users=request_wait(self.owner,'workspace/group-people',company=company)
        except Exception as exc:QMessageBox.warning(self,'گروه جدید',str(exc));return
        for user in users:
            item=QListWidgetItem(user['fullname']);item.setData(Qt.UserRole,user['id']);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked);people.addItem(item)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('ساخت گروه');buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()!=QDialog.Accepted:return
        members=[people.item(i).data(Qt.UserRole) for i in range(people.count()) if people.item(i).checkState()==Qt.Checked]
        if not title.text().strip():QMessageBox.warning(self,'گروه جدید','نام گروه را وارد کنید.');return
        self.run(lambda c:c.request('workspace/group',dict(company=company,title=title.text(),members=members,company_name=group_company.currentText() if group_company.currentIndex() else '',avatar=avatar['data'])),lambda _:self.changed())
    def attach(self):
        paths,_=QFileDialog.getOpenFileNames(self,'پیوست به پیام','','Files (*.png *.jpg *.jpeg *.pdf *.xlsx *.xls *.csv *.txt *.docx *.zip)')
        if not paths:return
        try:
            if len(self.files)+len(paths)>5:raise ValueError('حداکثر ۵ پیوست انتخاب کنید.')
            if sum(Path(p).stat().st_size for p in paths)+sum(f['size'] for f in self.files)>12*1024*1024:raise ValueError('مجموع پیوست‌ها حداکثر ۱۲ مگابایت باشد.')
            for path in paths:raw=Path(path).read_bytes();self.files.append(dict(name=Path(path).name,data=base64.b64encode(raw).decode(),size=len(raw)))
            self.attached.setText('، '.join(f['name'] for f in self.files))
        except Exception as e:QMessageBox.warning(self,'پیوست',str(e))
    def clear_files(self):self.files=[];self.attached.clear()
    def emoji(self):
        d=QDialog(self);d.setWindowTitle('اموجی');grid=QGridLayout(d);grid.setSpacing(4)
        for i,em in enumerate('😀 😃 😄 😁 😊 🙂 😉 😍 🥰 😎 🤔 😅 😂 🙏 👍 👎 👏 💪 ✅ ❌ ❤️ 💙 💚 💜 🎉 🎯 📌 📎 📅 🕒 💼 📊 📝 ☕ 🌹'.split()):b=QPushButton(em);b.setFixedSize(42,42);b.setFont(QFont('Segoe UI Emoji',18));b.setStyleSheet('padding:2px;');b.clicked.connect(lambda checked=False,e=em:(self.compose.insertPlainText(e),d.accept()));grid.addWidget(b,i//8,i%8)
        d.exec()
    def send(self):
        if not self.selected or not (self.compose.toPlainText().strip() or self.files):return
        s=self.selected;body=dict(company=s['company'],room=s['room'],text=self.compose.toPlainText(),attachments=[{k:v for k,v in f.items() if k!='size'} for f in self.files])
        def sent(_):self.compose.clear();self.clear_files();self.changed()
        self.run(lambda c:c.request('chat/messages',body),sent)
    def schedule_message(self):
        import uuid
        if not self.selected or not (self.compose.toPlainText().strip() or self.files):return
        if self.busy:self.status.setText('ابتدا پایان دریافت اطلاعات گفتگو را صبر کنید.');return
        dialog=ScheduleDialog(self)
        if dialog.exec()!=QDialog.Accepted:return
        room=copy.deepcopy(self.selected);files=copy.deepcopy(self.files);body=dict(company=room['company'],room=room['room'],text=self.compose.toPlainText(),due_at=dialog.due_at,request_id=uuid.uuid4().hex,attachments=[{k:v for k,v in f.items() if k!='size'} for f in files])
        def done(_):
            if self.compose.toPlainText()==body['text']:self.compose.clear()
            if self.files==files:self.clear_files()
            self.status.setText('پیام زمان‌بندی شد؛ میزبان شرکت باید روشن بماند.')
        self.run(lambda c:c.request('chat/scheduled',body),done)
    def scheduled_messages(self):
        if not self.selected:return
        room=copy.deepcopy(self.selected)
        def show(items):
            dialog=QDialog(self);dialog.setWindowTitle('پیام‌های زمان‌بندی‌شده من');dialog.setLayout(QVBoxLayout());listing=QListWidget();dialog.layout().addWidget(listing)
            for item in items:
                when=datetime.fromisoformat(item['due_at']).astimezone(timezone(timedelta(hours=3,minutes=30)));import jdatetime
                label=fa(jdatetime.date.fromgregorian(date=when.date()).strftime('%Y/%m/%d')+' '+when.strftime('%H:%M'))+' · '+(item['text'][:80] or '، '.join(item.get('file_names',[])))+' · '+{'pending':'در انتظار','sending':'در حال ارسال','failed':'ارسال ناموفق'}.get(item['status'],item['status']);listing.addItem(label);listing.item(listing.count()-1).setToolTip(item.get('error',''))
            choice={};cancel=QPushButton('لغو پیام انتخاب‌شده');dialog.layout().addWidget(cancel);cancel.clicked.connect(lambda:(choice.update(action='cancel'),dialog.accept()));change=QPushButton('تغییر زمان');dialog.layout().addWidget(change);change.clicked.connect(lambda:(choice.update(action='reschedule'),dialog.accept()));close=QPushButton('بستن');dialog.layout().addWidget(close);close.clicked.connect(dialog.reject);dialog.resize(500,360)
            if dialog.exec()==QDialog.Accepted and 0<=listing.currentRow()<len(items):
                entry=items[listing.currentRow()]
                if choice.get('action')=='reschedule':
                    picker=ScheduleDialog(self)
                    if picker.exec()==QDialog.Accepted:self.run(lambda c:c.request('chat/scheduled/reschedule',dict(id=entry['id'],due_at=picker.due_at,expected_due_at=entry['due_at'])),lambda _:self.status.setText('زمان ارسال تغییر کرد.'))
                else:self.run(lambda c:c.request('chat/scheduled/cancel',dict(id=entry['id'],expected_due_at=entry['due_at'])),lambda _:self.status.setText('زمان‌بندی پیام لغو شد.'))
        self.run(lambda c:c.request('chat/scheduled',company=room['company'],room=room['room']),show)
    def special(self,kind):
        if not self.selected:return
        d=MessageDialog(kind,self)
        if d.exec():s=self.selected;self.run(lambda c:c.request('chat/messages',dict(company=s['company'],room=s['room'],text=d.title.text(),kind=kind,payload=d.payload)),lambda _:self.changed())
    def download(self,file):
        def received(result):
            raw=base64.b64decode(result['data']);path,_=QFileDialog.getSaveFileName(self,'ذخیره '+file['name'],file['name'])
            if path:
                try:Path(path).write_bytes(raw)
                except OSError as e:QMessageBox.warning(self,'فایل',str(e))
            if file['mime'].startswith('image/'):
                pix=QPixmap();pix.loadFromData(raw)
                if not pix.isNull():d=QDialog(self);d.setWindowTitle(file['name']);v=QVBoxLayout(d);l=QLabel();l.setPixmap(pix.scaled(820,620,Qt.KeepAspectRatio,Qt.SmoothTransformation));v.addWidget(l);d.exec()
        self.run(lambda c:c.request('chat/file',id=file['id']),received)
