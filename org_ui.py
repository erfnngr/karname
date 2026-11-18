"""Company workspace, file attendance and LAN host controls."""
import base64,copy,json,threading,hashlib,sys,socket
from pathlib import Path
from datetime import datetime,date
from PySide6.QtCore import Qt,QObject,Signal,QTimer,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,QPushButton,QComboBox,QSpinBox,QCheckBox,QTextEdit,QScrollArea,QDialogButtonBox,QTableWidget,QTableWidgetItem,QAbstractItemView,QFileDialog,QMessageBox,QInputDialog,QMenu,QApplication,QListWidget,QListWidgetItem)
from storage import app_dir,fa,parse_j,today_j,jformat,normalize
from org_schema import SCHEMAS,STATUSES,ROLES
from org_client import Client,inspect_certificate,validate_url
from ui_icons import iconize

def label(text):
    w=QLabel(str(text));w.setTextFormat(Qt.PlainText);w.setWordWrap(True);return w
def action(title,key,fn):
    b=QPushButton(title);iconize(b,key);b.clicked.connect(fn);return b
class Result(QObject):done=Signal(object,object)

class RecordDialog(QDialog):
    def __init__(self,parent,kind,record=None,company_id=None):
        super().__init__(parent);self.panel=parent;self.kind=kind;self.record=record;self.widgets={};self.setWindowTitle(('ویرایش ' if record else 'افزودن ')+parent.kind.itemText(parent.kind.findData(kind)));self.resize(650,690)
        root=QVBoxLayout(self);area=QScrollArea();area.setWidgetResizable(True);body=QWidget();form=QFormLayout(body);area.setWidget(body);root.addWidget(area);p=record['payload'] if record else {};target_company=company_id or parent.company.currentData()
        fields=SCHEMAS[kind]['fields'] if kind in SCHEMAS else [dict(key='title',label='عنوان',type='text',required=True),dict(key='notes',label='توضیحات',type='multiline')]
        if kind=='task':
            fields=[dict(key=k,label=l,type=t,choices=c,required=k in ('title','due_date')) for k,l,t,c in [('title','عنوان','text',[]),('due_date','موعد شمسی','date',[]),('estimate_hours','زمان برآوردی؛ ساعت','number',[]),('status','وضعیت','choice',list(STATUSES)),('assignee_id','مسئول انجام','user',[]),('reviewer_id','مسئول تأیید','user',[]),('substitute_id','جانشین','user',[]),('category','بخش','choice',['مالیات','بیمه','سایر']),('department','واحد','text',[]),('private','فقط برای خودم','bool',[]),('require_approval','تأیید مسئول الزامی','bool',[]),('require_evidence','مدرک الزامی','bool',[]),('reference','شماره رسید / پیگیری','text',[]),('deadline_source','منبع موعد','text',[]),('dependencies','پیش‌نیازها','dependencies',[]),('checklist','چک‌لیست؛ هر خط یک مورد، انجام با [x]','multiline',[]),('notes','شرح کار','multiline',[])]]
        for f in fields:
            k,t=f['key'],f['type'];value=p.get(k,{'status':'draft' if kind=='task' else 'imported' if kind=='attendance' else 'pending','estimate_hours':'1','category':'سایر' if kind=='task' else ''}.get(k,''));w=None
            if k in ('user_id','reviewer_id','target_user','assignee_id'):t='user'
            if k=='rate_id':t='rate'
            if k=='form_id':t='form'
            if k=='client_id':t='client'
            if k=='contract_id':t='contract'
            if self.kind=='insurance_employee' and k=='employee_id':t='employee'
            if self.kind=='insurance_employee' and k=='workshop_id':t='insurance_workshop'
            if t in ('choice','user','rate','form','client','contract','employee','insurance_workshop'):
                w=QComboBox();w.addItem('—','')
                if t=='choice':
                    for choice in f.get('choices',[]):w.addItem(STATUSES.get(choice,{'pending':'منتظر بررسی','approved':'تأیید','rejected':'رد / اصلاح','imported':'واردشده','needs_review':'بررسی لازم','overdue':'تأخیر در موعد','review':'انتظار تأیید','attachment':'رسیدن مدرک'}.get(choice,choice)),choice)
                elif t=='user':
                    for person in parent.people:
                        if person['global_role']=='group_admin' or any(m['company_id']==target_company for m in person['memberships']):w.addItem(person['fullname'],person['id'])
                else:
                    for r in parent.records:
                        if r['kind']==t and r['company_id']==target_company:w.addItem(r['title'],r['id'])
                w.setCurrentIndex(max(0,w.findData(value)))
            elif t=='user_scope':
                w=QWidget();box=QVBoxLayout(w);box.setContentsMargins(0,0,0,0)
                w.everyone=QCheckBox('همه افراد دارای دسترسی بخش بیمه');w.everyone.setChecked(p.get(k) is None);box.addWidget(w.everyone)
                w.people=QListWidget();w.people.setMaximumHeight(150);box.addWidget(w.people)
                selected=p.get(k) or [];seen=set()
                for person in parent.people:
                    if any(m['company_id']==target_company for m in person.get('memberships',[])):
                        item=QListWidgetItem(person['fullname']);item.setData(Qt.UserRole,person['id']);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked if person['id'] in selected else Qt.Unchecked);w.people.addItem(item);seen.add(person['id'])
                for user_id in selected:
                    if user_id not in seen:
                        item=QListWidgetItem('کاربر خارج از فهرست');item.setData(Qt.UserRole,user_id);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked);w.people.addItem(item)
                w.people.setEnabled(not w.everyone.isChecked());w.everyone.toggled.connect(lambda checked,items=w.people:items.setEnabled(not checked))
            elif t=='bool':
                w=QCheckBox();w.setChecked(bool(record.get('private') if record and k=='private' else value if value!='' else k=='require_approval'))
            elif t=='dependencies':
                w=QComboBox();w.setEditable(True);w.addItem('','')
                for r in parent.records:
                    if r['kind']=='task' and r['company_id']==parent.company.currentData() and (not record or r['id']!=record['id']):w.addItem(r['title'],r['id'])
                deps=p.get(k,[])
                if len(deps)==1 and w.findData(deps[0])>=0:w.setCurrentIndex(w.findData(deps[0]))
                elif deps:w.setEditText(','.join(deps))
                w.setToolTip('یک کار را انتخاب کنید؛ برای چند پیش‌نیاز، شناسه‌ها را با ویرگول وارد کنید.')
            elif t=='multiline':
                if k=='checklist' and kind=='task':value='\n'.join(('[x] ' if x.get('done') else '[ ] ')+x['text'] for x in p.get(k,[]))
                w=QTextEdit();w.setAcceptRichText(False);w.setPlainText(str(value));w.setMinimumHeight(100)
            else:
                if k=='department' and record:value=record['department']
                w=QLineEdit(str(value));w.setPlaceholderText('۱۴۰۵/۰۸/۰۴' if t=='date' else '')
            w.setAccessibleName(f['label']);form.addRow(f['label']+(' *' if f.get('required') else ''),w);self.widgets[k]=(w,t)
        if kind=='form_response':
            self.answer_form=QFormLayout();form.addRow(self.answer_form);self.answer_widgets={};self.widgets['form_id'][0].currentIndexChanged.connect(self.form_fields);self.form_fields()
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);iconize(buttons.button(QDialogButtonBox.Save),'save','ذخیره');buttons.button(QDialogButtonBox.Cancel).setText('بازگشت');buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);root.addWidget(buttons)
    def form_fields(self):
        while self.answer_form.count():
            item=self.answer_form.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.answer_widgets={};id=self.widgets['form_id'][0].currentData();record=next((r for r in self.panel.records if r['id']==id),None)
        if not record:return
        old={}
        try:old=json.loads((self.record or {}).get('payload',{}).get('answers','{}'))
        except ValueError:pass
        for name in record['payload'].get('fields','').splitlines():
            name=name.strip()
            if name:w=QLineEdit(str(old.get(name,'')));self.answer_form.addRow(name,w);self.answer_widgets[name]=w
        self.widgets['answers'][0].hide()
    def validate(self):
        try:
            p=copy.deepcopy(self.record['payload']) if self.record else {}
            for k,(w,t) in self.widgets.items():
                p[k]=(None if w.everyone.isChecked() else [w.people.item(i).data(Qt.UserRole) for i in range(w.people.count()) if w.people.item(i).checkState()==Qt.Checked]) if t=='user_scope' else w.isChecked() if t=='bool' else w.currentData() if t in ('choice','user','rate','form','client','contract','employee','insurance_workshop') else w.toPlainText() if t=='multiline' else (w.currentData() if w.currentIndex()>=0 and w.currentText()==w.itemText(w.currentIndex()) else w.currentText()) if t=='dependencies' else w.text().strip()
            if self.kind=='form_response' and self.answer_widgets:p['answers']=json.dumps({k:w.text() for k,w in self.answer_widgets.items()},ensure_ascii=False)
            if self.kind=='task':
                p['dependencies']=[x.strip() for x in (p['dependencies'] or '').split(',') if x.strip()];p['checklist']=[dict(text=line.strip().removeprefix('[x]').removeprefix('[X]').removeprefix('[ ]').strip(),done=line.strip().lower().startswith('[x]')) for line in p['checklist'].splitlines() if line.strip()]
            from org_store import Store
            # Local validation shares the server schema; server repeats permission checks.
            Store.validate(None,self.kind,p)
            self.payload=p;self.accept()
        except Exception as exc:QMessageBox.warning(self,'اطلاعات را بررسی کنید',str(exc))

