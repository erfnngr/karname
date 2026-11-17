"""Complete explicit palettes, including all text-bearing controls and popups."""
from PySide6.QtGui import QFontDatabase,QFont,QPalette,QColor
from PySide6.QtWidgets import QApplication
from storage import package_file

LIGHT=dict(bg='#F3F6FA',panel='#FFFFFF',text='#172B45',muted='#496078',border='#C5D1DF',field='#FFFFFF',button='#E4ECF5',hover='#D6E3F2',accent='#066C64',selected='#D9EBFF',today='#D9F1E9',danger='#9F2635',warning='#8C4109')
DARK=dict(bg='#111A28',panel='#1B283B',text='#EFF5FF',muted='#B8C9E0',border='#4B617D',field='#24364D',button='#30465F',hover='#3F5875',accent='#087F76',selected='#244A73',today='#163E37',danger='#FFADB7',warning='#FFD1A3')

def palette_for(settings):
    from theme_catalog import PALETTES,preset
    key=preset(settings.get('theme_preset','default'))
    dark=settings.get('theme')=='dark'
    colors=PALETTES.get(key)
    return dict((colors[1 if dark else 0] if colors else DARK if dark else LIGHT))

def accent_foreground(color):
    return max(('#FFFFFF','#000000'),key=lambda value:contrast(value,color))

def init_font():
    for name in ('Vazirmatn-Regular.ttf','Vazirmatn-Bold.ttf','IRANSans-Regular.ttf','IRANSans-Bold.ttf'):
        QFontDatabase.addApplicationFont(str(package_file('assets/'+name)))
    for fam in ('Vazirmatn','IRANSans','Tahoma','Segoe UI'):
        QFont.insertSubstitutions(fam,['Segoe UI Emoji','Segoe UI Symbol'])

