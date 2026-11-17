"""Secrets at rest are bound to the current Windows account using DPAPI."""
import ctypes,os,json,tempfile
from pathlib import Path
from ctypes import wintypes

class Blob(ctypes.Structure):_fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]

def transform(data,decrypt=False):
    if os.name!='nt':raise OSError('ذخیره امن این گزینه به حساب ویندوز نیاز دارد.')
    buffer=ctypes.create_string_buffer(data);source=Blob(len(data),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)));out=Blob();crypt=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    fn=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)];fn.restype=wintypes.BOOL;kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(out)):
        code=ctypes.get_last_error();raise OSError('حساب ویندوز نتوانست اطلاعات امن را باز کند (خطای ویندوز '+str(code)+').')
    try:return ctypes.string_at(out.pbData,out.cbData)
    finally:kernel.LocalFree(out.pbData)

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);raw=transform(json.dumps(value,ensure_ascii=False).encode());fd,temp=tempfile.mkstemp(dir=path.parent,suffix='.secure');os.close(fd)
    try:Path(temp).write_bytes(raw);os.replace(temp,path)
    finally:Path(temp).unlink(missing_ok=True)

def load(path,default=None):
    path=Path(path)
    if not path.exists():return default
    return json.loads(transform(path.read_bytes(),True))