class AttendanceDialog(QDialog):
    def __init__(self,parent,path):
        super().__init__(parent);from attendance_import import read_table,guess_mapping,FIELDS
        self.headers,self.rows=read_table(path);self.mapping={};self.setWindowTitle('ورود تردد ماهانه از فایل');self.resize(900,650);v=QVBoxLayout(self);f=QFormLayout();v.addLayout(f);self.month=QLineEdit(normalize(jformat(today_j()))[:7]);f.addRow('ماه شمسی:',self.month)
        guessed=guess_mapping(self.headers)
        for key,name in FIELDS.items():
            box=QComboBox();box.addItem('انتخاب نشده',-1)
            for i,h in enumerate(self.headers):box.addItem(h,i)
            box.setCurrentIndex(guessed[key]+1);self.mapping[key]=box;f.addRow(name,box)
        preview=QPushButton('پیش‌نمایش و بررسی');preview.clicked.connect(self.preview);v.addWidget(preview);self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['ردیف','کد پرسنلی','تاریخ / دقیقه','نتیجه بررسی']);self.table.horizontalHeader().setStretchLastSection(True);v.addWidget(self.table,1);self.status=label('هیچ اطلاعاتی تا تأیید شما وارد نمی‌شود. تاریخ می‌تواند شمسی یا میلادی باشد.');v.addWidget(self.status);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);self.save=buttons.button(QDialogButtonBox.Save);self.save.setText('ورود ردیف‌های سالم');self.save.setEnabled(False);buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);v.addWidget(buttons);self.valid=[]
    def preview(self):
        from attendance_import import preview
        try:
            result=preview(self.headers,self.rows,{k:w.currentData() for k,w in self.mapping.items()},self.month.text());self.valid=[r['payload'] for r in result if r['valid']];self.table.setRowCount(min(len(result),500))
            for i,r in enumerate(result[:500]):
                p=r.get('payload',{})
                for j,t in enumerate([r['line'],p.get('employee_code',''),p.get('date','')+' · '+p.get('minutes',''),r.get('error','آماده ورود')]):self.table.setItem(i,j,QTableWidgetItem(str(t)))
            self.status.setText(fa(len(self.valid))+' ردیف سالم؛ '+fa(len(result)-len(self.valid))+' ردیف کنار گذاشته می‌شود. پیش‌نمایش حداکثر ۵۰۰ ردیف است.');self.save.setEnabled(bool(self.valid));self.month_value=normalize(self.month.text())
            self.month.setEnabled(False)
            for w in self.mapping.values():w.setEnabled(False)
        except Exception as exc:QMessageBox.warning(self,'بررسی فایل',str(exc))

