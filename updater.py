"""Signed update packages are staged; the running executable is never overwritten."""
import json,hashlib,zipfile,base64,os,re,uuid,subprocess,sys,tempfile
from pathlib import Path
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
from storage import package_file

from version_info import APP_VERSION
CURRENT=APP_VERSION
def version(v):
    if not re.fullmatch(r'\d{1,3}(\.\d{1,3}){1,3}',str(v)):raise ValueError('شماره نسخه معتبر نیست.')
    parts=tuple(map(int,str(v).split('.')));return parts+(0,)*(4-len(parts))

def verify_manifest(raw,signature,public_key=None):
    try:
        key=serialization.load_pem_public_key((Path(public_key) if public_key else package_file('assets/update-public.pem')).read_bytes());key.verify(signature,raw,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256());m=json.loads(raw)
        if m.get('format')!='karname-update-v1' or not isinstance(m.get('files'),dict):raise ValueError()
        version(m['version']);return m
    except Exception:raise ValueError('امضا یا ساختار بسته به‌روزرسانی مورد اعتماد نیست.')

def inspect_package(path,public_key=None,allow_current=False):
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)) or not {'update.json','update.sig','Karname.exe'}<=set(names):raise ValueError('بسته به‌روزرسانی کامل نیست.')
        if len(names)>100 or sum(i.file_size for i in z.infolist())>512*1024*1024:raise ValueError('بسته به‌روزرسانی بیش از حد بزرگ است.')
        m=verify_manifest(z.read('update.json'),z.read('update.sig'),public_key)
        if not allow_current and version(m['version'])<=version(CURRENT):raise ValueError('این بسته از نسخه فعلی جدیدتر نیست.')
        if set(names)!=(set(m['files'])|{'update.json','update.sig'}) or any(name not in ('Karname.exe','README_FA.md','FONT_LICENSE.txt') for name in m['files']):raise ValueError('فهرست بسته به‌روزرسانی معتبر نیست.')
        for name,meta in m['files'].items():
            raw=z.read(name)
            if len(raw)!=meta['size'] or hashlib.sha256(raw).hexdigest()!=meta['sha256']:raise ValueError('فایل به‌روزرسانی آسیب دیده است.')
        if not z.read('Karname.exe').startswith(b'MZ'):raise ValueError('برنامه ویندوز معتبر نیست.')
        return m

def stage_package(path,root,public_key=None,allow_current=False):
    m=inspect_package(path,public_key,allow_current);root=Path(root).resolve();stage=root/'updates'/('stage-'+uuid.uuid4().hex);stage.mkdir(parents=True)
    try:
        with zipfile.ZipFile(path) as z:
            raw=z.read('update.json');sig=z.read('update.sig')
            # Re-check after reopening: a package may have changed between the
            # inspection and extraction, even if it is stored on a network share.
            if verify_manifest(raw,sig,public_key)!=m:raise ValueError('بسته در هنگام آماده‌سازی تغییر کرد.')
            for name,expected in m['files'].items():
                content=z.read(name)
                if len(content)!=expected['size'] or hashlib.sha256(content).hexdigest()!=expected['sha256']:raise ValueError('یکی از فایل‌های آماده‌شده تغییر کرده است.')
                (stage/name).write_bytes(content)
            (stage/'update.json').write_bytes(raw);(stage/'update.sig').write_bytes(sig)
        return stage,m
    except Exception:
        # Only remove files that this invocation created in its own unique stage.
        for name in list(m['files'])+['update.json','update.sig']:(stage/name).unlink(missing_ok=True)
        stage.rmdir();raise

def feed(url,verify=True):
    from urllib.parse import urlsplit
    import requests
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password:raise ValueError('پیوند فهرست نسخه‌ها باید HTTPS باشد.')
    session=requests.Session();session.trust_env=False
    with session.get(url,timeout=(5,15),verify=verify,stream=True,allow_redirects=False) as r:
        r.raise_for_status()
        if r.status_code!=200:raise ValueError('دریافت فهرست نسخه‌ها ناموفق بود.')
        raw=bytearray()
        for block in r.iter_content(65536):
            raw.extend(block)
            if len(raw)>100000:raise ValueError('فهرست نسخه‌ها بیش از حد بزرگ است.')
    envelope=json.loads(raw);manifest=base64.b64decode(envelope['manifest'],validate=True);signature=base64.b64decode(envelope['signature'],validate=True);return verify_manifest(manifest,signature)

