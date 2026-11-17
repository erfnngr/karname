"""Keyboard navigation obeys the same visibility and permissions as buttons."""
from PySide6.QtGui import QKeySequence,QShortcut
from ui_permissions import allowed

PAGES=[
    ('Ctrl+Shift+H','home','خانه (H · Home)'),
    ('Ctrl+Shift+T','tax','مالیات (T · Tax)'),
    ('Ctrl+Shift+G','chat','گفتگو / چت (G · Goftego)'),
    ('Ctrl+Shift+A','assistant','دستیار کارنامه (A · Assistant)'),
    ('Ctrl+Shift+C','calendar','تقویم (C · Calendar)'),
    ('Ctrl+Shift+M','month','ماه جاری (M · Month)'),
    ('Ctrl+Shift+W','workspace','کارها و پیگیری‌ها (W · Work)'),
    ('Ctrl+Shift+D','desk','کارتابل من (D · Desk)'),
    ('Ctrl+Shift+F','clients','فاکتورها و مشتریان (F · Factors)'),
    ('Ctrl+Shift+R','attendance','تردد و ساعت کار (R · Attendance)'),
    ('Ctrl+Shift+J','calculation','محاسبه جرایم و حقوق (J · Jaraem)'),
    ('Ctrl+Shift+N','news','خبرها (N · News)'),
    ('Ctrl+Shift+S','services','سامانه‌ها (S · Services)'),
    ('Ctrl+Shift+B','company','فضای شرکت (B · Business)'),
]

def help_text():
    return '\n'.join(
        [title+'  —  '+key for key,_,title in PAGES]
        +[
            'یادآور تازه  —  Ctrl+N',
            'جستجو و فرمان  —  Ctrl+K',
            'تنظیمات  —  Ctrl+,',
            'تغییر حالت شب و روز  —  Ctrl+Shift+L',
            'راهنما  —  F1',
        ]
    )

def activate(owner,key):
    if not allowed(owner,key) or key not in owner.modules:return False
    action_name={'month':'month_action','calculation':'calculation_action','news':'news_action','attendance':'attendance_action'}.get(key)
    button=owner.nav_buttons.get(key)
    if action_name and not getattr(owner,action_name).isVisible():return False
    if not action_name and button and button.isHidden():return False
    if key=='calendar' and not owner.calendar_action.isVisible():return False
    owner.tabs.setCurrentWidget(owner.modules[key]);return True

def sync_theme(owner):
    from ui_icons import symbol
    from appearance import palette_for
    from theme_catalog import preset
    settings=owner.data['settings'];dark=settings.get('theme')=='dark'
    c=palette_for(settings);color=c['text'] if preset(settings.get('theme_preset'))=='emerald_ivory' else '#FFFFFF'
    can_edit=allowed(owner,'settings','edit')
    for button in (getattr(owner,'theme_button',None),getattr(owner,'theme_header_mode',None)):
        if button is None:continue
        button.setText('');button.setToolTip('حالت روز' if dark else 'حالت شب');button.setAccessibleName('تغییر به حالت روز' if dark else 'تغییر به حالت شب');button.setVisible(can_edit)
        button.setIcon(symbol('sun' if dark else 'moon',color))
        if hasattr(button,'set_theme_state'):
            button.set_theme_state(dark,palette=c,animate=True)

