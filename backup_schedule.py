"""Scheduled snapshots, integrity checks and scoped generation rotation."""
import copy,json,sqlite3,tempfile,os,shutil,uuid,zipfile
from contextlib import closing
from pathlib import Path
from datetime import datetime,timezone,timedelta
from backup_bundle import create_bundle,verify_bundle
from local_vault import load

def collect(owner):
    data=copy.deepcopy(owner.data);extras={};user=owner.session_user
    if user:extras['account/profile.json']=json.dumps(dict(id=user['id'],profile=user.get('profile',{})),ensure_ascii=False).encode()
    revision=None
    if owner.can_backup_server():
        store=owner.company_server.store
        with store.lock,tempfile.TemporaryDirectory(dir=owner.base_dir) as temp:
            db=Path(temp)/'company.sqlite';store.backup_database(db)
            with closing(sqlite3.connect(db)) as c:
                c.execute('DELETE FROM sessions');c.execute('DELETE FROM login_limits');revision=c.execute('SELECT COALESCE(MAX(id),0) FROM audit').fetchone()[0];c.commit()
            extras['server/company.sqlite']=db.read_bytes()
            for f in store.files.glob('*.bin'):extras['server/files/'+f.name]=f.read_bytes()
    return data,extras,revision

def create_scheduled(folder,data,extras,password,keep_daily=7,keep_weekly=4,second=None,clock=None):
    if not isinstance(password,str) or not password:raise ValueError('برای پشتیبان خودکار رمز تعیین کنید.')
    clock=clock or datetime.now().astimezone();folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);result=[]
    for kind,period,keep in [('daily',clock.strftime('%Y%m%d'),keep_daily),('weekly',clock.strftime('%G-W%V'),keep_weekly)]:
        if not 1<=int(keep)<=365:raise ValueError('تعداد نسخه‌ها بین ۱ و ۳۶۵ باشد.')
        standard=folder/f'Karname-auto-{kind}-{period}.karname';target=None
        candidates=[p for p in [standard,*folder.glob(f'Karname-auto-{kind}-{period}-*.karname')] if p.exists()]
        for candidate in sorted(candidates,key=lambda p:p.stat().st_mtime,reverse=True):
            try:verify_bundle(candidate,password=password);target=candidate;break
            except (ValueError,zipfile.BadZipFile,KeyError,TypeError):pass
        if target is None:
            # A password change or damaged prior snapshot must not block future
            # backups or overwrite an earlier copy.
            target=standard if not candidates else folder/f'Karname-auto-{kind}-{period}-{uuid.uuid4().hex[:12]}.karname'
            create_bundle(target,data,extras,password=password)
        # Verify before rotation or reporting successful backup.
        verify_bundle(target,password=password);result.append(str(target))
        if second:
            dest=Path(second);dest.mkdir(parents=True,exist_ok=True)
            if dest.resolve()==folder.resolve():raise ValueError('محل دوم با محل اصلی متفاوت باشد.')
            other=dest/target.name;fd,name=tempfile.mkstemp(prefix='.karname-copy-',suffix='.tmp',dir=dest);os.close(fd);tmp=Path(name)
            try:shutil.copyfile(target,tmp);verify_bundle(tmp,password=password);os.replace(tmp,other)
            finally:tmp.unlink(missing_ok=True)
        for place in [folder]+([Path(second)] if second else []):
            prefix='Karname-auto-'+kind+'-';period_len=8
            files=sorted(place.glob(prefix+'*.karname'),key=lambda x:(x.name[len(prefix):len(prefix)+period_len],x.name==target.name,x.stat().st_mtime),reverse=True)
            for old in files[int(keep):]:old.unlink()
    return result