def _build_qss(c, key, mode, size, font, radius, panel_background):
    on_accent=accent_foreground(c['accent']);nav=c.get('nav','#12314A');selection='#2675B8' if key=='default' else c['accent'];selection_fg='white' if key=='default' else on_accent;check='#088C7E' if key=='default' else c['accent'];check_border='#8BE3D7' if key=='default' else on_accent
    up=package_file('assets/control-up.svg').as_posix();down=package_file('assets/control-down.svg').as_posix()
    solid_panel=c['panel']
    return f'''
    QWidget {{ color:{c['text']}; background:{c['bg']}; font-family:"{font}","Tahoma","Segoe UI Emoji","Segoe UI Symbol"; font-size:{size}px; }}
    QDialog,QMessageBox {{ color:{c['text']}; background:{c['bg']}; }}
    QLabel {{ background:transparent; color:{c['text']}; }}
    QWidget#EmptyDay {{background:transparent;}}
    QLabel#Hero {{ font-size:{size+7}px;font-weight:bold;color:{c['text']}; }}
    QLabel#Sub,QLabel#Mini,QLabel#Gregorian {{ color:{c['muted']};font-size:{max(11,size-1)}px; }}
    QLabel#Warning {{color:{c['warning']};}} QLabel#Danger {{color:{c['danger']};}}
    QLabel#DayNumber {{font-size:{size+3}px;font-weight:bold;}}
    QFrame#Panel,QFrame#Day,QFrame#Task,QFrame#Intro {{background:{solid_panel};border:1px solid {c['border']};border-radius:{radius}px;}}
    QFrame#ServiceCard,QFrame#NewsCard {{background:{solid_panel};border:1px solid {c['border']};border-radius:{max(12,radius)}px;}}
    QFrame#ServiceCard:hover,QFrame#NewsCard:hover {{border:1px solid {c['accent']};}}
    QFrame#ServicesToolbar,QFrame#NewsToolbar {{background:{solid_panel};border:1px solid {c['border']};border-radius:{max(12,radius)}px;}}
    QFrame#AssistantComposer {{background:{c['panel']};border:1px solid {c['border']};border-radius:20px;}}
    QPlainTextEdit#AssistantPrompt {{background:transparent;color:{c['text']};border:0;padding:10px;}}
    QFrame#Today {{background:{c['today']};border:2px solid {c['accent']};border-radius:10px;}}
    QFrame#Selected {{background:{c['selected']};border:2px solid #598FD2;border-radius:10px;}}
    QLineEdit,QTextEdit,QPlainTextEdit,QComboBox,QSpinBox,QDoubleSpinBox {{background:{c['field']};color:{c['text']};border:1px solid {c['border']};border-radius:7px;padding:7px;selection-background-color:{selection};selection-color:{selection_fg};}}
    QComboBox {{padding-left:27px;}}
    QComboBox::drop-down {{subcontrol-origin:padding;subcontrol-position:top left;width:20px;border:0;background:transparent;}}
    QComboBox::down-arrow {{image:url("{down}");width:10px;height:10px;}}
    QSpinBox::up-button {{subcontrol-origin:border;subcontrol-position:top left;width:18px;border:0;background:{c['button']};border-top-left-radius:6px;}}
    QSpinBox::down-button {{subcontrol-origin:border;subcontrol-position:bottom left;width:18px;border:0;background:{c['button']};border-bottom-left-radius:6px;}}
    QSpinBox::up-arrow {{image:url("{up}");width:8px;height:8px;}}
    QSpinBox::down-arrow {{image:url("{down}");width:8px;height:8px;}}
    QComboBox QAbstractItemView,QToolTip {{background:{solid_panel};color:{c['text']};selection-background-color:{c['selected']};selection-color:{c['text']};border:1px solid {c['border']};border-radius:8px;padding:4px;outline:0;}}
    QMenu {{background-color:{solid_panel};color:{c['text']};border:1px solid {c['border']};border-radius:12px;padding:7px 6px;}}
    QMenu::item {{background-color:{c['field']};color:{c['text']};padding:9px 18px;border:1px solid {c['border']};border-radius:8px;margin:3px 2px;font-weight:bold;min-width:140px;}}
    QMenu::item:selected {{background-color:{c['selected']};color:{c['text']};border:1px solid {c['accent']};}}
    QMenu::item:disabled {{color:{c['muted']};}}
    QMenu::separator {{height:1px;background:{c['border']};margin:5px 8px;}}
    QListWidget,QTreeWidget {{background:{c['panel']};color:{c['text']};alternate-background-color:{c['field']};border:1px solid {c['border']};border-radius:9px;padding:4px;outline:0;}}
    QListWidget::item,QTreeWidget::item {{color:{c['text']};padding:6px 8px;border-radius:6px;}}
    QListWidget::item:hover,QTreeWidget::item:hover {{background:{c['hover']};color:{c['text']};}}
    QListWidget::item:selected,QTreeWidget::item:selected {{background:{c['selected']};color:{c['text']};}}
    QTableWidget {{background:{c['panel']};alternate-background-color:{c['field']};color:{c['text']};border:1px solid {c['border']};border-radius:9px;gridline-color:{c['border']};selection-background-color:{c['selected']};selection-color:{c['text']};}}
    QTableWidget::item {{padding:6px;border-bottom:1px solid {c['border']};color:{c['text']};}}
    QTableWidget::item:selected {{background:{c['selected']};color:{c['text']};}}
    QHeaderView::section {{background:{c['button']};color:{c['text']};border:0;border-bottom:1px solid {c['border']};padding:7px;font-weight:bold;}}
    QFrame#BoardColumnPanel {{background:{c['bg']};border:1px solid {c['border']};border-radius:10px;}}
    QLabel#BoardColumnTitle {{background:transparent;color:{c['text']};font-weight:bold;padding:6px;}}
    QListWidget#TaskBoard {{background:{c['button']};color:{c['text']};border:1px solid {c['border']};border-radius:8px;padding:6px;outline:0;}}
    QListWidget#TaskBoard::item {{background:{c['panel']};color:{c['text']};border:1px solid {c['border']};border-radius:7px;padding:8px;}}
    QListWidget#TaskBoard::item:hover {{background:{c['hover']};color:{c['text']};}}
    QListWidget#TaskBoard::item:selected {{background:{c['selected']};color:{c['text']};border:1px solid {c['accent']};}}
    QPushButton,QToolButton {{background:{c['button']};color:{c['text']};border:1px solid {c['border']};border-radius:7px;padding:7px 10px;font-weight:bold;}}
    QPushButton:hover,QToolButton:hover {{background:{c['hover']};color:{c['text']};}}
    QPushButton#Primary {{background:{c['accent']};color:{on_accent};border:1px solid {c['accent']};}}
    QPushButton#Small {{padding:5px 7px;font-size:{max(11,size-1)}px;}}
    QPushButton:disabled {{color:{c['muted']};background:{c['bg']};}}
    QCheckBox,QRadioButton {{background:transparent;color:{c['text']};spacing:7px;}}
    QCheckBox::indicator {{width:17px;height:17px;border:1px solid {c['border']};background:{c['field']};border-radius:3px;}}
    QCheckBox::indicator:checked {{background:{check};border:2px solid {check_border};}}
    QTabWidget::pane {{border:0;background:transparent;}}
    QTabBar::tab {{padding:10px 13px;background:{c['button']};color:{c['text']};margin:2px;border-radius:7px;font-weight:bold;}}
    QTabBar::tab:selected {{background:{c['accent']};color:{on_accent};}}
    QScrollArea {{border:0;background:{c['bg']};}}
    QScrollArea > QWidget > QWidget {{background:transparent;}}
    QScrollBar:vertical {{background:transparent;width:7px;margin:2px 0;border:0;}}
    QScrollBar::handle:vertical {{background:{c['border']};min-height:28px;border-radius:3px;}}
    QScrollBar::handle:vertical:hover {{background:{c['muted']};}}
    QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;border:0;background:transparent;}}
    QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {{background:transparent;}}
    QTextBrowser#AssistantTranscript QScrollBar:vertical,QScrollArea#ChatHistory QScrollBar:vertical {{background:transparent;width:5px;margin:2px 0;border:0;}}
    QTextBrowser#AssistantTranscript QScrollBar::handle:vertical,QScrollArea#ChatHistory QScrollBar::handle:vertical {{background:{c['border']};min-height:32px;border:0;border-radius:2px;}}
    QTextBrowser#AssistantTranscript QScrollBar::handle:vertical:hover,QScrollArea#ChatHistory QScrollBar::handle:vertical:hover {{background:{c['muted']};}}
    QTextBrowser#AssistantTranscript QScrollBar::add-line:vertical,QTextBrowser#AssistantTranscript QScrollBar::sub-line:vertical,QScrollArea#ChatHistory QScrollBar::add-line:vertical,QScrollArea#ChatHistory QScrollBar::sub-line:vertical {{height:0;border:0;background:transparent;}}
    QScrollBar:horizontal {{height:7px;margin:0 2px;background:transparent;border:0;}}
    QScrollBar::handle:horizontal {{background:{c['border']};min-width:28px;border-radius:3px;}}
    QScrollBar::handle:horizontal:hover {{background:{c['muted']};}}
    QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {{width:0;border:0;background:transparent;}}
    QScrollBar::add-page:horizontal,QScrollBar::sub-page:horizontal {{background:transparent;}}
    QGroupBox {{color:{c['text']};background:{solid_panel};border:1px solid {c['border']};border-radius:9px;margin-top:15px;padding:12px;}}
    QGroupBox::title {{color:{c['text']};subcontrol-origin:margin;right:15px;padding:0 5px;}}
    QDialogButtonBox {{background:transparent;}}
    QFrame#Navigation {{background:{nav};border:none;}}
    QFrame#Navigation QPushButton,QFrame#Navigation QToolButton {{background:transparent;color:#FFFFFF;border:0;padding:8px 12px;}}
    QFrame#Navigation QPushButton:hover,QFrame#Navigation QToolButton:hover {{background:#24516C;}}
    QFrame#HolidayDay {{background:{'#FFECEF' if mode!='dark' else '#482936'};border:1px solid {c['border']};border-radius:10px;}}
    QLabel#HolidayText {{color:{'#A9364C' if mode!='dark' else '#FFB3C3'};font-weight:bold;}}
    QLabel#Result {{background:{c['today']};color:{c['text']};padding:15px;border-radius:10px;font-size:{size+2}px;}}
    '''

