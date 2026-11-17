"""Local UI restrictions mirror, but never replace, server-side authorization."""
from permission_policy import any_allowed

def allowed(owner,module,action='view'):
    actor=getattr(owner,'session_user',None)
    # Standalone verification has no login; real sessions always provide an actor.
    return True if actor is None else any_allowed(actor,module,action)

def gate(owner,module,action='view'):
    if allowed(owner,module,action):return True
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.information(owner,'محدودیت دسترسی','این عملیات برای حساب شما فعال نیست. مدیر شرکت می‌تواند دسترسی را بررسی کند.')
    return False
