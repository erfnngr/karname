"""Application sign-in and manager-only account administration."""
import json,hashlib,threading,copy,shutil,re
from pathlib import Path
from PySide6.QtCore import Qt,QObject,Signal,QTimer
from PySide6.QtWidgets import (QFrame,QDialog,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,QComboBox,QCheckBox,QPushButton,QDialogButtonBox,QMessageBox,QFileDialog,QTableWidget,QTableWidgetItem,QAbstractItemView,QTabWidget,QTreeWidget,QTreeWidgetItem)
from org_client import Client,validate_url
from org_store import Store,DomainError
from ui_icons import iconize
from storage import normalize

def manager(user):return bool(user and (user['global_role'] in ('group_admin','system_admin') or any(m['role']=='company_manager' for m in user['memberships'])))
def config(root):
    try:return json.loads((Path(root)/'access-config.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}
def save_config(root,value):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);temp=root/'access-config.tmp';temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(root/'access-config.json')
class LoginSignals(QObject):
    done=Signal(object,object)
    found=Signal(object,object)

class LoginDialog(QDialog):
    def __init__(self,root,existing_server=None,locked_user=None,parent=None):
        super().__init__(parent);self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.server=existing_server;self.owns_server=False;self.locked=locked_user;self.busy=False;self.signals=LoginSignals();self.signals.done.connect(self.handle_login_result);self.setWindowTitle('ورود به کارنامه');self.setLayoutDirection(Qt.RightToLeft);self.resize(560,650);self.setMinimumWidth(480);outer=QVBoxLayout(self);outer.setContentsMargins(25,24,25,24);card=QFrame();card.setObjectName('LoginCard');v=QVBoxLayout(card);v.setContentsMargins(30,22,30,24);v.setSpacing(12);outer.addWidget(card);self.setStyleSheet('QFrame#LoginCard { background:#FFFFFF;border:1px solid #D7E2EA;border-radius:20px;} QFrame#LoginCard QLabel {color:#1A344C;} QFrame#LoginCard QLineEdit,QFrame#LoginCard QComboBox {background:#F5F8FB;color:#17364D;border:1px solid #CCD9E4;padding:10px;border-radius:9px;} QFrame#LoginCard QPushButton {background:#176E76;color:white;border:0;padding:10px;border-radius:9px;}');from brand import logo;v.addWidget(logo('کارنامه',64),0,Qt.AlignHCenter);heading=QLabel('کارنامه');heading.setAlignment(Qt.AlignCenter);heading.setObjectName('Hero');v.addWidget(heading);self.intro=QLabel('با حساب مدیر یا کارمند وارد شوید.');self.intro.setWordWrap(True);self.intro.setAlignment(Qt.AlignCenter);v.addWidget(self.intro);self.form=QFormLayout();v.addLayout(self.form);s=config(self.root)
        from chat_ui import avatar_label
        self.login_identity=QWidget();self.login_identity.setStyleSheet('background:transparent;');identity=QHBoxLayout(self.login_identity);identity.setContentsMargins(0,0,0,0);identity.addStretch();self.login_avatar=avatar_label(s.get('avatar',''),s.get('display_name','کاربر'),48);identity.addWidget(self.login_avatar);self.login_name=QLabel(s.get('display_name') or s.get('username',''));identity.addWidget(self.login_name);identity.addStretch();v.insertWidget(1,self.login_identity)
        from lan_discovery import load_profile,is_host
        self.network_profile=load_profile(self.root);self.network=None;self.discovering=False;self.dismissed=False;self.signals.found.connect(self.network_found)
        default_mode=s.get('mode','local' if is_host(self.root,self.network_profile) else 'auto' if self.network_profile else 'local')
        if self.network_profile and default_mode=='local' and not s.get('network_mode_version') and not is_host(self.root,self.network_profile):default_mode='auto'
        self.mode=QComboBox();self.mode.addItem('اطلاعات روی همین کامپیوتر','local');self.mode.addItem('نشانی دستی مرکز شرکت / اینترنت','remote');self.mode.addItem('شبکه شرکت · خودکار','auto');self.mode.setCurrentIndex(max(0,self.mode.findData(default_mode)));self.form.addRow('روش ورود:',self.mode)
        self.url=QLineEdit(s.get('url','https://'));self.url.setLayoutDirection(Qt.LeftToRight);self.form.addRow('نشانی مرکز شرکت:',self.url);self.cert=QPushButton('معرفی گواهی عمومی میزبان شرکت');self.cert.clicked.connect(self.import_certificate);v.addWidget(self.cert)
        self.find_network=QPushButton('یافتن دوباره شبکه شرکت');self.find_network.clicked.connect(self.discover_network);v.addWidget(self.find_network)
        self.first=QLineEdit();self.last=QLineEdit();self.username=QLineEdit(locked_user['username'] if locked_user else s.get('username',''));self.username.setLayoutDirection(Qt.LeftToRight);self.username.setPlaceholderText('name.lastname');self.password=QLineEdit();self.password.setEchoMode(QLineEdit.Password);self.confirm=QLineEdit();self.confirm.setEchoMode(QLineEdit.Password);self.form.addRow('نام:',self.first);self.form.addRow('نام خانوادگی:',self.last);self.form.addRow('نام کاربری انگلیسی:',self.username);self.form.addRow('رمز عبور:',self.password);self.form.addRow('تکرار رمز:',self.confirm)
        self.status=QLabel('');self.status.setWordWrap(True);v.addWidget(self.status);v.addStretch();self.buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);self.buttons.button(QDialogButtonBox.Cancel).setText('خروج');self.buttons.accepted.connect(self.submit);self.buttons.rejected.connect(self.reject);v.addWidget(self.buttons);self.mode.currentIndexChanged.connect(self.refresh);self.refresh()
        self.username.textChanged.connect(lambda value:self.login_identity.setVisible(not self.initial and value.casefold()==s.get('username','').casefold() and bool(value)))
        if locked_user:self.mode.setEnabled(False);self.url.setReadOnly(True);self.username.setReadOnly(True);self.cert.hide()
        from login_presentation import polish
        polish(self)
        self.network_timer=QTimer(self);self.network_timer.setInterval(12000);self.network_timer.timeout.connect(self.discover_network);self.network_timer.start()
    def refresh(self):
        remote=self.mode.currentData()=='remote';automatic=self.mode.currentData()=='auto';self.form.setRowVisible(self.url,remote);self.cert.setVisible(remote and not self.locked);self.find_network.setVisible(automatic);self.initial=self.mode.currentData()=='local' and not Store(self.root/'company-server').initialized();self.form.setRowVisible(self.first,self.initial);self.form.setRowVisible(self.last,self.initial);self.form.setRowVisible(self.confirm,self.initial);self.login_identity.setVisible(not self.initial and bool(config(self.root).get('username')));self.buttons.button(QDialogButtonBox.Ok).setText('ساخت مدیر اولیه و ورود' if self.initial else 'ورود');self.intro.setText('در نخستین اجرا، نام و حساب مدیر اولیه را تعیین کنید. افزودن افراد بعدی از تنظیمات ← دسترسی و فقط توسط مدیران انجام می‌شود.' if self.initial else 'شبکه شرکت خودکار پیدا می‌شود؛ با نام کاربری و رمز خود وارد شوید.' if automatic else 'برای ورود به برنامه، نام کاربری و رمز خود را وارد کنید.')
        if automatic and hasattr(self,'status'):QTimer.singleShot(100,self.discover_network)
    def discover_network(self):
        if self.discovering or self.busy or self.dismissed or self.mode.currentData()!='auto':return
        if not self.network_profile:self.status.setText('پیکربندی شبکه شرکت موجود نیست؛ روش نشانی دستی همچنان در دسترس است.');return
        self.discovering=True;self.find_network.setEnabled(False)
        if self.network is None:self.status.setText('در حال یافتن خودکار میزبان شرکت…')
        root=self.root;profile=self.network_profile
        def work():
            try:
                from lan_discovery import resolve_with_autostart
                value=resolve_with_autostart(root,profile);error=None
            except Exception as exc:value=None;error=exc
            try:self.signals.found.emit(value,error)
            except RuntimeError:pass
        threading.Thread(target=work,daemon=True).start()
    def network_found(self,value,error):
        self.discovering=False
        if self.dismissed:return
        self.find_network.setEnabled(True)
        if self.mode.currentData()!='auto' or self.busy:return
        if error:self.status.setText(str(error));return
        self.network=value;self.url.setText(value['url']);self.status.setText('شبکه شرکت پیدا شد؛ نام کاربری و رمز خود را وارد کنید.')
    def import_certificate(self):
        try:
            url=validate_url(self.url.text().strip());source,_=QFileDialog.getOpenFileName(self,'گواهی عمومی دریافت‌شده از مدیر شرکت','','Certificate (*.pem *.crt)')
            if not source:return
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes,serialization
            cert=x509.load_pem_x509_certificate(Path(source).read_bytes());fingerprint=cert.fingerprint(hashes.SHA256()).hex().upper()
            if QMessageBox.question(self,'تأیید گواهی میزبان','این اثر انگشت را با مدیر میزبان مقایسه کنید:\n'+fingerprint+'\n\nآیا یکسان است؟',QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
            folder=self.root/'trusted-certificates';folder.mkdir(exist_ok=True);(folder/(hashlib.sha256(url.encode()).hexdigest()+'.pem')).write_bytes(cert.public_bytes(serialization.Encoding.PEM));self.status.setText('گواهی معرفی شد.')
        except Exception as exc:self.status.setText(str(exc))
    def submit(self):
        if self.busy:return
        username=self.username.text().strip();password=self.password.text();first=self.first.text().strip();last=self.last.text().strip();automatic=self.mode.currentData()=='auto';remote=self.mode.currentData() in ('remote','auto');url=self.url.text().strip();initial=self.initial
        try:
            Store.clean_username(username)
            if not password:raise ValueError('رمز عبور را وارد کنید.')
            if initial and (not first or not last):raise ValueError('نام و نام خانوادگی مدیر اولیه را وارد کنید.')
            if initial and password!=self.confirm.text():raise ValueError('رمز و تکرار آن یکسان نیستند.')
            if remote and not automatic:validate_url(url)
            if automatic and not self.network_profile:raise ValueError('پیکربندی شبکه موجود نیست؛ نشانی دستی را انتخاب کنید.')
        except Exception as exc:self.status.setText(str(exc));return
        self.busy=True;self.buttons.setEnabled(False);self.status.setText('در حال بررسی حساب…')
        def work():
            try:
                network=None;fingerprint=None;origin=None
                if automatic:
                    from lan_discovery import resolve_with_autostart
                    from offline_cache import OfflineCache
                    origin='network://'+self.network_profile['fingerprint']
                    try:network=resolve_with_autostart(self.root,self.network_profile,timeout=.7)
                    except Exception:
                        cache=OfflineCache(self.root/'company-cache',origin,username,password)
                        if cache.path.exists():
                            snapshot=cache.load();self.signals.done.emit(dict(user=snapshot['user'],client=None,local_server=None,offline_snapshot=snapshot),None);return
                        raise
                if not remote:
                    store=Store(self.root/'company-server')
                    if initial:store.bootstrap(username,password,(first+' '+last).strip(),first,last)
                    if not self.server:
                        from org_http import RunningServer
                        self.server=RunningServer(self.root/'company-server','127.0.0.1',0);self.owns_server=True
                    target='http://127.0.0.1:'+str(self.server.port);certificate=None
                else:
                    target=network['url'] if network else validate_url(url);path=self.root/'trusted-certificates'/(hashlib.sha256(target.encode()).hexdigest()+'.pem');certificate=network['certificate'] if network else str(path) if path.exists() else None;fingerprint=network['fingerprint'] if network else None
                client=Client(target,certificate,fingerprint)
                try:user=client.login(username,password)
                except DomainError as exc:
                    if remote and exc.status==503:
                        from offline_cache import OfflineCache
                        cache=OfflineCache(self.root/'company-cache',origin or target,username,password)
                        if cache.path.exists():
                            snapshot=cache.load();self.signals.done.emit(dict(user=snapshot['user'],client=None,local_server=None,offline_snapshot=snapshot),None);return
                    raise
                from offline_cache import OfflineCache
                client.cache=OfflineCache(self.root/'company-cache',origin or (target if remote else 'local://karname'),username,password)
                self.signals.done.emit(dict(user=user,client=client,local_server=self.server if not remote else None,network=network),None)
            except Exception as exc:self.signals.done.emit(None,exc)
        threading.Thread(target=work,daemon=True).start()
    def handle_login_result(self,value,error):
        self.busy=False;self.buttons.setEnabled(True)
        if error:self.status.setText(str(error));self.password.clear();return
        if self.locked and value['user']['id']!=self.locked['id']:self.status.setText('این حساب با حساب نشست قبلی متفاوت است؛ برنامه را کامل ببندید و دوباره وارد شوید.');return
        if value.get('network'):self.network=value['network'];self.url.setText(self.network['url'])
        settings=config(self.root);settings.update(mode=self.mode.currentData(),url=self.url.text().strip() if self.mode.currentData() in ('remote','auto') else '',username=self.username.text().strip())
        if self.mode.currentData()=='auto' and self.network_profile:settings['server_identity']=self.network_profile['fingerprint']
        settings.update(avatar=value['user'].get('profile',{}).get('avatar',''),display_name=value['user']['fullname'])
        settings['network_mode_version']=1
        if self.initial:settings.setdefault('legacy_owner',value['user']['id'])
        save_config(self.root,settings);self.session=value;self.password.clear();self.confirm.clear();self.network_timer.stop();self.accept()
    def reject(self):
        if self.busy:return
        self.dismissed=True
        self.network_timer.stop()
        if self.owns_server and self.server:self.server.close();self.server=None
        super().reject()

def user_profile(root,user):
    """Legacy personal records go only to the first local manager, never to staff."""
    from storage import set_profile,load_data,save_data
    if not re.fullmatch(r'[0-9a-f]{32}',str(user.get('id',''))):raise ValueError('شناسه حساب معتبر نیست.')
    root=Path(root);folder=root/'profiles'/user['id'];fresh=not (folder/'calendar.json').exists();folder.mkdir(parents=True,exist_ok=True);settings=config(root)
    if fresh and settings.get('legacy_owner')==user['id'] and (root/'calendar.json').exists():shutil.copy2(root/'calendar.json',folder/'calendar.json')
    set_profile(folder)
    if fresh:
        data=load_data()
        if user['global_role'] not in ('group_admin','system_admin'):
            allowed=[m.get('company_name','') for m in user['memberships']]
            data['events']=[e for e in data['events'] if manager(user) and any(name and name in e.get('company','') for name in allowed)];data['companies']=allowed;data['source_duplicate_archive']=[];save_data(data)
    return folder

class UserDialog(QDialog):
    def __init__(self,panel,person=None,group='employee'):
        super().__init__(panel);self.setLayoutDirection(Qt.RightToLeft);self.panel=panel;self.person=person;self.setWindowTitle('ویرایش حساب' if person else 'حساب تازه');self.resize(600,640);v=QVBoxLayout(self);f=QFormLayout();v.addLayout(f);person=person or {};parts=person.get('fullname','').split(' ',1);self.first=QLineEdit(person.get('first_name') or (parts[0] if parts else ''));self.last=QLineEdit(person.get('last_name') or (parts[1] if len(parts)>1 else ''));self.username=QLineEdit(person.get('username',''));self.username.setLayoutDirection(Qt.LeftToRight);self.password=QLineEdit();self.password.setEchoMode(QLineEdit.Password);self.confirm=QLineEdit();self.confirm.setEchoMode(QLineEdit.Password)
        f.addRow('نام:',self.first);f.addRow('نام خانوادگی:',self.last);f.addRow('نام کاربری انگلیسی:',self.username);f.addRow('رمز تازه:' if person else 'رمز عبور:',self.password);f.addRow('تکرار رمز:',self.confirm);self.group=QComboBox();self.group.addItem('کارکنان','employee');self.group.addItem('مدیران','manager');self.group.setCurrentIndex(1 if (manager(person) if person else group=='manager') else 0)
        f.addRow('گروه:',self.group);self.active=QCheckBox('حساب فعال باشد');self.active.setChecked(bool(person.get('active',True)));f.addRow(self.active);self.all=QCheckBox('مدیر کل همه شرکت‌ها و مدیریت تمام دسترسی‌ها');self.all.setChecked(person.get('global_role')=='group_admin');self.all.setEnabled(panel.actor['global_role']=='group_admin');f.addRow(self.all)
        self.scopes=[];table=QTableWidget(len(panel.companies),3);table.setHorizontalHeaderLabels(['دسترسی','شرکت','سطح کاری']);table.horizontalHeader().setStretchLastSection(True);v.addWidget(table)
        for i,company in enumerate(panel.companies):
            old=next((m for m in person.get('memberships',[]) if m['company_id']==company['id']),None);check=QCheckBox();check.setChecked(bool(old));table.setCellWidget(i,0,check);table.setItem(i,1,QTableWidgetItem(company['name']));role=QComboBox()
            for key,name in [('employee','کارمند'),('finance','مسئول مالی'),('team_lead','سرپرست واحد'),('auditor','ناظر / حسابرس'),('company_manager','مدیر شرکت')]:role.addItem(name,key)
            role.setCurrentIndex(max(0,role.findData(old['role'] if old else 'company_manager' if group=='manager' else 'employee')));table.setCellWidget(i,2,role);self.scopes.append((company,check,role,old))
        if person.get('global_role')=='group_admin':
            self.group.setEnabled(False);self.active.setEnabled(False);self.all.setEnabled(False)
            for _,check,role,_ in self.scopes:check.setEnabled(False);role.setEnabled(False)
        self.department=QLineEdit(next((m.get('department','') for m in person.get('memberships',[])),''));f.addRow('واحد:',self.department);self.group.currentIndexChanged.connect(self.group_changed);self.group_changed(False);note=QLabel('برای حفظ رمز قبلی، دو کادر رمز را خالی بگذارید. رمز قبلی نمایش داده نمی‌شود. مدیر شرکت فقط حساب‌های محدوده خودش را مدیریت می‌کند.');note.setWordWrap(True);v.addWidget(note);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);iconize(buttons.button(QDialogButtonBox.Save),'save','ذخیره حساب');buttons.button(QDialogButtonBox.Cancel).setText('بازگشت');buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);v.addWidget(buttons)
    def group_changed(self,changed=True):
        is_manager=self.group.currentData()=='manager';self.all.setVisible(is_manager)
        if not is_manager:self.all.setChecked(False)
        if changed:
            for co,check,role,old in self.scopes:role.setCurrentIndex(role.findData('company_manager' if is_manager else 'employee'))
    def validate(self):
        try:
            first=self.first.text().strip();last=self.last.text().strip();username=Store.clean_username(self.username.text());password=self.password.text()
            if not first or not last:raise ValueError('نام و نام خانوادگی را وارد کنید.')
            if not self.person or password:
                if not password:raise ValueError('رمز عبور را وارد کنید.')
                if password!=self.confirm.text():raise ValueError('رمز و تکرار آن یکسان نیستند.')
            memberships=[dict(company_id=co['id'],role=role.currentData(),department=self.department.text().strip(),permissions=(old or {}).get('permissions',{})) for co,check,role,old in self.scopes if check.isChecked()]
            if self.person and self.person.get('global_role')=='group_admin':memberships=copy.deepcopy(self.person.get('memberships',[]))
            global_role='group_admin' if self.all.isChecked() else 'system_admin' if self.person and self.person['global_role']=='system_admin' else 'employee'
            if global_role=='employee' and not memberships:raise ValueError('حداقل یک شرکت را برای این حساب انتخاب کنید.')
            self.payload=dict(id=self.person['id'] if self.person else None,first_name=first,last_name=last,fullname=first+' '+last,username=username,password=password,active=self.active.isChecked(),global_role=global_role,memberships=memberships);self.accept()
        except Exception as exc:QMessageBox.warning(self,'حساب کاربری',str(exc))

