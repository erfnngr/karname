"""Open OS sharing/drafts; never send mail automatically."""
import os,subprocess,sys
from pathlib import Path
from urllib.parse import quote
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox,QApplication

def email_draft(parent,path):
    """MAPI_DIALOG requires the user's compose dialog; no recipient is supplied."""
    import ctypes
    from ctypes import wintypes
    U=ctypes.c_uint32
    class File(ctypes.Structure):_fields_=[('reserved',U),('flags',U),('position',U),('path',ctypes.c_wchar_p),('name',ctypes.c_wchar_p),('type',ctypes.c_void_p)]
    class Message(ctypes.Structure):_fields_=[('reserved',U),('subject',ctypes.c_wchar_p),('text',ctypes.c_wchar_p),('type',ctypes.c_wchar_p),('received',ctypes.c_wchar_p),('conversation',ctypes.c_wchar_p),('flags',U),('originator',ctypes.c_void_p),('recipients',U),('recipient_list',ctypes.c_void_p),('file_count',U),('files',ctypes.POINTER(File))]
    attachment=File(0,0,0xFFFFFFFF,str(path),path.name,None);message=Message();message.subject='فایل کارنامه';message.text='فایل پیوست از کارنامه تهیه شده است.';message.file_count=1;message.files=ctypes.pointer(attachment)
    fn=ctypes.WinDLL('MAPI32.dll').MAPISendMailW;fn.argtypes=[ctypes.c_size_t,ctypes.c_size_t,ctypes.POINTER(Message),U,U];fn.restype=U
    result=fn(0,int(parent.winId()),ctypes.byref(message),0x00040008,0)
    return result in (0,1) # success, or user canceled the compose dialog

def share_file(parent,path,email=False):
    path=Path(path).resolve()
    if email:
        if os.name=='nt':
            try:
                if email_draft(parent,path):return
            except (OSError,AttributeError):pass
        QDesktopServices.openUrl(QUrl('mailto:?subject='+quote('فایل کارنامه')))
        QApplication.clipboard().setText(str(path));QMessageBox.information(parent,'پیش‌نویس ایمیل','پیش‌نویس ایمیل باز شد. فایل را از پوشه بازشده پیوست کنید؛ نشانی فایل هم کپی شد.')
    if os.name=='nt':
        # Explorer supplies the installed Windows Share / SendTo handlers.
        subprocess.Popen(['explorer.exe','/select,',str(path)])
        if not email:QMessageBox.information(parent,'اشتراک‌گذاری فایل','فایل در ویندوز انتخاب شد. از گزینه «اشتراک‌گذاری / Share» یا «ارسال به / Send to» ویندوز استفاده کنید.')
    else:QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
