"""Qt-native scalable icons, accessible names and readable hover labels."""
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication,QStyle
from functools import lru_cache
from storage import package_file

# Lucide icons are distributed under the ISC license in assets/ui-icons/LICENSE.txt.
LUCIDE={'home':'house','check':'list-todo','calendar':'calendar-days','month':'calendar-range','attendance':'clock-3','calculator':'calculator','tax':'file-text','invoice':'receipt-text','desk':'inbox','news':'newspaper','company':'building','chat':'messages-square','assistant':'sparkles','settings':'settings-2','menu':'menu','moon':'moon','sun':'sun','schedule':'calendar-clock','schedule_list':'calendar-days','like':'heart','seen':'check-check','poll':'chart-column','meeting':'calendar-plus','attachment':'paperclip','save':'save','share':'share-2','mail':'mail','add':'folder-plus','edit':'pencil','refresh':'refresh-cw','export':'download','import':'upload','backup':'hard-drive','restore':'rotate-ccw','close':'x','open':'external-link','search':'search'}

ICONS={'save':QStyle.SP_DialogSaveButton,'share':QStyle.SP_DirLinkIcon,'mail':QStyle.SP_MessageBoxInformation,'add':QStyle.SP_FileDialogNewFolder,'edit':QStyle.SP_FileDialogDetailedView,'delete':QStyle.SP_TrashIcon,'refresh':QStyle.SP_BrowserReload,'export':QStyle.SP_DialogSaveButton,'import':QStyle.SP_DialogOpenButton,'backup':QStyle.SP_DriveHDIcon,'restore':QStyle.SP_DirOpenIcon,'close':QStyle.SP_DialogCloseButton,'open':QStyle.SP_ArrowForward,'search':QStyle.SP_FileDialogContentsView}
ICONS['settings']=QStyle.SP_FileDialogContentsView

@lru_cache(maxsize=256)
def symbol(key,color='#19354B'):
    from PySide6.QtCore import QByteArray,Qt
    from PySide6.QtGui import QPixmap,QPainter,QIcon
    from PySide6.QtSvg import QSvgRenderer
    path=package_file('assets/gallery-ui-icons/'+LUCIDE[key]+'.svg') if key in LUCIDE else None
    if path and not path.is_file():path=package_file('assets/ui-icons/'+LUCIDE[key]+'.svg')
    if path and path.is_file():
        from PySide6.QtGui import QColor
        ink=QColor(color).name() if QColor(color).isValid() else '#19354B';raw=path.read_text(encoding='utf-8').replace('currentColor',ink)
        renderer=QSvgRenderer(QByteArray(raw.encode('utf-8')))
        if renderer.isValid():
            pix=QPixmap(26,26);pix.fill(Qt.transparent);p=QPainter(pix);renderer.render(p);p.end();return QIcon(pix)
    shapes={'like':'<path d="M12 20 3.5 11.5C-1 6 6 1 12 7c6-6 13-1 8.5 4.5Z"/>','seen':'<path d="m2 12 4 4 8-9m-2 7 3 3 8-10"/>','emoji':'<circle cx="12" cy="12" r="9"/><path d="M7 14q5 7 10 0"/><path d="M8 8v2m8-2v2"/>','poll':'<path d="M4 20V10h4v10m3 0V4h4v16m3 0v-7h4v7"/>','meeting':'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 2v6m10-6v6M3 11h18m-9 3v4m-2-2h4"/>','attachment':'<path d="m8 13 7-7q4-4 7 0t-1 7L10 23q-5 4-9-1t1-9L13 2"/>'}
    shapes.update({'home':'<path d="m2 11 10-9 10 9M5 9v13h14V9m-10 13v-8h6v8"/>','check':'<rect x="3" y="3" width="18" height="18" rx="4"/><path d="m7 12 3 3 7-7"/>','calendar':'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 2v6m10-6v6M3 11h18m-11 5h1m5 0h1"/>','calculator':'<rect x="5" y="2" width="14" height="21" rx="3"/><path d="M8 6h8m-8 5h1m6 0h1m-8 5h1m6 0h1m-8 4h1m6 0h1"/>','news':'<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M7 8h5v5H7Zm9 0h2m-2 5h2M7 17h11"/>','company':'<path d="M4 22V4h10v18m0-12h6v12M7 8h4m-4 5h4m-4 5h4m6-4h1m-1 4h1"/>','chat':'<path d="M3 4h18v14H8l-5 4Zm4 5h10M7 13h7"/>','open':'<path d="M8 4H3v18h18v-5M13 3h9v9m0-9L10 15"/>','edit':'<path d="m5 17-1 5 5-1L22 8l-4-4ZM15 7l4 4"/>'})
    shapes['assistant']='<path d="M12 2l2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5Z"/>'
    shapes['menu']='<path d="M3 5h18M3 12h18M3 19h18"/>'
    shapes['moon']='<path d="M20 15A9 9 0 0 1 9 4a9 9 0 1 0 11 11Z"/>'
    shapes['sun']='<circle cx="12" cy="12" r="4"/><path d="M12 1v3m0 16v3M1 12h3m16 0h3M4 4l2 2m12 12 2 2M4 20l2-2M18 6l2-2"/>'
    shapes['trash']='<path d="M4 7h16M9 4h6m-9 3 1 14h10l1-14M10 10v8m4-8v8"/>'
    shapes['delete']=shapes['trash']
    shapes['schedule']='<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 3"/>'
    shapes['schedule_list']='<circle cx="7" cy="7" r="4"/><path d="M7 5v2l1.5 1M14 5h7M14 9h7M4 15h17M4 20h17"/>'
    raw='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 26 26"><g transform="translate(1 1)" fill="none" stroke="'+color+'" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'+shapes[key]+'</g></svg>';pix=QPixmap(26,26);pix.fill(Qt.transparent);p=QPainter(pix);QSvgRenderer(QByteArray(raw.encode())).render(p);p.end();return QIcon(pix)
def iconize(button,key,title=None):
    from PySide6.QtGui import QPalette
    title=title or button.text();button.setText('');color=QApplication.palette().color(QPalette.ButtonText).name();button.setIcon(symbol(key,color) if key in LUCIDE or key in ('emoji','poll','meeting','attachment','schedule','schedule_list','delete') else QApplication.style().standardIcon(ICONS[key]));button.setProperty('karnameIconKey',key);button.setIconSize(QSize(21,21));button.setToolTip(title);button.setAccessibleName(title);button.setMinimumSize(38,35)
    if key=='refresh':button.hide()
    return button