def download_package(url,root,expected_version,verify=True):
    from urllib.parse import urlsplit
    import requests
    p=urlsplit(url)
    if p.scheme!='https' or not p.hostname or p.username or p.password:raise ValueError('نشانی بسته باید HTTPS باشد.')
    folder=Path(root).resolve()/'updates';folder.mkdir(parents=True,exist_ok=True);fd,temp=tempfile.mkstemp(dir=folder,prefix='.download-',suffix='.tmp');os.close(fd);temp=Path(temp);target=folder/('download-'+uuid.uuid4().hex+'.karname-update')
    session=requests.Session();session.trust_env=False
    try:
        with session.get(url,timeout=(5,30),verify=verify,stream=True,allow_redirects=False) as r:
            r.raise_for_status()
            if r.status_code!=200:raise ValueError('دریافت بسته ناموفق بود.')
            size=0
            with temp.open('wb') as out:
                for block in r.iter_content(65536):
                    size+=len(block)
                    if size>512*1024*1024:raise ValueError('حجم بسته به‌روزرسانی بیش از حد مجاز است.')
                    out.write(block)
        m=inspect_package(temp)
        if version(m['version'])!=version(expected_version):raise ValueError('نسخه بسته با فهرست امضاشده یکسان نیست.')
        os.replace(temp,target);return target,m
    finally:session.close();temp.unlink(missing_ok=True)

def powershell_quote(value):return "'"+str(value).replace("'","''")+"'"

def helper_script(stage,target,pid,history,expected=None,old_expected=None):
    stage=Path(stage).resolve();target=Path(target).resolve();history=Path(history).resolve()
    if expected is None:expected=json.loads((stage/'update.json').read_text('utf-8'))['files']['Karname.exe']['sha256']
    if old_expected is None:old_expected=hashlib.sha256(target.read_bytes()).hexdigest()
    if not re.fullmatch('[0-9a-f]{64}',expected) or not re.fullmatch('[0-9a-f]{64}',old_expected):raise ValueError('اثر انگشت برنامه معتبر نیست.')
    return '''$ErrorActionPreference='Stop'
$target='''+powershell_quote(target)+'''
$stage='''+powershell_quote(stage)+'''
$history='''+powershell_quote(history)+'''
$processId='''+str(int(pid))+'''
function Get-Sha256([string]$Path) {
    $sha=[System.Security.Cryptography.SHA256]::Create()
    $stream=[System.IO.File]::OpenRead($Path)
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose(); $sha.Dispose() }
}
try {
    $deadline=(Get-Date).AddMinutes(2)
    while (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
        if ((Get-Date) -gt $deadline) { throw 'برنامه قبلی بسته نشد.' }
        Start-Sleep -Milliseconds 300
    }
    while (Get-Process -Name 'Karname' -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $target }) {
        if ((Get-Date) -gt $deadline) { throw 'نسخه دیگری از همین برنامه هنوز باز است.' }
        Start-Sleep -Milliseconds 300
    }
    New-Item -ItemType Directory -Path $history -Force | Out-Null
    $old=Join-Path $history 'Karname.exe'
    if ((Get-Sha256 $target) -ne '''+powershell_quote(old_expected)+''') { throw 'برنامه فعلی هنگام آماده‌سازی تغییر کرده است.' }
    Copy-Item -LiteralPath $target -Destination $old -Force
    $expected='''+powershell_quote(expected)+'''
    $incoming=Join-Path $stage 'Karname.exe'
    if ((Get-Sha256 $incoming) -ne $expected) { throw 'فایل آماده‌شده تغییر کرده است.' }
    try {
        Copy-Item -LiteralPath $incoming -Destination ($target+'.new') -Force
        Move-Item -LiteralPath ($target+'.new') -Destination $target -Force
        foreach ($name in @('README_FA.md','FONT_LICENSE.txt')) {
            $source=Join-Path $stage $name
            if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination (Join-Path (Split-Path -Parent $target) $name) -Force }
        }
        Set-Content -LiteralPath (Join-Path $history 'installed.ok') -Value 'ok'
    } catch {
        Copy-Item -LiteralPath $old -Destination $target -Force
        throw
    }
    Start-Process -FilePath $target -ArgumentList '--show' -WindowStyle Hidden
} catch {
    Set-Content -LiteralPath (Join-Path $stage 'update-error.txt') -Value $_.Exception.Message -Encoding UTF8
}
'''

