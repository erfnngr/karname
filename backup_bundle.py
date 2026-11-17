"""Verified, atomic local backups. A canceled/failed backup never clears dirty state."""
import copy,hashlib,json,os,tempfile,zipfile,io
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone

def digest(data):return hashlib.sha256(data).hexdigest()
def encode(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2).encode('utf-8')
def business_data(data):
    result=copy.deepcopy(data)
    for key in ('official_news','_recovery_notice','company_cache','company_connection_status','shared_alerts','chat_cursor','desk_alerts','finance_check_alerts','pending_desk_restore','pending_profile_restore','backup_schedule_state'):
        result.pop(key,None)
    cache=result.pop('desk_cache',None)
    if isinstance(cache,dict) and (cache.get('notes') or cache.get('leaves')):result['desk_business']={key:cache.get(key,[]) for key in ('notes','leaves')}
    for event in result.get('events',[]):
        for key in ('last_alerts','last_notified','notification_shown'):event.pop(key,None)
    return result
def fingerprint(data):return digest(encode(business_data(data)))

class BackupState:
    def __init__(self,folder,initial):
        self.path=Path(folder)/'backup-state.json';self.baseline=fingerprint(initial);self.server_revision=0
        try:
            value=json.loads(self.path.read_text(encoding='utf-8'));self.baseline=value['fingerprint'];self.server_revision=int(value.get('server_revision',0))
        except (OSError,ValueError,KeyError):
            if any(not e.get('created_from_excel') and not e.get('generated') for e in initial.get('events',[])) or initial.get('penalty_rules') or initial.get('company_write_at'):self.baseline='entered-before-first-backup'
            self._write(self.baseline)
    def _write(self,value):
        self.path.parent.mkdir(parents=True,exist_ok=True);tmp=self.path.with_suffix('.tmp');tmp.write_bytes(encode({'fingerprint':value,'server_revision':self.server_revision,'at':datetime.now(timezone.utc).isoformat()}));os.replace(tmp,self.path)
    def dirty(self,data):return fingerprint(data)!=self.baseline
    def mark_saved(self,data,server_revision=None):
        if server_revision is not None:self.server_revision=server_revision
        current=fingerprint(data);self._write(current);self.baseline=current

def create_bundle(target,data,extras=None,password=None):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    entries={'calendar.json':encode(data)}
    entries.update(extras or {})
    if any(not safe_name(name) or name=='manifest.json' for name in entries):raise ValueError('نام فایل پشتیبان معتبر نیست.')
    from version_info import APP_VERSION
    manifest=dict(format='karname-backup-v2',kind='server' if 'server/company.sqlite' in entries else 'personal',app_version=APP_VERSION,created=datetime.now(timezone.utc).isoformat(),files={k:dict(sha256=digest(v),size=len(v)) for k,v in entries.items()})
    fd,temp=tempfile.mkstemp(prefix='.karname-',suffix='.tmp',dir=target.parent);os.close(fd)
    try:
        # Password-protected backups must never leave a plaintext temporary archive
        # behind after a process crash. The payload was already assembled in memory.
        destination=io.BytesIO() if password else temp
        with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,content in entries.items():archive.writestr(name,content)
            archive.writestr('manifest.json',encode(manifest))
        if password:
            from backup_crypto import seal
            Path(temp).write_bytes(seal(destination.getvalue(),password));verify_bundle(temp,password=password)
        else:verify_bundle(temp)
        os.replace(temp,target)
    finally:Path(temp).unlink(missing_ok=True)
    return target

def safe_name(name):
    p=PurePosixPath(name)
    return bool(name and not p.is_absolute() and '\\' not in name and ':' not in name and '..' not in p.parts and not name.endswith('/'))
def verify_bundle(path,password=None):
    from backup_crypto import source
    with zipfile.ZipFile(source(path,password)) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(names)!=len(set(names)) or len(names)>30000 or any(not safe_name(n) for n in names):raise ValueError('ساختار پشتیبان معتبر نیست.')
        if sum(i.file_size for i in infos)>1024*1024*1024:raise ValueError('حجم پشتیبان بیش از حد مجاز است.')
        if any(i.file_size>100*1024*1024 for i in infos):raise ValueError('یکی از فایل‌ها بیش از حد بزرگ است.')
        manifest=json.loads(z.read('manifest.json'))
        if manifest.get('format') not in ('karname-backup-v1','karname-backup-v2') or set(names)!=(set(manifest['files'])|{'manifest.json'}):raise ValueError('فهرست پشتیبان همخوان نیست.')
        entries={}
        for name,expected in manifest['files'].items():
            value=z.read(name)
            if len(value)!=expected['size'] or digest(value)!=expected['sha256']:raise ValueError('صحت فایل پشتیبان تأیید نشد: '+name)
            entries[name]=value
        data=json.loads(entries['calendar.json'])
        if not isinstance(data,dict) or not isinstance(data.get('events'),list) or not isinstance(data.get('settings'),dict):raise ValueError('اطلاعات تقویم در پشتیبان معتبر نیست.')
        return data,entries,manifest
