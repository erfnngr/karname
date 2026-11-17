# -*- coding: utf-8 -*-
"""تقویم مالیاتی شمسی | Windows tray app with editable local reminders."""
import sys, os, re, csv, traceback
from pathlib import Path
from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize, Signal, QObject
from PySide6.QtGui import QFont, QColor, QPainter, QPixmap, QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QToolButton,
    QHBoxLayout, QVBoxLayout, QGridLayout, QScrollArea, QLineEdit, QTextEdit,
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QSystemTrayIcon,
    QMenu, QMessageBox, QFileDialog, QCheckBox, QSpinBox, QGraphicsDropShadowEffect, QTabWidget, QBoxLayout, QStyle, QSizePolicy
)
import jdatetime
from storage import (MONTHS, WEEKDAYS, fa, normalize, parse_j, jformat, jalali_date,
                     today_j, month_last_day, next_month, due_on, occurrence,
                     gregorian, load_data, save_data, import_excel, new_event,
                     app_dir, data_path, package_file)
from appearance import init_font,apply_appearance,stylesheet
from reminders import DEFAULT_LEADS,effective_leads,parse_leads,due_reminders,group_of

PRIORITIES = ['خیلی مهم', 'مهم', 'متوسط', 'کم']
REPEAT = ['بدون تکرار', 'ماهانه', 'سه‌ماهه', 'سالانه']
PRIO_COLOR = {'خیلی مهم':'#BC3F46','مهم':'#E18A20','متوسط':'#3783B5','کم':'#6B8791'}

def label(t='', name=None, weight=False, color=None, parent=None):
    l=QLabel(str(t),parent)
    l.setTextFormat(Qt.PlainText)
    l.setWordWrap(True)
    if name:l.setObjectName(name)
    if weight:l.setStyleSheet('font-weight:bold;')
    if color and color not in ('white','#E6F2F5'):l.setObjectName(name or 'Sub')
    return l

def btn(t, callback, primary=False, small=False):
    b=QPushButton(t)
    if primary:b.setObjectName('Primary')
    elif small:b.setObjectName('Small')
    b.setCursor(Qt.PointingHandCursor)
    b.clicked.connect(callback)
    return b

def make_icon():
    from storage import package_file
    return QIcon(str(package_file('assets/karname.png')))

class ClickDay(QFrame):
    def __init__(self, dt, click, today=False, selected=False):
        super().__init__(); self.date=dt;self.click=click
        self.setObjectName('Selected' if selected else 'Today' if today else 'Day')
        self.setCursor(Qt.PointingHandCursor)
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton:self.click(self.date)
        super().mousePressEvent(e)

