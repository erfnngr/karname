"""Single-host SQLite service for LAN/HTTPS deployments and responsive portal."""
import base64,hashlib,ipaddress,json,mimetypes,os,secrets,socket,ssl,sqlite3,tempfile,threading,zipfile,io
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit,parse_qs
from datetime import datetime,timezone,timedelta
from org_store import Store,DomainError
from org_schema import SCHEMAS,ROLES,STATUSES
from storage import package_file
from version_info import APP_VERSION

def make_certificate(folder,hosts):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);certfile=folder/'server-cert.pem';keyfile=folder/'server-key.pem'
    if certfile.exists()!=keyfile.exists():
        raise ValueError('یکی از دو فایل گواهی و کلید میزبان موجود نیست. فایل باقی‌مانده را حفظ و گواهی و کلید هماهنگ را بازیابی کنید.')
    if not certfile.exists():
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048);name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Karname Company Server')]);alt=[]
        for host in set(hosts)|{'localhost','127.0.0.1'}:
            try:alt.append(x509.IPAddress(ipaddress.ip_address(host)))
            except ValueError:alt.append(x509.DNSName(host))
        now=datetime.now(timezone.utc);cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=365)).add_extension(x509.SubjectAlternativeName(alt),False).add_extension(x509.BasicConstraints(ca=True,path_length=0),True).sign(key,hashes.SHA256())
        keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()));certfile.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        if os.name!='nt':keyfile.chmod(0o600)
    cert=x509.load_pem_x509_certificate(certfile.read_bytes())
    try:
        private=serialization.load_pem_private_key(keyfile.read_bytes(),password=None)
        fmt=serialization.PublicFormat.SubjectPublicKeyInfo;enc=serialization.Encoding.DER
        if private.public_key().public_bytes(enc,fmt)!=cert.public_key().public_bytes(enc,fmt):raise ValueError('کلید با گواهی فعلی میزبان مطابقت ندارد.')
        names=cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        dns={x.lower() for x in names.get_values_for_type(x509.DNSName)};ips=set(names.get_values_for_type(x509.IPAddress))
        for host in hosts:
            try:ok=ipaddress.ip_address(host) in ips
            except ValueError:ok=host.lower() in dns
            if not ok:raise ValueError('نشانی '+host+' در گواهی فعلی میزبان وجود ندارد. گواهی فعلی حفظ شد؛ مدیر شبکه باید گواهی سازگار با نشانی جدید را آماده و روی دستگاه‌ها دوباره معرفی کند.')
    except x509.ExtensionNotFound:raise ValueError('گواهی میزبان نشانی معتبر ندارد؛ فایل فعلی حفظ شد و باید گواهی مناسب معرفی شود.')
    return certfile,keyfile,cert.fingerprint(hashes.SHA256()).hex().upper()

def public_record(store,actor,record):
    from org_store import public_record_data
    store.require(store.readable(actor,record));return public_record_data(actor,record)

