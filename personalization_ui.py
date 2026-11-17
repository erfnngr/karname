"""Account-scoped presentation settings, company cards and recovery controls."""
import copy,base64,threading
from pathlib import Path
from PySide6.QtCore import Qt,QObject,Signal,QEventLoop,QBuffer,QIODevice
from PySide6.QtGui import QPixmap,QImage
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QFormLayout,QLabel,QLineEdit,QPlainTextEdit,QCheckBox,QPushButton,QListWidget,QListWidgetItem,QDialog,QDialogButtonBox,QSpinBox,QMessageBox,QFileDialog,QProgressDialog)
from color_wheel import ColorWheelDialog
from ui_icons import iconize
from chat_ui import avatar_label,circular_avatar
from storage import MONTHS,fa,today_j,month_last_day

MODULES=[('home','خانه'),('month','ماه جاری'),('calendar','تقویم'),('occasions','مناسبت‌ها'),('calculation','محاسبه'),('tax','مالیات'),('services','سامانه‌ها'),('news','خبرها'),('company','فضای شرکت'),('chat','چت'),('desk','کارتابل من'),('workspace','کارها و پیگیری‌ها'),('attendance','تردد و ساعت کار'),('assistant','کارنامه'),('clients','مشتریان')]
DEFAULT_HELP='از نوار بالای صفحه بخش دلخواه را باز کنید.\nدر تقویم روی روز یا نام ماه و سال کلیک کنید.\nیادآورها در تنظیمات شخصی‌سازی می‌شوند.\nبرای همکاری اعضا، مدیر مرکز شرکت را روی شبکه راه‌اندازی می‌کند.\nدر تنظیمات ← بازیابی می‌توانید پشتیبان بسازید یا برگردانید.'

class CallSignals(QObject):done=Signal(object,object)
def request_wait(owner,path,payload=None,_quiet=False,**query):
    client=owner.org.client
    if not client:raise ValueError('برای این تغییر به مرکز شرکت متصل شوید.')
    from org_client import Client
    worker=Client(client.url,client.session.verify if isinstance(client.session.verify,str) else None,getattr(client,'fingerprint',None));worker.token=client.token;signal=CallSignals();loop=QEventLoop();result={};progress=None if _quiet else QProgressDialog('در حال ذخیره اطلاعات…',None,0,0,owner)
    if progress:progress.setWindowModality(Qt.ApplicationModal)
    def done(value,error):result.update(value=value,error=error);loop.quit()
    signal.done.connect(done)
    def run():
        try:signal.done.emit(worker.request(path,payload,**query),None)
        except Exception as e:signal.done.emit(None,e)
        finally:worker.session.close()
    if progress:progress.show()
    threading.Thread(target=run,daemon=True).start();loop.exec()
    from shiboken6 import isValid
    if progress and isValid(progress):progress.close()
    if 'error' not in result:raise RuntimeError('درخواست پیش از تکمیل متوقف شد.')
    if result['error']:raise result['error']
    return result['value']

def choose_image(parent):
    path,_=QFileDialog.getOpenFileName(parent,'انتخاب تصویر','','Image (*.png *.jpg *.jpeg)')
    if not path:return None
    if Path(path).stat().st_size>15*1024*1024:raise ValueError('تصویر حداکثر ۱۵ مگابایت باشد.')
    image=QImage(path)
    if image.isNull():raise ValueError('تصویر خوانده نشد.')
    image=image.scaled(256,256,Qt.KeepAspectRatio,Qt.SmoothTransformation);buf=QBuffer();buf.open(QIODevice.WriteOnly);image.save(buf,'PNG');return base64.b64encode(bytes(buf.data())).decode()

class PersonalPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;profile=(owner.session_user or {}).get('profile',{});self.avatar=profile.get('avatar','');self.color=profile.get('color','#DDEBF8');self.original=copy.deepcopy(owner.data.get('preferences',{}));v=QVBoxLayout(self);row=QHBoxLayout();self.preview=avatar_label(self.avatar,(owner.session_user or {}).get('fullname','کاربر'),58);row.addWidget(self.preview)
        for title,fn in [('انتخاب عکس',self.photo),('حذف عکس',self.remove_photo),('رنگ پیام‌های من',self.chat_color)]:b=QPushButton(title);b.clicked.connect(fn);row.addWidget(b)
        row.addStretch();v.addLayout(row);f=QFormLayout();v.addLayout(f);self.calendar_name=QLineEdit(self.original.get('calendar_name','تقویم'));f.addRow('نام بخش تقویم',self.calendar_name)
        from PySide6.QtWidgets import QComboBox
        from birthday_service import MISSING_DAY_POLICIES,parse_birthday
        saved_bday=None
        try:saved_bday=parse_birthday(self.original.get('birthday'))
        except ValueError:saved_bday=None
        bday_row=QHBoxLayout();bday_row.setSpacing(6)
        self.birthday_enabled=QCheckBox('ثبت تاریخ تولد (شمسی)');self.birthday_enabled.setChecked(bool(saved_bday))
        self.birthday_day=QComboBox();self.birthday_month=QComboBox();self.birthday_year=QComboBox()
        cur_j=today_j().year
        for d in range(1,32):self.birthday_day.addItem(fa(d),d)
        for m_idx,m_name in enumerate(MONTHS,1):self.birthday_month.addItem(m_name,m_idx)
        for yr in range(cur_j,1299,-1):self.birthday_year.addItem(fa(yr),yr)
        self.birthday_policy=QComboBox()
        for pk,ptitle in MISSING_DAY_POLICIES:self.birthday_policy.addItem(ptitle,pk)
        if saved_bday:
            self.birthday_year.setCurrentIndex(max(0,self.birthday_year.findData(saved_bday['year'])))
            self.birthday_month.setCurrentIndex(max(0,self.birthday_month.findData(saved_bday['month'])))
            self.birthday_day.setCurrentIndex(max(0,self.birthday_day.findData(saved_bday['day'])))
            self.birthday_policy.setCurrentIndex(max(0,self.birthday_policy.findData(saved_bday.get('missing_day_policy','last_day_of_month'))))
        else:
            self.birthday_year.setCurrentIndex(max(0,self.birthday_year.findData(min(cur_j,1375))))
        self.birthday_clear=QPushButton('حذف تولد');self.birthday_clear.setObjectName('Small')
        from ui_icons import symbol
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QPalette
        self.birthday_preview=QPushButton('آزمایش جشن تولد');self.birthday_preview.setObjectName('Small')
        self.birthday_preview.setIcon(symbol('assistant',QApplication.palette().color(QPalette.ButtonText).name()))
        self.birthday_preview.setProperty('karnameIconKey','assistant')
        def _sync_bday_controls():
            on=self.birthday_enabled.isChecked()
            for w in (self.birthday_day,self.birthday_month,self.birthday_year,self.birthday_policy):w.setEnabled(on)
            self.birthday_clear.setEnabled(on)
            y=self.birthday_year.currentData() or cur_j;m=self.birthday_month.currentData() or 1
            limit=month_last_day(int(y),int(m))
            cur_day=self.birthday_day.currentData() or 1
            if self.birthday_day.count()!=limit:
                self.birthday_day.blockSignals(True);self.birthday_day.clear()
                for d in range(1,limit+1):self.birthday_day.addItem(fa(d),d)
                self.birthday_day.setCurrentIndex(max(0,self.birthday_day.findData(min(cur_day,limit))))
                self.birthday_day.blockSignals(False)
        def _clear_bday():
            self.birthday_enabled.setChecked(False);_sync_bday_controls()
        def _preview_bday():
            from birthday_ui import BirthdayCelebrationOverlay
            host=self.window()
            if hasattr(self,'_preview_overlay') and self._preview_overlay is not None:
                try:self._preview_overlay.dismiss()
                except Exception:pass
            user=getattr(owner,'session_user',None) or {}
            person=(user.get('fullname') or getattr(self,'name',None) and self.name.text() or 'دوست عزیز').strip()
            self._preview_overlay=BirthdayCelebrationOverlay(host,person,owner.data.get('settings',{}),duration_banner_ms=2600)
        self.birthday_enabled.toggled.connect(lambda _:_sync_bday_controls())
        self.birthday_year.currentIndexChanged.connect(lambda _:_sync_bday_controls())
        self.birthday_month.currentIndexChanged.connect(lambda _:_sync_bday_controls())
        self.birthday_clear.clicked.connect(_clear_bday)
        self.birthday_preview.clicked.connect(_preview_bday)
        _sync_bday_controls()
        bday_row.addWidget(self.birthday_day);bday_row.addWidget(self.birthday_month);bday_row.addWidget(self.birthday_year);bday_row.addWidget(self.birthday_clear);bday_row.addWidget(self.birthday_preview)
        f.addRow(self.birthday_enabled,bday_row)
        f.addRow('رفتار روز ناموجود در سال غیرکبیسه',self.birthday_policy)
        self.checks={}
        for key,title,default in [('calendar_gregorian','تاریخ میلادی در تقویم',True),('calendar_occasions','نشان مناسبت در تقویم',True),('calendar_tasks','نشان یادآورها در خانه‌های تقویم',True),('calendar_side','فهرست یادآورهای روز کنار تقویم',True),('chat_notifications','اعلان پیام تازه و جلسه روی ویندوز',True)]:w=QCheckBox(title);w.setChecked(self.original.get(key,default));v.addWidget(w);self.checks[key]=w
        v.addWidget(QLabel('بخش‌هایی که برای حساب من نمایش داده شوند'));self.modules={};grid=QGridLayout()
        if self.original.get('preferences_schema',0)<7:
            visible=list(self.original.get('visible_modules',[k for k,_ in MODULES]));self.original['visible_modules']=list(dict.fromkeys(visible+['desk']))
        if self.original.get('preferences_schema',0)<8:
            visible=list(self.original.get('visible_modules',[k for k,_ in MODULES]));self.original['visible_modules']=list(dict.fromkeys(visible+['workspace']))
        if self.original.get('preferences_schema',0)<9:
            visible=list(self.original.get('visible_modules',[k for k,_ in MODULES]));self.original['visible_modules']=list(dict.fromkeys(visible+['attendance']))
        if self.original.get('preferences_schema',0)<10:
            visible=list(self.original.get('visible_modules',[k for k,_ in MODULES]));self.original['visible_modules']=list(dict.fromkeys(visible+['assistant']))
        if self.original.get('preferences_schema',0)<11:
            visible=list(self.original.get('visible_modules',[k for k,_ in MODULES]));self.original['visible_modules']=list(dict.fromkeys(visible+['clients']))
        if self.original.get('preferences_schema',0)<12:
            visible=list(self.original.get('visible_modules',[k for k,_ in MODULES]));self.original['visible_modules']=list(dict.fromkeys(visible+['tax']))
        for i,(key,title) in enumerate(MODULES):
            c=QCheckBox(title);c.setChecked(key in self.original.get('visible_modules',[k for k,_ in MODULES]));self.modules[key]=c;grid.addWidget(c,i//3,i%3)
        v.addLayout(grid);v.addWidget(QLabel('متن راهنما؛ از نماد کنار تنظیمات باز می‌شود'));self.help=QPlainTextEdit(self.original.get('help_text',DEFAULT_HELP));self.help.setMaximumHeight(170);v.addWidget(self.help);v.addStretch()
    def photo(self):
        try:
            value=choose_image(self)
            if value is not None:self.avatar=value;self.set_preview()
        except Exception as e:QMessageBox.warning(self,'عکس حساب',str(e))
    def remove_photo(self):self.avatar='';self.set_preview()
    def set_preview(self):
        pix=QPixmap()
        if self.avatar:pix.loadFromData(base64.b64decode(self.avatar))
        if pix.isNull():self.preview.clear();self.preview.setText(((self.owner.session_user or {}).get('fullname','ک'))[:1])
        else:self.preview.setPixmap(circular_avatar(pix,58))
    def chat_color(self):
        color=ColorWheelDialog.choose(self.color,self)
        if color:self.color=color
    def values(self):
        from birthday_service import parse_birthday
        result=copy.deepcopy(self.original);result.update({key:w.isChecked() for key,w in self.checks.items()});result.update(calendar_name=self.calendar_name.text().strip()[:30] or 'تقویم',visible_modules=[k for k,w in self.modules.items() if w.isChecked()],help_text=self.help.toPlainText()[:16000]);result['preferences_schema']=12
        if self.birthday_enabled.isChecked():
            result['birthday']=parse_birthday(dict(year=self.birthday_year.currentData(),month=self.birthday_month.currentData(),day=self.birthday_day.currentData(),missing_day_policy=self.birthday_policy.currentData()))
        else:
            result['birthday']=None
        return result

def default_services():
    from features_ui import SERVICES
    return [dict(name=t.split(' — ')[0]+' · '+t.split(' — ')[-1],topic=t,notes='',url=u,color='#258B87' if 'مالیات' in t else '#387FC0',opacity=14,enabled=True) for t,_,u in SERVICES]

class ServiceDialog(QDialog):
    def __init__(self,item=None,parent=None):
        super().__init__(parent);self.setWindowTitle('سامانه');self.setLayoutDirection(Qt.RightToLeft);self.resize(510,450);v=QVBoxLayout(self);f=QFormLayout();v.addLayout(f);self.item=copy.deepcopy(item or dict(name='',topic='',notes='',url='https://',color='#258B87',opacity=15,enabled=True));self.fields={}
        for key,title in [('name','نام سایت'),('topic','موضوع'),('url','پیوند'),('notes','توضیح دلخواه')]:w=QLineEdit(self.item.get(key,''));self.fields[key]=w;f.addRow(title,w)
        self.fields['url'].setLayoutDirection(Qt.LeftToRight);self.enabled=QCheckBox('نمایش');self.enabled.setChecked(self.item['enabled']);f.addRow(self.enabled);self.opacity=QSpinBox();self.opacity.setRange(5,100);self.opacity.setSuffix('٪');self.opacity.setValue(self.item['opacity']);f.addRow('شدت رنگ',self.opacity);color=QPushButton('انتخاب رنگ');color.clicked.connect(self.choose_color);f.addRow(color);b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.button(QDialogButtonBox.Save).setText('ذخیره');b.button(QDialogButtonBox.Cancel).setText('انصراف');b.accepted.connect(self.validate);b.rejected.connect(self.reject);v.addWidget(b)
    def choose_color(self):
        color=ColorWheelDialog.choose(self.item['color'],self)
        if color:self.item['color']=color
    def validate(self):
        try:
            from official_news import validate_source_url
            self.item.update({k:w.text().strip() for k,w in self.fields.items()});validate_source_url(self.item['url'])
            if not self.item['name']:raise ValueError('نام سایت را وارد کنید.')
            self.item.update(opacity=self.opacity.value(),enabled=self.enabled.isChecked());self.accept()
        except Exception as e:QMessageBox.warning(self,'سامانه',str(e))

class ServicesSettings(QWidget):
    def __init__(self,owner):
        super().__init__();self.items=copy.deepcopy(owner.data.get('preferences',{}).get('services',default_services()));v=QVBoxLayout(self);self.list=QListWidget();self.list.doubleClicked.connect(self.edit);v.addWidget(self.list);row=QHBoxLayout()
        for title,key,fn in [('افزودن','add',self.add),('ویرایش','edit',self.edit),('حذف','delete',self.remove)]:b=QPushButton(title);iconize(b,key,title);b.clicked.connect(fn);row.addWidget(b)
        row.addStretch();v.addLayout(row);self.render()
    def render(self):self.list.clear();self.list.addItems([x['name']+('' if x.get('enabled',True) else ' · پنهان') for x in self.items])
    def add(self):
        d=ServiceDialog(parent=self)
        if d.exec():self.items.append(d.item);self.render()
    def edit(self):
        i=self.list.currentRow()
        if i<0:return
        d=ServiceDialog(self.items[i],self)
        if d.exec():self.items[i]=d.item;self.render()
    def remove(self):
        i=self.list.currentRow()
        if i>=0:self.items.pop(i);self.render()

class CompanyDialog(QDialog):
    def __init__(self,company=None,parent=None):
        super().__init__(parent);self.setWindowTitle('مشخصات شرکت');self.setLayoutDirection(Qt.RightToLeft);self.resize(550,470);v=QVBoxLayout(self);f=QFormLayout();v.addLayout(f);self.company=copy.deepcopy(company or {});self.fields={}
        for key,title in [('name','نام شرکت'),('phone','شماره تلفن'),('address','نشانی'),('extra','اطلاعات تکمیلی')]:w=QLineEdit(self.company.get(key,''));self.fields[key]=w;f.addRow(title,w)
        row=QHBoxLayout();self.preview=avatar_label(self.company.get('logo',''),self.company.get('name','شرکت'),64);row.addWidget(self.preview);b=QPushButton('نماد شرکت');b.clicked.connect(self.photo);row.addWidget(b);color=QPushButton('رنگ شرکت و اعلان');color.clicked.connect(self.choose_color);row.addWidget(color);v.addLayout(row);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.button(QDialogButtonBox.Save).setText('ذخیره');buttons.button(QDialogButtonBox.Cancel).setText('انصراف');buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);v.addWidget(buttons)
    def choose_color(self):
        value=ColorWheelDialog.choose(self.company.get('color','#187C85'),self)
        if value:self.company['color']=value
    def photo(self):
        try:
            value=choose_image(self)
            if value is not None:self.company['logo']=value;pix=QPixmap();pix.loadFromData(base64.b64decode(value));self.preview.setPixmap(pix.scaled(64,64,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        except Exception as e:QMessageBox.warning(self,'نماد',str(e))
    def validate(self):
        self.company.update({k:w.text().strip() for k,w in self.fields.items()})
        if self.company['name']:self.accept()
        else:QMessageBox.warning(self,'شرکت','نام شرکت را وارد کنید.')

class CompaniesSettings(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self.companies=[];v=QVBoxLayout(self);self.list=QListWidget();self.list.doubleClicked.connect(self.edit);v.addWidget(self.list);row=QHBoxLayout()
        for title,key,fn in [('افزودن شرکت','add',self.add),('ویرایش شرکت','edit',self.edit),('شبکه مشترک شرکت','settings',self.network)]:b=QPushButton(title);iconize(b,key,title);b.clicked.connect(fn);row.addWidget(b)
        v.addLayout(row);self.note=QLabel('افزودن شرکت فقط برای مدیر کل و ویرایش برای مدیر همان شرکت است.');self.note.setWordWrap(True);v.addWidget(self.note)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0,self.load)
    def load(self):
        from shiboken6 import isValid
        if not isValid(self):return
        try:
            companies=request_wait(self.owner,'companies')
            if not isValid(self):return
            self.companies=companies;self.list.clear()
            for c in self.companies:self.list.addItem(c['name']+(' · '+c.get('phone','') if c.get('phone') else ''))
        except Exception as e:
            if isValid(self):self.note.setText(str(e))
    def add(self):self.edit_company(None)
    def edit(self):
        i=self.list.currentRow()
        if i>=0:self.edit_company(self.companies[i])
    def edit_company(self,company):
        d=CompanyDialog(company,self)
        if d.exec():
            try:
                request_wait(self.owner,'companies',d.company);self.owner.data['company_write_at']=__import__('datetime').datetime.now().isoformat();self.owner.persist();self.load();self.owner.org.revision=None;self.owner.org.sync()
            except Exception as e:QMessageBox.warning(self,'شرکت',str(e))
    def network(self):
        from ui_permissions import gate
        if not gate(self.owner,'network'):return
        from org_ui import ServerDialog
        ServerDialog(self.owner).exec()

class RecoveryPanel(QWidget):
    def __init__(self,owner):
        super().__init__();self.owner=owner;v=QVBoxLayout(self);title=QLabel('پشتیبان و بازیابی');title.setObjectName('Hero');v.addWidget(title);tip=QLabel('فایل ‎.karname شامل داده و فهرست بررسی سلامت است. پشتیبان‌های ZIP نسخه قبلی هم پذیرفته می‌شوند. پشتیبان مدیر کل میزبان، حساب‌ها، گفتگوها و پیوست‌ها را نیز در بر می‌گیرد.');tip.setWordWrap(True);v.addWidget(tip)
        from ui_permissions import allowed
        for title,key,fn,permission in [('ساخت پشتیبان قابل بازیابی','backup',owner.backup_now,'personal'),('بررسی فایل پشتیبان','import',self.inspect,'personal'),('بازیابی اطلاعات شخصی','restore',owner.restore_backup,'personal'),('بازیابی کامل مرکز شرکت','restore',self.restore_server,'full')]:b=QPushButton(title);iconize(b,key,title);b.setText(title);b.clicked.connect(fn);b.setEnabled(allowed(owner,'backup',permission));v.addWidget(b)
        note=QLabel('پیش از جایگزینی اطلاعات شخصی، نسخه فعلی ذخیره می‌شود. بازیابی مرکز فقط با دسترسی مدیر کل میزبان انجام می‌شود و پوشه قبلی حفظ خواهد شد.');note.setWordWrap(True);v.addWidget(note);v.addStretch()
    def inspect(self):
        path,_=QFileDialog.getOpenFileName(self,'بررسی پشتیبان','','Karname Backup (*.karname *.zip)')
        if not path:return
        from backup_crypto import unlock_ui
        if not unlock_ui(path,self):return
        try:
            from backup_bundle import verify_bundle
            data,entries,manifest=verify_bundle(path);full='server/company.sqlite' in entries;extra=''
            if full:
                from server_restore import inspect_server_backup
                counts=inspect_server_backup(path)[3];extra='\nحساب‌ها: '+str(counts['users'])+' · پرونده‌ها: '+str(counts['records'])
            QMessageBox.information(self,'پشتیبان سالم است',('مرکز شرکت و اطلاعات شخصی' if full else 'اطلاعات شخصی؛ داده شرکت به‌صورت خروجی مطالعه')+'\nرویدادها: '+str(len(data['events']))+'\nتاریخ: '+manifest['created']+extra)
        except Exception as e:QMessageBox.warning(self,'پشتیبان نامعتبر',str(e))
    def restore_server(self):
        from org_ui import ServerDialog
        ServerDialog(self.owner).restore_server()