def stylesheet(settings):
    from theme_catalog import preset
    c=palette_for(settings);key=preset(settings.get('theme_preset','default'))
    mode='dark' if settings.get('theme')=='dark' else 'light'
    panel_background=c['panel'] if key=='default' else ('rgba(32,57,72,235)' if mode=='dark' else 'rgba(250,253,255,235)')
    radius=3 if key in ('orange_grid','paper_ink') else 15 if key in ('blue_cloud','glass_mist') else 10
    size=int(settings.get('font_size',13));font=settings.get('font_family','Vazirmatn')
    return _build_qss(c, key, mode, size, font, radius, panel_background)

def section_stylesheet(settings, resolved_theme):
    """Build scoped QSS for an individual Python widget when overridden per section."""
    c=resolved_theme['colors']
    tokens=resolved_theme.get('tokens') or {}
    mode=resolved_theme.get('mode','light')
    radius=int(tokens.get('radius',12))
    scale=float(tokens.get('font_scale',1.0) or 1.0)
    size=max(10,min(22,int(round(int(settings.get('font_size',13))*scale))))
    font=settings.get('font_family','Vazirmatn')
    density=settings.get('density','comfortable');padding=4 if density=='compact' else 8
    return _build_qss(c, resolved_theme.get('id','custom'), mode, size, font, radius, c['panel']) + f'\nQPushButton{{padding:{padding}px 10px;}} QPushButton[active="true"]{{border:1px solid {c["accent"]};background:{c["today"]};font-weight:bold;}}'