def toggle_theme(owner):
    if not allowed(owner,'settings','edit'):return False
    if getattr(owner,'_theme_toggling',False):return False
    from PySide6.QtCore import QTimer
    from appearance import apply_appearance, apply_section_appearances
    owner._theme_toggling=True
    try:
        settings=owner.data['settings'];old=settings.get('theme','light');settings['theme']='light' if old=='dark' else 'dark'
        try:owner.persist()
        except Exception as exc:settings['theme']=old;owner.statusBar().showMessage('تغییر ظاهر ذخیره نشد: '+str(exc),6000);return False
        seq=int(getattr(owner,'_theme_seq',0))+1;owner._theme_seq=seq
        current=owner.tabs.currentWidget() if hasattr(owner,'tabs') else None
        def _is_react_active(w):
            if w is None:return False
            if hasattr(w,'_react_home_active'):
                try:return bool(w._react_home_active())
                except Exception:pass
            rv=getattr(w,'react_view',None);st=getattr(w,'_react_stack',None)
            return bool(rv is not None and st is not None and st.currentWidget() is rv)
        is_react=_is_react_active(current)
        owner.setUpdatesEnabled(False)
        try:
            apply_appearance(settings,defer_qss=is_react)
            if not is_react:
                apply_section_appearances(owner)
            sync_theme(owner)
            if hasattr(owner,'sidebar'):owner.sidebar.apply()
            if is_react:
                rv=getattr(current,'react_view',None)
                if rv is not None and hasattr(rv,'appearance'):
                    rv.appearance.publish()
            dirty=set()
            if hasattr(owner,'tabs'):
                for idx in range(owner.tabs.count()):
                    w=owner.tabs.widget(idx)
                    if w is not None and w is not current:
                        dirty.add(w)
            owner._dirty_theme_widgets=dirty
            if current is getattr(owner,'home',None) and hasattr(owner,'home') and not is_react:
                owner.home.refresh()
            elif current is getattr(owner,'chat',None) and hasattr(owner,'chat') and not is_react:
                owner.chat.apply_theme()
            elif current is getattr(owner,'ai',None) and hasattr(owner,'ai') and not is_react:
                owner.ai.render()
            elif current is getattr(owner,'services',None) and hasattr(owner,'services'):
                owner.services.refresh()
            elif current is getattr(owner,'calendar_page',None) and not is_react and hasattr(owner,'render_calendar'):
                owner.render_calendar();owner.render_items()
        finally:
            owner.setUpdatesEnabled(True)

        def _sync_background_react():
            try:
                from shiboken6 import isValid
                if not isValid(owner):return
            except Exception:pass
            if getattr(owner,'_theme_seq',0)!=seq or getattr(owner,'_locking',False) or getattr(owner,'_exit_approved',False):return
            cur=owner.tabs.currentWidget() if hasattr(owner,'tabs') else None
            if hasattr(owner,'home') and hasattr(owner.home,'react_view') and owner.home._react_home_active():
                owner.home.react_view.bridge.publish()
            for attr in ('home','calendar_page','tax_center','chat','ai'):
                panel=getattr(owner,attr,None)
                if panel is None:continue
                rv=getattr(panel,'react_view',None)
                if rv is not None and getattr(rv,'loaded',True):
                    if hasattr(rv,'appearance'):rv.appearance.publish()
                    if panel is not cur and hasattr(rv,'bridge') and hasattr(rv.bridge,'publish'):rv.bridge.publish()

        timer=getattr(owner,'_theme_bg_timer',None)
        if timer is None:
            timer=QTimer(owner);timer.setSingleShot(True);owner._theme_bg_timer=timer
        else:
            timer.stop()
            try:timer.timeout.disconnect()
            except (RuntimeError,TypeError):pass
        timer.timeout.connect(_sync_background_react)
        timer.start(75)
        return True
    finally:
        owner._theme_toggling=False

def install(owner):
    owner.navigation_shortcuts=[]
    for sequence,key,_ in PAGES:
        shortcut=QShortcut(QKeySequence(sequence),owner);shortcut.activated.connect(lambda key=key:activate(owner,key));owner.navigation_shortcuts.append(shortcut)
    for sequence,fn in [('Ctrl+,',owner.settings),('F1',owner.show_guide),('Ctrl+Shift+L',lambda:toggle_theme(owner))]:
        shortcut=QShortcut(QKeySequence(sequence),owner);shortcut.activated.connect(fn);owner.navigation_shortcuts.append(shortcut)


