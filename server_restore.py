"""Validate a complete server backup, stage it, then swap closed directories."""
import hashlib,os,re,shutil,sqlite3,tempfile,uuid
from contextlib import closing
from pathlib import Path
from backup_bundle import verify_bundle

def inspect_server_backup(path,password=None):
    data,entries,manifest=verify_bundle(path,password=password)
    if 'server/company.sqlite' not in entries:raise ValueError('این فایل پشتیبان کامل میزبان نیست؛ برای تقویم از بازگردانی معمولی استفاده کنید.')
    with tempfile.TemporaryDirectory() as folder:
        db=Path(folder)/'company.sqlite';db.write_bytes(entries['server/company.sqlite'])
        with closing(sqlite3.connect(db)) as c:
            if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('پایگاه اطلاعات پشتیبان سالم نیست.')
            if not c.execute("SELECT 1 FROM users WHERE global_role='group_admin' AND active=1").fetchone():raise ValueError('پشتیبان باید دست‌کم یک مدیر کل فعال داشته باشد.')
            users=c.execute('SELECT COUNT(*) FROM users').fetchone()[0];records=c.execute('SELECT COUNT(*) FROM records WHERE deleted=0').fetchone()[0]
            for id,digest,size in c.execute('SELECT id,sha256,size FROM files'):
                if not re.fullmatch('[0-9a-f]{32}',id):raise ValueError('شناسه مدرک در پشتیبان معتبر نیست.')
                raw=entries.get('server/files/'+id+'.bin')
                if raw is None or len(raw)!=size or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('یکی از مدارک پشتیبان ناقص یا ناسالم است.')
            if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='chat_files'").fetchone():
                for id,digest,size in c.execute('SELECT id,sha256,size FROM chat_files'):
                    if not re.fullmatch('[0-9a-f]{32}',id):raise ValueError('شناسه پیوست چت معتبر نیست.')
                    raw=entries.get('server/files/'+id+'.bin')
                    if raw is None or len(raw)!=size or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('یکی از پیوست‌های چت ناقص یا ناسالم است.')
            if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='finance_receipts'").fetchone():
                for id,digest,size in c.execute('SELECT id,sha256,size FROM finance_receipts'):
                    if not re.fullmatch('[0-9a-f]{32}',id):raise ValueError('شناسه رسید مالی معتبر نیست.')
                    raw=entries.get('server/files/'+id+'.bin')
                    if raw is None or len(raw)!=size or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('یکی از رسیدهای مالی ناقص یا ناسالم است.')
    return data,entries,manifest,dict(users=users,records=records)

def restore_closed_server(root,path,password=None):
    root=Path(root).resolve();target=root/'company-server';data,entries,manifest,counts=inspect_server_backup(path,password=password);stage=root/('company-server-restore-'+uuid.uuid4().hex);archive=root/('company-server-before-restore-'+uuid.uuid4().hex)
    from network_tools import stop_autohost
    stop_autohost(root)
    # Every recursive directory rename is explicitly bounded to this app root.
    for candidate in (target,stage,archive):
        if candidate.resolve().parent!=root:raise ValueError('مسیر بازگردانی خارج از پوشه برنامه است.')
    stage.mkdir();(stage/'files').mkdir();(stage/'company.sqlite').write_bytes(entries['server/company.sqlite'])
    with closing(sqlite3.connect(stage/'company.sqlite')) as c:
        c.execute('DELETE FROM sessions');c.execute('DELETE FROM login_limits')
        # A deliberate restore must not trigger the one-time upgrade reset on
        # its next start and silently erase the chat included in the backup.
        c.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)')
        for marker in ('chat_reset_v9_empty','chat_reset_v9_saved_v2'):
            c.execute('INSERT OR IGNORE INTO meta(key,value) VALUES(?,?)',(marker,'restored'))
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='chat_scheduled'").fetchone():
            from datetime import datetime,timezone
            now=datetime.now(timezone.utc).isoformat(timespec='seconds')
            c.execute("UPDATE chat_scheduled SET status='failed',lease_until=NULL,error=? WHERE status='sending' OR (status='pending' AND due_at<=?)",('پس از بازیابی، وضعیت ارسال پیشین نیازمند بررسی است.',now))
        c.commit()
    for name,raw in entries.items():
        if re.fullmatch(r'server/files/[0-9a-f]{32}\.bin',name):(stage/'files'/Path(name).name).write_bytes(raw)
    # Keep the current host's identity; a backup never supplies executable paths,
    # a TLS private key, or an OCR program to run on the restored machine.
    for name in ('server-cert.pem','server-key.pem','ocr-settings.json'):
        if (target/name).is_file():shutil.copy2(target/name,stage/name)
    moved=False
    try:
        if target.exists():os.replace(target,archive);moved=True
        os.replace(stage,target)
    except Exception:
        if moved and not target.exists():os.replace(archive,target)
        raise
    return counts,archive if moved else None
