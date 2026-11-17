"""Portable password encryption; password and integrity are checked before restore."""
import os,json,struct,io
from pathlib import Path
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

MAGIC=b'KARNAME3\n'
_passwords={}
class PasswordRequired(ValueError):pass

def encrypted(path):
    with open(path,'rb') as f:return f.read(len(MAGIC))==MAGIC

def key(password,salt):
    if not isinstance(password,str) or not password:raise PasswordRequired('رمز پشتیبان را وارد کنید.')
    if len(password)>1000:raise ValueError('رمز پشتیبان حداکثر ۱۰۰۰ نویسه باشد.')
    return Scrypt(salt=salt,length=32,n=32768,r=8,p=1).derive(password.encode('utf-8'))

def seal(raw,password):
    salt=os.urandom(16);nonce=os.urandom(12);header=json.dumps(dict(format='karname-encrypted-v3',salt=salt.hex(),nonce=nonce.hex()),sort_keys=True).encode();aad=MAGIC+struct.pack('>I',len(header))+header
    return aad+AESGCM(key(password,salt)).encrypt(nonce,raw,aad)

def unseal(raw,password):
    if not raw.startswith(MAGIC):return raw
    if not password:raise PasswordRequired('این پشتیبان رمزگذاری شده است.')
    try:
        offset=len(MAGIC);size=struct.unpack('>I',raw[offset:offset+4])[0]
        if not 0<size<=1024:raise ValueError()
        end=offset+4+size;header=json.loads(raw[offset+4:end]);assert header['format']=='karname-encrypted-v3';salt=bytes.fromhex(header['salt']);nonce=bytes.fromhex(header['nonce']);assert len(salt)==16 and len(nonce)==12
        return AESGCM(key(password,salt)).decrypt(nonce,raw[end:],raw[:end])
    except InvalidTag:raise ValueError('رمز نادرست است یا فایل پشتیبان آسیب دیده است.')
    except (KeyError,AssertionError,TypeError,struct.error):raise ValueError('ساختار فایل رمزدار معتبر نیست.')

def source(path,password=None):
    path=Path(path)
    if not encrypted(path):return path
    if path.stat().st_size>1100*1024*1024:raise ValueError('پشتیبان بیش از حد بزرگ است.')
    return io.BytesIO(unseal(path.read_bytes(),password or _passwords.get(str(path.resolve()))))

def unlock_ui(path,parent=None):
    if not encrypted(path):return True
    from PySide6.QtWidgets import QInputDialog,QLineEdit,QMessageBox
    value,ok=QInputDialog.getText(parent,'رمز پشتیبان','رمز فایل پشتیبان:',QLineEdit.Password)
    if not ok:return False
    try:
        from backup_bundle import verify_bundle
        verify_bundle(path,password=value);_passwords[str(Path(path).resolve())]=value;return True
    except ValueError as e:QMessageBox.warning(parent,'بازکردن پشتیبان',str(e));return False