class EventDialog(QDialog):
    def __init__(self, parent, companies, item=None, date_value=None, company=None):
        super().__init__(parent)
        self.setWindowTitle('ویرایش یادآور' if item else 'افزودن یادآور جدید')
        self.setMinimumSize(530,480);self.setLayoutDirection(Qt.RightToLeft)
        available=QApplication.primaryScreen().availableGeometry();self.resize(min(600,available.width()-30),min(700,available.height()-50))
        host=QVBoxLayout(self);area=QScrollArea();area.setWidgetResizable(True);shell=QWidget();outer=QVBoxLayout(shell);area.setWidget(shell);host.addWidget(area);outer.setSpacing(13)
        outer.addWidget(label('ویرایش رویداد' if item else 'یادآور جدید',name='Hero'))
        form=QFormLayout();form.setSpacing(12);outer.addLayout(form)
        self.company=QComboBox();self.company.setEditable(True)
        self.company.addItems(list(dict.fromkeys(['شخصی']+(companies or []))))
        from brand import company_brand
        from storage import package_file
        for ix in range(self.company.count()):
            brand=company_brand(self.company.itemText(ix))
            if brand:
                from brand import company_pixmap
                self.company.setItemIcon(ix,QIcon(company_pixmap(self.company.itemText(ix))))
        self.company.setCurrentText(item.get('company','') if item else (company or 'شخصی'))
        form.addRow('گروه / شرکت:',self.company)
        self.title=QLineEdit(item.get('title','') if item else '')
        self.title.setPlaceholderText('مثلاً ارسال اظهارنامه ارزش افزوده')
        form.addRow('عنوان:',self.title)
        self.category=QComboBox();self.category.addItems(['مالیات','بیمه','سایر'])
        self.category.setCurrentText(item.get('category','بیمه' if 'بیمه' in item.get('title','') else 'مالیات') if item else 'مالیات')
        form.addRow('بخش:',self.category)
        self.when=QLineEdit(item.get('date_jalali','') if item and item.get('date_jalali') else date_value or jformat(today_j()))
        self.when.setAlignment(Qt.AlignRight)
        from ui_icons import iconize
        date_row=QHBoxLayout();date_row.addWidget(self.when);date_pick=QPushButton();iconize(date_pick,'calendar','انتخاب تاریخ');date_pick.clicked.connect(self.pick_date);date_row.addWidget(date_pick);form.addRow('تاریخ شمسی:',date_row)
        self.priority=QComboBox();self.priority.addItems(PRIORITIES)
        self.priority.setCurrentText(item.get('priority','متوسط') if item else 'متوسط')
        form.addRow('اهمیت:',self.priority)
        self.repeat=QComboBox();self.repeat.addItems(REPEAT)
        self.repeat.setCurrentText(item.get('recurrence','بدون تکرار') if item else 'بدون تکرار')
        form.addRow('تکرار:',self.repeat)
        self.reminder_group=QComboBox();self.reminder_group.addItem('شخصی','personal');self.reminder_group.addItem('یادآور کاری','default');self.reminder_group.setCurrentIndex(1 if item and group_of(item)=='default' else 0);form.addRow('گروه یادآوری:',self.reminder_group)
        self.custom_reminder=QCheckBox('زمان‌بندی اختصاصی این رویداد');self.custom_reminder.setChecked(bool(item and item.get('reminder_custom')));form.addRow(self.custom_reminder)
        self.leads=QLineEdit('، '.join(str(i) for i in effective_leads(item or {},parent.data['settings'])))
        self.leads.setPlaceholderText('۲۰، ۱۵، ۱۰، ۵، ۴، ۳، ۲، ۱، ۰');self.leads.setEnabled(self.custom_reminder.isChecked());self.custom_reminder.toggled.connect(self.leads.setEnabled)
        lead_row=QHBoxLayout();lead_row.addWidget(self.leads);lead_pick=QPushButton('انتخاب روزها');lead_pick.setEnabled(self.custom_reminder.isChecked());self.custom_reminder.toggled.connect(lead_pick.setEnabled);lead_pick.clicked.connect(self.pick_leads);lead_row.addWidget(lead_pick);form.addRow('یادآوری چند روز زودتر:',lead_row)
        self.notes=QTextEdit();self.notes.setAcceptRichText(False);self.notes.setPlainText(item.get('notes','') if item else '')
        self.notes.setPlaceholderText('یادداشت، جرایم، لینک و مدارک موردنیاز ...')
        self.notes.setMinimumHeight(105)
        form.addRow('توضیحات:',self.notes)
        if item and item.get('created_from_excel'):
            outer.addWidget(label('متن اولیه اکسل: '+item.get('original_deadline',''),name='Sub'))
        if item and item.get('needs_review'):
            outer.addWidget(label('نیازمند بررسی: '+item.get('review_reason',''),color='#B35B21'))
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText('ذخیره')
        buttons.button(QDialogButtonBox.Cancel).setText('انصراف')
        buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);host.addWidget(buttons)
        self.delete_requested=False
        if item and item.get('id'):
            delete=buttons.addButton('حذف یادآور',QDialogButtonBox.DestructiveRole)
            delete.clicked.connect(self.request_delete)
        self.payload=None

    def pick_date(self):
        from report_ui import JalaliDatePicker
        picker=JalaliDatePicker(self.when.text(),self)
        if picker.exec()==QDialog.Accepted:self.when.setText(picker.value())
    def pick_leads(self):
        from reminders import parse_leads
        try:selected=set(parse_leads(self.leads.text()))
        except ValueError:selected=set()
        dialog=QDialog(self);dialog.setWindowTitle('روزهای یادآوری');layout=QVBoxLayout(dialog);grid=QGridLayout();layout.addLayout(grid);checks=[]
        for index,day in enumerate(sorted(set(range(31))|selected,reverse=True)):
            box=QCheckBox(fa(day)+' روز قبل' if day else 'روز موعد');box.setChecked(day in selected);grid.addWidget(box,index//4,index%4);checks.append((day,box))
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()==QDialog.Accepted:self.leads.setText('، '.join(str(day) for day,box in checks if box.isChecked()))
    def request_delete(self):
        self.delete_requested=True;self.reject()

    def validate(self):
        try:
            title=self.title.text().strip()
            if not title:raise ValueError('عنوان یادآور نمی‌تواند خالی باشد.')
            dt=parse_j(self.when.text())
            nums=parse_leads(self.leads.text())
            company=self.company.currentText().strip() or 'شخصی'
            self.payload={'company':company,'title':title,'date_jalali':f'{dt.year:04d}/{dt.month:02d}/{dt.day:02d}',
                          'priority':self.priority.currentText(),'recurrence':self.repeat.currentText(),
                          'lead_days':nums,'notes':self.notes.toPlainText(),'category':self.category.currentText(),'reminder_custom':self.custom_reminder.isChecked(),'reminder_group':self.reminder_group.currentData()}
            self.accept()
        except Exception as e:QMessageBox.warning(self,'تاریخ یا اطلاعات نامعتبر',str(e))

class StartupPopup(QWidget):
    clicked=Signal()
    def __init__(self,text,settings=None,title='یادآور کارنامه',company=None):
        super().__init__()
        from storage import DEFAULT_SETTINGS
        self.settings=dict(DEFAULT_SETTINGS,**(settings or {}))
        from brand import popup_style
        self.settings,_=popup_style(company,self.settings)
        self.setWindowFlags(Qt.Tool|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setLayoutDirection(Qt.RightToLeft)
        root=QVBoxLayout(self);root.setContentsMargins(10,10,10,10)
        from karname_ui import WatermarkPanel
        pane=WatermarkPanel(self.settings['popup_bg'],company);pane.setObjectName('Pane')
        bg=self.settings['popup_bg'];fg=self.settings['popup_fg']
        self.setStyleSheet(f'QWidget {{background:transparent;color:{fg};font-family:"{self.settings["font_family"]}";font-size:{self.settings["font_size"]}px;}} QFrame#Pane{{background:{bg};border:1px solid {fg};border-radius:14px}} QLabel{{color:{fg};background:transparent}} QPushButton{{color:{bg};background:{fg};border:0;border-radius:7px;padding:7px}}')
        lay=QVBoxLayout(pane);lay.setContentsMargins(21,17,21,17)
        heading=QHBoxLayout()
        from brand import logo,company_brand
        if company_brand(company):heading.addWidget(logo(company,32))
        heading.addWidget(label(title,weight=True));lay.addLayout(heading)
        l=label(text);l.setMinimumWidth(320);l.setMaximumWidth(420)
        lay.addWidget(l)
        b=QPushButton('باز کردن تقویم');b.clicked.connect(self.on_click);lay.addWidget(b)
        root.addWidget(pane)
        self.setWindowOpacity(0)
        self.fade=None
    def show_popup(self):
        self.adjustSize()
        scr=QApplication.primaryScreen().availableGeometry()
        self.move(scr.right()-self.width()-15,scr.bottom()-self.height()-16)
        self.show();self.raise_()
        self.fade=QPropertyAnimation(self,b'windowOpacity')
        self.fade.setDuration(min(250,self.settings['popup_fade_ms']));self.fade.setStartValue(0.0);self.fade.setEndValue(self.settings['popup_opacity']/100)
        self.fade.setEasingCurve(QEasingCurve.OutCubic);self.fade.start()
        fade_ms=min(self.settings['popup_fade_ms'],self.settings['popup_seconds']*1000)
        QTimer.singleShot(max(0,self.settings['popup_seconds']*1000-fade_ms),self.fade_out)
    def fade_out(self):
        if not self.isVisible():return
        self.fade=QPropertyAnimation(self,b'windowOpacity')
        self.fade.setDuration(min(self.settings['popup_fade_ms'],self.settings['popup_seconds']*1000));self.fade.setStartValue(self.windowOpacity());self.fade.setEndValue(0.0)
        self.fade.finished.connect(self.hide)
        self.fade.start()
    def on_click(self):self.clicked.emit();self.fade_out()

class TaxWindow(QMainWindow):
    def __init__(self,session=None,base_dir=None):
        super().__init__()
        self.session_user=session.get('user') if session else None;self.base_dir=Path(base_dir) if base_dir else app_dir();self.auth_client=session.get('client') if session else None;self._locking=False
        self.data=load_data();self.events=self.data['events']
        if session and self.data.get('pending_profile_restore'):self.session_user['profile']=self.data['pending_profile_restore']
        elif session and self.session_user.get('profile',{}).get('preferences'):self.data['preferences']=self.session_user['profile']['preferences']
        self.shared_events=[];self.desk_events=[];self.company_server=session.get('local_server') if session else None;self.network_server=None;self._host_address='127.0.0.1';self._host_fingerprint='ورود محلی روی همین کامپیوتر'
        from backup_bundle import BackupState
        self.backup_state=BackupState(app_dir(),self.data);self._exit_approved=False;self._exit_pending=False
        recovery_notice=self.data.pop('_recovery_notice',None)
        init_font();apply_appearance(self.data['settings'])
        self.selected=today_j();self.year=self.selected.year;self.month=self.selected.month
        self._popups=[]
        self._popup_queue=[]
        self._pending_alerts=set()
        self.setWindowTitle('کارنامه')
        self.setWindowIcon(make_icon());self.setMinimumSize(800,520)
        screen=QApplication.primaryScreen().availableGeometry()
        self.resize(min(1270,screen.width()-40),min(830,screen.height()-45))
        self.setLayoutDirection(Qt.RightToLeft)
        from appearance import apply_section_appearances
        self.build_ui(); self.make_tray();self.refresh();apply_section_appearances(self)
        if recovery_notice:self.statusBar().showMessage(recovery_notice,20000)
        self.timer=QTimer(self);self.timer.setInterval(60*1000)
        self._last_day=date.today();self.timer.timeout.connect(self.daily_tick);self.timer.start()
        self.home.weather_service.changed.connect(self.check_assistant_alerts)
        QTimer.singleShot(1600,self.first_notification)
        QShortcut(QKeySequence('Ctrl+N'),self).activated.connect(self.add_event)
        if session:
            self.org.client=session.get('client')
            if self.org.client:self.org.url.setText(self.org.client.url);self.org.username.setText(self.session_user['username']);QTimer.singleShot(0,self.org.sync)
            elif session.get('offline_snapshot'):QTimer.singleShot(0,lambda:self.org.apply_snapshot(session['offline_snapshot'],True))
            if self.company_server:QTimer.singleShot(0,self.restore_network_host)

    def restore_network_host(self):
        import json
        from org_http import RunningServer
        try:
            settings=json.loads((self.base_dir/'server-host.json').read_text(encoding='utf-8'))
            if settings.get('enabled'):
                try:
                    state=json.loads((self.base_dir/'company-host-status.json').read_text('utf-8'))
                    if state.get('running'):
                        from org_client import Client
                        c=Client('https://127.0.0.1:'+str(settings['port']),str(self.base_dir/'company-server/server-cert.pem'))
                        try:c.request('status')
                        finally:c.session.close()
                        self._external_host=True;self._host_address=settings['address'];self._host_fingerprint=settings['fingerprint'];return
                except Exception:pass
                from lan_discovery import preferred_address
                folder=self.base_dir/'company-server';self.network_server=RunningServer(folder,'0.0.0.0',int(settings['port']),True,folder/'server-cert.pem',folder/'server-key.pem',background=False,discovery=True);self._host_address=preferred_address(settings['address']);self._host_fingerprint=settings['fingerprint']
        except FileNotFoundError:pass
        except Exception as exc:self.statusBar().showMessage('میزبان شبکه شروع نشد؛ ورود محلی فعال است. '+str(exc),20000)

    def lock_session(self):
        if self._locking or not self.session_user:return
        self.ai.reset()
        self._locking=True;self.hide();self.timer.stop();self.org.timer.stop();self.chat.timer.stop();self.desk.timer.stop();self.workspace.timer.stop();self.v8.stop.set();self.v8.identity=None;self.org.client=None;self.org.records=[];self.shared_events=[];self._popup_queue.clear()
        for popup in self._popups:popup.hide()
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget,QDialog) and widget is not self and widget.parent() is not None:widget.reject()
        from access_ui import LoginDialog
        dialog=LoginDialog(self.base_dir,self.company_server,self.session_user,self)
        if dialog.exec()==QDialog.Accepted:
            self.session_user=dialog.session['user'];self.auth_client=dialog.session['client'];self.company_server=dialog.session.get('local_server') or self.company_server;self.org.client=self.auth_client;self._locking=False;self.timer.start();self.org.timer.start();self.chat.timer.start();self.desk.timer.start();self.workspace.timer.start();self.org.revision=None;self.org.sync();self.show_main()
        else:
            self._locking=False;self.exit_app()
            if not self._exit_approved:QTimer.singleShot(0,self.lock_session)

    def reconnect_company(self):
        """Reauthenticate an offline session before making shared changes."""
        if self._locking or self._exit_pending or self._exit_approved:return False
        if not self.session_user:
            QMessageBox.information(self,'اتصال به مرکز شرکت','برای تغییر اطلاعات مشترک ابتدا با حساب خود وارد کارنامه شوید.')
            return False
        from access_ui import LoginDialog
        dialog=LoginDialog(self.base_dir,self.company_server,self.session_user,self)
        dialog.setWindowTitle('اتصال دوباره به مرکز شرکت')
        if dialog.exec()!=QDialog.Accepted:return False
        session=dialog.session;client=session.get('client');user=session.get('user')
        if not client:
            QMessageBox.information(self,'مرکز شرکت در دسترس نیست','اکنون فقط نسخه آفلاین برای مشاهده در دسترس است. میزبان شرکت باید روشن و از طریق شبکه قابل دسترسی باشد؛ سپس دوباره برای اتصال اقدام کنید.')
            return False
        if not user or user.get('id')!=self.session_user.get('id'):
            client.session.close();QMessageBox.warning(self,'حساب متفاوت','برای ادامه باید با همان حساب فعلی وارد شوید.')
            return False
        self.session_user=user;self.auth_client=client;self.company_server=session.get('local_server') or self.company_server
        self.org.client=client;self.org.revision=None;self.org.sync()
        return True

    def persist(self):
        self.data['events']=self.events;save_data(self.data)

    def display_events(self):return self.events+self.shared_events+self.desk_events

    def can_backup_server(self):
        user=self.session_user or (self.org.client.user if getattr(self,'org',None) and self.org.client else None)
        if not self.company_server or not user or not self.org.client:return False
        try:
            fresh=self.company_server.store.authenticate(self.org.client.token)
            return fresh['id']==user['id'] and fresh['global_role'] in ('group_admin','system_admin')
        except Exception:return False

    def build_ui(self):
        from main_ui import build_window
        build_window(self)

    def make_tray(self):
        self.tray=None
        if not QSystemTrayIcon.isSystemTrayAvailable():return
        self.tray=QSystemTrayIcon(make_icon(),self)
        menu=QMenu()
        menu.addAction('باز کردن تقویم',self.show_main)
        menu.addAction('افزودن یادآور',self.add_event)
        menu.addAction('یادآورهای پیش رو',lambda:self.mode_and_show('۴۵ روز آینده و معوق'))
        menu.addAction('ماه جاری',lambda:(self.goto_today(),self.tabs.setCurrentWidget(self.overview),self.show_main()))
        menu.addSeparator();menu.addAction('خروج کامل',self.exit_app);menu.addAction('خروج بدون پشتیبان‌گیری',self.exit_without_backup)
        menu.addAction('ادامه در پس‌زمینه',self.minimize_to_tray)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason:self.show_main() if reason in (QSystemTrayIcon.Trigger,QSystemTrayIcon.DoubleClick) else None)
        self.tray.show()

    def exit_app(self):
        if not self.prepare_exit():return
        self.ai.cancel()
        keep_host=bool(not getattr(self,'_updating',False) and self.data['settings'].get('host_auto') and self.can_backup_server())
        self.chat.timer.stop();self.desk.timer.stop();self.org.timer.stop();self.workspace.timer.stop();self.v8.stop.set();self.v8.timer.stop();self.timer.stop();self.news_panel.timer.stop()
        if self.network_server:self.network_server.close();self.network_server=None
        if self.company_server:self.company_server.close();self.company_server=None
        if keep_host and not getattr(self,'_external_host',False):
            try:
                from network_tools import start_autohost
                start_autohost(self.base_dir)
            except Exception:pass
        QApplication.instance().setQuitOnLastWindowClosed(True)
        if self.tray:self.tray.hide()
        QApplication.instance().quit()

    def exit_without_backup(self):
        if self.org.busy or self.chat.busy or self.desk.busy or self.attendance.busy or self.ai.applying or getattr(getattr(self,'workspace',None),'busy',False) or getattr(getattr(self,'v8',None),'backup_busy',False):
            QMessageBox.information(self,'ذخیره در حال انجام','پس از پایان عملیات دوباره خارج شوید.');return
        if QMessageBox.question(self,'خروج بدون پشتیبان','برنامه بدون ساخت پشتیبان تازه بسته شود؟ اطلاعات ذخیره‌شده حفظ می‌شوند.',QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        self.persist();self._exit_approved=True;self.exit_app()

    def show_main(self):
        if self._locking:return
        self.show();self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.raise_();self.activateWindow();self.refresh()

    def closeEvent(self,e):
        if self._exit_approved:e.accept();return
        e.ignore();QTimer.singleShot(0,self.exit_app)

    def minimize_to_tray(self):
        if self.tray and self.tray.isVisible():self.hide()
        else:self.showMinimized()

    def prepare_exit(self):
        if self._exit_approved:return True
        if self._exit_pending:return False
        self._exit_pending=True
        org_timer_active=self.org.timer.isActive();self.org.timer.stop()
        try:
            if self.org.busy or self.chat.busy or self.desk.busy or self.attendance.busy or self.ai.applying or getattr(getattr(self,'workspace',None),'busy',False) or getattr(getattr(self,'v8',None),'backup_busy',False):
                QMessageBox.information(self,'انتظار برای ذخیره','عملیات مرکز شرکت در حال انجام است؛ پس از پایان آن دوباره خارج شوید.');return False
            server_dirty=bool(self.can_backup_server() and self.company_server.store.revision()!=self.backup_state.server_revision)
            if self.backup_state.dirty(self.data) or server_dirty:
                box=QMessageBox(self);box.setWindowTitle('پشتیبان‌گیری و خروج');box.setText('اطلاعات تازه یا ویرایش‌شده دارید. پس از تأیید و ذخیره پشتیبان، برنامه کامل بسته می‌شود.');save=box.addButton('پشتیبان‌گیری و خروج',QMessageBox.AcceptRole);skip=box.addButton('خروج بدون پشتیبان‌گیری',QMessageBox.DestructiveRole);box.addButton('بازگشت به برنامه',QMessageBox.RejectRole);box.exec()
                if box.clickedButton() is not skip and (box.clickedButton() is not save or not self.backup_now()):return False
            self._exit_approved=True;return True
        finally:
            self._exit_pending=False
            if org_timer_active and not self._exit_approved:self.org.timer.start()

    def backup_now(self, filename=None):
        from ui_permissions import gate
        if not gate(self,'backup','personal'):return False
        from backup_bundle import create_bundle
        from datetime import datetime
        if self.org.busy or self.desk.busy:QMessageBox.information(self,'پشتیبان','عملیات مرکز در حال انجام است؛ پس از پایان آن پشتیبان بگیرید.');return False
        default=app_dir()/'backups'/('Karname-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.karname');default.parent.mkdir(parents=True,exist_ok=True)
        if filename is None:filename,_=QFileDialog.getSaveFileName(self,'ذخیره پشتیبان',str(default),'Karname Backup (*.karname *.zip)')
        filename=str(filename) if filename else ''
        if not filename:return False
        if not filename.lower().endswith(('.karname','.zip')):filename+='.karname'
        org_timer_active=self.org.timer.isActive();self.org.timer.stop()
        try:
            extras={}
            if self.session_user:
                import json
                extras['account/profile.json']=json.dumps(dict(id=self.session_user['id'],profile=self.session_user.get('profile',{})),ensure_ascii=False).encode('utf-8')
                from ai_schedule import backup_data
                scheduled=backup_data(self.session_user['id'])
                if scheduled is not None:extras['account/assistant-schedules.json']=json.dumps(scheduled,ensure_ascii=False).encode('utf-8')
            cache=getattr(self.auth_client,'cache',None)
            cached=cache.path if cache else None
            if not cached and self.session_user:
                from access_ui import config
                import hashlib
                cfg=config(self.base_dir);origin='network://'+cfg['server_identity'] if cfg.get('mode')=='auto' and cfg.get('server_identity') else cfg.get('url','') if cfg.get('mode')=='remote' else 'local://karname';identity=(origin.rstrip('/')+'\n'+self.session_user['username'].strip().casefold()).encode();cached=self.base_dir/'company-cache'/(hashlib.sha256(identity).hexdigest()+'.cache')
            if cached and cached.is_file():extras['offline/'+cached.name]=cached.read_bytes()
            if self.org.client:
                from PySide6.QtCore import QEventLoop
                from PySide6.QtWidgets import QProgressDialog
                import json,base64,threading
                progress=QProgressDialog('دریافت نسخه مجاز اطلاعات شرکت…',None,0,0,self);progress.setWindowModality(Qt.ApplicationModal);progress.show();loop=QEventLoop();result={}
                class BackupSignals(QObject):done=Signal()
                signals=BackupSignals();signals.done.connect(loop.quit);client=self.org.client
                def fetch_backup():
                    try:result['value']=client.request('export')
                    except Exception as exc:result['error']=exc
                    finally:signals.done.emit()
                threading.Thread(target=fetch_backup,daemon=True).start();loop.exec();progress.close()
                if 'error' in result:raise result['error']
                value=result['value'];extras['company/export.json']=json.dumps(value['data'],ensure_ascii=False).encode('utf-8');extras.update({'company/files/'+key+'.bin':base64.b64decode(raw) for key,raw in value['attachments'].items()})
            server_revision=None
            if self.can_backup_server():
                import tempfile,sqlite3
                from contextlib import closing
                store=self.company_server.store
                with store.lock,tempfile.TemporaryDirectory(dir=app_dir()) as temp:
                    db=Path(temp)/'company.sqlite';store.backup_database(db)
                    with closing(sqlite3.connect(db)) as c:
                        c.execute('DELETE FROM sessions');c.execute('DELETE FROM login_limits');server_revision=c.execute('SELECT COALESCE(MAX(id),0) FROM audit').fetchone()[0];c.commit()
                    extras['server/company.sqlite']=db.read_bytes()
                    for file in store.files.glob('*.bin'):extras['server/files/'+file.name]=file.read_bytes()
            from v8_controller import password_for_backup
            self.persist();create_bundle(filename,self.data,extras,password=password_for_backup(self));self.backup_state.mark_saved(self.data,server_revision);self.statusBar().showMessage('پشتیبان ذخیره و صحت آن بررسی شد.',8000);self._last_backup=filename;return True
        except Exception as exc:QMessageBox.warning(self,'پشتیبان ذخیره نشد','برنامه باز می‌ماند.\n'+str(exc));return False
        finally:
            if org_timer_active:self.org.timer.start()

    def restore_backup(self):
        from ui_permissions import gate
        if not gate(self,'backup','personal'):return
        from backup_bundle import verify_bundle,create_bundle
        from datetime import datetime
        filename,_=QFileDialog.getOpenFileName(self,'بازگردانی پشتیبان','','Karname Backup (*.karname *.zip)')
        if not filename:return
        from backup_crypto import unlock_ui
        if not unlock_ui(filename,self):return
        try:
            data,entries,manifest=verify_bundle(filename)
            if QMessageBox.question(self,'بازگردانی پشتیبان','اطلاعات تقویم با '+fa(len(data['events']))+' رویداد جایگزین می‌شود. پیش از آن از وضعیت فعلی پشتیبان می‌گیریم. پس از بازگردانی برنامه بسته می‌شود؛ دوباره آن را باز کنید.',QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
            import json
            safety=app_dir()/'backups'/('before-restore-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.karname');safety_extra={}
            if self.session_user:safety_extra['account/profile.json']=json.dumps(dict(id=self.session_user['id'],profile=self.session_user.get('profile',{})),ensure_ascii=False).encode('utf-8')
            if self.session_user:
                from ai_schedule import backup_data
                scheduled=backup_data(self.session_user['id'])
                if scheduled is not None:safety_extra['account/assistant-schedules.json']=json.dumps(scheduled,ensure_ascii=False).encode('utf-8')
            create_bundle(safety,self.data,safety_extra)
            account=json.loads(entries.get('account/profile.json',b'{}'))
            previous_schedules=None;schedules_written=False
            if self.session_user and (not account.get('id') or account['id']==self.session_user['id']):
                profile=account.get('profile') or data.get('account_profile') or dict(self.session_user.get('profile',{}));profile=dict(profile,preferences=data.get('preferences',profile.get('preferences',{})));data['pending_profile_restore']=profile;data['account_profile']=profile
                desk_cache=data.get('desk_cache',{})
                if desk_cache.get('user_id')==self.session_user['id']:data['pending_desk_restore']=desk_cache.get('notes',[])
                if 'account/assistant-schedules.json' in entries:
                    from ai_schedule import prepare_restore,write,backup_data
                    previous_schedules=backup_data(self.session_user['id']);restored=prepare_restore(self.session_user['id'],json.loads(entries['account/assistant-schedules.json']));write(self.session_user['id'],restored);schedules_written=True
            try:save_data(data)
            except Exception:
                if schedules_written:write(self.session_user['id'],previous_schedules['items'] if previous_schedules else [])
                raise
            self.data=data;self.events=data['events'];self.backup_state.mark_saved(data);self._exit_approved=True
            for name,raw in entries.items():
                if re.fullmatch(r'offline/[0-9a-f]{64}\.cache',name):folder=self.base_dir/'company-cache';folder.mkdir(exist_ok=True);(folder/Path(name).name).write_bytes(raw)
            if self.network_server:self.network_server.close();self.network_server=None
            if self.company_server:self.company_server.close();self.company_server=None
            if self.tray:self.tray.hide()
            QApplication.instance().quit()
        except Exception as exc:QMessageBox.warning(self,'بازگردانی انجام نشد',str(exc))

    def share_data(self):
        from sharing import share_file
        filename,_=QFileDialog.getOpenFileName(self,'انتخاب فایل برای اشتراک‌گذاری',str(app_dir()),'همه فایل‌ها (*.*)')
        if not filename:return
        menu=QMenu(self);windows=menu.addAction('اشتراک‌گذاری با ویندوز');mail=menu.addAction('پیش‌نویس ایمیل');selected=menu.exec(self.mapToGlobal(self.rect().center()))
        if selected:share_file(self,filename,email=selected is mail)

    def mode_and_show(self,mode):
        self.mode_filter.setCurrentText(mode);self.tabs.setCurrentWidget(self.calendar_page);self.show_main()

    def jump_month(self):
        d=QDialog(self);d.setWindowTitle('انتخاب ماه و سال');v=QVBoxLayout(d);form=QFormLayout();v.addLayout(form)
        year=QSpinBox();year.setRange(1300,1499);year.setValue(self.year);month=QComboBox();month.addItems(MONTHS);month.setCurrentIndex(self.month-1);form.addRow('سال:',year);form.addRow('ماه:',month)
        actions=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);actions.accepted.connect(d.accept);actions.rejected.connect(d.reject);v.addWidget(actions)
        if d.exec():self.year=year.value();self.month=month.currentIndex()+1;self.selected=jalali_date(self.year,self.month,1);self.mode_filter.setCurrentText('کارهای ماه انتخابی');self.refresh()

    def filtered_company(self, ev):
        current=self.company_filter.currentText()
        kind=self.category_filter.currentText()
        category='بیمه' if 'بیمه' in ev.get('category','')+ev.get('title','') else 'سایر' if ev.get('category')=='سایر' else 'مالیات'
        return (current=='همه شرکت‌ها' or ev.get('company')==current) and (kind=='مالیات و بیمه' or kind==category)

    def selected_changed(self,d):
        self.selected=d;self.mode_filter.setCurrentText('موعدهای روز انتخابی');self.refresh()

    def shift_month(self,delta):
        self.year,self.month=next_month(self.year,self.month,delta)
        if self.selected.year!=self.year or self.selected.month!=self.month:
            self.selected=jalali_date(self.year,self.month,1)
        self.refresh()

    def goto_today(self):
        self.selected=today_j();self.year=self.selected.year;self.month=self.selected.month;self.refresh()

    def clear_layout(self,lay):
        while lay.count():
            child=lay.takeAt(0)
            if child.widget():child.widget().hide();child.widget().deleteLater()
            elif child.layout():self.clear_layout(child.layout())

    def quick_pick(self,kind):
        from karname_ui import QuickPicker
        picker=QuickPicker(self,kind)
        if picker.exec():
            if kind=='year':self.year=picker.value
            else:self.month=picker.value
            self.selected=jalali_date(self.year,self.month,min(self.selected.day,month_last_day(self.year,self.month)));self.refresh()

    def show_occasions(self):
        self.occasions_panel.year.setValue(self.year);self.occasions_panel.month.setCurrentIndex(self.month-1);self.tabs.setCurrentWidget(self.occasions_panel)

    def render_calendar(self):
        from occasions import on_date
        from iran_calendar import day_off
        self.month_title.setText(MONTHS[self.month-1]);self.year_title.setText(fa(self.year))
        first=jalali_date(self.year,self.month,1);last=jalali_date(self.year,self.month,month_last_day(self.year,self.month))
        self.greg_month.setText(f"{first.togregorian():%B %Y} — {last.togregorian():%B %Y}")
        self.clear_layout(self.grid)
        for i,weekday in enumerate(WEEKDAYS):
            head=label(weekday,weight=True);head.setAlignment(Qt.AlignCenter)
            if i>=5:head.setObjectName('HolidayText')
            self.grid.addWidget(head,0,i)
        offset=(first.togregorian().weekday()+2)%7;days=month_last_day(self.year,self.month);indexed={};repeating=[]
        for ev in self.display_events():
            if not self.filtered_company(ev) or ev.get('done') or ev.get('needs_review') or not ev.get('date_jalali'):continue
            if ev.get('recurrence','بدون تکرار')!='بدون تکرار':repeating.append(ev);continue
            try:indexed.setdefault(parse_j(ev['date_jalali']).togregorian(),[]).append(ev)
            except ValueError:continue
        for i in range(42):
            row,col=divmod(i,7);day=i-offset+1
            if not 1<=day<=days:
                empty=QWidget();empty.setObjectName('EmptyDay');self.grid.addWidget(empty,row+1,col);continue
            jd=jalali_date(self.year,self.month,day);gd=jd.togregorian();matched=indexed.get(gd,[])+[ev for ev in repeating if due_on(ev,gd)];occasions=on_date(gd)
            box=ClickDay(jd,self.selected_changed,jd==today_j(),jd==self.selected)
            if day_off(gd) and jd!=self.selected and jd!=today_j():box.setObjectName('HolidayDay')
            cell=QVBoxLayout(box);cell.setContentsMargins(7,5,7,6);cell.setSpacing(3)
            date_row=QWidget();date_row.setStyleSheet('background:transparent;');date_row.setLayoutDirection(Qt.LeftToRight);top=QHBoxLayout(date_row);top.setContentsMargins(0,0,0,0);top.setDirection(QBoxLayout.LeftToRight)
            greg=label(gd.strftime('%d %b'),name='Gregorian',parent=date_row);greg.setVisible(self.data.get('preferences',{}).get('calendar_gregorian',True));greg.setWordWrap(False);greg.setStyleSheet('font-size:9px;');top.addWidget(greg);top.addStretch()
            num=label(fa(day),name='DayNumber');num.setAlignment(Qt.AlignRight)
            if day_off(gd):num.setObjectName('HolidayText')
            top.addWidget(num);cell.addWidget(date_row)
            if matched and self.data.get('preferences',{}).get('calendar_tasks',True):
                from brand import event_type,row_colors
                for ev in matched[:1]:
                    bg,fg,accent=row_colors(ev,self.data['settings']);chip=label(ev['title'][:11]+'…');chip.setWordWrap(False);chip.setStyleSheet(f'background:{bg};color:{fg};font-size:10px;border-radius:4px;padding:2px;');cell.addWidget(chip)
                if len(matched)>1:box.setToolTip('یادآورها: '+fa(len(matched)))
            if occasions and self.data.get('preferences',{}).get('calendar_occasions',True):
                from calendar_labels import OccasionLabel
                cell.addWidget(OccasionLabel([item['title'] for item in occasions],box,any(item.get('holiday') for item in occasions)))
            cell.addStretch();box.setMinimumHeight(48);box.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Expanding);box.setToolTip('\n'.join(x['title'] for x in matched+occasions));self.grid.addWidget(box,row+1,col)
        for col in range(7):self.grid.setColumnStretch(col,1)
        for r in range(1,7):self.grid.setRowStretch(r,1)

    def event_reference_date(self,ev,after=None):
        if ev.get('needs_review') or not ev.get('date_jalali'):return None
        try:
            orig=parse_j(ev['date_jalali']).togregorian()
            if ev.get('recurrence','بدون تکرار')!='بدون تکرار':return occurrence(ev,after or date.today())
            return orig
        except Exception:return None

    def get_visible_events(self):
        mode=self.mode_filter.currentText();query=normalize(self.search.text()).lower()
        today=date.today();items=[];self._visible_dates={}
        for ev in self.display_events():
            if not self.filtered_company(ev):continue
            if query and query not in normalize(ev.get('title','')+' '+ev.get('notes','')).lower():continue
            after=self.selected.togregorian() if mode=='موعدهای روز انتخابی' else jalali_date(self.year,self.month,1).togregorian() if mode=='کارهای ماه انتخابی' else today
            deadline=self.event_reference_date(ev,after)
            completed=ev.get('completed_occurrences',[])
            if mode=='انجام‌شده‌ها' and completed:
                try:deadline=max(date.fromisoformat(value) for value in completed)
                except ValueError:pass
            if mode=='موعدهای روز انتخابی' and not due_on(ev,self.selected.togregorian()):continue
            if mode=='کارهای ماه انتخابی' and (not deadline or (jdatetime.date.fromgregorian(date=deadline).year,jdatetime.date.fromgregorian(date=deadline).month)!=(self.year,self.month)):continue
            if mode=='نیازمند بررسی' and not ev.get('needs_review'):continue
            if mode=='انجام‌شده‌ها' and not (ev.get('done') or completed):continue
            if mode=='۴۵ روز آینده و معوق' and (ev.get('done') or ev.get('needs_review') or not deadline or deadline>today+timedelta(days=45)):continue
            if mode not in ('همه رویدادها','انجام‌شده‌ها') and ev.get('done'):continue
            items.append((deadline or date(9999,1,1),ev))
            self._visible_dates[ev['id']]=deadline
        return [it[1] for it in sorted(items,key=lambda x:(x[0],PRIORITIES.index(x[1].get('priority','متوسط')) if x[1].get('priority','متوسط') in PRIORITIES else 2))]

    def change_items_page(self,delta):
        self._items_page=max(0,self._items_page+delta);self.render_items(reset_page=False)

    def render_items(self,*_,reset_page=True):
        if reset_page:self._items_page=0
        mode=self.mode_filter.currentText()
        if mode=='موعدهای روز انتخابی':
            self.side_title.setText('کارهای '+jformat(self.selected))
            self.side_caption.setText('روز میلادی: '+self.selected.togregorian().strftime('%Y-%m-%d'))
        else:
            self.side_title.setText(mode)
            self.side_caption.setText('مرتب‌سازی بر اساس موعد و اهمیت')
        from occasions import on_date
        selected_occasions=on_date(self.selected.togregorian()) if self.data.get('preferences',{}).get('calendar_occasions',True) else []
        self.selected_occasions.setText('مناسبت‌های روز\n'+'\n'.join('• '+item['title'] for item in selected_occasions));self.selected_occasions.setVisible(bool(selected_occasions))
        self.clear_layout(self.list_layout)
        items=self.get_visible_events()
        if not items:
            self.list_layout.addWidget(label('در این بخش موردی وجود ندارد.\nمی‌توانی یادآور جدید اضافه کنی.',color='#6F8997'))
        self._items_page=min(self._items_page,max(0,(len(items)-1)//self.items_per_page));start=self._items_page*self.items_per_page
        self.previous_items.setEnabled(self._items_page>0);self.next_items.setEnabled(start+self.items_per_page<len(items))
        self.items_count.setText((fa(start+1)+' تا '+fa(min(start+self.items_per_page,len(items)))+' از '+fa(len(items))) if items else '۰ رویداد')
        for ev in items[start:start+self.items_per_page]:self.list_layout.addWidget(self.task_card(ev,self._visible_dates.get(ev['id'])))
        self.list_layout.addStretch()
        flagged=sum(1 for e in self.events if e.get('needs_review'))
        self.footer.setText(f'کل رویدادها: {fa(len(self.display_events()))}   |   نیازمند بررسی: {fa(flagged)}   |   اطلاعات شخصی روی رایانه؛ اطلاعات مشترک روی مرکز شرکت')

    def task_card(self,ev,reference_date=None):
        from karname_ui import CompactRow
        return CompactRow(self,ev,reference_date)

    def refresh(self,*_):
        self.render_calendar();self.render_items()
        if hasattr(self,'overview'):self.overview.refresh()
        if hasattr(self,'home'):self.home.refresh()
        cal_rv=getattr(getattr(self,'calendar_page',None),'react_view',None)
        if cal_rv is not None:cal_rv.bridge.publish()
        if hasattr(self,'chat'):self.chat.apply_theme()

    def update_companies(self):
        chosen=self.company_filter.currentText()
        self.company_filter.blockSignals(True)
        self.company_filter.clear();self.company_filter.addItem('همه شرکت‌ها')
        for c in self.data['companies']:self.company_filter.addItem(c)
        self.company_filter.setCurrentText(chosen if chosen in self.data['companies'] else 'همه شرکت‌ها')
        self.company_filter.blockSignals(False)

    def add_event(self):
        from ui_permissions import gate
        from appearance import flush_pending_qss
        if not gate(self,'calendar','create'):return
        flush_pending_qss()
        company=self.company_filter.currentText()
        if company=='همه شرکت‌ها':company='شخصی'
        dialog=EventDialog(self,self.data['companies'],date_value=jformat(self.selected),company=company)
        if dialog.exec()==QDialog.Accepted:
            payload=dialog.payload
            ev=new_event(payload['company'],payload['title'],payload['date_jalali'],payload['notes'],payload['priority'],payload['recurrence'],payload['lead_days'])
            ev.update(category=payload['category'],reminder_custom=payload['reminder_custom'],reminder_group=payload['reminder_group'])
            self.events.append(ev)
            if payload['company'] not in self.data['companies']:self.data['companies'].append(payload['company']);self.update_companies()
            self.persist();self.refresh()

    def edit_event(self,ev):
        from ui_permissions import gate
        if not gate(self,'calendar','edit'):return
        if ev.get('desk_note_id'):self.desk.edit_note(ev['desk_note_id']);return
        if ev.get('shared_id'):
            self.tabs.setCurrentWidget(self.org);record=next((r for r in self.org.records if r['id']==ev['shared_id']),None)
            if record:self.org.edit(record=record)
            return
        dialog=EventDialog(self,self.data['companies'],item=ev)
        result=dialog.exec()
        if dialog.delete_requested:self.delete_event(ev);return
        if result==QDialog.Accepted:
            if ev.get('created_from_excel'):ev.setdefault('source_title',ev.get('title',''))
            def schedule(item):
                try:day=parse_j(item.get('date_jalali','')).togregorian()
                except ValueError:day=None
                return (day,item.get('recurrence','بدون تکرار'),group_of(item),tuple(effective_leads(item,self.data['settings'])))
            schedule_changed=schedule(ev)!=schedule(dialog.payload)
            ev.update(dialog.payload)
            ev['needs_review']=False;ev['review_reason']='';ev['snooze_until']=None
            if schedule_changed:ev['last_alerts']={}
            if ev['company'] not in self.data['companies']:self.data['companies'].append(ev['company']);self.update_companies()
            self.persist();self.refresh()

    def delete_event(self,ev):
        from ui_permissions import gate
        if not gate(self,'calendar','delete'):return
        if QMessageBox.question(self,'حذف یادآور','«'+ev.get('title','')+'» حذف شود؟',QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        import copy
        self.data.setdefault('event_trash',[]).append(dict(event=copy.deepcopy(ev),deleted_at=datetime.now().astimezone().isoformat()))
        self.events.remove(ev);self.persist();self.refresh()

    def set_done(self,ev,value,when=None):
        from ui_permissions import gate
        if not gate(self,'calendar','edit'):return
        if ev.get('desk_note_id'):self.desk.complete_note(ev['desk_note_id'],value);return
        if ev.get('shared_id'):self.edit_event(ev);self.refresh();return
        if ev.get('recurrence','بدون تکرار')!='بدون تکرار':
            d=when or self.event_reference_date(ev)
            if d:
                taken=ev.setdefault('completed_occurrences',[])
                if value and d.isoformat() not in taken:taken.append(d.isoformat())
                elif not value and d.isoformat() in taken:taken.remove(d.isoformat())
        else:ev['done']=value
        ev['snooze_until']=None
        self.persist();self.refresh()

    def snooze(self,ev):
        ev['snooze_until']=(date.today()+timedelta(days=1)).isoformat()
        self.persist();self.refresh()
        QMessageBox.information(self,'تعویق یادآور','این یادآور تا فردا نمایش داده نمی‌شود.')

    def show_guide(self):
        from appearance import flush_pending_qss,palette_for
        from personalization_ui import DEFAULT_HELP
        from navigation_shortcuts import help_text
        flush_pending_qss()
        c=palette_for(self.data.get('settings',{}))
        d=QDialog(self);d.setWindowTitle('راهنما و میانبرهای صفحه‌کلید');d.setMinimumSize(640,480);d.setLayoutDirection(Qt.RightToLeft)
        d.setStyleSheet(f'QDialog{{background:{c["bg"]};color:{c["text"]};}} QTextEdit{{background:{c["panel"]};color:{c["text"]};border:1px solid {c["border"]};border-radius:12px;padding:12px;}}')
        v=QVBoxLayout(d);v.setContentsMargins(18,16,18,16);v.setSpacing(10)
        head=label('راهنمای کارنامه و کلیدهای میانبر (بر اساس حرف اول بخش‌ها)',weight=True);head.setObjectName('Hero');v.addWidget(head)
        area=QTextEdit();area.setReadOnly(True);area.setPlainText(self.data.get('preferences',{}).get('help_text',DEFAULT_HELP)+'\n\nمیانبرهای صفحه‌کلید (بر اساس حرف اول بخش‌ها)\n'+help_text());v.addWidget(area,1);close_btn=btn('بستن',d.accept);close_btn.setObjectName('Primary');v.addWidget(close_btn,0,Qt.AlignLeft);d.exec()

    def import_spreadsheet(self):
        from ui_permissions import gate
        if not gate(self,'calendar','create'):return
        name,_=QFileDialog.getOpenFileName(self,'انتخاب فایل اکسل',str(Path.home()),'Excel (*.xlsx)')
        if not name:return
        try:
            added,flagged=import_excel(name,self.data);self.events=self.data['events']
            self.update_companies();self.persist();self.refresh()
            QMessageBox.information(self,'وارد شد',f'{fa(added)} ردیف جدید وارد شد.\n{fa(flagged)} ردیف نیاز به بررسی تاریخ دارد.\nردیف‌های تکراری و ویرایش‌های قبلی حفظ شدند.')
        except Exception as e:QMessageBox.critical(self,'خطای ورود اکسل',str(e))

    def export_ics(self):
        from ui_permissions import gate
        if not gate(self,'calendar','export'):return
        filename,_=QFileDialog.getSaveFileName(self,'خروجی تقویم برای Outlook',str(Path.home()/'TaxCalendar.ics'),'iCalendar (*.ics)')
        if not filename:return
        def esc(v):return str(v or '').replace('\\','\\\\').replace('\n','\\n').replace(',','\\,').replace(';','\\;')
        lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//TaghvimMaliatiFA//FA','CALSCALE:GREGORIAN','METHOD:PUBLISH']
        count=0
        for ev in self.events:
            if ev.get('needs_review') or ev.get('done'):continue
            base=self.event_reference_date(ev)
            if not base:continue
            dates=[base]
            if ev.get('recurrence','بدون تکرار')!='بدون تکرار':
                dates=[];cursor=max(date.today(),parse_j(ev['date_jalali']).togregorian())
                for i in range(30):
                    nextdate=occurrence(ev,cursor)
                    if not nextdate or nextdate>date.today()+timedelta(days=730):break
                    dates.append(nextdate);cursor=nextdate+timedelta(days=1)
            for d in dates:
                count+=1
                lines+=['BEGIN:VEVENT','UID:'+ev['id']+'-'+d.strftime('%Y%m%d')+'@taghvim-fa',
                    'DTSTAMP:'+date.today().strftime('%Y%m%d')+'T000000Z',
                    'DTSTART;VALUE=DATE:'+d.strftime('%Y%m%d'),
                    'DTEND;VALUE=DATE:'+(d+timedelta(days=1)).strftime('%Y%m%d'),
                    'SUMMARY:'+esc(ev.get('title','')),
                    'DESCRIPTION:'+esc(ev.get('notes','')+'\n'+ev.get('company','')),'END:VEVENT']
        lines.append('END:VCALENDAR')
        from calendar_export import encode_ics
        Path(filename).write_bytes(encode_ics(lines))
        QMessageBox.information(self,'خروجی ساخته شد',f'{fa(count)} رویداد صادر شد.\nفایل را می‌توانی در Outlook وارد کنی؛ همگام‌سازی خودکار با تقویم ویندوز نیست.')

    def open_data_dir(self):
        import subprocess
        folder=app_dir()
        if os.name=='nt':os.startfile(str(folder))
        else:subprocess.Popen(['xdg-open',str(folder)])

    def _startup_value(self,enabled):
        if os.name!='nt':return
        import winreg
        if getattr(sys,'frozen',False):cmd='"'+sys.executable+'" --tray'
        else:
            executable=sys.executable
            if executable.lower().endswith('python.exe'):executable=executable[:-10]+'pythonw.exe'
            cmd='"'+executable+'" "'+str(Path(__file__).resolve().with_name('launcher.py'))+'" --tray'
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            if enabled:winreg.SetValueEx(key,'TaghvimMaliatiFA',0,winreg.REG_SZ,cmd)
            else:
                try:winreg.DeleteValue(key,'TaghvimMaliatiFA')
                except FileNotFoundError:pass

    def settings(self):
        from appearance import flush_pending_qss
        from ui_permissions import gate
        if not gate(self,'settings','view'):return
        flush_pending_qss()
        from settings_ui import SettingsDialog
        dialog=SettingsDialog(self)
        if dialog.exec()!=QDialog.Accepted:return
        self.data['settings']=dialog.result_value;self.data['news_sources']=dialog.result_sources
        try:self._startup_value(dialog.result_value['startup'])
        except Exception as exc:QMessageBox.warning(self,'شروع خودکار','ثبت اجرای خودکار انجام نشد: '+str(exc))
        self.persist();self.v8.last_check='';apply_appearance(self.data['settings']);self.news_panel.reload_sources();
        from main_ui import apply_preferences
        from appearance import apply_section_appearances
        from navigation_shortcuts import sync_theme
        apply_preferences(self);self.refresh();apply_section_appearances(self);sync_theme(self)
        if hasattr(self,'sidebar'):self.sidebar.apply()
        if hasattr(self,'ai'):self.ai.render()
        if hasattr(self,'home') and hasattr(self.home,'react_view') and self.home._react_home_active():
            self.home.react_view.bridge.publish()
        from navigation_shortcuts import sync_theme
        sync_theme(self)

    def daily_tick(self):
        self.home.refresh_quote()
        if date.today()!=self._last_day:
            self._last_day=date.today();self.goto_today();self.first_notification()
        else:self.check_alerts()
        self.check_assistant_alerts()

    def check_assistant_alerts(self):
        from ui_permissions import allowed
        from assistant_awareness import alerts,weather_context,review_alerts
        if self._locking or not self.data['settings'].get('reminder_enabled',True) or not allowed(self,'calendar'):return
        identity=str((self.session_user or {}).get('id') or 'local')
        histories=self.data.setdefault('assistant_alert_history',{});history=histories.setdefault(identity,{})
        items=alerts(self.display_events(),weather_context(self.home.weather_service),history)
        if getattr(self.org,'client',None) and allowed(self,'assistant','context') and self.data['settings'].get('ai_app_access',True):
            items+=review_alerts(self.org.records,self.session_user,history)
        if not items:return
        for key,_ in items:history[key]=True
        if len(history)>300:histories[identity]=dict(list(history.items())[-200:])
        self.persist()
        self.popup('\n'.join(message for _,message in items),title='دستیار کارنامه')

    def due_for_alert(self):
        return [(diff,event) for diff,event,dt,key in due_reminders(self.display_events(),self.data['settings'])]

    def popup(self,text,settings=None,title='یادآور کارنامه',company=None,alerts=None,on_click=None,on_shown=None):
        self._popup_queue.append((text,dict(settings or self.data['settings']),title,company,alerts,on_click,on_shown))
        if not self._popups:self._show_next_popup()

    def _show_next_popup(self):
        if not self._popup_queue:return
        text,settings,title,company,alerts,on_click,on_shown=self._popup_queue.pop(0)
        if alerts:
            expected={(event['id'],key) for _,event,_,key in alerts};self._pending_alerts.difference_update(expected)
            settings=dict(self.data['settings'])
            alerts=[item for item in due_reminders(self.display_events(),settings) if (item[1]['id'],item[3]) in expected] if settings.get('reminder_enabled',True) else []
            if not alerts:
                QTimer.singleShot(0,self._show_next_popup);return
            text='\n'.join(('امروز' if diff==0 else fa(diff)+' روز تا موعد')+' — '+event['title'][:85] for diff,event,_,_ in alerts)
        p=StartupPopup(text,settings,title,company);self._popups.append(p)
        p.clicked.connect(on_click or (lambda:self.mode_and_show('۴۵ روز آینده و معوق')))
        p.show_popup()
        if on_click:
            for button in p.findChildren(QPushButton):button.setText('باز کردن')
        if on_shown:on_shown()
        if alerts:self.record_shown_alerts(alerts)
        QTimer.singleShot(settings['popup_seconds']*1000+100,lambda:self.release_popup(p))

    def record_shown_alerts(self,items):
        for _,event,_,key in items:
            alerts=event.setdefault('last_alerts',{});alerts[key]=True
            if len(alerts)>80:event['last_alerts']=dict(list(alerts.items())[-60:])
            if event.get('shared_id'):self.data.setdefault('shared_alerts',{})[event['shared_id']]=event['last_alerts']
            if event.get('desk_note_id'):self.data.setdefault('desk_alerts',{})[event['desk_note_id']]=event['last_alerts']
        self.persist()

    def release_popup(self,p):
        if p in self._popups:self._popups.remove(p)
        p.close();p.deleteLater()
        QTimer.singleShot(150,self._show_next_popup)

    def first_notification(self):
        # Startup never produces an unscheduled reminder or monthly-summary popup.
        self.check_alerts()
        self.check_birthday_celebration()

    def check_birthday_celebration(self, today_g=None, duration_banner_ms=5000):
        if self._locking or self._exit_pending or self._exit_approved:
            return None
        user = getattr(self, 'session_user', None) or {}
        user_id = str(user.get('id') or '').strip()
        if not user_id:
            return None
        birth = (self.data.get('preferences') or {}).get('birthday') or ((user.get('profile') or {}).get('preferences') or {}).get('birthday')
        if not birth:
            return None
        from birthday_service import is_user_birthday_today, parse_birthday
        try:
            parsed = parse_birthday(birth)
        except ValueError:
            return None
        if not parsed:
            return None
        is_today, celeb_year, _ = is_user_birthday_today(parsed, today_g=today_g)
        if not is_today or celeb_year is None:
            return None
        shown_map = self.data.setdefault('birthday_celebrations_shown', {})
        if not isinstance(shown_map, dict):
            shown_map = {}
            self.data['birthday_celebrations_shown'] = shown_map
        stamp_key = f'{user_id}:{celeb_year}'
        if shown_map.get(stamp_key):
            return None
        if getattr(self, '_birthday_overlay', None) is not None:
            return None
        shown_map[stamp_key] = True
        self.persist()
        from birthday_ui import BirthdayCelebrationOverlay
        person_name = user.get('first_name') or user.get('fullname') or 'همکار عزیز'
        overlay = BirthdayCelebrationOverlay(self, person_name, self.data.get('settings', {}), duration_banner_ms=duration_banner_ms)
        self._birthday_overlay = overlay
        overlay.closed.connect(lambda: setattr(self, '_birthday_overlay', None))
        return overlay

    def check_alerts(self,notify_popup=True):
        from ui_permissions import allowed
        if not allowed(self,'calendar'):return
        s=self.data['settings']
        if not s.get('reminder_enabled',True):return
        due=[item for item in due_reminders(self.display_events(),s) if (item[1]['id'],item[3]) not in self._pending_alerts]
        if not due:return
        from brand import company_group
        grouped={}
        for diff,event,dt,key in due:
            company=company_group(event.get('company'))
            grouped.setdefault(company,[]).append((diff,event,dt,key))
        for company,items in grouped.items():
            title='یادآور '+(company or 'شخصی')
            for offset in range(0,len(items),4):
                page=items[offset:offset+4];lines=[('امروز' if diff==0 else fa(diff)+' روز تا موعد')+' — '+event['title'][:85] for diff,event,_,_ in page]
                if notify_popup:
                    self._pending_alerts.update((event['id'],key) for _,event,_,key in page)
                    self.popup('\n'.join(lines),title=title,company=company,alerts=page)
            if items and self.tray and s.get('windows_notifications',False):
                self.tray.showMessage(title,'\n'.join(ev['title'][:90] for _,ev,_,_ in items[:3]),QSystemTrayIcon.Information,5000)
                if not notify_popup:self.record_shown_alerts(items)


def main():
    try:
        from version_info import APP_VERSION
        from react_design_host import register_design_scheme
        register_design_scheme()
        app=QApplication(sys.argv);app.setApplicationName('کارنامه');app.setApplicationVersion(APP_VERSION)
        if '--verify-startup' in sys.argv:
            if not os.getenv('TAXCALENDAR_DATA_DIR'):raise ValueError('آزمایش فقط در پوشه جداگانه مجاز است.')
            # Packaged integration check; use TAXCALENDAR_DATA_DIR to isolate test data.
            import json
            app.setLayoutDirection(Qt.RightToLeft)
            from PySide6.QtCore import QEvent
            qa_ghosts=[]
            class LabelObserver(QObject):
                def eventFilter(self,obj,event):
                    if event.type()==QEvent.Show and isinstance(obj,QLabel) and obj.isWindow():qa_ghosts.append(obj.objectName())
                    return False
            observer=LabelObserver();app.installEventFilter(observer)
            win=TaxWindow();win.show_main()
            def verify():
                calc=win.calculator
                calc.amount.setText('100000000');calc.fixed.setText('10');calc.monthly.setText('2');calc.months.setText('3')
                report=dict(frozen=bool(getattr(sys,'frozen',False)),events=len(win.events),tabs=win.tabs.count(),visible=win.isVisible(),calculator_ok='۱۶,۰۰۰,۰۰۰' in calc.result.text())
                from PySide6.QtGui import QFontDatabase
                report['font_loaded']='Vazirmatn' in QFontDatabase.families();report['planning_end']=win.data.get('planning_end')
                report['home_active']=win.tabs.currentWidget() is win.home;report['ui_version']=win.data.get('ui_version')
                report['version']=app.applicationVersion();report['source_rows_archived']=len(win.data.get('source_duplicate_archive',[]));report['source_rows_preserved']=sum(not e.get('generated') for e in win.events)+report['source_rows_archived']
                report['svg_loaded']=not QPixmap(str(package_file('assets/control-down.svg'))).isNull()
                report['brand_assets']=all(not QPixmap(str(package_file('assets/'+name))).isNull() for name in ('karname.png','mana.jpg','arka.jpg'))
                # Exercise the bundled host and HTTP client with isolated data:
                # one user in all three companies must see only one saved chat.
                import tempfile
                from org_http import RunningServer
                from org_client import Client
                with tempfile.TemporaryDirectory(dir=app_dir(),prefix='chat-smoke-') as folder:
                    host=RunningServer(folder,'127.0.0.1',0,background=False);client=Client('http://127.0.0.1:'+str(host.port))
                    try:
                        manager=host.store.bootstrap('smokeadmin','1','آزمایش');user=host.store.save_user(manager,dict(username='smokeuser',password='1',fullname='آزمایش',memberships=[dict(company_id=co,role='employee') for co in ('mana','airia','arka')]))
                        client.login('smokeuser','1');rooms=client.request('chat/rooms');report['empty_chat']=not rooms;saved=client.request('workspace/saved-chat',{});rooms=client.request('chat/rooms');report['optional_saved_chat']=len(rooms)==1 and saved.get('room')=='saved:'+user['id'];report['host_version']=client.request('status')['version']
                    finally:client.session.close();host.close()
                win.home.edit_layout();app.processEvents();report['home_editor_ready']=bool(win.home.home_editor.isVisible() and win.home.home_editor.order);win.home.home_editor.cancel()
                from quotes import collection
                report['daily_quotes']=len(collection());report['quote_visible']=win.home.quote_panel.isVisible();report['web_assets']=all(package_file('web/'+n).exists() for n in ('index.html','app.js','style.css','chat.html','chat.js','delivery.js','attendance.html','attendance.js','workspace.html','workspace.js','permissions.js'))
                import cryptography,pypdf
                report['company_dependencies']=bool(cryptography.__version__ and pypdf.__version__);report['stray_calendar_windows']=len(qa_ghosts);report['personal_desk']=hasattr(win,'desk');report['attendance']=hasattr(win,'attendance');report['workspace']=hasattr(win,'workspace');report['update_public_key']=package_file('assets/update-public.pem').is_file();report['lmstudio_chat']=hasattr(win,'ai');report['calendar_nav_same_width']=win.calendar_button.width()==win.nav_buttons['home'].width();report['calendar_nav_same_height']=win.calendar_button.height()==win.nav_buttons['home'].height();report['customers']=hasattr(win,'clients');report['navigation_shortcuts']=len(win.navigation_shortcuts);report['quick_theme']=hasattr(win,'theme_button');report['automatic_network_profile']=package_file('data/network-defaults.json').is_file()
                win.grab().save(str(app_dir()/'startup-preview.png'))
                (app_dir()/'startup-test.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
                if win.tray:win.tray.hide()
                # The isolated smoke test must not open the interactive backup
                # confirmation when QApplication closes its test window.
                win._exit_approved=True
                app.quit()
            QTimer.singleShot(500,verify)
            sys.exit(app.exec())
        if '--qa-preview' in sys.argv:
            if not os.getenv('TAXCALENDAR_DATA_DIR'):raise ValueError('پوشه جداگانه آزمایش تعیین نشده است.')
            app.setLayoutDirection(Qt.RightToLeft);win=TaxWindow();win.setWindowTitle('کارنامه — آزمایش نسخه ۹');win.show_main()
            stop=QTimer();stop.setInterval(400);stop.timeout.connect(lambda:app.quit() if (app_dir()/'stop-test').exists() else None);stop.start();sys.exit(app.exec())
        from PySide6.QtNetwork import QLocalServer, QLocalSocket
        import hashlib
        channel='TaghvimMaliatiFA-'+hashlib.sha256(str(app_dir().resolve()).encode()).hexdigest()[:18] if os.getenv('TAXCALENDAR_DATA_DIR') else 'TaghvimMaliatiFA-v4'
        socket=QLocalSocket();socket.connectToServer(channel)
        if socket.waitForConnected(500):
            socket.write(b'show');socket.flush();socket.waitForBytesWritten(500);return
        server=QLocalServer()
        if not server.listen(channel):
            raise RuntimeError('برنامه دیگری در حال اجراست یا دسترسی به کانال محلی ممکن نیست.')
        app.setQuitOnLastWindowClosed(False)
        app.setLayoutDirection(Qt.RightToLeft)
        from access_ui import LoginDialog,user_profile
        from storage import DEFAULT_SETTINGS
        init_font();apply_appearance(DEFAULT_SETTINGS);base=app_dir();login=LoginDialog(base)
        if login.exec()!=QDialog.Accepted:return
        user_profile(base,login.session['user']);win=TaxWindow(login.session,base)
        def activate_existing():
            connection=server.nextPendingConnection()
            if connection:connection.close();connection.deleteLater()
            win.show_main()
        server.newConnection.connect(activate_existing)
        if '--tray' not in sys.argv or '--show' in sys.argv or not QSystemTrayIcon.isSystemTrayAvailable():win.show_main()
        sys.exit(app.exec())
    except Exception:
        app_dir().mkdir(parents=True,exist_ok=True)
        with (app_dir()/'error.log').open('a',encoding='utf-8') as f:f.write(traceback.format_exc()+'\n')
        raise

if __name__=='__main__':main()