def launch_helper(stage,target,root,public_key=None):
    root=Path(root).resolve();stage=Path(stage).resolve();target=Path(target).resolve()
    if stage.parent!=root/'updates' or not stage.name.startswith(('stage-','rollback-')):raise ValueError('مسیر بسته آماده‌شده معتبر نیست.')
    if (stage/'update.sig').exists():m=verify_manifest((stage/'update.json').read_bytes(),(stage/'update.sig').read_bytes(),public_key)
    else:
        proof=json.loads((stage/'rollback-source.json').read_text('utf-8'));source=Path(proof['history']).resolve()
        if source.parent!=root/'updates' or not source.name.startswith('previous-') or not (source/'installed.ok').is_file():raise ValueError('نسخه قبلی معتبر نیست.')
        info=json.loads((source/'rollback.json').read_text('utf-8'));m=json.loads((stage/'update.json').read_text('utf-8'))
        if m['files']['Karname.exe']['sha256']!=info['sha256']:raise ValueError('نسخه قبلی تغییر کرده است.')
    for name,meta in m['files'].items():
        if name not in ('Karname.exe','README_FA.md','FONT_LICENSE.txt'):raise ValueError('فایل به‌روزرسانی معتبر نیست.')
        raw=(stage/name).read_bytes()
        if len(raw)!=meta['size'] or hashlib.sha256(raw).hexdigest()!=meta['sha256']:raise ValueError('بسته آماده‌شده تغییر کرده است.')
    history=root/'updates'/('previous-'+uuid.uuid4().hex);history.mkdir(parents=True);old_expected=hashlib.sha256(target.read_bytes()).hexdigest();(history/'rollback.json').write_text(json.dumps(dict(format='karname-rollback-v1',sha256=old_expected,size=target.stat().st_size,version=CURRENT)),'utf-8');script=stage/'apply.ps1';script.write_text(helper_script(stage,target,os.getpid(),history,m['files']['Karname.exe']['sha256'],old_expected),encoding='utf-8-sig');kwargs={}
    if os.name=='nt':kwargs['creationflags']=subprocess.CREATE_NO_WINDOW
    subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File',str(script)],**kwargs);return history

def stage_rollback(history,root):
    root=Path(root).resolve();history=Path(history).resolve()
    if history.parent!=(root/'updates') or not history.name.startswith('previous-') or not (history/'installed.ok').is_file():raise ValueError('نسخه قبلی معتبر نیست.')
    meta=json.loads((history/'rollback.json').read_text('utf-8'));raw=(history/'Karname.exe').read_bytes()
    if meta.get('format')!='karname-rollback-v1' or len(raw)!=meta['size'] or hashlib.sha256(raw).hexdigest()!=meta['sha256']:raise ValueError('نسخه قبلی آسیب دیده است.')
    stage=root/'updates'/('rollback-'+uuid.uuid4().hex);stage.mkdir();(stage/'Karname.exe').write_bytes(raw);(stage/'update.json').write_text(json.dumps(dict(files={'Karname.exe':dict(size=len(raw),sha256=meta['sha256'])},version=meta['version'])),'utf-8');(stage/'rollback-source.json').write_text(json.dumps(dict(history=str(history))),'utf-8');return stage


