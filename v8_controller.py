"""Background change watcher and scheduled backups, owned by the desktop window."""
import copy,threading,json,time
from datetime import datetime,timezone
from PySide6.QtCore import QObject,Signal,QTimer
from local_vault import load

class V8Controller(QObject):
    changed=Signal(int);backup_done=Signal(object,object);update_done=Signal(object,object);checks_done=Signal(object,object,object)
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.identity=None;self.stop=threading.Event();self.backup_busy=False;self.checks_busy=False;self.checks_last=0;self.last_check='';self.last_update_check='';self.changed.connect(self.refresh);self.backup_done.connect(self.backup_finished);self.update_done.connect(self.update_finished);self.checks_done.connect(self.checks_finished);self.timer=QTimer(self);self.timer.setInterval(2000);self.timer.timeout.connect(self.tick);self.timer.start();owner.destroyed.connect(lambda:self.stop.set());self.revision=-1
    def tick(self):
        if self.owner._locking or self.owner._exit_pending or self.owner._exit_approved:return
        c=self.owner.org.client;identity=(c.url,c.token) if c and c.token else None
        if identity!=self.identity:
            self.stop.set();self.stop=threading.Event();self.identity=identity;self.checks_last=0
            if identity:self.watch(c,self.stop)
        settings=self.owner.data.get('settings',{})
        if identity and settings.get('reminder_enabled',True) and settings.get('check_reminders',True) and not self.checks_busy and time.monotonic()-self.checks_last>=60:self.check_deadlines(c,identity)
        day=datetime.now().strftime('%Y%m%d')
        if self.last_check!=day and not self.backup_busy and self.owner.data.get('settings',{}).get('backup_auto_enabled'):
            self.last_check=day;self.backup()
        url=self.owner.data.get('settings',{}).get('update_feed','').strip()
        if url and self.last_update_check!=day:
            self.last_update_check=day;self.check_update(url)
    def check_update(self,url):
        from urllib.parse import urlsplit
        p=urlsplit(url);cert=self.owner.org.certificate(p.scheme+'://'+p.netloc) or True
        def work():
            try:
                from updater import feed
                self.update_done.emit(feed(url,cert),None)
            except Exception as e:
                try:self.update_done.emit(None,e)
                except RuntimeError:pass
        threading.Thread(target=work,daemon=True).start()
    def check_deadlines(self,source,identity):
        from org_client import Client
        self.checks_busy=True;self.checks_last=time.monotonic()
        def work():
            client=Client(source.url,source.session.verify if isinstance(source.session.verify,str) else None,getattr(source,'fingerprint',None));client.token=source.token
            try:
                rows=[]
                for company in client.request('companies'):
                    try:checks=client.request('finance/check-alerts',company=company['id'])
                    except Exception as exc:
                        if getattr(exc,'status',None)==403:continue
                        raise
                    rows.extend(dict(check,company_id=company['id'],company_name=company['name']) for check in checks)
                self.checks_done.emit(rows,None,identity)
            except Exception as exc:
                try:self.checks_done.emit(None,exc,identity)
                except RuntimeError:pass
            finally:client.session.close()
        threading.Thread(target=work,daemon=True).start()
    def checks_finished(self,rows,error,identity):
        self.checks_busy=False;o=self.owner;client=o.org.client;current=(client.url,client.token) if client and client.token else None
        if error or current!=identity or o._locking or o._exit_pending or o._exit_approved or o._popups or o._popup_queue:return
        actor=o.session_user or {};settings=o.data.get('settings',{});shown=o.data.get('finance_check_alerts',{})
        if not actor.get('id'):return
        if not isinstance(shown,dict):shown={};o.data['finance_check_alerts']=shown
        from check_reminders import due
        from permission_policy import allowed
        from storage import fa
        rows=[r for r in (rows or []) if allowed(actor,r['company_id'],'clients','view') and allowed(actor,r['company_id'],'finance','view')]
        due_items=due(rows,settings,shown,actor.get('id',''))
        if not due_items:return
        company=due_items[0][1]['company_id'];group=[item for item in due_items if item[1]['company_id']==company];name=group[0][1]['company_name'];lines=[]
        for days,item,_ in group[:5]:
            label='چک خرج‌شده' if item.get('transferred') else 'چک دریافتی' if item['direction']=='received' else 'چک پرداختی'
            lines.append(('امروز' if days==0 else fa(days)+' روز تا سررسید')+' · '+label+' '+str(item['number'])[:32])
        if len(group)>5:lines.append('و '+fa(len(group)-5)+' چک دیگر')
        def mark():
            alerts=o.data.setdefault('finance_check_alerts',{})
            for _,_,key in group:alerts[key]=True
            if len(alerts)>2000:o.data['finance_check_alerts']=dict(list(alerts.items())[-1500:])
            o.persist()
        def open_finance():
            from permission_policy import allowed
            if not o.session_user or not allowed(o.session_user,company,'clients','view') or not allowed(o.session_user,company,'finance','view'):return
            o.show_main();o.tabs.setCurrentWidget(o.clients);index=o.clients.company.findData(company)
            if index>=0:o.clients.company.setCurrentIndex(index);o.clients.pages.setCurrentWidget(o.clients.finance)
        o.popup('\n'.join(lines),title='سررسید چک',company=name,on_click=open_finance,on_shown=mark)
    def update_finished(self,manifest,error):
        if error:return
        from updater import version,CURRENT
        if version(manifest['version'])>version(CURRENT):self.owner.statusBar().showMessage('نسخه '+manifest['version']+' آماده بررسی است؛ به تنظیمات پشتیبان، شبکه و به‌روزرسانی مراجعه کنید.',30000)
    def watch(self,original,stop):
        from org_client import Client
        def work():
            c=Client(original.url,original.session.verify if isinstance(original.session.verify,str) else None,getattr(original,'fingerprint',None));c.token=original.token;after=0
            try:
                while not stop.is_set():
                    try:
                        value=c.request('workspace/changes',after=after,wait=1);revision=value['revision']
                        if revision!=after and not stop.is_set():after=revision;self.changed.emit(revision)
                    except Exception:
                        if stop.wait(5):break
            finally:c.session.close()
        threading.Thread(target=work,daemon=True).start()
    def refresh(self,revision):
        if self.owner._locking or self.owner._exit_pending or self.owner._exit_approved:return
        self.revision=revision;self.owner.org.sync();self.owner.chat.poll();self.owner.workspace.refresh();self.owner.desk.sync()
        if not getattr(self,'_finance_refresh_pending',False):self._finance_refresh_pending=True;self.refresh_visible_finance()
    def refresh_visible_finance(self):
        from PySide6.QtWidgets import QApplication
        o=self.owner
        if o._locking or o._exit_pending or o._exit_approved:self._finance_refresh_pending=False;return
        if QApplication.activeModalWidget():QTimer.singleShot(1000,self.refresh_visible_finance);return
        self._finance_refresh_pending=False
        if o.tabs.currentWidget() is not o.clients:return
        page=o.clients.pages.currentWidget()
        if page in (o.clients.finance,o.clients.inventory):page.reload(True)
    def backup(self,manual=False):
        if self.backup_busy:return
        o=self.owner
        from ui_permissions import allowed
        if not allowed(o,'backup','personal'):return
        try:
            from storage import app_dir
            value=load(app_dir()/'backup-secret.dpapi',{})
            if not value.get('password'):raise ValueError('ابتدا رمز پشتیبان را در تنظیمات تعیین کنید.')
            data=copy.deepcopy(o.data);settings=data['settings'];server=o.company_server.store if o.can_backup_server() else None;user=copy.deepcopy(o.session_user);base=app_dir()
            from ai_schedule import backup_data
            scheduled=backup_data(user['id']) if user else None
            self.backup_busy=True
            def work():
                try:
                    import tempfile,sqlite3
                    from contextlib import closing
                    from pathlib import Path
                    from backup_schedule import create_scheduled
                    extras={}
                    if user:extras['account/profile.json']=json.dumps(dict(id=user['id'],profile=user.get('profile',{})),ensure_ascii=False).encode()
                    if scheduled is not None:extras['account/assistant-schedules.json']=json.dumps(scheduled,ensure_ascii=False).encode()
                    if server:
                        with server.lock,tempfile.TemporaryDirectory(dir=base) as temp:
                            db=Path(temp)/'company.sqlite';server.backup_database(db)
                            with closing(sqlite3.connect(db)) as con:con.execute('DELETE FROM sessions');con.execute('DELETE FROM login_limits');con.commit()
                            extras['server/company.sqlite']=db.read_bytes()
                            for file in server.files.glob('*.bin'):extras['server/files/'+file.name]=file.read_bytes()
                    paths=create_scheduled(settings.get('backup_folder') or base/'backups'/'automatic',data,extras,value['password'],settings.get('backup_keep_daily',7),settings.get('backup_keep_weekly',4),settings.get('backup_second_folder') or None);self.backup_done.emit(paths,None)
                except Exception as e:self.backup_done.emit(None,e)
            threading.Thread(target=work,daemon=True).start()
        except Exception as e:self.backup_finished(None,e)
    def backup_finished(self,paths,error):
        self.backup_busy=False
        if error:self.last_check='';self.owner.statusBar().showMessage('پشتیبان خودکار کامل نشد: '+str(error),20000);self.timer.setInterval(60000)
        else:self.owner.data.setdefault('backup_schedule_state',{})['last_success']=datetime.now(timezone.utc).isoformat();self.owner.persist();self.owner.statusBar().showMessage('پشتیبان رمزدار و بررسی‌شده آماده شد.',8000);self.timer.setInterval(2000)

def password_for_backup(owner):
    if not owner.data.get('settings',{}).get('backup_encrypt',False):return None
    from storage import app_dir
    secret=load(app_dir()/'backup-secret.dpapi',{})
    if not secret.get('password'):raise ValueError('رمز پشتیبان را در تنظیمات تعیین کنید.')
    return secret['password']
