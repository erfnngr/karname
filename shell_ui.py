"""A collapsible right sidebar with consistent navigation and optional detail pane."""
from PySide6.QtCore import Qt,QObject,QEvent,QTimer,QSize
from PySide6.QtGui import QKeySequence,QShortcut
from PySide6.QtWidgets import QWidget,QFrame,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QSplitter,QScrollArea,QToolButton,QSizePolicy,QMenu
from ui_icons import symbol

class SidebarController(QObject):
    def __init__(self,owner,sidebar,buttons,toggle):
        super().__init__(owner);self.owner=owner;self.sidebar=sidebar;self.buttons=buttons;self.toggle=toggle;owner.installEventFilter(self);self.apply()
    def eventFilter(self,obj,event):
        if obj is self.owner and event.type()==QEvent.Resize:self.apply()
        return False
    def flip(self):
        prefs=self.owner.data.setdefault('preferences',{});prefs['sidebar_collapsed']=not getattr(self,'collapsed',False);self.owner.persist();self.apply()
    def apply(self):
        from theme_catalog import preset
        from section_themes import resolve_section_theme
        from appearance import palette_for,contrast,accent_foreground
        settings=self.owner.data['settings']
        sb_res=resolve_section_theme(settings,'sidebar')
        sb_over=sb_res['overridden']
        theme_key=preset(settings.get('theme_preset','default'));self.collapsed=self.owner.data.get('preferences',{}).get('sidebar_collapsed',self.owner.width()<(950 if theme_key=='emerald_ivory' else 1250));self.sidebar.setFixedWidth(54 if self.collapsed else 174)
        key=theme_key;top=key in ('glass_mist','violet_modular','bento_grid');self.sidebar.setVisible(not top);self.owner.theme_header.setVisible(top);self.owner.header_bar.setVisible(not top)
        c=sb_res['theme']['colors'] if sb_over else palette_for(settings);emerald=key=='emerald_ivory' and not sb_over
        self.owner.sidebar_brand.setVisible(emerald and not self.collapsed)
        from brand import logo,dark_variant
        from PySide6.QtGui import QPixmap
        from storage import package_file
        if emerald:
            
            if not hasattr(self.owner,'_sidebar_light_logo'):self.owner._sidebar_light_logo=dark_variant(QPixmap(str(package_file('assets/karname.png')))).scaled(28,28,Qt.KeepAspectRatio,Qt.SmoothTransformation)
            self.owner.sidebar_brand_logo.setStyleSheet('background:transparent;');self.owner.sidebar_brand_logo.setPixmap(self.owner._sidebar_light_logo)
        dark=settings.get('theme')=='dark'
        if top:
            brand_sig=(theme_key,dark)
            if getattr(self,'_last_header_brand',None)!=brand_sig:
                self._last_header_brand=brand_sig;fresh=logo('کارنامه',32);self.owner.header_brand_logo.setStyleSheet(fresh.styleSheet());self.owner.header_brand_logo.setPixmap(fresh.pixmap());fresh.deleteLater()

        from brand import gear_icon
        sb_nav_bg=c.get('nav',c['panel'])
        sb_text='#FFFFFF' if sb_over and contrast('#FFFFFF',sb_nav_bg)>=contrast('#111827',sb_nav_bg) else '#111827' if sb_over else (c['text'] if emerald else 'white')
        sb_fg=accent_foreground(c['accent'])
        sb_rad=int((sb_res['theme'].get('tokens') or {}).get('radius',9))
        self.owner.settings_button.setIcon(gear_icon(c['text'] if emerald else sb_text if sb_over else 'white'))
        sb_qss='';hb_qss=''
        use_liquid_sidebar = not sb_over and theme_key in ('default', 'emerald_ivory')
        if sb_over:
            sb_qss=f'QFrame#Panel {{background:{sb_nav_bg};border:1px solid {c["border"]};border-radius:0;}} QScrollArea,QWidget {{background:transparent;}} QPushButton {{background:transparent;color:{sb_text};border:0;text-align:right;padding:8px;}} QPushButton[active="true"] {{background:{c["accent"]};color:{sb_fg};border-radius:{sb_rad}px;}} QPushButton:hover {{background:{c["hover"]};color:{c["text"]};border-radius:{sb_rad}px;}}'
            hb_qss=f'QFrame#Navigation {{background:{sb_nav_bg};border:0;}} QLabel {{color:{sb_text};}} QPushButton,QToolButton {{color:{sb_text};background:transparent;border:0;}} QPushButton:hover,QToolButton:hover {{background:{c["hover"]};color:{c["text"]};}}'
            ac_ss=f'color:{sb_text};font-size:11px;';pt_ss=f'color:{sb_text};padding:5px 10px;font-weight:bold;'
        elif emerald:
            sb_qss='QFrame#Panel {background:%s;border:0;border-radius:0;} QScrollArea,QWidget {background:transparent;} QPushButton {background:transparent;color:#F4FBF5;border:0;text-align:right;padding:8px;} QPushButton[active="true"] {background:transparent;color:#FFFFFF;font-weight:bold;border-radius:9px;} QPushButton:hover {background:transparent;color:#FFFFFF;}'%c['nav']
            hb_qss='QFrame#Navigation {background:%s;} QLabel {color:%s;} QPushButton,QToolButton {color:%s;background:transparent;border:0;}'%(c['bg'],c['text'],c['text']);ac_ss='color:%s;font-size:11px;'%c['text'];pt_ss='color:%s;padding:5px 10px;font-weight:bold;'%c['text']
        else:
            nav=c.get('nav','#12314A')
            sb_qss='QFrame#Panel {background:%s;border:0;border-radius:0;} QScrollArea,QWidget {background:transparent;} QPushButton {background:transparent;color:white;border:0;text-align:right;padding:8px;} QPushButton[active="true"] {background:transparent;color:white;font-weight:bold;border-radius:9px;} QPushButton:hover {background:transparent;color:white;border-radius:9px;}'%(nav)
            hb_qss='QFrame#Navigation {background:%s;border:0;} QLabel {color:white;} QPushButton,QToolButton {color:white;background:transparent;border:0;} QPushButton:hover,QToolButton:hover {background:%s;color:%s;}'%(nav,c['hover'],c['text'])
            ac_ss='color:white;font-size:11px;';pt_ss='color:white;padding:5px 10px;font-weight:bold;'
        if getattr(self,'_last_sb_qss',None)!=sb_qss:self._last_sb_qss=sb_qss;self.sidebar.setStyleSheet(sb_qss)
        if getattr(self,'_last_hb_qss',None)!=hb_qss:self._last_hb_qss=hb_qss;self.owner.header_bar.setStyleSheet(hb_qss)
        if getattr(self,'_last_ac_ss',None)!=ac_ss:self._last_ac_ss=ac_ss;self.owner.account_name.setStyleSheet(ac_ss)
        if getattr(self,'_last_pt_ss',None)!=pt_ss:self._last_pt_ss=pt_ss;self.owner.page_title.setStyleSheet(pt_ss)
        from PySide6.QtWidgets import QBoxLayout
        cal=self.owner.calendar_body;cal.setDirection(QBoxLayout.RightToLeft if key=='violet_modular' else QBoxLayout.LeftToRight);cal.setSpacing(16 if key in ('glass_mist','bento_grid') else 9 if key=='emerald_ivory' else 12);cal.setStretch(0,2 if key in ('violet_modular','glass_mist','bento_grid') else 3);cal.setStretch(1,1 if key!='default' else 2);self.owner.grid.setSpacing(0 if key=='emerald_ivory' else 8 if key in ('glass_mist','bento_grid') else 5)
        btn_sig=(theme_key,dark,self.collapsed,sb_over,c['accent'],c['text'],self.owner.data.get('preferences',{}).get('calendar_name','تقویم'))
        if getattr(self,'_last_btn_sig',None)!=btn_sig:
            self._last_btn_sig=btn_sig
            for bkey,(b,title) in self.buttons.items():
                icon_key={'home':'home','workspace':'check','desk':'desk','attendance':'attendance','month':'month','calendar':'calendar','calculation':'calculator','tax':'tax','services':'open','news':'news','company':'company','chat':'chat','assistant':'assistant','clients':'invoice'}.get(bkey,'open')
                icon_color=sb_text if sb_over else ('#E6F3E9' if emerald else '#72AFC5' if theme_key=='default' else palette_for(settings)['accent']);b.setIcon(symbol(icon_key,icon_color))
                caption=self.owner.data.get('preferences',{}).get('calendar_name','تقویم') if bkey=='calendar' else title
                b.setText(caption if not self.collapsed or isinstance(b,QToolButton) else '');b.setToolTip(caption);b.setAccessibleName(caption);b.setFixedHeight(38);b.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed)
                b.setProperty('flowCustomLiquid',bool(use_liquid_sidebar))
                if sb_over:b.setStyleSheet(f'QPushButton {{background:transparent;color:{sb_text};border:0;text-align:center;padding:6px;}} QPushButton[active="true"], QPushButton[active="true"]:hover {{background:{c["accent"]};color:{sb_fg};border-radius:{sb_rad}px;}} QPushButton:hover {{background:{c["hover"]};color:{c["text"]};border-radius:{sb_rad}px;}}')
                elif emerald:b.setStyleSheet('QPushButton {background:transparent;color:#F3FBF5;border:0;text-align:center;padding:6px;} QPushButton[active="true"], QPushButton[active="true"]:hover {background:transparent;color:#FFFFFF;font-weight:bold;border-radius:9px;} QPushButton:hover {background:transparent;color:#FFFFFF;}')
                if isinstance(b,QToolButton):b.setToolButtonStyle(Qt.ToolButtonIconOnly if self.collapsed else Qt.ToolButtonTextBesideIcon)
                elif not emerald and not sb_over:b.setStyleSheet('padding:7px;' if self.collapsed else 'text-align:center;padding:7px;')
        if hasattr(self.owner,'sidebar_liquid'):
            self.owner.sidebar_liquid.backdrop.setVisible(bool(use_liquid_sidebar))
            self.owner.sidebar_liquid.set_theme(c,dark,theme_key)
        self.owner.sync_theme_nav();self.toggle.setText('' if self.collapsed else 'جمع‌کردن منو');self.toggle.setIcon(symbol('menu','#72AFC5'));self.toggle.setToolTip('باز / بسته کردن منو');self.toggle.setAccessibleName('باز / بسته کردن منو')