class PermissionDialog(QDialog):
    """Per-company module grants. Record and room authorization still applies."""
    def __init__(self,panel,person):
        super().__init__(panel);self.panel=panel;self.person=person;self.result_payload=None;self.setLayoutDirection(Qt.RightToLeft);self.setWindowTitle('دسترسی بخش‌ها · '+person['fullname']);self.resize(650,680);v=QVBoxLayout(self);hint=QLabel('دسترسی برای هر شرکت جداست. دسترسی به یک بخش، مالکیت داده و سطح شرکت را تغییر نمی‌دهد. برای محافظت از مدیریت، دسترسی مدیر کل و حساب فعلی از این صفحه قابل تغییر نیست.');hint.setWordWrap(True);v.addWidget(hint)
        self.company=QComboBox();self.scopes=[]
        from permission_policy import allowed
        for co in panel.companies:
            member=next((m for m in person.get('memberships',[]) if m['company_id']==co['id']),None)
            if member and (panel.actor['global_role']=='group_admin' or allowed(panel.actor,co['id'],'access','manage') and any(m['company_id']==co['id'] and m['role']=='company_manager' for m in panel.actor['memberships'])):self.scopes.append((co,member));self.company.addItem(co['name'],co['id'])
        row=QHBoxLayout();row.addWidget(QLabel('شرکت'));row.addWidget(self.company,1);v.addLayout(row);self.tree=QTreeWidget();self.tree.setHeaderLabels(['بخش / عملیات','مجاز']);self.tree.setAlternatingRowColors(True);self.tree.setColumnWidth(0,410);v.addWidget(self.tree,1);self.tip=QLabel('هر علامت، اجازه یک عملیات را تعیین می‌کند. وقتی نمایش یک بخش غیرفعال شود، عملیات آن نیز اجرا نمی‌شود.');self.tip.setWordWrap(True);v.addWidget(self.tip);self.tree.itemChanged.connect(self.changed);self.company.currentIndexChanged.connect(self.load_scope);self.load_scope()
        defaults=QPushButton('بازگردانی پیش‌فرض نقش');defaults.clicked.connect(self.defaults);v.addWidget(defaults);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('ذخیره دسترسی');buttons.button(QDialogButtonBox.Save).setEnabled(bool(self.scopes));buttons.button(QDialogButtonBox.Cancel).setText('بستن');buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);v.addWidget(buttons)
    def load_scope(self):
        from permission_policy import MODULE_REGISTRY,baseline_allowed
        self.tree.blockSignals(True);self.tree.clear();self.items={};i=self.company.currentIndex()
        if 0<=i<len(self.scopes):
            co,member=self.scopes[i];overrides=member.get('permissions') or {};role=member['role']
            for key,meta in MODULE_REGISTRY.items():
                group=QTreeWidgetItem(self.tree,[meta['title'],'']);group.setExpanded(True);children={}
                for action,title in meta['actions'].items():
                    item=QTreeWidgetItem(group,[title,'']);item.setData(0,Qt.UserRole,(key,action));item.setFlags(item.flags()|Qt.ItemIsUserCheckable);value=overrides.get('module.'+key+'.'+action,baseline_allowed(role,key,action));item.setCheckState(1,Qt.Checked if value is True else Qt.Unchecked);children[action]=item
                self.items[key]=children
            for children in self.items.values():self.apply_enabled(children)
        self.tree.blockSignals(False)
    def apply_enabled(self,children):
        view=children['view'].checkState(1)==Qt.Checked
        for action,item in children.items():
            if action!='view':item.setDisabled(not view)
    def changed(self,item,column):
        data=item.data(0,Qt.UserRole)
        if data and data[1]=='view':self.apply_enabled(self.items[data[0]])
    def defaults(self):
        from permission_policy import baseline_allowed
        if self.company.currentIndex()<0:return
        role=self.scopes[self.company.currentIndex()][1]['role'];self.tree.blockSignals(True)
        for key,children in self.items.items():
            for action,item in children.items():item.setCheckState(1,Qt.Checked if baseline_allowed(role,key,action) else Qt.Unchecked)
            self.apply_enabled(children)
        self.tree.blockSignals(False)
    def validate(self):
        from permission_policy import baseline_allowed,validate_overrides
        i=self.company.currentIndex()
        if not 0<=i<len(self.scopes):return
        co,member=self.scopes[i];role=member['role'];old=member.get('permissions') or {};result={k:v for k,v in old.items() if not k.startswith('module.')}
        for key,children in self.items.items():
            for action,item in children.items():
                value=item.checkState(1)==Qt.Checked
                if value!=baseline_allowed(role,key,action):result['module.'+key+'.'+action]=value
        try:self.result_payload=dict(user_id=self.person['id'],company=co['id'],permissions=validate_overrides(result));self.accept()
        except ValueError as e:QMessageBox.warning(self,'دسترسی',str(e))

