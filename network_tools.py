"""Connection diagnostics and an opt-in host at Windows sign-in."""
import os,sys,json,socket,subprocess,hashlib,time,ctypes,tempfile
from pathlib import Path
from urllib.parse import urlsplit
from org_client import validate_url,Client

def autohost_enabled(root,fallback=False):
    try:return bool(json.loads((Path(root)/'company-host-autostart.json').read_text('utf-8')).get('enabled',False))
    except (OSError,ValueError):return fallback

def diagnose(url,certificate=None):
    results=[]
    try:
        url=validate_url(url);p=urlsplit(url);port=p.port or (443 if p.scheme=='https' else 80);socket.getaddrinfo(p.hostname,port);results.append(dict(step='شناخت نشانی میزبان',ok=True))
    except Exception as e:return [dict(step='نشانی میزبان',ok=False,message='نام یا نشانی میزبان معتبر یا قابل شناسایی نیست. '+str(e)[:200])]
    try:
        with socket.create_connection((p.hostname,port),timeout=3):pass
        results.append(dict(step='دسترسی به درگاه',ok=True))
    except OSError:return results+[dict(step='دسترسی به درگاه',ok=False,message='میزبان خاموش است، درگاه درست نیست یا ارتباط شبکه اجازه عبور نمی‌دهد. نشانی، شبکه مشترک و تنظیم مسئول شبکه را بررسی کنید.')]
    try:
        c=Client(url,certificate);status=c.request('status');c.session.close();results.append(dict(step='پاسخ کارنامه و گواهی اتصال',ok=True,message='نسخه '+status['version']));return results
    except Exception as e:return results+[dict(step='پاسخ کارنامه / گواهی',ok=False,message=str(e))]

def startup_command(root):
    args=[sys.executable]+([] if getattr(sys,'frozen',False) else [str(Path(__file__).with_name('launcher.py'))])+['--company-host','--host-root',str(Path(root).resolve())]
    return subprocess.list2cmdline(args)

def start_autohost(root):
    root=Path(root).resolve()
    try:enabled=json.loads((root/'company-host-autostart.json').read_text('utf-8')).get('enabled',False)
    except (OSError,ValueError):enabled=False
    if not enabled:return None
    executable=sys.executable
    if os.name=='nt' and getattr(sys,'frozen',False) and os.getenv('LOCALAPPDATA'):
        installed=Path(os.environ['LOCALAPPDATA'])/'Programs'/'Karname'/'Karname.exe'
        if installed.is_file():executable=str(installed)
    args=[executable]+([] if getattr(sys,'frozen',False) else [str(Path(__file__).with_name('launcher.py'))])+['--company-host','--host-root',str(root)]
    kwargs={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    if getattr(sys,'frozen',False):kwargs['env']=dict(os.environ,PYINSTALLER_RESET_ENVIRONMENT='1')
    return subprocess.Popen(args,**kwargs)

def _process_alive(pid):
    if not isinstance(pid,int) or pid<=0:return False
    if os.name!='nt':
        try:os.kill(pid,0);return True
        except OSError:return False
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.OpenProcess.argtypes=[ctypes.c_uint,ctypes.c_int,ctypes.c_uint];kernel.OpenProcess.restype=ctypes.c_void_p;kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint];kernel.CloseHandle.argtypes=[ctypes.c_void_p];handle=kernel.OpenProcess(0x100000,False,pid)
    if not handle:return False
    try:return kernel.WaitForSingleObject(handle,0)==0x102
    finally:kernel.CloseHandle(handle)

def stop_autohost(root,timeout=8):
    root=Path(root).resolve();status=root/'company-host-status.json';(root/'company-host.stop').write_text('stop','ascii');deadline=time.monotonic()+timeout
    while True:
        try:state=json.loads(status.read_text('utf-8'))
        except (OSError,ValueError):return
        if not state.get('running') or not _process_alive(state.get('pid')):return
        if time.monotonic()>=deadline:raise ValueError('مرکز مستقل هنوز بسته نشده است؛ پیش از بازگردانی یا تغییر میزبان، آن را ببندید.')
        time.sleep(.1)

def set_autohost(root,enabled):
    if os.name!='nt':raise OSError('اجرای خودکار مرکز به ویندوز نیاز دارد.')
    import winreg
    root=Path(root);cfgpath=root/'server-host.json'
    try:cfg=json.loads(cfgpath.read_text('utf-8'))
    except (OSError,ValueError):raise ValueError('ابتدا میزبان HTTPS شرکت را راه‌اندازی کنید.')
    if enabled and (not cfg.get('enabled') or not (root/'company-server/server-cert.pem').is_file()):raise ValueError('ابتدا میزبان HTTPS و گواهی آن را آماده کنید.')
    name='KarnameCompanyHost-'+hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:12]
    # The local marker lets a running helper notice disablement and allows a
    # previously stopped helper to restart at the next sign-in.
    state=root/'company-host-autostart.json';old=state.read_bytes() if state.exists() else None
    fd,temp=tempfile.mkstemp(prefix='.host-',suffix='.tmp',dir=root);os.close(fd);temp=Path(temp)
    try:temp.write_text(json.dumps(dict(enabled=bool(enabled))),encoding='utf-8');os.replace(temp,state)
    finally:temp.unlink(missing_ok=True)
    try:
      with winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Run') as reg:
        if enabled:winreg.SetValueEx(reg,name,0,winreg.REG_SZ,startup_command(root));(root/'company-host.stop').unlink(missing_ok=True)
        else:
            try:winreg.DeleteValue(reg,name)
            except FileNotFoundError:pass
            (root/'company-host.stop').write_text('stop','ascii')
    except Exception:
        if old is None:state.unlink(missing_ok=True)
        else:state.write_bytes(old)
        raise
    return enabled

def run_host(root):
    from org_http import RunningServer
    root=Path(root).resolve();cfg=json.loads((root/'server-host.json').read_text('utf-8'))
    if not cfg.get('enabled'):return
    state=root/'company-host-autostart.json'
    try:enabled=json.loads(state.read_text('utf-8')).get('enabled',False)
    except (OSError,ValueError):enabled=False
    if not enabled:return
    (root/'company-host.stop').unlink(missing_ok=True)
    mutex=None
    if os.name=='nt':
        kernel=ctypes.windll.kernel32;kernel.CreateMutexW.restype=ctypes.c_void_p;kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p];kernel.CloseHandle.argtypes=[ctypes.c_void_p];mutex=kernel.CreateMutexW(None,False,'Local\\KarnameHost-'+hashlib.sha256(str(root).encode()).hexdigest()[:24])
        if kernel.GetLastError()==183:
            if mutex:kernel.CloseHandle(mutex)
            return
    server=None
    try:
        folder=root/'company-server';server=RunningServer(folder,'0.0.0.0',int(cfg['port']),True,folder/'server-cert.pem',folder/'server-key.pem',discovery=True);(root/'company-host-status.json').write_text(json.dumps(dict(running=True,pid=os.getpid(),port=server.port,automatic_network=True)),'utf-8')
        while not (root/'company-host.stop').exists():
            try:
                if not json.loads(state.read_text('utf-8')).get('enabled',False):break
            except (OSError,ValueError):break
            time.sleep(1)
    finally:
        if server:server.close()
        (root/'company-host-status.json').write_text(json.dumps(dict(running=False)),'utf-8')
        if mutex:kernel.CloseHandle(mutex)
