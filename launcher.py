"""Report startup/import failures even in the windowed executable."""
import os
import sys
import traceback
import faulthandler
from pathlib import Path

_fault_log = None
def enable_crash_log():
    """Keep native crash traces available after an unexpected Qt failure."""
    global _fault_log
    try:
        folder=Path(os.getenv('TAXCALENDAR_DATA_DIR') or Path(os.getenv('APPDATA') or Path.home())/'TaghvimMaliatiFA')
        folder.mkdir(parents=True,exist_ok=True)
        _fault_log=(folder/'native-crash.log').open('a',encoding='utf-8')
        _fault_log.write('\n--- process %s ---\n' % os.getpid());_fault_log.flush()
        faulthandler.enable(file=_fault_log,all_threads=True)
    except (OSError,RuntimeError):
        if _fault_log:_fault_log.close();_fault_log=None

def report(exc_type, exc, tb):
    detail=''.join(traceback.format_exception(exc_type,exc,tb))
    folder=Path(os.getenv('TAXCALENDAR_DATA_DIR') or Path(os.getenv('APPDATA') or Path.home())/'TaghvimMaliatiFA')
    folder.mkdir(parents=True,exist_ok=True)
    log=folder/'error.log'
    with log.open('a',encoding='utf-8') as f:f.write(detail+'\n')
    if os.name=='nt':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,'برنامه با خطا روبه‌رو شد. گزارش خطا:\n'+str(log)+'\n\n'+str(exc),'کارنامه',0x10)

if __name__=='__main__':
    sys.excepthook=report
    enable_crash_log()
    try:
        if '--enable-autohost' in sys.argv:
            from network_tools import set_autohost,start_autohost
            root=sys.argv[sys.argv.index('--host-root')+1];set_autohost(root,True);start_autohost(root)
        elif '--company-host' in sys.argv:
            from network_tools import run_host
            root=sys.argv[sys.argv.index('--host-root')+1];run_host(root)
        else:
            from app import main
            main()
    except Exception:
        report(*sys.exc_info())
        sys.exit(1)
