"""Direct, per-user dashboard editing with drag handles and resize grips."""
import copy
from datetime import date
from PySide6.QtCore import Qt,QMimeData,QPoint,QTimer
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (QApplication,QComboBox,QFrame,QGridLayout,QHBoxLayout,
    QLabel,QMessageBox,QPushButton,QScrollArea,QVBoxLayout,QWidget)
from appearance import palette_for
from home_layout import WIDGET_NAMES,initial_widgets,pack_widgets
from storage import due_on
from theme_catalog import preset
from theme_dashboard import ThemeDashboard,clear
from ui_permissions import allowed

MIME='application/x-karname-home-widget'

class DragHandle(QLabel):
    def __init__(self,key,title,parent):
        super().__init__('جابه‌جایی · '+title,parent);self.key=key;self.origin=None;self.setCursor(Qt.OpenHandCursor);self.setStyleSheet('font-weight:700;');self.setAccessibleName('جابه‌جایی '+title);self.setToolTip('برای جابه‌جایی ویجت را بکشید')
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:self.origin=event.position().toPoint();self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.origin is not None and event.buttons() & Qt.LeftButton and (event.position().toPoint()-self.origin).manhattanLength()>=QApplication.startDragDistance():
            data=QMimeData();data.setData(MIME,self.key.encode('utf-8'));drag=QDrag(self);drag.setMimeData(data);self.origin=None;board=self.parentWidget().board;board.dragging=True
            try:drag.exec(Qt.MoveAction)
            finally:board.dragging=False;QTimer.singleShot(0,board.rebuild)
            self.setCursor(Qt.OpenHandCursor)
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):self.origin=None;self.setCursor(Qt.OpenHandCursor);super().mouseReleaseEvent(event)

class ResizeHandle(QLabel):
    def __init__(self,board,key,parent):
        super().__init__('اندازه ↘',parent);self.board=board;self.key=key;self.start=None;self.setCursor(Qt.SizeFDiagCursor);self.setAccessibleName('تغییر اندازه '+WIDGET_NAMES[key]);self.setToolTip('برای تغییر اندازه بکشید');self.setFixedSize(64,22);self.setAlignment(Qt.AlignCenter)
    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:self.start=event.globalPosition().toPoint()
        super().mousePressEvent(event)
    def mouseReleaseEvent(self,event):
        if self.start is not None:
            delta=event.globalPosition().toPoint()-self.start;self.start=None
            dx=1 if delta.x()>35 else -1 if delta.x()<-35 else 0;dy=1 if delta.y()>35 else -1 if delta.y()<-35 else 0
            if dx or dy:self.board.resize_card(self.key,dx,dy)
        super().mouseReleaseEvent(event)

class EditableCard(QFrame):
    def __init__(self,board,key,content):
        super().__init__();self.board=board;self.key=key;self.setObjectName('EditableCard');self.setAcceptDrops(True)
        root=QVBoxLayout(self);root.setContentsMargins(4,4,4,4);root.setSpacing(2);header=QHBoxLayout();header.setDirection(QHBoxLayout.RightToLeft)
        header.addWidget(DragHandle(key,WIDGET_NAMES[key],self),1);remove=QPushButton('×');remove.setFixedSize(25,25);remove.setAccessibleName('حذف '+WIDGET_NAMES[key]+' از صفحه اصلی');remove.clicked.connect(lambda:self.board.remove_card(key));header.addWidget(remove);root.addLayout(header)
        content.setAttribute(Qt.WA_TransparentForMouseEvents,True);root.addWidget(content,1);footer=QHBoxLayout();footer.addStretch();footer.addWidget(ResizeHandle(board,key,self));root.addLayout(footer)
    def dragEnterEvent(self,event):
        if event.mimeData().hasFormat(MIME):event.acceptProposedAction()
    def dropEvent(self,event):
        try:key=bytes(event.mimeData().data(MIME)).decode('utf-8')
        except UnicodeError:return
        if key in self.board.order and key!=self.key:self.board.move_card(key,self.key,event.position().x()>self.width()/2);event.acceptProposedAction()