def apply_section_appearances(owner):
    """Apply per-section themes to Python modules and notify active React views."""
    from section_themes import resolve_section_theme
    settings=owner.data.get('settings',{})
    qt_targets={
        'workspace':('workspace',),
        'calendar':('calendar_page','overview'),
        'calculation':('calculation_page',),
        'clients':('clients',),
        'desk':('desk',),
        'company':('org',),
        'services':('services','news_panel'),
        'attendance':('attendance',),
        'occasions':('occasions_panel',),
    }
    for sec,attrs in qt_targets.items():
        resolved=resolve_section_theme(settings,sec)
        qss=section_stylesheet(settings,resolved['theme']) if resolved['overridden'] else ''
        for attr in attrs:
            widget=getattr(owner,attr,None)
            if widget is not None and getattr(widget,'_karname_section_qss',None)!=qss:
                widget._karname_section_qss=qss
                widget.setStyleSheet(qss)
    for attr in ('home','calendar_page','chat','ai','tax_center'):
        panel=getattr(owner,attr,None)
        rv=getattr(panel,'react_view',None)
        if rv is not None and hasattr(rv,'appearance'):
            rv.appearance.publish()

def menu_stylesheet(settings):
    c=palette_for(settings)
    solid_panel=c['panel']
    return (
        f'QMenu {{background-color:{solid_panel};color:{c["text"]};border:1px solid {c["border"]};border-radius:12px;padding:7px 6px;}}'
        f' QMenu::item {{background-color:{c["field"]};color:{c["text"]};padding:9px 18px;border:1px solid {c["border"]};border-radius:8px;margin:3px 2px;font-weight:bold;min-width:140px;}}'
        f' QMenu::item:selected {{background-color:{c["selected"]};color:{c["text"]};border:1px solid {c["accent"]};}}'
        f' QMenu::item:disabled {{color:{c["muted"]};}}'
        f' QMenu::separator {{height:1px;background:{c["border"]};margin:5px 8px;}}'
    )

