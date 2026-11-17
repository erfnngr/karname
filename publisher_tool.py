"""Release signing for the owner. Private material is NEVER bundled with Karname.

Use the separate publisher directory and keep its encrypted key outside releases.
The local DPAPI file grants access only to the current Windows account; a recovery
passphrase can be displayed interactively and kept separately for another machine.
"""
import argparse,base64,getpass,hashlib,json,os,secrets,sys,zipfile
from pathlib import Path
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding,rsa
from local_vault import save,load

# Python on a legacy Windows console may otherwise abort when printing Persian,
# even after the key was successfully created.
for stream in (sys.stdout,sys.stderr):
    if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8',errors='backslashreplace')

def initialize(directory,public_path):
    directory=Path(directory);public_path=Path(public_path);directory.mkdir(parents=True,exist_ok=True);private=directory/'publisher-private.pem';secret=directory/'publisher-pass.dpapi'
    if private.exists() or secret.exists() or public_path.exists():raise ValueError('کلید ناشر یا کلید عمومی از قبل وجود دارد؛ هیچ فایلی جایگزین نشد.')
    passphrase=secrets.token_urlsafe(48);key=rsa.generate_private_key(public_exponent=65537,key_size=3072);raw=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.BestAvailableEncryption(passphrase.encode()))
    fd=os.open(str(private),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'wb') as f:f.write(raw)
        save(secret,{'password':passphrase});public_path.parent.mkdir(parents=True,exist_ok=True)
        with public_path.open('xb') as f:f.write(key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    except Exception:
        private.unlink(missing_ok=True);secret.unlink(missing_ok=True)
        raise
    return directory

def private_key(directory,recovery=False):
    directory=Path(directory);secret=directory/'publisher-pass.dpapi'
    passphrase=getpass.getpass('رمز بازیابی ناشر: ') if recovery else (load(secret,{}) or {}).get('password')
    if not passphrase:raise ValueError('رمز کلید ناشر در این حساب ویندوز در دسترس نیست؛ حالت بازیابی را انتخاب کنید.')
    try:return serialization.load_pem_private_key((directory/'publisher-private.pem').read_bytes(),password=passphrase.encode())
    except (ValueError,TypeError):raise ValueError('رمز کلید ناشر نادرست است یا کلید آسیب دیده است.')

def restore(directory):
    directory=Path(directory);passphrase=getpass.getpass('رمز بازیابی ناشر: ')
    try:serialization.load_pem_private_key((directory/'publisher-private.pem').read_bytes(),password=passphrase.encode())
    except (ValueError,TypeError):raise ValueError('رمز کلید ناشر نادرست است یا کلید آسیب دیده است.')
    save(directory/'publisher-pass.dpapi',{'password':passphrase})

def show_recovery(directory):
    secret=load(Path(directory)/'publisher-pass.dpapi',{})
    if not secret or not secret.get('password'):raise ValueError('کلید محلی ناشر پیدا نشد.')
    print('رمز بازیابی را در جایی امن و جدا از بسته برنامه نگه دارید:')
    print(secret['password'])

def create(directory,exe,version,target,notes='',url='',recovery=False):
    from updater import version as parse_version
    parse_version(version);exe=Path(exe);target=Path(target);raw=exe.read_bytes()
    if not raw.startswith(b'MZ') or len(raw)>512*1024*1024:raise ValueError('فایل اجرایی ویندوز معتبر نیست یا بیش از حد بزرگ است.')
    if target.exists():raise ValueError('فایل مقصد از قبل وجود دارد؛ نام تازه انتخاب کنید.')
    if url:
        from urllib.parse import urlsplit
        u=urlsplit(url)
        if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('نشانی بسته باید HTTPS باشد.')
    meta=dict(format='karname-update-v1',version=version,notes=str(notes)[:2000],files={'Karname.exe':dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest())})
    if url:meta['url']=url
    manifest=json.dumps(meta,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode();key=private_key(directory,recovery);sig=key.sign(manifest,padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.MAX_LENGTH),hashes.SHA256());target.parent.mkdir(parents=True,exist_ok=True)
    # Acquire the new destination exclusively before the cleanup handler: a
    # concurrent publisher's existing file must never be removed on collision.
    fd=os.open(str(target),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,'wb') as out,zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('update.json',manifest);z.writestr('update.sig',sig);z.writestr('Karname.exe',raw)
    except Exception:target.unlink(missing_ok=True);raise
    return dict(manifest=base64.b64encode(manifest).decode(),signature=base64.b64encode(sig).decode())

def main():
    parser=argparse.ArgumentParser(description='امضای بسته به‌روزرسانی کارنامه');sub=parser.add_subparsers(dest='command',required=True)
    for name in ('init','recovery','restore','create'):
        x=sub.add_parser(name);x.add_argument('--directory',required=True)
        if name=='init':x.add_argument('--public-key',required=True)
        if name=='create':
            x.add_argument('--exe',required=True);x.add_argument('--version',required=True);x.add_argument('--output',required=True);x.add_argument('--feed-output');x.add_argument('--url',default='');x.add_argument('--notes',default='');x.add_argument('--recovery',action='store_true')
    a=parser.parse_args()
    try:
        if a.command=='init':initialize(a.directory,a.public_key);print('کلید ناشر ساخته شد؛ راهنمای نگهداری امن را بخوانید.')
        elif a.command=='recovery':show_recovery(a.directory)
        elif a.command=='restore':restore(a.directory);print('دسترسی حساب ویندوز به کلید بازیابی شد.')
        else:
            envelope=create(a.directory,a.exe,a.version,a.output,a.notes,a.url,a.recovery)
            if a.feed_output:
                f=Path(a.feed_output)
                with f.open('x',encoding='utf-8') as output:json.dump(envelope,output,ensure_ascii=False)
            print('بسته امضاشده ساخته شد.')
    except Exception as e:print('عملیات انجام نشد:',str(e),file=sys.stderr);return 1
    return 0

if __name__=='__main__':sys.exit(main())