class AccessPanel(QWidget):
    def __init__(self,owner,parent=None):
        super().__init__(parent);self.owner=owner;self.client=getattr(owner.org,'client',None);self.actor=getattr(owner,'session_user',None) or (self.client.user if self.client else None);self.people=[];self.companies=[];v=QVBoxLayout(self);self.status=QLabel('ساخت حساب و تعیین رمز فقط برای مدیران فعال است.');self.status.setWordWrap(True);v.addWidget(self.status);self.tabs=QTabWidget();self.tables={}
        for key,title in [('manager','مدیران'),('employee','کارکنان')]:
            table=QTableWidget(0,4);table.setHorizontalHeaderLabels(['نام','نام خانوادگی','نام کاربری','وضعیت']);table.setSelectionBehavior(QAbstractItemView.SelectRows);table.setEditTriggers(QAbstractItemView.NoEditTriggers);table.horizontalHeader().setStretchLastSection(True);table.doubleClicked.connect(self.edit);self.tables[key]=table;self.tabs.addTab(table,title)
        self.search=QLineEdit();self.search.setPlaceholderText('جستجوی نام یا نام کاربری');self.search.textChanged.connect(self.render_people);v.addWidget(self.search);v.addWidget(self.tabs);row=QHBoxLayout();self.buttons=[]
        for name,key,fn in [('افزودن کاربر','add',self.add),('ویرایش حساب / تعیین رمز تازه','edit',self.edit),('سطح دسترسی بخش‌ها','settings',self.edit_permissions),('تازه‌سازی','refresh',self.load)]:
            b=QPushButton(name);iconize(b,key);b.clicked.connect(fn);row.addWidget(b);self.buttons.append(b)
        from permission_policy import any_allowed
        row.addStretch();v.addLayout(row);self.signals=LoginSignals();self.signals.done.connect(self.finished);self.busy=False;self.allowed=bool(self.client and manager(self.actor) and any_allowed(self.actor,'access','view'));self.can_manage=bool(self.allowed and any_allowed(self.actor,'access','manage'))
        self.set_button_states()
        if self.allowed:QTimer.singleShot(0,self.load)
        else:self.status.setText('نمایش یا مدیریت دسترسی‌ها برای این حساب فعال نیست، یا اتصال مرکز برقرار نیست.')
    def set_button_states(self):
        for b in self.buttons[:-1]:b.setEnabled(self.can_manage and not self.busy)
        self.buttons[-1].setEnabled(self.allowed and not self.busy)
    def run(self,fn,done):
        if self.busy or not self.allowed:return
        self.busy=True;self.callback=done
        self.set_button_states()
        client=Client(self.client.url,self.client.session.verify if isinstance(self.client.session.verify,str) else None,getattr(self.client,'fingerprint',None));client.token=self.client.token;self.worker_client=client
        def work():
            try:self.signals.done.emit(fn(client),None)
            except Exception as exc:self.signals.done.emit(None,exc)
        threading.Thread(target=work,daemon=True).start()
    def finished(self,value,error):
        self.busy=False
        self.set_button_states()
        if error:self.status.setText(str(error));return
        self.callback(value)
    def load(self):
        def ready(value):
            self.people=value['users'];self.companies=value['companies'];self.render_people()
            self.status.setText('مدیران و کارکنان · حساب انتخاب‌شده با نماد ویرایش قابل تغییر است.')
        self.run(lambda c:dict(users=c.request('users'),companies=c.request('companies')),ready)
    def render_people(self,*_):
        query=normalize(self.search.text()).casefold().strip();self.visible={key:[p for p in self.people if manager(p)==(key=='manager') and (not query or query in normalize(p['fullname']+' '+p['username']).casefold())] for key in self.tables}
        for key,table in self.tables.items():
            table.setRowCount(len(self.visible[key]))
            for i,p in enumerate(self.visible[key]):
                parts=p['fullname'].split(' ',1)
                for j,val in enumerate([p.get('first_name') or parts[0],p.get('last_name') or (parts[1] if len(parts)>1 else ''),p['username'],'فعال' if p['active'] else 'غیرفعال']):table.setItem(i,j,QTableWidgetItem(val))
    def add(self):self.open_user(None)
    def edit(self,*_):
        key='manager' if self.tabs.currentIndex()==0 else 'employee';row=self.tables[key].currentRow()
        if 0<=row<len(getattr(self,'visible',{}).get(key,[])):self.open_user(self.visible[key][row])
    def edit_permissions(self):
        if not self.can_manage:return
        key='manager' if self.tabs.currentIndex()==0 else 'employee';row=self.tables[key].currentRow();people=getattr(self,'visible',{}).get(key,[])
        if not 0<=row<len(people):QMessageBox.information(self,'دسترسی','ابتدا یک کاربر را انتخاب کنید.');return
        person=people[row]
        if person['id']==self.actor['id'] or person['global_role']=='group_admin':QMessageBox.information(self,'دسترسی','دسترسی مدیر کل و حساب فعلی قابل تغییر نیست.');return
        d=PermissionDialog(self,person)
        if not d.scopes:QMessageBox.information(self,'دسترسی','این حساب در شرکت تحت مدیریت شما عضویت قابل ویرایش ندارد.');return
        if d.exec()!=QDialog.Accepted:return
        def ready(_):self.owner.data['company_write_at']=__import__('datetime').datetime.now().isoformat();self.owner.persist();self.owner.org.revision=None;self.load()
        self.run(lambda c:c.request('permissions',d.result_payload),ready)
    def open_user(self,person):
        if not self.can_manage or self.busy:return
        if person and person.get('global_role')=='group_admin' and person['id']!=self.actor['id']:QMessageBox.information(self,'دسترسی','فقط خود مدیر کل می‌تواند مشخصات و رمز حسابش را ویرایش کند.');return
        dialog=UserDialog(self,person,'manager' if self.tabs.currentIndex()==0 else 'employee')
        if dialog.exec()!=QDialog.Accepted:return
        def ready(_):
            self.owner.data['company_write_at']=__import__('datetime').datetime.now().isoformat();self.owner.persist();self.owner.org.revision=None
            if person and person['id']==self.actor['id'] and getattr(self.owner,'session_user',None):
                self.window().reject();QTimer.singleShot(0,self.owner.lock_session)
            else:self.load()
        self.run(lambda c:c.request('users',dialog.payload),ready)