class HomeLayoutEditor(ThemeDashboard):
    def __init__(self,owner,parent):
        super().__init__(owner,parent);self.setObjectName('HomeLayoutEditor');self.order=[];self.widths={};self.heights={};self.columns=3;self.current_key='default';self.dragging=False;self.setLayoutDirection(Qt.LeftToRight)
    def resizeEvent(self,event):
        # ThemeDashboard's resize handler rebuilds the normal dashboard; retain
        # this editor and its unsaved drag state while the window is resized.
        QWidget.resizeEvent(self,event)
    def begin(self):
        settings=self.owner.data['settings'];prefs=self.owner.data.get('preferences',{});self.editor_user=(self.owner.session_user or {}).get('id');self.current_key=preset(settings.get('theme_preset','default'));saved=prefs.get('home_widgets')
        use_saved=isinstance(saved,list) and (self.current_key!='default' or prefs.get('home_custom_on_default'))
        order=saved if use_saved else initial_widgets(self.current_key,settings.get('weather_enabled',True),settings.get('daily_quote_enabled',True))
        self.order=list(dict.fromkeys(k for k in order if k in WIDGET_NAMES));self.widths=copy.deepcopy(prefs.get('home_widget_sizes',{})) if use_saved else {};self.heights=copy.deepcopy(prefs.get('home_widget_row_sizes',{})) if use_saved else {};self.columns=max(2,min(4,int(prefs.get('home_widget_columns',3))))
        if not isinstance(self.widths,dict):self.widths={}
        if not isinstance(self.heights,dict):self.heights={}
        self.rebuild();self.show();self.raise_()
    def set_columns(self,value):
        self.columns=value;QTimer.singleShot(0,self.rebuild)
    def move_card(self,key,target,after=False):
        if key not in self.order or target not in self.order:return
        self.order.remove(key);self.order.insert(self.order.index(target)+(1 if after else 0),key)
        if not self.dragging:QTimer.singleShot(0,self.rebuild)
    def resize_card(self,key,dx,dy):
        if key not in self.order:return
        try:width=int(self.widths.get(key,1));height=int(self.heights.get(key,1))
        except (ValueError,TypeError):width=height=1
        self.widths[key]=max(1,min(self.columns,width+dx));self.heights[key]=max(1,min(2,height+dy));QTimer.singleShot(0,self.rebuild)
    def remove_card(self,key):
        if key in self.order:self.order.remove(key);QTimer.singleShot(0,self.rebuild)
    def add_card(self,key):
        if key in WIDGET_NAMES and key not in self.order:self.order.append(key);QTimer.singleShot(0,self.rebuild)
    def rebuild(self):
        clear(self.root);c=palette_for(self.owner.data['settings']);self.setStyleSheet('QWidget#HomeLayoutEditor{background:transparent;} QFrame#EditableCard{background:%s;border:1px dashed %s;border-radius:10px;} QLabel{color:%s;} QPushButton{color:%s;} QScrollArea{background:transparent;border:0;}'%(c['panel'],c['accent'],c['text'],c['text']))
        toolbar=QHBoxLayout();toolbar.setDirection(QHBoxLayout.RightToLeft);heading=QLabel('ویرایش صفحه اصلی');heading.setAccessibleName('ویرایش صفحه اصلی');toolbar.addWidget(heading)
        toolbar.addWidget(QLabel('ستون‌ها'));columns=QComboBox()
        for n in (2,3,4):columns.addItem(str(n),n)
        columns.setCurrentIndex(columns.findData(self.columns));columns.currentIndexChanged.connect(lambda _:self.set_columns(columns.currentData()));toolbar.addWidget(columns)
        choices=QComboBox();choices.setAccessibleName('ویجت برای افزودن')
        for key,name in WIDGET_NAMES.items():
            if key not in self.order:choices.addItem(name,key)
        toolbar.addWidget(choices);add=QPushButton('افزودن');add.setEnabled(choices.count()>0);add.clicked.connect(lambda:self.add_card(choices.currentData()));toolbar.addWidget(add);toolbar.addStretch()
        save=QPushButton('ذخیره چیدمان');save.setObjectName('Primary');save.clicked.connect(self.save);toolbar.addWidget(save);cancel=QPushButton('انصراف');cancel.clicked.connect(self.cancel);toolbar.addWidget(cancel);self.root.addLayout(toolbar)
        hint=QLabel('برای جابه‌جایی، عنوان ویجت را بکشید؛ با گوشه پایین اندازه را تغییر دهید.');hint.setAlignment(Qt.AlignRight);self.root.addWidget(hint)
        area=QScrollArea();area.setWidgetResizable(True);body=QWidget();body.setObjectName('HomeEditorCanvas');grid=QGridLayout(body);grid.setSpacing(8);grid.setContentsMargins(2,2,2,2);area.setWidget(body);self.root.addWidget(area,1)
        events=self.owner.display_events() if allowed(self.owner,'calendar') else [];marked={d for e in events if (d:=self.owner.event_reference_date(e)) and not e.get('done')};factories=self.widget_factories(self.current_key,events,marked)
        for key,row,column,height,width in pack_widgets(self.order,self.widths,self.heights,self.columns):
            content=factories[key]() if key in factories else QLabel('این ویجت در تنظیمات فعلی در دسترس نیست.')
            wrapper=EditableCard(self,key,content);wrapper.setMinimumHeight(120*height);grid.addWidget(wrapper,row,column,height,width);content.show();wrapper.show()
        for column in range(self.columns):grid.setColumnStretch(column,1)
        body.show();area.show()
    def cancel(self):
        self.hide()
        home=self.parentWidget()
        stack=getattr(home,'_react_stack',None)
        if stack is not None:
            rv=getattr(home,'react_view',None);nh=getattr(home,'_react_native_host',None)
            target=rv if rv is not None else nh
            if target is not None:stack.setCurrentWidget(target)
    def save(self):
        if not allowed(self.owner,'settings','edit'):return
        if (self.owner.session_user or {}).get('id')!=self.editor_user:
            self.hide();QMessageBox.warning(self,'ذخیره چیدمان','حساب کاربری تغییر کرده است؛ ویرایش را دوباره باز کنید.');return
        prefs=copy.deepcopy(self.owner.data.get('preferences',{}));prefs.update(home_widgets=list(self.order),home_widget_sizes=copy.deepcopy(self.widths),home_widget_row_sizes=copy.deepcopy(self.heights),home_widget_columns=self.columns,home_customize_v2=True)
        if self.current_key=='default':prefs['home_custom_on_default']=True
        profile=copy.deepcopy((self.owner.session_user or {}).get('profile') or self.owner.data.get('account_profile') or {});profile.update(preferences=prefs)
        oldprefs=self.owner.data.get('preferences',{});oldprofile=self.owner.data.get('account_profile');oldpending=self.owner.data.get('pending_profile_restore')
        try:
            self.owner.data['preferences']=prefs;self.owner.data['account_profile']=profile
            if self.owner.session_user and not getattr(self.owner.org,'client',None):self.owner.data['pending_profile_restore']=profile
            elif self.owner.session_user:self.owner.data.pop('pending_profile_restore',None)
            try:self.owner.persist()
            except Exception:
                self.owner.data['preferences']=oldprefs;self.owner.data['account_profile']=oldprofile
                if oldpending is None:self.owner.data.pop('pending_profile_restore',None)
                else:self.owner.data['pending_profile_restore']=oldpending
                raise
            if self.owner.session_user and getattr(self.owner.org,'client',None):
                from personalization_ui import request_wait
                try:profile=request_wait(self.owner,'profile',profile)
                except Exception:
                    self.owner.data['preferences']=oldprefs;self.owner.data['account_profile']=oldprofile
                    if oldpending is None:self.owner.data.pop('pending_profile_restore',None)
                    else:self.owner.data['pending_profile_restore']=oldpending
                    try:self.owner.persist()
                    except Exception as rollback_error:raise RuntimeError('ذخیره شبکه انجام نشد و بازگرداندن تنظیمات محلی نیز ناموفق بود: '+str(rollback_error)) from None
                    raise
                self.owner.data['account_profile']=profile
            if self.owner.session_user:self.owner.session_user['profile']=profile
            self.cancel();self.owner.refresh()
        except Exception as exc:QMessageBox.warning(self,'ذخیره چیدمان',str(exc))
