"""Explicit controls for encryption, retention, network diagnostics and updates."""
import os,sys,copy,threading,json,hashlib,shutil,uuid
from pathlib import Path
from PySide6.QtCore import Qt,QObject,Signal,QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QLineEdit,QComboBox,QCheckBox,QSpinBox,QPushButton,QFileDialog,QMessageBox,QInputDialog,QScrollArea
from storage import app_dir
from local_vault import load,save

class ToolSignals(QObject):done=Signal(object,object,object)

class EnhancementSettings(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.signals=ToolSignals();self.signals.done.connect(self.finished);self.pending_password=None;self.busy=False;v=QVBoxLayout(self);area=QScrollArea();area.setWidgetResizable(True);body=QWidget();f=QFormLayout(body);area.setWidget(body);v.addWidget(area);s=owner.data['settings'];self.density=QComboBox();self.density.addItem('راحت','comfortable');self.density.addItem('فشرده','compact');self.density.setCurrentIndex(max(0,self.density.findData(s.get('density','comfortable'))));f.addRow('فاصله و تراکم نمایش',self.density)
        self.encrypt=QCheckBox('پشتیبان‌های جدید رمزگذاری شوند');self.encrypt.setChecked(s.get('backup_encrypt',False));f.addRow(self.encrypt);pw=QPushButton('تعیین / تغییر رمز پشتیبان');pw.clicked.connect(self.password);f.addRow(pw);self.auto=QCheckBox('پشتیبان روزانه و هفتگی هنگام بازبودن برنامه');self.auto.setChecked(s.get('backup_auto_enabled',False));f.addRow(self.auto);self.folder=QLineEdit(s.get('backup_folder',''));self.folder.setPlaceholderText(str(app_dir()/'backups'/'automatic'));self.second=QLineEdit(s.get('backup_second_folder',''))
        backup_rows=[]
        for title,w in [('پوشه پشتیبان',self.folder),('محل دوم؛ فلش / پوشه شبکه',self.second)]:
            row=QHBoxLayout();row.addWidget(w);b=QPushButton('انتخاب');b.clicked.connect(lambda checked=False,w=w:self.choose_folder(w));row.addWidget(b);f.addRow(title,row);backup_rows.append(row)
        self.daily=QSpinBox();self.daily.setRange(1,365);self.daily.setValue(s.get('backup_keep_daily',7));self.weekly=QSpinBox();self.weekly.setRange(1,365);self.weekly.setValue(s.get('backup_keep_weekly',4));f.addRow('تعداد نسخه روزانه',self.daily);f.addRow('تعداد نسخه هفتگی',self.weekly);backup=QPushButton('آزمایش پشتیبان خودکار با تنظیمات ذخیره‌شده');backup.clicked.connect(lambda:owner.v8.backup(True));f.addRow(backup);hint=QLabel('رمز را جدا از فایل پشتیبان نگه دارید؛ برای بازیابی روی دستگاه دیگر لازم است. نسخه‌های قدیمی بدون رمز همچنان قابل بازیابی‌اند. اگر محل دوم در دسترس نباشد، خطا نمایش داده می‌شود و نسخه اصلی حفظ می‌شود.');hint.setWordWrap(True);f.addRow(hint)
        self.host_auto=QCheckBox('اجرای مستقل مرکز پس از ورود همین حساب به ویندوز');self.host_auto.setChecked(__import__('network_tools').autohost_enabled(owner.base_dir,s.get('host_auto',False)));self.host_auto.setEnabled(owner.can_backup_server());f.addRow(self.host_auto);host_note=QLabel('این گزینه با اختیار مدیر کل میزبان فعال می‌شود؛ کامپیوتر باید روشن و حساب ویندوز وارد شده باشد. مرکز می‌تواند بدون بازکردن صفحه ورود برنامه پاسخ دهد.');host_note.setWordWrap(True);f.addRow(host_note);self.url=QLineEdit(getattr(owner.org.client,'url',None) or s.get('company_url',''));self.url.setLayoutDirection(Qt.LeftToRight);f.addRow('نشانی برای آزمایش اتصال',self.url);diag=QPushButton('آزمایش نشانی، درگاه و گواهی');diag.clicked.connect(self.diagnostics);f.addRow(diag)
        self.feed=QLineEdit(s.get('update_feed',''));self.feed.setPlaceholderText('https://...  اختیاری؛ فهرست امضاشده شرکت');self.feed.setLayoutDirection(Qt.LeftToRight);f.addRow('منبع نسخه‌های جدید',self.feed);row=QHBoxLayout()
        for title,fn in [('بررسی نسخه جدید',self.check_update),('بازکردن بسته به‌روزرسانی',self.update),('برگشت به نسخه قبل',self.rollback)]:b=QPushButton(title);b.clicked.connect(fn);row.addWidget(b)
        f.addRow(row);self.status=QLabel();self.status.setTextInteractionFlags(Qt.TextSelectableByMouse);self.status.setWordWrap(True);v.addWidget(self.status)
        from ui_permissions import allowed
        self.can_backup=allowed(owner,'backup','personal');self.can_network=allowed(owner,'network')
        for item in [self.encrypt,pw,self.auto,self.daily,self.weekly,backup,hint,*backup_rows]:f.setRowVisible(item,self.can_backup)
        for item in [self.host_auto,host_note,self.url,diag]:f.setRowVisible(item,self.can_network)
    def choose_folder(self,w):
        path=QFileDialog.getExistingDirectory(self,'انتخاب پوشه')
        if path:w.setText(path)
    def password(self):
        value,ok=QInputDialog.getText(self,'رمز پشتیبان','رمز قابل نگهداری برای بازیابی:',QLineEdit.Password)
        if not ok:return
        again,ok=QInputDialog.getText(self,'تکرار رمز','همان رمز را دوباره وارد کنید:',QLineEdit.Password)
        if ok and value and value==again:self.pending_password=value;self.encrypt.setChecked(True);self.status.setText('رمز پس از ذخیره تنظیمات اعمال می‌شود. آن را برای بازیابی روی دستگاه دیگر نگه دارید.')
        else:self.status.setText('رمزها یکسان و غیرخالی باشند.')
    def values(self):
        if self.can_backup and (self.encrypt.isChecked() or self.auto.isChecked()) and not (self.pending_password or load(app_dir()/'backup-secret.dpapi',{}).get('password')):raise ValueError('ابتدا رمز پشتیبان را تعیین کنید.')
        if self.second.text() and Path(self.second.text()).resolve()==Path(self.folder.text() or app_dir()/'backups'/'automatic').resolve():raise ValueError('محل دوم باید با محل اصلی متفاوت باشد.')
        return dict(density=self.density.currentData(),backup_encrypt=self.encrypt.isChecked(),backup_auto_enabled=self.auto.isChecked(),backup_folder=self.folder.text().strip(),backup_second_folder=self.second.text().strip(),backup_keep_daily=self.daily.value(),backup_keep_weekly=self.weekly.value(),host_auto=self.host_auto.isChecked(),update_feed=self.feed.text().strip())
    def commit(self):
        if self.pending_password:save(app_dir()/'backup-secret.dpapi',{'password':self.pending_password})
        old=__import__('network_tools').autohost_enabled(self.owner.base_dir,self.owner.data['settings'].get('host_auto',False))
        if old!=self.host_auto.isChecked():
            if not self.owner.can_backup_server():raise ValueError('اجرای مستقل مرکز فقط توسط مدیر کل فعال همین میزبان تنظیم می‌شود.')
            from network_tools import set_autohost
            set_autohost(self.owner.base_dir,self.host_auto.isChecked())
    def run(self,fn,callback):
        if self.busy:return
        self.busy=True;self.status.setText('در حال بررسی…')
        def work():
            try:self.signals.done.emit(fn(),None,callback)
            except Exception as e:self.signals.done.emit(None,e,callback)
        threading.Thread(target=work,daemon=True).start()
    def finished(self,value,error,callback):
        self.busy=False
        if error:self.status.setText(str(error))
        else:callback(value)
    def diagnostics(self):
        from network_tools import diagnose
        url=self.url.text().strip();cert=self.owner.org.certificate(url.rstrip('/'));self.run(lambda:diagnose(url,cert),lambda rows:self.status.setText('\n'.join(('✓ ' if r['ok'] else '× ')+r['step']+' · '+r.get('message','') for r in rows)))
    def check_update(self):
        from updater import feed,version,CURRENT
        from urllib.parse import urlsplit
        url=self.feed.text().strip()
        if not url:self.status.setText('منبع به‌روزرسانی هنوز تعیین نشده است؛ می‌توانید بسته امضاشده را از فایل باز کنید.');return
        p=urlsplit(url);origin=p.scheme+'://'+p.netloc;cert=self.owner.org.certificate(origin) or True
        def show(m):
            is_new=version(m['version'])>version(CURRENT);self.status.setText(('نسخه جدید: ' if is_new else 'نسخه فعلی به‌روز است: ')+m['version']+'\n'+m.get('notes',''))
            if is_new and m.get('url') and QMessageBox.question(self,'نسخه جدید','نسخه '+m['version']+' پیدا شد. بسته را دریافت و بررسی کنیم؟',QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:
                from updater import download_package
                update_url=m['url'];u=urlsplit(update_url);update_cert=self.owner.org.certificate(u.scheme+'://'+u.netloc) or True
                self.run(lambda:download_package(update_url,self.owner.base_dir,m['version'],update_cert),lambda result:self.confirm_update(result[0],result[1]))
        self.run(lambda:feed(url,cert),show)
    def update(self):
        if not getattr(sys,'frozen',False):self.status.setText('اعمال به‌روزرسانی در نسخه اجرایی ویندوز فعال است؛ بررسی بسته در نسخه کد نیز ممکن است.')
        path,_=QFileDialog.getOpenFileName(self,'بسته امضاشده کارنامه','','Karname Update (*.karname-update *.zip)')
        if not path:return
        from updater import inspect_package
        self.run(lambda:inspect_package(path),lambda m:self.confirm_update(path,m))
    def confirm_update(self,path,manifest):
        if not getattr(sys,'frozen',False):self.status.setText('بسته معتبر · نسخه '+manifest['version']);return
        if QMessageBox.question(self,'به‌روزرسانی بررسی‌شده','نسخه '+manifest['version']+' آماده است. ابتدا پشتیبان می‌گیرید و سپس برنامه برای جایگزینی بسته می‌شود. ادامه؟',QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        if not self.owner.backup_now():return
        try:
            from updater import stage_package,launch_helper
            stage,m=stage_package(path,self.owner.base_dir);self.prepare_update(stage)
        except Exception as e:self.status.setText(str(e))
    def prepare_update(self,stage):
        from updater import launch_helper
        from network_tools import stop_autohost
        root=self.owner.base_dir;stop_autohost(root);launch_helper(stage,sys.executable,root);self.owner._updating=True;self.owner._exit_approved=True;self.owner.exit_app()
    def rollback(self):
        from updater import stage_rollback
        folder=self.owner.base_dir/'updates';histories=sorted([p for p in folder.glob('previous-*') if (p/'installed.ok').is_file() and (p/'rollback.json').is_file()],key=lambda p:p.stat().st_mtime,reverse=True)
        if not histories:self.status.setText('نسخه قبلیِ ثبت‌شده‌ای برای برگشت وجود ندارد.');return
        if not getattr(sys,'frozen',False):self.status.setText('برگشت در نسخه اجرایی ویندوز انجام می‌شود.');return
        if QMessageBox.question(self,'برگشت نسخه','از اطلاعات فعلی پشتیبان گرفته شود و نسخه اجرایی قبلی برگردد؟ داده‌ها از فایل پشتیبان خودکار جایگزین نمی‌شوند.',QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        if not self.owner.backup_now():return
        try:stage=stage_rollback(histories[0],self.owner.base_dir);self.prepare_update(stage)
        except Exception as e:self.status.setText(str(e))