def install_shell(o,wrapper,outer,oldbar,gear,help_button):
    from workspace_ui import WorkspacePanel,DetailDrawer,CommandPalette
    o.workspace=WorkspacePanel(o);o.tabs.addTab(o.workspace,'کارها و پیگیری‌ها');o.modules['workspace']=o.workspace
    o.denied_page=QWidget();denied_layout=QVBoxLayout(o.denied_page);denied=QLabel('بخشی برای این حساب فعال نیست؛ مدیر شرکت می‌تواند دسترسی را بررسی کند.');denied.setWordWrap(True);denied_layout.addWidget(denied);denied_layout.addStretch();o.tabs.addTab(o.denied_page,'دسترسی')
    def open_trash():
        from ui_permissions import allowed
        if not allowed(o,'workspace'):return
        o.workspace.refresh_local_trash();o.workspace.recycle.show();o.workspace.recycle.raise_();o.workspace.recycle.activateWindow()
        def fetch_when_ready(attempts=0):
            if o._locking or o._exit_pending or o._exit_approved:return
            if o.workspace.busy:
                if attempts<50:QTimer.singleShot(200,lambda:fetch_when_ready(attempts+1))
            else:o.workspace.refresh()
        fetch_when_ready()
    top=QFrame();o.header_bar=top;top.setObjectName('Navigation');top.setLayoutDirection(Qt.LeftToRight);line=QHBoxLayout(top);line.setContentsMargins(8,4,8,4);line.addWidget(gear);o.settings_button=gear;trash=QPushButton();trash.setIcon(symbol('trash','white'));trash.setToolTip('سطل بازیافت');trash.setAccessibleName('سطل بازیافت');trash.clicked.connect(open_trash);line.addWidget(trash);o.trash_button=trash;line.addWidget(help_button);line.addWidget(o.account_badge);line.addStretch();quick=QPushButton('جستجو و فرمان');quick.setToolTip('دسترسی سریع');quick.clicked.connect(lambda:CommandPalette(o).exec());line.addWidget(quick);o.page_title=QLabel('خانه');o.page_title.setStyleSheet('color:white;padding:5px 10px;font-weight:bold;');line.addWidget(o.page_title);outer.addWidget(top)
    from navigation_shortcuts import toggle_theme,sync_theme
    from liquid_controls import LiquidThemeToggle,LiquidNavEffect,LiquidSidebarEffect,HoverSubmenuController,prepare_glass_menu
    o.theme_button=LiquidThemeToggle();o.theme_button.clicked.connect(lambda:toggle_theme(o));line.insertWidget(2,o.theme_button);sync_theme(o)
    body=QHBoxLayout();body.setContentsMargins(0,0,0,0);body.setSpacing(6);sidebar=QFrame();sidebar.setObjectName('Panel');sv=QVBoxLayout(sidebar);sv.setContentsMargins(5,8,5,8);sv.setSpacing(3);brand_widget=QWidget();brand_widget.setStyleSheet('background:transparent;');brand_row=QHBoxLayout(brand_widget);brand_row.setContentsMargins(6,8,6,12);from brand import logo;o.sidebar_brand_logo=logo('کارنامه',32);brand_row.addWidget(o.sidebar_brand_logo);brand_name=QLabel('کارنامه');brand_name.setStyleSheet('font-size:21px;font-weight:bold;color:white;background:transparent;');brand_row.addWidget(brand_name);sv.addWidget(brand_widget);o.sidebar_brand=brand_widget;toggle=QPushButton('☰');sv.addWidget(toggle);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);content=QWidget();nav=QVBoxLayout(content);nav.setContentsMargins(0,0,0,0);nav.setSpacing(3);scroll.setWidget(content);sv.addWidget(scroll,1);buttons={};titles=dict(home='خانه',workspace='کارها و پیگیری‌ها',clients='فاکتورها',desk='کارتابل من',attendance='تردد و ساعت کار',month='ماه جاری',calendar='تقویم',calculation='محاسبه',services='سامانه‌ها',news='خبرها',company='فضای شرکت',chat='چت',assistant='کارنامه');icons=dict(home='home',workspace='check',desk='edit',attendance='calendar',month='calendar',calendar='calendar',calculation='calculator',services='open',news='news',company='company',chat='chat',assistant='assistant',clients='company')
    titles['tax']='مالیات';icons.update(tax='tax',clients='invoice',desk='desk',attendance='attendance',month='month')
    for key,title in titles.items():
        b=o.nav_buttons.get(key)
        if b is None:b=QPushButton(title);b.clicked.connect(lambda checked=False,key=key:o.tabs.setCurrentWidget(o.modules[key]));o.nav_buttons[key]=b
        b.setProperty('flowShiny',True);b.setParent(content);b.setStyleSheet('text-align:center;padding:7px;');b.setIcon(symbol(icons.get(key,'open'),'#72AFC5'));b.setIconSize(QSize(18,18));nav.addWidget(b);buttons[key]=(b,title)
    nav.addStretch();body.addWidget(sidebar)
    o.sidebar_liquid=LiquidSidebarEffect(content,{k:b for k,(b,_) in buttons.items()})
    # The visual concepts with horizontal navigation retain every permitted
    # section in a compact top strip; the original buttons remain the
    # single source of truth for permissions and user personalization.
    from appearance import palette_for,accent_foreground
    strip=QScrollArea();strip.setWidgetResizable(True);strip.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);strip.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);strip.setFixedHeight(57);strip.setObjectName('ThemeNavigation');navhost=QWidget();navhost.setLayoutDirection(Qt.RightToLeft);navrow=QHBoxLayout(navhost);navrow.setContentsMargins(6,4,6,4);navrow.setSpacing(3);navrow.setAlignment(Qt.AlignRight);mirror={}
    for key,(original,title) in buttons.items():
        item=QPushButton(title);item.setProperty('flowShiny',True);item.setProperty('flowCustomLiquid',True);item.setMinimumHeight(39);item.setIconSize(QSize(18,18));item.setToolTip(title);item.setAccessibleName(title)
        if key=='calendar':item.setMenu(o.calendar_menu)
        elif key=='services':item.setMenu(o.services_menu)
        elif key=='desk':item.setMenu(o.desk_menu)
        else:item.clicked.connect(lambda checked=False,key=key:o.tabs.setCurrentWidget(o.modules[key]))
        navrow.addWidget(item);mirror[key]=item
    navhost.setObjectName('ThemeNavHost');strip.setWidget(navhost);o.theme_nav=strip;o.theme_nav_liquid=LiquidNavEffect(navhost,mirror)
    for m in (o.calendar_menu,o.services_menu,o.desk_menu):prepare_glass_menu(m)
    o.hover_menus=HoverSubmenuController(o,[mirror['calendar'],mirror['services'],mirror['desk'],o.nav_buttons['calendar'],o.nav_buttons['services'],o.nav_buttons['desk']])
    header=QFrame();header.setObjectName('ThemeHeader');header.setLayoutDirection(Qt.RightToLeft);hl=QHBoxLayout(header);hl.setContentsMargins(15,5,15,5);hl.setSpacing(8)
    from brand import logo
    brand_box=QWidget();brand_box.setObjectName('ThemeBrand');bl=QHBoxLayout(brand_box);bl.setContentsMargins(0,0,0,0);bl.setSpacing(3);o.header_brand_logo=logo('کارنامه',32);bl.addWidget(o.header_brand_logo);brand_text=QLabel('کارنامه');brand_text.setObjectName('ThemeBrandText');bl.addWidget(brand_text);hl.addWidget(brand_box)
    hl.addWidget(strip,1);header_gear=QPushButton();from brand import gear_icon;header_gear.setIcon(gear_icon());header_gear.setAccessibleName('تنظیمات');header_gear.setToolTip('تنظیمات');header_gear.clicked.connect(o.settings);hl.addWidget(header_gear);header_trash=QPushButton();header_trash.setIcon(symbol('trash'));header_trash.setToolTip('سطل بازیافت');header_trash.setAccessibleName('سطل بازیافت');header_trash.clicked.connect(open_trash);hl.addWidget(header_trash);header_help=QPushButton('؟');header_help.setToolTip('راهنما');header_help.setAccessibleName('راهنما');header_help.clicked.connect(o.show_guide);hl.addWidget(header_help);header_mode=LiquidThemeToggle();header_mode.setToolTip('تغییر حالت روز و شب');header_mode.setAccessibleName('تغییر حالت روز و شب');header_mode.clicked.connect(lambda:toggle_theme(o));o.theme_header_mode=header_mode;hl.addWidget(header_mode);outer.insertWidget(1,header);o.theme_header=header

    for item in (gear,trash,help_button,o.theme_button,header_gear,header_trash,header_help,header_mode):
        item.setProperty('flowShiny',True);item.setIconSize(QSize(18,18))
    def sync_theme_nav():
        from appearance import menu_stylesheet
        key=o.data['settings'].get('theme_preset','default');dark=o.data['settings'].get('theme')=='dark';c=palette_for(o.data['settings']);fg=accent_foreground(c['accent']);sharp=key in ('orange_grid','paper_ink');rad=2 if sharp else 18 if key in ('blue_cloud','glass_mist','bento_grid') else 9
        header.setStyleSheet('QFrame#ThemeHeader {background:%s;border:0;border-radius:14px;} QWidget#ThemeBrand {background:transparent;} QLabel#ThemeBrandText {background:transparent;color:%s;font-size:20px;font-weight:bold;} QPushButton {color:%s;}'%(c['panel'],c['text'],c['text']));header_gear.setVisible(not gear.isHidden());header_gear.setIcon(gear_icon(c['text']));header_trash.setIcon(symbol('trash',c['text']));header_mode.setVisible(not o.theme_button.isHidden());header_mode.setIcon(symbol('sun' if dark else 'moon',c['text']));header_mode.set_theme_state(dark,palette=c,animate=True)
        mqss=menu_stylesheet(o.data['settings'])
        for m in (getattr(o,'calendar_menu',None),getattr(o,'services_menu',None),getattr(o,'desk_menu',None)):
            if m is not None:m.setStyleSheet(mqss)
        strip.setStyleSheet('QScrollArea#ThemeNavigation, QWidget#ThemeNavHost {background:transparent;border:0;} QPushButton {background:transparent;color:%s;border:0;border-radius:%spx;padding:6px 6px;} QPushButton[active="true"] {background:transparent;color:%s;font-weight:bold;} QPushButton:hover {background:transparent;} QPushButton::menu-indicator {subcontrol-position:center left;left:3px;}'%(c['text'],rad,fg));navhost.setObjectName('ThemeNavHost')
        short={'workspace':'کارها','desk':'کارتابل','attendance':'تردد','company':'شرکت','assistant':'دستیار'}
        for key,(original,title) in buttons.items():
            item=mirror[key];name=original.accessibleName();active=o.tabs.currentWidget() is o.modules.get(key);item.setText(short.get(key,name));item.setToolTip(name);item.setAccessibleName(name);item.setIcon(symbol(icons.get(key,'open'),fg) if active else original.icon());item.setProperty('active',active);item.setVisible(not original.isHidden());item.style().unpolish(item);item.style().polish(item)
        # Preserve all permitted destinations, even in a narrow window. If
        # necessary, secondary labels collapse to icons with accessible names.
        visible=[key for key in buttons if not buttons[key][0].isHidden()]
        # Account for the header controls and both layout margins before
        # deciding which labels can remain visible at narrow laptop widths.
        view_w=strip.viewport().width() if strip.viewport().width()>120 else max(0,o.width()-380)
        available=max(0,min(view_w,max(0,o.width()-360))-4)
        needed=lambda:navrow.contentsMargins().left()+navrow.contentsMargins().right()+sum(mirror[k].sizeHint().width() for k in visible)+max(0,len(visible)-1)*navrow.spacing()
        for key in ('workspace','company','clients','assistant','chat','desk','services','tax','calendar','home'):
            if needed()<=available:break
            if key in visible:mirror[key].setText('')
        o.theme_nav_liquid.set_theme(c,dark,key);QTimer.singleShot(0,lambda:o.theme_nav_liquid.sync_active(animate=True))
    o.sync_theme_nav=sync_theme_nav;o.theme_nav_buttons=mirror
    o.drawer=DetailDrawer(o);o.content_split=QSplitter(Qt.Horizontal);o.content_split.addWidget(o.tabs);o.content_split.addWidget(o.drawer);o.content_split.setStretchFactor(0,1);body.addWidget(o.content_split,1);outer.addLayout(body,1);oldbar.hide();oldbar.deleteLater();o.setCentralWidget(wrapper);o.sidebar=SidebarController(o,sidebar,buttons,toggle);toggle.clicked.connect(o.sidebar.flip)
    def selected(i):
        w=o.tabs.widget(i)
        rv=getattr(w,'react_view',None);st=getattr(w,'_react_stack',None)
        is_react_w=bool(rv is not None and st is not None and st.currentWidget() is rv)
        dirty=getattr(o,'_dirty_theme_widgets',None)
        needs_refresh=bool(isinstance(dirty,set) and w in dirty)
        if needs_refresh:
            dirty.discard(w)
        if not is_react_w:
            from appearance import flush_pending_qss,apply_section_appearances
            if flush_pending_qss() or needs_refresh:
                apply_section_appearances(o)
                if w is getattr(o,'home',None) and hasattr(o,'home'):o.home.refresh()
                elif w is getattr(o,'calendar_page',None) and hasattr(o,'render_calendar'):o.render_calendar();o.render_items()
                elif w is getattr(o,'overview',None) and hasattr(o,'overview'):o.overview.refresh()
                elif w is getattr(o,'services',None) and hasattr(o,'services'):o.services.refresh()
                elif w is getattr(o,'attendance',None) and hasattr(o,'attendance'):o.attendance.update()
                elif w is getattr(o,'chat',None) and hasattr(o,'chat'):o.chat.apply_theme()
                elif w is getattr(o,'ai',None) and hasattr(o,'ai'):o.ai.render()
        elif getattr(rv,'loaded',True):
            if hasattr(rv,'appearance'):rv.appearance.publish()
            if hasattr(rv,'bridge') and hasattr(rv.bridge,'publish'):rv.bridge.publish()
        o.page_title.setText(o.tabs.tabText(i));o.sync_theme_nav()
        for key,(b,_) in buttons.items():b.setProperty('active',o.tabs.currentWidget() is o.modules.get(key));b.style().unpolish(b);b.style().polish(b)
        if hasattr(o,'sidebar_liquid'):o.sidebar_liquid.sync_active()
    def _open_palette():
        from appearance import flush_pending_qss
        flush_pending_qss()
        CommandPalette(o).exec()
    o.tabs.currentChanged.connect(selected);selected(o.tabs.currentIndex());o.command_shortcut=QShortcut(QKeySequence('Ctrl+K'),o);o.command_shortcut.activated.connect(_open_palette);o.org.table.itemSelectionChanged.connect(lambda:o.drawer.record(o.org.selected()) if o.org.selected() else None)
    from v8_controller import V8Controller
    o.v8=V8Controller(o)
    from navigation_shortcuts import install
    install(o)