class ServerDialog(QDialog):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.setWindowTitle('میزبان فضای شرکت');self.resize(680,580);v=QVBoxLayout(self);f=QFormLayout();v.addLayout(f);self.host=QComboBox();self.host.addItem('فقط همین کامپیوتر','127.0.0.1');self.host.addItem('شبکه شرکت با HTTPS','0.0.0.0');f.addRow('دسترسی:',self.host);self.port=QSpinBox();self.port.setRange(1024,65535);self.port.setValue(8843);f.addRow('درگاه:',self.port);self.address=QLineEdit();self.address.setPlaceholderText('IP یا نام ثابت همین میزبان برای گواهی شبکه');f.addRow('نشانی این میزبان در شبکه:',self.address)
        from org_store import Store
        self.folder=owner.base_dir/'company-server';store=Store(self.folder)
        self.username=QLineEdit();self.fullname=QLineEdit();self.password=QLineEdit();self.password.setEchoMode(QLineEdit.Password)
        if not store.initialized():f.addRow('نام کاربری مدیر اولیه:',self.username);f.addRow('نام مدیر:',self.fullname);f.addRow('رمز مدیر؛ حداقل ۱۰ نویسه:',self.password)
        v.addWidget(label('برای استفاده در شبکه، میزبان باید روشن بماند. نشانی اینترنتی را نیز می‌توانید در صفحه اتصال وارد کنید. فعال‌سازی فایروال یا انتشار عمومی را مدیر شبکه انجام می‌دهد.'))
        self.status=QTextEdit();self.status.setReadOnly(True);v.addWidget(self.status,1);self.start=QPushButton('شروع میزبان');self.start.clicked.connect(self.start_host);v.addWidget(self.start);cert=QPushButton('ذخیره گواهی عمومی برای دستگاه‌های دیگر');cert.clicked.connect(self.export_cert);v.addWidget(cert);backup=QPushButton('پشتیبان کامل میزبان');backup.clicked.connect(self.backup_server);v.addWidget(backup);restore=QPushButton('بازگردانی کامل میزبان');restore.clicked.connect(self.restore_server);v.addWidget(restore)
        from lan_discovery import load_profile,preferred_address
        profile=load_profile(owner.base_dir)
        if profile:self.host.setCurrentIndex(1);self.address.setText(preferred_address(profile['preferred_ip']));self.address.setPlaceholderText('خودکار از شبکه فعلی؛ قابل ویرایش')
        if getattr(owner,'network_server',None):self.host.setCurrentIndex(1);self.address.setText(owner._host_address);self.port.setValue(owner.network_server.port)
        if getattr(owner,'company_server',None):self.describe()
    def start_host(self):
        from ui_permissions import gate
        if not gate(self.owner,'network','manage'):return
        from org_store import Store
        from org_http import RunningServer,make_certificate
        try:
            if self.owner.session_user and not self.owner.can_backup_server():raise ValueError('تنظیم میزبان فقط در اختیار مدیر کل فعال همین میزبان است.')
            if self.owner.org.busy:raise ValueError('پس از پایان عملیات مرکز، دوباره تلاش کنید.')
            store=Store(self.folder)
            if not store.initialized():store.bootstrap(self.username.text(),self.password.text(),self.fullname.text());self.password.clear()
            tls=self.host.currentData()!='127.0.0.1';hosts=[self.address.text().strip()] if tls else []
            if tls and not hosts[0]:raise ValueError('IP یا نام ثابت میزبان را وارد کنید تا گواهی همان نشانی ساخته شود.')
            cert,key,fp=make_certificate(self.folder,hosts)
            if getattr(self.owner,'_external_host',False):
                from network_tools import stop_autohost
                stop_autohost(self.owner.base_dir);self.owner._external_host=False
            if tls:
                if self.owner.network_server:self.owner.network_server.close();self.owner.network_server=None
                self.owner.network_server=RunningServer(self.folder,'0.0.0.0',self.port.value(),True,cert,key,background=not bool(self.owner.company_server),discovery=True);self.owner._host_address=hosts[0];self.owner._host_fingerprint=fp
            elif self.owner.network_server:self.owner.network_server.close();self.owner.network_server=None
            if not self.owner.company_server:self.owner.company_server=RunningServer(self.folder,'127.0.0.1',0)
            settings=dict(enabled=tls,port=self.port.value(),address=hosts[0] if tls else '',fingerprint=fp);(self.owner.base_dir/'server-host.json').write_text(json.dumps(settings,ensure_ascii=False),encoding='utf-8');self.describe()
        except Exception as exc:QMessageBox.warning(self,'میزبان شروع نشد',str(exc))
    def describe(self):
        if getattr(self.owner,'_external_host',False):
            cfg=json.loads((self.owner.base_dir/'server-host.json').read_text('utf-8'));url='https://'+self.owner._host_address+':'+str(cfg['port']);self.status.setPlainText('مرکز مستقل شرکت فعال است:\n'+url+'\n\nاثر انگشت گواهی:\n'+self.owner._host_fingerprint);self.start.setText('اعمال تنظیمات میزبان');return
        server=self.owner.network_server or self.owner.company_server;scheme='https' if server.server.tls else 'http';url=f'{scheme}://{self.owner._host_address if server.server.tls else "127.0.0.1"}:{server.port}';self.status.setPlainText('میزبان فعال است:\n'+url+'\n\nاثر انگشت گواهی عمومی:\n'+self.owner._host_fingerprint+'\n\nاین پنجره را می‌توانید ببندید؛ بستن کامل کارنامه میزبان را هم متوقف می‌کند.');self.start.setText('اعمال تنظیمات میزبان');self.owner.org.url.setText(url)
    def export_cert(self):
        source=self.folder/'server-cert.pem'
        if not source.exists():QMessageBox.information(self,'گواهی','ابتدا میزبان را راه‌اندازی کنید.');return
        target,_=QFileDialog.getSaveFileName(self,'ذخیره گواهی عمومی','Karname-Server-Certificate.pem','Certificate (*.pem)')
        if target:Path(target).write_bytes(source.read_bytes())
    def restore_server(self):
        from ui_permissions import gate
        if not gate(self.owner,'backup','full'):return
        if not self.owner.can_backup_server():QMessageBox.warning(self,'دسترسی','بازگردانی کامل میزبان فقط در اختیار مدیر کل است.');return
        if self.owner.org.busy:QMessageBox.information(self,'بازگردانی','پس از پایان عملیات مرکز دوباره تلاش کنید.');return
        from server_restore import inspect_server_backup,restore_closed_server
        path,_=QFileDialog.getOpenFileName(self,'انتخاب پشتیبان کامل میزبان','','Karname Backup (*.karname *.zip)')
        if not path:return
        from backup_crypto import unlock_ui
        if not unlock_ui(path,self):return
        stopped=False
        try:
            data,entries,manifest,counts=inspect_server_backup(path)
            if QMessageBox.question(self,'بازگردانی کامل میزبان','پشتیبان شامل '+fa(counts['users'])+' حساب و '+fa(counts['records'])+' پرونده است. حساب‌ها، رمزها و اطلاعات مشترک به زمان پشتیبان برمی‌گردند. پوشه فعلی برای بازیابی حفظ می‌شود و پس از پایان، برنامه بسته خواهد شد. بازگردانی انجام شود؟',QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
            from network_tools import stop_autohost
            stop_autohost(self.owner.base_dir)
            self.owner.persist();self.owner.org.timer.stop();self.owner.chat.timer.stop();self.owner.timer.stop();stopped=True
            if self.owner.network_server:self.owner.network_server.close();self.owner.network_server=None
            if self.owner.company_server:self.owner.company_server.close();self.owner.company_server=None
            _,old=restore_closed_server(self.owner.base_dir,path);QMessageBox.information(self,'بازگردانی انجام شد','برنامه را دوباره باز کنید و با حساب و رمز زمان پشتیبان وارد شوید.\nنسخه قبلی برای بازیابی نگه داشته شد:\n'+str(old or ''))
            self.owner._exit_approved=True;QApplication.instance().quit()
        except Exception as exc:
            QMessageBox.warning(self,'بازگردانی انجام نشد',str(exc))
            if stopped:QTimer.singleShot(0,self.owner.lock_session)
    def backup_server(self):
        from ui_permissions import gate
        if not gate(self.owner,'backup','full'):return
        if not self.owner.can_backup_server():QMessageBox.warning(self,'دسترسی','پشتیبان کامل میزبان فقط در اختیار مدیر کل است. از خروجی مجاز شرکت خود استفاده کنید.');return
        # Local host administrator action. Sessions are removed from the snapshot.
        import tempfile,zipfile,sqlite3
        from contextlib import closing
        from org_store import Store
        target,_=QFileDialog.getSaveFileName(self,'پشتیبان کامل میزبان','Karname-Server-Backup.karname','Karname Backup (*.karname)')
        if not target:return
        try:
            with tempfile.TemporaryDirectory(dir=app_dir()) as folder:
                db=Path(folder)/'company.sqlite';store=Store(self.folder);store.backup_database(db)
                with closing(sqlite3.connect(db)) as connection:connection.execute('DELETE FROM sessions');connection.execute('DELETE FROM login_limits');connection.commit()
                from backup_bundle import create_bundle
                extras={'server/company.sqlite':db.read_bytes()}
                for p in store.files.glob('*.bin'):extras['server/files/'+p.name]=p.read_bytes()
                from v8_controller import password_for_backup
                create_bundle(target,self.owner.data,extras,password=password_for_backup(self.owner))
            QMessageBox.information(self,'پشتیبان میزبان','نسخه کامل اطلاعات و مدارک ذخیره و صحت آن بررسی شد. رمزهای ورود به صورت درهم‌سازی‌شده در آن هستند؛ فایل را نزد مدیر نگه دارید.')
        except Exception as exc:QMessageBox.warning(self,'پشتیبان ذخیره نشد',str(exc))

class CompanyPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.client=None;self.records=[];self.people=[];self.notices=[];self.birthdays=[];self.birthday_reminders=[];self.busy=False;self.signals=Result();self.signals.done.connect(self.finished);self.callback=None;self.revision=None;self.shown=set();v=QVBoxLayout(self);v.setContentsMargins(20,15,20,15)
        self.state=label('فضای شرکت · اتصال به مرکز محلی یا اینترنتی');v.addWidget(self.state);connect=QHBoxLayout();self.url=QLineEdit(owner.data['settings'].get('company_url','http://127.0.0.1:8843'));self.url.setLayoutDirection(Qt.LeftToRight);self.url.setPlaceholderText('https://server:8843');self.username=QLineEdit(owner.data['settings'].get('company_username',''));self.username.setPlaceholderText('نام کاربری');self.password=QLineEdit();self.password.setEchoMode(QLineEdit.Password);self.password.setPlaceholderText('رمز عبور');connect.addWidget(self.url,2);connect.addWidget(self.username);connect.addWidget(self.password);self.login_button=QPushButton('ورود');self.login_button.clicked.connect(self.login);connect.addWidget(self.login_button);v.addLayout(connect)
        connection_actions=QHBoxLayout();host=QPushButton('راه‌اندازی میزبان');host.clicked.connect(lambda:ServerDialog(owner).exec());connection_actions.addWidget(host);pair=QPushButton('جفت‌سازی گواهی شبکه');pair.clicked.connect(self.pair);connection_actions.addWidget(pair);browser=QPushButton('پنل مرورگر / موبایل');browser.clicked.connect(self.open_portal);connection_actions.addWidget(browser);logout=QPushButton('خروج از حساب');logout.clicked.connect(self.logout);connection_actions.addWidget(logout);connection_actions.addStretch();v.addLayout(connection_actions)
        tools=QHBoxLayout();self.company=QComboBox();self.company.currentIndexChanged.connect(self.render);tools.addWidget(self.company);self.kind=QComboBox();self.kind.addItem('همه پرونده‌ها','');self.kind.addItem('کارها','task');self.kind.addItem('اسناد و رسیدها','document')
        for key,schema in SCHEMAS.items():self.kind.addItem(schema['label'],key)
        self.kind.currentIndexChanged.connect(self.render);tools.addWidget(self.kind);self.search=QLineEdit();self.search.setPlaceholderText('جست‌وجو در پرونده‌ها');self.search.textChanged.connect(self.render);tools.addWidget(self.search,1)
        for title,key,fn in [('افزودن','add',self.add),('ویرایش','edit',self.edit),('تازه‌سازی','refresh',self.sync),('خروجی و اشتراک‌گذاری','export',self.export),('ورود فایل تردد ماهانه','import',self.import_attendance)]:tools.addWidget(action(title,key,fn))
        v.addLayout(tools);self.summary=label('');v.addWidget(self.summary);self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['عنوان','بخش','وضعیت','موعد','مسئول']);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.SingleSelection);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.horizontalHeader().setStretchLastSection(True);self.table.doubleClicked.connect(self.edit);v.addWidget(self.table,1);self.inbox_button=QPushButton('صندوق اعلان‌ها');self.inbox_button.clicked.connect(self.show_inbox);v.addWidget(self.inbox_button);self.timer=QTimer(self);self.timer.setInterval(30000);self.timer.timeout.connect(self.sync);self.timer.start()
        if getattr(owner,'session_user',None):
            from access_ui import manager
            for w in (self.url,self.username,self.password,self.login_button,pair):w.hide()
            host.setVisible(owner.session_user['global_role'] in ('group_admin','system_admin'));logout.setText('خروج از حساب و برنامه')
    def run(self,fn,done):
        if self.busy:return False
        self.busy=True;self.callback=done;self.state.setText('در حال ارتباط با مرکز اطلاعات…');self.login_button.setEnabled(False)
        def work():
            try:value,error=fn(),None
            except Exception as exc:value,error=None,exc
            try:self.signals.done.emit(value,error)
            except RuntimeError:pass  # The window may have closed while the request was in flight.
        threading.Thread(target=work,daemon=True).start();return True
    def finished(self,value,error):
        self.busy=False;self.login_button.setEnabled(True);callback=self.callback;self.callback=None
        if error:
            if getattr(error,'status',None)==401:
                self.client=None;self.records=[];self.people=[];self.notices=[];self.owner.shared_events=[];self.company.clear();self.render();self.owner.refresh()
                if getattr(self.owner,'session_user',None):QTimer.singleShot(0,self.owner.lock_session)
            self.state.setText('اتصال / عملیات انجام نشد: '+str(error)+'\nفهرست آخرین دریافت، تا اتصال دوباره فقط قابل‌مشاهده است.');return
        self.state.setText('متصل · آخرین دریافت '+datetime.now().strftime('%H:%M'));callback(value)
    def certificate(self,url):
        path=app_dir()/'trusted-certificates'/(hashlib.sha256(url.encode()).hexdigest()+'.pem');return str(path) if path.exists() else None
    def pair(self):
        try:
            url=validate_url(self.url.text().strip());pem,fp=inspect_certificate(url);d=QDialog(self);d.setWindowTitle('تأیید هویت میزبان');v=QVBoxLayout(d);v.addWidget(label('این اثر انگشت باید دقیقاً با پنجره میزبان شرکت برابر باشد:'));code=QLineEdit(fp);code.setReadOnly(True);code.setLayoutDirection(Qt.LeftToRight);v.addWidget(code);agree=QCheckBox('اثر انگشت را با میزبان شرکت مقایسه کردم و یکسان است.');v.addWidget(agree);buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Ok).setText('اعتماد به این گواهی');buttons.button(QDialogButtonBox.Ok).setEnabled(False);agree.toggled.connect(buttons.button(QDialogButtonBox.Ok).setEnabled);buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);v.addWidget(buttons)
            if d.exec()==QDialog.Accepted:path=app_dir()/'trusted-certificates'/(hashlib.sha256(url.encode()).hexdigest()+'.pem');path.parent.mkdir(exist_ok=True);path.write_text(pem,encoding='ascii');self.state.setText('گواهی جفت شد؛ اکنون وارد شوید.')
        except Exception as exc:QMessageBox.warning(self,'جفت‌سازی انجام نشد',str(exc))
    def login(self):
        try:client=Client(self.url.text().strip(),self.certificate(self.url.text().strip().rstrip('/')));username=self.username.text().strip();password=self.password.text()
        except Exception as exc:QMessageBox.warning(self,'اتصال',str(exc));return
        def login():
            from offline_cache import OfflineCache
            cache=OfflineCache(self.owner.base_dir/'company-cache',client.url,username,password)
            try:client.login(username,password);client.cache=cache;return dict(client=client)
            except Exception as exc:
                if getattr(exc,'status',None)==503 and cache.path.exists():return dict(snapshot=cache.load())
                raise
        def ready(value):
            self.password.clear();self.shown=set()
            if 'snapshot' in value:self.client=None;self.apply_snapshot(value['snapshot'],True);return
            self.client=value['client'];self.owner.data['settings'].update(company_url=client.url,company_username=username);self.owner.persist();self.revision=None;self.sync()
        self.run(login,ready)
    def logout(self):
        if getattr(self.owner,'session_user',None):self.owner.exit_app();return
        if self.busy:return
        client=self.client
        def clear(_=None):self.client=None;self.records=[];self.people=[];self.notices=[];self.owner.shared_events=[];self.company.clear();self.render();self.owner.refresh();self.state.setText('از حساب شرکت خارج شدید.')
        if client:self.run(lambda:client.logout(),clear)
        else:clear()
    def sync(self):
        if not self.client or self.busy or self.owner._exit_pending or self.owner._exit_approved:return
        client=self.client;pending_profile=self.owner.data.get('pending_profile_restore')
        if not pending_profile and self.owner.data.get('pending_birthday_sync') and self.owner.session_user:
            pending_profile=dict(avatar=self.owner.session_user.get('profile',{}).get('avatar',''),color=self.owner.session_user.get('profile',{}).get('color','#DDEBF8'),preferences=self.owner.data.get('preferences',{}))
        previous_records=copy.deepcopy(self.records);previous_revision=self.revision or 0
        def fetch():
            profile_restored=False;profile_blocked=False
            if pending_profile:
                try:client.request('profile',{k:v for k,v in pending_profile.items() if k in ('avatar','color','preferences')});profile_restored=True
                except Exception as exc:
                    if getattr(exc,'status',None)==403:profile_blocked=True
                    else:raise
            user=client.request('me');companies=client.request('companies');people=client.request('users');dashboard=client.request('dashboard');delta=client.request('workspace/records-delta',dict(after=previous_revision,known=[r['id'] for r in previous_records])) if dashboard['revision']!=self.revision else None;records=None
            if delta:
                merged={} if delta['full'] else {r['id']:r for r in previous_records if r['id'] not in delta['removed']};merged.update({r['id']:r for r in delta['items']});records=list(merged.values())
            inbox=client.request('inbox')
            try:birthday_data=client.request('birthdays')
            except Exception:birthday_data=None
            return dict(user=user,companies=companies,people=people,dashboard=dashboard,records=records,inbox=inbox,birthdays=birthday_data,profile_restored=profile_restored,profile_blocked=profile_blocked)
        self.run(fetch,self.apply_snapshot)
    def apply_snapshot(self,value,offline=False):
        if self.client:self.client.user=value['user']
        if self.owner.session_user and self.owner.session_user['id']==value['user']['id']:self.owner.session_user=value['user']
        if value.get('profile_restored') and not offline:
            self.owner.data.pop('pending_profile_restore',None)
            self.owner.data.pop('pending_birthday_sync',None)
            self.owner.persist()
        elif value.get('profile_blocked') and not offline:self.state.setText('بازیابی تنظیمات شخصی تا فعال‌شدن دسترسی ویرایش توسط مدیر در انتظار است؛ سایر بخش‌ها متصل‌اند.')
        bday_snap=value.get('birthdays') or {}
        if bday_snap:
            self.birthdays=bday_snap.get('birthdays',[]);self.birthday_reminders=bday_snap.get('reminders',[])
            own_b=bday_snap.get('own_birthday')
            prefs=self.owner.data.setdefault('preferences',{})
            if own_b:prefs['birthday']=own_b
        from brand import register_company
        for company in value['companies']:register_company(company)
        from main_ui import apply_preferences
        apply_preferences(self.owner)
        self.people=value['people'];old=self.company.currentData();self.company.blockSignals(True);self.company.clear()
        for c in value['companies']:self.company.addItem(c['name'],c['id'])
        self.company.setCurrentIndex(max(0,self.company.findData(old)));self.company.blockSignals(False);self.revision=value['dashboard']['revision']
        if value['records'] is not None:
            self.records=value['records']
            if hasattr(self.owner,'tax_center'):
                self.owner.tax_center.comparison.setRowCount(0);self.owner.tax_center.comparison_note.setText('اطلاعات شرکت تغییر کرده است؛ برای به‌روزرسانی نتیجه، دوباره مقایسه را بزنید.')
        if hasattr(self.owner,'tax_center'):self.owner.tax_center.sync_companies(value['companies'])
        if hasattr(self.owner,'clients'):self.owner.clients.refresh_data(value['companies'])
        d=value['dashboard'];self.summary.setText('کارها: '+fa(d['total'])+' · معوق: '+fa(d['overdue'])+' · منتظر تأیید: '+fa(d['review'])+' · تکمیل: '+fa(d['completed'])+' · تعهد ۳۰ روز آینده: '+fa(d['upcoming_amount'])+' ریال');self.notices=value['inbox'];self.inbox_button.setText('صندوق اعلان‌ها · '+fa(len(self.notices)));self.render();self.calendar_events(value['companies']);self.owner.refresh()
        if offline:self.state.setText('آفلاین · آخرین دریافت ذخیره‌شده، فقط برای مطالعه. برای ثبت تغییر، پس از اتصال دوباره وارد شوید.');return
        cache=getattr(self.client,'cache',None)
        if cache:
            try:cache.save(dict(value,records=self.records))
            except OSError:self.state.setText('متصل؛ ذخیره نسخه آفلاین انجام نشد.')
        for n in self.notices:
            if n['id'] not in self.shown and not n['receipt']['opened']:
                self.shown.add(n['id']);self.owner.popup(n['payload']['body'][:350],title=n['title'],company=next((c['name'] for c in value['companies'] if c['id']==n['company_id']),None),on_click=self.open_inbox)
        for br in (bday_snap.get('reminders') or []):
            if br.get('shown'):continue
            bkey=('birthday',br.get('id'),br.get('birthday_date_j'))
            if bkey in self.shown:continue
            self.shown.add(bkey)
            def _ack(act_name,rid=br['id'],cl=self.client):
                def _w():
                    try:cl.request('birthdays/ack',{'id':rid,'action':act_name})
                    except Exception:pass
                threading.Thread(target=_w,daemon=True).start()
            self.owner.popup(br['body'],title=br['title'],on_click=lambda rid=br['id']:(_ack('opened',rid),self.owner.show_main(),self.owner.tabs.setCurrentWidget(self.owner.calendar_page)),on_shown=lambda rid=br['id']:_ack('shown',rid))
        if hasattr(self.owner,'check_birthday_celebration') and self.owner.isVisible():
            QTimer.singleShot(150,self.owner.check_birthday_celebration)
    def open_inbox(self):self.owner.show_main();self.owner.tabs.setCurrentWidget(self);self.show_inbox()
    def calendar_events(self,companies):
        new_names=list(dict.fromkeys(self.owner.data['companies']+[c['name'] for c in companies]))
        if new_names!=self.owner.data['companies']:self.owner.data['companies']=new_names;self.owner.update_companies()
        names={c['id']:c['name'] for c in companies};events=[]
        for r in self.records:
            p=r['payload']
            if r['kind'] not in ('task','commitment','contract','installment','tax_job','invoice','tax_case') or not p.get('due_date'):continue
            if r['kind']=='invoice' and p.get('status')=='cancelled':continue
            ev=dict(id='shared-'+r['id'],shared_id=r['id'],title=p['title'],company=names.get(r['company_id'],'شخصی'),date_jalali=p['due_date'],category='مالیات' if r['kind']=='tax_case' else p.get('category','سایر'),notes=p.get('notes',''),done=(p.get('status')=='completed' if r['kind']=='tax_case' else p.get('status') in ('completed','submitted','paid') or bool(p.get('paid'))),needs_review=False,recurrence='بدون تکرار',priority=p.get('priority','مهم'),reminder_group='default',last_alerts=self.owner.data.setdefault('shared_alerts',{}).get(r['id'],{}));events.append(ev)
        for event in events:
            override=self.owner.data.get('shared_reminder_overrides',{}).get(event['shared_id'])
            if isinstance(override,dict) and override.get('lead_days'):
                from reminders import parse_leads
                try:event.update(lead_days=parse_leads(','.join(map(str,override['lead_days']))),reminder_custom=True)
                except (ValueError,TypeError):pass
        self.owner.shared_events=events
    def render(self,*_):
        query=normalize(self.search.text()).casefold();co=self.company.currentData();kind=self.kind.currentData();self.visible=[r for r in self.records if (not co or r['company_id']==co or r['private']) and (not kind or r['kind']==kind) and (not query or query in normalize(r['title']+' '+json.dumps(r['payload'],ensure_ascii=False)).casefold())];self.table.setRowCount(min(len(self.visible),500));people={p['id']:p['fullname'] for p in self.people}
        for i,r in enumerate(self.visible[:500]):
            p=r['payload']
            for col,value in enumerate([r['title'],SCHEMAS.get(r['kind'],{}).get('label',{'task':'کار','document':'سند','notice':'اطلاعیه'}.get(r['kind'],r['kind'])),STATUSES.get(p.get('status'),{'approved':'تأییدشده','pending':'منتظر بررسی','imported':'واردشده','rejected':'ردشده'}.get(p.get('status'),'')),p.get('due_date',p.get('date','')),people.get(p.get('assignee_id'),'')]):self.table.setItem(i,col,QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
    def mutation(self,fn):
        def done(_):self.owner.data['company_revision_entered']=self.revision or 0;self.owner.data['company_write_at']=datetime.now().isoformat();self.owner.persist();self.revision=None;self.sync()
        self.run(fn,done)
    def add(self):
        if not self.client:return
        kind=self.kind.currentData()
        if kind in ('client','invoice','tax_job') and hasattr(self.owner,'clients'):
            self.owner.clients.refresh_data();self.owner.clients.company.setCurrentIndex(self.owner.clients.company.findData(self.company.currentData()));self.owner.tabs.setCurrentWidget(self.owner.clients);self.owner.clients.new_record(kind);return
        kind=self.kind.currentData() or 'task';d=RecordDialog(self,kind)
        if kind=='task':
            templates=[r for r in self.records if r['kind']=='template' and r['company_id']==self.company.currentData()]
            if templates:
                names=['بدون الگو']+[r['title'] for r in templates];choice,ok=QInputDialog.getItem(self,'الگوی کار','شروع از الگو:',names,0,False)
                if not ok:return
                if choice!='بدون الگو':
                    p=templates[names.index(choice)-1]['payload']
                    for key in ('title','notes','category','checklist','require_approval','require_evidence'):
                        if key not in d.widgets or key not in p:continue
                        w,t=d.widgets[key];value=p[key]
                        if t=='bool':w.setChecked(bool(value))
                        elif t=='choice':w.setCurrentIndex(max(0,w.findData(value)))
                        elif t=='multiline':w.setPlainText(str(value))
                        else:w.setText(str(value))
        if d.exec()==QDialog.Accepted:self.save_dialog(d)
    def selected(self):
        row=self.table.currentRow();return self.visible[row] if 0<=row<len(self.visible) else None
    def edit(self,*_,record=None):
        record=record or self.selected()
        if not record:return
        if record['kind'] in ('client','invoice','tax_job') and hasattr(self.owner,'clients'):
            self.owner.clients.refresh_data();self.owner.clients.company.setCurrentIndex(self.owner.clients.company.findData(record['company_id']));self.owner.tabs.setCurrentWidget(self.owner.clients);self.owner.clients.edit_record(record['kind'],record);return
        if not self.client:
            d=QDialog(self);d.setWindowTitle('نسخه آفلاین · '+record['title']);d.resize(650,500);v=QVBoxLayout(d);text=QTextEdit();text.setReadOnly(True);text.setPlainText(json.dumps(record['payload'],ensure_ascii=False,indent=2));v.addWidget(text);d.exec();return
        if record['kind']=='notice':self.show_inbox();return
        d=RecordDialog(self,record['kind'],record);v=d.layout();tools=QHBoxLayout()
        for title,key,fn in [('مدارک، نظر و تاریخچه','open',lambda:self.record_details(record)),('بایگانی پرونده','delete',lambda:self.archive(record,d)),('ساخت نسخه تازه','add',lambda:self.duplicate(record,d))]:tools.addWidget(action(title,key,fn))
        v.addLayout(tools)
        if d.exec()==QDialog.Accepted:self.save_dialog(d)
    def duplicate(self,record,dialog):
        dialog.reject();d=RecordDialog(self,record['kind'],record);d.record=None
        if d.exec()==QDialog.Accepted:self.save_dialog(d)
    def archive(self,record,dialog):
        if QMessageBox.question(self,'بایگانی','پرونده بایگانی شود؟ تاریخچه حفظ می‌شود.',QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:dialog.reject();self.mutation(lambda:self.client.request('archive',dict(id=record['id'],version=record['version'])))
    def save_dialog(self,dialog):
        p=dialog.payload;old=dialog.record;department=p.pop('department','') if dialog.kind=='task' else p.get('department','');private=p.pop('private',False) if dialog.kind=='task' else False;payload=dict(kind=dialog.kind,payload=p,company=self.company.currentData(),id=old['id'] if old else None,version=old['version'] if old else None,department=department,private=private);self.mutation(lambda:self.client.request('records',payload))
    def open_portal(self):
        try:QDesktopServices.openUrl(QUrl(validate_url(self.url.text().strip())))
        except ValueError as exc:QMessageBox.warning(self,'نشانی مرکز',str(exc))
    def record_details(self,record):
        if not self.client:return
        def ready(value):
            d=QDialog(self);d.setWindowTitle(record['title']);d.resize(700,600);v=QVBoxLayout(d);box=QTextEdit();box.setReadOnly(True);box.setPlainText('شناسه پرونده: '+record['id']+'\n\n'+json.dumps(record['payload'],ensure_ascii=False,indent=2)+'\n\n'+ '\n'.join(c.get('fullname','')+': '+c['text'] for c in value['comments'])+'\n\nتاریخچه:\n'+'\n'.join(h['created']+' · '+(h.get('fullname') or 'سیستم')+' · '+h['action']+(' · علت: '+h['reason'] if h.get('reason') else '') for h in value['history']));v.addWidget(box)
            choices=QComboBox()
            for f in value['files']:choices.addItem(f['name']+' · نسخه '+fa(f['version']),f['id'])
            v.addWidget(choices);row=QHBoxLayout();row.addWidget(action('افزودن مدرک','import',lambda:self.upload(record,d)));row.addWidget(action('دریافت مدرک','export',lambda:self.download(choices.currentData())));row.addWidget(action('خواندن متن PDF / تصویر','search',lambda:self.extract(choices.currentData(),box)));v.addLayout(row);comment=QLineEdit();comment.setPlaceholderText('نظر یا توضیح');v.addWidget(comment);v.addWidget(action('ثبت نظر','save',lambda:self.post_comment(record,comment.text(),d)));d.exec()
        self.run(lambda:dict(files=self.client.request('files',id=record['id']),comments=self.client.request('comments',id=record['id']),history=self.client.request('history',id=record['id'])),ready)
    def upload(self,record,dialog):
        path,_=QFileDialog.getOpenFileName(self,'افزودن مدرک','','Documents (*.pdf *.png *.jpg *.jpeg *.txt *.csv *.xlsx *.docx *.zip)')
        if not path:return
        if Path(path).stat().st_size>12*1024*1024:QMessageBox.warning(self,'مدرک','حداکثر حجم ۱۲ مگابایت است.');return
        data=base64.b64encode(Path(path).read_bytes()).decode();dialog.accept();self.mutation(lambda:self.client.request('files',dict(id=record['id'],name=Path(path).name,data=data)))
    def download(self,id):
        if not id:return
        def ready(value):
            path,_=QFileDialog.getSaveFileName(self,'دریافت مدرک',value['info']['name'])
            if path:Path(path).write_bytes(base64.b64decode(value['data']))
        self.run(lambda:self.client.request('file',id=id),ready)
    def extract(self,id,box):
        if id:self.run(lambda:self.client.request('extract',dict(id=id)),lambda value:box.setPlainText('متن پیشنهادی؛ پیش از استفاده بررسی کنید:\n'+value['text']))
    def post_comment(self,record,text,dialog):
        if not text.strip():return
        dialog.accept();self.mutation(lambda:self.client.request('comments',dict(id=record['id'],text=text)))
    def show_inbox(self):
        d=QDialog(self);d.setWindowTitle('صندوق اعلان‌ها');d.resize(720,580);v=QVBoxLayout(d);area=QScrollArea();area.setWidgetResizable(True);body=QWidget();lay=QVBoxLayout(body);lay.setAlignment(Qt.AlignTop);area.setWidget(body);v.addWidget(area)
        for n in self.notices:
            lay.addWidget(label(n['title']));lay.addWidget(label(n['payload']['body']));row=QHBoxLayout()
            for action_type,title in [('open','مشاهده شد'),('ack','تأیید دریافت')]:
                if action_type=='ack' and not n['payload'].get('require_ack'):continue
                b=QPushButton(title);b.setEnabled(not n['receipt']['opened' if action_type=='open' else 'acknowledged']);b.clicked.connect(lambda checked=False,item=n,a=action_type:self.receipt(item,a,d));row.addWidget(b)
            lay.addLayout(row)
        if not self.notices:lay.addWidget(label('اعلان فعالی ندارید.'))
        publish=QPushButton('ارسال اطلاعیه / مدیریت کاربران در پنل شرکت');publish.clicked.connect(self.open_portal);v.addWidget(publish);d.exec()
    def receipt(self,item,action,dialog):dialog.accept();self.run(lambda:self.client.request('receipt',dict(id=item['id'],action=action)),lambda _:self.sync())
    def import_attendance(self):
        if not self.client:return
        path,_=QFileDialog.getOpenFileName(self,'انتخاب فایل ماهانه از فلش یا پوشه','','Attendance (*.xlsx *.csv *.txt *.tsv)')
        if not path:return
        try:
            d=AttendanceDialog(self,path)
            if d.exec()==QDialog.Accepted:
                company=self.company.currentData();rows=d.valid;month=d.month_value
                if len(rows)>10000:raise ValueError('در هر بار حداکثر ۱۰ هزار ردیف را وارد کنید.')
                self.mutation(lambda:self.client.request('attendance',dict(company=company,rows=rows,month=month)))
        except Exception as exc:QMessageBox.warning(self,'ورود تردد',str(exc))
    def export(self):
        if not self.client:return
        menu=QMenu(self);xlsx=menu.addAction('گزارش Excel');pdf=menu.addAction('گزارش PDF');payroll=menu.addAction('خروجی کارکرد ماهانه برای حقوق');backup=menu.addAction('بایگانی اطلاعات و مدارک مجاز');chosen=menu.exec(self.mapToGlobal(self.rect().center()))
        if not chosen:return
        if chosen is backup:
            def ready(value):
                from backup_bundle import create_bundle
                path,_=QFileDialog.getSaveFileName(self,'ذخیره بایگانی','Karname-Company-Export.zip','ZIP (*.zip)')
                if path:
                    extras={'company/export.json':json.dumps(value['data'],ensure_ascii=False).encode()}
                    extras.update({'company/files/'+id+'.bin':base64.b64decode(raw) for id,raw in value['attachments'].items()});create_bundle(path,self.owner.data,extras);self.offer_share(path)
            self.run(lambda:self.client.request('export',company=self.company.currentData()),ready);return
        from org_reports import flat_rows
        rows=flat_rows(self.visible)
        def save(rows):
            from org_reports import spreadsheet,pdf_report
            is_pdf=chosen is pdf;path,_=QFileDialog.getSaveFileName(self,'ذخیره گزارش','Karname-Report.'+('pdf' if is_pdf else 'xlsx'),'PDF (*.pdf)' if is_pdf else 'Excel (*.xlsx)')
            if path:
                try:(pdf_report if is_pdf else spreadsheet)(path,rows);self.offer_share(path)
                except Exception as exc:QMessageBox.warning(self,'گزارش',str(exc))
        if chosen is payroll:
            month,ok=QInputDialog.getText(self,'کارکرد ماهانه','ماه شمسی: ۱۴۰۵/۰۸',text=normalize(jformat(today_j()))[:7])
            if ok:self.run(lambda:self.client.request('payroll',company=self.company.currentData(),month=normalize(month)),save)
        else:save(rows)
    def offer_share(self,path):
        from sharing import share_file
        if QMessageBox.question(self,'فایل آماده است','فایل ذخیره شد. امکانات اشتراک‌گذاری ویندوز باز شود؟',QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:share_file(self,path)