def _refresh_icon_inks(app, ink):
    if not ink or app.property('_karname_icon_ink')==ink:
        return
    app.setProperty('_karname_icon_ink',ink)
    from PySide6.QtWidgets import QAbstractButton
    from ui_icons import symbol,LUCIDE
    for button in app.allWidgets():
        if isinstance(button,QAbstractButton):
            icon_key=button.property('karnameIconKey')
            if icon_key and (icon_key in LUCIDE or icon_key in ('emoji','delete')):
                button.setIcon(symbol(icon_key,ink))

def flush_pending_qss(app=None):
    app=app or QApplication.instance()
    if app is None:return False
    pending=app.property('_karname_pending_qss')
    pending_ink=app.property('_karname_pending_ink')
    changed=False
    if pending:
        app.setProperty('_karname_pending_qss',None)
        if app.property('_karname_full_qss')!=pending:
            app.setStyleSheet(pending)
            app.setProperty('_karname_full_qss',pending)
            changed=True
    if pending_ink:
        app.setProperty('_karname_pending_ink',None)
        _refresh_icon_inks(app,pending_ink)
    return changed
def apply_appearance(settings,defer_qss=False):
    app=QApplication.instance()
    if not app.property('_karname_fusion_set'):
        if app.style() is None or app.style().objectName().lower()!='fusion':
            app.setStyle('Fusion')
        app.setProperty('_karname_fusion_set',True)
    font_family=settings.get('font_family','Vazirmatn');font_size=int(settings.get('font_size',13))
    font_key=(font_family,font_size)
    if app.property('_karname_font_key')!=font_key:
        app.setFont(QFont(font_family,font_size))
        app.setProperty('_karname_font_key',font_key)
    c=palette_for(settings);app.setProperty('karname_dark',settings.get('theme')=='dark');app.setProperty('karname_preset',settings.get('theme_preset','default'))
    palette=QPalette()
    for role,key in ((QPalette.Window,'bg'),(QPalette.WindowText,'text'),(QPalette.Base,'field'),(QPalette.AlternateBase,'panel'),(QPalette.Text,'text'),(QPalette.Button,'button'),(QPalette.ButtonText,'text'),(QPalette.ToolTipBase,'panel'),(QPalette.ToolTipText,'text'),(QPalette.PlaceholderText,'muted')):
        palette.setColor(role,QColor(c[key]))
    is_default=settings.get('theme_preset','default')=='default';highlight='#2675B8' if is_default else c['accent'];palette.setColor(QPalette.Highlight,QColor(highlight));palette.setColor(QPalette.HighlightedText,QColor('white' if is_default else accent_foreground(highlight)))
    app.setPalette(palette);density=settings.get('density','comfortable');padding=4 if density=='compact' else 8
    full_qss=stylesheet(settings)+f'\nQPushButton{{padding:{padding}px 10px;}} QHeaderView::section{{padding:6px;}} QToolTip{{padding:3px 6px;border-radius:6px;font-size:11px;}} QPushButton[active="true"]{{border:1px solid #4D9EAA;background:{c["today"]};font-weight:bold;}}'
    if defer_qss:
        app.setProperty('_karname_pending_qss',full_qss if app.property('_karname_full_qss')!=full_qss else None)
        app.setProperty('_karname_pending_ink',c['text'] if app.property('_karname_icon_ink')!=c['text'] else None)
        from flow_buttons import install
        install(app,c)
        return
    app.setProperty('_karname_pending_qss',None)
    app.setProperty('_karname_pending_ink',None)
    if app.property('_karname_full_qss')!=full_qss:
        app.setStyleSheet(full_qss)
        app.setProperty('_karname_full_qss',full_qss)
    from flow_buttons import install
    install(app,c)
    _refresh_icon_inks(app,c['text'])

def contrast(fg,bg):
    def light(color):
        values=[int(color[i:i+2],16)/255 for i in (1,3,5)]
        values=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
        return sum(v*w for v,w in zip(values,(.2126,.7152,.0722)))
    a,b=sorted((light(fg),light(bg)));return (b+.05)/(a+.05)