class CompanyServer(ThreadingHTTPServer):
    daemon_threads=False;allow_reuse_address=True
    def __init__(self,address,store,tls=False):
        self.store=store;self.tls=tls;self.slots=threading.BoundedSemaphore(64);self.change_slots=threading.BoundedSemaphore(40);self.ai_slots=threading.BoundedSemaphore(3);self.closing=threading.Event();super().__init__(address,Handler)
    def process_request(self,request,address):
        if not self.slots.acquire(False):request.close();return
        try:super().process_request(request,address)
        except Exception:self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0';server_version='Karname/9';sys_version=''
    def setup(self):super().setup();self.connection.settimeout(25)
    def log_message(self,*args):pass # Never log credentials or document content.
    def reply(self,value,status=200,kind='application/json; charset=utf-8',headers=None):
        if status>=400:self.close_connection=True
        data=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode('utf-8');self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data: blob:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        if self.close_connection:self.send_header('Connection','close')
        for key,val in (headers or {}).items():self.send_header(key,val)
        self.end_headers();self.wfile.write(data)
    def do_GET(self):self.dispatch('GET')
    def do_POST(self):self.dispatch('POST')
    def token(self):
        auth=self.headers.get('Authorization','')
        if auth.startswith('Bearer '):return auth[7:]
        from http.cookies import SimpleCookie
        cookie=SimpleCookie()
        try:cookie.load(self.headers.get('Cookie',''))
        except Exception:return ''
        return cookie['karname'].value if 'karname' in cookie else ''
    def dispatch(self,method):
        try:
            parsed=urlsplit(self.path);path=parsed.path;query={k:v[0] for k,v in parse_qs(parsed.query).items()};store=self.server.store;payload={}
            if method=='POST':
                if self.headers.get('X-Karname')!='1':raise DomainError('درخواست معتبر نیست.',403)
                origin=self.headers.get('Origin')
                if origin and urlsplit(origin).netloc.lower()!=self.headers.get('Host','').lower():raise DomainError('مبدأ درخواست معتبر نیست.',403)
                size=int(self.headers.get('Content-Length','0'))
                if size<1 or size>18*1024*1024:raise DomainError('حجم درخواست معتبر نیست.',413)
                if self.headers.get_content_type()!='application/json':raise DomainError('قالب درخواست معتبر نیست.',415)
                payload=json.loads(self.rfile.read(size))
                if not isinstance(payload,dict):raise DomainError('ساختار درخواست معتبر نیست.')
            if path=='/api/status':return self.reply(dict(version=APP_VERSION,initialized=store.initialized(),secure=self.server.tls,automatic_network=True))
            if path=='/api/login' and method=='POST':
                session=store.login(str(payload.get('username',''))[:64],str(payload.get('password','')));token=session['token'];header={'Set-Cookie':'karname='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'+('; Secure' if self.server.tls else '')}
                return self.reply(session,headers=header)
            if not path.startswith('/api/'):
                static={'/':'web/index.html','/app.js':'web/app.js','/style.css':'web/style.css','/workspace':'web/workspace.html','/workspace.js':'web/workspace.js','/workspace.css':'web/workspace.css','/attendance':'web/attendance.html','/attendance.js':'web/attendance.js','/attendance.css':'web/attendance.css','/permissions.js':'web/permissions.js','/delivery.js':'web/delivery.js','/chat':'web/chat.html','/desk':'web/desk.html','/desk.js':'web/desk.js','/desk.css':'web/desk.css','/chat.js':'web/chat.js','/chat.css':'web/chat.css','/font.ttf':'assets/Vazirmatn-Regular.ttf','/logo.png':'assets/karname.png'}.get(path)
                if method!='GET' or not static:raise DomainError('صفحه پیدا نشد.',404)
                file=package_file(static)
                if not file.is_file():raise DomainError('فایل صفحه موجود نیست.',404)
                return self.reply(file.read_bytes(),kind={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.ttf':'font/ttf','.png':'image/png'}[file.suffix])
            actor=store.authenticate(self.token())
            if path.startswith('/api/ai/'):
                from ai_gateway import dispatch
                return dispatch(self,actor,path,method,payload)
            if path.startswith('/api/workspace/'):
                from workspace_http import dispatch
                if path.endswith('/changes'):
                    if not self.server.change_slots.acquire(False):raise DomainError('دریافت تغییرات شلوغ است؛ دوباره تلاش کنید.',429)
                    query['_closing']=self.server.closing
                    try:return self.reply(dispatch(store,actor,path,method,payload,query))
                    finally:self.server.change_slots.release()
                return self.reply(dispatch(store,actor,path,method,payload,query))
            if path=='/api/me':return self.reply(actor)
            if path=='/api/schema':
                from permission_policy import schema
                return self.reply(dict(schemas=SCHEMAS,roles=ROLES,statuses=STATUSES,permissions=schema()))
            if path=='/api/companies':
                if method=='POST' and payload.get('id'):store.require_module(actor,payload['id'],'company','edit')
                return self.reply(store.company_profiles(actor) if method=='GET' else store.save_company(actor,payload))
            if path=='/api/profile':return self.reply(store.own_profile(actor) if method=='GET' else store.save_profile(actor,payload))
            if path=='/api/birthdays' and method=='GET':return self.reply(store.birthdays_snapshot(actor))
            if path=='/api/birthdays/ack' and method=='POST':return self.reply(store.birthday_ack(actor,**payload))
            if path=='/api/desk':store.require_module(actor,None,'desk','view');return self.reply(store.desk_snapshot(actor))
            if path=='/api/desk/leave' and method=='POST':return self.reply(store.desk_leave_save(actor,**payload))
            if path=='/api/desk/review' and method=='POST':return self.reply(store.desk_leave_review(actor,**payload))
            if path=='/api/desk/cancel' and method=='POST':return self.reply(store.desk_leave_cancel(actor,**payload))
            if path=='/api/desk/note' and method=='POST':return self.reply(store.desk_note_save(actor,**payload))
            if path=='/api/desk/delete-note' and method=='POST':return self.reply(store.desk_note_delete(actor,**payload))
            if path=='/api/desk/restore' and method=='POST':return self.reply(store.desk_restore_notes(actor,payload['notes']))
            if path=='/api/desk/notification' and method=='POST':return self.reply(store.desk_notification(actor,**payload))
            if path=='/api/chat/rooms':return self.reply(store.chat_rooms(actor))
            if path=='/api/chat/messages':return self.reply(store.chat_list(actor,query['company'],query['room'],query.get('before'),query.get('limit',50),q=query.get('q',''),thread=query.get('thread'),saved=query.get('saved')=='1',pinned=query.get('pinned')=='1') if method=='GET' else store.chat_send(actor,**payload))
            if path=='/api/chat/action' and method=='POST':return self.reply(store.chat_action(actor,**payload))
            if path=='/api/chat/state' and method=='POST':return self.reply(store.chat_state(actor,**payload))
            if path=='/api/chat/scheduled':return self.reply(store.chat_scheduled_list(actor,query['company'],query['room']) if method=='GET' else store.chat_schedule(actor,**payload))
            if path=='/api/chat/scheduled/cancel' and method=='POST':return self.reply(store.chat_scheduled_cancel(actor,**payload))
            if path=='/api/chat/scheduled/reschedule' and method=='POST':return self.reply(store.chat_scheduled_reschedule(actor,**payload))
            if path=='/api/chat/file':return self.reply(store.chat_download(actor,query['id']))
            if path=='/api/chat/updates':return self.reply(store.chat_updates(actor,query.get('after',0)))
            if path=='/api/users':
                if method!='GET':return self.reply(store.save_user(actor,payload))
                users=store.users(actor)
                for person in users:
                    for membership in person.get('memberships',[]):
                        if person['id']!=actor['id'] and not (store.desk_manager(actor,membership['company_id']) and store.module_permission(actor,membership['company_id'],'access','view')):membership.pop('permissions',None)
                return self.reply(users)
            if path=='/api/permissions' and method=='POST':return self.reply(store.save_permissions(actor,**payload))
            if path=='/api/invoice/next-number' and method=='GET':return self.reply(store.finance_next_invoice_number(actor,query.get('company'),query.get('kind')))
            if path=='/api/inventory' and method=='GET':return self.reply(store.inventory_list(actor,query.get('company')))
            if path=='/api/inventory/group' and method=='POST':return self.reply(store.inventory_group(actor,**payload))
            if path=='/api/inventory/product' and method=='POST':return self.reply(store.inventory_product(actor,**payload))
            if path=='/api/inventory/archive' and method=='POST':return self.reply(store.inventory_archive(actor,**payload))
            if path=='/api/inventory/adjust' and method=='POST':return self.reply(store.inventory_adjust(actor,**payload))
            if path=='/api/finance' and method=='GET':return self.reply(store.finance_list(actor,query.get('company')))
            if path=='/api/finance/check-history' and method=='GET':return self.reply(store.finance_check_history(actor,query.get('company'),query.get('id')))
            if path=='/api/finance/check-alerts' and method=='GET':return self.reply(store.finance_check_alerts(actor,query.get('company')))
            if path=='/api/finance/receipts' and method=='GET':return self.reply(store.finance_receipt_list(actor,query.get('company'),query.get('transaction_id')))
            if path=='/api/finance/receipt' and method=='GET':return self.reply(store.finance_receipt_get(actor,query.get('company'),query.get('id')))
            if path=='/api/finance/receipt' and method=='POST':return self.reply(store.finance_receipt_add(actor,**payload))
            if path=='/api/finance/bank' and method=='POST':return self.reply(store.finance_bank_add(actor,**payload))
            if path=='/api/finance/check' and method=='POST':return self.reply(store.finance_check_add(actor,**payload))
            if path=='/api/finance/check/edit' and method=='POST':return self.reply(store.finance_check_edit(actor,**payload))
            if path=='/api/finance/check/status' and method=='POST':return self.reply(store.finance_check_status(actor,**payload))
            if path=='/api/finance/check-transfer' and method=='POST':return self.reply(store.finance_transfer_check(actor,**payload))
            if path=='/api/finance/check-untransfer' and method=='POST':return self.reply(store.finance_untransfer_check(actor,**payload))
            if path=='/api/finance/transaction' and method=='POST':return self.reply(store.finance_transaction(actor,**payload))
            if path=='/api/finance/bank-match' and method=='POST':return self.reply(store.finance_match_bank(actor,**payload))
            if path=='/api/finance/bank-unmatch' and method=='POST':return self.reply(store.finance_unmatch_bank(actor,**payload))
            if path=='/api/records':
                if method=='GET':
                    data=store.list_records(actor,query.get('kind'),query.get('company'),query.get('q',''),int(query.get('limit',100)),int(query.get('page',1)));data['items']=[public_record(store,actor,r) for r in data['items']];return self.reply(data)
                return self.reply(public_record(store,actor,store.save_record(actor,**payload)))
            if path=='/api/record':return self.reply(public_record(store,actor,store.record(query['id'])))
            if path=='/api/archive' and method=='POST':return self.reply(store.delete_record(actor,payload['id'],payload['version']))
            if path=='/api/comments':return self.reply(store.comments(actor,query['id']) if method=='GET' else store.add_comment(actor,payload['id'],payload['text']))
            if path=='/api/files':return self.reply(store.file_list(actor,query['id']) if method=='GET' else store.add_file(actor,payload['id'],payload['name'],base64.b64decode(payload['data'],validate=True),payload.get('mime','application/octet-stream')))
            if path=='/api/file':
                info,data=store.read_file(actor,query['id']);return self.reply(dict(info=info,data=base64.b64encode(data).decode()))
            if path=='/api/extract' and method=='POST':return self.reply(store.extract_document(actor,payload['id']))
            if path=='/api/notices' and method=='POST':return self.reply(store.publish(actor,payload))
            if path=='/api/inbox':return self.reply(store.inbox(actor))
            if path=='/api/receipt' and method=='POST':return self.reply(store.acknowledge(actor,payload['id'],payload['action']))
            if path=='/api/receipts':return self.reply(store.receipt_report(actor,query['id']))
            if path=='/api/history':return self.reply(store.history(actor,query.get('id')))
            if path=='/api/dashboard':return self.reply(store.dashboard(actor,query.get('company')))
            if path=='/api/search':return self.reply(store.knowledge_search(actor,query.get('q',''),query.get('company')))
            if path=='/api/attendance' and method=='POST':return self.reply(store.import_attendance(actor,payload['company'],payload['rows'],payload['month']))
            if path=='/api/payroll':return self.reply(store.payroll(actor,query['company'],query['month']))
            if path=='/api/export':
                data=store.export_scope(actor,query.get('company'));files={}
                for f in data['files']:
                    raw=(store.files/(f['id']+'.bin')).read_bytes();files[f['id']]=base64.b64encode(raw).decode()
                return self.reply(dict(data=data,attachments=files))
            if path=='/api/logout' and method=='POST':store.logout(self.token());return self.reply({'ok':True},headers={'Set-Cookie':'karname=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
            raise DomainError('مسیر پیدا نشد.',404)
        except DomainError as exc:self.reply({'error':str(exc)},exc.status)
        except (ValueError,KeyError,TypeError) as exc:self.reply({'error':'اطلاعات درخواست معتبر نیست: '+str(exc)[:180]},400)
        except sqlite3.IntegrityError:self.reply({'error':'نام تکراری یا پیوند پرونده معتبر نیست.'},409)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError,TimeoutError):pass
        except Exception:self.reply({'error':'عملیات انجام نشد؛ اطلاعات حفظ شده‌اند. گزارش میزبان را بررسی کنید.'},500)

class RunningServer:
    def __init__(self,folder,host='127.0.0.1',port=8843,tls=False,cert=None,key=None,background=True,discovery=False,discovery_port=8844):
        if not tls and host not in ('127.0.0.1','localhost','::1'):raise ValueError('اتصال شبکه باید HTTPS باشد؛ HTTP فقط روی همین کامپیوتر مجاز است.')
        self.store=Store(folder)
        if host not in ('127.0.0.1','localhost','::1') and not self.store.initialized():raise ValueError('ابتدا مدیر اولیه را روی همین میزبان بسازید.')
        self.server=CompanyServer((host,int(port)),self.store,tls)
        try:
            if tls:
                context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.minimum_version=ssl.TLSVersion.TLSv1_2;context.load_cert_chain(cert,key);self.server.socket=context.wrap_socket(self.server.socket,server_side=True)
            self.store.reset_chat_once()
        except Exception:self.server.server_close();raise
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.port=self.server.server_port;self.stop_event=threading.Event();self.worker=threading.Thread(target=self.work,daemon=True) if background else None
        self.discovery=None
        if discovery:
            if not tls:self.close();raise ValueError('کشف خودکار شبکه به HTTPS نیاز دارد.')
            try:
                from lan_discovery import Responder
                self.discovery=Responder(cert,key,self.port,discovery_port)
            except Exception:self.close();raise
        if self.worker:self.worker.start()
    def work(self):
        import time
        next_automation=0
        while not self.stop_event.is_set():
            try:self.store.process_scheduled_chat()
            except Exception:pass
            if time.monotonic()>=next_automation:
                try:self.store.run_automations()
                except Exception:pass
                next_automation=time.monotonic()+60
            if self.stop_event.wait(5):break
    def close(self):
        if getattr(self,'discovery',None):self.discovery.close();self.discovery=None
        self.stop_event.set();self.server.closing.set();self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)


